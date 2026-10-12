"""lector.db - local store of BHL search results, page OCR text and saved searches.

Plain rollback journal (no WAL) because the file lives in the OneDrive-synced
data/ folder. Schema version in PRAGMA user_version (see schema.py):
  0/1  harvests up to fix2 (searches, pages, page_hits)
  2    saved searches, runs, review notes (12 Oct 2026)
A database at an older version is not changed silently: LectorStore raises
NeedsMigration and the caller runs schema.migrate() after a backup
(`python -m Lector` asks first; scripts/migrate_lector_v2.py has a dry run).
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from . import config
from .schema import NeedsMigration, create_or_check

__all__ = ["LectorStore", "NeedsMigration", "now"]


def now():
    return datetime.now().isoformat(timespec="seconds")


_now = now                                   # old name, kept for callers


PAGE_COLUMNS = ("item_id", "title_id", "title", "volume", "year", "page_label",
                "page_url", "ocr_url", "page_type", "part_id", "article_title", "authors")


class LectorStore:
    def __init__(self, db_path=None, check_same_thread=True):
        db_path = Path(db_path or config.LECTOR_DB)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.path = db_path
        self.conn = sqlite3.connect(str(db_path), check_same_thread=check_same_thread)
        self.conn.row_factory = sqlite3.Row
        try:
            create_or_check(self.conn)
        except NeedsMigration:
            self.conn.close()
            raise

    def close(self):
        self.conn.commit()
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def commit(self):
        self.conn.commit()

    # --- per-name log (pre-saved-search table, still kept up to date) -----
    def search_done(self, accepted_name, query_name):
        row = self.conn.execute(
            "SELECT 1 FROM searches WHERE accepted_name=? AND query_name=?",
            (accepted_name, query_name)).fetchone()
        return row is not None

    def record_search(self, entry, query_name, role, total, kept):
        self.conn.execute(
            "INSERT OR REPLACE INTO searches VALUES (?,?,?,?,?,?,?)",
            (entry.name, query_name, entry.tvk, role, now(), total, kept))
        self.conn.commit()

    # --- BHL's answer per name, before filters (LEC5: re-filter offline) ---
    def cache_name_hits(self, query_name, pages):
        self.conn.execute("DELETE FROM name_hits WHERE query_name=?", (query_name,))
        self.conn.executemany(
            "INSERT OR REPLACE INTO name_hits (query_name, page_id, record) VALUES (?,?,?)",
            [(query_name, p["page_id"], json.dumps(p, ensure_ascii=False)) for p in pages])
        self.conn.execute(
            "INSERT OR REPLACE INTO name_lookups (query_name, searched_at, pages) VALUES (?,?,?)",
            (query_name, now(), len(pages)))
        self.conn.commit()

    def cached_name_hits(self, query_name):
        """BHL's page list for a name as last fetched, or None if never fetched."""
        if not self.conn.execute("SELECT 1 FROM name_lookups WHERE query_name=?",
                                 (query_name,)).fetchone():
            return None
        return [json.loads(r[0]) for r in self.conn.execute(
            "SELECT record FROM name_hits WHERE query_name=? ORDER BY page_id", (query_name,))]

    def name_lookup(self, query_name):
        return self.conn.execute("SELECT * FROM name_lookups WHERE query_name=?",
                                 (query_name,)).fetchone()

    def forget_name_hits(self, query_names):
        for n in query_names:
            self.conn.execute("DELETE FROM name_hits WHERE query_name=?", (n,))
            self.conn.execute("DELETE FROM name_lookups WHERE query_name=?", (n,))

    # --- pages ----------------------------------------------------------
    def upsert_page(self, page):
        """Insert page metadata, or refresh it from BHL's latest answer
        (year, page type, authors...). Downloaded text is never touched."""
        self.conn.execute("INSERT OR IGNORE INTO pages (page_id) VALUES (?)", (page["page_id"],))
        cols = [c for c in PAGE_COLUMNS if page.get(c) is not None]
        if cols:
            self.conn.execute(
                f"UPDATE pages SET {', '.join(c + '=?' for c in cols)} WHERE page_id=?",
                [page[c] for c in cols] + [page["page_id"]])

    def add_hit(self, page_id, accepted_name, query_name, tvk):
        self.conn.execute(
            "INSERT OR IGNORE INTO page_hits (page_id, accepted_name, query_name, tvk)"
            " VALUES (?,?,?,?)", (page_id, accepted_name, query_name, tvk))

    def add_page_hit(self, page, entry, query_name):
        """Insert page metadata (if new) and link it to this species/name."""
        self.upsert_page(page)
        self.add_hit(page["page_id"], entry.name, query_name, entry.tvk)

    def pages_missing_text(self, accepted_name=None, page_ids=None):
        if page_ids is not None:
            ids = list(page_ids)
            if not ids:
                return []
            marks = ",".join("?" * len(ids))
            rows = self.conn.execute(
                f"SELECT page_id FROM pages WHERE fetched_at IS NULL AND page_id IN ({marks})"
                " ORDER BY year, page_id", ids).fetchall()
            return [r["page_id"] for r in rows]
        rows = self.conn.execute(
            "SELECT DISTINCT p.page_id FROM pages p JOIN page_hits h USING(page_id)"
            " WHERE h.accepted_name=? AND p.fetched_at IS NULL"
            " ORDER BY p.year, p.page_id", (accepted_name,)).fetchall()
        return [r["page_id"] for r in rows]

    def save_text(self, page_id, text, text_source, names_found):
        self.conn.execute(
            "UPDATE pages SET ocr_text=?, text_source=?, names_found=?, fetched_at=?"
            " WHERE page_id=?", (text, text_source, names_found, now(), page_id))
        self.conn.commit()

    # --- reporting ------------------------------------------------------
    def status_rows(self):
        return self.conn.execute(
            "SELECT h.accepted_name, MAX(h.tvk) AS tvk,"
            " COUNT(DISTINCT h.page_id) AS pages,"
            " COUNT(DISTINCT CASE WHEN p.fetched_at IS NOT NULL THEN p.page_id END) AS fetched,"
            " MIN(p.year) AS first_year, MAX(p.year) AS last_year"
            " FROM page_hits h JOIN pages p USING(page_id)"
            " GROUP BY h.accepted_name ORDER BY h.accepted_name").fetchall()

    def species_names(self):
        rows = self.conn.execute(
            "SELECT DISTINCT accepted_name FROM page_hits ORDER BY accepted_name")
        return [r[0] for r in rows]

    def reviewed_count(self, accepted_name):
        """Pages of a species with a review status other than unreviewed, or notes."""
        return self.conn.execute(
            "SELECT COUNT(DISTINCT page_id) FROM page_hits WHERE accepted_name=?"
            " AND (review_status != 'unreviewed' OR COALESCE(notes, '') != '')",
            (accepted_name,)).fetchone()[0]

    def forget_species(self, accepted_name):
        """Drop a species' searches and page links. Page text stays cached, so
        a re-fetch with new filters costs one request per name, not per page.
        BHL's cached name lists go too, so the re-fetch asks BHL afresh."""
        names = [r[0] for r in self.conn.execute(
            "SELECT DISTINCT query_name FROM page_hits WHERE accepted_name=?"
            " UNION SELECT query_name FROM searches WHERE accepted_name=?",
            (accepted_name, accepted_name))]
        n = self.conn.execute("DELETE FROM page_hits WHERE accepted_name=?",
                              (accepted_name,)).rowcount
        self.conn.execute("DELETE FROM searches WHERE accepted_name=?", (accepted_name,))
        self.forget_name_hits(names)
        self.conn.execute(
            "DELETE FROM search_pages WHERE search_id IN (SELECT search_id FROM"
            " saved_searches WHERE target_name=? AND kind='species')", (accepted_name,))
        self.conn.commit()
        return n

    def dossier_rows(self, accepted_name):
        return self.conn.execute(
            "SELECT p.*, GROUP_CONCAT(DISTINCT h.query_name) AS matched_names,"
            " MAX(h.tvk) AS tvk, GROUP_CONCAT(DISTINCT h.review_status) AS statuses,"
            " MAX(h.notes) AS notes, MAX(h.review_tag) AS review_tag"
            " FROM pages p JOIN page_hits h USING(page_id)"
            " WHERE h.accepted_name=? GROUP BY p.page_id", (accepted_name,)).fetchall()

    def pages_for_species(self, accepted_name):
        return self.conn.execute(
            "SELECT p.*, GROUP_CONCAT(DISTINCT h.query_name) AS matched_names"
            " FROM pages p JOIN page_hits h USING(page_id)"
            " WHERE h.accepted_name=? GROUP BY p.page_id"
            " ORDER BY p.year IS NULL, p.year, p.title, p.page_id",
            (accepted_name,)).fetchall()

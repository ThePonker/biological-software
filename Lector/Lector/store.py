"""lector.db - local store of BHL search results and page OCR text.

Plain rollback journal (no WAL) because the file lives in the OneDrive-synced
data/ folder. All schema creation is idempotent.
"""
import sqlite3
from datetime import datetime

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS searches (
    accepted_name TEXT NOT NULL,      -- current UKSI name (or as supplied)
    query_name    TEXT NOT NULL,      -- name actually sent to BHL
    tvk           TEXT,               -- UKSI TVK of the accepted name
    name_role     TEXT NOT NULL,      -- 'accepted' or 'synonym'
    searched_at   TEXT NOT NULL,
    hits_total    INTEGER,            -- pages BHL returned
    hits_kept     INTEGER,            -- pages kept after filters/cap
    PRIMARY KEY (accepted_name, query_name)
);
CREATE TABLE IF NOT EXISTS pages (
    page_id     INTEGER PRIMARY KEY,
    item_id     INTEGER,
    title_id    INTEGER,
    title       TEXT,
    volume      TEXT,
    year        INTEGER,
    page_label  TEXT,                 -- printed page number, e.g. 'p. 147'
    page_url    TEXT,
    ocr_url     TEXT,
    text_source TEXT,                 -- OCR / Text Import / corrected OCR
    ocr_text    TEXT,
    names_found TEXT,                 -- '; '-joined names BHL found on page
    fetched_at  TEXT
);
CREATE TABLE IF NOT EXISTS page_hits (
    page_id       INTEGER NOT NULL REFERENCES pages(page_id),
    accepted_name TEXT NOT NULL,
    query_name    TEXT NOT NULL,
    tvk           TEXT,
    review_status TEXT NOT NULL DEFAULT 'unreviewed',  -- for the review stage
    PRIMARY KEY (page_id, accepted_name, query_name)
);
CREATE INDEX IF NOT EXISTS idx_hits_accepted ON page_hits(accepted_name);
CREATE INDEX IF NOT EXISTS idx_hits_tvk ON page_hits(tvk);
CREATE INDEX IF NOT EXISTS idx_pages_year ON pages(year);
"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


class LectorStore:
    def __init__(self, db_path=config.LECTOR_DB):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.commit()
        self.conn.close()

    # --- searches -------------------------------------------------------
    def search_done(self, accepted_name, query_name):
        row = self.conn.execute(
            "SELECT 1 FROM searches WHERE accepted_name=? AND query_name=?",
            (accepted_name, query_name)).fetchone()
        return row is not None

    def record_search(self, entry, query_name, role, total, kept):
        self.conn.execute(
            "INSERT OR REPLACE INTO searches VALUES (?,?,?,?,?,?,?)",
            (entry.name, query_name, entry.tvk, role, _now(), total, kept))
        self.conn.commit()

    # --- pages ----------------------------------------------------------
    def add_page_hit(self, page, entry, query_name):
        """Insert page metadata (if new) and link it to this species/name."""
        self.conn.execute(
            "INSERT OR IGNORE INTO pages (page_id, item_id, title_id, title, volume,"
            " year, page_label, page_url, ocr_url) VALUES (?,?,?,?,?,?,?,?,?)",
            (page["page_id"], page["item_id"], page["title_id"], page["title"],
             page["volume"], page["year"], page["page_label"], page["page_url"],
             page["ocr_url"]))
        self.conn.execute(
            "INSERT OR IGNORE INTO page_hits (page_id, accepted_name, query_name, tvk)"
            " VALUES (?,?,?,?)", (page["page_id"], entry.name, query_name, entry.tvk))

    def commit(self):
        self.conn.commit()

    def pages_missing_text(self, accepted_name):
        rows = self.conn.execute(
            "SELECT DISTINCT p.page_id FROM pages p JOIN page_hits h USING(page_id)"
            " WHERE h.accepted_name=? AND p.fetched_at IS NULL"
            " ORDER BY p.year, p.page_id", (accepted_name,)).fetchall()
        return [r["page_id"] for r in rows]

    def save_text(self, page_id, text, text_source, names_found):
        self.conn.execute(
            "UPDATE pages SET ocr_text=?, text_source=?, names_found=?, fetched_at=?"
            " WHERE page_id=?", (text, text_source, names_found, _now(), page_id))
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

    def pages_for_species(self, accepted_name):
        return self.conn.execute(
            "SELECT p.*, GROUP_CONCAT(DISTINCT h.query_name) AS matched_names"
            " FROM pages p JOIN page_hits h USING(page_id)"
            " WHERE h.accepted_name=? GROUP BY p.page_id"
            " ORDER BY p.year IS NULL, p.year, p.title, p.page_id",
            (accepted_name,)).fetchall()

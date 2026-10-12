"""lector.db schema, version 3 (12 Oct 2026), and the in-place migration to it.

Version 2 adds, without changing or removing anything already stored:
  pages            + page_type (fix2), part_id, article_title, authors
  page_hits        + notes, review_tag, reviewed_at  (review_status kept as it was)
  saved_searches   one row per saved search (name, target taxon, kind, status)
  search_names     names a search sends to BHL, where each came from, held back or not
  search_filters   the filter set of each search (LEC5)
  runs, run_pages  every run with a snapshot of its settings; which pages were new,
                   unchanged or withdrawn in that run
  search_pages     the pages a search currently holds (current / withdrawn / kept)
  name_hits, name_lookups   BHL's full page list per name, so changed filters can be
                   re-applied without asking BHL again
  journal_presets  word lists such as "British periodicals"
  exports          files written, for the Exports screen
The old per-name `searches` table keeps its name and rows. Each species already
fetched becomes a saved search with one run (migrate_legacy below).

Version 3 (12 Oct 2026, Round 8) adds, again without changing stored rows:
  runs             + name_requests, text_requests (BHL requests split by kind)
  activity         other work shown under Recent activity ("Fetch missing text")
"""
import json
import sqlite3

from .presets import BUILTIN_PRESETS

VERSION = 3


class NeedsMigration(RuntimeError):
    """lector.db was made by an older Lector; run migrate() after a backup."""


LEGACY = """
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

NEW_COLUMNS = {
    "pages": [("page_type", "TEXT"), ("part_id", "INTEGER"), ("article_title", "TEXT"),
              ("authors", "TEXT")],
    "page_hits": [("notes", "TEXT"), ("review_tag", "TEXT"), ("reviewed_at", "TEXT")],
}
V3_COLUMNS = {"runs": [("name_requests", "INTEGER"), ("text_requests", "INTEGER")]}

V2 = """
CREATE TABLE IF NOT EXISTS saved_searches (
    search_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    target_tvk  TEXT,
    target_name TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'species' CHECK (kind IN ('species','family','list')),
    status      TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active')),
    created     TEXT NOT NULL,
    updated     TEXT,
    notes       TEXT
);
CREATE TABLE IF NOT EXISTS search_names (
    search_id        INTEGER NOT NULL REFERENCES saved_searches(search_id),
    name             TEXT NOT NULL,
    origin           TEXT NOT NULL CHECK (origin IN ('accepted','uksi_synonym','user_added')),
    included         INTEGER NOT NULL DEFAULT 1,
    held_back_reason TEXT,
    accepted_name    TEXT NOT NULL,   -- species the name belongs to
    accepted_tvk     TEXT,
    position         INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (search_id, name)
);
CREATE TABLE IF NOT EXISTS search_filters (
    search_id       INTEGER PRIMARY KEY REFERENCES saved_searches(search_id),
    from_year       INTEGER,
    to_year         INTEGER,
    journal_preset  TEXT,
    include_words   TEXT NOT NULL DEFAULT '[]',   -- JSON list, whole words
    exclude_words   TEXT NOT NULL DEFAULT '[]',
    max_pages       INTEGER,                      -- per name; NULL or 0 = no cap
    skip_index      INTEGER NOT NULL DEFAULT 0,
    skip_duplicates INTEGER NOT NULL DEFAULT 1,
    recorded        INTEGER NOT NULL DEFAULT 1    -- 0: filters of a pre-12-Oct fetch unknown
);
CREATE TABLE IF NOT EXISTS runs (
    run_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id INTEGER NOT NULL REFERENCES saved_searches(search_id),
    started   TEXT NOT NULL,
    finished  TEXT,
    mode      TEXT NOT NULL CHECK (mode IN ('count','fetch')),
    settings  TEXT NOT NULL,          -- JSON snapshot: names + filters used
    found     INTEGER,                -- distinct pages BHL returned for the names
    kept      INTEGER,                -- pages within the filters
    requests  INTEGER,
    failed    INTEGER,
    status    TEXT NOT NULL DEFAULT 'running',  -- running/done/cancelled/failed/migrated
    message   TEXT,
    name_requests INTEGER,            -- v3: BHL name searches in this run
    text_requests INTEGER             -- v3: BHL page-text downloads in this run
);
CREATE TABLE IF NOT EXISTS run_pages (
    run_id        INTEGER NOT NULL REFERENCES runs(run_id),
    page_id       INTEGER NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('new','unchanged','withdrawn')),
    matched_names TEXT,
    PRIMARY KEY (run_id, page_id)
);
CREATE TABLE IF NOT EXISTS search_pages (
    search_id     INTEGER NOT NULL REFERENCES saved_searches(search_id),
    page_id       INTEGER NOT NULL,
    state         TEXT NOT NULL CHECK (state IN ('current','withdrawn','kept')),
    matched_names TEXT,
    first_run     INTEGER,
    last_run      INTEGER,
    PRIMARY KEY (search_id, page_id)
);
CREATE TABLE IF NOT EXISTS name_hits (
    query_name TEXT NOT NULL,
    page_id    INTEGER NOT NULL,
    record     TEXT NOT NULL,         -- JSON page record as extract_pages() gives it
    PRIMARY KEY (query_name, page_id)
);
CREATE TABLE IF NOT EXISTS name_lookups (
    query_name  TEXT PRIMARY KEY,
    searched_at TEXT NOT NULL,
    pages       INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS journal_presets (
    name          TEXT PRIMARY KEY,
    description   TEXT,
    include_words TEXT NOT NULL DEFAULT '[]',
    exclude_words TEXT NOT NULL DEFAULT '[]',
    builtin       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS exports (
    export_id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id INTEGER,
    created   TEXT NOT NULL,
    kind      TEXT NOT NULL,
    path      TEXT NOT NULL,
    pages     INTEGER
);
CREATE TABLE IF NOT EXISTS activity (
    activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id   INTEGER,
    started     TEXT NOT NULL,
    finished    TEXT,
    kind        TEXT NOT NULL,        -- 'fetch_text'
    status      TEXT,                 -- done / cancelled / failed
    text        TEXT,                 -- plain English, as Recent activity shows it
    requests    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_run_pages_page ON run_pages(page_id);
CREATE INDEX IF NOT EXISTS idx_search_pages_page ON search_pages(page_id);
CREATE INDEX IF NOT EXISTS idx_runs_search ON runs(search_id);
"""


def _tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def version(conn):
    return conn.execute("PRAGMA user_version").fetchone()[0]


def needs_migration(conn):
    return "pages" in _tables(conn) and version(conn) < VERSION


def create_or_check(conn):
    """Create a new database, or check an existing one is at VERSION."""
    if needs_migration(conn):
        raise NeedsMigration(
            "lector.db was made by an older Lector and needs updating (new tables for "
            "saved searches; nothing stored is changed).")
    if version(conn) < VERSION:                      # brand-new file
        _apply(conn)
        conn.execute(f"PRAGMA user_version = {VERSION}")
        conn.commit()


def _add_columns(conn, columns):
    for table, cols in columns.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, typ in cols:
            if col not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")


def _apply(conn):
    conn.executescript(LEGACY)
    _add_columns(conn, NEW_COLUMNS)
    conn.executescript(V2)
    _add_columns(conn, V3_COLUMNS)              # runs made by version 2
    for p in BUILTIN_PRESETS:
        conn.execute(
            "INSERT OR IGNORE INTO journal_presets (name, description, include_words,"
            " exclude_words, builtin) VALUES (?,?,?,?,1)",
            (p["name"], p["description"], json.dumps(p["include"]), json.dumps(p["exclude"])))


def counts(conn):
    """Row counts for the before/after report."""
    t = _tables(conn)
    out = {}
    for table in ("searches", "pages", "page_hits", "saved_searches", "search_names",
                  "runs", "run_pages", "search_pages", "journal_presets", "activity"):
        out[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] \
            if table in t else None
    if "pages" in t:
        out["pages with text"] = conn.execute(
            "SELECT COUNT(*) FROM pages WHERE fetched_at IS NOT NULL").fetchone()[0]
    if "page_hits" in t:
        out["reviewed hits"] = conn.execute(
            "SELECT COUNT(*) FROM page_hits WHERE review_status != 'unreviewed'").fetchone()[0]
    return out


def migrate(conn, check=None):
    """Bring an older lector.db to VERSION in place. Returns the saved searches made
    (only a database from before saved searches, version 0/1, gets them).
    check(name, tvk) -> candidate_names() list, used to check the old names (see
    migrate_legacy); None when UKSI is not at hand."""
    conn.row_factory = sqlite3.Row
    start = version(conn)
    with conn:
        _apply(conn)
        made = migrate_legacy(conn, check) if start < 2 else []
        conn.execute(f"PRAGMA user_version = {VERSION}")
    return made


def checked_names(name, tvk, old_names, check, accepted=()):
    """The names a migrated search starts with: [(name, origin, included, reason)].

    The old fetches' names are history, not your choices (L5, Round 8): each is
    checked as a new search's names are (candidate_names: UKSI synonym checks and
    your synonym list). A name the checks hold back is stored unticked with the
    reason; the held-back names the old fetch never used are listed too, unticked.
    Without check (no UKSI) the names are stored as fetched."""
    cands = {}
    if check is not None and tvk:
        try:
            cands = {c["name"].lower(): c for c in check(name, tvk)}
        except Exception:  # noqa: BLE001 - UKSI unreadable: keep the names as fetched
            cands = {}
    out = []
    for n in old_names:
        c = cands.get(n.lower())
        origin = "accepted" if n == name or n in accepted else "uksi_synonym"
        held = c is not None and not c["included"]
        out.append((n, origin, 0 if held else 1, c["held_back_reason"] if held else None))
    have = {n.lower() for n in old_names}
    for key, c in cands.items():
        if key not in have and not c["included"]:
            out.append((c["name"], "uksi_synonym", 0, c["held_back_reason"]))
    return out


def migrate_legacy(conn, check=None):
    """Each species fetched before saved searches existed becomes a saved search
    named after it, with its names (checked: see checked_names) and one run holding
    the pages it has. The filters of those fetches were never stored: recorded=0."""
    rows = conn.execute(
        "SELECT accepted_name, MAX(tvk) AS tvk FROM ("
        " SELECT accepted_name, tvk FROM searches UNION ALL"
        " SELECT accepted_name, tvk FROM page_hits) GROUP BY accepted_name"
        " ORDER BY accepted_name").fetchall()
    made = []
    for r in rows:
        name, tvk = r["accepted_name"], r["tvk"]
        if conn.execute("SELECT 1 FROM saved_searches WHERE kind='species' AND target_name=?",
                        (name,)).fetchone():
            continue
        logs = conn.execute("SELECT * FROM searches WHERE accepted_name=? ORDER BY searched_at",
                            (name,)).fetchall()
        hit_names = [x[0] for x in conn.execute(
            "SELECT DISTINCT query_name FROM page_hits WHERE accepted_name=?", (name,))]
        names = list(dict.fromkeys([g["query_name"] for g in logs] + hit_names)) or [name]
        roles = {g["query_name"]: g["name_role"] for g in logs}
        started = logs[0]["searched_at"] if logs else "2026-10-07T00:00:00"
        finished = logs[-1]["searched_at"] if logs else started
        sid = conn.execute(
            "INSERT INTO saved_searches (name, target_tvk, target_name, kind, status, created,"
            " notes) VALUES (?,?,?,?,?,?,?)",
            (name, tvk, name, "species", "active", started,
             "Made from the command-line fetches before saved searches (12 Oct 2026).")
        ).lastrowid
        ordered = sorted(names, key=lambda x: (x != name, x))
        checked = checked_names(name, tvk, ordered, check,
                                {k for k, v in roles.items() if v == "accepted"})
        for i, (n, origin, inc, reason) in enumerate(checked):
            conn.execute(
                "INSERT INTO search_names (search_id, name, origin, included, held_back_reason,"
                " accepted_name, accepted_tvk, position) VALUES (?,?,?,?,?,?,?,?)",
                (sid, n, origin, inc, reason, name, tvk, i))
        conn.execute("INSERT INTO search_filters (search_id, max_pages, recorded)"
                     " VALUES (?, NULL, 0)", (sid,))
        pages = conn.execute(
            "SELECT h.page_id, GROUP_CONCAT(DISTINCT h.query_name) AS m,"
            " MAX(p.fetched_at IS NULL) AS missing FROM page_hits h JOIN pages p USING(page_id)"
            " WHERE h.accepted_name=? GROUP BY h.page_id", (name,)).fetchall()
        settings = {"names": names, "filters": None,
                    "note": "Fetched with the command line before 12 Oct 2026; the filters "
                            "used were not recorded."}
        rid = conn.execute(
            "INSERT INTO runs (search_id, started, finished, mode, settings, found, kept,"
            " requests, failed, status, message) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (sid, started, finished, "fetch", json.dumps(settings),
             sum(g["hits_total"] or 0 for g in logs) if logs else None, len(pages), None,
             sum(p["missing"] for p in pages), "migrated",
             "Run made from the stored pages when saved searches were added.")).lastrowid
        conn.executemany(
            "INSERT INTO run_pages (run_id, page_id, status, matched_names) VALUES (?,?,'new',?)",
            [(rid, p["page_id"], p["m"]) for p in pages])
        conn.executemany(
            "INSERT INTO search_pages (search_id, page_id, state, matched_names, first_run,"
            " last_run) VALUES (?,?,'current',?,?,?)",
            [(sid, p["page_id"], p["m"], rid, rid) for p in pages])
        made.append({"search_id": sid, "name": name, "names": names, "pages": len(pages),
                     "held_back": [[n, r] for n, _o, inc, r in checked if not inc]})
    return made

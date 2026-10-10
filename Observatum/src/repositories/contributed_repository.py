"""Read-only access to contributed records (backlog K1, 9 Oct 2026).

`contributed_observations` in observatum.db holds records other people sent Wil
(loaded by scripts/import_contributed.py). The Contributed tab browses them; nothing
here writes. Plain functions over a sqlite3 connection so the tests can run them
against an in-memory table; the tab opens the real database with open_ro().

    conn = open_ro(paths.OBSERVATUM_DB)
    groups = list_groups(conn)
    rows = fetch_records(conn, contributor="Moore, J.", text="Carabus")
"""
import sqlite3

from shared.db_open import connect_ro

TABLE = "contributed_observations"

# (column, heading) in display order -- only columns the table actually has.
COLUMNS = [
    ("species_name", "Species"),
    ("common_name", "Common name"),
    ("date", "Date"),
    ("grid_ref", "Grid ref"),
    ("site_name", "Site"),
    ("quantity", "Qty"),
    ("stage", "Stage"),
    ("sex", "Sex"),
    ("recorder", "Recorder"),
    ("determiner", "Determiner"),
    ("method", "Method"),
    ("vice_county", "Vice-county"),
    ("project_name", "Project"),
    ("client", "Client"),
    ("contributor", "Contributor"),
    ("source_file", "Source file"),
    ("received_date", "Received"),
    ("permission", "Permission"),
    ("import_batch", "Import batch"),
    ("comment", "Comment"),
]

# Columns the free-text filter searches.
TEXT_COLUMNS = ("species_name", "common_name", "family", "order_name", "grid_ref",
                "site_name", "sub_location", "recorder", "determiner", "method",
                "comment", "project_name", "client", "source_file")


def open_ro(db_path) -> sqlite3.Connection:
    """Open observatum.db read-only (a stray write fails loudly)."""
    return connect_ro(db_path)


def has_table(conn) -> bool:
    """True if this database has the contributed_observations table."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (TABLE,)).fetchone()
    return row is not None


def list_groups(conn) -> list:
    """One dict per (contributor, project, batch) with its record count, sorted.

    Keys: contributor, project_name, import_batch, source_file, received_date, n.
    A batch normally comes from one file; if it spans several, they are joined.
    """
    sql = f"""
        SELECT contributor, project_name, import_batch,
               GROUP_CONCAT(DISTINCT source_file) AS source_file,
               MAX(received_date) AS received_date,
               COUNT(*) AS n
        FROM {TABLE}
        GROUP BY contributor, project_name, import_batch
        ORDER BY contributor COLLATE NOCASE, project_name COLLATE NOCASE, import_batch
    """
    return _rows(conn, sql)


def fetch_records(conn, contributor=None, project=..., batch=..., text="") -> list:
    """Contributed records as dicts (every column), filtered and sorted.

    `contributor` None means all. `project` / `batch` use Ellipsis for "all", so that
    None can mean "records with no project" / "no batch" (the tree shows those too).
    `text`: every word of it in one of TEXT_COLUMNS (case-insensitive), or the species it
    names -- by TVK, through the shared species search (typing slips, old and common names;
    10 Oct 2026).
    """
    where, params = [], []
    if contributor is not None:
        where.append("contributor = ?")
        params.append(contributor)
    if project is not ...:
        where.append("project_name IS ?")
        params.append(project)
    if batch is not ...:
        where.append("import_batch IS ?")
        params.append(batch)
    text = (text or "").strip()
    if text:
        from shared.species_filter import sql_for_table
        words = []
        for w in text.split():
            like = "%" + w.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            words.append("(" + " OR ".join(
                f"COALESCE({c}, '') LIKE ? ESCAPE '\\'" for c in TEXT_COLUMNS) + ")")
            params.extend([like] * len(TEXT_COLUMNS))
        sp_clause, sp_params = sql_for_table(
            text, lambda q, p=(): conn.execute(q, p).fetchall(), TABLE)
        where.append("((" + " AND ".join(words) + ") OR " + sp_clause + ")")
        params.extend(sp_params)
    sql = f"SELECT * FROM {TABLE}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY species_name COLLATE NOCASE, date, id"
    return _rows(conn, sql, params)


def _rows(conn, sql, params=()):
    cur = conn.execute(sql, params)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]

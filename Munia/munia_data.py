"""Munia data layer — capacity planning with April-March business year."""

import sqlite3
from pathlib import Path

# Business year: April to March. "Year 2026" = Apr 2026 – Mar 2027
BIZ_MONTHS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]
BIZ_LABELS = ["Apr", "May", "Jun", "Jul", "Aug", "Sep",
              "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
FIELD_MONTHS = {4, 5, 6, 7}
MICRO_MONTHS = {8, 9, 10}
REPORT_MONTHS = {11, 12}
SEASON_DAYS = 15

def current_biz_year() -> int:
    from datetime import date
    t = date.today()
    return t.year if t.month >= 4 else t.year - 1

def _resolve_db() -> Path:
    try:
        import paths
        if hasattr(paths, "MUNIA_DB"):
            return Path(paths.MUNIA_DB)
        return Path(paths.DATA_DIR) / "munia.db"
    except ImportError:
        return Path(__file__).resolve().parent.parent / "data" / "munia.db"

DB_PATH = _resolve_db()

def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn

def ensure_schema(conn: sqlite3.Connection):
    _migrate(conn)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS capacity (
            year INTEGER NOT NULL, month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
            field_budget REAL DEFAULT 0, PRIMARY KEY (year, month));
        CREATE TABLE IF NOT EXISTS annual_capacity (
            year INTEGER PRIMARY KEY, micro_budget REAL DEFAULT 0,
            report_budget REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_year INTEGER NOT NULL, end_year INTEGER NOT NULL,
            project_name TEXT NOT NULL, client TEXT DEFAULT '',
            status TEXT DEFAULT 'quoted' CHECK(status IN (
                'quoted','accepted','complete','declined','no_response')),
            quote_value REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(start_year, project_name));
        CREATE TABLE IF NOT EXISTS project_field_months (
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
            field_days REAL DEFAULT 0, PRIMARY KEY (project_id, year, month));
        CREATE TABLE IF NOT EXISTS project_annual_days (
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            year INTEGER NOT NULL, micro_days REAL DEFAULT 0, report_days REAL DEFAULT 0,
            id_deadline TEXT DEFAULT '', report_deadline TEXT DEFAULT '',
            notes TEXT DEFAULT '', PRIMARY KEY (project_id, year));
        CREATE INDEX IF NOT EXISTS idx_projects_years ON projects(start_year, end_year);
    """)
    conn.commit()

def _migrate(conn):
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(projects)").fetchall()]
        if not cols:
            return
        if "start_year" not in cols:
            for t in ("capacity", "annual_capacity", "projects",
                      "project_field_months", "project_annual_days",
                      "project_months", "day_entries",
                      "sync_settings", "sync_log", "planned_days"):
                conn.execute(f"DROP TABLE IF EXISTS {t}")
            conn.commit()
            return
        if "id_deadline" in cols:
            ad_cols = [r[1] for r in
                       conn.execute("PRAGMA table_info(project_annual_days)").fetchall()]
            if "id_deadline" not in ad_cols:
                conn.execute("ALTER TABLE project_annual_days ADD COLUMN id_deadline TEXT DEFAULT ''")
                conn.execute("ALTER TABLE project_annual_days ADD COLUMN report_deadline TEXT DEFAULT ''")
                conn.execute("ALTER TABLE project_annual_days ADD COLUMN notes TEXT DEFAULT ''")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS projects_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_year INTEGER NOT NULL, end_year INTEGER NOT NULL,
                    project_name TEXT NOT NULL, client TEXT DEFAULT '',
                    status TEXT DEFAULT 'quoted' CHECK(status IN (
                        'quoted','accepted','complete','declined','no_response')),
                    quote_value REAL DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(start_year, project_name));
                INSERT INTO projects_new (id, start_year, end_year, project_name,
                    client, status, quote_value, created_at)
                SELECT id, start_year, end_year, project_name, client,
                       status, quote_value, created_at FROM projects;
                DROP TABLE projects;
                ALTER TABLE projects_new RENAME TO projects;
            """)
            conn.commit()
    except Exception:
        pass

def get_field_capacity(conn, year: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM capacity WHERE year = ? ORDER BY month", (year,)).fetchall()
    existing = {r["month"] for r in rows}
    for m in range(1, 13):
        if m not in existing:
            default = SEASON_DAYS if m in FIELD_MONTHS else 0
            conn.execute("INSERT OR IGNORE INTO capacity (year, month, field_budget) "
                         "VALUES (?, ?, ?)", (year, m, default))
    if len(existing) < 12:
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM capacity WHERE year = ? ORDER BY month", (year,)).fetchall()
    return [dict(r) for r in rows]

def get_annual_capacity(conn, year: int) -> dict:
    row = conn.execute("SELECT * FROM annual_capacity WHERE year = ?", (year,)).fetchone()
    if row:
        return dict(row)
    micro = SEASON_DAYS * len(MICRO_MONTHS)
    report = SEASON_DAYS * len(REPORT_MONTHS)
    conn.execute("INSERT INTO annual_capacity (year, micro_budget, report_budget) "
                 "VALUES (?, ?, ?)", (year, micro, report))
    conn.commit()
    return {"year": year, "micro_budget": micro, "report_budget": report}

def get_projects_for_year(conn, year: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM projects WHERE start_year <= ? AND end_year >= ? "
        "ORDER BY project_name", (year, year)).fetchall()
    return [dict(r) for r in rows]

def add_project(conn, data: dict) -> int:
    cur = conn.execute(
        "INSERT INTO projects (start_year, end_year, project_name, client, "
        "status, quote_value) VALUES (?, ?, ?, ?, ?, ?)",
        (data["start_year"], data["end_year"], data["project_name"],
         data.get("client", ""), data.get("status", "quoted"),
         data.get("quote_value", 0)))
    conn.commit()
    return cur.lastrowid

def update_project(conn, project_id: int, data: dict):
    allowed = {"start_year", "end_year", "project_name", "client",
               "status", "quote_value"}
    sets = {k: v for k, v in data.items() if k in allowed}
    if not sets:
        return
    clause = ", ".join(f"{k} = ?" for k in sets)
    conn.execute(f"UPDATE projects SET {clause} WHERE id = ?",
                 [*sets.values(), project_id])
    conn.commit()

def delete_project(conn, project_id: int):
    conn.execute("DELETE FROM project_field_months WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM project_annual_days WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()

def get_project_field_months(conn, project_id: int, year: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM project_field_months WHERE project_id = ? AND year = ? "
        "ORDER BY month", (project_id, year)).fetchall()
    return [dict(r) for r in rows]

def set_project_field_months(conn, project_id: int, year: int, months: list[dict]):
    conn.execute("DELETE FROM project_field_months WHERE project_id = ? AND year = ?",
                 (project_id, year))
    for m in months:
        if m.get("field_days", 0):
            conn.execute("INSERT INTO project_field_months "
                         "(project_id, year, month, field_days) VALUES (?, ?, ?, ?)",
                         (project_id, year, m["month"], m["field_days"]))
    conn.commit()

def get_project_annual_days(conn, project_id: int, year: int) -> dict:
    row = conn.execute(
        "SELECT * FROM project_annual_days WHERE project_id = ? AND year = ?",
        (project_id, year)).fetchone()
    if row:
        return dict(row)
    return {"micro_days": 0, "report_days": 0,
            "id_deadline": "", "report_deadline": "", "notes": ""}

def set_project_annual_days(conn, project_id: int, year: int, data: dict):
    conn.execute(
        "INSERT OR REPLACE INTO project_annual_days "
        "(project_id, year, micro_days, report_days, "
        "id_deadline, report_deadline, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_id, year, data.get("micro_days", 0), data.get("report_days", 0),
         data.get("id_deadline", ""), data.get("report_deadline", ""),
         data.get("notes", "")))
    conn.commit()

def get_project_field_total(conn, project_id: int) -> float:
    row = conn.execute("SELECT COALESCE(SUM(field_days), 0) AS t "
                       "FROM project_field_months WHERE project_id = ?",
                       (project_id,)).fetchone()
    return row["t"]

def get_project_micro_total(conn, project_id: int) -> float:
    row = conn.execute("SELECT COALESCE(SUM(micro_days), 0) AS t "
                       "FROM project_annual_days WHERE project_id = ?",
                       (project_id,)).fetchone()
    return row["t"]

def get_project_report_total(conn, project_id: int) -> float:
    row = conn.execute("SELECT COALESCE(SUM(report_days), 0) AS t "
                       "FROM project_annual_days WHERE project_id = ?",
                       (project_id,)).fetchone()
    return row["t"]

def get_field_totals_by_month(conn, year: int, statuses: tuple) -> dict:
    ph = ",".join("?" for _ in statuses)
    rows = conn.execute(
        f"SELECT fm.month, SUM(fm.field_days) AS total "
        f"FROM project_field_months fm JOIN projects p ON fm.project_id = p.id "
        f"WHERE fm.year = ? AND p.status IN ({ph}) GROUP BY fm.month",
        (year, *statuses)).fetchall()
    result = {m: 0.0 for m in range(1, 13)}
    for r in rows:
        result[r["month"]] = r["total"]
    return result

def get_annual_totals(conn, year: int, statuses: tuple) -> dict:
    ph = ",".join("?" for _ in statuses)
    row = conn.execute(
        f"SELECT COALESCE(SUM(ad.micro_days), 0) AS micro, "
        f"COALESCE(SUM(ad.report_days), 0) AS report "
        f"FROM project_annual_days ad JOIN projects p ON ad.project_id = p.id "
        f"WHERE ad.year = ? AND p.status IN ({ph})",
        (year, *statuses)).fetchone()
    return {"micro": row["micro"], "report": row["report"]}

def get_accepted_field_total(conn, year: int) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(fm.field_days), 0) AS t "
        "FROM project_field_months fm JOIN projects p ON fm.project_id = p.id "
        "WHERE fm.year = ? AND p.status = 'accepted'", (year,)).fetchone()
    return row["t"]

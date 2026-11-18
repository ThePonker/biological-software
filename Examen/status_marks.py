"""
Examen -- "likely to be downgraded" status marks (the [square brackets]).

A species whose published status is out of date and likely to be downgraded on review is
shown with its status in square brackets, e.g. "[Nb]", and left out of the "revised" Key
Species figures. Two tables in examen.db (created by scripts/add_report_tables.py):

    status_downgrades           global marks, every job (tvk, species_name, reason)
    status_downgrade_overrides  one job's exception: project + client + survey_year + tvk;
                                bracket = 1 brackets the species there only, bracket = 0 leaves a
                                globally marked species unbracketed there. An override wins.

Reads open the database read-only and return nothing when the tables are not there. A write is
one INSERT OR REPLACE / DELETE ... WHERE <primary key>, done only when the user asks for it; if
the tables are missing it raises MissingTables (message: what to run) and changes nothing.
"""
import sqlite3
from datetime import datetime

import paths

RUN_FIRST = "Run scripts\\add_report_tables.py first"
GLOBAL_TABLE = "status_downgrades"
OVERRIDE_TABLE = "status_downgrade_overrides"


class MissingTables(Exception):
    """The mark tables are not in examen.db; str() says what to run."""

    def __init__(self, message=RUN_FIRST):
        super().__init__(message)


class MarkError(Exception):
    """A write was refused (an away machine); str() says why."""


def _db():
    return str(paths.EXAMEN_DB)


def _ro():
    return sqlite3.connect(f"file:{_db()}?mode=ro", uri=True)


def tables_present() -> bool:
    try:
        c = _ro()
    except sqlite3.Error:
        return False
    try:
        have = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    except sqlite3.Error:
        return False
    finally:
        c.close()
    return GLOBAL_TABLE in have and OVERRIDE_TABLE in have


def _read(sql, params=()):
    """Rows from a read-only connection; [] when the database or tables are missing."""
    if not tables_present():
        return []
    try:
        c = _ro()
        try:
            return c.execute(sql, params).fetchall()
        finally:
            c.close()
    except sqlite3.Error:
        return []


def _year(survey_year) -> str:
    return str(survey_year or "")


def list_marks() -> list:
    """Global marks as [{'tvk', 'species_name', 'reason'}], by species name."""
    return [{"tvk": t, "species_name": n, "reason": r or ""} for t, n, r in _read(
        f"SELECT tvk, species_name, reason FROM {GLOBAL_TABLE} ORDER BY species_name, tvk")]


def list_overrides(project_name=None, client="", survey_year="") -> list:
    """Overrides as [{'project_name', 'client', 'survey_year', 'tvk', 'species_name',
    'bracket'}]; for one job when project_name is given."""
    sql = (f"SELECT project_name, client, survey_year, tvk, species_name, bracket "
           f"FROM {OVERRIDE_TABLE}")
    params = ()
    if project_name is not None:
        sql += " WHERE project_name = ? AND client = ? AND survey_year = ?"
        params = (project_name, client or "", _year(survey_year))
    keys = ("project_name", "client", "survey_year", "tvk", "species_name", "bracket")
    return [dict(zip(keys, r)) for r in _read(sql + " ORDER BY species_name, tvk", params)]


def bracket_checker(project_name="", client="", survey_year=""):
    """A function tvk -> bool for one job, reading the tables once. Override wins over global."""
    marked = {t for (t,) in _read(f"SELECT tvk FROM {GLOBAL_TABLE}")}
    over = {t: bool(b) for t, b in _read(
        f"SELECT tvk, bracket FROM {OVERRIDE_TABLE} "
        "WHERE project_name = ? AND client = ? AND survey_year = ?",
        (project_name or "", client or "", _year(survey_year)))}
    return lambda tvk: over[tvk] if tvk in over else tvk in marked


def is_bracketed(tvk, project_name="", client="", survey_year="") -> bool:
    if not tvk:
        return False
    return bracket_checker(project_name, client, survey_year)(tvk)


def is_globally_marked(tvk) -> bool:
    return bool(tvk) and any(m["tvk"] == tvk for m in list_marks())


# ---- writes: one row each, on an explicit user action ------------------------------

def _write(sql, params):
    from shared.away_mode import away_active
    if away_active():
        raise MarkError("Away machine: status marks cannot be saved here.")
    if not tables_present():
        raise MissingTables()
    c = sqlite3.connect(_db(), timeout=10)
    try:
        with c:
            c.execute(sql, params)
    finally:
        c.close()


def _now():
    return datetime.now().isoformat(timespec="seconds")


def set_mark(tvk, species_name, reason=""):
    """Mark a species as likely to be downgraded, for every job."""
    if not tvk:
        raise ValueError("a species needs a TVK to be marked")
    created = next((r[0] for r in _read(
        f"SELECT created_at FROM {GLOBAL_TABLE} WHERE tvk = ?", (tvk,))), None) or _now()
    _write(f"INSERT OR REPLACE INTO {GLOBAL_TABLE} "
           "(tvk, species_name, reason, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
           (tvk, species_name or "", reason or "", created, _now()))


def clear_mark(tvk):
    _write(f"DELETE FROM {GLOBAL_TABLE} WHERE tvk = ?", (tvk,))


def set_override(project_name, client, survey_year, tvk, species_name, bracket):
    """bracket True: bracketed in this job only; False: not bracketed in this job."""
    if not tvk:
        raise ValueError("a species needs a TVK to be marked")
    _write(f"INSERT OR REPLACE INTO {OVERRIDE_TABLE} "
           "(project_name, client, survey_year, tvk, species_name, bracket, updated_at) "
           "VALUES (?, ?, ?, ?, ?, ?, ?)",
           (project_name or "", client or "", _year(survey_year), tvk, species_name or "",
            1 if bracket else 0, _now()))


def clear_override(project_name, client, survey_year, tvk):
    _write(f"DELETE FROM {OVERRIDE_TABLE} WHERE project_name = ? AND client = ? "
           "AND survey_year = ? AND tvk = ?",
           (project_name or "", client or "", _year(survey_year), tvk))


def remove_mark(project_name, client, survey_year, tvk):
    """"Remove mark" in one job: the global mark and this job's override both go, so the species
    is not bracketed in this job (other jobs lose a global mark too: it was the same mark)."""
    clear_override(project_name, client, survey_year, tvk)
    clear_mark(tvk)


# ---- display and figures ------------------------------------------------------------

def bracket_text(text):
    """'Nb' -> '[Nb]'; empty stays empty."""
    return f"[{text}]" if text else text


def revised_key_figures(keys, is_bracketed_fn):
    """(status_only_revised, rare_revised): the one place these are worked out.

    Status-only revised = Key Species with a status-only tier that are not bracketed for the job;
    Rare Key revised = Rare Key Species (Telfer) that are not bracketed.
    """
    try:
        from Examen.workbook_export import status_only_tier, telfer_tier
    except ImportError:  # pragma: no cover
        from workbook_export import status_only_tier, telfer_tier
    keep = [k for k in keys if not is_bracketed_fn(getattr(k, "tvk", ""))]
    return (sum(1 for k in keep if status_only_tier(k)),
            sum(1 for k in keep if telfer_tier(k) == "rare"))

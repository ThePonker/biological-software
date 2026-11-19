"""
Examen -- "likely to be downgraded" status marks (the [square brackets]).

A species whose published status is out of date and likely to be downgraded on review is
shown with its status in square brackets, e.g. "[Nb]", and left out of the "revised" Key
Species figures. Two tables in examen.db (created by scripts/add_report_tables.py):

    status_downgrades           global marks, every job (tvk, species_name, reason)
    status_downgrade_overrides  one job's exception: project + client + survey_year + tvk;
                                bracket = 1 brackets the species there only, bracket = 0 leaves a
                                globally marked species unbracketed there. An override wins.

Each mark also stores the status it was made against (status_marked: the species' rarity and
threat codes, one normalised string from status_key). A mark applies only while the species' current
status_key equals it (or it is '' = not recorded); once a new status review changes the codes the
mark is "stale" and the published status is used unbracketed. mark_state is the one place that
decides this; every caller goes through bracket_checker / is_bracketed.

Reads open the database read-only and return nothing when the tables are not there (a missing status_marked column reads as ''). A write is
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


def _select(table, cols, tail="", params=()):
    """Rows of the named columns; a status_marked column the table lacks (not migrated yet)
    reads as ''. [] when the database or tables are missing."""
    if not tables_present():
        return []
    try:
        c = _ro()
        try:
            have = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
            expr = ", ".join("'' AS status_marked" if x == "status_marked" and x not in have
                             else x for x in cols)
            return c.execute(f"SELECT {expr} FROM {table} {tail}", params).fetchall()
        finally:
            c.close()
    except sqlite3.Error:
        return []


def columns_present() -> bool:
    """True when both tables have the status_marked column (writes need it)."""
    try:
        c = _ro()
    except sqlite3.Error:
        return False
    try:
        return all("status_marked" in {r[1] for r in c.execute(f"PRAGMA table_info({t})")}
                   for t in (GLOBAL_TABLE, OVERRIDE_TABLE))
    except sqlite3.Error:
        return False
    finally:
        c.close()


# ---- the status a mark was made against ----------------------------------------------

NOT_GIVEN = object()        # no current status available: staleness cannot be judged
APPLIED, STALE, UNRECORDED = "applied", "stale", "unrecorded"


def status_key(entry) -> str:
    """The species' rarity and threat codes as one normalised string, e.g. "RDB1" or "NS; VU":
    the codes bracket_parts can bracket (never the threat categories LC / NA / NE / WL; Notable A "Na" is kept), upper-cased, de-duplicated,
    sorted and joined with "; ". entry: an object with rarity / threat / threat_legacy, or an
    iterable of codes; None -> ''. Marks are made and checked against the Codex key of the
    species' own TVK (codex_status_keys), never against an analysis entry, so the mode (Codex
    Full or Pantheon Only) cannot change the answer."""
    from Examen.workbook_export import never_bracket, status_codes
    if entry is None or entry is NOT_GIVEN:
        return ""
    if isinstance(entry, str):
        codes = [entry]
    elif hasattr(entry, "__iter__"):
        codes = list(entry)
    else:
        codes = status_codes(entry)
    norm = {(c or "").strip().upper() for c in codes if c and not never_bracket(c)}
    return "; ".join(sorted(c for c in norm if c))


def mark_state(status_marked, current_key) -> str:
    """The one decision: does a mark made against status_marked still apply?
    UNRECORDED (marked '' -- applies), APPLIED (current status is the one marked), or STALE (the
    status changed since: not applied). current_key NOT_GIVEN: cannot be judged, so it applies."""
    if not status_marked:
        return UNRECORDED
    if current_key is NOT_GIVEN or current_key == status_marked:
        return APPLIED
    return STALE


def mark_applies(status_marked, current_key) -> bool:
    return mark_state(status_marked, current_key) != STALE


def list_marks() -> list:
    """Global marks as [{'tvk', 'species_name', 'reason', 'status_marked', 'updated_at'}], by
    species name."""
    return [{"tvk": t, "species_name": n, "reason": r or "", "status_marked": m or "",
             "updated_at": u or ""} for t, n, r, m, u in _select(
        GLOBAL_TABLE, ("tvk", "species_name", "reason", "status_marked", "updated_at"),
        "ORDER BY species_name, tvk")]


def list_overrides(project_name=None, client="", survey_year="") -> list:
    """Overrides as [{'project_name', 'client', 'survey_year', 'tvk', 'species_name',
    'bracket', 'status_marked', 'updated_at'}]; for one job when project_name is given."""
    tail, params = "", ()
    if project_name is not None:
        tail = "WHERE project_name = ? AND client = ? AND survey_year = ? "
        params = (project_name, client or "", _year(survey_year))
    keys = ("project_name", "client", "survey_year", "tvk", "species_name", "bracket",
            "status_marked", "updated_at")
    rows = _select(OVERRIDE_TABLE, keys, tail + "ORDER BY species_name, tvk", params)
    return [{**dict(zip(keys, r)), "status_marked": r[6] or "", "updated_at": r[7] or ""}
            for r in rows]


class _Checker:
    """tvk -> bool for one job (override wins over global, a stale mark does not apply); .detail
    says why. current: {tvk: Codex status_key} for the marked species; unchecked: Codex could not
    be read, so marks are applied as saved."""

    def __init__(self, marked, over, current, unchecked=False):
        self._marked, self._over, self._current = marked, over, current
        self.unchecked = unchecked

    def _cur(self, tvk):
        return NOT_GIVEN if self.unchecked else self._current.get(tvk, "")

    def detail(self, tvk) -> dict:
        """{'bracketed', 'state' (APPLIED/STALE/UNRECORDED or None when no mark counts here),
        'scope' ('job'/'global'/None), 'status_marked', 'current', 'global_state' (the global
        mark's own state, whatever this job's override says)}."""
        cur = self._cur(tvk)
        out = {"bracketed": False, "state": None, "scope": None, "status_marked": "",
               "current": "" if cur is NOT_GIVEN else cur, "global_state": None}
        if tvk in self._marked:
            out["global_state"] = mark_state(self._marked[tvk], cur)
        if tvk in self._over:
            bracket, marked = self._over[tvk]
            out.update(scope="job", status_marked=marked)
            if bracket:
                out["state"] = mark_state(marked, cur)
        elif tvk in self._marked:
            out.update(scope="global", status_marked=self._marked[tvk],
                       state=out["global_state"])
        out["bracketed"] = out["state"] in (APPLIED, UNRECORDED)
        return out

    def __call__(self, tvk) -> bool:
        return self.detail(tvk)["bracketed"]


def bracket_checker(project_name="", client="", survey_year="", cache=None):
    """A checker tvk -> bool for one job. The marks are read once, and the Codex status_key of
    every marked species with a recorded status is looked up once, in one batch, by its own TVK
    (cache: a dict to keep those between calls, e.g. for a tab). If Codex cannot be read the
    checker is .unchecked and marks apply as saved."""
    marked = {t: m or "" for t, m in _select(GLOBAL_TABLE, ("tvk", "status_marked"))}
    over = {t: (bool(b), m or "") for t, b, m in _select(
        OVERRIDE_TABLE, ("tvk", "bracket", "status_marked"),
        "WHERE project_name = ? AND client = ? AND survey_year = ?",
        (project_name or "", client or "", _year(survey_year)))}
    cache = {} if cache is None else cache
    need = sorted({t for t, m in marked.items() if m} | {t for t, (b, m) in over.items() if b and m})
    need = [t for t in need if t not in cache]
    unchecked = False
    if need:
        try:
            cache.update(codex_status_keys(need))
        except Exception:  # noqa: BLE001 -- Codex unreadable: apply as marked, and say so
            unchecked = True
    return _Checker(marked, over, cache, unchecked)


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
    if not tables_present() or not columns_present():
        raise MissingTables()
    c = sqlite3.connect(_db(), timeout=10)
    try:
        with c:
            c.execute(sql, params)
    finally:
        c.close()


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _as_key(v) -> str:
    """A string is a key already made by status_key (or current_key): normalise its spelling
    only. Filtering it again would read Notable A's upper-cased "NA" as the threat category NA
    and lose it. Anything else (an entry, codes) goes through status_key."""
    if isinstance(v, str):
        return "; ".join(sorted({p.strip().upper() for p in v.split(";") if p.strip()}))
    return status_key(v)


def set_mark(tvk, species_name, reason="", status_marked=""):
    """Mark a species as likely to be downgraded, for every job. status_marked: the status it is
    judged against (a status_key string, an entry or codes)."""
    if not tvk:
        raise ValueError("a species needs a TVK to be marked")
    created = next((r[0] for r in _read(
        f"SELECT created_at FROM {GLOBAL_TABLE} WHERE tvk = ?", (tvk,))), None) or _now()
    _write(f"INSERT OR REPLACE INTO {GLOBAL_TABLE} "
           "(tvk, species_name, reason, status_marked, created_at, updated_at) "
           "VALUES (?, ?, ?, ?, ?, ?)",
           (tvk, species_name or "", reason or "", _as_key(status_marked), created, _now()))


def clear_mark(tvk):
    _write(f"DELETE FROM {GLOBAL_TABLE} WHERE tvk = ?", (tvk,))


def set_override(project_name, client, survey_year, tvk, species_name, bracket,
                 status_marked=""):
    """bracket True: bracketed in this job only (against status_marked); False: not bracketed in
    this job."""
    if not tvk:
        raise ValueError("a species needs a TVK to be marked")
    _write(f"INSERT OR REPLACE INTO {OVERRIDE_TABLE} "
           "(project_name, client, survey_year, tvk, species_name, bracket, status_marked, "
           "updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
           (project_name or "", client or "", _year(survey_year), tvk, species_name or "",
            1 if bracket else 0, _as_key(status_marked) if bracket else "", _now()))


def clear_override(project_name, client, survey_year, tvk):
    _write(f"DELETE FROM {OVERRIDE_TABLE} WHERE project_name = ? AND client = ? "
           "AND survey_year = ? AND tvk = ?",
           (project_name or "", client or "", _year(survey_year), tvk))


def remove_mark(project_name, client, survey_year, tvk):
    """"Remove mark" in one job: the global mark and this job's override both go, so the species
    is not bracketed in this job (other jobs lose a global mark too: it was the same mark)."""
    clear_override(project_name, client, survey_year, tvk)
    clear_mark(tvk)


def current_key(tvk) -> str:
    """The species' status_key in Codex now (raises if Codex cannot be read)."""
    return codex_status_keys([tvk]).get(tvk, "")


def mark_again(tvk, species_name):
    """"Mark again with the current status": the global mark and every bracket override for this
    TVK (any job) are re-saved against the Codex status now (reason and dates kept)."""
    key = current_key(tvk)
    for m in list_marks():
        if m["tvk"] == tvk:
            set_mark(tvk, m["species_name"] or species_name, m["reason"], key)
    for o in list_overrides():
        if o["tvk"] == tvk and o["bracket"]:
            set_override(o["project_name"], o["client"], o["survey_year"], tvk,
                         o["species_name"] or species_name, True, key)


def codex_status_keys(tvks):
    """{tvk: status_key} from Codex as the analysis reads it (the same rarity / threat tracks as
    KeySpeciesEntry); read-only. Raises if Codex cannot be read."""
    from types import SimpleNamespace

    from shared.repositories.codex_repository import CodexRepository
    repo = CodexRepository(str(paths.CODEX_DB), str(paths.PANTHEON_DB), str(paths.UKSI_DB))
    try:
        got = repo.get_statuses_batch(list(tvks))
    finally:
        repo.close()
    val = lambda e: e.value if e else ""  # noqa: E731
    return {t: status_key(SimpleNamespace(
        rarity=val(getattr(cs, "rarity_modern", None)) or val(getattr(cs, "rarity_legacy", None)),
        threat=val(getattr(cs, "threat_iucn_2001", None)),
        threat_legacy=val(getattr(cs, "threat_iucn_legacy", None))))
        for t, cs in got.items()}


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

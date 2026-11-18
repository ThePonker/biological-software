"""
Examen -- the Key Species benchmark: which surveys count, and the figures across them.

One row per survey (project + client + survey year) from examen_data.load_all_projects, each
with its "% Key Species (status only)" figure. That figure is worked out exactly as the workbook's
Summary row is (workbook_export.status_only_tier over the analysis' key species, divided by the
species recorded, rounded to 0.1) -- never by a separate rule.

Which surveys are included:
    saved choice   examen.db benchmark_choices (included 1 / 0), made in the Benchmark dialog
    otherwise      the default rule: England, 3 or more distinct visit dates, not a deadwood
                   survey and not a targeted survey.
observatum.db holds no field for a survey's type (deadwood / targeted), so every survey counts as
neither until the author unticks it; the Type column says "not recorded".

Saving is one upsert per survey. It is refused, changing nothing, on an away machine or when the
table is missing (BenchmarkError; the message says what to run).
"""
import sqlite3
import statistics
from datetime import datetime

import paths

TABLE = "benchmark_choices"
RUN_FIRST = "Run scripts\\add_report_tables.py first"
DEFAULT_COUNTRY = "England"
DEFAULT_MIN_VISITS = 3
TYPE_NOT_RECORDED = "not recorded"


class BenchmarkError(Exception):
    """A save was refused; str() says why."""


def _ro():
    return sqlite3.connect(f"file:{paths.EXAMEN_DB}?mode=ro", uri=True)


def table_ready() -> bool:
    try:
        c = _ro()
    except sqlite3.Error:
        return False
    try:
        return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                         (TABLE,)).fetchone() is not None
    except sqlite3.Error:
        return False
    finally:
        c.close()


def load_choices() -> dict:
    """{(project_name, client, survey_year): bool}; {} when the table or database is missing."""
    if not table_ready():
        return {}
    try:
        c = _ro()
        try:
            return {(p, cl or "", str(y or "")): bool(i) for p, cl, y, i in c.execute(
                f"SELECT project_name, client, survey_year, included FROM {TABLE}")}
        finally:
            c.close()
    except sqlite3.Error:
        return {}


def status_only_pct(result):
    """The workbook Summary's "% Key Species (status only)" as a number (None: no analysis)."""
    if result is None:
        return None
    from Examen.workbook_export import status_only_tier
    n = sum(1 for k in result.key_species if status_only_tier(k))
    return round(n / (result.total_species or 1) * 100, 1)


def default_included(country, visits, deadwood=False, targeted=False) -> bool:
    return (country == DEFAULT_COUNTRY and (visits or 0) >= DEFAULT_MIN_VISITS
            and not deadwood and not targeted)


def survey_key(project, client="", survey_year="") -> tuple:
    """The key a survey has in the benchmark rows and in benchmark_choices."""
    return (project or "", client or "", str(survey_year or ""))


def benchmark_rows(mode, jurisdiction=None, current=None) -> list:
    """One dict per survey: project, client, survey_year, country, visits, deadwood, targeted,
    type, pct, default, included, key, this_survey. jurisdiction is passed to load_all_projects
    (default: each survey under its own country, as the Examen table shows it).

    current: (project, client, survey_year) of the survey being reported. That survey is never
    counted in its own benchmark: its row has this_survey True and included False, whatever was
    saved or the default says."""
    cur = survey_key(*current) if current else None
    from Examen import examen_data as ed
    kwargs = {"jurisdiction": jurisdiction} if jurisdiction else {}
    choices = load_choices()
    rows = []
    for p in ed.load_all_projects(mode, **kwargs):
        year = str(p.survey_year or "")
        detail = ed.load_project_detail(p.project_name, p.client, mode,
                                        survey_year=year or None, jurisdiction=p.jurisdiction)
        pct = status_only_pct(getattr(detail, "analysis", None)) if detail else None
        key = (p.project_name, p.client or "", year)
        mine = key == cur
        dflt = pct is not None and default_included(p.jurisdiction, p.visit_count)
        rows.append({"project": p.project_name, "client": p.client or "", "survey_year": year,
                     "country": p.jurisdiction, "visits": p.visit_count,
                     "deadwood": False, "targeted": False, "type": TYPE_NOT_RECORDED,
                     "pct": pct, "default": dflt,
                     "included": (bool(choices.get(key, dflt)) and pct is not None and not mine),
                     "key": key, "this_survey": mine})
    return rows


def benchmark_summary(rows) -> dict:
    """n, median, q1, q3, min, max of the included surveys' status-only %. Quartiles by
    statistics.quantiles(method='inclusive'); with one survey q1 = q3 = its figure; with none
    n is 0 and the rest None."""
    vals = sorted(r["pct"] for r in rows if r.get("included") and not r.get("this_survey")
                  and r.get("pct") is not None)
    if not vals:
        return {"n": 0, "median": None, "q1": None, "q3": None, "min": None, "max": None}
    if len(vals) == 1:
        q1 = q3 = vals[0]
    else:
        q1, _, q3 = statistics.quantiles(vals, n=4, method="inclusive")
    return {"n": len(vals), "median": statistics.median(vals), "q1": q1, "q3": q3,
            "min": vals[0], "max": vals[-1]}


def summary_line(s) -> str:
    if not s["n"]:
        return "n = 0: no survey included"
    return (f"n = {s['n']}, median {s['median']:.1f}%, IQR {s['q1']:.1f}–{s['q3']:.1f}%, "
            f"range {s['min']:.1f}–{s['max']:.1f}%")


def save_choices(rows) -> int:
    """Write the ticked / unticked state of rows: every survey that already has a saved choice
    or whose state differs from the default. Returns rows written. Raises BenchmarkError (nothing
    changed) on an away machine or when the table is missing."""
    from shared.away_mode import away_active
    if away_active():
        raise BenchmarkError("Away machine: the benchmark choices cannot be saved here.")
    if not table_ready():
        raise BenchmarkError(f"The benchmark table is missing. {RUN_FIRST}")
    saved = load_choices()
    todo = [r for r in rows if not r.get("this_survey")
            and (r["key"] in saved or bool(r["included"]) != bool(r["default"]))]
    if not todo:
        return 0
    now = datetime.now().isoformat(timespec="seconds")
    c = sqlite3.connect(str(paths.EXAMEN_DB), timeout=10)
    try:
        with c:
            for r in todo:
                p, cl, y = r["key"]
                c.execute(
                    f"INSERT INTO {TABLE} (project_name, client, survey_year, included, "
                    "updated_at) VALUES (?,?,?,?,?) ON CONFLICT(project_name, client, "
                    "survey_year) DO UPDATE SET included=excluded.included, "
                    "updated_at=excluded.updated_at", (p, cl, y, 1 if r["included"] else 0, now))
    finally:
        c.close()
    return len(todo)

"""
Examen -- the data behind the report pack's tables (see report_pack).

Figures come from the report model (the workbook read back); this module only picks and shapes
them. The record lines for the species accounts and the visit dates come from the same records
the workbook's occurrence sentences use: the survey's WHERE clause is workbook_export's own
(_survey_where), and a Data Entry preview reads the job's staged rows.
"""
import re
import sqlite3
from datetime import date

import paths
from Examen.report_model import plain
from Examen.taxonomic_summary import SAPROXYLIC_LABEL, TOTAL_LABEL
from Examen.workbook_export import UNCHECKED_NOTE, _survey_where

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


def long_date(iso) -> str:
    """'2026-06-26' -> '26 June 2026'; anything else as it is."""
    m = _ISO.match(str(iso or ""))
    if not m:
        return str(iso or "")
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return str(iso)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def survey_scope(detail, project, pooled_years):
    """(project_name, client, survey_year or None, preview_rows or None) as the workbook uses."""
    site = getattr(detail, "site", None)
    name = getattr(project, "project_name", "") or getattr(site, "site_name", "")
    client = getattr(project, "client", "") or getattr(site, "client", "")
    year = getattr(site, "survey_year", "") or None
    preview = getattr(detail, "preview_rows", None) if getattr(site, "preview_job", "") else None
    return name, client, (None if pooled_years else year), preview


def _query(sql_tail, cols, scope):
    name, client, year, _ = scope
    where, params = _survey_where(name, client, year)
    try:
        c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
        try:
            return c.execute(f"SELECT {cols} FROM assessment_records WHERE {where} {sql_tail}",
                             params).fetchall()
        finally:
            c.close()
    except sqlite3.Error:
        return []


def visit_dates(scope) -> list:
    """[(iso date, visit number text)] in date order, one per distinct date."""
    _, _, _, preview = scope
    if preview is not None:
        pairs = [(r[2], r[10]) for r in preview if r[2]]
    else:
        pairs = _query("AND date IS NOT NULL AND date != ''", "date, visit_number", scope)
    seen = {}
    for d, v in pairs:
        nums = seen.setdefault(d, [])
        v = str(v or "").strip()
        if v and v not in nums:
            nums.append(v)
    return [(d, ", ".join(sorted(nums))) for d, nums in sorted(seen.items())]


def visit_table(scope, weather) -> list:
    """Rows for Table 4.1: date, visit number, temperature, wind, cloud ('' where none)."""
    out = []
    for d, v in visit_dates(scope):
        w = weather.get(d, {})
        out.append([long_date(d), v, w.get("temperature", ""), w.get("wind", ""),
                    w.get("cloud", "")])
    return out


_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


def count_text(qty) -> str:
    """1 -> 'one' ... 10 -> 'ten'; larger as figures; anything held that is not a number as typed."""
    s = str(qty if qty is not None else "").strip()
    if not s:
        return ""
    try:
        f = float(s)
    except ValueError:
        return s
    if f == int(f):
        n = int(f)
        return _WORDS[n] if 1 <= n <= 10 else str(n)
    return s


_NO_METHOD = {"unknown", "not recorded", "other method (add comment)", "other method", "other"}


def method_text(method) -> str:
    """Lower case, keeping all-capital words (UV, MV) as they are; a placeholder such as
    'Unknown' or 'Other method (add comment)' says nothing to a reader and is left out."""
    if str(method or "").strip().lower() in _NO_METHOD:
        return ""
    words = str(method or "").strip().split()
    return " ".join(w if (len(w) > 1 and w.isupper()) else w.lower() for w in words)


def determiner_text(det) -> str:
    """'Falk, S.J.' -> 'S.J. Falk'; a name without a comma as typed; several names separated by
    ';' each turned round and joined with 'and'."""
    names = [n.strip() for n in str(det or "").split(";") if n.strip()]
    if len(names) > 1:
        return " and ".join(determiner_text(n) for n in names)
    s = names[0] if names else ""
    last, comma, first = s.partition(",")
    if comma and last.strip() and first.strip():
        return f"{first.strip()} {last.strip()}"
    return s


def _join(parts, last_word="and"):
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + f" {last_word} " + parts[-1]


def record_sentence(records) -> str:
    """One sentence for a species' records, [(date, place, method, qty, determiner)] in date order:
    grouped by date and place, with method and count (and the determiner) per group; one
    determiner at the end when all the groups share it. '' when there are no records."""
    raw = {}                                      # (date, place) -> [(item, determiner)]
    for d, place, method, qty, det in records:
        key = (str(d or "").strip(), str(place or "").strip())
        item = ", ".join(b for b in (count_text(qty), method_text(method)) if b)
        raw.setdefault(key, []).append((item, determiner_text(det)))
    if not raw:
        return ""
    groups = {}                                   # (date, place) -> ([item], [determiner])
    for key, recs in raw.items():
        dets = {dt for _, dt in recs}
        if len(dets) == 1:                        # one determiner (or none) for the whole group
            groups[key] = ([i for i, _ in recs if i], [dt for dt in dets if dt])
        else:                                     # differing: each record keeps its own
            groups[key] = ([", ".join(b for b in (i, f"det. {dt}" if dt else "") if b)
                            for i, dt in recs if i or dt], [])
    all_dets = {tuple(v[1]) for v in groups.values()}
    shared = len(groups) > 1 and len(all_dets) == 1 and next(iter(all_dets)) != ()
    by_date = {}
    for (d, place), (items, dets) in groups.items():
        inner = list(items)
        if dets and not shared:
            inner.append("det. " + " and ".join(dets))
        by_date.setdefault(d, []).append(
            (place, f" ({'; '.join(inner)})" if inner else ""))
    clauses = []
    for d, places in by_date.items():
        bits = [((f"at {pl}" if pl else "") + extra).strip() for pl, extra in places]
        bits = [b for b in bits if b]
        clauses.append(" ".join(x for x in (f"on {long_date(d)}" if d else "",
                                            _join(bits) if bits else "") if x))
    clauses = [c for c in clauses if c]
    if not clauses:                    # records exist, but with no date, place, count or method
        return "Recorded (no date, place or method held)."
    if len(clauses) == 1:
        body = clauses[0]
    else:
        body = "; ".join(clauses[:-1]) + "; and " + clauses[-1]
    if shared:
        body += "; det. " + " and ".join(next(iter(all_dets)))
    return f"Recorded {body}."


def records_by_tvk(tvks, scope) -> dict:
    """{tvk: one sentence} in date order (see record_sentence), from the same records as before."""
    _, _, _, preview = scope
    if preview is not None:
        rows = [(r[1], r[2], r[7], r[8], r[5], r[9]) for r in preview if r[1]]
    else:
        rows = _query("AND species_tvk IS NOT NULL",
                      "species_tvk, date, grid_ref, method, quantity, determiner", scope)
    by = {}
    for tvk, d, grid, method, qty, det in sorted(rows, key=lambda r: (r[1] or "", r[0] or "")):
        if tvk in tvks:
            by.setdefault(tvk, []).append((d, grid, method, qty, det))
    return {tvk: record_sentence(recs) for tvk, recs in by.items()}


def group_table(rep) -> list:
    """Table 5.1 rows: [group, 'species (key species)']; totals row last (bold by label)."""
    table = dict(rep["tables"]).get("Taxonomic summary")
    rows = []
    if table:
        heads = table["heads"]
        g, t, k = heads.index("Group"), heads.index("Taxa"), heads.index("Spp. with status")
        for r in table["rows"]:
            if plain(r[g]) == SAPROXYLIC_LABEL:
                continue
            rows.append([plain(r[g]), f"{plain(r[t])} ({plain(r[k])})"])
        rows.sort(key=lambda r: r[0] == TOTAL_LABEL)
    return rows


def biotope_rows(rep) -> list:
    """Table 5.3 rows from the Habitats sheet: the broad-biotope lines only."""
    table = dict(rep["tables"]).get("Habitats")
    if not table:
        return []
    h = table["heads"]
    keep = [h.index(c) for c in ("Broad biotope", "Species", "Scoring", "SQI", "% national pool")]
    return [[r[i] if i < len(r) else "" for i in keep] for r in table["rows"]
            if r and plain(r[0])]


def sat_rows(rep):
    table = dict(rep["tables"]).get("Specific assemblage types")
    return (table["heads"], table["rows"]) if table else ([], [])


def figure(rep, label, default=""):
    for lab, value, _ in rep["figures"]:
        if lab == label:
            return value
    return default


def key_sentence(rep) -> str:
    """One sentence: Key Species total, with the status-only and revised figures where they
    differ (all read from the Summary rows)."""
    n, pct = figure(rep, "Key Species", 0), figure(rep, "% Key Species")
    so, so_pct = figure(rep, "Key Species (status only)", n), figure(rep, "% Key Species (status only)")
    rev, rev_pct = (figure(rep, "Key Species (status only, revised)", so),
                    figure(rep, "% Key Species (status only, revised)"))
    s = f"The survey recorded {n} Key Species ({pct} of the species recorded)"
    if so != n:
        s += (f", of which {so} ({so_pct}) are Key Species on rarity and threat status alone")
    if rev != so:
        s += (f"; {rev} ({rev_pct}) when species whose status is likely to be downgraded "
              "(shown in square brackets) are left out")
    s += "."
    texts = [plain(x[0]) for x in rep["figures"]] + [plain(b[0]) for b in rep["basis"]] + \
        [plain(a) for a in rep["attribution"]]
    if UNCHECKED_NOTE in texts:       # the workbook could not check the marks against Codex
        s += " " + UNCHECKED_NOTE
    return s


def benchmark_sentence(summary, site_pct) -> str:
    """The benchmark sentence, or '' when no survey is included."""
    if not summary["n"]:
        return ""
    return (f"Across the {summary['n']} comparable surveys, the proportion of status-only Key "
            f"Species ranged from {summary['min']:.1f}% to {summary['max']:.1f}% (median "
            f"{summary['median']:.1f}%, interquartile range {summary['q1']:.1f}–"
            f"{summary['q3']:.1f}%); this site's figure is {site_pct}.")

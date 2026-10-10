"""import_core -- the pieces every import wizard needs, written once (9 Oct 2026). No Qt.

Built for the scheme and specimen repairs (backlog I7b; faults F33-F35), and the seed of
merging the three wizards (C4). The observation wizard keeps its own versions until then.

    read_table_file(path)            -> columns, rows, encoding   (BOM-safe; quoted newlines kept)
    parse_quantity("c.20")           -> (20, "c.20")
    parse_record_date("6.vi.2021")   -> ParsedDate("2021-06-06", "D", "", "")   (10 Oct, IMP-12/13)
    auto_map_columns(columns, patterns) -> {field: column}       (whole words only; IMP-11)
    vc_for_grid_refs(vc_service, refs) -> {ref: {vc_number, vc_name, warning, error}}  (+ tetrads)
    chunked_select(db, sql, values)  -> rows                      (900 at a time; raises, never swallows)
    insert_rows(db, table, records, ref) -> (inserted, [(ref, error)])
    taxonomy_for_tvks(tvks)          -> {tvk: {sort_key, superfamily, subfamily, order_name, family}}

`db` is Observatum's database manager (execute_main / execute_main_write / execute_main_many).
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import re
import sqlite3
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

CHUNK = 900          # under SQLite's old 999-variable limit; as the F37 fix

# ---------------------------------------------------------------- files

ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")     # utf-8-sig reads plain UTF-8 too; latin-1 never fails


def read_table_file(path: str) -> Tuple[List[str], List[Dict[str, str]], str]:
    """A CSV / tab-separated file as (columns, rows, encoding).

    Plain 'utf-8' used to be tried first: it decodes a file with a byte-order mark without
    error but leaves '\\ufeff' on the first heading -- so iRecord's 'ID' column was never
    found and every iRecord ID was lost (the 35,104 scheme rows, 9 Oct 2026). Splitting on
    '\\n' also broke quoted comments containing a line break; the csv module reads them whole.
    """
    raw = open(path, "rb").read()
    for enc in ENCODINGS:
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    first = text.split("\n", 1)[0]
    delim = "\t" if first.count("\t") > first.count(",") else ","
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delim)
    cols = [(c or "").lstrip("﻿").strip() for c in (reader.fieldnames or [])]
    reader.fieldnames = cols
    rows = [{k: (v if v is not None else "") for k, v in r.items() if k is not None} for r in reader]
    return cols, rows, enc


# ---------------------------------------------------------------- values

_QTY = re.compile(r"^\s*(?:c\.?|ca\.?|circa|approx\.?|~|>=?|<=?)?\s*(\d+)(?:\.0+)?\s*\+?\s*"
                  r"(?:adults?\s*)?(?:\(exact\))?\s*$", re.I)        # NBN: "2 (Exact)", "1 Adult (Exact)"


def parse_quantity(text) -> Tuple[Optional[int], Optional[str]]:
    """'12' -> (12, None); 'c.20' -> (20, 'c.20'); '5+' -> (5, '5+'); 'many' -> (None, 'many').

    The second value is the original text when it was not a plain number, to be kept
    (organism_quantity) rather than lost -- "c.20" used to become 1.
    """
    if text is None:
        return None, None
    s = str(text).strip()
    if not s:
        return None, None
    if re.fullmatch(r"\d+(?:\.0+)?", s):
        return int(float(s)), None
    m = _QTY.match(s)
    return (int(m.group(1)), s) if m else (None, s)


def quantity_or_default(text, default: int = 1) -> Tuple[int, Optional[str]]:
    """parse_quantity for storing: (quantity, text to keep). No number at all gives `default`;
    a count of 0 stays 0 (IMP-12: "0" used to become 1 through `... or 1`)."""
    n, kept = parse_quantity(text)
    return (default if n is None else n), kept


# ---------------------------------------------------------------- dates (10 Oct 2026)

@dataclass
class ParsedDate:
    """One date as an import stores it, the way the rest of the suite does (Data Entry's
    date_utils, iRecord): `date` is the ISO first day of the period, `date_type` says what it
    is -- D day, O month, Y year, and for ranges DD / OO / YY (iRecord's codes, already in
    recording_scheme). `note` explains a period or range; `error` is set when it can't be used."""
    date: str = ""
    date_type: str = ""
    note: str = ""
    error: str = ""

    @property
    def exact(self) -> bool:
        return self.date_type == "D"


_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9,
          "x": 10, "xi": 11, "xii": 12}
_MONTH_WORDS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}
_FULL_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august",
                "september", "october", "november", "december", "sept")
_SEP = r"[/.\-\s]+"
_MIN_YEAR = 1700                                         # as DataEntry/date_utils
_KIND_ORDER = "DOY"                                      # finer to coarser


def _month(word: str) -> Optional[int]:
    """1-12 for a month number, roman numeral (vi) or name (Jun / June), else None."""
    w = word.strip(". ").lower()
    if w.isdigit():
        return int(w) if 1 <= int(w) <= 12 else None
    if w in _ROMAN:
        return _ROMAN[w]
    if w[:3] in _MONTH_WORDS and (len(w) == 3 or w in _FULL_MONTHS):
        return _MONTH_WORDS[w[:3]]
    return None


def _year(text: str, today: _dt.date) -> Optional[int]:
    if not text.isdigit() or len(text) not in (2, 4):
        return None
    y = int(text)
    if len(text) == 2:                     # 21 -> 2021, 85 -> 1985: never a year still to come
        y += 2000 if y <= today.year % 100 else 1900
    return y if y >= _MIN_YEAR else None


# A time after a date -- "01/06/2024 00:00", "01/06/2024 10:30:00", ISO "...T10:30:00+01:00",
# "10:30 pm" -- is ignored: records hold the day (review 10 Oct 2026).
_TIME = re.compile(r"(?:(?<=\d)t|\s+)\d{1,2}:\d{2}(?::\d{2}(?:[.,]\d+)?)?\s*(?:am|pm)?"
                   r"\s*(?:z|[+-]\d{2}(?::?\d{2})?)?$")


def _drop_time(text: str) -> str:
    s = " ".join(str(text).strip().lower().split())
    return _TIME.sub("", s).strip()


def _two_digit_year(text: str) -> bool:
    """'24/06/01', '1.6.24': the year was written with two digits (and so was read as
    1900s or 2000s -- see _year)."""
    return bool(re.search(r"(?<![\d])\d{2}$", _drop_time(text))) and not re.search(
        r"\d{4}", _drop_time(text))


def _one_date(text: str, today: _dt.date) -> Optional[Tuple[_dt.date, str]]:
    """(first day, 'D' / 'O' / 'Y') for one date written any usual way, else None.
    A time after the date is ignored."""
    s = _drop_time(text)
    if not s:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[t ][\d:.]+z?)?", s)       # ISO, maybe a time
    if m:
        y, mo, d = (int(g) for g in m.groups())
        return _day(y, mo, d)
    m = re.fullmatch(r"(\d{4})/(\d{1,2})/(\d{1,2})", s)                          # 2024/06/01
    if m:
        y, mo, d = (int(g) for g in m.groups())
        return _day(y, mo, d)
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?" + _SEP + r"([a-z]+\.?|\d{1,2})" + _SEP + r"(\d{2}|\d{4})", s)
    if m:                                       # 1/6/2024, 1.6.24, 6.vi.2021, 6 June 2021, 6-Jun-21
        mo, y = _month(m.group(2)), _year(m.group(3), today)
        return _day(y, mo, int(m.group(1))) if mo and y else None
    m = re.fullmatch(r"(\d{4})", s)                                                 # 2021
    if m:
        y = int(s)
        return (_dt.date(y, 1, 1), "Y") if y >= _MIN_YEAR else None
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", s) or re.fullmatch(
        r"([a-z]+\.?|\d{1,2})" + _SEP + r"(\d{4})", s)              # 2021-06, 06/2021, vi.2021, June 2021
    if m:
        a, b = m.groups()
        y, mo = (int(a), _month(b)) if len(a) == 4 and a.isdigit() else (_year(b, today), _month(a))
        if y and mo and y >= _MIN_YEAR:
            return _dt.date(y, mo, 1), "O"
    return None


def _day(y, mo, d):
    try:
        return _dt.date(y, mo, d), "D"
    except (TypeError, ValueError):
        return None


def _period_end(start: _dt.date, kind: str) -> _dt.date:
    if kind == "D":
        return start
    if kind == "Y":
        return _dt.date(start.year, 12, 31)
    nxt = _dt.date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return nxt - _dt.timedelta(days=1)


def date_bounds(text, today: Optional[_dt.date] = None) -> Optional[Tuple[str, str]]:
    """(first day, last day) as ISO text for one date typed in a filter box, written any
    usual way: '2021' -> 2021-01-01..2021-12-31, '06/2021' -> the month, '01/06/2021' or
    '2021-06-01' -> that day. None if unreadable. (The Mapping tab's date boxes, MAP3.)"""
    one = _one_date(str(text or ""), today or _dt.date.today())
    if not one:
        return None
    start, kind = one
    return start.isoformat(), _period_end(start, kind).isoformat()


_RANGE_SEPS = (" to ", " - ", " \u2013 ", "\u2013", "\u2014", "/", "-")
_KIND_NAMES = {"D": "", "O": "a month", "Y": "a year"}


def parse_record_date(text, today: Optional[_dt.date] = None) -> ParsedDate:
    """Any date an import file holds, as the suite stores it -- never guessed into a day.

    '01/06/2024', '2024-06-01', '6.vi.2021', '6 June 2021' -> D;  '2021-06', 'June 2021',
    'vi.2021' -> O;  '2021' -> Y;  '2024-05-01/2024-05-15', '1/5/2024 to 15/5/2024' -> DD
    (OO / YY for month and year ranges), stored from the first day with a note giving the
    range. Unreadable text, a date still to come (for a range: one that starts after today)
    and a range that ends before it starts are errors (IMP-12, IMP-13; 10 Oct 2026). A time
    after the date is ignored; a two-digit year ('24/06/01') is read as the latest year not
    still to come and the note says which ('read as 24/06/2001'). Blank gives ParsedDate()."""
    today = today or _dt.date.today()
    original = "" if text is None else str(text).strip()
    if not original:
        return ParsedDate()
    one = _one_date(original, today)
    if one:
        start, kind = one
        end = _period_end(start, kind)
        if start > today:
            return ParsedDate(error=f"Date is in the future: '{original}'")
        note = (f"Date '{original}' is {_KIND_NAMES[kind]}: stored as {start.isoformat()} "
                f"with date type {kind}" if kind != "D" else "")
        if kind == "D" and _two_digit_year(original):     # show the century it was given
            note = f"Date '{original}' read as {start.strftime('%d/%m/%Y')} (two-digit year)"
        return ParsedDate(start.isoformat(), kind, note)
    for sep in _RANGE_SEPS:
        if sep not in original:
            continue
        a, _, b = original.partition(sep)
        if sep == "-" and not re.fullmatch(r"\s*\d{4}\s*-\s*\d{4}\s*", original):
            continue                                  # only 2019-2021; 2021-06 is a month
        first, last = _one_date(a, today), _one_date(b, today)
        if not (first and last):
            continue
        kind = max(first[1], last[1], key=_KIND_ORDER.index)
        start, end = first[0], _period_end(last[0], last[1])
        if end < start:
            return ParsedDate(error=f"Date range ends before it starts: '{original}'")
        if start > today:     # a range running on past today ('2025-2026') is fine
            return ParsedDate(error=f"Date is in the future: '{original}'")
        if end == _period_end(start, kind):                    # one period: 2024-06-01/2024-06-01
            return ParsedDate(start.isoformat(), kind,
                              f"Date '{original}' stored as {start.isoformat()}" if kind != "D" else "")
        code = kind * 2
        return ParsedDate(start.isoformat(), code,
                          f"Date range '{original}': stored from {start.isoformat()} "
                          f"(to {end.isoformat()}) with date type {code}")
    return ParsedDate(error=f"Unreadable date: '{original}'")


# ---------------------------------------------------------------- column auto-mapping

def _words(text: str) -> Tuple[str, ...]:
    return tuple(re.sub(r"[^0-9a-z]+", " ", str(text or "").lower()).split())


def auto_map_columns(columns: Sequence[str], patterns: Dict[str, Sequence[str]]) -> Dict[str, str]:
    """Match a file's headings to fields by WHOLE words, each heading used once (IMP-11).

    `patterns` is {field: [alias, ...]} in order of preference. A heading matches an alias
    when it is the alias (best), starts with it ('Site name' <- 'site') or ends with it
    ('OS grid reference' <- 'grid reference'). An alias written '=name' must be the whole
    heading. Part-words never match: 'count' no longer finds 'Vice County' and 'name' no
    longer turns 'Site name' into the species column ('Wood A' became Anemone nemorosa)."""
    candidates = []
    for f_i, (field_id, aliases) in enumerate(patterns.items()):
        for a_i, alias in enumerate(aliases):
            whole_only = alias.startswith("=")
            aw = _words(alias.lstrip("="))
            if not aw:
                continue
            for c_i, col in enumerate(columns):
                cw = _words(col)
                if not cw:
                    continue
                if cw == aw:
                    kind = 3.0
                elif whole_only or len(aw) >= len(cw):
                    continue
                elif cw[:len(aw)] == aw:
                    kind = 2.0
                elif cw[-len(aw):] == aw:
                    kind = 1.5
                else:
                    continue
                candidates.append((-kind, a_i, -len(aw) / len(cw), f_i, c_i, field_id, col))
    mapping: Dict[str, str] = {}
    used = set()
    for *_, field_id, col in sorted(candidates):
        if field_id in mapping or col in used:
            continue
        mapping[field_id] = col
        used.add(col)
    return mapping


# ---------------------------------------------------------------- vice counties

_TETRAD = re.compile(r"[A-Z]{2}\d\d[A-NP-Z]")


def vc_for_grid_refs(vc_service, grid_refs: Iterable[str]) -> Dict[str, dict]:
    """The VC service's get_vc_batch, plus 2 km tetrads (SP46Q) -- IMP-13, 10 Oct 2026.

    VCLookupService.parse_grid_ref reads only all-digit references, so a tetrad was an
    'Invalid grid reference'. shared/osgb reads DINTY tetrads and the service's assess()
    works from it, so tetrads are looked up that way here. The service itself is unchanged:
    the maps that call parse_grid_ref would start drawing the 101 tetrad records already
    held in the recording scheme, a change to map figures for Wil to decide."""
    refs = [r for r in dict.fromkeys(grid_refs) if r]
    tetrads = [r for r in refs if _TETRAD.fullmatch(str(r).upper().replace(" ", ""))]
    others = [r for r in refs if r not in tetrads]
    out: Dict[str, dict] = {}
    if others:
        if hasattr(vc_service, "get_vc_batch"):
            out.update(vc_service.get_vc_batch(others))
        else:
            for g in others:
                ok, msg = vc_service.validate_grid_ref(g)
                if not ok:
                    out[g] = {"vc_number": None, "vc_name": "", "warning": "",
                              "error": f"Invalid grid reference: {msg}"}
                    continue
                res = vc_service.get_vc_from_grid_ref(g)
                out[g] = {"vc_number": res[0] if res else None, "vc_name": res[1] if res else "",
                          "warning": "" if res else "Could not determine Vice County", "error": ""}
    for g in tetrads:
        try:
            a = vc_service.assess(g) if hasattr(vc_service, "assess") else None
        except Exception as e:                                  # say so; never a silent blank
            out[g] = {"vc_number": None, "vc_name": "", "warning": "", "error": f"VC lookup error: {e}"}
            continue
        if a:
            out[g] = {"vc_number": a["vc_number"], "vc_name": a.get("vc_name") or "",
                      "warning": a.get("note") or "", "error": "",
                      "boundary": bool(a.get("boundary")), "vcs": a.get("vcs") or []}
        else:
            out[g] = {"vc_number": None, "vc_name": "", "warning": "Could not determine Vice County",
                      "error": ""}
    return out


def grid_precision(grid_ref) -> Optional[int]:
    """Size of the square in metres (tetrads included), or None if unreadable."""
    from shared.osgb import gridref_to_en
    p = gridref_to_en(grid_ref)
    return p[2] if p else None


# ---------------------------------------------------------------- summary


def summary_lines(counts: Dict[str, int], order: Sequence[Tuple[str, str]]) -> List[str]:
    """'Label: n' for each (key, label) in order whose count is not zero; the first is always
    shown. One wording for what each wizard's summary page reports (IMP-16)."""
    lines = []
    for i, (key, label) in enumerate(order):
        n = int(counts.get(key, 0) or 0)
        if n or i == 0:
            lines.append(f"{label}: {n}")
    return lines


# ---------------------------------------------------------------- database

def _val(r, i, key):
    return r[i] if isinstance(r, (list, tuple)) else r[key]


def chunked_select(db, sql: str, values: Iterable) -> list:
    """Run `sql` (with one '{ph}' placeholder list) over `values`, CHUNK at a time.

    Raises on failure: an import must stop when it cannot check for duplicates, not carry
    on as though there were none (F35)."""
    values = list(values)
    out = []
    for i in range(0, len(values), CHUNK):
        part = values[i:i + CHUNK]
        out += list(db.execute_main(sql.format(ph=",".join("?" * len(part))), tuple(part)) or [])
    return out


def table_columns(db, table: str) -> List[str]:
    return [_val(r, 1, "name") for r in db.execute_main(f"PRAGMA table_info({table})")]


def insert_rows(db, table: str, records: List[dict],
                ref: Callable[[dict], str] = lambda r: str(r.get("species_name") or "?")):
    """Insert records into `table` as one transaction; on failure, row by row.

    The column list is FIXED -- every table column any record supplies -- so a column that
    happens to be empty in the first row is no longer dropped for the whole batch (F33).
    Returns (inserted, failures) where failures is [(ref(record), error text)]; a failure
    is never silent."""
    if not records:
        return 0, []
    known = set(table_columns(db, table))
    cols = [c for c in dict.fromkeys(k for r in records for k in r) if c in known and c != "id"]
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
    params = [tuple(r.get(c) for c in cols) for r in records]
    try:
        db.execute_main_many(sql, params)
        return len(params), []
    except Exception as batch_error:
        print(f"[import_core] batch insert into {table} failed ({batch_error}); row by row")
    ok, fails = 0, []
    for rec, p in zip(records, params):
        try:
            db.execute_main_write(sql, p)
            ok += 1
        except Exception as e:
            fails.append((ref(rec), str(e)))
    return ok, fails


# ---------------------------------------------------------------- taxonomy

_SUBFAMILY_SQL = (
    'SELECT sp.tvk, sf.scientific_name FROM taxa sp JOIN taxa g ON sp.parent_tvk = g.tvk '
    'JOIN taxa sf ON g.parent_tvk = sf.tvk AND sf.rank = "Subfamily" WHERE sp.tvk IN ({ph}) '
    'UNION SELECT sp.tvk, sf.scientific_name FROM taxa sp JOIN taxa g ON sp.parent_tvk = g.tvk '
    'JOIN taxa t ON g.parent_tvk = t.tvk JOIN taxa sf ON t.parent_tvk = sf.tvk AND sf.rank = "Subfamily" '
    'WHERE sp.tvk IN ({ph})')


def taxonomy_for_tvks(tvks: Iterable[str], uksi_path=None) -> Dict[str, dict]:
    """{tvk: {sort_key, superfamily, subfamily, order_name, family}} from the current UKSI.

    Computed from each row's FINAL TVK at import time, so a species picked by hand gets its
    own sort key -- a hand-picked specimen used to import with none (invisible in the
    collection sidebar) or with the previous species' key (filed in the wrong place).
    Raises on failure; the caller decides whether to import without."""
    try:
        from src.utils.constants import compute_taxonomic_sort_key
    except ImportError:                                   # outside Observatum (tests, scripts)
        from Observatum.src.utils.constants import compute_taxonomic_sort_key
    if uksi_path is None:
        import paths
        uksi_path = paths.UKSI_DB
    tvks = [t for t in dict.fromkeys(tvks) if t]
    out: Dict[str, dict] = {}
    if not tvks:
        return out
    conn = sqlite3.connect(f"file:{uksi_path}?mode=ro", uri=True)
    try:
        for i in range(0, len(tvks), 450):                # the subfamily query uses each twice
            part = tvks[i:i + 450]
            ph = ",".join("?" * len(part))
            for tvk, code, order, superfamily, family in conn.execute(
                    f'SELECT tvk, sort_code, "order", superfamily, family FROM taxa WHERE tvk IN ({ph})', part):
                out[tvk] = {"sort_key": compute_taxonomic_sort_key(order or "", code or 0),
                            "superfamily": superfamily or "", "subfamily": "",
                            "order_name": order or "", "family": family or ""}
            for tvk, sub in conn.execute(_SUBFAMILY_SQL.format(ph=ph), part + part):
                if tvk in out and sub:
                    out[tvk]["subfamily"] = sub
    finally:
        conn.close()
    return out

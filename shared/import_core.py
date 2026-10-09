"""import_core -- the pieces every import wizard needs, written once (9 Oct 2026). No Qt.

Built for the scheme and specimen repairs (backlog I7b; faults F33-F35), and the seed of
merging the three wizards (C4). The observation wizard keeps its own versions until then.

    read_table_file(path)            -> columns, rows, encoding   (BOM-safe; quoted newlines kept)
    parse_quantity("c.20")           -> (20, "c.20")
    chunked_select(db, sql, values)  -> rows                      (900 at a time; raises, never swallows)
    insert_rows(db, table, records, ref) -> (inserted, [(ref, error)])
    taxonomy_for_tvks(tvks)          -> {tvk: {sort_key, superfamily, subfamily, order_name, family}}

`db` is Observatum's database manager (execute_main / execute_main_write / execute_main_many).
"""
from __future__ import annotations

import csv
import io
import re
import sqlite3
from typing import Callable, Dict, Iterable, List, Optional, Tuple

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

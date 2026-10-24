"""check_fresh_schema.py -- does reset_database.py still build the live schema?

    py -3.14 scripts\\check_fresh_schema.py                    # against paths.OBSERVATUM_DB
    py -3.14 scripts\\check_fresh_schema.py --live <path>      # against another copy

Builds a fresh empty database in a temporary folder with reset_database's builder, then
compares its tables, columns and indexes with the live observatum.db (opened read-only).
Columns in a different order are fine. Exit 0 = no differences. The live file is never
written, and the temporary folder is left where it is (it is in the system temp folder).
"""
import argparse
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum"), os.path.join(_ROOT, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402


def _tables(conn):
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")}


def _columns(conn, table):
    # (type, notnull, default, pk) by column name -- order does not matter
    return {r[1]: (r[2], r[3], r[4], r[5]) for r in conn.execute(f"PRAGMA table_info('{table}')")}


def _indexes(conn):
    # index name -> (table, unique, columns); automatic indexes (UNIQUE constraints) by columns
    out = {}
    for (table,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"):
        for r in conn.execute(f"PRAGMA index_list('{table}')").fetchall():
            name, unique, origin = r[1], r[2], r[3]
            cols = tuple(c[2] for c in conn.execute(f"PRAGMA index_info('{name}')"))
            key = name if origin == "c" else f"(auto) {table}{list(cols)}"
            out[key] = (table, unique, cols)
    return out


def differences(fresh, live):
    """List of plain sentences describing how two open connections' schemas differ."""
    out = []
    tf, tl = _tables(fresh), _tables(live)
    for t in sorted(tl - tf):
        out.append(f"table only in the live database: {t}")
    for t in sorted(tf - tl):
        out.append(f"table only in the fresh database: {t}")
    for t in sorted(tf & tl):
        cf, cl = _columns(fresh, t), _columns(live, t)
        for c in sorted(set(cl) - set(cf)):
            out.append(f"column only in the live database: {t}.{c}")
        for c in sorted(set(cf) - set(cl)):
            out.append(f"column only in the fresh database: {t}.{c}")
        for c in sorted(set(cf) & set(cl)):
            if cf[c] != cl[c]:
                out.append(f"column differs: {t}.{c}  fresh {cf[c]}  live {cl[c]}")
    xf, xl = _indexes(fresh), _indexes(live)
    for k in sorted(set(xl) - set(xf)):
        out.append(f"index only in the live database: {k}")
    for k in sorted(set(xf) - set(xl)):
        out.append(f"index only in the fresh database: {k}")
    for k in sorted(set(xf) & set(xl)):
        if xf[k] != xl[k]:
            out.append(f"index differs: {k}  fresh {xf[k]}  live {xl[k]}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--live", default=str(paths.OBSERVATUM_DB))
    a = ap.parse_args(argv)
    import reset_database
    tmp = Path(tempfile.mkdtemp(prefix="fresh_schema_")) / "observatum.db"
    print("Fresh schema check")
    print("=" * 40)
    reset_database.build_new_database(tmp)
    fresh = sqlite3.connect(f"file:{tmp.as_posix()}?mode=ro", uri=True)
    live = sqlite3.connect(f"file:{Path(a.live).resolve().as_posix()}?mode=ro", uri=True)
    try:
        diffs = differences(fresh, live)
    finally:
        fresh.close()
        live.close()
    print(f"\nFresh database (temporary): {tmp}")
    print(f"Live database:              {a.live}")
    if diffs:
        print(f"\n{len(diffs)} difference(s):")
        for d in diffs:
            print(f"  - {d}")
    else:
        print("\nNo differences: tables, columns and indexes match.")
    print("\nREAD ONLY. Nothing has been changed.")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())

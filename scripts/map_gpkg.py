"""GeoPackage reading for scripts/build_map_layers.py: read-only, and robust about column names
(PRAGMA table_info; the text column is the first of NAME_COLS present, the type / class column
the first of TYPE_COLS, or, for Soft / Classes types, the one that actually holds the values).
Split out of build_map_layers.py (18 Oct 2026) to keep both under 400 lines.
"""
import sqlite3
from pathlib import Path

import shapely.wkb

from shared.maps import place_classes

_ENVELOPE = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}      # GPKG header envelope indicator -> bytes

NAME_COLS = ("name1", "name", "distname", "text")     # the text column, first one present wins
TYPE_COLS = ("type", "class", "local_type")           # the type / class column, ditto


class Soft(list):
    """Types applied only if one of the table's type columns holds them (the scale versions
    "National" / "Regional" of a table that might not have them); else every row is read."""


class Classes(list):
    """Place classes: the type column used is the one that holds any of `detect` (default: these
    values; all the known classes when the file for one lod may have none), case ignored."""
    detect = None


def open_ro(path):
    return sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)


def decode_gpkg(blob):
    """GeoPackage geometry blob -> shapely geometry (None if empty)."""
    blob = bytes(blob)
    if blob[:2] != b"GP":
        raise ValueError("not a GeoPackage geometry blob")
    flags = blob[3]
    if (flags >> 4) & 1:                              # empty-geometry flag
        return None
    ind = (flags >> 1) & 7
    if ind not in _ENVELOPE:
        raise ValueError(f"bad envelope indicator {ind}")
    return shapely.wkb.loads(blob[8 + _ENVELOPE[ind]:])


def table_info(conn, table):
    """(geometry column, type column or None, name column or None, canonical table name).

    The type column is the first of TYPE_COLS present, the name column the first of NAME_COLS
    (found with PRAGMA table_info, case ignored). Raises ValueError if the table is missing or
    its srs is not 27700."""
    row = conn.execute("SELECT table_name FROM gpkg_contents WHERE lower(table_name)=lower(?)",
                       (table,)).fetchone()
    if not row:
        raise ValueError(f"table {table} not found")
    real = row[0]
    g = conn.execute("SELECT column_name, srs_id FROM gpkg_geometry_columns "
                     "WHERE lower(table_name)=lower(?)", (table,)).fetchone()
    if not g:
        raise ValueError(f"table {table} has no geometry column registered")
    if g[1] != 27700:
        raise ValueError(f"table {table} is in srs {g[1]}, not 27700 - refusing")
    cols = {r[1].lower(): r[1] for r in conn.execute(f'PRAGMA table_info("{real}")')}
    first = lambda names: next((cols[c] for c in names if c in cols), None)    # noqa: E731
    return g[0], first(TYPE_COLS), first(NAME_COLS), real


def _plan(conn, table, types):
    """(geometry column, type column, name column, table, filter column, values, lowered):
    what to select and which rows. Soft / Classes types look for the column that holds them
    (Classes: none does -> ValueError; Soft: none does -> every row)."""
    gcol, tcol, ncol, real = table_info(conn, table)
    if not types:
        return gcol, tcol, ncol, real, None, [], False
    if not isinstance(types, (Soft, Classes)):
        return gcol, tcol, ncol, real, tcol, list(types), False
    want = {str(t).lower() for t in types}
    seek = {str(t).lower() for t in (getattr(types, "detect", None) or types)}
    present = {r[1].lower(): r[1] for r in conn.execute(f'PRAGMA table_info("{real}")')}
    for c in (present[n] for n in TYPE_COLS if n in present):
        held = {str(r[0]).lower() for r in conn.execute(
            f'SELECT DISTINCT "{c}" FROM "{real}" WHERE "{c}" IS NOT NULL')}
        if held & seek:
            return gcol, c, ncol, real, c, sorted(want), True
    if isinstance(types, Classes):
        raise ValueError(f"table {table}: no type column ({', '.join(TYPE_COLS)}) holds any of "
                         f"{sorted(seek)} - run --describe {table}")
    return gcol, tcol, ncol, real, None, [], False


def _where(fcol, vals, lowered=False):
    if fcol and vals:
        col = f'lower("{fcol}")' if lowered else f'"{fcol}"'
        return f" WHERE {col} IN ({','.join('?' * len(vals))})", list(vals)
    return "", []


def count_rows(conn, table, types):
    _g, _t, _n, real, fcol, vals, low = _plan(conn, table, types)
    w, args = _where(fcol, vals, low)
    return conn.execute(f'SELECT COUNT(*) FROM "{real}"{w}', args).fetchone()[0]


def read_rows(conn, table, types, want_name=False, want_type=False):
    """Yield (geometry, name, type) for each row of the table matching types (name / type are
    None unless asked for and the table has the column)."""
    gcol, tcol, ncol, real, fcol, vals, low = _plan(conn, table, types)
    w, args = _where(fcol, vals, low)
    sel = (f'"{gcol}"' + (f', "{ncol}"' if want_name and ncol else ", NULL")
           + (f', "{tcol}"' if want_type and tcol else ", NULL"))
    cur = conn.execute(f'SELECT {sel} FROM "{real}"{w}', args)
    while True:
        chunk = cur.fetchmany(2000)
        if not chunk:
            return
        for blob, name, typ in chunk:
            if blob is not None:
                yield decode_gpkg(blob), name, typ




def point_features(conn, tables):
    """(features, rows read) for a point layer (place names): {"bbox", "pt", "n": name, "t": the
    source's class}; unnamed rows and repeats (same name and class in the same km) dropped,
    sorted by class then name so the file is the same every time."""
    seen, feats, rows = set(), [], 0
    for table, types in tables:
        for geom, name, typ in read_rows(conn, table, types, want_name=True, want_type=True):
            rows += 1
            name = str(name or "").strip()
            if not name or geom is None or geom.is_empty:
                continue
            pt = geom if geom.geom_type == "Point" else geom.representative_point()
            e, n = int(round(pt.x)), int(round(pt.y))
            key = (name, str(typ).lower(), e // 1000, n // 1000)
            if key not in seen:
                seen.add(key)
                feats.append({"bbox": [e, n, e, n], "pt": [e, n], "n": name, "t": typ})
    feats.sort(key=lambda f: (place_classes.rank_of(f["t"]), f["n"], f["pt"]))
    return feats, rows

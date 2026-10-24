"""--describe for scripts/build_map_layers.py: what is in the named tables of the OS GeoPackages.

READ ONLY. For each table: the GeoPackage it is in, its columns, row count, geometry type and,
for every type-like column (type, class, kind, category, theme, scale ...), the 30 most common
values. Wil sends this output back so the layer build can be matched to the real data.
"""
import sqlite3
from pathlib import Path

from scripts.map_gpkg import decode_gpkg, open_ro

TYPE_LIKE = ("type", "class", "kind", "categ", "theme", "scale")     # in a column's name
COMMON = 30


def _find(source, table):
    """(path, connection) of the first *.gpkg under source holding `table`, else (None, None)."""
    root = Path(source)
    for path in sorted(root.rglob("*.gpkg")) if root.is_dir() else []:
        try:
            conn = open_ro(path)
            hit = conn.execute("SELECT table_name FROM gpkg_contents WHERE lower(table_name)=lower(?)",
                               (table,)).fetchone()
        except sqlite3.Error:
            continue
        if hit:
            return path, conn, hit[0]
        conn.close()
    return None, None, None


def _geometry_type(conn, real, gcol):
    """The registered geometry type, else the type of the first geometry in the table."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(gpkg_geometry_columns)")]
    if "geometry_type_name" in cols:
        row = conn.execute("SELECT geometry_type_name FROM gpkg_geometry_columns "
                           "WHERE lower(table_name)=lower(?)", (real,)).fetchone()
        if row and row[0]:
            return str(row[0])
    row = conn.execute(f'SELECT "{gcol}" FROM "{real}" WHERE "{gcol}" IS NOT NULL LIMIT 1').fetchone()
    try:
        g = decode_gpkg(row[0]) if row else None
        return (g.geom_type.upper() + " (read from the first row)") if g is not None else "(none)"
    except Exception:
        return "(unreadable)"


def describe_table(source, table) -> bool:
    path, conn, real = _find(source, table)
    if conn is None:
        print(f"\n{table}: not found in any .gpkg under {source}")
        return False
    try:
        g = conn.execute("SELECT column_name, srs_id FROM gpkg_geometry_columns "
                         "WHERE lower(table_name)=lower(?)", (real,)).fetchone()
        gcol, srs = (g[0], g[1]) if g else (None, None)
        cols = [(r[1], r[2]) for r in conn.execute(f'PRAGMA table_info("{real}")')]
        n = conn.execute(f'SELECT COUNT(*) FROM "{real}"').fetchone()[0]
        print(f"\n=== {real}  ({path.name})")
        print(f"  rows: {n:,}")
        print(f"  geometry: {_geometry_type(conn, real, gcol) if gcol else '(none registered)'}"
              f", column {gcol}, srs {srs}")
        print("  columns: " + ", ".join(f"{c} {t}".strip() for c, t in cols))
        for c, _t in cols:
            if c == gcol or not any(w in c.lower() for w in TYPE_LIKE):
                continue
            rows = conn.execute(f'SELECT "{c}", COUNT(*) FROM "{real}" GROUP BY "{c}" '
                                f'ORDER BY 2 DESC, 1 LIMIT {COMMON}').fetchall()
            print(f"  most common values of {c} ({len(rows)} shown):")
            for v, k in rows:
                print(f"    {k:>10,}  {v if v is not None else '(null)'}")
        return True
    finally:
        conn.close()


def describe(source, tables) -> int:
    print(f"Describing {', '.join(tables)} in {source}")
    ok = [describe_table(source, t) for t in tables]
    print("\nREAD ONLY. Nothing has been changed.")
    return 0 if all(ok) else 1

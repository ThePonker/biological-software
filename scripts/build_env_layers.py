"""build_env_layers.py -- turn downloaded environment datasets into the Mapping tab's Environment layers.

    py -3.14 scripts\\build_env_layers.py                       # dry run: finds each source, says what it would build
    py -3.14 scripts\\build_env_layers.py --apply               # build every layer that has its source
    py -3.14 scripts\\build_env_layers.py --apply --only sssi,haduk_rain
    py -3.14 scripts\\build_env_layers.py --apply --only phi --types "Deciduous woodland,Lowland fens"
    py -3.14 scripts\\build_env_layers.py --describe sssi        # read-only: each source's columns

Designated sites, ancient woodland, geology, soils, habitat inventories, access land (GeoPackage
or shapefile, EPSG:27700) and the Met Office HadUK-Grid 1991-2020 averages (NetCDF) are read from
--source (default ~/Environment data) and written to data/maps/layers/ (--out): <key>_gb.json and
<key>_county.json for polygons (the same simplification as build_map_layers.py; each feature
carries its name "n" and class "t"), <key>_gb.json + .bin for the value grids. Where to download
each: docs/drafts/environment_layers_downloads.md. Sources that are not EPSG:27700 are refused (no
reprojection). Shapefiles need nothing extra (env_shp.py); NetCDF needs `pip install h5py`, for
this script only. The sources are only read; only the output folder is written.
"""
import argparse
import json
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import paths  # noqa: E402
import shapely  # noqa: E402

from scripts import env_attrs, env_shp  # noqa: E402
from scripts.build_map_layers import LODS, to_features, write_doc  # noqa: E402
from scripts.env_sources import (GRID_BY_KEY, GRID_SPECS, LAYER_SPECS, SPEC_BY_KEY,  # noqa: E402
                                 ancient_code, find_files, is_flag_set, pick_column)
from scripts.map_gpkg import (count_all, feature_tables, open_ro, read_attrs,  # noqa: E402
                              table_columns)
from shared.maps import env_registry as env, value_grid  # noqa: E402


MAX_COUNTY_BYTES = 150 * 1024 * 1024        # a county file bigger than this needs --allow-large


class Problem(Exception):
    """A source that cannot be used; the message says why and is printed as it is."""


# ---- one source file ----
def inspect(path, part):
    """{"path", "kind", "table", "columns", "count", "name", "cls"} for a source file; Problem if it
    is not EPSG:27700, has no usable table, or lacks a required name field."""
    path = Path(path)
    if path.suffix.lower() == ".shp":
        ok, why = env_shp.crs_is_27700(path)
        if not ok:
            raise Problem(f"{path.name}: refused, {why}")
        try:
            info = {"kind": "shp", "table": "", "columns": env_shp.shapefile_columns(path),
                    "count": env_shp.shapefile_count(path)}
        except (OSError, ValueError) as e:
            raise Problem(f"{path.name}: cannot read the .dbf ({e})")
    else:
        try:
            conn = open_ro(path)
            try:
                tables = feature_tables(conn)
                if not tables:
                    raise Problem(f"{path.name}: no feature tables")
                squashed = [(t, "".join(ch for ch in t.lower() if ch.isalnum())) for t in tables]
                # a table with every word of one alternative (BGS's one GeoPackage holds bedrock,
                # superficial, dykes and faults: "625k" alone is in all of them), else any word
                full = [t for t, sq in squashed if any(all(tok in sq for tok in alt)
                                                       for alt in part.any_of)
                        and not any(x in sq for x in part.exclude)]
                hit = full or [t for t, sq in squashed
                               if any(tok in sq for alt in part.any_of for tok in alt)]
                table = tables[0] if len(tables) == 1 else (hit[0] if hit else None)
                if table is None:
                    raise Problem(f"{path.name}: several tables {tables}; none matches - "
                                  "put the file in a folder named for the dataset")
                info = {"kind": "gpkg", "table": table, "columns": table_columns(conn, table),
                        "count": count_all(conn, table)}
            finally:
                conn.close()
        except ValueError as e:
            raise Problem(f"{path.name}: refused, {e}")
        except Exception as e:
            if isinstance(e, Problem):
                raise
            raise Problem(f"{path.name}: cannot be read as a GeoPackage ({e})")
    cols = info["columns"]
    info["path"] = path
    info["name"] = pick_column(cols, part.name, "name") if part.name else None
    info["cls"] = pick_column(cols, part.cls) if part.cls else None
    info["res"] = env_attrs.resolve(cols, part)
    info["flags"] = [(c, label) for c, label in
                     ((pick_column(cols, (f,)), label) for f, label in part.flags) if c]
    if part.only_flagged and not info["flags"]:
        raise Problem(f"{path.name}: none of the fields {[f for f, _ in part.flags]} found; its "
                      f"columns are {cols}. Correct scripts/env_sources.py")
    if part.need_name and not info["name"]:
        raise Problem(f"{path.name}: none of the name fields {list(part.name)} found; its columns "
                      f"are {cols}. Correct scripts/env_sources.py")
    return info


def rows_of(info):
    """Yield (geometry, name, class, [label of each flag field set], {detail column: value}) of
    every row of an inspected source."""
    flags = info.get("flags") or []
    more = info["res"]["cols"]
    want = [c for c in (info["name"], info["cls"]) if c] + [c for c, _ in flags] + more
    if info["kind"] == "shp":
        for geom, rec in env_shp.read_shapefile(info["path"]):
            yield geom, (rec.get(info["name"]) if info["name"] else None), \
                (rec.get(info["cls"]) if info["cls"] else None), \
                [label for c, label in flags if is_flag_set(rec.get(c))], \
                {c: rec.get(c) for c in more}
        return
    conn = open_ro(info["path"])
    try:
        for geom, vals in read_attrs(conn, info["table"], want):
            it = iter(vals)
            name = next(it) if info["name"] else None
            cls = next(it) if info["cls"] else None
            hit = [label for (c, label), v in zip(flags, it) if is_flag_set(v)]
            yield geom, name, cls, hit, dict(zip(more, it))
    finally:
        conn.close()


def _clean(v):
    if v is None:
        return ""
    if isinstance(v, float) and v == int(v):
        v = int(v)
    return str(v).strip()


def labelled(info, part):
    """Yield (geometry, n, t, a, u): n the feature's name, t its class (prefix / fixed / short code),
    a its details [[label, text], ...], u its web link ("" for none)."""
    for geom, name, cls, set_flags, rec in rows_of(info):
        if geom is None or geom.is_empty:
            continue
        if part.only_flagged and not set_flags:
            continue                    # common land: only the rows flagged as common land
        if part.xform == "ancient" and "deleted" in _clean(cls).lower():
            continue                    # NRW AWI: "... Deleted" rows are no longer in the inventory
        if any(_clean(cls).upper().startswith(x) for x in part.skip):
            continue                    # superficial: "DRIFT GEOLOGY NOT MAPPED" is not a deposit
        if not geom.is_valid:
            geom = shapely.make_valid(geom)
        t = _clean(cls)
        if part.xform == "period":
            t = env_attrs.period_of(rec, info["res"])
        elif t and part.xform == "ancient":
            t = ancient_code(t)
        elif t and part.xform == "sentence":
            t = env_attrs.sentence(t)
        if not t and set_flags and not part.only_flagged:
            t = " + ".join(lab for lab in set_flags if lab)      # CRoW: "Open country + ..."
        t = (part.prefix + t) if t else part.fixed
        a, u = env_attrs.details(rec, info["res"], part)
        yield geom, _clean(name), t, a, u


# ---- one layer ----
def prefer_gpkg(files):
    """(files, dropped): where a .shp and a .gpkg of the same source (same folder and name) both
    match, only the .gpkg is kept; `dropped` are the .shp files left out."""
    gp = {(f.parent, f.stem.lower()) for f in files if f.suffix.lower() == ".gpkg"}
    dropped = [f for f in files if f.suffix.lower() == ".shp" and (f.parent, f.stem.lower()) in gp]
    return [f for f in files if f not in dropped], dropped


def find_parts(spec, source):
    return [(p, find_files(source, p.any_of, p.exclude)) for p in spec.parts]


def _mb(n):
    return f"{n / 1048576:,.1f} MB"


def build_polygon_layer(spec, source, out, apply, types=None, allow_large=False, replace=False):
    """Dry run: describe. Apply: write the JSON files. Returns the number of problems."""
    found = find_parts(spec, source)
    infos, problems = [], 0
    for part, files in found:
        files, dropped = prefer_gpkg(files)
        for d in dropped:
            print(f"  {spec.key} / {part.region}: {d.name} skipped, the .gpkg copy of it is used")
        if not files:
            print(f"  {spec.key} / {part.region}: not found (looking for {list(part.any_of)})")
            continue
        for f in files:
            try:
                info = inspect(f, part)
            except Problem as e:
                print(f"  {spec.key} / {part.region}: {e}")
                problems += 1
                continue
            infos.append((info, part))
            print(f"  {spec.key} / {part.region}: {f.name}"
                  + (f" table {info['table']}" if info["table"] else "")
                  + f", {info['count']} features, name field {info['name'] or '-'}, "
                    f"class field {info['cls'] or ('- (fixed: ' + part.fixed + ')' if part.fixed else '-')}"
                  + (f", details {', '.join(x.lower() for x in env_attrs.labels_of(info['res'], part))}"
                     if env_attrs.labels_of(info["res"], part) else "")
                  + (f", flags {', '.join(c for c, _ in info['flags'])}" if info["flags"] else "")
                  + (" (only rows with it set)" if part.only_flagged else ""))
    if problems or not infos:
        if infos and problems:
            print(f"  {spec.key}: NOT built, a source was refused (above)")
        return problems or 0
    if not apply:
        return 0
    lods = [lod for lod in LODS if (spec.gb if lod == "gb" else spec.county)]
    want = {x.strip().lower() for x in (types or [])}
    if want:
        old = [f for f in (Path(out) / f"{spec.key}_{lod}.json" for lod in LODS) if f.is_file()]
        if old and not replace:
            print(f"  {spec.key}: NOT built. {old[0].name} exists and --types would replace it with a "
                  "subset; add --replace if that is what you want. Nothing has been changed.")
            return 1
    docs = []
    for lod in lods:
        tol, area = spec.gb if lod == "gb" else spec.county
        items = []
        for info, part in infos:
            for geom, n, t, a, u in labelled(info, part):
                if want and t.lower() not in want:
                    continue
                items.append((geom, n, t, tuple(map(tuple, a)), u))
        if spec.dissolve:
            groups = {}
            for geom, n, t, a, u in items:
                groups.setdefault((n, t, a, u), []).append(geom)
            items = [(shapely.unary_union(g), *k) for k, g in sorted(groups.items())]
        feats = []
        for geom, n, t, a, u in items:
            for f in to_features(geom, "polygon", tol, area):
                if n:
                    f["n"] = n
                if t:
                    f["t"] = t
                if a:
                    f["a"] = [list(x) for x in a]
                if u:
                    f["u"] = u
                feats.append(f)
        size = len(json.dumps(feats, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        print(f"  {spec.key}_{lod}: {len(feats):,} features, about {_mb(size)}")
        if lod == "county" and size > MAX_COUNTY_BYTES and not allow_large:
            print(f"  {spec.key}: NOT built. The county file would be about {_mb(size)}, over "
                  f"{_mb(MAX_COUNTY_BYTES)}: it would be slow to load and use a lot of memory. Narrow it "
                  f"(--types \"A,B\" for phi) or add --allow-large. Nothing has been written for {spec.key}.")
            return 1
        docs.append((lod, tol, area, feats, len(items)))
    src = "; ".join(f"{part.region}: {info['path'].name}" for info, part in infos)
    for lod, tol, area, feats, rows in docs:
        write_doc(out, spec.key, lod, "polygon", src, " ".join(env.ENV_BY_KEY[spec.key].credits),
                  tol, area, feats, rows)
    return 0


# ---- value grids ----
def build_grid(spec, source, out, apply):
    files = find_files(source, spec.any_of, spec.exclude, exts=(".nc",))
    if not files:
        print(f"  {spec.key}: not found (looking for a .nc whose path has {list(spec.any_of)})")
        return 0
    path = files[0]
    print(f"  {spec.key}: {path.name}, variable {spec.variable}")
    try:
        from scripts import env_netcdf
        values, extent, cell, units = env_netcdf.read_grid(path, spec.variable) if apply else (None,) * 4
    except ImportError:
        print("  h5py is needed to read NetCDF: py -3.14 -m pip install h5py")
        return 1
    except (env_netcdf.NotBritishGrid, ValueError, OSError, KeyError) as e:
        print(f"  {spec.key}: refused, {e}")
        return 1
    if not apply:
        return 0
    import numpy as np
    ok = np.isfinite(values)
    if not ok.any():
        print(f"  {spec.key}: refused, no data in the grid")
        return 1
    rows, cols = np.where(ok)            # crop to the data (the file covers well beyond GB)
    r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    values = values[r0:r1, c0:c1]
    e0, n1 = extent[0] + c0 * cell, extent[3] - r0 * cell
    box = (e0, n1 - values.shape[0] * cell, e0 + values.shape[1] * cell, n1)
    if units and units != spec.units:
        print(f"  note: the file says units '{units}', the layer says '{spec.units}'")
    value_grid.write(out, spec.key, values, box, cell, scale=spec.scale, offset=spec.offset,
                     units=spec.units, label=spec.label, decimals=spec.decimals,
                     attribution=" ".join(env.ENV_BY_KEY[spec.key].credits), source=path.name)
    print(f"  {spec.key}_gb: {values.shape[1]} x {values.shape[0]} cells of {cell:g} m written")
    return 0


# ---- main ----
def main(argv=None) -> int:
    from shared.away_mode import refuse_if_away
    refuse_if_away("build_env_layers")
    keys_all = [s.key for s in LAYER_SPECS] + [g.key for g in GRID_SPECS]
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="build the files (default is a dry run)")
    ap.add_argument("--only", default="", help="comma list of layers: " + ",".join(keys_all))
    ap.add_argument("--types", default="", help="phi only: keep just these main habitats (comma list)")
    ap.add_argument("--allow-large", action="store_true",
                    help="write a county file over 150 MB (else refused; narrow it with --types)")
    ap.add_argument("--replace", action="store_true",
                    help="--types may overwrite an existing phi file with the subset")
    ap.add_argument("--describe", default="", metavar="KEY[,KEY]",
                    help="read-only: the columns of each layer's source files")
    ap.add_argument("--source", default=str(Path.home() / "Environment data"))
    ap.add_argument("--out", default=str(Path(paths.ROOT) / "data" / "maps" / "layers"))
    a = ap.parse_args(argv)
    keys = [k.strip() for k in (a.describe or a.only).split(",") if k.strip()] or keys_all
    bad = [k for k in keys if k not in keys_all]
    if bad:
        print(f"Unknown layer(s) {bad}; choose from {keys_all}. Nothing has been changed.")
        return 1
    mode = "DESCRIBE (read only)" if a.describe else "BUILD" if a.apply else "DRY RUN"
    print(f"\nEnvironment layers ({mode}) <- {a.source} -> {a.out}")
    if not Path(a.source).is_dir():
        print(f"\nThe source folder {a.source} does not exist. See "
              "docs/drafts/environment_layers_downloads.md. Nothing has been changed.")
        return 1
    if a.apply and not a.describe:
        Path(a.out).mkdir(parents=True, exist_ok=True)
    problems = 0
    types = [t for t in a.types.split(",") if t.strip()]
    for key in keys:
        if key in GRID_BY_KEY:
            if not a.describe:
                problems += build_grid(GRID_BY_KEY[key], a.source, a.out, a.apply)
            continue
        spec = SPEC_BY_KEY[key]
        problems += build_polygon_layer(spec, a.source, a.out, a.apply and not a.describe,
                                        types if key == "phi" else None, a.allow_large, a.replace)
        if a.describe:
            for part, files in find_parts(spec, a.source):
                for f in files:
                    try:
                        print(f"    {f.name} columns: {inspect(f, part)['columns']}")
                    except Problem:
                        pass
    done = a.apply and not a.describe
    print("\n" + ("Done." if done and not problems else "Finished with problems." if done else
                  "Nothing has been changed."))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

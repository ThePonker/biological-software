"""A minimal pure-python reader for polygon shapefiles (.shp + .dbf + .prj), for
scripts/build_env_layers.py (25 Oct 2026): no pyshp needed. Read only.

    for geom, record in read_shapefile(path): ...    # shapely (Multi)Polygon, {FIELD: value}

Handles Polygon, PolygonZ and PolygonM; other shape types raise ValueError. crs_is_27700() reads
the .prj text: shapefiles whose .prj is missing or is not the British National Grid are refused
by the caller (no reprojection here).
"""
import re
import struct
from pathlib import Path

from shapely.geometry import MultiPolygon, Polygon

POLYGON_TYPES = (5, 15, 25)


def _prj_is_bng(text):
    """True for a PROJECTED British National Grid: a PROJCS containing British_National_Grid, or a
    Transverse_Mercator with false easting 400000 and false northing -100000 on OSGB36. A geographic
    GCS_OSGB_1936 (degrees) is not."""
    t = re.sub(r"[\s\"]+", "", text).lower()
    if not t.startswith("projcs"):
        return False
    if "british_national_grid" in t:
        return True
    return (re.search(r"transverse_?mercator", t) is not None
            and re.search(r"false_easting,400000(\.0*)?\]", t) is not None
            and re.search(r"false_northing,-100000(\.0*)?\]", t) is not None
            and ("osgb" in t or "airy" in t))


def crs_is_27700(shp_path):
    """(True, "") when the .prj says a projected British National Grid; else (False, the reason)."""
    prj = Path(shp_path).with_suffix(".prj")
    if not prj.is_file():
        return False, "no .prj file, so EPSG:27700 cannot be confirmed"
    text = prj.read_text(encoding="utf-8", errors="replace")
    if _prj_is_bng(text):
        return True, ""
    return False, "its .prj is not a projected British National Grid: " + text[:80].replace("\n", " ")


def _area2(ring):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]))


def _shapes(path):
    """Yield the shapefile's records as lists of rings ([] for a null shape)."""
    with open(path, "rb") as fh:
        data = fh.read()
    stype = struct.unpack("<i", data[32:36])[0]
    if stype not in POLYGON_TYPES and stype != 0:
        raise ValueError(f"{Path(path).name}: shape type {stype} is not a polygon")
    pos = 100
    while pos + 8 <= len(data):
        length = struct.unpack(">i", data[pos + 4:pos + 8])[0] * 2
        body = data[pos + 8:pos + 8 + length]
        pos += 8 + length
        if len(body) < 4 or struct.unpack("<i", body[:4])[0] == 0:
            yield []
            continue
        nparts, npts = struct.unpack("<ii", body[36:44])
        parts = list(struct.unpack(f"<{nparts}i", body[44:44 + 4 * nparts]))
        o = 44 + 4 * nparts
        flat = struct.unpack(f"<{2 * npts}d", body[o:o + 16 * npts])
        pts = list(zip(flat[0::2], flat[1::2]))
        bounds = parts + [npts]
        yield [pts[bounds[i]:bounds[i + 1]] for i in range(nparts)]


def _polygon(rings):
    """Shapefile rings -> shapely geometry: clockwise rings are outer, anticlockwise are holes."""
    outers, holes = [], []
    for r in rings:
        if len(r) < 4:
            continue
        (outers if _area2(r) <= 0 else holes).append(r)
    if not outers:                  # a file with the rings the other way round
        outers, holes = holes, []
    polys = [[o, []] for o in outers]
    for h in holes:
        if len(polys) == 1:
            polys[0][1].append(h)
            continue
        pt = Polygon(h).representative_point()      # inside the hole, whatever its first vertex touches
        covering = [p for p in polys if Polygon(p[0]).covers(pt)]
        if covering:
            min(covering, key=lambda p: Polygon(p[0]).area)[1].append(h)
    geoms = [Polygon(o, hs) for o, hs in polys]
    return geoms[0] if len(geoms) == 1 else MultiPolygon(geoms)


def read_dbf_header(path):
    """([(name, type, length, decimals)], record count) of a .dbf."""
    with open(path, "rb") as fh:
        head = fh.read(32)
        n, hlen = struct.unpack("<IH", head[4:10])
        fh.seek(32)
        raw = fh.read(hlen - 32)
    fields = []
    for i in range(0, len(raw), 32):
        d = raw[i:i + 32]
        if not d or d[0] == 0x0D:
            break
        fields.append((d[:11].split(b"\0")[0].decode("ascii", "replace"), chr(d[11]), d[16], d[17]))
    return fields, n


def _encoding(dbf_path):
    cpg = Path(dbf_path).with_suffix(".cpg")
    return cpg.read_text(errors="replace").strip() if cpg.is_file() else "utf-8"


def _records(dbf_path):
    """Yield each record as a dict (None for a deleted record, so it stays in step with the .shp)."""
    fields, n = read_dbf_header(dbf_path)
    with open(dbf_path, "rb") as fh:
        hlen, rlen = struct.unpack("<HH", (fh.read(12))[8:12])
        fh.seek(hlen)
        enc = _encoding(dbf_path)
        for _ in range(n):
            rec = fh.read(rlen)
            if len(rec) < rlen:
                return
            if rec[:1] == b"*":
                yield None
                continue
            o, out = 1, {}
            for name, ftype, flen, _dec in fields:
                raw = rec[o:o + flen]
                o += flen
                try:
                    text = raw.decode(enc)
                except (UnicodeDecodeError, LookupError):
                    text = raw.decode("cp1252", errors="replace")
                text = text.strip()
                if ftype in "NF":
                    try:
                        out[name] = float(text) if text else None
                    except ValueError:
                        out[name] = None
                else:
                    out[name] = text
            yield out


def shapefile_columns(path):
    return [f[0] for f in read_dbf_header(Path(path).with_suffix(".dbf"))[0]]


def shapefile_count(path):
    return read_dbf_header(Path(path).with_suffix(".dbf"))[1]


def read_shapefile(path):
    """Yield (shapely geometry, {field: value}) for each live record with a shape."""
    path = Path(path)
    for rings, rec in zip(_shapes(path), _records(path.with_suffix(".dbf"))):
        if rec is None or not rings:
            continue
        yield _polygon(rings), rec

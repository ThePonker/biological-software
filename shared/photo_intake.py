"""photo_intake -- records from phone (field) photos (14 Oct 2026). No Qt.

read_photo / grid_ref / group read what the photos carry (EXIF date and GPS); make_rows turns
each group into one Data Entry staging row with its photos attached (held in Photos/_Bench until
commit); attach_to_record / to_species_folder file photos in the species folder (a field photo
lives in the species folder itself, not in Specimen). Photos are only ever moved with os.rename,
never copied, never over another file, never deleted.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from shared import bench_photos, osgb
from shared import photo_files as pf
from shared import photo_links as pl
from shared.photo_names import field_photo_stem

_EXIF_IFD, _GPS_IFD = 0x8769, 0x8825


def _num(v) -> float:
    return float(v)


def _dms(vals, ref) -> Optional[float]:
    d, m, s = (_num(x) for x in vals)
    deg = d + m / 60 + s / 3600
    ref = (ref.decode() if isinstance(ref, bytes) else str(ref or "")).strip().upper()
    if ref in ("S", "W"):
        deg = -deg
    return deg


def read_photo(path) -> dict:
    """{'path','taken' ('YYYY-MM-DD' or ''),'time' ('HH:MM:SS' or ''),'lat','lon' (None if no GPS)}.
    Missing or garbled EXIF gives blanks; never raises."""
    out = {"path": str(path), "taken": "", "time": "", "lat": None, "lon": None}
    try:
        from PIL import Image
        with Image.open(path) as im:
            exif = im.getexif()
            try:
                stamp = exif.get_ifd(_EXIF_IFD).get(0x9003)
            except Exception:
                stamp = None
            try:
                gps = exif.get_ifd(_GPS_IFD)
            except Exception:
                gps = {}
    except Exception:
        return out
    try:
        if isinstance(stamp, bytes):
            stamp = stamp.decode("ascii", "ignore")
        d, _, t = str(stamp or "").strip().partition(" ")
        y, mo, dd = (int(x) for x in d.split(":"))
        import datetime
        out["taken"] = datetime.date(y, mo, dd).isoformat()
        out["time"] = t.strip()[:8]
    except Exception:
        out["taken"], out["time"] = "", ""
    try:
        if gps and gps.get(2) and gps.get(4):
            lat, lon = _dms(gps[2], gps.get(1)), _dms(gps[4], gps.get(3))
            if -90 <= lat <= 90 and -180 <= lon <= 180 and (lat or lon):
                out["lat"], out["lon"] = lat, lon
    except Exception:
        pass
    return out


def grid_ref(lat, lon) -> Optional[str]:
    """6-figure OS grid reference of a WGS84 point, or None (no point, or outside Great Britain)."""
    if lat is None or lon is None:
        return None
    if 51.3 <= lat <= 55.45 and lon < (-6.0 if lat >= 55.0 else -5.45):
        return None                           # Ireland / Northern Ireland: not on the OS grid
    try:
        e, n = osgb.wgs84_to_osgb_en(lat, lon)
        return osgb.en_to_gridref(e, n, digits=6)
    except Exception:
        return None


def _has_gps(p) -> bool:
    return p.get("lat") is not None and p.get("lon") is not None


def group(photos: List[dict], metres: float = 100) -> List[List[dict]]:
    """Photos of one date and place: each group holds one date, and every photo with GPS is
    within `metres` of the group's first GPS photo. Photos without GPS of the same date share one
    group (separate from the GPS ones)."""
    ordered = sorted(photos, key=lambda p: (p.get("taken") or "", p.get("time") or "", p.get("path") or ""))
    groups: List[List[dict]] = []
    for p in ordered:
        for g in groups:
            first = g[0]
            if (first.get("taken") or "") != (p.get("taken") or ""):
                continue
            if _has_gps(p) != _has_gps(first):
                continue
            if not _has_gps(p) or osgb.distance_m(first["lat"], first["lon"], p["lat"], p["lon"]) <= metres:
                g.append(p)
                break
        else:
            groups.append([p])
    return groups


def existing_records(conn, species_name, species_tvk, iso_date, lat=None, lon=None,
                     metres: float = 100) -> list:
    """[(observation id, site_name, grid_ref)] of the same species (TVK, or name when there is
    none) on the same date, at the photo's place (grid-ref centre within metres + half the
    square's size) -- or anywhere when the photo has no GPS. Read only."""
    if not iso_date or not (species_tvk or species_name):
        return []
    if species_tvk:
        where, args = "species_tvk = ?", [species_tvk]
    else:
        where, args = "species_name = ? COLLATE NOCASE", [species_name]
    rows = conn.execute(f"SELECT id, site_name, grid_ref FROM observations WHERE {where} AND date = ? "
                        "ORDER BY id", args + [iso_date]).fetchall()
    out = []
    for r in rows:
        oid, site, ref = r[0], r[1], r[2]
        if lat is not None and lon is not None:
            en = osgb.gridref_to_en(ref) if ref else None
            c = osgb.gridref_to_wgs84(ref) if en else None
            if not c or osgb.distance_m(lat, lon, c[0], c[1]) > metres + en[2] / 2:
                continue
        out.append((oid, site or "", ref or ""))
    return out


def _stem(species: dict, iso_date: str) -> str:
    return field_photo_stem(species.get("species_name") or "", species.get("common_name") or "", iso_date or "")


def make_rows(conn, job_id: int, groups: List[List[dict]], species: dict, defaults: Optional[dict] = None,
              failures: Optional[list] = None) -> List[int]:
    """One staging row per group, its photos attached (moved to Photos/_Bench). Returns the row
    ids. A photo that cannot be moved stays where it is and is added to `failures` as
    (path, reason)."""
    from DataEntry import staging_repo as repo
    defaults = defaults or {}
    ids = []
    for g in groups:
        if not g:
            continue
        iso = g[0].get("taken") or ""
        first_gps = next((p for p in g if _has_gps(p)), None)
        ref = (grid_ref(first_gps["lat"], first_gps["lon"]) if first_gps else None) or ""
        data = {
            "species_name": species.get("species_name"), "species_tvk": species.get("species_tvk"),
            "common_name": species.get("common_name"), "order_name": species.get("order_name"),
            "family": species.get("family"), "taxon_rank": species.get("taxon_rank"),
            "date": iso or None, "grid_ref": ref or None, "quantity": "1",
            "recorder": defaults.get("recorder") or None, "determiner": defaults.get("determiner") or None,
            "site_name": defaults.get("site_name") or None,
        }
        rid = repo.insert_row(conn, job_id, {k: v for k, v in data.items() if v is not None})
        ids.append(rid)
        stem = _stem(species, iso)
        for p in g:
            try:
                bench_photos.attach(conn, Path(p["path"]), rid, stem, field=True)
            except Exception as e:
                if failures is not None:
                    failures.append((p["path"], str(e)))
    conn.commit()
    return ids


def _species_folder(species: dict) -> Path:
    return pf.specimen_folder_for(species.get("species_name") or "", species.get("family") or "",
                                  species.get("order_name") or "").parent


def to_species_folder(conn, src_path, species: dict, iso_date: str) -> str:
    """Move a photo into the species folder (not Specimen), named like a field photo. No link."""
    src = Path(src_path)
    dst = pf.free_path(_species_folder(species), _stem(species, iso_date), src.suffix.lower())
    return pf.move_photo(conn, src, dst)


def attach_to_record(conn, src_path, observation_id: int, species: dict, iso_date: str) -> str:
    """Move a photo into the species folder and link it to an existing observation. If the link
    fails the file goes back where it came from."""
    src = Path(src_path)
    dst = pf.free_path(_species_folder(species), _stem(species, iso_date), src.suffix.lower())
    stored = pf.move_photo(conn, src, dst)
    try:
        pl.add_link(conn, stored, observation_id=observation_id, method=pl.FIELD)
        conn.commit()
    except Exception as e:
        conn.rollback()
        try:
            os.rename(pf.absolute(stored), src)
        except OSError as e2:
            raise OSError(f"not linked ({e}) and could not be put back ({e2}); it is at {stored}")
        raise OSError(f"not linked ({e}); left in the capture folder")
    return stored

"""A8 step 1: what is in the photo library, and how much of it can be linked by name. READ ONLY.

    py -3.14 scripts\\check_media_library.py
    py -3.14 scripts\\check_media_library.py --root "D:\\some\\folder" --csv out.csv --no-match

Walks the library with os.scandir only (directory entries and their attributes). NO FILE IS
EVER OPENED, so a OneDrive cloud-only file is never downloaded: the name, folder, size and the
Windows attribute bits are all read from the directory listing.

Cloud-only test (Windows): st_file_attributes & 0x00400000 (RECALL_ON_DATA_ACCESS, a read would
download it); 0x00080000 PINNED = "Always keep on this device". On another system there are no
such bits and every file is counted as local (the report says so).

Reports: files and GB by top folder and kind (images, videos, other) and by extension; local vs
cloud-only; how many file names follow each convention; UKSI matches (exact / synonym / fuzzy /
none) and the most common unmatched names; species folder vs file name disagreements; microscope
photos with one / several / no specimen of the same species and date. Writes one CSV row per
file (default scripts\\_oneoff\\media_library_check_<date>.csv) -- the only file it writes.
uksi.db and observatum.db are opened read-only.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import paths  # noqa: E402,F401
from shared.photo_names import AREA_LIFE, AREA_MICROSCOPE, PhotoName, parse_photo_path  # noqa: E402

RECALL_ON_DATA_ACCESS = 0x00400000
UNPINNED = 0x00100000
PINNED = 0x00080000
OFFLINE = 0x00001000
GB = 1024 ** 3
FINAL = "READ ONLY. Nothing has been changed. No cloud-only file was opened."


@dataclass
class FileEntry:
    rel: str                     # relative to the root, '/'-separated
    size: int
    attrs: Optional[int]         # None where the system has no attribute bits
    cloud_only: bool
    pinned: bool


def file_attributes(st) -> Optional[int]:
    return getattr(st, "st_file_attributes", None)


def scan_tree(root: Path) -> List[FileEntry]:
    """Every file under root, from directory listings only (never opens a file)."""
    out: List[FileEntry] = []
    stack = [str(root)]
    while stack:
        d = stack.pop()
        try:
            it = os.scandir(d)
        except OSError as e:
            print(f"  ! cannot list {d}: {e}")
            continue
        with it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False):
                        stack.append(e.path)
                        continue
                    if not e.is_file(follow_symlinks=False):
                        continue
                    st = e.stat(follow_symlinks=False)
                except OSError as err:
                    print(f"  ! cannot read the entry {e.path}: {err}")
                    continue
                a = file_attributes(st)
                cloud = bool(a is not None and a & (RECALL_ON_DATA_ACCESS | OFFLINE))
                rel = os.path.relpath(e.path, root).replace(os.sep, "/")
                out.append(FileEntry(rel, st.st_size, a, cloud, bool(a is not None and a & PINNED)))
    out.sort(key=lambda f: f.rel.lower())
    return out


def top_folder(rel: str) -> str:
    parts = rel.split("/")
    if len(parts) == 1:
        return "(root)"
    if parts[0].lower() == "photos" and len(parts) > 2:
        return f"{parts[0]}/{parts[1]}"
    return parts[0]


def analyse(entries: List[FileEntry], matcher=None, specimens=None,
            today: Optional[datetime.date] = None) -> List[dict]:
    """One dict per file: parse + match (+ specimen candidates). Reads only names and the DBs."""
    from shared.photo_match import folder_warnings
    names: List[PhotoName] = [parse_photo_path(f.rel, today=today) for f in entries]
    matches: Dict[tuple, object] = {}
    if matcher is not None:
        matches = matcher.match_many((n.binomial, n.common_name) for n in names if n.binomial)
    rows = []
    for f, n in zip(entries, names):
        pm = matches.get((n.binomial, n.common_name)) if n.binomial else None
        warns = list(n.warnings) + (folder_warnings(n, pm) if pm is not None else [])
        specs = None
        if (specimens is not None and pm is not None and pm.tvk and n.date
                and (n.area == AREA_MICROSCOPE or n.convention == "microscope")):
            specs = specimens.candidates(pm.tvk, n.date, pm.scientific_name or "")
        rows.append({
            "rel_path": f.rel, "top_folder": top_folder(f.rel), "area": n.area, "kind": n.kind,
            "ext": n.ext, "size_bytes": f.size, "cloud_only": int(f.cloud_only),
            "pinned": int(f.pinned), "convention": n.convention or "", "parsed": int(n.parsed),
            "name_source": n.name_source or "", "written_name": n.written_name,
            "binomial": n.binomial, "common_name_in_file": n.common_name,
            "number": "" if n.number is None else n.number, "note": n.note,
            "date": n.date or "", "date_raw": n.date_raw, "folder_name": n.folder_name,
            "folder_agrees": "" if n.folder_agrees is None else int(n.folder_agrees),
            "folder_order": n.folder_order, "folder_family": n.folder_family,
            "warnings": " | ".join(warns),
            "match_status": pm.status if pm is not None else "",
            "match_method": pm.method if pm is not None else "",
            "tvk": (pm.tvk or "") if pm is not None else "",
            "uksi_name": (pm.scientific_name or "") if pm is not None else "",
            "uksi_common": (pm.common_name or "") if pm is not None else "",
            "match_note": pm.note if pm is not None else "",
            "candidates": "; ".join(pm.candidates[:5]) if pm is not None else "",
            "specimen_count": "" if specs is None else len(specs),
            "specimen_ids": "" if not specs else ";".join(
                f"{s['id']}:{s['specimen_code'] or ''}" for s in specs),
        })
    return rows


def write_csv(rows: List[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = list(rows[0]) if rows else ["rel_path"]
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def _gb(n: int) -> str:
    return f"{n / GB:,.2f} GB"


def report(entries: List[FileEntry], rows: List[dict], top: int = 25,
           has_attrs: bool = True, matched: bool = True) -> List[str]:
    L: List[str] = []
    total = sum(f.size for f in entries)
    cloud = [f for f in entries if f.cloud_only]
    L.append(f"Files: {len(entries):,} ({_gb(total)})")
    if has_attrs:
        L.append(f"  local: {len(entries) - len(cloud):,} ({_gb(total - sum(f.size for f in cloud))})"
                 f"   cloud-only: {len(cloud):,} ({_gb(sum(f.size for f in cloud))})"
                 f"   always kept on this device: {sum(f.pinned for f in entries):,}")
    else:
        L.append("  (no Windows file attributes on this system: every file is counted as local)")

    L.append("\nBy top folder (files / GB):  images  videos  other")
    by: Dict[str, Counter] = {}
    for r in rows:
        c = by.setdefault(r["top_folder"], Counter())
        c[r["kind"]] += 1
        c["bytes"] += r["size_bytes"]
        c["cloud"] += r["cloud_only"]
    for k in sorted(by):
        c = by[k]
        L.append(f"  {k:<40} {c['image']:>7,} {c['video']:>7,} {c['other']:>6,}   {_gb(c['bytes'])}"
                 + (f"   cloud-only {c['cloud']:,}" if has_attrs else ""))
    exts = Counter((r["ext"] or "(none)", r["kind"]) for r in rows)
    L.append("\nBy extension: " + ", ".join(f"{e} {n:,} ({k})" for (e, k), n in exts.most_common()))

    imgs = [r for r in rows if r["kind"] == "image"]
    L.append("\nFile names understood (images):")
    for area, conv in ((AREA_LIFE, "life"), (AREA_MICROSCOPE, "microscope")):
        a = [r for r in imgs if r["area"] == area]
        hit = sum(1 for r in a if r["parsed"] and r["convention"] == conv)
        other = sum(1 for r in a if r["parsed"] and r["convention"] != conv)
        folder = sum(1 for r in a if r["name_source"] == "folder")
        dated = sum(1 for r in a if r["date"])
        pct = f"{100 * hit / len(a):.1f}%" if a else "-"
        L.append(f"  {area:<18} {len(a):>6,} images; {hit:,} follow the {conv} convention ({pct})"
                 f"; {other:,} the other one; {folder:,} named from the folder only"
                 + (f"; {dated:,} with a date" if area == AREA_MICROSCOPE else ""))
    rest = [r for r in imgs if r["area"] not in (AREA_LIFE, AREA_MICROSCOPE)]
    L.append(f"  {'elsewhere':<18} {len(rest):>6,} images; {sum(r['parsed'] for r in rest):,} have a species name")
    bad_dates = [r for r in rows if r["date_raw"] and not r["date"]]
    future = [r for r in rows if "in the future" in r["warnings"]]
    L.append(f"  dates that could not be read: {len(bad_dates):,}; dates in the future: {len(future):,}")
    unread = Counter(r["rel_path"].rsplit("/", 1)[0] for r in imgs
                     if r["area"] in (AREA_LIFE, AREA_MICROSCOPE) and not r["binomial"])
    if unread:
        L.append(f"  folders with images whose name was not understood (top {min(top, len(unread))}):")
        L.extend(f"    {n:>5,}  {k}" for k, n in unread.most_common(top))

    if matched:
        named = [r for r in rows if r["binomial"]]
        L.append(f"\nUKSI (files with a name: {len(named):,}; distinct names: "
                 f"{len({r['binomial'] for r in named}):,}):")
        st = Counter(r["match_status"] for r in named)
        for k in ("exact", "exact, review", "synonym, review", "fuzzy, review", "none"):
            L.append(f"  {k:<16} {st.get(k, 0):>6,}")
        un = Counter(r["binomial"] for r in named if r["match_method"] == "none")
        if un:
            L.append(f"  top unmatched names (of {len(un):,}):")
            L.extend(f"    {n:>5,}  {k}" for k, n in un.most_common(top))
        fz = Counter((r["binomial"], r["uksi_name"]) for r in named if r["match_method"] in ("fuzzy", "synonym"))
        if fz:
            L.append("  synonym / fuzzy matches to check (most files first):")
            L.extend(f"    {n:>5,}  {a} -> {b}" for (a, b), n in fz.most_common(top))
    dis = [r for r in rows if r["folder_agrees"] == 0]
    L.append(f"\nSpecies folder and file name disagree: {len(dis):,}")
    L.extend(f"    {r['rel_path']}" for r in dis[:top])
    fw = [r for r in rows if "folder '" in r["warnings"] and r["area"] == AREA_MICROSCOPE]
    L.append(f"Microscope Order/Family folder differs from UKSI (soft check): {len(fw):,}")
    if matched:
        sp = [r for r in rows if r["specimen_count"] != ""]
        one = sum(1 for r in sp if r["specimen_count"] == 1)
        sev = sum(1 for r in sp if r["specimen_count"] > 1)
        L.append(f"\nMicroscope photos with a matched species and a date: {len(sp):,}")
        L.append(f"  exactly one specimen of that species and date: {one:,}")
        L.append(f"  several: {sev:,}")
        L.append(f"  none: {len(sp) - one - sev:,}")
    return L


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(Path.home() / "OneDrive" / "Documents" / "Media"))
    ap.add_argument("--csv", default=None)
    ap.add_argument("--uksi", default=str(paths.UKSI_DB))
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB))
    ap.add_argument("--no-match", action="store_true", help="skip the UKSI and specimen matching")
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args(argv)
    root = Path(a.root)
    out = Path(a.csv) if a.csv else Path(ROOT) / "scripts" / "_oneoff" / \
        f"media_library_check_{datetime.date.today():%Y%m%d}.csv"
    print(f"Library: {root}")
    if not root.is_dir():
        print("  not found -- give the folder with --root")
        print(FINAL)
        return 1
    entries, rows = run_scan(root, None if a.no_match else a.uksi, None if a.no_match else a.db)
    has_attrs = any(f.attrs is not None for f in entries) or os.name == "nt"
    for line in report(entries, rows, a.top, has_attrs, not a.no_match):
        print(line)
    write_csv(rows, out)
    print(f"\nOne row per file written to {out}")
    print(FINAL)
    return 0


def run_scan(root: Path, uksi_path=None, db_path=None):
    """(entries, rows). The scan and the matching: no file under root is opened here."""
    entries = scan_tree(root)
    matcher = specimens = None
    if uksi_path:
        from shared.photo_match import PhotoMatcher, SpecimenIndex
        matcher = PhotoMatcher(uksi_path)
        if db_path and Path(db_path).exists():
            specimens = SpecimenIndex(db_path=db_path)
    return entries, analyse(entries, matcher, specimens)


if __name__ == "__main__":
    sys.exit(main())

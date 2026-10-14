"""photo_review_sheet.py -- a spreadsheet for Wil to settle the photos that have SEVERAL candidate
specimens (photos B2 follow-up, 14 Oct 2026). Read only.

    py -3.14 scripts\\photo_review_sheet.py        # writes scripts\\_oneoff\\photo_review_<date_time>.xlsx

Takes the photos link_specimen_photos.py left as "several specimens" (species and date match
more than one specimen), leaves out any already linked to a specimen (photo_links), and lists
each with its candidate specimens (sex, site, grid ref, collector, drawer). Suggestions go in
"Link to specimen id" only where safe:
  identical group -- N photos, N candidates, and the candidates agree on sex, site, grid ref and
                     collector: photos (names sorted) are paired to candidates (ids ascending);
  sex matches     -- the photo name says male/female and exactly one candidate has that sex.
Otherwise it is blank for Wil. Check or change the column, then run apply_photo_review.py.
Nothing in the library or the database is changed.
"""
import argparse
import datetime
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402
from shared import photo_links as pl  # noqa: E402

SHEET, SUMMARY = "Review", "Summary"
COLS = ["Species", "Photo date", "Photo", "Photo sex", "Photo view", "Candidates",
        "Candidate details", "Link to specimen id", "Why", "Note", "Photo path"]
WIDTHS = [26, 12, 46, 10, 12, 14, 70, 14, 16, 30, 40]
IDENTICAL, SEX_MATCH = "identical group", "sex matches"
_SEX = re.compile(r"(?<![\w])(male|female)(?![\w])", re.IGNORECASE)
_VIEWS = ("gen", "genitalia", "aedeagus", "head", "pronotum", "elytra", "dorsal", "ventral",
          "lateral", "habitus", "face", "frons", "palp", "palps", "antenna", "leg", "abdomen",
          "epigyne", "vulva", "wing")
_VIEW = re.compile(r"(?<![\w])(" + "|".join(_VIEWS) + r")(?![\w])", re.IGNORECASE)


def photo_words(stem: str):
    """(sex word or '', view words) from a photo's file name. Both sexes named -> no sex."""
    sexes = {m.lower() for m in _SEX.findall(stem)}
    views = []
    for v in (m.lower() for m in _VIEW.findall(stem)):
        if v not in views:
            views.append(v)
    return (sexes.pop() if len(sexes) == 1 else ""), " ".join(views)


def parse_ids(text) -> list:
    """Specimen ids from the scan's 'id:code;id:code' text (or any list of numbers)."""
    return [int(x) for x in re.findall(r"\d+", ";".join(
        p.split(":", 1)[0] for p in str(text or "").split(";")))]


def _norm(v) -> str:
    return " ".join(str(v or "").split()).lower()


def _same(cands) -> bool:
    keys = {(_norm(c["sex"]), _norm(c["site_name"]), _norm(c["grid_ref"]), _norm(c["collector"]))
            for c in cands}
    return len(keys) == 1


def describe(c) -> str:
    bits = [c["sex"] or "sex not recorded", " ".join(x for x in (c["site_name"], c["grid_ref"]) if x)]
    if c["collector"]:
        bits.append(f"coll. {c['collector']}")
    if c["drawer_number"]:
        bits.append(f"drawer {c['drawer_number']}")
    code = f" ({c['specimen_code']})" if c["specimen_code"] else ""
    return f"id {c['id']}{code}: " + ", ".join(b for b in bits if b)


def load_details(conn, ids) -> dict:
    out, ids = {}, sorted(set(ids))
    cols = ("id", "specimen_code", "sex", "site_name", "grid_ref", "collector", "drawer_number")
    for i in range(0, len(ids), 900):
        part = ids[i:i + 900]
        for r in conn.execute(f"SELECT {','.join(cols)} FROM specimens WHERE id IN "
                              f"({','.join('?' * len(part))})", part):
            out[r[0]] = dict(zip(cols, r))
    return out


def build_rows(scan_rows, details, linked, root):
    """Review rows (dicts keyed by COLS plus '_uri') for the unlinked several-specimens photos.

    scan_rows: check_media_library rows; details: {specimen id: dict}; linked: set of photo
    paths already linked to a specimen."""
    groups = defaultdict(list)
    for r in scan_rows:
        if not (isinstance(r.get("specimen_count"), int) and r["specimen_count"] > 1):
            continue
        p = pl.norm(r["rel_path"])
        if p in linked:
            continue
        ids = sorted(i for i in parse_ids(r.get("specimen_ids")) if i in details)
        groups[tuple(ids)].append((p, r))
    out, identical_groups = [], 0
    for ids, items in groups.items():
        items.sort(key=lambda t: t[0].rsplit("/", 1)[-1].lower())
        cands = [details[i] for i in ids]
        # one photo per specimen only when every photo shows the same view: two views of one
        # specimen (dorsal, ventral) must not be shared out between two specimens (review)
        views = {photo_words(Path(p).stem)[1] for p, _r in items}
        pair = len(items) == len(ids) > 1 and _same(cands) and len(views) == 1
        identical_groups += pair
        for n, (p, r) in enumerate(items):
            stem = Path(p).stem
            sex, view = photo_words(stem)
            link, why = "", ""
            if pair:
                link, why = ids[n], IDENTICAL
            elif sex:
                hit = [c["id"] for c in cands if _norm(c["sex"]) == sex]
                if len(hit) == 1:
                    link, why = hit[0], SEX_MATCH
            out.append({
                "Species": r.get("uksi_name") or r.get("binomial") or "", "Photo date": r.get("date") or "",
                "Photo": p.rsplit("/", 1)[-1], "Photo sex": sex, "Photo view": view,
                "Candidates": ", ".join(str(i) for i in ids),
                "Candidate details": "\n".join(describe(c) for c in cands),
                "Link to specimen id": link, "Why": why, "Note": "", "Photo path": p,
                "_uri": (Path(root) / p).as_uri()})
    out.sort(key=lambda d: (d["Species"].lower(), d["Photo date"], d["Candidates"], d["Photo"].lower()))
    return out, identical_groups


def counts(rows, identical_groups) -> list:
    n_ident = sum(1 for r in rows if r["Why"] == IDENTICAL)
    n_sex = sum(1 for r in rows if r["Why"] == SEX_MATCH)
    return [("Photos to review", len(rows)), ("Identical groups", identical_groups),
            ("Photos suggested: identical group", n_ident), ("Photos suggested: sex matches", n_sex),
            ("Suggested in all", n_ident + n_sex), ("Left for Wil", len(rows) - n_ident - n_sex)]


def write_xlsx(rows, summary, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET
    ws.append(COLS)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="44546A")
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for r in rows:
        ws.append([r[c] for c in COLS])
        cell = ws.cell(row=ws.max_row, column=COLS.index("Photo") + 1)
        cell.hyperlink = r["_uri"]
        cell.font = Font(color="0563C1", underline="single")
        ws.cell(row=ws.max_row, column=COLS.index("Link to specimen id") + 1).fill = \
            PatternFill("solid", fgColor="FFF2CC")
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    for i, w in enumerate(WIDTHS, 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    sm = wb.create_sheet(SUMMARY)
    sm.append(["Photos with several candidate specimens", "Count"])
    for k, v in summary:
        sm.append([k, v])
    sm.column_dimensions["A"].width = 44
    sm["A1"].font = sm["B1"].font = Font(bold=True)
    path = Path(path)
    if path.exists():                     # never over a sheet Wil may have filled in
        raise FileExistsError(f"{path} already exists -- give another --out")
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=str(paths.MEDIA_ROOT))
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--uksi", default=str(paths.UKSI_DB), help=argparse.SUPPRESS)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    from scripts.check_media_library import run_scan
    root = Path(a.root)
    print(f"\nPhotos -- review sheet\n  library: {root}\n  observatum.db: {a.db}")
    if not root.is_dir():
        print("  library not found (give it with --root). Nothing has been changed.")
        return 1
    ro = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        linked = set()
        if pl.has_table(ro):
            linked = {pl.norm(r[0]) for r in ro.execute(
                f"SELECT photo_path FROM {pl.TABLE} WHERE specimen_id IS NOT NULL")}
        _entries, scan = run_scan(root, a.uksi, a.db)
        ids = {i for r in scan if isinstance(r.get("specimen_count"), int) and r["specimen_count"] > 1
               for i in parse_ids(r.get("specimen_ids"))}
        details = load_details(ro, ids)
    finally:
        ro.close()
    rows, groups = build_rows(scan, details, linked, root)
    summary = counts(rows, groups)
    out = a.out or os.path.join(_ROOT, "scripts", "_oneoff",
                                f"photo_review_{datetime.datetime.now():%Y%m%d_%H%M%S}.xlsx")
    write_xlsx(rows, summary, out)
    for k, v in summary:
        print(f"  {k:<36}{v:>6,}")
    print(f"  sheet written to {out}\n\nNothing has been changed (library and database read only).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

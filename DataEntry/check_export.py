"""check_export -- "Export for checking": rows of a Data Entry job as a spreadsheet plus a
folder of copies of their photos, to send to someone who can say what the animal is.

No Qt here (the dialog is check_export_dialog.py) and nothing is written to the database. The
photos are COPIES (new files in a new folder outside the library; the library is never touched).
Each export gets a folder of its own that never existed before -- an existing one is never
written into.
"""
from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List
from urllib.parse import quote

from DataEntry import date_utils
from DataEntry import staging_repo as repo

# (label, staging key) in the order the dialog lists them
CHECK_COLUMNS = [
    ("Species", "species_name"), ("Common name", "common_name"), ("Date", "date"),
    ("Site", "site_name"), ("Grid ref", "grid_ref"), ("VC", "vice_county"), ("Sex", "sex"),
    ("Stage", "stage"), ("No.", "quantity"), ("Method", "method"),
    ("Determiner", "determiner"), ("Comment", "comment"), ("Check note", "check_note"),
]
DEFAULT_COLUMNS = ["Species", "Common name", "Date", "Sex", "Stage", "No.", "Check note"]
REPLY_COLUMNS = ["Agree?", "Their ID", "Notes"]       # left empty, for the reply
# which Data Entry row each Ref stands for (17 Oct 2026): a hidden sheet in the workbook, which
# travels with the checker's reply, and the same list in refs.json in the export's folder, for
# a reply that comes back as a CSV. check_readback.py reads them.
REFS_SHEET = "_rows"
DATA_SHEET = "For checking"
REFS_FILE = "refs.json"
REFS_HEAD = ["Ref", "row_id", "job_id", "species"]


def default_out_root() -> Path:
    """Documents\\Observatum exports (the photo library's folder is Documents\\Media)."""
    import paths
    return Path(paths.MEDIA_ROOT).parent / "Observatum exports"


def _safe(name: str) -> str:
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", str(name or "")).strip(" .")
    return " ".join(s.split()) or "job"


def new_folder(out_root: Path, job_name: str, today: date = None) -> Path:
    """Create (never reuse) out_root / "<job> for checking dd-mm-yyyy", adding " (2)", " (3)"."""
    today = today or date.today()
    base = f"{_safe(job_name)} for checking {today.strftime('%d-%m-%Y')}"
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    n = 1
    while True:
        folder = out_root / (base if n == 1 else f"{base} ({n})")
        try:
            folder.mkdir()                     # fails if it exists: never write into one
            return folder
        except FileExistsError:
            n += 1


def _free_name(folder: Path, name: str) -> str:
    """name, or "stem (2).ext", "stem (3).ext" ... if a file of that name is already there."""
    p = Path(name)
    cand, n = name, 1
    while (folder / cand).exists():
        n += 1
        cand = f"{p.stem} ({n}){p.suffix}"
    return cand


def _cell(row: Dict, key: str) -> str:
    v = row.get(key)
    if key == "vice_county" and v in (None, ""):
        v = row.get("vc_number")
    if v in (None, ""):
        return ""
    return date_utils.to_display(v) if key == "date" else str(v)


def _copy_photos(conn, ref: str, row_id: int, photos_dir: Path, counts: Dict) -> List[str]:
    """Copy one row's photos into photos_dir as "<ref> <original name>"; the new names."""
    from shared import photo_files, photo_links
    names = []
    for stored in photo_links.photos_for_staging(conn, row_id):
        src = photo_files.absolute(stored)
        if not src.is_file():
            counts["missing"] += 1
            continue
        photos_dir.mkdir(exist_ok=True)
        name = _free_name(photos_dir, f"{ref} {src.name}")
        shutil.copy2(src, photos_dir / name)               # a copy: the library is untouched
        counts["copied"] += 1
        names.append(name)
    return names


def export_for_checking(conn, job: Dict, row_ids: Iterable[int], columns: Iterable[str],
                        out_root) -> Dict:
    """Write the folder for `row_ids` (in that order) and return
    {rows, photos_copied, photos_missing, folder, xlsx}. `columns`: labels from CHECK_COLUMNS."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    import paths
    lib = Path(paths.MEDIA_ROOT).resolve()  # copies inside the library would read as duplicates
    out = Path(out_root).resolve()
    if out == lib or lib in out.parents:
        raise ValueError(f"Choose an exports folder outside the photo library ({paths.MEDIA_ROOT}).")
    keys = dict(CHECK_COLUMNS)
    chosen = [c for c in columns if c in keys]
    by_id = {r["id"]: r for r in repo.fetch_rows(conn, job["id"])}
    rows = [by_id[i] for i in row_ids if i in by_id]
    folder = new_folder(Path(out_root), job.get("name") or "job")
    photos_dir = folder / "photos"
    counts = {"copied": 0, "missing": 0}

    lines = []                                             # (ref, row, [photo names])
    for n, row in enumerate(rows, start=1):
        ref = f"R{n:03d}"
        lines.append((ref, row, _copy_photos(conn, ref, row["id"], photos_dir, counts)))
    extra = max([len(p) for _r, _w, p in lines] + [1]) - 1          # "Photo 2", "Photo 3" ...

    # Row id: Data Entry's own number for the row; the read-back checks it against the list
    head = ["Ref", "Row id"] + chosen + ["Photos"] + [f"Photo {i}" for i in range(2, extra + 2)] + REPLY_COLUMNS
    wb = Workbook()
    ws = wb.active
    ws.title = DATA_SHEET
    ws.append(head)
    link_font = Font(color="0563C1", underline="single")
    for ref, row, photos in lines:
        ws.append([ref, row["id"]] + [_cell(row, keys[c]) for c in chosen]
                  + ["\n".join(photos)] + [""] * extra + [""] * len(REPLY_COLUMNS))
        r = ws.max_row
        first = 3 + len(chosen)                                      # the Photos column
        for i, name in enumerate(photos):
            c = ws.cell(row=r, column=first + i)
            if i > 0:
                c.value = name
            c.hyperlink = "photos/" + quote(name)
            c.font = link_font
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "A2"
    for col in ws.columns:
        width = max(len(line) for cell in col for line in str(cell.value or "").split("\n"))
        ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 10), 50)
        for cell in col:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    refs = wb.create_sheet(REFS_SHEET)
    refs.append(REFS_HEAD)
    for ref, row, _photos in lines:
        refs.append([ref, row["id"], job["id"], row.get("species_name") or ""])
    refs.sheet_state = "hidden"
    xlsx = folder / f"{folder.name}.xlsx"
    wb.save(xlsx)
    import json
    (folder / REFS_FILE).write_text(json.dumps(
        {"job_id": job["id"], "job": job.get("name") or "",
         "rows": [{"ref": ref, "row_id": row["id"], "species": row.get("species_name") or ""}
                  for ref, row, _p in lines]}, indent=1), encoding="utf-8")
    return {"rows": len(rows), "photos_copied": counts["copied"],
            "photos_missing": counts["missing"], "folder": str(folder), "xlsx": str(xlsx)}

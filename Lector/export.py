"""Export harvested pages as readable text bundles with citation headers.

One .txt per species or saved search (pages in date order, each headed by its
citation - authors and article title where BHL gives them - and BHL link)
plus an index CSV: the format to read through, or to bring to Claude for
fact extraction.
"""
import csv
import re

from . import config
from .entries import citation as _citation, prepare_row

RULE = "=" * 78


def _safe_filename(name):
    return re.sub(r"[^\w\-. ]+", "_", name).strip().replace(" ", "_") or "species"


def citation(row):
    return _citation(prepare_row(row))


def write_text_bundle(title, rows, out_dir, stem):
    """Write <stem>.txt and <stem>_index.csv; returns (txt_path, n_pages)."""
    rows = [prepare_row(r) for r in rows]
    if not rows:
        return None, 0
    rows.sort(key=lambda r: (r["year"] is None, r["year"] or 0, r["title"] or "", r["page_id"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    txt_path = out_dir / f"{stem}.txt"
    csv_path = out_dir / f"{stem}_index.csv"

    with txt_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{title} - BHL pages harvested by Lector\n")
        fh.write(f"{len(rows)} pages. OCR text is unverified: check names, "
                 "numbers and localities against the page image.\n")
        for row in rows:
            fh.write(f"\n{RULE}\n{_citation(row)}\n{row['page_url']}\n")
            fh.write(f"Matched as: {row['matched_names']}   "
                     f"Text source: {row['text_source'] or 'not fetched'}\n")
            if row["notes"]:
                fh.write(f"Your note: {row['notes']}\n")
            fh.write(f"{RULE}\n")
            fh.write((row["ocr_text"] or "[no text fetched]").strip() + "\n")

    # authors / article_title only when BHL gave one for some page (L15, Round 8)
    optional = [k for k in ("authors", "article_title")
                if any((row[k] or "").strip() for row in rows)]
    cols = ["page_id", "year", "title", "volume", "page_label", "matched_names", "page_url",
            "has_text"] + optional + ["citation"]
    head = {"page_label": "page"}
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([head.get(c, c) for c in cols])
        for row in rows:
            vals = dict(row, has_text="yes" if row["ocr_text"] else "no",
                        citation=_citation(row))
            writer.writerow([vals[c] for c in cols])
    return txt_path, len(rows)


CONSOLE_SUFFIX = "_all_pages"


def console_stem(accepted_name):
    """File names of the console's exports: '<Species>_all_pages' (Round 8 review). The
    console exports every page ever linked to the species, withdrawn ones too; the window
    exports a saved search's own pages as '<Search>'. Different names, so neither
    overwrites the other."""
    return _safe_filename(accepted_name) + CONSOLE_SUFFIX


def export_species(store, accepted_name, out_dir=config.EXPORT_DIR):
    """Console export: <Species>_all_pages.txt and <Species>_all_pages_index.csv."""
    return write_text_bundle(accepted_name, store.pages_for_species(accepted_name),
                             out_dir, console_stem(accepted_name))

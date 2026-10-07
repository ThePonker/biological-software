"""Export harvested pages as readable text bundles with citation headers.

One .txt per species (pages in date order, each headed by its citation and
BHL link) plus an index CSV - the format to read through, or to bring to
Claude for fact extraction.
"""
import csv
import re

from . import config

RULE = "=" * 78


def _safe_filename(name):
    return re.sub(r"[^\w\-. ]+", "_", name).strip().replace(" ", "_") or "species"


def citation(row):
    bits = [row["title"] or "Untitled"]
    if row["volume"]:
        bits.append(str(row["volume"]))
    if row["year"]:
        bits.append(f"({row['year']})")
    if row["page_label"]:
        bits.append(row["page_label"])
    return ", ".join(bits)


def export_species(store, accepted_name, out_dir=config.EXPORT_DIR):
    rows = store.pages_for_species(accepted_name)
    if not rows:
        return None, 0
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_filename(accepted_name)
    txt_path = out_dir / f"{stem}.txt"
    csv_path = out_dir / f"{stem}_index.csv"

    with txt_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{accepted_name} - BHL pages harvested by Lector\n")
        fh.write(f"{len(rows)} pages. OCR text is unverified: check names, "
                 "numbers and localities against the page image.\n")
        for row in rows:
            fh.write(f"\n{RULE}\n{citation(row)}\n{row['page_url']}\n")
            fh.write(f"Matched as: {row['matched_names']}   "
                     f"Text source: {row['text_source'] or 'not fetched'}\n{RULE}\n")
            fh.write((row["ocr_text"] or "[no text fetched]").strip() + "\n")

    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["page_id", "year", "title", "volume", "page",
                         "matched_names", "page_url", "has_text"])
        for row in rows:
            writer.writerow([row["page_id"], row["year"], row["title"], row["volume"],
                             row["page_label"], row["matched_names"], row["page_url"],
                             "yes" if row["ocr_text"] else "no"])
    return txt_path, len(rows)

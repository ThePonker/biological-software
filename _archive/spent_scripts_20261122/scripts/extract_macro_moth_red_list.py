"""
Extract macro-moth Red List data from Fox et al. (2019) PDF.

Downloads Appendix 1 table from the Butterfly Conservation report PDF
and produces a CSV ready for import_codex_review.py.

Prerequisites:
    pip install pdfplumber --break-system-packages

Usage:
    1. Download the PDF from Butterfly Conservation:
       https://butterfly-conservation.org/sites/default/files/2022-01/
       S19-17%20A%20review%20of%20the%20status%20of%20the%20macro-moths%20of%20Great%20Britain.pdf
    
    2. Save it somewhere accessible, e.g.:
       data/reviews/macro-moth-red-list-2019.pdf
    
    3. Run:
       python scripts/extract_macro_moth_red_list.py data/reviews/macro-moth-red-list-2019.pdf
    
    4. Output: data/reviews/macro_moth_red_list_2019.csv
    
    5. Import into Codex:
       python scripts/import_codex_review.py data/reviews/macro_moth_red_list_2019.csv ^
           --name "GB Macro-moth Red List" ^
           --author "Fox, Parsons & Harrower, 2019" ^
           --group "Lepidoptera" ^
           --track gb_red_list ^
           --date 2019-01-01 ^
           --dry-run

       Then remove --dry-run to import for real.
       Then run: python scripts/seed_codex.py   (for SQS gap-fill)
"""

import sys
import csv
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("pdfplumber not installed. Run:")
    print("  pip install pdfplumber --break-system-packages")
    sys.exit(1)


# Valid IUCN Red List categories from the review
VALID_RED_LIST = {"RE", "CR", "CR(PE)", "EN", "VU", "NT", "DD", "LC", "NA", "NE"}

# Valid GB Rarity statuses
VALID_RARITY = {"NR", "NS"}


def extract_appendix(pdf_path: str, output_dir: str = None):
    """Extract Appendix 1 species table from the macro-moth PDF."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return None

    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = pdf_path.parent

    print(f"Reading: {pdf_path}")
    print(f"This may take a minute for a large PDF...")

    species_data = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        print(f"  Pages: {len(pdf.pages)}")

        # The appendix is typically in the latter portion of the PDF.
        # We look for table rows that have a species name pattern
        # (italic binomial) and an IUCN category.
        
        in_appendix = False
        
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            
            # Detect start of Appendix 1
            if "Appendix 1" in text and "status review" in text.lower():
                in_appendix = True
                print(f"  Found Appendix 1 start at page {page_num + 1}")
            
            if not in_appendix:
                continue
            
            # Try table extraction
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    for row in table:
                        if not row or len(row) < 2:
                            continue
                        _parse_row(row, species_data)
            else:
                # Fallback: parse text lines
                for line in text.split("\n"):
                    parts = line.split()
                    if len(parts) >= 3:
                        _parse_text_line(parts, species_data)

    if not species_data:
        print("\n  WARNING: No species data extracted from tables.")
        print("  The PDF structure may differ from expected.")
        print("  Try opening the PDF and manually checking Appendix 1.")
        print("  The appendix should have columns like:")
        print("    Species name | Red List | GB Rarity | ...")
        print("")
        print("  If the PDF has a different structure, you may need to")
        print("  extract the data manually into a CSV with columns:")
        print("    species_name,status_value")
        return None

    # Deduplicate (keep first occurrence)
    seen = set()
    unique = []
    for entry in species_data:
        key = entry["species_name"]
        if key not in seen:
            seen.add(key)
            unique.append(entry)

    # Write Red List CSV
    red_list_path = out_dir / "macro_moth_red_list_2019.csv"
    red_list_entries = [e for e in unique if e.get("red_list")]
    _write_csv(red_list_path, red_list_entries, "red_list")
    print(f"\n  Red List CSV: {red_list_path}")
    print(f"  Species with Red List category: {len(red_list_entries)}")

    # Write Rarity CSV (separate track)
    rarity_path = out_dir / "macro_moth_rarity_2019.csv"
    rarity_entries = [e for e in unique if e.get("rarity")]
    if rarity_entries:
        _write_csv(rarity_path, rarity_entries, "rarity")
        print(f"  Rarity CSV: {rarity_path}")
        print(f"  Species with Rarity status: {len(rarity_entries)}")

    # Summary
    categories = {}
    for e in red_list_entries:
        cat = e["red_list"]
        categories[cat] = categories.get(cat, 0) + 1
    print(f"\n  Red List breakdown:")
    for cat in ["RE", "CR", "CR(PE)", "EN", "VU", "NT", "DD", "LC", "NA", "NE"]:
        if cat in categories:
            print(f"    {cat:8s}  {categories[cat]:>4}")

    return red_list_path


def _parse_row(row, species_data):
    """Parse a table row looking for species name + IUCN category."""
    # Clean cells
    cells = [(c or "").strip() for c in row]
    
    # Look for a binomial name (two capitalised/lowercase words)
    # and an IUCN category in any cell
    species_name = None
    red_list = None
    rarity = None
    
    for cell in cells:
        # Check for IUCN category
        upper = cell.upper().strip()
        if upper in VALID_RED_LIST:
            red_list = upper
        elif upper in VALID_RARITY:
            rarity = upper
        
        # Check for species name (binomial: Genus species)
        words = cell.split()
        if len(words) >= 2 and words[0][0].isupper() and words[1][0].islower():
            # Likely a binomial
            candidate = f"{words[0]} {words[1]}"
            if len(words[0]) > 2 and len(words[1]) > 2:
                if not any(c.isdigit() for c in candidate):
                    species_name = candidate
    
    if species_name and (red_list or rarity):
        species_data.append({
            "species_name": species_name,
            "red_list": red_list,
            "rarity": rarity,
        })


def _parse_text_line(parts, species_data):
    """Fallback: parse a text line for species + category."""
    if len(parts) < 3:
        return
    
    # Look for binomial at start
    if parts[0][0].isupper() and len(parts[0]) > 2:
        if parts[1][0].islower() and len(parts[1]) > 2:
            species_name = f"{parts[0]} {parts[1]}"
            if any(c.isdigit() for c in species_name):
                return
            
            # Look for category in remaining parts
            for p in parts[2:]:
                upper = p.upper().strip("(),.")
                if upper in VALID_RED_LIST:
                    species_data.append({
                        "species_name": species_name,
                        "red_list": upper,
                        "rarity": None,
                    })
                    return
                if upper in VALID_RARITY:
                    species_data.append({
                        "species_name": species_name,
                        "red_list": None,
                        "rarity": upper,
                    })
                    return


def _write_csv(path, entries, value_key):
    """Write entries to a CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["species_name", "status_value"])
        for entry in entries:
            writer.writerow([entry["species_name"], entry[value_key]])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/extract_macro_moth_red_list.py <path-to-pdf>")
        print("")
        print("Download the PDF first from:")
        print("  https://butterfly-conservation.org/sites/default/files/2022-01/")
        print("  S19-17%20A%20review%20of%20the%20status%20of%20the%20macro-moths%20of%20Great%20Britain.pdf")
        sys.exit(1)

    result = extract_appendix(sys.argv[1])
    if result:
        print(f"\nDone. Import with:")
        print(f'  python scripts/import_codex_review.py "{result}" ^')
        print(f'      --name "GB Macro-moth Red List" ^')
        print(f'      --author "Fox, Parsons & Harrower, 2019" ^')
        print(f'      --group "Lepidoptera" ^')
        print(f'      --track gb_red_list ^')
        print(f'      --date 2019-01-01 ^')
        print(f'      --dry-run')

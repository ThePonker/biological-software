"""
Extract sawfly Phase 1 Red List data from Musgrove (2022) PDF.

Prerequisites:
    pip install pdfplumber --break-system-packages

Usage:
    1. Download the PDF:
       https://www.sawflies.org.uk/wp-content/uploads/2022/10/Sawfly-Review-Phase-1-FINAL.pdf
    
    2. Save it, e.g.: data/reviews/sawfly-phase1-2022.pdf
    
    3. Run:
       python scripts/extract_sawfly_red_list.py data/reviews/sawfly-phase1-2022.pdf
    
    4. Outputs:
       - data/reviews/sawfly_red_list_2022.csv  (IUCN Red List categories)
       - data/reviews/sawfly_rarity_2022.csv    (NR/NS rarity statuses)
    
    5. Import Red List into Codex:
       python scripts/import_codex_review.py data/reviews/sawfly_red_list_2022.csv ^
           --name "GB Sawfly Red List Phase 1" ^
           --author "Musgrove, 2022" ^
           --group "Hymenoptera: Symphyta" ^
           --track gb_red_list ^
           --date 2022-10-01 ^
           --dry-run
    
    6. Import Rarity into Codex (separate track):
       python scripts/import_codex_review.py data/reviews/sawfly_rarity_2022.csv ^
           --name "GB Sawfly Rarity Phase 1" ^
           --author "Musgrove, 2022" ^
           --group "Hymenoptera: Symphyta" ^
           --track gb_rarity ^
           --date 2022-10-01 ^
           --dry-run
"""

import sys
import csv
import re
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("pdfplumber not installed. Run:")
    print("  pip install pdfplumber --break-system-packages")
    sys.exit(1)


VALID_RED_LIST = {"RE", "CR", "CR(PE)", "EN", "VU", "NT", "DD", "LC", "NA", "NE"}
VALID_RARITY = {"NR", "NS"}


def extract_sawfly(pdf_path: str, output_dir: str = None):
    """Extract species status data from the sawfly Phase 1 PDF."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return None

    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = pdf_path.parent

    print(f"Reading: {pdf_path}")

    red_list = []  # species_name, category
    rarity = []    # species_name, NR/NS
    all_text = ""

    with pdfplumber.open(str(pdf_path)) as pdf:
        print(f"  Pages: {len(pdf.pages)}")

        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            all_text += text + "\n"

            # Try table extraction on every page
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    for row in table:
                        if not row or len(row) < 2:
                            continue
                        _parse_sawfly_row(row, red_list, rarity)

    # If table extraction didn't find much, try text parsing
    if len(red_list) < 10:
        print(f"  Table extraction found {len(red_list)} Red List entries — trying text parsing...")
        _parse_sawfly_text(all_text, red_list, rarity)

    # Deduplicate
    red_list = _dedup(red_list)
    rarity = _dedup(rarity)

    if not red_list and not rarity:
        print(f"\n  WARNING: No species data extracted.")
        print(f"  The PDF structure may differ from expected.")
        print(f"  Try manually extracting the results tables.")
        print(f"  Expected: species name + IUCN category + NR/NS rarity")
        return None

    # Write Red List CSV
    if red_list:
        rl_path = out_dir / "sawfly_red_list_2022.csv"
        with open(rl_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["species_name", "status_value"])
            for name, cat in red_list:
                writer.writerow([name, cat])
        print(f"\n  Red List CSV: {rl_path}")
        print(f"  Species: {len(red_list)}")
        cats = {}
        for _, c in red_list:
            cats[c] = cats.get(c, 0) + 1
        for c in ["RE", "CR", "EN", "VU", "NT", "DD", "LC"]:
            if c in cats:
                print(f"    {c:4s}  {cats[c]:>3}")

    # Write Rarity CSV
    if rarity:
        rar_path = out_dir / "sawfly_rarity_2022.csv"
        with open(rar_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["species_name", "status_value"])
            for name, status in rarity:
                writer.writerow([name, status])
        print(f"\n  Rarity CSV: {rar_path}")
        print(f"  NR: {sum(1 for _, s in rarity if s == 'NR')}")
        print(f"  NS: {sum(1 for _, s in rarity if s == 'NS')}")

    return out_dir / "sawfly_red_list_2022.csv" if red_list else None


def _parse_sawfly_row(row, red_list, rarity):
    """Parse a table row for species name + status."""
    cells = [(c or "").strip() for c in row]

    species_name = None
    rl_cat = None
    rar_cat = None

    for cell in cells:
        upper = cell.upper().strip()
        if upper in VALID_RED_LIST:
            rl_cat = upper
        elif upper in VALID_RARITY:
            rar_cat = upper

        # Binomial detection
        words = cell.split()
        if len(words) >= 2 and words[0][0].isupper() and words[1][0].islower():
            candidate = f"{words[0]} {words[1]}"
            if len(words[0]) > 2 and len(words[1]) > 2:
                if not any(c.isdigit() for c in candidate):
                    species_name = candidate

    if species_name:
        if rl_cat:
            red_list.append((species_name, rl_cat))
        if rar_cat:
            rarity.append((species_name, rar_cat))


def _parse_sawfly_text(text, red_list, rarity):
    """Fallback: parse full text for species + status patterns."""
    # Pattern: "Species name ... CR" or "Species name ... NR"
    # The review uses lines like "Arge berberidis ... RE"
    binomial = re.compile(
        r'([A-Z][a-z]{2,})\s+([a-z]{2,}(?:\s+[a-z]+)?)'  # Genus species (optional subsp)
    )

    lines = text.split("\n")
    for line in lines:
        match = binomial.search(line)
        if not match:
            continue

        species = f"{match.group(1)} {match.group(2).split()[0]}"

        # Look for category after the species name
        remainder = line[match.end():]
        words = remainder.upper().split()
        for w in words:
            w = w.strip("(),.")
            if w in VALID_RED_LIST:
                red_list.append((species, w))
                break
            if w in VALID_RARITY:
                rarity.append((species, w))
                break


def _dedup(pairs):
    """Deduplicate (species, status) pairs, keeping first."""
    seen = set()
    result = []
    for name, status in pairs:
        if name not in seen:
            seen.add(name)
            result.append((name, status))
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/extract_sawfly_red_list.py <path-to-pdf>")
        print("")
        print("Download the PDF from:")
        print("  https://www.sawflies.org.uk/wp-content/uploads/2022/10/Sawfly-Review-Phase-1-FINAL.pdf")
        sys.exit(1)

    result = extract_sawfly(sys.argv[1])
    if result:
        print(f"\nDone. Import Red List with:")
        print(f'  python scripts/import_codex_review.py "{result}" ^')
        print(f'      --name "GB Sawfly Red List Phase 1" ^')
        print(f'      --author "Musgrove, 2022" ^')
        print(f'      --group "Hymenoptera: Symphyta" ^')
        print(f'      --track gb_red_list ^')
        print(f'      --date 2022-10-01 ^')
        print(f'      --dry-run')

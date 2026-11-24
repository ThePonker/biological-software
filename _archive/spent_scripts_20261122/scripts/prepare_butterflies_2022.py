"""Butterflies 2022 Red List -> standard extracted CSVs for load_review.py.

Reads   data\\reviews\\lepidoptera_butterflies_fox_2022\\extracted\\butterfly_red_list_2022.csv
        (species_name, status_value, notes -- hand-prepared in March 2026)
Writes  review.csv    citation, tracks_assessed = threat (a Red List only: no
                      rarity assessment, so rarity statuses are left alone)
        statuses.csv  species_name, tvk (blank: matched by name), iucn_status,
                      qualifying_criteria (= the notes), rarity (blank)
        accounts.csv  header only -- the paper has no species accounts

Checks the totals against the paper (Fox et al. 2022): 62 species --
RE 4, EN 8, VU 16, NT 5, LC 29. Writes NOTHING if they differ.

Run:  python scripts\\prepare_butterflies_2022.py
"""
import csv, os, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "reviews", "lepidoptera_butterflies_fox_2022", "extracted")
SRC = os.path.join(D, "butterfly_red_list_2022.csv")
EXPECT = {"RE": 4, "EN": 8, "VU": 16, "NT": 5, "LC": 29}

rows = [r for r in csv.DictReader(open(SRC, encoding="utf-8-sig")) if (r.get("species_name") or "").strip()]
got = Counter((r["status_value"] or "").strip().upper() for r in rows)
print("Butterflies 2022 -- prepare extracted CSVs")
print("=" * 64)
print(f"  rows {len(rows)}   statuses {dict(got)}")
bad = [f"{k}: {got.get(k, 0)} (paper {v})" for k, v in EXPECT.items() if got.get(k, 0) != v]
extra = [k for k in got if k not in EXPECT]
if len(rows) != 62 or bad or extra:
    print(f"  x does not match the paper: rows {len(rows)} (62); {bad} unexpected {extra}")
    sys.exit("ABORTED -- nothing written. Check the March CSV against Table S1 of the paper.")

with open(os.path.join(D, "review.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["review_name", "author", "date_published", "citation", "licence", "source_file",
                "species_count", "taxon_group", "tracks_assessed"])
    w.writerow(["A revised Red List of British butterflies", "Fox, R., Dennis, E.B., Brown, A.F. & Curson, J.",
                "2022-05", "Fox et al. 2022. Insect Conservation and Diversity 15: 485-495. doi:10.1111/icad.12582",
                "Journal article - statuses only; no accounts held", "butterfly_red_list_2022.csv",
                len(rows), "Lepidoptera: butterflies", "threat"])
with open(os.path.join(D, "statuses.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["species_name", "tvk", "iucn_status", "qualifying_criteria", "rarity"])
    w.writeheader()
    for r in rows:
        w.writerow({"species_name": r["species_name"].strip(), "tvk": "",
                    "iucn_status": r["status_value"].strip().upper(),
                    "qualifying_criteria": (r.get("notes") or "").strip(), "rarity": ""})
with open(os.path.join(D, "accounts.csv"), "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerow(["species_name", "tvk", "account_text", "source_columns", "sheet_row"])
print("  ok -- review.csv, statuses.csv, accounts.csv (empty) written")
print("\nNext:  python scripts\\load_review.py data\\reviews\\lepidoptera_butterflies_fox_2022")

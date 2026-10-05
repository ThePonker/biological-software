"""Correct misspelled species names in a review's extracted accounts.csv.

The source spreadsheets misspell a few names, so their accounts were not loaded
(no UKSI match). Each correction is applied to extracted\\accounts.csv and
logged in extracted\\name_corrections.csv (wrong, right, date) -- the published
source file is never edited.

Run:  python scripts\\fix_account_names.py
Then: python scripts\\load_review.py data\\reviews\\<folder> --add-accounts   (dry run, then --apply)
"""
import csv, os, sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXES = {
    "coleoptera_staphylinidae_necr390_2022": {"Dropephylla heerii": "Dropephylla heeri"},
    "coleoptera_cerambycidae_necr272_2019": {"Hylotrupes bajalus": "Hylotrupes bajulus",
                                             "Pachytodes cerambycifornmis": "Pachytodes cerambyciformis",
                                             "Saperda carcharius": "Saperda carcharias"},
}
for folder, fixes in FIXES.items():
    p = os.path.join(ROOT, "data", "reviews", folder, "extracted", "accounts.csv")
    rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
    done = []
    for r in rows:
        if r["species_name"] in fixes:
            done.append((r["species_name"], fixes[r["species_name"]]))
            r["species_name"] = fixes[r["species_name"]]
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    log = os.path.join(os.path.dirname(p), "name_corrections.csv")
    new = not os.path.exists(log)
    with open(log, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["wrong", "right", "date", "note"])
        for a, b in done:
            w.writerow([a, b, date.today().isoformat(), "misspelling in the review's data table"])
    print(f"{folder}: corrected {len(done)} of {len(fixes)}: {done}")

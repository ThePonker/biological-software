"""Why were six citations missed, and where are the stonefly/mayfly names?  READ ONLY.

  1. For NECR134/148/174/188/193/224: the text around "cite"/"citation" on the
     first 8 pages, and the page each appears on.
  2. For the NECR174 and NECR193 tables: the first 4 rows, every column.
"""
import os, re

DL = os.path.join(os.path.expanduser("~"), "Downloads")
from pypdf import PdfReader

print("1. Citation wording in the older reports")
print("=" * 80)
for necr, pat in (("134", r"^NECR134 _edition_2\.pdf$"), ("148", r"^NECR148_edition_2\.pdf$"),
                  ("174", r"^NECR174_edition_1\.pdf$"), ("188", r"^NECR188_edition_1\.pdf$"),
                  ("193", r"^NECR193_edition_1\.pdf$"), ("224", r"^NECR224 .*\.pdf$")):
    f = next((os.path.join(DL, x) for x in os.listdir(DL) if re.search(pat, x)), None)
    if not f:
        print(f"\nNECR{necr}: file not found");  continue
    pages = PdfReader(f).pages
    hit = False
    for i in range(min(8, len(pages))):
        t = re.sub(r"\s+", " ", pages[i].extract_text() or "")
        for m in re.finditer(r"cite|citation", t, re.I):
            print(f"\nNECR{necr} page {i + 1}: ...{t[max(0, m.start() - 60):m.start() + 260]}...")
            hit = True
            break
        if hit:
            break
    if not hit:
        t = re.sub(r"\s+", " ", pages[1].extract_text() or "")
        print(f"\nNECR{necr}: no 'cite' on pages 1-8; page 2 starts: {t[:300]}")

print("\n\n2. Stonefly and mayfly table layout (first 4 rows)")
print("=" * 80)
import xlrd
for necr in ("174", "193"):
    f = next((os.path.join(DL, x) for x in os.listdir(DL) if x.startswith(f"NECR{necr} data table")), None)
    if not f:
        print(f"NECR{necr}: table not found");  continue
    s = xlrd.open_workbook(f).sheets()[0]
    print(f"\nNECR{necr}: {s.nrows} rows x {s.ncols} cols")
    for r in range(min(4, s.nrows)):
        print(f"  row {r + 1}: {[str(v)[:22] for v in s.row_values(r)]}")
print("\nREAD ONLY")

"""Does the UKSI Simplified Copy cover the TVKs our Dec-2023 UKSI.mdb lacks?  READ ONLY.

  1. sheets, header rows and row counts (to plan an extractor)
  2. of the TVKs in JNCC 2026 designations and in your records that are in
     NEITHER uksi.db NOR UKSI.mdb's NAMESERVER: how many this copy contains

Run:  python scripts\\check_uksi_simplified.py "<path to UKSI ... Simplified Copy.xlsx>"
"""
import os, re, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths, openpyxl

if len(sys.argv) < 2 or not os.path.isfile(sys.argv[1]):
    sys.exit("  usage: python scripts\\check_uksi_simplified.py \"<path to the .xlsx>\"")
X = sys.argv[1]
TVK = re.compile(r"^[A-Z]{6}\d{10}$")

# the TVKs that need a newer UKSI: unknown to uksi.db and absent from the mdb nameserver
u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
known = {t for (t,) in u.execute("SELECT tvk FROM taxa")}
c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
o = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
jncc = {t for (t,) in c.execute("SELECT DISTINCT tvk FROM designations")} - known
recs = {t for (t,) in o.execute("SELECT DISTINCT species_tvk FROM assessment_records WHERE species_tvk IS NOT NULL")} - known
try:
    import pyodbc
    drv = [d for d in pyodbc.drivers() if "Access" in d][0]
    m = pyodbc.connect(f"DRIVER={{{drv}}};DBQ={r'C:\BiologicalSoftware_Backups\reference\UKSI.mdb'};").cursor()
    in_mdb = lambda t: m.execute("SELECT 1 FROM NAMESERVER WHERE INPUT_TAXON_VERSION_KEY=?", t).fetchone() is not None
    jncc = {t for t in jncc if not in_mdb(t)}
    recs = {t for t in recs if not in_mdb(t)}
except Exception as e:
    print(f"  (mdb not checked: {e})")
print(f"UKSI simplified copy check   READ ONLY\n{'=' * 80}\n  {os.path.basename(X)}")
print(f"  TVKs newer than our UKSI.mdb: JNCC {len(jncc)}, your records {len(recs)}")

wb = openpyxl.load_workbook(X, read_only=True, data_only=True)
seen, newest = set(), {}
try:
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        hdr = next(rows, None)
        n = 0
        for r in rows:
            n += 1
            for v in r:
                if isinstance(v, str) and TVK.match(v):
                    seen.add(v)
        print(f"\n  sheet '{ws.title}': {n} rows")
        print(f"    columns: {[h for h in (hdr or []) if h][:20]}")
finally:
    wb.close()
print(f"\n  distinct TVKs in this copy: {len(seen)}")
print(f"  JNCC TVKs newer than our mdb found here: {len(jncc & seen)} of {len(jncc)}")
print(f"  your records' TVKs newer than our mdb found here: {len(recs & seen)} of {len(recs)}")
left = sorted(jncc - seen)
if left:
    print(f"  still missing (newer than this copy too), e.g.: {left[:8]}")
print("\nREAD ONLY -- nothing has been changed.")

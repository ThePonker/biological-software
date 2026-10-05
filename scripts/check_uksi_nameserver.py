"""Are the TVKs our uksi.db 'does not know' simply non-recommended name TVKs that
UKSI.mdb's NAMESERVER maps to a recommended TVK?  And how current is UKSI.mdb?  READ ONLY.

  1. the newest entry/changed dates in UKSI.mdb (how recent the copy really is)
  2. for every TVK in codex.db designations and your records that is not in
     uksi.db taxa: found in NAMESERVER? -> its recommended TVK, and is THAT in uksi.db?

Needs the Microsoft Access ODBC driver (as the UKSI extractor uses).

Run:  python scripts\\check_uksi_nameserver.py
"""
import os, sqlite3, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths
try:
    import pyodbc
except ImportError:
    sys.exit("  x pyodbc not installed: pip install pyodbc --break-system-packages")

MDB = getattr(paths, "UKSI_MDB", None) or r"C:\BiologicalSoftware_Backups\reference\UKSI.mdb"
drivers = [d for d in pyodbc.drivers() if "Access" in d]
if not drivers:
    sys.exit(f"  x no Access ODBC driver found; available: {pyodbc.drivers()}")
m = pyodbc.connect(f"DRIVER={{{drivers[0]}}};DBQ={MDB};").cursor()
tables = {t.table_name.upper() for t in m.tables(tableType="TABLE")}
print(f"UKSI.mdb nameserver check   READ ONLY\n{'=' * 80}\n  {MDB}\n  tables: {len(tables)}; NAMESERVER present: {'NAMESERVER' in tables}")

print("\n1. How current is UKSI.mdb?")
for tbl in ("TAXON_VERSION", "TAXON", "NAMESERVER", "TAXON_LIST_ITEM"):
    if tbl not in tables:
        continue
    cols = {c.column_name.upper() for c in m.columns(table=tbl)}
    for col in ("ENTRY_DATE", "CHANGED_DATE"):
        if col in cols:
            r = m.execute(f"SELECT MAX({col}) FROM {tbl}").fetchone()[0]
            print(f"   {tbl}.{col}: newest {r}")

u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
known = {t for (t,) in u.execute("SELECT tvk FROM taxa")}
c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
o = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
jncc = {t for (t,) in c.execute("SELECT DISTINCT tvk FROM designations")} - known
mine = Counter(t for (t,) in o.execute("SELECT species_tvk FROM assessment_records WHERE species_tvk IS NOT NULL"))
recs = {t for t in mine if t not in known}
print(f"\n2. TVKs not in uksi.db taxa: JNCC {len(jncc)}, your records {len(recs)} ({sum(mine[t] for t in recs)} records)")

ns_cols = {c.column_name.upper() for c in m.columns(table="NAMESERVER")}
inp = "INPUT_TAXON_VERSION_KEY" if "INPUT_TAXON_VERSION_KEY" in ns_cols else None
rec = "RECOMMENDED_TAXON_VERSION_KEY" if "RECOMMENDED_TAXON_VERSION_KEY" in ns_cols else None
if not (inp and rec):
    sys.exit(f"  x NAMESERVER columns not as expected: {sorted(ns_cols)}")


def lookup(tvks):
    found, rec_known, missing = {}, 0, []
    for t in tvks:
        r = m.execute(f"SELECT {rec} FROM NAMESERVER WHERE {inp}=?", t).fetchone()
        if r:
            found[t] = r[0]
            rec_known += r[0] in known
        else:
            missing.append(t)
    return found, rec_known, missing


for label, tvks in (("JNCC 2026", jncc), ("your records", recs)):
    found, rk, miss = lookup(sorted(tvks))
    print(f"\n   {label}: {len(tvks)} unknown -> in NAMESERVER {len(found)} "
          f"(recommended TVK known to uksi.db: {rk}); not in mdb at all: {len(miss)}")
    for t, r in list(found.items())[:5]:
        print(f"      {t} -> {r}  {'(known)' if r in known else '(NOT in uksi.db)'}")
    if miss:
        print(f"      e.g. not in mdb: {miss[:6]}")
print("\n  'in NAMESERVER, recommended known' = an extraction gap (fixable from this mdb);")
print("  'not in mdb at all' = TVKs newer than this mdb (needs a newer UKSI).")
print("\nREAD ONLY -- nothing has been changed.")

"""Grid-reference / date corrections  --  agreed 26 September 2026.

DRY RUN by default. Re-run with --apply to write.

Safety:
  - backup of observatum.db (SQLite online backup) before any write; aborts if it fails
  - every update is guarded: the record's CURRENT value must match what was
    diagnosed, otherwise nothing at all is written
  - one transaction; all or nothing
  - every changed row is read back from a fresh connection afterwards
  - specimens get a provenance note appended to import_notes

Run:
  python scripts\\fix_gridrefs_20260926.py 2>&1 | Out-File -FilePath gridref_fix_dryrun.txt -Encoding utf8
  python scripts\\fix_gridrefs_20260926.py --apply 2>&1 | Out-File -FilePath gridref_fix_apply.txt -Encoding utf8
"""
import os, sys, re, sqlite3, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

APPLY = "--apply" in sys.argv
TODAY = datetime.date.today().isoformat()
BACKUP_DIR = r"C:\BiologicalSoftware_Backups\reference"

# (table, id, column, expected current value, new value, note or None)
FIXES = [
    ("specimens", 1049, "grid_ref", "SV111428", "SU111428",
     "Grid ref corrected {d}: was 'SV111428' (wrong 100km square letter)"),
    ("specimens", 1050, "grid_ref", "SV111428", "SU111428",
     "Grid ref corrected {d}: was 'SV111428' (wrong 100km square letter)"),
    ("specimens", 841, "grid_ref", "SP55906", "SP559096",
     "Grid ref corrected {d}: was 'SP55906' (digit dropped; matches site refs)"),
    ("specimens", 1222, "grid_ref", "TQ688684`", "TQ688684",
     "Grid ref corrected {d}: was 'TQ688684`' (stray backtick)"),
    ("specimens", 1601, "grid_ref", "SK55955639687", "SK5955639687",
     "Grid ref corrected {d}: was 'SK55955639687' (doubled leading digit)"),
    ("specimens", 1930, "grid_ref", "SP16623", "SP5920",
     "Grid ref set {d} to 1km site-level fallback SP5920; original 'SP16623' unrecoverable"),
    ("specimens", 2261, "grid_ref", "18/05/2024", "SO8074",
     "Grid ref set {d} to 1km site-level fallback SO8074; field held the date '18/05/2024'"),
    ("observations", 23187, "date", "2026-07-10", "2024-07-10",
     "Date corrected {d}: was '2026-07-10' (year typo; matches 10 Jul 2024 Ashenbank visit)"),
]

# Left alone on purpose -- flagged only
FLAGGED = [
    ("observations", 23009, "TQ678990 -- unrecoverable; check source Kent Deadwood workbook"),
    ("observations", 23049, "TQ678990 -- unrecoverable; check source Kent Deadwood workbook"),
]


def precision_of(gr):
    m = re.match(r"^[A-Z]{2}(\d+)$", gr)
    if not m or len(m.group(1)) % 2:
        return None
    return {2: 10000, 4: 1000, 6: 100, 8: 10, 10: 1}.get(len(m.group(1)))


def columns(con, table):
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}


print("Grid-ref / date corrections  --  " + ("APPLY" if APPLY else "DRY RUN"))
print("=" * 76)

con = sqlite3.connect(str(paths.OBSERVATUM_DB))
con.row_factory = sqlite3.Row
cols = {t: columns(con, t) for t in ("specimens", "observations")}

# ---------------------------------------------------------------- guard
problems = []
for table, rid, col, expected, new, note in FIXES:
    row = con.execute(f"SELECT {col} v FROM {table} WHERE id=?", (rid,)).fetchone()
    cur = None if row is None else row["v"]
    ok = cur == expected
    print(f"  {'ok ' if ok else 'XX '} {table:<12} id={rid:<6} {col:<9} "
          f"{cur!r:<18} -> {new!r}")
    if not ok:
        problems.append(f"{table} id={rid}: expected {expected!r}, found {cur!r}")

print()
for table, rid, why in FLAGGED:
    print(f"  --  {table:<12} id={rid:<6} left unchanged: {why}")

if problems:
    print("\nABORTED -- current values differ from the diagnosis:")
    for p in problems:
        print("   ", p)
    print("Nothing has been changed.")
    sys.exit(1)

if not APPLY:
    print("\nAll 8 guards pass.")
    print("DRY RUN -- nothing has been changed. Re-run with --apply to write.")
    sys.exit(0)

# ---------------------------------------------------------------- backup
os.makedirs(BACKUP_DIR, exist_ok=True)
bp = os.path.join(BACKUP_DIR, "observatum_pre_gridref_fix_" +
                  datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".db")
try:
    dst = sqlite3.connect(bp)
    con.backup(dst)
    dst.close()
    size = os.path.getsize(bp)
    chk = sqlite3.connect(bp).execute("PRAGMA integrity_check").fetchone()[0]
    if size == 0 or chk != "ok":
        raise RuntimeError(f"backup check failed (size={size}, integrity={chk})")
except Exception as e:
    print(f"\nABORTED -- backup failed: {e}\nNothing has been changed.")
    sys.exit(1)
print(f"\n  backup: {bp}  ({size:,} bytes, integrity ok)")

# ---------------------------------------------------------------- write
now = datetime.datetime.now().isoformat()
try:
    with con:
        for table, rid, col, expected, new, note in FIXES:
            sets, args = [f"{col}=?"], [new]
            if table == "specimens" and col == "grid_ref" and "grid_precision" in cols[table]:
                sets.append("grid_precision=?")
                args.append(precision_of(new))
            if note and "import_notes" in cols[table]:
                sets.append("import_notes = CASE WHEN import_notes IS NULL OR import_notes='' "
                            "THEN ? ELSE import_notes || ' | ' || ? END")
                n = "[" + note.format(d=TODAY) + "]"
                args += [n, n]
            if "updated_at" in cols[table]:
                sets.append("updated_at=?")
                args.append(now)
            args += [rid, expected]
            cur = con.execute(f"UPDATE {table} SET {', '.join(sets)} "
                              f"WHERE id=? AND {col}=?", args)
            if cur.rowcount != 1:
                raise RuntimeError(f"{table} id={rid}: updated {cur.rowcount} rows, expected 1")
except Exception as e:
    print(f"\nABORTED -- write failed, transaction rolled back: {e}")
    sys.exit(1)
con.close()
print("  written: 8 records, one transaction")

# ---------------------------------------------------------------- read back
print("\n  Read-back (fresh connection):")
rb = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
bad = 0
for table, rid, col, expected, new, note in FIXES:
    v = rb.execute(f"SELECT {col} FROM {table} WHERE id=?", (rid,)).fetchone()[0]
    ok = v == new
    bad += not ok
    print(f"    {'ok ' if ok else 'XX '} {table:<12} id={rid:<6} {col} = {v!r}")
print("\n" + ("All 8 verified." if not bad else f"{bad} FAILED read-back -- restore from {bp}"))

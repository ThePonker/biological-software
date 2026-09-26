"""Move review accounts to Codex; make observatum.db.species_profiles yours alone.

  1. Copy every origin='review' account from observatum.db into
     codex.db.species_profiles under its review (NECR702 = review 1).
  2. Read every copy back and compare it, text and TVK, with the original.
     Any mismatch: the copies are removed again and nothing else happens.
  3. Recreate observatum.db.species_profiles keyed on species_tvk (UNIQUE,
     NOT NULL) -- your own accounts only. The provenance columns (origin,
     source_review, source_year) are dropped: provenance now lives in Codex.
     Any non-review rows are carried across.
  4. Patch scripts/reset_database.py to create the same table.

DRY RUN by default. --apply to write. Close Observatum and Examen first.
Optional: --licence "Open Government Licence v3.0" sets the review's licence.

Run:
  python scripts\\move_review_profiles_to_codex.py
  python scripts\\move_review_profiles_to_codex.py --apply
"""
import datetime, io, os, py_compile, shutil, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

APPLY = "--apply" in sys.argv
LICENCE = None
if "--licence" in sys.argv:
    i = sys.argv.index("--licence")
    LICENCE = sys.argv[i + 1] if i + 1 < len(sys.argv) else None

BACKUP_DIR = r"C:\BiologicalSoftware_Backups\reference"
RESET = os.path.join(ROOT, "scripts", "reset_database.py")

NEW_TABLE_BODY = """    id INTEGER PRIMARY KEY AUTOINCREMENT,
    species_name TEXT NOT NULL,
    species_tvk TEXT UNIQUE NOT NULL,
    common_name TEXT,
    order_name TEXT,
    family TEXT,
    conservation_status TEXT,
    uk_status TEXT,
    flight_period TEXT,
    habitat TEXT,
    notes TEXT,
    profile_text TEXT,
    image_path TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP"""
KEEP_COLS = ["species_name", "species_tvk", "common_name", "order_name", "family",
             "conservation_status", "uk_status", "flight_period", "habitat", "notes",
             "profile_text", "image_path", "created_at", "updated_at"]


def stop(msg):
    print(f"\nABORTED -- {msg}\nNothing has been changed.")
    sys.exit(1)


print("Move review accounts to Codex  --  " + ("APPLY" if APPLY else "DRY RUN"))
print("=" * 72)

cx = sqlite3.connect(str(paths.CODEX_DB))
ob = sqlite3.connect(str(paths.OBSERVATUM_DB))

# ---------------------------------------------------------------- guards
cx_cols = [r[1] for r in cx.execute("PRAGMA table_info(species_profiles)")]
if "review_id" not in cx_cols:
    stop("codex.db has the old species_profiles schema -- run the schema patch and rebuild first")

rev = cx.execute("SELECT id, review_name, licence FROM reviews "
                 "WHERE review_name LIKE '%NECR702%'").fetchall()
if len(rev) != 1:
    stop(f"expected exactly one NECR702 review in codex.db, found {len(rev)}")
rid, rname, rlic = rev[0]
print(f"  review {rid}: {rname[:60]}")
print(f"  licence now: {rlic!r}" + (f"  ->  {LICENCE!r}" if LICENCE else ""))

already = cx.execute("SELECT COUNT(1) FROM species_profiles WHERE review_id=?", (rid,)).fetchone()[0]
if already:
    stop(f"codex.db already holds {already} accounts for review {rid} -- already moved?")

ob_cols = [r[1] for r in ob.execute("PRAGMA table_info(species_profiles)")]
if "origin" not in ob_cols:
    stop("observatum.db.species_profiles has no origin column -- already migrated?")

rows = ob.execute("""SELECT species_tvk, species_name, profile_text, source_review, created_at
                     FROM species_profiles WHERE origin='review'""").fetchall()
others = ob.execute(f"""SELECT {', '.join(c for c in KEEP_COLS if c in ob_cols)}
                        FROM species_profiles
                        WHERE origin IS NULL OR origin != 'review'""").fetchall()
print(f"  observatum.db: {len(rows)} review accounts, {len(others)} other accounts")

bad = [r for r in rows if "NECR702" not in (r[3] or "")]
if bad:
    stop(f"{len(bad)} review accounts cite something other than NECR702, e.g. {bad[0][1]}")
if any(not r[0] for r in rows):
    stop("a review account has no TVK")
if len({r[0] for r in rows}) != len(rows):
    stop("a TVK appears twice among the review accounts")
o_tvk_i = [c for c in KEEP_COLS if c in ob_cols].index("species_tvk")
o_tvks = [o[o_tvk_i] for o in others]
if any(not t for t in o_tvks):
    stop("one of your own accounts has no TVK -- it cannot go into a TVK-keyed table")
if len(set(o_tvks)) != len(o_tvks):
    stop("two of your own accounts share a TVK")

# reset_database.py markers
rtext_raw = io.open(RESET, "rb").read()
rbom = rtext_raw.startswith(b"\xef\xbb\xbf")
rlines = rtext_raw.decode("utf-8-sig").split("\n")
starts = [i for i, l in enumerate(rlines) if "CREATE TABLE IF NOT EXISTS species_profiles (" in l]
if len(starts) != 1:
    stop(f"reset_database.py: species_profiles CREATE found {len(starts)} times")
rs = starts[0]
re_ = next((i for i in range(rs, min(len(rlines), rs + 30))
            if rlines[i].strip().rstrip("\r").startswith(");")), None)
if re_ is None:
    stop("reset_database.py: end of the species_profiles CREATE not found")
block = "\n".join(rlines[rs:re_ + 1])
if "species_name TEXT UNIQUE NOT NULL" not in block:
    stop("reset_database.py: species_profiles block is not the version reviewed")
print(f"  reset_database.py: species_profiles block at lines {rs + 1}-{re_ + 1}")

if not APPLY:
    print("\nAll guards pass.")
    print("DRY RUN -- nothing has been changed. Close Observatum and Examen, then --apply.")
    sys.exit(0)

# ---------------------------------------------------------------- backups
os.makedirs(BACKUP_DIR, exist_ok=True)
stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
for con, name in ((cx, "codex"), (ob, "observatum")):
    p = os.path.join(BACKUP_DIR, f"{name}_pre_profile_move_{stamp}.db")
    try:
        t = sqlite3.connect(p); con.backup(t); t.close()
        if sqlite3.connect(p).execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("integrity check failed")
    except Exception as e:
        stop(f"backup of {name} failed: {e}")
    print(f"  backup: {p}")

# ---------------------------------------------------------------- 1. copy to Codex
now = datetime.datetime.now().isoformat()
with cx:
    cx.executemany("""INSERT INTO species_profiles
        (tvk, review_id, species_name, profile_text, source,
         date_added, date_updated, added_by)
        VALUES (?,?,?,?,?,?,NULL,'review-import')""",
        [(t, rid, n, txt, src, created or now) for t, n, txt, src, created in rows])
    if LICENCE:
        cx.execute("UPDATE reviews SET licence=? WHERE id=?", (LICENCE, rid))
print(f"  copied {len(rows)} accounts to codex.db (review {rid})")

# ---------------------------------------------------------------- 2. verify copies
chk = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
got = dict(chk.execute("SELECT tvk, profile_text FROM species_profiles WHERE review_id=?", (rid,)))
chk.close()
mismatch = [t for t, n, txt, s, c in rows if got.get(t) != txt]
if len(got) != len(rows) or mismatch:
    with cx:
        cx.execute("DELETE FROM species_profiles WHERE review_id=?", (rid,))
    stop(f"read-back failed ({len(got)} found, {len(mismatch)} differ) -- copies removed")
print(f"  verified: all {len(rows)} copies match text and TVK")

# ---------------------------------------------------------------- 3. observatum table
cols_present = [c for c in KEEP_COLS if c in ob_cols]
ob.isolation_level = None
try:
    ob.execute("BEGIN")
    ob.execute(f"CREATE TABLE species_profiles_new (\n{NEW_TABLE_BODY}\n)")
    if others:
        ph = ",".join("?" * len(cols_present))
        ob.executemany(f"INSERT INTO species_profiles_new ({', '.join(cols_present)}) "
                       f"VALUES ({ph})", others)
    ob.execute("DROP TABLE species_profiles")
    ob.execute("ALTER TABLE species_profiles_new RENAME TO species_profiles")
    ob.execute("CREATE INDEX IF NOT EXISTS idx_profile_species ON species_profiles(species_name)")
    ob.execute("CREATE INDEX IF NOT EXISTS idx_profile_tvk ON species_profiles(species_tvk)")
    ob.execute("COMMIT")
except Exception as e:
    ob.execute("ROLLBACK")
    print(f"\n  x observatum.db table rebuild failed and was rolled back: {e}")
    print("    The Codex copies are in place and verified; observatum.db is unchanged.")
    sys.exit(1)

n_after = ob.execute("SELECT COUNT(1) FROM species_profiles").fetchone()[0]
uniq = [r for r in ob.execute("PRAGMA index_list(species_profiles)") if r[2]]
ucols = [[x[2] for x in ob.execute(f"PRAGMA index_info('{r[1]}')")] for r in uniq]
print(f"  observatum.db.species_profiles rebuilt: {n_after} rows (your own), unique on {ucols}")
if n_after != len(others) or ["species_tvk"] not in ucols:
    print("  x UNEXPECTED -- check before continuing")

# ---------------------------------------------------------------- 4. reset_database.py
eol = "\r" if rlines[rs].endswith("\r") else ""
ind = rlines[rs][:len(rlines[rs]) - len(rlines[rs].lstrip())]
new_block = ([f"{ind}CREATE TABLE IF NOT EXISTS species_profiles ({eol}",
              f"{ind}    -- Wil's own species accounts. Review accounts live in{eol}",
              f"{ind}    -- codex.db.species_profiles, one per species per review.{eol}"]
             + [ind + l + eol for l in NEW_TABLE_BODY.split("\n")]
             + [rlines[re_]])
shutil.copy2(RESET, RESET + ".bak_profiles")
rlines[rs:re_ + 1] = new_block
io.open(RESET, "w", encoding="utf-8-sig" if rbom else "utf-8", newline="").write("\n".join(rlines))
try:
    py_compile.compile(RESET, doraise=True)
    print("  reset_database.py patched and compiles (backup: .bak_profiles)")
except py_compile.PyCompileError as e:
    shutil.copy2(RESET + ".bak_profiles", RESET)
    print(f"  x reset_database.py failed to compile -- restored from backup\n{e}")

print("\nDone. Observatum's profile displays will be empty for these species until")
print("step 4 points them at Codex.")

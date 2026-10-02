"""Contributed records -- the table and the view.

  contributed_observations   Records other people collected, kept apart from
                             yours. Stats, dashboards, mapping and the iRecord
                             export never read it, because they read
                             `observations`. Nothing to remember, nothing to
                             filter: safe by default.

  assessment_records         A VIEW: your observations UNION ALL contributed
                             records, with an `origin` column ('own' /
                             'contributed'). Examen reads this. The rule "what
                             counts in an assessment" lives here, once.

Applies to the live observatum.db (backup first) and adds the same definitions
to scripts/reset_database.py. Writes NOTHING unless every guard passes.

DRY RUN by default; --apply to write. Close Observatum and Examen first.

Run:  python scripts\\patch_contributed_schema.py
      python scripts\\patch_contributed_schema.py --apply
"""
import ast, datetime, io, os, py_compile, shutil, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

APPLY = "--apply" in sys.argv
BACKUP_DIR = r"C:\BiologicalSoftware_Backups\reference"
RESET = os.path.join(ROOT, "scripts", "reset_database.py")

TABLE_SQL = """CREATE TABLE IF NOT EXISTS contributed_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- the record
    species_name TEXT NOT NULL,
    species_tvk TEXT,
    common_name TEXT,
    order_name TEXT,
    family TEXT,
    taxon_rank TEXT,
    date TEXT NOT NULL,
    date_type TEXT DEFAULT 'D',
    grid_ref TEXT,
    grid_precision INTEGER,
    vice_county TEXT,
    vc_number INTEGER,
    site_name TEXT,
    sub_location TEXT,
    trap_number TEXT,
    visit_number TEXT,
    recorder TEXT,
    determiner TEXT,
    sex TEXT,
    stage TEXT,
    quantity INTEGER DEFAULT 1,
    method TEXT,
    comment TEXT,
    record_type TEXT DEFAULT 'Commercial',
    project_name TEXT,
    client TEXT,
    -- whose it is and on what terms
    contributor TEXT NOT NULL,
    source_file TEXT,
    received_date TEXT,
    permission TEXT,
    import_batch TEXT,
    import_notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)"""

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_contrib_project ON contributed_observations(project_name)",
    "CREATE INDEX IF NOT EXISTS idx_contrib_tvk ON contributed_observations(species_tvk)",
    "CREATE INDEX IF NOT EXISTS idx_contrib_contributor ON contributed_observations(contributor)",
    "CREATE INDEX IF NOT EXISTS idx_contrib_batch ON contributed_observations(import_batch)",
]

VIEW_COLS = ("id, record_type, project_name, client, site_name, sub_location, "
             "trap_number, visit_number, date, species_name, species_tvk, common_name, "
             "order_name, family, quantity, sex, stage, method, recorder, determiner, "
             "grid_ref, vice_county, vc_number")
VIEW_SQL = (
    "CREATE VIEW IF NOT EXISTS assessment_records AS\n"
    f"    SELECT 'own' AS origin, NULL AS contributor, {VIEW_COLS}\n"
    "    FROM observations\n"
    "    UNION ALL\n"
    f"    SELECT 'contributed' AS origin, contributor, {VIEW_COLS}\n"
    "    FROM contributed_observations")


def stop(msg):
    print(f"\nABORTED -- {msg}\nNothing has been changed.")
    sys.exit(1)


print("Contributed records -- table and view  --  " + ("APPLY" if APPLY else "DRY RUN"))
print("=" * 72)

# ---------------------------------------------------------------- live db guards
o = sqlite3.connect(str(paths.OBSERVATUM_DB))
existing = {r[0] for r in o.execute(
    "SELECT name FROM sqlite_master WHERE name IN ('contributed_observations','assessment_records')")}
if existing:
    stop(f"already present in observatum.db: {sorted(existing)}")
obs_cols = {r[1] for r in o.execute("PRAGMA table_info(observations)")}
missing = [c.strip() for c in VIEW_COLS.split(",") if c.strip() not in obs_cols]
if missing:
    stop(f"observations lacks columns the view needs: {missing}")
print("  observatum.db: neither object exists yet; observations has every column the view needs")

# ---------------------------------------------------------------- reset_database.py guards
raw = io.open(RESET, "rb").read()
bom = raw.startswith(b"\xef\xbb\xbf")
lines = raw.decode("utf-8-sig").split("\n")
if any("contributed_observations" in l for l in lines):
    stop("reset_database.py already mentions contributed_observations")


def one(pred, name):
    hits = [i for i, l in enumerate(lines) if pred(l.rstrip("\r"))]
    if len(hits) != 1:
        stop(f"reset_database.py: {name} found {len(hits)} times")
    return hits[0]


i_idx = one(lambda l: l.strip() == 'CREATE_INDEXES = """', "CREATE_INDEXES = \"\"\"")
i_reg = one(lambda l: l.strip() == "('entry_staging', CREATE_ENTRY_STAGING),",
            "('entry_staging', CREATE_ENTRY_STAGING),")
print(f"  reset_database.py: CREATE_INDEXES at line {i_idx + 1}, table list entry at line {i_reg + 1}")

if not APPLY:
    print("\nAll guards pass.")
    print("DRY RUN -- nothing has been changed. Close Observatum and Examen, then --apply.")
    sys.exit(0)

# ---------------------------------------------------------------- live db
os.makedirs(BACKUP_DIR, exist_ok=True)
bp = os.path.join(BACKUP_DIR, "observatum_pre_contributed_" +
                  datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".db")
t = sqlite3.connect(bp); o.backup(t); t.close()
print(f"\n  backup: {bp}")

o.isolation_level = None
try:
    o.execute("BEGIN")
    o.execute(TABLE_SQL)
    for s in INDEX_SQL:
        o.execute(s)
    o.execute(VIEW_SQL)
    o.execute("COMMIT")
except Exception as e:
    o.execute("ROLLBACK")
    stop(f"live database change failed and was rolled back: {e}")
print("  observatum.db: table, 4 indexes and view created")

# Two numbers side by side: the view must reproduce Examen's project list exactly.
q = """SELECT project_name, substr(date,1,4), COUNT(*), COUNT(DISTINCT species_name)
       FROM {src} WHERE record_type='Commercial' AND project_name IS NOT NULL
       AND project_name != '' GROUP BY 1, 2 ORDER BY 1, 2"""
a = o.execute(q.format(src="observations")).fetchall()
b = o.execute(q.format(src="assessment_records")).fetchall()
n_obs = o.execute("SELECT COUNT(1) FROM observations").fetchone()[0]
n_view = o.execute("SELECT COUNT(1) FROM assessment_records").fetchone()[0]
print(f"  observations {n_obs:,} rows   assessment_records {n_view:,} rows   "
      f"({'equal' if n_obs == n_view else 'DIFFERENT'})")
print(f"  Examen's project list from each: {len(a)} vs {len(b)} survey rows -- "
      f"{'identical' if a == b else 'DIFFERENT'}")
if a != b or n_obs != n_view:
    print("  x the view does not reproduce observations -- investigate before going on")

# ---------------------------------------------------------------- reset_database.py
eol = "\r" if lines[i_idx].endswith("\r") else ""


def L(text):
    return [x + eol for x in text.split("\n")]


const = L('CREATE_CONTRIBUTED_OBSERVATIONS = """\n'
          "-- Records other people collected. Never read by stats, mapping or the\n"
          "-- iRecord export, which all read `observations`. Examen reads the\n"
          "-- assessment_records view, which combines the two.\n"
          + TABLE_SQL + ';\n"""\n')
idx_block = L("-- contributed records, and the view Examen reads (see CREATE_CONTRIBUTED_OBSERVATIONS)\n"
              + ";\n".join(INDEX_SQL) + ";\n" + VIEW_SQL + ";")
reg_line = lines[i_reg].replace("('entry_staging', CREATE_ENTRY_STAGING),",
                                "('contributed_observations', CREATE_CONTRIBUTED_OBSERVATIONS),")

# bottom-up so indices stay valid
edits = sorted([(i_reg, "after", [reg_line]),
                (i_idx, "after", idx_block),
                (i_idx, "before", const)], key=lambda t: (-t[0], t[1] == "before"))
for i, where, new in edits:
    if where == "after":
        lines[i + 1:i + 1] = new
    else:
        lines[i:i] = new

shutil.copy2(RESET, RESET + ".bak_contrib")
io.open(RESET, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write("\n".join(lines))
try:
    py_compile.compile(RESET, doraise=True)
except py_compile.PyCompileError as e:
    shutil.copy2(RESET + ".bak_contrib", RESET)
    print(f"  x reset_database.py failed to compile -- restored\n{e}")
    sys.exit(1)

# re-read; per-table audit: each definition exactly once
txt = io.open(RESET, encoding="utf-8-sig").read()
for marker in ("CREATE TABLE IF NOT EXISTS contributed_observations",
               "CREATE VIEW IF NOT EXISTS assessment_records",
               "('contributed_observations', CREATE_CONTRIBUTED_OBSERVATIONS)"):
    print(f"  {'ok' if txt.count(marker) == 1 else 'x '} reset_database.py: {marker!r} x{txt.count(marker)}")
print("  reset_database.py compiles (backup: .bak_contrib)")

print("\nDone. Nothing reads the new table yet; Examen is switched to the view in step 3.")

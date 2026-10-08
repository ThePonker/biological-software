"""Does the suite still reproduce its frozen reference figures?  READ ONLY.

Compares the live databases with scripts/reference_figures.json:
  1. Codex table counts -- move only with a rebuild or a review load
  2. Every survey: species, key species, SQI, SQI on Pantheon's scores alone.
     Computed by check_sqi_table.py, run as a child process, so the SQI
     arithmetic stays in one place.

A figure that moved on purpose (new review, JNCC or UKSI update): update the
JSON and docs/02_Current_State.md in the same commit, saying why.
A figure that moved and you did not mean it to: stop and find out why.

Run:  py -3.14 scripts\\check_reference_figures.py
Exit code 0 if every figure matches, 1 otherwise.
"""
import json, os, sqlite3, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

REF_FILE = os.path.join(ROOT, "scripts", "reference_figures.json")
SQI_SCRIPT = os.path.join(ROOT, "scripts", "check_sqi_table.py")

# check_sqi_table.py --save writes, per survey:
#   [species, scoring, sqi, scoring_pantheon_only, sqi_pantheon_only, key]
SQI_FIELDS = {"species": 0, "sqi": 2, "sqi_pantheon": 4, "key": 5}

with open(REF_FILE, encoding="utf-8") as f:
    ref = json.load(f)

failures = 0


def compare(label, want, got):
    global failures
    ok = want == got
    if not ok:
        failures += 1
    print(f"  {'✓' if ok else '✗'} {label:<46} {want!s:>7} {got!s:>7}"
          + ("" if ok else "   <- DIFFERS"))


print("Reference figures check   READ ONLY")
print("=" * 78)

# 1. Codex counts
print(f"\n1. codex.db table counts{'':>27}{'frozen':>7} {'now':>7}")
con = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
for table, want in ref["codex_counts"].items():
    got = con.execute(f"SELECT COUNT(1) FROM {table}").fetchone()[0]
    compare(table, want, got)
con.close()

# 2. Surveys
print(f"\n2. Surveys{'':>41}{'frozen':>7} {'now':>7}")
with tempfile.TemporaryDirectory() as tmp:
    out = os.path.join(tmp, "sqi_now.json")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    run = subprocess.run([sys.executable, SQI_SCRIPT, "--save", out], cwd=ROOT,
                         env=env, capture_output=True, text=True, encoding="utf-8")
    if run.returncode != 0 or not os.path.exists(out):
        failures += 1
        print("  ✗ check_sqi_table.py failed:")
        print("    " + "\n    ".join((run.stderr or run.stdout).strip().splitlines()[-15:]))
        now = {}
    else:
        with open(out, encoding="utf-8") as f:
            now = json.load(f)

if now:
    for survey, figures in ref["surveys"].items():
        if survey not in now:
            failures += 1
            print(f"  ✗ {survey}: not found in Examen's project list")
            continue
        for field, want in figures.items():
            compare(f"{survey[:30]} {field}", want, now[survey][SQI_FIELDS[field]])
    extra = sorted(set(now) - set(ref["surveys"]))
    if extra:
        print(f"\n  New since the reference was frozen (not checked): {', '.join(extra)}")

print("\n" + ("ALL MATCH" if failures == 0 else f"{failures} FIGURE(S) DIFFER"))
print("READ ONLY -- nothing has been changed.")
sys.exit(1 if failures else 0)

"""Does the suite still reproduce its frozen reference figures?  READ ONLY.

Compares the live databases with scripts/reference_figures.json:
  1. Codex table counts -- move only with a rebuild or a review load
  2. Every survey: species, key species, SQI, SQI on Pantheon's scores alone.
     Computed by check_sqi_table.py, run as a child process, so the SQI
     arithmetic stays in one place.
  3. Every survey in Pantheon Only (strict) mode: SQI and key species, from
     Examen's project table; and, in both modes, that the project table shows
     the detail's own SQI and key-species count (EXA1 / EXA16, 9 Oct 2026).
  4. The exports, both modes: the assessment workbook (which the PDF and Word
     reports are laid out from, via report_model.read_report) is written to a
     temporary folder and its Summary sheet -- species recorded, key species,
     SQI -- and the appendix footer SQI are checked against the frozen figures
     (EXA16, 10 Oct 2026). Nothing is written outside the temporary folder.

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
            if field in SQI_FIELDS:          # sqi_strict / key_strict: section 3
                compare(f"{survey[:30]} {field}", want, now[survey][SQI_FIELDS[field]])
    extra = sorted(set(now) - set(ref["surveys"]))
    if extra:
        print(f"\n  New since the reference was frozen (not checked): {', '.join(extra)}")

# 3. Strict mode, and the project table against the detail
print(f"\n3. Pantheon Only mode; project table = detail{'':>8}{'frozen':>7} {'now':>7}")
try:
    sys.path[:0] = [ROOT, os.path.join(ROOT, "Observatum")]
    from shared.repositories.codex_repository import AnalysisMode
    from Examen import examen_data as ed
    for mode in (AnalysisMode.CODEX_FULL, AnalysisMode.PANTHEON_ONLY):
        strict = mode == AnalysisMode.PANTHEON_ONLY
        for p in ed.load_all_projects(mode):
            survey = f"{p.project_name} {p.survey_year}"
            want = ref["surveys"].get(survey, {})
            if strict:
                for field, got in (("sqi_strict", p.sqi), ("key_strict", p.key_species_count)):
                    if field in want:
                        compare(f"{survey[:30]} {field}", want[field], got)
            d = ed.load_project_detail(p.project_name, p.client, mode,
                                       survey_year=p.survey_year or None,
                                       jurisdiction=getattr(p, "jurisdiction", None))
            a = getattr(d, "analysis", None)
            if a is None:
                continue
            tag = "strict" if strict else "full"
            if (p.sqi, p.key_species_count, p.species_count) != \
                    (a.overall_sqi.sqi, a.key_species_count, a.total_species):
                compare(f"{survey[:24]} table=detail ({tag})",
                        (a.overall_sqi.sqi, a.key_species_count, a.total_species),
                        (p.sqi, p.key_species_count, p.species_count))
    print("  (table = detail checked for every survey in both modes; only differences listed)")
except Exception as e:  # noqa: BLE001 -- a failed check is a failure, not a crash
    failures += 1
    print(f"  ✗ strict-mode / table check failed: {e}")

# 4. The exports: the workbook (the PDF and Word reports' source) in both modes
print(f"\n4. Exports (workbook = PDF / Word source){'':>12}{'frozen':>7} {'now':>7}")
try:
    from Examen.workbook_export import export_workbook
    from Examen.report_model import read_report
    checked = 0
    with tempfile.TemporaryDirectory() as tmp:
        for mode in (AnalysisMode.CODEX_FULL, AnalysisMode.PANTHEON_ONLY):
            strict = mode == AnalysisMode.PANTHEON_ONLY
            for p in ed.load_all_projects(mode):
                survey = f"{p.project_name} {p.survey_year}"
                want = ref["surveys"].get(survey)
                if not want:
                    continue
                d = ed.load_project_detail(p.project_name, p.client, mode,
                                           survey_year=p.survey_year or None,
                                           jurisdiction=getattr(p, "jurisdiction", None))
                if d is None or getattr(d, "analysis", None) is None:
                    failures += 1
                    print(f"  \u2717 {survey}: no analysis to export")
                    continue
                out = os.path.join(tmp, f"check_{checked}.xlsx")
                export_workbook(d.analysis, d, p, out,
                                jurisdiction=getattr(d, "jurisdiction", None) or "England")
                rep_ = read_report(out)
                fig = {str(r[0]): r[1] for r in rep_["figures"]}
                foot = dict(rep_["appendix"]["footer"]) if rep_.get("appendix") else {}
                tag = "strict" if strict else "full"
                pairs = ([("sqi_strict", "Species Quality Index (SQI)"),
                          ("key_strict", "Key Species")] if strict else
                         [("species", "Species recorded"), ("key", "Key Species"),
                          ("sqi", "Species Quality Index (SQI)")])
                for field, label in pairs:
                    if field in want and fig.get(label) != want[field]:
                        compare(f"{survey[:24]} workbook {label[:12]} ({tag})",
                                want[field], fig.get(label))
                if foot.get("Species Quality Index (SQI)") != fig.get("Species Quality Index (SQI)"):
                    compare(f"{survey[:24]} appendix footer SQI ({tag})",
                            fig.get("Species Quality Index (SQI)"),
                            foot.get("Species Quality Index (SQI)"))
                checked += 1
    print(f"  ({checked} workbooks written to a temporary folder and read back; "
          "only differences listed)")
except Exception as e:  # noqa: BLE001 -- a failed check is a failure, not a crash
    failures += 1
    print(f"  \u2717 export check failed: {e}")

print("\n" + ("ALL MATCH" if failures == 0 else f"{failures} FIGURE(S) DIFFER"))
print("READ ONLY -- nothing has been changed.")
sys.exit(1 if failures else 0)

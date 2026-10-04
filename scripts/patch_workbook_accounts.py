"""Workbook Key species sheet: accounts from both layers, by the publication rule.

_profiles() read only observatum.db, which since 26 September holds only YOUR
accounts -- so no review account reached the workbook. Now, per key species:

  1. your account                                   -> "Your account"
  2. else the current review account, if its licence is open (OGL, Creative
     Commons): "[Quoted from Lane, 2026] ..."       -> "Quoted - Lane, 2026"
  3. else, licence not open: "See Musgrove, A.J. 2023."
                                                    -> "Not quoted (licence) - see ..."
  4. else blank                                     -> ""

Read through shared/species_accounts.py -- the reader the panel and editor use.
New "Account source" column after "Species account". _profiles is replaced only
if nothing else in Examen calls it.

Writes NOTHING unless every anchor is found exactly once. Backup: .bak_wbaccounts.

Run:  python scripts\\patch_workbook_accounts.py
"""
import ast, glob, importlib, io, os, py_compile, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "Examen", "workbook_export.py")

NEW_PROFILES = '''def _profiles(tvks):
    """{tvk: (account_text, source_label)} -- your account, else an open-licence
    review account quoted and cited, else a pointer to the review. Read through
    shared/species_accounts.py, the reader the panel and editor use."""
    out = {}
    if not tvks:
        return out
    try:
        from shared.species_accounts import get_species_accounts
    except Exception:
        return out
    for tvk in tvks:
        try:
            acc = get_species_accounts(tvk)
        except Exception:
            continue
        if acc.own:
            out[tvk] = (acc.own, "Your account")
            continue
        r = acc.current_review
        if not (r and r.text):
            continue
        year = (r.date_published or "")[:4]
        cite = r.author or r.cite
        if year and year not in cite:
            cite = f"{cite} {year}"
        lic = (r.licence or "").lower()
        if any(k in lic for k in ("open government licence", "creative commons", "cc by", "ogl")):
            out[tvk] = (f"[Quoted from {cite}] {r.text}", f"Quoted - {cite}")
        else:
            out[tvk] = (f"See {cite}.", f"Not quoted (licence) - see {cite}")
    return out
'''

SHEET_EDITS = [
    ('"Species account", "Occurrence \u2014 to write (evidence follows)"],',
     '"Species account", "Account source",\n                 "Occurrence \u2014 to write (evidence follows)"],'),
    ("[12, 16, 20, 26, 20, 26, 6, 22, 24, 70, 44])",
     "[12, 16, 20, 26, 20, 26, 6, 22, 24, 70, 26, 44])"),
    ('prof, origin, source = profiles.get(k.tvk, ("", "", None))',
     'prof, prof_source = profiles.get(k.tvk, ("", ""))'),
    ('if prof and origin == "review" and source:', None),
    ('prof = f"[From {source}] {prof}"', None),
    ("prof,", "prof,\n                   prof_source,"),
    ("for col in (10, 11):", "for col in (10, 12):"),
    ('value="Species accounts are drawn from the species profile store. "',
     'value="Species account: yours where written; otherwise the current published "\n'
     '                  "review account, quoted and cited where its licence is open, or a "\n'
     '                  "pointer to the review where it is not (see Account source). "'),
    ('"profile written yet.").font = NOTE_FONT',
     '"account yet.").font = NOTE_FONT'),
]

raw = io.open(P, "rb").read()
bom = raw.startswith(b"\xef\xbb\xbf")
txt = raw.decode("utf-8-sig")
crlf = "\r\n" in txt
lines = txt.replace("\r\n", "\n").split("\n")
tree = ast.parse("\n".join(lines))
fn = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

print("Workbook -- key species accounts from both layers")
print("=" * 72)
if "get_species_accounts" in txt:
    sys.exit("  already patched -- nothing written")
problems = []

others = [f for f in glob.glob(os.path.join(ROOT, "Examen", "**", "*.py"), recursive=True)
          if os.path.abspath(f) != os.path.abspath(P) and "_profiles(" in io.open(f, encoding="utf-8-sig", errors="replace").read()]
print(f"  other Examen files calling _profiles(): {len(others)} {[os.path.basename(f) for f in others]}")
if others:
    problems.append("_profiles is used elsewhere -- not replacing it")

pf, sk = fn.get("_profiles"), fn.get("_sheet_key_species")
if not pf or not sk:
    problems.append("_profiles or _sheet_key_species not found")
else:
    body = lines[sk.lineno - 1:sk.end_lineno]
    new_body, ok = [], True
    for old, new in SHEET_EDITS:
        hits = [i for i, l in enumerate(body) if l.strip() == old]
        print(f"  x{len(hits)}  {old[:62]}")
        if len(hits) != 1:
            problems.append(f"anchor x{len(hits)}: {old[:50]}")
            ok = False
    if ok:
        # find every anchor first, then edit -- deletions must not disturb the search
        idx = {old: next(i for i, l in enumerate(body) if l.strip() == old) for old, _ in SHEET_EDITS}
        for old, new in SHEET_EDITS:
            i = idx[old]
            ind = body[i][:len(body[i]) - len(body[i].lstrip())]
            body[i] = None if new is None else ind + new
        body = [l for l in body if l is not None]
if problems:
    for p in problems:
        print(f"  x {p}")
    sys.exit("\nABORTED -- nothing written.")

out = lines[:pf.lineno - 1] + NEW_PROFILES.rstrip("\n").split("\n") + lines[pf.end_lineno:sk.lineno - 1] \
      + "\n".join(body).split("\n") + lines[sk.end_lineno:]
shutil.copy2(P, P + ".bak_wbaccounts")
io.open(P, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write(
    ("\r\n" if crlf else "\n").join(out))
try:
    py_compile.compile(P, doraise=True)
    sys.path[:0] = [ROOT, os.path.join(ROOT, "Observatum")]
    m = importlib.import_module("Examen.workbook_export")
except Exception as e:
    shutil.copy2(P + ".bak_wbaccounts", P)
    sys.exit(f"  x FAILED ({type(e).__name__}: {e}) -- restored")
print("\n  ok written, compiles, imports (backup: .bak_wbaccounts)")

import sqlite3, paths
c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
sample = [r[0] for r in c.execute("""SELECT p.tvk FROM species_profiles p JOIN reviews r ON r.id=p.review_id
                                    WHERE r.id IN (1, 3) GROUP BY r.id""")]
for tvk, (text, label) in m._profiles(set(sample)).items():
    print(f"  e.g. {tvk}: {label:<44} {text[:60]!r}")
print("\nRe-export a workbook and look at the Key species sheet.")

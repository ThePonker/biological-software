"""patch_workbook_stamp.py -- correct the Codex version stamp and a plural.

    python scripts/patch_workbook_stamp.py

Two fixes to Examen/workbook_export.py.

1. The version stamp read "14161" -- the bridge species count. `_codex_version`
   took the last row of `metadata` rather than looking up a key, and the last
   row happens to be `bridge_species`.

   codex.db actually carries everything the stamp needs:

       metadata.version        5.0
       metadata.build_date     2026-09-05T15:51:23
       metadata.jncc_date      2023-12-06
       build_log.notes         JNCC Dec 2023, Pantheon v3.7.4, 11-track scheme

   The stamp now reports the Codex version and build date, the JNCC designation
   spreadsheet date, and the Pantheon version separately -- which is what makes
   a figure reproducible: not "Codex 5.0" but "Codex 5.0 built 2026-09-05 from
   JNCC 2023-12-06 and Pantheon 3.7.4".

2. "(1 spp)" now reads "(1 sp)". Small, but it appears in a report.

Safe to re-run. Backs up as workbook_export.py.bak_fix1.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "Examen", "workbook_export.py")
BACKUP = TARGET + ".bak_fix1"

OLD_VERSION = '''def _codex_version():
    try:
        c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
        for tbl, col in (("build_log", "build_date"), ("metadata", "value")):
            try:
                r = c.execute(f"SELECT {col} FROM {tbl} ORDER BY rowid DESC "
                              "LIMIT 1").fetchone()
                if r and r[0]:
                    c.close()
                    return str(r[0])[:19]
            except sqlite3.Error:
                continue
        c.close()
    except sqlite3.Error:
        pass
    return "unknown"'''

NEW_VERSION = '''def _codex_provenance():
    """What the figures were computed against.

    Reproducibility needs more than a version number: the same Codex build,
    from the same JNCC spreadsheet and the same Pantheon release, gives the
    same figures. All three are recorded in codex.db.

    Returns [(label, value), ...] for the basis block.
    """
    meta, notes = {}, ""
    try:
        c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
        try:
            meta = {k: v for k, v in c.execute("SELECT key, value FROM metadata")}
        except sqlite3.Error:
            pass
        try:
            r = c.execute("SELECT notes FROM build_log ORDER BY id DESC "
                          "LIMIT 1").fetchone()
            notes = (r[0] or "") if r else ""
        except sqlite3.Error:
            pass
        c.close()
    except sqlite3.Error:
        pass

    version = meta.get("version") or meta.get("schema_version") or "unknown"
    built = (meta.get("build_date") or "")[:19].replace("T", " ")
    jncc = meta.get("jncc_date", "")

    pantheon = ""
    for token in notes.replace(",", " ").split():
        if token.lower().startswith("v3.") or token.lower().startswith("3."):
            pantheon = token.lstrip("vV")
            break

    out = [("Codex version", f"{version}" + (f", built {built}" if built else ""))]
    if jncc:
        out.append(("JNCC designations", jncc))
    if pantheon:
        out.append(("Pantheon version", pantheon))
    elif notes:
        out.append(("Source data", notes))
    return out'''

OLD_STAMP = '''            ("Jurisdiction", jurisdiction),
            ("Codex version", _codex_version()),
            ("Survey validity", "Two years from the survey date (CIEEM, 2019)"),
        ],'''

NEW_STAMP = '''            ("Jurisdiction", jurisdiction),
        ] + _codex_provenance() + [
            ("Survey validity", "Two years from the survey date (CIEEM, 2019)"),
        ],'''

OLD_SPP = '''    if n < SQI_MIN_SPECIES:
        return f"({n} spp)"
    return int(round(v))'''

NEW_SPP = '''    if n < SQI_MIN_SPECIES:
        return f"({n} sp)" if n == 1 else f"({n} spp)"
    return int(round(v))'''

OLD_FOOTER = '''            ("Species Quality Index (SQI)",
             sqi if scoring >= SQI_MIN_SPECIES else f"({scoring} spp)")]:'''

NEW_FOOTER = '''            ("Species Quality Index (SQI)",
             sqi if scoring >= SQI_MIN_SPECIES
             else f"({scoring} sp)" if scoring == 1 else f"({scoring} spp)")]:'''

EDITS = [
    ("_codex_provenance replaces _codex_version", OLD_VERSION, NEW_VERSION),
    ("stamp uses the provenance rows", OLD_STAMP, NEW_STAMP),
    ("singular 'sp' in _sqi_cell", OLD_SPP, NEW_SPP),
    ("singular 'sp' in the appendix footer", OLD_FOOTER, NEW_FOOTER),
]


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching Examen/workbook_export.py -- version stamp and plural")
    print("=" * 70)

    if "_codex_provenance" in text:
        print("  = already patched -- nothing to do")
        return 0

    failed = 0
    for label, old, new in EDITS:
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  + {label}")
        else:
            print(f"  x {label}  ({n} matches, expected 1)")
            failed += 1

    print("")
    if failed:
        print(f"  {failed} edit(s) failed -- NOTHING WRITTEN.")
        return 1

    shutil.copy2(TARGET, BACKUP)
    print(f"  backup written: {os.path.basename(BACKUP)}")
    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(text)

    print("")
    print("  Checking it imports and reads the provenance...")
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        sys.path.insert(0, _ROOT)
        import importlib
        m = importlib.import_module("Examen.workbook_export")
        importlib.reload(m)
        for label, value in m._codex_provenance():
            print(f"    {label:22} {value}")
    except Exception as e:  # noqa: BLE001
        print(f"  x FAILED: {type(e).__name__}: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} workbook_export.py")
        return 1

    print("")
    print("  Re-run scripts/test_workbook.py to regenerate.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())

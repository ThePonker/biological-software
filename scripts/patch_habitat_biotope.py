"""Habitats nest under the biotope Pantheon places them in.

Pantheon stores a species' biotopes and habitats as two unlinked lists, so a
species with two biotopes had each habitat counted under both -- "decaying
wood" under open habitats. Pantheon's own hierarchy is in habitat_traits: each
habitat's parent_trait_id is its broad biotope. Checked against the data: among
single-biotope species every habitat falls under its own biotope only; wet
woodland legitimately sits under both tree-associated and wetland.

  shared/services/pantheon_analysis_service.py
    + _habitat_biotopes(): {habitat: {biotope}} from habitat_traits, cached;
      empty (old behaviour) if pantheon.db cannot be read
    biotope x habitat pairing skips a habitat under a biotope that is not its own

One place: both the workbook's Habitats sheet and the Habitats tab read these
pairs. Biotope and habitat totals are unaffected -- only the nesting changes.

Prints Birmingham's biotope -> habitat counts before and after. Writes NOTHING
unless both anchors are found exactly once. Backup: .bak_habbio.

Run:  python scripts\\patch_habitat_biotope.py
"""
import importlib, io, os, py_compile, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "shared", "services", "pantheon_analysis_service.py")

PROBE = r'''
import sys, os
R = __ROOT__
sys.path[:0] = [R, os.path.join(R, "Observatum")]
from shared.repositories.pantheon_repository import PantheonRepository
from shared.repositories.codex_repository import CodexRepository
from shared.services.pantheon_analysis_service import PantheonAnalysisService
from Examen import examen_data as ed
d = ed.load_project_detail("Birmingham - Wheels Park", "", survey_year="2026")
tvks = [s.tvk for s in d.species_list if s.tvk]
r = PantheonAnalysisService(PantheonRepository(), CodexRepository()).analyse(tvks)
for bio in sorted(r.biotope_counts, key=lambda b: -r.biotope_counts[b]):
    habs = r.biotope_habitat_counts.get(bio, {})
    print(f"{bio} ({r.biotope_counts[bio]}): " +
          ", ".join(f"{h} {n}" for h, n in sorted(habs.items(), key=lambda kv: -kv[1])))
'''.replace("__ROOT__", repr(ROOT))


def probe():
    r = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, cwd=ROOT)
    out = (r.stdout + (("\n" + r.stderr[-800:]) if r.returncode else "")).strip()
    return "    " + out.replace("\n", "\n    ")


raw = io.open(P, "rb").read()
bom = raw.startswith(b"\xef\xbb\xbf")
lines = raw.decode("utf-8-sig").split("\n")

print("Habitats under their own biotope")
print("=" * 76)
if any("_habitat_biotopes" in l for l in lines):
    sys.exit("  already patched -- nothing written")

PAIR = "pairs.setdefault(bio, {}).setdefault(hab, set()).add(tvk)"
h1 = [i for i, l in enumerate(lines) if l.strip().rstrip("\r") == PAIR]
h2 = [i for i, l in enumerate(lines) if l.strip().rstrip("\r") == "class SQIResult:"]
print(f"  {PAIR!r}: x{len(h1)}")
print(f"  'class SQIResult:': x{len(h2)}")
if len(h1) != 1 or len(h2) != 1 or not lines[h2[0] - 1].strip().startswith("@dataclass"):
    sys.exit("ABORTED -- anchors not found as expected. Nothing written.")


def blk(i, body, ind=None):
    s = lines[i].rstrip("\r")
    ind = s[:len(s) - len(s.lstrip())] if ind is None else ind
    e = "\r" if lines[i].endswith("\r") else ""
    return [(ind + b if b else "") + e for b in body.split("\n")]


print("\n  BEFORE -- Birmingham biotope -> habitats:")
print(probe())

i = h1[0]
lines[i:i + 1] = blk(i, """# Pantheon places each habitat under its own biotope(s): decaying wood is
# tree-associated, never open habitats. Skip pairings Pantheon does not make.
_home = _habitat_biotopes().get(str(hab).lower())
if _home and str(bio).lower() not in _home:
    continue
""" + PAIR)

i = h2[0] - 1            # the @dataclass line above class SQIResult
lines[i:i] = blk(i, '''_HAB_BIO = None


def _habitat_biotopes():
    """{habitat: {biotope, ...}} from Pantheon's own hierarchy.

    habitat_traits holds the tree: each habitat row's parent_trait_id is its
    broad biotope. Wet woodland sits under both tree-associated and wetland.
    Cached. Empty if pantheon.db cannot be read -- pairing then falls back to
    every combination rather than failing.
    """
    global _HAB_BIO
    if _HAB_BIO is not None:
        return _HAB_BIO
    out = {}
    try:
        import sqlite3
        import paths
        c = sqlite3.connect(f"file:{paths.PANTHEON_DB}?mode=ro", uri=True)
        bio_names = {str(tid): str(name).strip().lower() for tid, name in c.execute(
            "SELECT DISTINCT trait_id, trait_name FROM habitat_traits "
            "WHERE trait_type = 'broad biotope'")}
        for name, parent in c.execute(
                "SELECT DISTINCT trait_name, parent_trait_id FROM habitat_traits "
                "WHERE trait_type = 'habitat'"):
            bio = bio_names.get(str(parent))
            if bio:
                out.setdefault(str(name).strip().lower(), set()).add(bio)
        c.close()
    except Exception:
        out = {}
    _HAB_BIO = out
    return out

''', ind="")

shutil.copy2(P, P + ".bak_habbio")
io.open(P, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write("\n".join(lines))
try:
    py_compile.compile(P, doraise=True)
    sys.path[:0] = [ROOT, os.path.join(ROOT, "Observatum")]
    m = importlib.import_module("shared.services.pantheon_analysis_service")
    hb = m._habitat_biotopes()
    print(f"\n  ok written, compiles, imports (backup: .bak_habbio)")
    print(f"  Pantheon hierarchy read: {len(hb)} habitats")
    for h in sorted(hb):
        print(f"    {h:<28} -> {', '.join(sorted(hb[h]))}")
except Exception as e:
    shutil.copy2(P + ".bak_habbio", P)
    sys.exit(f"  x FAILED ({type(e).__name__}: {e}) -- restored")

print("\n  AFTER -- Birmingham biotope -> habitats:")
print(probe())
print("\nBiotope totals (in brackets) should be unchanged; habitats should now sit only")
print("under their own biotope. Re-export the workbook to see it on the Habitats sheet.")

"""Codex build: decide "invertebrate" from UKSI taxonomy, not from designations.

Fault: the Pantheon SQS import kept a score only if the species held a Codex
DESIGNATION with category 'Invertebrate'. Common species hold none -- 7-spot
Ladybird, Common Greenbottle, Marmalade Hoverfly -- so their Pantheon SQS 1 was
discarded as a "non-invertebrate TVK collision": 4,085 scores. Every SQI since
was computed without most SQS-1 species, so every SQI was too high. Species that
arrive with Pantheon ecology still showed in Examen, which hid the loss.

Fix: invert_tvks = the designations set UNION every UKSI taxon in kingdom
Animalia outside phylum Chordata. Genuine collisions (a historic Pantheon TVK
now naming a plant, bird or fungus) are still filtered.

Edits scripts/build_codex_db.py only. Nothing is rebuilt here. Writes NOTHING
unless the anchor is found exactly once. Backup: .bak_invert.

Run:  python scripts\\patch_codex_invert_filter.py
Then: python scripts\\check_sqi_table.py --save sqi_before.txt
      back up codex.db, rebuild, seed
      python scripts\\check_sqi_table.py --compare sqi_before.txt
"""
import io, os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "scripts", "build_codex_db.py")

raw = io.open(P, "rb").read()
bom = raw.startswith(b"\xef\xbb\xbf")
lines = raw.decode("utf-8-sig").split("\n")

print("Codex build -- invertebrate filter from UKSI taxonomy")
print("=" * 72)
if any("_n_desig" in l for l in lines):
    sys.exit("  already patched -- nothing written")
A = "invert_tvks = {r[0] for r in c.fetchall()}"
h = [i for i, l in enumerate(lines) if l.strip().rstrip("\r") == A]
ctx = [i for i, l in enumerate(lines) if "FROM designations WHERE category = 'Invertebrate'" in l]
print(f"  {A!r}: x{len(h)}   designations query: x{len(ctx)}")
if len(h) != 1 or len(ctx) != 1 or not (0 < h[0] - ctx[0] < 5):
    sys.exit("ABORTED -- anchor not found as expected. Nothing written.")

i = h[0]
s = lines[i].rstrip("\r")
ind = s[:len(s) - len(s.lstrip())]
eol = "\r" if lines[i].endswith("\r") else ""
block = '''# Designations alone miss every common species (no designation, so not
# "invertebrate"), and their Pantheon SQS 1 was dropped -- 4,085 scores,
# inflating every SQI. Add UKSI's own taxonomy: Animalia outside Chordata.
# Genuine collisions (a historic TVK now naming a plant/bird/fungus) still fail.
_n_desig = len(invert_tvks)
try:
    import paths as _paths
    _u = sqlite3.connect(f"file:{_paths.UKSI_DB}?mode=ro", uri=True)
    invert_tvks |= {r[0] for r in _u.execute(
        "SELECT tvk FROM taxa WHERE LOWER(COALESCE(kingdom,'')) = 'animalia' "
        "AND LOWER(COALESCE(phylum,'')) != 'chordata'")}
    _u.close()
except Exception as _e:
    print(f"  WARNING: UKSI taxonomy unavailable ({_e}); invertebrate set from designations only")
print(f"  Invertebrate TVKs: {_n_desig:,} from designations, "
      f"{len(invert_tvks):,} with UKSI taxonomy")'''
lines[i + 1:i + 1] = [(ind + b if b else "") + eol for b in block.split("\n")]

shutil.copy2(P, P + ".bak_invert")
io.open(P, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write("\n".join(lines))
try:
    py_compile.compile(P, doraise=True)
except py_compile.PyCompileError as e:
    shutil.copy2(P + ".bak_invert", P)
    sys.exit(f"  x COMPILE FAILED -- restored\n{e}")
print("  ok written and compiles (backup: build_codex_db.py.bak_invert)")
print("\n  Lines now:")
now = io.open(P, encoding="utf-8-sig").read().split("\n")
for k in range(i - 4, i + 20):
    print(f"  {k + 1:5}: {now[k].rstrip()}")
print("\nNothing rebuilt. Next: check_sqi_table.py --save sqi_before.txt")

"""Codex build: route NS-excludes / NR-excludes -- they are Nationally Scarce / Rare.

JNCC: "NS-excludes" = Nationally Scarce, excluding Red Listed taxa;
      "NS-includes" = Nationally Scarce, including Red Listed taxa.
Both say the species is Nationally Scarce. The build routed only -includes,
calling -excludes a duplicate. For 272 species -excludes is the ONLY NS code
(older reviews published only that form: Falk & Crossley 2005, water beetles
2010, hoverflies 2014, Falk & Chandler 2005), so their status was discarded.

  DESIG_TO_TRACK  + "NR-excludes" -> rarity_modern NR, "NS-excludes" -> NS
  ABBR_PRIORITY   + both at 89, one below the -includes twins (90), so a
                  species carrying both keeps one entry
  header comment  corrected

Edits scripts/build_codex_db.py only; nothing rebuilt. Writes NOTHING unless
every anchor is found exactly once. Backup: .bak_excludes.

Run:  python scripts\\patch_codex_excludes.py
"""
import io, os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "scripts", "build_codex_db.py")
raw = io.open(P, "rb").read()
bom = raw.startswith(b"\xef\xbb\xbf")
lines = raw.decode("utf-8-sig").split("\n")

print("Codex build -- route NS/NR-excludes")
print("=" * 72)
if any(l.strip().startswith('"NS-excludes":') for l in lines):
    sys.exit("  already patched -- nothing written")


def one(pred, name):
    h = [i for i, l in enumerate(lines) if pred(l.strip().rstrip("\r"))]
    print(f"  {name:<34} x{len(h)}")
    return h[0] if len(h) == 1 else None


track = one(lambda s: s.startswith('"NS-includes":') and "rarity_modern" in s, "DESIG_TO_TRACK NS-includes")
prio = one(lambda s: s.startswith('"NS-includes":') and s.rstrip(",").split(":")[-1].strip().isdigit(),
           "ABBR_PRIORITY NS-includes")
hdr = one(lambda s: s == "- NR/NS-excludes variants dropped (redundant with -includes)", "header comment")
if None in (track, prio, hdr):
    sys.exit("ABORTED -- anchors not found exactly once. Nothing written.")


def like(i, text):
    s = lines[i].rstrip("\r")
    ind = s[:len(s) - len(s.lstrip())]
    return ind + text + ("\r" if lines[i].endswith("\r") else "")


# bottom-up
p_i, t_i = max(prio, track), min(prio, track)
for i in sorted([track, prio, hdr], reverse=True):
    if i == prio:
        lines[i + 1:i + 1] = [like(i, '"NR-excludes":            89,'),
                              like(i, '"NS-excludes":            89,')]
    elif i == track:
        lines[i + 1:i + 1] = [
            like(i, "# -excludes is routed too: for 272 species (Falk & Crossley 2005, water"),
            like(i, "# beetles 2010, hoverflies 2014 ...) it is the ONLY NS/NR code. Ranked"),
            like(i, "# one below -includes in ABBR_PRIORITY, so a species with both keeps one."),
            like(i, '"NR-excludes":                  ("rarity_modern", "NR", None),'),
            like(i, '"NS-excludes":                  ("rarity_modern", "NS", None),')]
    else:
        lines[i] = like(i, "- NR/NS-excludes routed as NR/NS (some reviews publish only -excludes)")

shutil.copy2(P, P + ".bak_excludes")
io.open(P, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write("\n".join(lines))
try:
    py_compile.compile(P, doraise=True)
except py_compile.PyCompileError as e:
    shutil.copy2(P + ".bak_excludes", P)
    sys.exit(f"  x COMPILE FAILED -- restored\n{e}")
print("  ok written and compiles (backup: build_codex_db.py.bak_excludes)\n")
now = io.open(P, encoding="utf-8-sig").read().split("\n")
for k, l in enumerate(now, 1):
    if "excludes" in l:
        print(f"  {k:5}: {l.rstrip()}")
print("\nNothing rebuilt yet.")

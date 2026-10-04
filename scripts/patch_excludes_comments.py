"""Correct two comments in build_codex_db.py that still say -excludes is ignored.

  line ~176  "(e.g. -excludes rarity variants)" -> "(e.g. WL, some global and bird codes)"
  line ~246  the comment block above "NR-includes" is replaced with one that
             says both forms are routed

Comment lines only: refuses if the block it would replace contains any code.
Backup: .bak_comments.

Run:  python scripts\\patch_excludes_comments.py
"""
import io, os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "scripts", "build_codex_db.py")
raw = io.open(P, "rb").read()
bom = raw.startswith(b"\xef\xbb\xbf")
lines = raw.decode("utf-8-sig").split("\n")
S = lambda i: lines[i].strip().rstrip("\r")

a = [i for i in range(len(lines)) if "(e.g. -excludes rarity variants)" in lines[i]]
b = [i for i in range(len(lines)) if S(i).startswith('# Only the "-includes" variants are routed.')]
print(f"  line-176 comment x{len(a)}   line-246 block start x{len(b)}")
if len(a) != 1 or len(b) != 1:
    sys.exit("ABORTED -- anchors not found exactly once (already done?). Nothing written.")
start = b[0]
end = next((i for i in range(start, start + 12) if S(i).startswith('"NR-includes":')), None)
if end is None or not all(S(i).startswith("#") or not S(i) for i in range(start, end)):
    sys.exit("ABORTED -- block above NR-includes is not comments only. Nothing written.")

eol = "\r" if lines[start].endswith("\r") else ""
ind = lines[start][:len(lines[start]) - len(lines[start].lstrip())]
print("  replacing:")
for i in range(start, end):
    print(f"    {i + 1:5}: {lines[i].rstrip()}")
lines[start:end] = [ind + "# Both forms of the modern rarity codes are routed. JNCC: -includes = NS/NR" + eol,
                    ind + "# including Red Listed taxa; -excludes = NS/NR excluding them. Both mean the" + eol,
                    ind + "# species is Nationally Scarce/Rare, and some reviews publish only -excludes." + eol]
lines[a[0]] = lines[a[0]].replace("(e.g. -excludes rarity variants)", "(e.g. WL, some global and bird codes)")

shutil.copy2(P, P + ".bak_comments")
io.open(P, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write("\n".join(lines))
try:
    py_compile.compile(P, doraise=True)
except py_compile.PyCompileError as e:
    shutil.copy2(P + ".bak_comments", P)
    sys.exit(f"  x COMPILE FAILED -- restored\n{e}")
print("  ok -- comments corrected, compiles (backup: .bak_comments)")
for k, l in enumerate(io.open(P, encoding="utf-8-sig").read().split("\n"), 1):
    if "excludes" in l:
        print(f"  {k:5}: {l.rstrip()}")

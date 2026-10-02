"""Site Analysis: the project table can no longer be squeezed away.

  line 204  setMaximumHeight(180)  ->  setMinimumHeight(150)
            A cap with no floor let the detail panel crush the table to a
            sliver. Now it keeps ~5 rows, and can be dragged taller.
  line 223  + setChildrenCollapsible(False)  -- neither pane can vanish
            + a starting split (table ~1/4)
            + the split you drag to is remembered (QSettings "Flauna"/"Examen")

Writes NOTHING unless both anchors are found exactly once. Backup: .bak_splitter.
Compiles the file; the Qt view is not imported (05_Rules.md). Prints lines
196-230 afterwards so the result can be read, not trusted.

Run:  python scripts\\patch_examen_splitter.py
"""
import io, os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "Examen", "site_analysis_view.py")

raw = io.open(P, "rb").read()
bom = raw.startswith(b"\xef\xbb\xbf")
lines = raw.decode("utf-8-sig").split("\n")

A1 = "self.table.setMaximumHeight(180)"
A2 = "splitter.setStretchFactor(0, 0); splitter.setStretchFactor(1, 1)"

print("Examen Site Analysis -- splitter")
print("=" * 72)
if any("setChildrenCollapsible" in l for l in lines):
    sys.exit("  already patched -- nothing written")
h1 = [i for i, l in enumerate(lines) if l.strip().rstrip("\r") == A1]
h2 = [i for i, l in enumerate(lines) if l.strip().rstrip("\r") == A2]
print(f"  {A1!r}: x{len(h1)}")
print(f"  {A2!r}: x{len(h2)}")
if len(h1) != 1 or len(h2) != 1:
    sys.exit("ABORTED -- anchors not found exactly once. Nothing written.")


def blk(i, body):
    s = lines[i].rstrip("\r")
    ind = s[:len(s) - len(s.lstrip())]
    eol = "\r" if lines[i].endswith("\r") else ""
    return [(ind + b if b else "") + eol for b in body.split("\n")]


# bottom first, so the earlier index stays valid
i2 = h2[0]
lines[i2:i2 + 1] = blk(i2, A2 + """
# Neither pane may collapse: the table keeps its minimum, the detail its own.
splitter.setChildrenCollapsible(False)
self._splitter = splitter
from PySide6.QtCore import QSettings
_st = QSettings("Flauna", "Examen").value("site_analysis/splitter")
if _st is None or not splitter.restoreState(_st):
    splitter.setSizes([240, 760])          # table ~1/4 on first run
splitter.splitterMoved.connect(
    lambda *_: QSettings("Flauna", "Examen").setValue(
        "site_analysis/splitter", self._splitter.saveState()))""")

i1 = h1[0]
lines[i1:i1 + 1] = blk(i1, """# A floor, not a cap: ~5 rows always visible, draggable taller.
self.table.setMinimumHeight(150)""")

shutil.copy2(P, P + ".bak_splitter")
io.open(P, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write("\n".join(lines))
try:
    py_compile.compile(P, doraise=True)
    print("  ok written and compiles (backup: site_analysis_view.py.bak_splitter)")
except py_compile.PyCompileError as e:
    shutil.copy2(P + ".bak_splitter", P)
    sys.exit(f"  x COMPILE FAILED -- restored\n{e}")

print("\n  Lines 196-236 as they now stand:")
now = io.open(P, encoding="utf-8-sig").read().split("\n")
for i in range(195, min(len(now), 236)):
    print(f"  {i + 1:4}: {now[i].rstrip()}")
print("\nNext: open Examen, click several projects, drag the divider, reopen.")

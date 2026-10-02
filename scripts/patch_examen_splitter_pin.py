"""Site Analysis: clicking a project no longer moves the divider.

Cause: each project fills the detail tabs with different content, and the
splitter honours the content's minimum size, so every click took height from
the table.

  1. detail_container.setMinimumHeight(200) -- an explicit minimum, which the
     splitter uses INSTEAD of following the content.
  2. The click handler is wrapped: the split is recorded before the project
     loads and restored after, immediately and again once Qt has finished
     laying out (QTimer.singleShot(0, ...)).

Requires patch_examen_splitter.py to have been applied first. Writes NOTHING
unless every anchor is found exactly once. Backup: .bak_pin. Compiles; prints
the changed region.

Run:  python scripts\\patch_examen_splitter_pin.py
"""
import io, os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "Examen", "site_analysis_view.py")

raw = io.open(P, "rb").read()
bom = raw.startswith(b"\xef\xbb\xbf")
text = raw.decode("utf-8-sig")

print("Examen Site Analysis -- pin the divider across clicks")
print("=" * 72)
if "_keep_split" in text:
    sys.exit("  already patched -- nothing written")

OLD_CONNECT = "self.table.cellClicked.connect(self._on_project_clicked)"
ADD_DETAIL = "splitter.addWidget(detail_container)"
AFTER = "splitter.setChildrenCollapsible(False)"
counts = {a: text.count(a) for a in (OLD_CONNECT, ADD_DETAIL, AFTER)}
for a, n in counts.items():
    print(f"  {a!r}: x{n}")
if any(n != 1 for n in counts.values()):
    sys.exit("ABORTED -- an anchor is not found exactly once "
             "(was patch_examen_splitter.py applied?). Nothing written.")

lines = text.split("\n")


def idx(s):
    return next(i for i, l in enumerate(lines) if s in l)


def blk(i, body):
    s = lines[i].rstrip("\r")
    ind = s[:len(s) - len(s.lstrip())]
    eol = "\r" if lines[i].endswith("\r") else ""
    return [(ind + b if b else "") + eol for b in body.split("\n")]


# 3. after setChildrenCollapsible: the wrapper and its connection
i = idx(AFTER)
lines[i + 1:i + 1] = blk(i, """# Clicking a project must not move the divider: record the split, load,
# restore -- now and again once Qt has finished laying out.
def _keep_split(row, col):
    sizes = self._splitter.sizes()
    self._on_project_clicked(row, col)
    self._splitter.setSizes(sizes)
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, lambda: self._splitter.setSizes(sizes))
self.table.cellClicked.connect(_keep_split)""")

# 2. explicit minimum on the detail panel, just before it is added
i = idx(ADD_DETAIL)
lines[i:i] = blk(i, "detail_container.setMinimumHeight(200)   # explicit: the splitter stops following content")

# 1. remove the original direct connection (the wrapper replaces it)
i = idx(OLD_CONNECT)
l = lines[i]
if l.strip().rstrip("\r") == OLD_CONNECT:
    del lines[i]
elif (OLD_CONNECT + "; ") in l:
    lines[i] = l.replace(OLD_CONNECT + "; ", "")
else:
    sys.exit("ABORTED -- the connect line has an unexpected shape. Nothing written.")

shutil.copy2(P, P + ".bak_pin")
io.open(P, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write("\n".join(lines))
try:
    py_compile.compile(P, doraise=True)
    print("  ok written and compiles (backup: site_analysis_view.py.bak_pin)")
except py_compile.PyCompileError as e:
    shutil.copy2(P + ".bak_pin", P)
    sys.exit(f"  x COMPILE FAILED -- restored\n{e}")

now = io.open(P, encoding="utf-8-sig").read()
print(f"  connections to _on_project_clicked now: "
      f"{now.count('cellClicked.connect(self._on_project_clicked)')} (expect 0)")
print(f"  connections to _keep_split: {now.count('cellClicked.connect(_keep_split)')} (expect 1)")
print("\n  Region as it now stands:")
nl = now.split("\n")
s = next(i for i, l in enumerate(nl) if "QSplitter(Qt.Orientation.Vertical)" in l)
for k in range(s, min(len(nl), s + 52)):
    print(f"  {k + 1:4}: {nl[k].rstrip()}")

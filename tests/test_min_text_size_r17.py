"""R17 C4, raised in R18: no interface text below 12 px (stylesheets) or 9 pt (fonts set in code).

Scans the .py files for literal `font-size: Npx` (N < 12) / `font-size: Npt` (N < 9) and for
setPointSize(N) / QFont("...", N) with N < 9. Left out, on purpose: text drawn onto maps,
exports and the 3D view (views/mapping, shared/maps), Curator's printed-label and box previews
(painted at print size), tests, scripts, the archive, the manual's screenshot script, and the
files other Round 17 builders were changing when this was written (listed in SKIP_FOR_NOW,
which the manager empties after merging: then the scan covers them too).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = ("_archive", "tests", "scripts", "docs", "data", "packaging", ".git", "_r17_shots")
SKIP_PREFIXES = ("Observatum/src/views/mapping/view3d", "shared/maps/")      # R18: the mapping widgets are scanned now
PRINT_LAYOUTS = ("Curator/planner_preview.py",)         # painted print previews (7 pt); its interface label is checked by the R18 scan
SKIP_FOR_NOW = ()                                       # emptied after the Round 17 merge

CSS = re.compile(r"font-size:\s*(\d+(?:\.\d+)?)\s*(px|pt)")
PT_CODE = re.compile(r"setPointSize(?:F)?\(\s*(\d+(?:\.\d+)?)\s*\)|QFont\([^()]*,\s*(\d+(?:\.\d+)?)\s*[,)]")


def _files():
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if rel.split("/")[0] in SKIP_DIRS or rel.startswith(SKIP_PREFIXES) \
                or rel in PRINT_LAYOUTS or rel.startswith(SKIP_FOR_NOW):
            continue
        yield rel, p


def test_no_small_text_in_stylesheets_or_fonts():
    found = []
    for rel, p in _files():
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in CSS.finditer(line):
                v, unit = float(m.group(1)), m.group(2)
                if (unit == "px" and v < 12) or (unit == "pt" and v < 9):
                    found.append(f"{rel}:{n}: {m.group(0)}")
            for m in PT_CODE.finditer(line):
                v = float(m.group(1) or m.group(2))
                if v < 9:
                    found.append(f"{rel}:{n}: point size {v:g}")
    assert not found, "text below the minimum size:\n" + "\n".join(found)

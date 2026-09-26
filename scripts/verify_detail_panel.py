import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "Observatum"))   # config expects src/ here

import py_compile
for rel in (r"Observatum\src\views\collection\family_detail_panel.py",
            r"Observatum\src\views\collection\taxonomic_sidebar.py"):
    py_compile.compile(os.path.join(ROOT, rel), doraise=True)
print("both compile")

from shared.sex_summary import format_sex_summary
def specimens_text(n, sexes=None):
    if not sexes:
        return str(n)
    s = format_sex_summary(*sexes)
    return f"{n} ({s})" if s else str(n)

for (n, sx), expect in [((55, (5, 2, 48)), "55 (\u26425 \u26402 +48)"),
                        ((13, (0, 1, 12)), "13 (\u26401 +12)"),
                        ((7, (0, 0, 7)), "7"),
                        ((7, None), "7"),
                        ((2, (1, 1, 0)), "2 (\u26421 \u26401)")]:
    got = specimens_text(n, sx)
    print(("  ok  " if got == expect else "  BAD ") + f"{n}, {sx} -> {got}")

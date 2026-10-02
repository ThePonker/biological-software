"""Site Analysis project table: sortable headers, dd/mm/yyyy dates.

  * Click a header to sort; click again to reverse. Each cell DISPLAYS its text
    but SORTS on its value: numbers as numbers (9 before 19), dates by the ISO
    date behind the dd/mm/yyyy display, text case-insensitively.
  * Each row carries its project (UserRole on column 0). The click handler reads
    it from there instead of self._projects[row], so a sorted table still opens
    the project you clicked.
  * Sorting is off while the table fills, on afterwards -- with it on, setItem
    can re-sort mid-fill and rows land against the wrong data.
  * Dates column shows dd/mm/yyyy.

_load_projects and _on_project_clicked are located by parsing, so the edit
cannot land in the same-looking line in the build method. Writes NOTHING unless
every anchor is found exactly once. Backup: .bak_sort. Compiles; prints the
changed methods.

Run:  python scripts\\patch_examen_table_sort.py
"""
import ast, io, os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "Examen", "site_analysis_view.py")

raw = io.open(P, "rb").read()
bom = raw.startswith(b"\xef\xbb\xbf")
text = raw.decode("utf-8-sig")
lines = text.split("\n")

print("Examen project table -- sorting and dd/mm/yyyy")
print("=" * 72)
if "_SortItem" in text:
    sys.exit("  already patched -- nothing written")

tree = ast.parse(text.replace("\r", ""))
fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
first_class = min((n.lineno for n in tree.body if isinstance(n, ast.ClassDef)), default=None)
for need in ("_load_projects", "_on_project_clicked"):
    if need not in fns:
        sys.exit(f"ABORTED -- {need}() not found. Nothing written.")
if first_class is None:
    sys.exit("ABORTED -- no top-level class found. Nothing written.")

lp, oc = fns["_load_projects"], fns["_on_project_clicked"]


def find_in(fn, s):
    hits = [i for i in range(fn.lineno - 1, fn.end_lineno)
            if lines[i].strip().rstrip("\r") == s]
    return hits


# ---- _load_projects: replace from setRowCount to the Stretch line
a = find_in(lp, "self.table.setRowCount(len(self._projects))")
b = find_in(lp, "self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)")
# ---- _on_project_clicked: the two row-position lines
c1 = find_in(oc, "if row >= len(self._projects): return")
c2 = find_in(oc, "proj = self._projects[row]")
for name, h in (("setRowCount", a), ("Stretch", b), ("row guard", c1), ("_projects[row]", c2)):
    print(f"  {name:<16} x{len(h)}")
if not (len(a) == len(b) == len(c1) == len(c2) == 1) or b[0] < a[0]:
    sys.exit("ABORTED -- anchors not found exactly once in their methods. Nothing written.")


def blk(i, body):
    s = lines[i].rstrip("\r")
    ind = s[:len(s) - len(s.lstrip())]
    eol = "\r" if lines[i].endswith("\r") else ""
    return [(ind + x if x else "") + eol for x in body.split("\n")]


eol0 = "\r" if lines[first_class - 1].endswith("\r") else ""
HELPERS = [x + eol0 for x in '''# ---- project table: display one thing, sort on another --------------------
_PROJ_ROLE = int(Qt.ItemDataRole.UserRole)        # column 0: index into self._projects
_SORT_ROLE = int(Qt.ItemDataRole.UserRole) + 1    # every column: the value to sort on


class _SortItem(QTableWidgetItem):
    """Shows its text; sorts on _SORT_ROLE -- numbers as numbers, dates as ISO."""
    def __lt__(self, other):
        a, b = self.data(_SORT_ROLE), other.data(_SORT_ROLE)
        if a is None or b is None or type(a) is not type(b):
            return super().__lt__(other)
        return a < b


def _dmy(iso):
    """'2026-05-05' -> '05/05/2026'; anything else unchanged."""
    s = str(iso or "")
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return f"{s[8:10]}/{s[5:7]}/{s[:4]}"
    return s

'''.split("\n")]

# bottom-up
i = c1[0]
lines[i:c2[0] + 1] = blk(i, """# The row carries its project: after sorting, row N is not self._projects[N].
_it = self.table.item(row, 0)
_idx = _it.data(_PROJ_ROLE) if _it is not None else None
if _idx is None or _idx >= len(self._projects): return
proj = self._projects[_idx]""")

i = a[0]
lines[i:b[0] + 1] = blk(i, """# Sorting off while filling: with it on, setItem can re-sort mid-fill.
self.table.setSortingEnabled(False)
self.table.setRowCount(len(self._projects))
self.freeze_btn.setEnabled(False); self.appendix_btn.setEnabled(False)
self._current_detail = None; self._current_result = None; self.detail_tabs.hide()

def put(r, c, text, key, centre=True, colour=None, tip=None):
    it = _SortItem(text)
    it.setData(_SORT_ROLE, key)
    if centre: it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    if colour: it.setForeground(QColor(colour))
    if tip: it.setToolTip(tip)
    self.table.setItem(r, c, it)
    return it

for i, p in enumerate(self._projects):
    name = put(i, 0, p.project_name, (p.project_name or "").lower(), centre=False)
    name.setData(_PROJ_ROLE, i)          # travels with the row when it sorts
    yr = str(p.survey_year or "")
    put(i, 1, yr or "all", int(yr) if yr.isdigit() else 0,
        colour=None if yr else TEXT_MUTED)
    put(i, 2, p.client or "", (p.client or "").lower(), centre=False)
    put(i, 3, str(p.site_count), int(p.site_count or 0),
        tip=", ".join(p.site_names) if p.site_names else None)
    put(i, 4, str(p.visit_count), int(p.visit_count or 0))
    put(i, 5, str(p.species_count), int(p.species_count or 0))
    put(i, 6, str(p.key_species_count), int(p.key_species_count or 0),
        colour=RED_STATUS if (p.key_species_count or 0) > 0 else None)
    put(i, 7, f"{p.key_species_pct}%", float(p.key_species_pct or 0))
    sq = (str(int(p.sqi)) if p.sqi > 0 else "-") + ("*" if p.sqi > 0 and not p.sqi_reliable else "")
    put(i, 8, sq, float(p.sqi or 0),
        colour=MOSS_GREEN if p.sqi >= 150 else (AMBER if p.sqi >= 125 else None))
    put(i, 9, f"{_dmy(p.first_date)} \\u2013 {_dmy(p.last_date)}" if p.first_date else "",
        p.first_date or "", centre=False)
self.table.resizeColumnsToContents()
self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
self.table.setSortingEnabled(True)""")

lines[first_class - 1:first_class - 1] = HELPERS

shutil.copy2(P, P + ".bak_sort")
io.open(P, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write("\n".join(lines))
try:
    py_compile.compile(P, doraise=True)
    print("  ok written and compiles (backup: site_analysis_view.py.bak_sort)")
except py_compile.PyCompileError as e:
    shutil.copy2(P + ".bak_sort", P)
    sys.exit(f"  x COMPILE FAILED -- restored\n{e}")

now = io.open(P, encoding="utf-8-sig").read()
print(f"  self._projects[row] remaining: {now.count('self._projects[row]')} (expect 0)")
print(f"  setSortingEnabled(True): {now.count('setSortingEnabled(True)')} (expect 1)")
t2 = ast.parse(now.replace("\r", ""))
f2 = {n.name: n for n in ast.walk(t2) if isinstance(n, ast.FunctionDef)}
nl = now.split("\n")
for nm in ("_on_project_clicked",):
    f = f2[nm]
    print(f"\n  {nm}() opening lines:")
    for k in range(f.lineno - 1, min(f.lineno + 7, f.end_lineno)):
        print(f"  {k + 1:4}: {nl[k].rstrip()}")

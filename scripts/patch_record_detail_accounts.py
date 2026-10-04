"""Record Detail windows: species accounts in full, in a right-hand column.

Installs  Observatum/src/views/components/species_accounts_panel.py  (from the
same folder as this script) and patches the two LIVE windows:

  views/dialogs/record_detail_dialog.py         RecordDetailDialog
  views/dialogs/scheme_record_detail_dialog.py  SchemeRecordDetailDialog

In each:
  _add_profile_section  -> builds SpeciesAccountsPanel (tab colours: _accent,
                           _accent_light, _accent_dark); not added to the column
  _setup_ui             -> record scroll | accounts panel, side by side (QSplitter)
  update_profile        -> reloads the panel after the editor saves
  __init__              -> wider window (min 1000, opens at 1200 x 760)

Callers unchanged: profile_requested / update_profile work as before.
The dead copies (observations/record_detail.py, scheme/scheme_dialogs.py's
SchemeRecordDetailDialog) are not touched.

Every change is located by parsing (ast) inside its own function; NOTHING is
written unless every anchor is found exactly once in both files. Backups:
*.bak_accounts. Restored if either file fails to compile.

Run:  python scripts\\patch_record_detail_accounts.py
"""
import ast, io, os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = os.path.join(ROOT, "Observatum", "src", "views")
PANEL_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "species_accounts_panel.py")
PANEL_DST = os.path.join(V, "components", "species_accounts_panel.py")
FILES = {
    os.path.join(V, "dialogs", "record_detail_dialog.py"):
        [("self.setMinimumWidth(600)", "self.setMinimumWidth(1000)"),
         ("self.resize(700, 700)", "self.resize(1200, 760)")],
    os.path.join(V, "dialogs", "scheme_record_detail_dialog.py"):
        [("self.setFixedWidth(700)", "self.setMinimumWidth(1000)"),
         ("self.resize(700, 700)", "self.resize(1200, 760)")],
}

NEW_PROFILE = '''    def _add_profile_section(self, layout):
        """Species accounts live in the right-hand column (SpeciesAccountsPanel):
        built here in the tab's colours, placed beside the record by _setup_ui."""
        from ..components.species_accounts_panel import SpeciesAccountsPanel
        r = self.record or {}
        self._accounts_panel = SpeciesAccountsPanel(
            r.get('species_tvk') or r.get('tvk') or r.get('taxon_version_key'),
            r.get('species_name') or r.get('scientific_name') or r.get('species'),
            self._accent, self._accent_light, self._accent_dark, self)
        self._accounts_panel.edit_requested.connect(
            lambda: self.profile_requested.emit(self.record))
        self._profile_preview = None
        self._profile_btn = None
'''
NEW_UPDATE = '''    def update_profile(self, profile_text: str):
        """Called by the host after the editor saves: reload the accounts panel."""
        self.profile_text = profile_text
        if getattr(self, '_accounts_panel', None):
            self._accounts_panel.refresh()
'''
SPLIT = '''from PySide6.QtWidgets import QSplitter
body = QSplitter(Qt.Orientation.Horizontal)
body.setChildrenCollapsible(False)
body.addWidget(scroll)
body.addWidget(self._accounts_panel)
body.setSizes([520, 680])
main_layout.addWidget(body, 1)'''

print("Record Detail -- species accounts column")
print("=" * 72)
if not os.path.isfile(PANEL_SRC):
    sys.exit(f"  x {PANEL_SRC} missing -- save species_accounts_panel.py beside this script")

plans, problems = {}, []
for path, inits in FILES.items():
    raw = io.open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    lines = raw.decode("utf-8-sig").split("\n")
    if any("SpeciesAccountsPanel" in l for l in lines):
        problems.append(f"{os.path.basename(path)} already patched")
        continue
    eol = "\r" if lines[0].endswith("\r") else ""
    tree = ast.parse("\n".join(l.rstrip("\r") for l in lines))
    fn = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    edits = []
    for name, new in (("_add_profile_section", NEW_PROFILE), ("update_profile", NEW_UPDATE)):
        n = fn.get(name)
        if not n:
            problems.append(f"{os.path.basename(path)}: {name} not found");  continue
        edits.append((n.lineno - 1, n.end_lineno - 1, [l + eol for l in new.rstrip("\n").split("\n")]))
    su = fn.get("_setup_ui")
    hits = [i for i in range(su.lineno - 1, su.end_lineno) if lines[i].strip() == "main_layout.addWidget(scroll, 1)"] if su else []
    if len(hits) != 1:
        problems.append(f"{os.path.basename(path)}: _setup_ui scroll line x{len(hits)}")
    else:
        i = hits[0]
        ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
        edits.append((i, i, [ind + s + eol for s in SPLIT.split("\n")]))
    ini = fn.get("__init__")
    for old, new in inits:
        h = [i for i in range(ini.lineno - 1, ini.end_lineno) if lines[i].strip() == old] if ini else []
        if len(h) != 1:
            problems.append(f"{os.path.basename(path)}: {old} x{len(h)}")
        else:
            edits.append((h[0], h[0], [lines[h[0]].replace(old, new)]))
    print(f"  {os.path.relpath(path, ROOT):<56} edits {len(edits)}")
    plans[path] = (lines, edits, bom)

if problems:
    for p in problems:
        print(f"  x {p}")
    sys.exit("\nABORTED -- nothing written.")

os.makedirs(os.path.dirname(PANEL_DST), exist_ok=True)
if os.path.exists(PANEL_DST):
    shutil.copy2(PANEL_DST, PANEL_DST + ".bak_accounts")
shutil.copy2(PANEL_SRC, PANEL_DST)
for path, (lines, edits, bom) in plans.items():
    for s, e, new in sorted(edits, key=lambda x: -x[0]):
        lines[s:e + 1] = new
    shutil.copy2(path, path + ".bak_accounts")
    io.open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write("\n".join(lines))
try:
    for p in list(plans) + [PANEL_DST]:
        py_compile.compile(p, doraise=True)
except py_compile.PyCompileError as e:
    for p in plans:
        shutil.copy2(p + ".bak_accounts", p)
    os.remove(PANEL_DST)
    sys.exit(f"  x COMPILE FAILED -- all restored\n{e}")
print(f"\n  ok -- panel installed at {os.path.relpath(PANEL_DST, ROOT)}")
print("  both windows patched and compile (backups: *.bak_accounts)")
print("\nOpen any record in Observatum: record on the left, accounts on the right.")

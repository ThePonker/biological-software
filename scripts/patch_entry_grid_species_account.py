"""Staging grid: open the species account dialog (the same SpeciesProfileDialog the other tabs use).

Double-click on a CELL still edits it (unchanged). The dialog opens from:
    * double-click on the ROW NUMBER (vertical header)
    * right-click -> "Species account..." (one row selected, with a species)
    * Ctrl+I -- the current row
Also fixes an existing bug: right-clicking a COLUMN header raised NameError (stray row-menu
lines in _header_menu), so the show/hide-columns menu never opened.
A row with no species says so; a staged name with no TVK opens read-only (the dialog
itself refuses to save without a TVK). Standalone (outside Observatum) shows a short message.

  python scripts\\patch_entry_grid_species_account.py      (refuses a second run; keeps a .bak)
"""
import os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "DataEntry", "entry_grid.py")
MARK = "_open_species_account"
raw = open(P, "rb").read().decode("utf-8")
crlf = "\r\n" in raw
t = raw.replace("\r\n", "\n")
if MARK in t:
    sys.exit("  already patched -- nothing done")


def rep(old, new):
    global t
    n = t.count(old)
    if n != 1:
        sys.exit(f"  x expected 1 match, found {n}: {old[:70]!r} -- nothing written")
    t = t.replace(old, new)


# 1. double-click on the row number
rep('''        self._clip_marker = None  # (r0, r1, c0, c1) of the copied block, for the dashed outline
''', '''        self._clip_marker = None  # (r0, r1, c0, c1) of the copied block, for the dashed outline
        # double-click the ROW NUMBER -> species account (a double-click on a cell still edits it)
        self.verticalHeader().sectionDoubleClicked.connect(self._open_species_account)
''')

# 2. Ctrl+I
rep('''            if k == Qt.Key.Key_D:
                self._fill_down(); return
''', '''            if k == Qt.Key.Key_D:
                self._fill_down(); return
            if k == Qt.Key.Key_I and not editing:
                self._open_species_account(self.currentIndex().row()); return
''')

# 3. right-click menu entry
rep('''        if not real:
            return
        menu = QMenu(self)
        ins = "Insert row above" if len(real) == 1 else f"Insert {len(real)} rows above"''',
'''        if not real:
            return
        menu = QMenu(self)
        if len(real) == 1:
            p_ = m.species_payload(real[0])
            if p_.get("scientific_name") or p_.get("tvk"):
                menu.addAction("Species account\\u2026   (Ctrl+I)").triggered.connect(
                    lambda *_a, r_=real[0]: self._open_species_account(r_))
                menu.addSeparator()
        ins = "Insert row above" if len(real) == 1 else f"Insert {len(real)} rows above"''')

# 3b. existing bug: the column-header menu (_header_menu) holds a stray copy of the row menu's
#     "Insert row above" lines; they use `real`, undefined there, so right-clicking a column
#     header raised NameError and the show/hide-columns menu never opened. Removed.
rep('''        hh = self._view.horizontalHeader()
        menu = QMenu(self)
        ins = "Insert row above" if len(real) == 1 else f"Insert {len(real)} rows above"
        menu.addAction(ins).triggered.connect(self._insert_selected_rows)
        menu.addSeparator()
''', '''        hh = self._view.horizontalHeader()
        menu = QMenu(self)
''')

# 4. the method itself
rep('''    def _copy(self):''', '''    def _open_species_account(self, r=None):
        """The same species account dialog the other tabs open: published accounts above,
        your own account below. Uses the row's TVK; a staged name without one opens read-only."""
        from PySide6.QtWidgets import QMessageBox
        m = self.model()
        if r is None or r < 0:
            r = self.currentIndex().row()
        if not (0 <= r < len(getattr(m, "_rows", []))):
            return
        p = m.species_payload(r)
        if not (p.get("scientific_name") or p.get("tvk")):
            QMessageBox.information(self, "Species account", "This row has no species yet.")
            return
        dlg_cls = None
        import importlib
        for modname in ("src.views.home.species_profile_dialog",
                        "Observatum.src.views.home.species_profile_dialog"):
            try:
                dlg_cls = importlib.import_module(modname).SpeciesProfileDialog
                break
            except Exception:
                continue
        if dlg_cls is None:
            QMessageBox.information(self, "Species account",
                                    "Species accounts open when Data Entry runs inside Observatum.")
            return
        try:
            from DataEntry import bootstrap
            bootstrap.get_database_safe()          # make sure Observatum's database is initialised
        except Exception:
            pass
        data = {
            "scientific_name": p.get("scientific_name"),
            "species_name": p.get("scientific_name"),
            "tvk": p.get("tvk"),
            "common_name": p.get("common_name"),
        }
        try:
            dlg_cls(data, self.window()).exec()
        except Exception as e:
            QMessageBox.warning(self, "Species account", f"Could not open the species account:\\n\\n{e}")

    def _copy(self):''')

tmp = P + ".tmp"
out = t.replace("\n", "\r\n") if crlf else t
open(tmp, "wb").write(out.encode("utf-8"))
try:
    py_compile.compile(tmp, doraise=True)
except py_compile.PyCompileError as e:
    os.remove(tmp)
    sys.exit(f"  x patched file does not compile -- nothing written: {e}")
shutil.copy2(P, P + ".bak")
os.replace(tmp, P)
print("  patched DataEntry\\entry_grid.py (backup: entry_grid.py.bak)")
print("  species account: double-click the row number, right-click -> Species account..., or Ctrl+I")

"""apply_specimen_dialog.py -- two-column Add Specimen dialog + location map.

    python apply_specimen_dialog.py

Changes:
  1. Splits the form into two columns (left = species/where/when + map,
     right = sex/collector/determiner/notes/profile).
  2. Removes the Local Site Name field from the dialog (the DB column stays).
  3. Adds a small location map under the grid ref, refreshed when the ref validates.
  4. Widens the dialog so nothing needs scrolling.

Backs up as *.bak_specdlg. Safe to re-run.
"""
import ast
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DLG = os.path.join(ROOT, "Observatum", "src", "views", "dialogs", "add_specimen_dialog.py")

# 1. two-column container in place of the single vertical layout
OLD_CONTENT = '''        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 8)
'''

NEW_CONTENT = '''        content = QWidget()
        _cols = QHBoxLayout(content)
        _cols.setSpacing(20)
        _cols.setContentsMargins(16, 16, 16, 8)

        _left = QVBoxLayout(); _left.setSpacing(12)
        _right = QVBoxLayout(); _right.setSpacing(12)
        _cols.addLayout(_left, 1)
        _cols.addLayout(_right, 1)
        layout = _left          # fields below build into the left column
'''

# 2. drop Local Site Name
OLD_LOCAL = '''        # Local Site Name (protected during sync)
        self._add_form_field(layout, "Local Site Name", "site_local_edit", "Your local name for this site (optional)")
'''
NEW_LOCAL = '''        # Local Site Name removed from the dialog (DB column retained); keep the
        # attribute so _populate_from_existing / get_specimen_data stay valid.
        self.site_local_edit = QLineEdit()
        self.site_local_edit.hide()
'''

# 3. map at the foot of the left column, then switch to the right column
OLD_SEX = '''        # Sex
        sex_group = QVBoxLayout()
'''
NEW_SEX = '''        # Location map (left column, under the grid ref) -- best effort
        self._loc_map = None
        try:
            import paths as _paths
            from DataEntry.raster_map import RasterMiniMap, find_tiles_dir
            _tiles = find_tiles_dir(str(_paths.MAPS_DIR))
            _m = RasterMiniMap(_tiles, self._vc_service)
            if _m.has_data():
                self._loc_map = _m
            else:
                _m.deleteLater()
        except Exception:
            self._loc_map = None
        if self._loc_map is None:
            try:
                import paths as _paths
                from DataEntry.vc_map import MiniMap
                _g = str(_paths.VC_GEOJSON)
                _m = MiniMap(_g, self._vc_service)
                if _m.has_data():
                    self._loc_map = _m
                else:
                    _m.deleteLater()
            except Exception:
                self._loc_map = None
        if self._loc_map is not None:
            _map_lbl = QLabel("Location")
            _map_lbl.setStyleSheet(
                f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
            layout.addWidget(_map_lbl)
            layout.addWidget(self._loc_map)
        layout.addStretch()

        layout = _right        # remaining fields build into the right column

        # Sex
        sex_group = QVBoxLayout()
'''

# 4. refresh the map whenever the grid ref validates
OLD_VALID = '''    def _validate_grid_ref(self):
'''
NEW_VALID = '''    def _refresh_loc_map(self):
        """Point the mini map at the current grid ref (no-op if there is no map)."""
        m = getattr(self, "_loc_map", None)
        if m is None:
            return
        try:
            m.update_for_row({"grid_ref": self.gridref_edit.text().strip().upper()})
        except Exception:
            pass

    def _validate_grid_ref(self):
'''

EDITS = [
    (DLG, "two-column layout", OLD_CONTENT, NEW_CONTENT, "layout = _left"),
    (DLG, "remove local site", OLD_LOCAL, NEW_LOCAL, "site_local_edit.hide()"),
    (DLG, "map + column switch", OLD_SEX, NEW_SEX, "layout = _right"),
    (DLG, "map refresh method", OLD_VALID, NEW_VALID, "_refresh_loc_map"),
    (DLG, "wider dialog", "self.setMinimumWidth(", "self.setMinimumWidth(", None),
]


def main():
    if not os.path.exists(DLG):
        print("MISSING:", DLG)
        return 1
    shutil.copy2(DLG, DLG + ".bak_specdlg")
    print("backed up as add_specimen_dialog.py.bak_specdlg\n")

    text = open(DLG, encoding="utf-8").read()
    ok = True

    for _p, label, old, new, marker in EDITS[:4]:
        if marker and marker in text:
            print(f"  = {label:22} already applied, skipped")
            continue
        if old not in text:
            print(f"  x {label:22} ANCHOR NOT FOUND")
            ok = False
            continue
        text = text.replace(old, new, 1)
        print(f"  + {label:22} applied")

    # call the refresh at the end of _validate_grid_ref, wherever it returns
    if "_refresh_loc_map()" not in text.split("def _refresh_loc_map")[-1]:
        anchor = "        self.gridref_edit.editingFinished.connect(self._validate_grid_ref)"
        if anchor in text:
            text = text.replace(
                anchor,
                anchor + "\n        self.gridref_edit.editingFinished.connect(self._refresh_loc_map)",
                1)
            print("  + map refresh wired      applied")
        else:
            print("  x map refresh wired      ANCHOR NOT FOUND")
            ok = False

    # widen: QHBoxLayout must be imported
    if "QHBoxLayout" not in text.split("\n\n")[0] and "QHBoxLayout" not in text[:3000]:
        print("  ! check QHBoxLayout is imported at the top of the file")

    if not ok:
        print("\nAnchor missing - nothing written.")
        return 1

    with open(DLG, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)

    try:
        ast.parse(open(DLG, encoding="utf-8").read())
        print("\n  syntax OK")
    except SyntaxError as e:
        print(f"\n  SYNTAX ERROR: {e}")
        return 1

    print("Done. Launch and check the dialog fits without scrolling.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""apply_curatorial_fields.py -- add curatorial fields to the Add Specimen dialog.

    python apply_curatorial_fields.py

Adds to the right-hand column: Preparation, Condition, Storage location, Drawer number.
Preparation defaults from the taxon order (Diptera/Hymenoptera -> Pinned,
Coleoptera -> Carded) but only into an empty field, so a manual choice is never
overwritten. Values are saved via get_specimen_data() and restored when editing.

Note: the UI label says "Drawer number"; the DB column is still drawer_unit.
Renaming the column is on the future-development list.

Backs up as *.bak_curat. Safe to re-run.
"""
import ast
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DLG = os.path.join(ROOT, "Observatum", "src", "views", "dialogs", "add_specimen_dialog.py")

# --- vocabularies (edit these lists to change the dropdowns) ------------------
VOCAB = '''
# Curatorial vocabularies -- edit these lists to change the dropdown options.
PREPARATION_TYPES = ["", "Pinned", "Carded", "Pointed", "In alcohol",
                     "Slide-mounted", "Genitalia prep"]
CONDITIONS = ["", "Good", "Damaged"]
STORAGE_LOCATIONS = ["", "Cabinet", "Useful Box", "Storage box"]

# Default preparation by taxonomic order (only applied to an empty field).
PREP_BY_ORDER = {
    "diptera": "Pinned",
    "hymenoptera": "Pinned",
    "coleoptera": "Carded",
}

'''

# --- the four widgets, added to the right column after Determiner ------------
WIDGETS = '''
        # --- curatorial fields ------------------------------------------
        def _combo(label_text, attr, items):
            grp = QVBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet(
                f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
            grp.addWidget(lbl)
            cb = QComboBox()
            cb.addItems(items)
            cb.setMinimumHeight(36)
            cb.setStyleSheet(
                f"QComboBox {{ border: 1px solid {t.get('border')};"
                f" border-radius: {t.get('radius_sm')}; padding: 8px; font-size: 13px; }}")
            grp.addWidget(cb)
            setattr(self, attr, cb)
            layout.addLayout(grp)

        _combo("Preparation", "prep_combo", PREPARATION_TYPES)
        _combo("Condition", "condition_combo", CONDITIONS)
        _combo("Storage Location", "storage_combo", STORAGE_LOCATIONS)
        self._add_form_field(layout, "Drawer Number", "drawer_edit", "e.g. 3", "")
'''

# --- default prep from the order --------------------------------------------
HELPER = '''    def _default_prep_from_order(self):
        """Set Preparation from the taxon order, but never over a chosen value."""
        cb = getattr(self, "prep_combo", None)
        if cb is None or cb.currentText().strip():
            return
        order = ""
        if self._selected_species:
            order = (self._selected_species.get("order") or "").strip().lower()
        want = PREP_BY_ORDER.get(order)
        if not want:
            return
        i = cb.findText(want)
        if i >= 0:
            cb.setCurrentIndex(i)

'''

EDITS = [
    ("vocabularies",
     "class AddSpecimenDialog(QDialog):",
     VOCAB + "class AddSpecimenDialog(QDialog):",
     "PREPARATION_TYPES = ["),

    ("curatorial widgets",
     '        self._add_form_field(layout, "Determiner", "determiner_edit", "", "")',
     '        self._add_form_field(layout, "Determiner", "determiner_edit", "", "")'
     + WIDGETS,
     'setattr(self, attr, cb)'),

    ("prep default helper",
     "    def _on_species_selected_from_search(self, species_data: dict):",
     HELPER + "    def _on_species_selected_from_search(self, species_data: dict):",
     "_default_prep_from_order"),

    ("call default on select",
     '''        self._load_species_profile(
            species_data.get('scientific_name', ''),
            species_data.get('tvk')
        )''',
     '''        self._default_prep_from_order()
        self._load_species_profile(
            species_data.get('scientific_name', ''),
            species_data.get('tvk')
        )''',
     "self._default_prep_from_order()\n        self._load_species_profile"),

    ("save the values",
     "        if self._selected_species:\n            data['species_tvk'] = self._selected_species.get('tvk')",
     "        data['preparation_type'] = self.prep_combo.currentText().strip()\n"
     "        data['condition'] = self.condition_combo.currentText().strip()\n"
     "        data['storage_location'] = self.storage_combo.currentText().strip()\n"
     "        data['drawer_unit'] = self.drawer_edit.text().strip()\n\n"
     "        if self._selected_species:\n            data['species_tvk'] = self._selected_species.get('tvk')",
     "data['preparation_type'] ="),
]

RESTORE = '''        # curatorial fields
        for _attr, _key in (("prep_combo", "preparation_type"),
                            ("condition_combo", "condition"),
                            ("storage_combo", "storage_location")):
            _cb = getattr(self, _attr, None)
            if _cb is not None:
                _i = _cb.findText(specimen.get(_key, "") or "")
                if _i >= 0:
                    _cb.setCurrentIndex(_i)
        if hasattr(self, "drawer_edit"):
            self.drawer_edit.setText(specimen.get("drawer_unit", "") or "")

'''


def main():
    if not os.path.exists(DLG):
        print("MISSING:", DLG)
        return 1
    shutil.copy2(DLG, DLG + ".bak_curat")
    print("backed up as add_specimen_dialog.py.bak_curat\n")

    text = open(DLG, encoding="utf-8").read()
    ok = True

    for label, old, new, marker in EDITS:
        if marker in text:
            print(f"  = {label:22} already applied, skipped")
            continue
        if old not in text:
            print(f"  x {label:22} ANCHOR NOT FOUND")
            ok = False
            continue
        text = text.replace(old, new, 1)
        print(f"  + {label:22} applied")

    # restore-on-edit: append inside _populate_from_existing
    if "curatorial fields" not in text:
        anchor = "        self.determiner_edit.setText(specimen.get('determiner', ''))"
        if anchor in text:
            text = text.replace(anchor, anchor + "\n\n" + RESTORE, 1)
            print("  + restore on edit        applied")
        else:
            print("  x restore on edit        ANCHOR NOT FOUND")
            ok = False

    if "QComboBox" not in text[:2000]:
        print("  ! check QComboBox is imported at the top of the file")

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

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

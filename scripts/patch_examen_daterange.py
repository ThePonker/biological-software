"""patch_examen_daterange.py -- date-range control on the Site Analysis toolbar.

    python scripts/patch_examen_daterange.py

Apply AFTER dropping in the new Examen/examen_data.py (v4), which adds the
date_from / date_to parameters this reads.

Why
---
A project may span several survey years. Bicester Graven Hill runs 2023-06 to
2025-07 and pools into one 519-species list, so every figure is computed over a
sample that was never published -- the 2023 report gives 389 species / 27 key,
the 2025 report 433 / 34.

Without scoping, Examen cannot be checked against either.

What this adds
--------------
A "Dates" checkbox and two date fields on the toolbar. Unticked, behaviour is
exactly as now. Ticked, every query is restricted to the window, including the
project table's own species and visit counts.

Bounds default to the full range present in the data.

Line-based patching. Safe to re-run. Backs up as site_analysis_view.py.bak_fix1.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "Examen", "site_analysis_view.py")
BACKUP = TARGET + ".bak_fix1"

OLD_IMPORT = "from .examen_data import load_all_projects, load_project_detail, AnalysisMode"
NEW_IMPORT = ("from .examen_data import (load_all_projects, load_project_detail,\n"
              "                          date_range_available, AnalysisMode)")

OLD_QT = "from PySide6.QtCore import Qt"
NEW_QT = "from PySide6.QtCore import Qt, QDate"

OLD_WIDGETS = "    QTabWidget, QFileDialog, QMessageBox, QInputDialog,"
NEW_WIDGETS = ("    QTabWidget, QFileDialog, QMessageBox, QInputDialog,\n"
               "    QCheckBox, QDateEdit,")

OLD_INIT = "        self._current_site_name = \"\""
NEW_INIT = ("        self._current_site_name = \"\"\n"
            "        self._date_from = None      # ISO 'YYYY-MM-DD' or None\n"
            "        self._date_to = None")

# Toolbar: insert the date controls before the Import button.
OLD_TOOLBAR = "        import_btn = QPushButton(\"Import List...\"); import_btn.setStyleSheet(BTN_ACCENT)"
NEW_TOOLBAR = '''        # Date scoping -- a project may span several survey years, and pooling
        # them produces a species list that was never published.
        self.date_chk = QCheckBox("Dates")
        self.date_chk.setToolTip("Restrict to a survey window.\\n"
                                 "Unticked, all records for the project are pooled.")
        self.date_chk.toggled.connect(self._on_dates_toggled)
        toolbar.addWidget(self.date_chk)

        lo, hi = date_range_available()
        self.date_from = QDateEdit(); self.date_to = QDateEdit()
        for w, iso, fallback in ((self.date_from, lo, "2000-01-01"),
                                 (self.date_to, hi, "2030-12-31")):
            w.setCalendarPopup(True)
            w.setDisplayFormat("dd MMM yyyy")
            w.setDate(QDate.fromString(iso or fallback, "yyyy-MM-dd"))
            w.setEnabled(False)
            w.dateChanged.connect(self._on_dates_changed)
            w.setStyleSheet("QDateEdit { padding: 3px 6px; border: 1px solid "
                            + BORDER + "; border-radius: 3px; font-size: 11px; }")
        toolbar.addWidget(self.date_from)
        toolbar.addWidget(QLabel("to"))
        toolbar.addWidget(self.date_to)

        import_btn = QPushButton("Import List..."); import_btn.setStyleSheet(BTN_ACCENT)'''

OLD_SETMODE = '''    def set_mode(self, mode):
        self._mode = mode; self._load_projects()'''
NEW_SETMODE = '''    def set_mode(self, mode):
        self._mode = mode; self._load_projects()

    # ── Date scoping ─────────────────────────────────────────────
    def _on_dates_toggled(self, on):
        self.date_from.setEnabled(on)
        self.date_to.setEnabled(on)
        self._on_dates_changed()

    def _on_dates_changed(self, *_):
        if self.date_chk.isChecked():
            self._date_from = self.date_from.date().toString("yyyy-MM-dd")
            self._date_to = self.date_to.date().toString("yyyy-MM-dd")
        else:
            self._date_from = self._date_to = None
        self._load_projects()'''

OLD_LOAD = "        self._projects = load_all_projects(self._mode); self.table.setRowCount(len(self._projects))"
NEW_LOAD = ("        self._projects = load_all_projects(self._mode, self._date_from, self._date_to)\n"
            "        self.table.setRowCount(len(self._projects))")

OLD_DETAIL = "        detail = load_project_detail(proj.project_name, proj.client, self._mode)"
NEW_DETAIL = ("        detail = load_project_detail(proj.project_name, proj.client, self._mode,\n"
              "                                     self._date_from, self._date_to)")

OLD_SUMMARY = ('        self.summary_label.setText(f"{len(self._projects)} projects  |  '
               '{sum(p.species_count for p in self._projects)} species  |  Mode: {mode_t}")')
NEW_SUMMARY = ('        scope = (f"  |  {self._date_from} to {self._date_to}"\n'
               '                 if self._date_from else "  |  all dates")\n'
               '        self.summary_label.setText(f"{len(self._projects)} projects  |  "\n'
               '                                   f"{sum(p.species_count for p in self._projects)} species  |  "\n'
               '                                   f"Mode: {mode_t}{scope}")')

EDITS = [
    ("examen_data import", OLD_IMPORT, NEW_IMPORT),
    ("QDate import", OLD_QT, NEW_QT),
    ("widget imports", OLD_WIDGETS, NEW_WIDGETS),
    ("state fields", OLD_INIT, NEW_INIT),
    ("toolbar controls", OLD_TOOLBAR, NEW_TOOLBAR),
    ("date handlers", OLD_SETMODE, NEW_SETMODE),
    ("load_all_projects call", OLD_LOAD, NEW_LOAD),
    ("load_project_detail call", OLD_DETAIL, NEW_DETAIL),
    ("summary line", OLD_SUMMARY, NEW_SUMMARY),
]


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching Examen/site_analysis_view.py -- date range control")
    print("=" * 70)

    if "date_range_available" in text:
        print("  = already patched -- nothing to do")
        return 0

    failed = 0
    for desc, old, new in EDITS:
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  + {desc}")
        else:
            print(f"  x {desc}  ({n} matches, expected 1)")
            failed += 1

    print("")
    if failed:
        print(f"  {failed} edit(s) failed -- NOTHING WRITTEN.")
        return 1

    shutil.copy2(TARGET, BACKUP)
    print(f"  backup written: {os.path.basename(BACKUP)}")
    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(text)

    print("")
    print("  Checking the file compiles...")
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        print("  + compiles cleanly")
    except Exception as e:  # noqa: BLE001
        print(f"  x COMPILE FAILED: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} site_analysis_view.py")
        return 1

    print("")
    print("  NEXT: python -m Examen")
    print("  Tick Dates, set 01 Jan 2025 to 31 Dec 2025, select Bicester.")
    print("  The 2025 report gives 433 species and 34 key species.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())

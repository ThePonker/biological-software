"""patch_examen_surveyyear.py -- group the project table by survey year.

    python scripts/patch_examen_surveyyear.py

Apply AFTER dropping in Examen/examen_data.py v5.

Supersedes patch_examen_daterange.py. If that was applied, this reverts its
toolbar controls and replaces them -- run it either way.

Why
---
A project may hold several surveys. Bicester Graven Hill is 2023 (367 species,
synced to iRecord) and 2025 (254 species, embargoed) under one name; pooled they
make a 519-species list that corresponds to no report.

A date range expresses that, but clumsily -- you have to know which years exist
and type the bounds each time. The natural unit is the survey, and the data
already carries it.

What changes
------------
  * The project table gains a Year column and shows one row per project per
    survey year, newest first.
  * A "Pool years" checkbox switches the whole table to one row per project,
    all years combined -- the previous behaviour, now an explicit choice.
    Mixing pooled and per-year rows in one table was rejected: it invites the
    confusion this is meant to remove.
  * The detail header names the survey ("Bicester Graven Hill - 2025 - Watermans").
  * The date fields are removed.

Line-based edits, each anchored on a single unique line where possible.
The summary-line edit accepts either the original or the post-revert form:
a patch that reverts an earlier patch must anchor on what the revert left,
not on the original text.
Safe to re-run. Backs up as site_analysis_view.py.bak_fix2.
"""
import os
import re
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "Examen", "site_analysis_view.py")
BACKUP = TARGET + ".bak_fix2"


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching Examen/site_analysis_view.py -- survey-year grouping")
    print("=" * 70)

    if "_pool_years" in text:
        print("  = already patched -- nothing to do")
        return 0

    failed = []

    def sub(label, old, new, count=1):
        nonlocal text
        n = text.count(old)
        if n == count:
            text = text.replace(old, new)
            print(f"  + {label}")
        else:
            print(f"  x {label}  ({n} matches, expected {count})")
            failed.append(label)

    # ---- 1. Remove the v4 date-range controls if present -------------
    if "date_range_available" in text:
        print("  . reverting the date-range controls")
        text = re.sub(
            r"        # Date scoping.*?toolbar\.addWidget\(self\.date_to\)\n\n",
            "", text, flags=re.S)
        text = re.sub(r"    # ── Date scoping ─.*?self\._load_projects\(\)\n\n",
                      "", text, flags=re.S)
        text = text.replace(
            "from .examen_data import (load_all_projects, load_project_detail,\n"
            "                          date_range_available, AnalysisMode)",
            "from .examen_data import load_all_projects, load_project_detail, AnalysisMode")
        text = text.replace(
            "        self._date_from = None      # ISO 'YYYY-MM-DD' or None\n"
            "        self._date_to = None\n", "")
        text = text.replace(
            "        self._projects = load_all_projects(self._mode, self._date_from, self._date_to)\n"
            "        self.table.setRowCount(len(self._projects))",
            "        self._projects = load_all_projects(self._mode)\n"
            "        self.table.setRowCount(len(self._projects))")
        text = text.replace(
            "        detail = load_project_detail(proj.project_name, proj.client, self._mode,\n"
            "                                     self._date_from, self._date_to)",
            "        detail = load_project_detail(proj.project_name, proj.client, self._mode)")
        text = re.sub(r'        scope = \(f"  \|  \{self\._date_from\}.*?f"Mode: \{mode_t\}\{scope\}"\)',
                      '        self.summary_label.setText(f"{len(self._projects)} projects  |  "\n'
                      '                                   f"{sum(p.species_count for p in self._projects)} species  |  "\n'
                      '                                   f"Mode: {mode_t}")', text, flags=re.S)
        text = text.replace("from PySide6.QtCore import Qt, QDate",
                            "from PySide6.QtCore import Qt")
        text = text.replace("    QCheckBox, QDateEdit,\n", "")

    # ---- 2. Imports --------------------------------------------------
    sub("widget imports",
        "    QTabWidget, QFileDialog, QMessageBox, QInputDialog,",
        "    QTabWidget, QFileDialog, QMessageBox, QInputDialog, QCheckBox,")

    # ---- 3. State ----------------------------------------------------
    sub("state field",
        '        self._current_site_name = ""',
        '        self._current_site_name = ""\n'
        '        self._pool_years = False    # False = one row per survey year')

    # ---- 4. Toolbar --------------------------------------------------
    sub("pool-years checkbox",
        '        import_btn = QPushButton("Import List..."); import_btn.setStyleSheet(BTN_ACCENT)',
        '''        # A project may hold several surveys. One row per survey year is the
        # default because that is what a report covers; pooling is a choice.
        self.pool_chk = QCheckBox("Pool years")
        self.pool_chk.setToolTip(
            "Off: one row per survey year -- what a report covers.\\n"
            "On:  all years of a project combined into one list.")
        self.pool_chk.toggled.connect(self._on_pool_toggled)
        toolbar.addWidget(self.pool_chk)

        import_btn = QPushButton("Import List..."); import_btn.setStyleSheet(BTN_ACCENT)''')

    # ---- 5. Handler --------------------------------------------------
    sub("pool handler",
        '''    def set_mode(self, mode):
        self._mode = mode; self._load_projects()''',
        '''    def set_mode(self, mode):
        self._mode = mode; self._load_projects()

    def _on_pool_toggled(self, on):
        self._pool_years = on
        self._load_projects()''')

    # ---- 6. Table columns -------------------------------------------
    sub("column count",
        '        self.table = QTableWidget(); self.table.setColumnCount(9)',
        '        self.table = QTableWidget(); self.table.setColumnCount(10)')
    sub("column headers",
        '        self.table.setHorizontalHeaderLabels(["Project", "Client", "Sites", '
        '"Visits", "Species", "Key spp", "% Key", "SQI", "Dates"])',
        '        self.table.setHorizontalHeaderLabels(["Project", "Year", "Client", "Sites", '
        '"Visits", "Species", "Key spp", "% Key", "SQI", "Dates"])')

    # ---- 7. Loading --------------------------------------------------
    sub("load call",
        "        self._projects = load_all_projects(self._mode)",
        "        self._projects = load_all_projects(self._mode,\n"
        "                                           by_year=not self._pool_years)")

    # ---- 8. Row population (columns shift right by one) --------------
    sub("row fill",
        '''            self.table.setItem(i, 0, QTableWidgetItem(p.project_name))
            self.table.setItem(i, 1, QTableWidgetItem(p.client))
            st = QTableWidgetItem(str(p.site_count)); st.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            st.setToolTip(", ".join(p.site_names) if p.site_names else ""); self.table.setItem(i, 2, st)
            for col, val in [(3, p.visit_count), (4, p.species_count), (5, p.key_species_count)]:
                it = QTableWidgetItem(str(val)); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 5 and val > 0: it.setForeground(QColor(RED_STATUS))
                self.table.setItem(i, col, it)
            pct = QTableWidgetItem(f"{p.key_species_pct}%"); pct.setTextAlignment(Qt.AlignmentFlag.AlignCenter); self.table.setItem(i, 6, pct)''',
        '''            self.table.setItem(i, 0, QTableWidgetItem(p.project_name))
            yr = QTableWidgetItem(p.survey_year or "all")
            yr.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if not p.survey_year:
                yr.setForeground(QColor(TEXT_MUTED))
            self.table.setItem(i, 1, yr)
            self.table.setItem(i, 2, QTableWidgetItem(p.client))
            st = QTableWidgetItem(str(p.site_count)); st.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            st.setToolTip(", ".join(p.site_names) if p.site_names else ""); self.table.setItem(i, 3, st)
            for col, val in [(4, p.visit_count), (5, p.species_count), (6, p.key_species_count)]:
                it = QTableWidgetItem(str(val)); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 6 and val > 0: it.setForeground(QColor(RED_STATUS))
                self.table.setItem(i, col, it)
            pct = QTableWidgetItem(f"{p.key_species_pct}%"); pct.setTextAlignment(Qt.AlignmentFlag.AlignCenter); self.table.setItem(i, 7, pct)''')

    sub("sqi + dates columns",
        '''            si = QTableWidgetItem(sq); si.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if p.sqi >= 150: si.setForeground(QColor(MOSS_GREEN))
            elif p.sqi >= 125: si.setForeground(QColor(AMBER))
            self.table.setItem(i, 7, si)
            self.table.setItem(i, 8, QTableWidgetItem(f"{p.first_date} \\u2013 {p.last_date}" if p.first_date else ""))''',
        '''            si = QTableWidgetItem(sq); si.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if p.sqi >= 150: si.setForeground(QColor(MOSS_GREEN))
            elif p.sqi >= 125: si.setForeground(QColor(AMBER))
            self.table.setItem(i, 8, si)
            self.table.setItem(i, 9, QTableWidgetItem(f"{p.first_date} \\u2013 {p.last_date}" if p.first_date else ""))''')

    # ---- 9. Detail load scoped to the row's year ---------------------
    sub("detail call",
        "        detail = load_project_detail(proj.project_name, proj.client, self._mode)",
        "        detail = load_project_detail(proj.project_name, proj.client, self._mode,\n"
        "                                     survey_year=proj.survey_year or None)")
    sub("detail header",
        '        self._run_analysis(tvks, names, f"{proj.project_name} \\u2014 {proj.client}{sites_info}", detail.site.visit_count)',
        '        title = (f"{proj.display_name} \\u2014 {proj.client}{sites_info}"\n'
        '                 if proj.survey_year else\n'
        '                 f"{proj.project_name} \\u2014 {proj.client}{sites_info} (all years pooled)")\n'
        '        self._run_analysis(tvks, names, title, detail.site.visit_count)')
    sub("current site name",
        "        self._current_detail = detail; self._current_site_name = proj.project_name",
        "        self._current_detail = detail\n"
        "        self._current_site_name = proj.display_name")

    # ---- 10. Summary line -------------------------------------------
    # The revert step above rewrites this line, so the original anchor no
    # longer exists once it has run. Accept either form.
    _new_summary = (
        '        grouping = "pooled across years" if self._pool_years else "by survey year"\n'
        '        self.summary_label.setText(f"{len(self._projects)} rows ({grouping})  |  "\n'
        '                                   f"Mode: {mode_t}")')
    _summary_original = (
        '        self.summary_label.setText(f"{len(self._projects)} projects  |  '
        '{sum(p.species_count for p in self._projects)} species  |  Mode: {mode_t}")')
    _summary_reverted = (
        '        self.summary_label.setText(f"{len(self._projects)} projects  |  "\n'
        '                                   f"{sum(p.species_count for p in self._projects)} species  |  "\n'
        '                                   f"Mode: {mode_t}")')
    if text.count(_summary_reverted) == 1:
        sub("summary line (post-revert form)", _summary_reverted, _new_summary)
    else:
        sub("summary line", _summary_original, _new_summary)

    # ---- 11. CSV export gains the year -------------------------------
    sub("csv header",
        '            w.writerow(["Project","Client","Sites","Visits","Species","Key Species","% Key","SQI","Reliable","Rare","Scarce","Priority","First","Last"])',
        '            w.writerow(["Project","Year","Client","Sites","Visits","Species","Key Species","% Key","SQI","Reliable","Rare","Scarce","Priority","First","Last"])')
    sub("csv row",
        '                w.writerow([s.project_name, s.client, s.site_count, s.visit_count, s.species_count,',
        '                w.writerow([s.project_name, s.survey_year or "all", s.client, s.site_count, s.visit_count, s.species_count,')

    print("")
    if failed:
        print(f"  {len(failed)} edit(s) failed -- NOTHING WRITTEN.")
        for f_ in failed:
            print(f"    {f_}")
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
    print("  Bicester Graven Hill should now appear twice -- 2023 and 2025 --")
    print("  with 367 and 254 species. Tick 'Pool years' for the combined 519.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())

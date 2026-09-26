"""patch_workbook_button.py -- Export Workbook button on the Site Analysis toolbar.

    python scripts/patch_workbook_button.py

The exporter (Examen/workbook_export.py) is validated but reachable only from a
script. This makes it a button beside Export Appendix.

Appendix vs Workbook
--------------------
Both stay. They answer different needs:

    Export Appendix    one sheet, the species list -- what goes to a client's
                       ecologist who wants to check the identifications
    Export Workbook    seven sheets, the whole assessment with its stamp -- what
                       the report is written from

The workbook needs the ProjectRecord as well as the detail, because the stamp
carries the survey year, client and site list. `_on_project_clicked` therefore
keeps a reference, and `_on_import` clears it: an imported list has no project,
so the workbook falls back to what the detail can supply.

Safe to re-run. Backs up as site_analysis_view.py.bak_fix3.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "Examen", "site_analysis_view.py")
BACKUP = TARGET + ".bak_fix3"

OLD_STATE = """        self._current_site_name = ""
        self._pool_years = False    # False = one row per survey year"""

NEW_STATE = """        self._current_site_name = ""
        self._current_project = None    # ProjectRecord; None for an imported list
        self._pool_years = False    # False = one row per survey year"""

OLD_BUTTONS = """        self.appendix_btn = QPushButton("Export Appendix"); self.appendix_btn.setStyleSheet(BTN_OUTLINE)
        self.appendix_btn.clicked.connect(self._on_export_appendix); self.appendix_btn.setEnabled(False); toolbar.addWidget(self.appendix_btn)"""

NEW_BUTTONS = """        self.appendix_btn = QPushButton("Export Appendix"); self.appendix_btn.setStyleSheet(BTN_OUTLINE)
        self.appendix_btn.setToolTip("One sheet: the species list, for checking.")
        self.appendix_btn.clicked.connect(self._on_export_appendix); self.appendix_btn.setEnabled(False); toolbar.addWidget(self.appendix_btn)
        self.workbook_btn = QPushButton("Export Workbook"); self.workbook_btn.setStyleSheet(BTN_PRIMARY)
        self.workbook_btn.setToolTip(
            "Seven sheets: summary, key species, full appendix, habitats,\\n"
            "assemblages, guilds and status definitions — with the stamp\\n"
            "recording what the figures were computed against.")
        self.workbook_btn.clicked.connect(self._on_export_workbook)
        self.workbook_btn.setEnabled(False); toolbar.addWidget(self.workbook_btn)"""

OLD_CLICK = """        self._current_detail = detail
        self._current_site_name = proj.display_name"""

NEW_CLICK = """        self._current_detail = detail
        self._current_project = proj
        self._current_site_name = proj.display_name"""

OLD_IMPORT = """                self._current_detail = None; self._current_site_name = "Imported List\""""

NEW_IMPORT = """                self._current_detail = None; self._current_project = None
                self._current_site_name = "Imported List\""""

OLD_ENABLE = """        self.freeze_btn.setEnabled(True); self.appendix_btn.setEnabled(True)"""

NEW_ENABLE = """        self.freeze_btn.setEnabled(True); self.appendix_btn.setEnabled(True)
        self.workbook_btn.setEnabled(True)"""

OLD_EXPORT = """    def _on_freeze(self):"""

NEW_EXPORT = '''    def _on_export_workbook(self):
        """Write the full assessment workbook.

        Pooled analyses are still exportable -- the stamp says so, rather than
        the export refusing -- because a deliberately pooled site-wide list is a
        legitimate thing to assess, just not the same thing as a survey.
        """
        if not self._current_result:
            return
        from .workbook_export import export_workbook

        proj = self._current_project
        base = (self._current_site_name or "Assessment").replace(" \\u2014 ", " ")
        base = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in base)
        suggested = f"{base.strip()} assessment.xlsx"

        path, _ = QFileDialog.getSaveFileName(
            self, "Export assessment workbook", suggested, "Excel workbook (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        try:
            export_workbook(self._current_result, self._current_detail, proj, path,
                            pooled_years=self._pool_years)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed",
                                f"The workbook could not be written.\\n\\n{e}")
            return
        QMessageBox.information(
            self, "Workbook exported",
            f"Written to:\\n{path}\\n\\nThe Summary sheet records the Codex "
            "version, survey scope and jurisdiction the figures were computed "
            "against.")

    def _on_freeze(self):'''


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching Examen/site_analysis_view.py -- Export Workbook button")
    print("=" * 70)

    if "_on_export_workbook" in text:
        print("  = already patched -- nothing to do")
        return 0

    # QFileDialog and QMessageBox are already imported in this file; confirm.
    for needed in ("QFileDialog", "QMessageBox"):
        if needed not in text.split("class ")[0]:
            print(f"  x {needed} is not imported at the top of the file")
            print("  NOTHING WRITTEN.")
            return 1
    print("  . QFileDialog and QMessageBox already imported")

    failed = 0
    for label, old, new in [
            ("project reference on the view", OLD_STATE, NEW_STATE),
            ("Export Workbook button", OLD_BUTTONS, NEW_BUTTONS),
            ("keep the project on selection", OLD_CLICK, NEW_CLICK),
            ("clear the project on import", OLD_IMPORT, NEW_IMPORT),
            ("enable with the other exports", OLD_ENABLE, NEW_ENABLE),
            ("_on_export_workbook", OLD_EXPORT, NEW_EXPORT)]:
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  + {label}")
        else:
            print(f"  x {label}  ({n} matches, expected 1)")
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
    print("  Select a project; Export Workbook sits beside Export Appendix.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())

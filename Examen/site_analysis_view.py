"""
Examen - Site Analysis View (E5 refactor)

Project table at top, toolbar with mode/actions, tabbed detail area
with 5 sub-tabs: Overview, Habitats, Assemblages, Species, Conservation.
"""

import csv
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QFileDialog, QMessageBox, QCheckBox, QComboBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from .examen_data import (load_all_projects, load_project_detail, AnalysisMode,
                          AUTO_JURISDICTION, country_for_vc, resolve_jurisdiction)
from .overview_tab import OverviewTab
from .habitat_tab import HabitatTab
from .assemblage_tab import AssemblageTab
from .species_tab import SpeciesTab
from .conservation_tab import ConservationTab

BG = "#f5f5f4"; SURFACE = "#ffffff"; TEXT_PRIMARY = "#1f2937"; TEXT_HEADING = "#4b5563"
TEXT_SECONDARY = "#6b7280"; TEXT_MUTED = "#9ca3af"; BORDER = "#d1d5db"; SEPARATOR = "#e5e7eb"
MOSS_GREEN = "#4a7c59"; MOSS_HOVER = "#3d6649"; WARM_GRAY = "#8b8178"
ACCENT = "#7c6c9f"; ACCENT_LIGHT = "#f0edf5"; ACCENT_DARK = "#5a4d78"
RED_STATUS = "#a63d40"; AMBER = "#c2956e"

BTN_PRIMARY = ("QPushButton { background-color: " + MOSS_GREEN + "; color: white; border: none; "
    "padding: 6px 16px; border-radius: 4px; font-size: 12px; } QPushButton:hover { background-color: " + MOSS_HOVER + "; }"
    " QPushButton:disabled { background: #d1d5db; color: #9ca3af; }")
BTN_ACCENT = ("QPushButton { background-color: " + ACCENT + "; color: white; border: none; "
    "padding: 6px 16px; border-radius: 4px; font-size: 12px; } QPushButton:hover { background-color: " + ACCENT_DARK + "; }")
BTN_OUTLINE = ("QPushButton { color: " + MOSS_GREEN + "; border: 1px solid " + MOSS_GREEN + "; "
    "padding: 6px 16px; border-radius: 4px; font-size: 12px; background: none; } QPushButton:hover { background: #e6f0ea; }"
    " QPushButton:disabled { color: #d1d5db; border-color: #d1d5db; }")
TABLE_STYLE = ("QTableWidget { border: 1px solid " + BORDER + "; gridline-color: " + SEPARATOR + "; font-size: 12px; }"
    "QHeaderView::section { background: " + BG + "; border: none; border-bottom: 2px solid " + BORDER + "; "
    "padding: 6px; font-weight: bold; font-size: 11px; color: " + TEXT_HEADING + "; }"
    "QTableWidget::item:selected { background: " + ACCENT_LIGHT + "; color: " + TEXT_PRIMARY + "; }")
TAB_STYLE = (
    "QTabWidget::pane { border: 1px solid " + BORDER + "; border-top: none; background: " + BG + "; }"
    "QTabBar::tab { padding: 6px 16px; font-size: 11px; border: none; "
    "border-bottom: 2px solid transparent; color: " + TEXT_MUTED + "; background: none; }"
    "QTabBar::tab:selected { color: " + ACCENT_DARK + "; border-bottom: 2px solid " + ACCENT + "; font-weight: bold; }"
    "QTabBar::tab:hover:!selected { color: " + TEXT_SECONDARY + "; }")


# ---- project table: display one thing, sort on another --------------------
_PROJ_ROLE = int(Qt.ItemDataRole.UserRole)        # column 0: index into self._projects
_SORT_ROLE = int(Qt.ItemDataRole.UserRole) + 1    # every column: the value to sort on


class _SortItem(QTableWidgetItem):
    """Shows its text; sorts on _SORT_ROLE -- numbers as numbers, dates as ISO."""
    def __lt__(self, other):
        a, b = self.data(_SORT_ROLE), other.data(_SORT_ROLE)
        if a is None or b is None or type(a) is not type(b):
            return super().__lt__(other)
        return a < b


# Dates and mode labels come from one place, shared with the assessment workbook.
from shared.display_format import dmy as _dmy, mode_label  # noqa: E402


class SiteAnalysisView(QWidget):

    def __init__(self, analysis_service):
        super().__init__()
        self._service = analysis_service
        self._projects = []; self._mode = AnalysisMode.CODEX_FULL
        self._current_detail = None; self._current_result = None
        self._current_site_name = ""
        self._current_project = None    # ProjectRecord; None for an imported list
        self._jurisdiction = "England"  # resolved per project; see _resolve_jurisdiction
        self._pool_years = False    # False = one row per survey year
        self._setup_ui(); self._load_projects()

    def set_mode(self, mode):
        self._mode = mode; self._load_projects()

    # ── Jurisdiction ─────────────────────────────────────────────
    # Resolved in examen_data, for the project table and the detail header
    # alike, so the two cannot classify Key species under different rules (EXA2).
    @classmethod
    def _country_for_vc(cls, vc):
        return country_for_vc(vc)

    def _resolve_jurisdiction(self, proj):
        """The jurisdiction to assess under, and how it was arrived at."""
        return resolve_jurisdiction(proj, self.juris_combo.currentText())

    def _on_jurisdiction_changed(self, _text=None):
        # The table's Key species follow the setting; the detail is cleared and
        # the project re-selected to apply it there.
        self._load_projects()

    def _on_pool_toggled(self, on):
        self._pool_years = on
        self._load_projects()

    def _setup_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(8, 8, 8, 8); layout.setSpacing(6)
        toolbar = QHBoxLayout(); toolbar.setSpacing(8)
        title = QLabel("Commercial projects"); title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: " + TEXT_HEADING + ";"); toolbar.addWidget(title); toolbar.addStretch()
        # A project may hold several surveys. One row per survey year is the
        # default because that is what a report covers; pooling is a choice.
        self.pool_chk = QCheckBox("Pool years")
        self.pool_chk.setToolTip(
            "Off: one row per survey year -- what a report covers.\n"
            "On:  all years of a project combined into one list.")
        self.pool_chk.toggled.connect(self._on_pool_toggled)
        toolbar.addWidget(self.pool_chk)

        # Jurisdiction decides which priority listings confer key status. It is
        # a property of the site, so it is derived from the vice-county by
        # default rather than left as a mode that can be forgotten.
        toolbar.addWidget(QLabel("Jurisdiction:"))
        self.juris_combo = QComboBox()
        self.juris_combo.addItems([AUTO_JURISDICTION, "England", "Wales",
                                   "Scotland", "Northern Ireland"])
        self.juris_combo.setToolTip(
            "Which country's rules decide key species.\n"
            "Auto reads the vice-county from the records.\n"
            "Rarity and threat are GB-wide and unaffected.")
        self.juris_combo.currentTextChanged.connect(self._on_jurisdiction_changed)
        self.juris_combo.setStyleSheet(
            "QComboBox { padding: 3px 6px; border: 1px solid " + BORDER +
            "; border-radius: 3px; font-size: 11px; }")
        toolbar.addWidget(self.juris_combo)

        import_btn = QPushButton("Import List..."); import_btn.setStyleSheet(BTN_ACCENT)
        import_btn.clicked.connect(self._on_import); toolbar.addWidget(import_btn)
        refresh_btn = QPushButton("Refresh"); refresh_btn.setStyleSheet(BTN_ACCENT)
        refresh_btn.clicked.connect(self._load_projects); toolbar.addWidget(refresh_btn)
        self.appendix_btn = QPushButton("Export Appendix"); self.appendix_btn.setStyleSheet(BTN_OUTLINE)
        self.appendix_btn.setToolTip("One sheet: the species list, for checking.")
        self.appendix_btn.clicked.connect(self._on_export_appendix); self.appendix_btn.setEnabled(False); toolbar.addWidget(self.appendix_btn)
        self.workbook_btn = QPushButton("Export Workbook"); self.workbook_btn.setStyleSheet(BTN_PRIMARY)
        self.workbook_btn.setToolTip(
            "Seven sheets: summary, key species, full appendix, habitats,\n"
            "assemblages, guilds and status definitions — with the stamp\n"
            "recording what the figures were computed against.")
        self.workbook_btn.clicked.connect(self._on_export_workbook)
        self.workbook_btn.setEnabled(False); toolbar.addWidget(self.workbook_btn)
        self.pdf_btn = QPushButton("Export PDF"); self.pdf_btn.setStyleSheet(BTN_PRIMARY)
        self.pdf_btn.setToolTip(
            "The assessment as a report: basis, figures, key species with\n"
            "accounts, habitats, assemblages, guilds, appendices. Laid out from\n"
            "the workbook, so every figure is the workbook's own.")
        self.pdf_btn.clicked.connect(self._on_export_pdf)
        self.pdf_btn.setEnabled(False); toolbar.addWidget(self.pdf_btn)
        self.word_btn = QPushButton("Export Word"); self.word_btn.setStyleSheet(BTN_PRIMARY)
        self.word_btn.setToolTip(
            "The same report as the PDF, as an editable Word document for\n"
            "copying into a report template.")
        self.word_btn.clicked.connect(self._on_export_word)
        self.word_btn.setEnabled(False); toolbar.addWidget(self.word_btn)
        export_btn = QPushButton("Export CSV"); export_btn.setStyleSheet(BTN_OUTLINE)
        export_btn.clicked.connect(self._export_csv); toolbar.addWidget(export_btn)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.table = QTableWidget(); self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(["Project", "Year", "Client", "Sites", "Visits", "Species", "Key spp", "% Key", "SQI", "Dates"])
        from .presentation import SQI_TOOLTIP
        self.table.horizontalHeaderItem(8).setToolTip(SQI_TOOLTIP)    # the scale (E8)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True); self.table.setStyleSheet(TABLE_STYLE)
        # A floor, not a cap: ~5 rows always visible, draggable taller.
        self.table.setMinimumHeight(260)
        splitter.addWidget(self.table)

        detail_container = QWidget()
        dl = QVBoxLayout(detail_container); dl.setContentsMargins(0, 0, 0, 0); dl.setSpacing(4)
        self.detail_header = QLabel("Select a project or import a species list")
        self.detail_header.setFont(QFont("Georgia", 13, QFont.Weight.Bold))
        self.detail_header.setStyleSheet("color: " + ACCENT_DARK + ";"); dl.addWidget(self.detail_header)
        self.detail_tabs = QTabWidget(); self.detail_tabs.setStyleSheet(TAB_STYLE)
        self.overview_tab = OverviewTab(); self.habitat_tab = HabitatTab()
        self.assemblage_tab = AssemblageTab(); self.species_tab = SpeciesTab()
        self.conservation_tab = ConservationTab()
        self.detail_tabs.addTab(self.overview_tab, "Overview")
        self.detail_tabs.addTab(self.habitat_tab, "Habitats")
        self.detail_tabs.addTab(self.assemblage_tab, "Assemblages")
        self.detail_tabs.addTab(self.species_tab, "Species")
        self.detail_tabs.addTab(self.conservation_tab, "Conservation")
        self.detail_tabs.hide(); dl.addWidget(self.detail_tabs, 1)
        detail_container.setMinimumHeight(200)   # explicit: the splitter stops following content
        splitter.addWidget(detail_container)
        splitter.setStretchFactor(0, 0); splitter.setStretchFactor(1, 1)
        # Neither pane may collapse: the table keeps its minimum, the detail its own.
        splitter.setChildrenCollapsible(False)
        # Clicking a project must not move the divider: record the split, load,
        # restore -- now and again once Qt has finished laying out.
        def _keep_split(row, col):
            sizes = self._splitter.sizes()
            self._on_project_clicked(row, col)
            self._splitter.setSizes(sizes)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._splitter.setSizes(sizes))
        self.table.cellClicked.connect(_keep_split)
        self._splitter = splitter
        from PySide6.QtCore import QSettings
        _st = QSettings("Flauna", "Examen").value("site_analysis/splitter")
        if _st is None or not splitter.restoreState(_st):
            splitter.setSizes([340, 660])          # table ~1/4 on first run
        splitter.splitterMoved.connect(
            lambda *_: QSettings("Flauna", "Examen").setValue(
                "site_analysis/splitter", self._splitter.saveState()))
        layout.addWidget(splitter, 1)
        self.summary_label = QLabel(""); self.summary_label.setStyleSheet("color: " + TEXT_MUTED + "; font-size: 11px;")
        layout.addWidget(self.summary_label)

    def _load_projects(self):
        self._projects = load_all_projects(self._mode,
                                           by_year=not self._pool_years,
                                           jurisdiction=self.juris_combo.currentText())
        # Sorting off while filling: with it on, setItem can re-sort mid-fill.
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._projects))
        self.appendix_btn.setEnabled(False)
        if hasattr(self, 'workbook_btn'): self.workbook_btn.setEnabled(False)
        if hasattr(self, 'pdf_btn'): self.pdf_btn.setEnabled(False)
        if hasattr(self, 'word_btn'): self.word_btn.setEnabled(False)
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
                colour=RED_STATUS if (p.key_species_count or 0) > 0 else None,
                tip=(f"Key species under {p.jurisdiction}" if getattr(p, "jurisdiction", "")
                     else None))
            put(i, 7, f"{p.key_species_pct}%", float(p.key_species_pct or 0))
            # Pantheon's red triangle below 15 scoring species (backlog E9)
            weak = p.sqi > 0 and not p.sqi_reliable
            sq = (str(int(p.sqi)) if p.sqi > 0 else "-") + (" \u25b2" if weak else "")
            put(i, 8, sq, float(p.sqi or 0),
                colour=RED_STATUS if weak else
                MOSS_GREEN if p.sqi >= 150 else (AMBER if p.sqi >= 125 else None),
                tip=(f"Fewer than 15 scoring species ({p.species_with_sqs}): "
                     "Pantheon flags this SQI as unreliable") if weak else None)
            put(i, 9, f"{_dmy(p.first_date)} \u2013 {_dmy(p.last_date)}" if p.first_date else "",
                p.first_date or "", centre=False)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSortingEnabled(True)
        mode_t = mode_label(self._mode)
        grouping = "pooled across years" if self._pool_years else "by survey year"
        self.summary_label.setText(f"{len(self._projects)} rows ({grouping})  |  "
                                   f"Mode: {mode_t}")

    def _on_project_clicked(self, row, col):
        # The row carries its project: after sorting, row N is not self._projects[N].
        _it = self.table.item(row, 0)
        _idx = _it.data(_PROJ_ROLE) if _it is not None else None
        if _idx is None or _idx >= len(self._projects): return
        proj = self._projects[_idx]
        self._jurisdiction, how = self._resolve_jurisdiction(proj)
        detail = load_project_detail(proj.project_name, proj.client, self._mode,
                                     survey_year=proj.survey_year or None,
                                     jurisdiction=self._jurisdiction)
        if not detail: return
        self._current_detail = detail
        self._current_project = proj
        self._current_site_name = proj.display_name
        # Every TVK recorded -- a species recorded as s.l. and s.s. is merged by
        # the analysis, which needs both (EXA14).
        tvks = list(getattr(detail, "recorded_tvks", None) or
                    [sp.tvk for sp in detail.species_list if sp.tvk])
        names = {sp.tvk: sp.name for sp in detail.species_list if sp.tvk}
        sites_info = f" ({proj.site_count} sites)" if proj.site_count > 1 else ""
        title = (f"{proj.display_name} \u2014 {proj.client}{sites_info}"
                 if proj.survey_year else
                 f"{proj.project_name} \u2014 {proj.client}{sites_info} (all years pooled)")
        title += f"   \u2014 assessed under {self._jurisdiction} ({how})"
        # The species list was built from this analysis: reuse it, so the list,
        # the tabs and the table row are one computation.
        self._run_analysis(tvks, names, title, detail.site.visit_count,
                           result=getattr(detail, "analysis", None))

    def _run_analysis(self, tvks, names, title, visits=0, result=None):
        mode = self._mode if isinstance(self._mode, AnalysisMode) else AnalysisMode.CODEX_FULL
        juris = getattr(self, "_jurisdiction", "England")
        try:
            if result is None:
                try:
                    result = self._service.analyse(tvks, names, mode, juris)
                except TypeError:
                    result = self._service.analyse(tvks, names, mode)
            self._current_result = result
        except Exception as e:
            self.detail_header.setText(f"Analysis error: {e}"); return
        self.detail_header.setText(title)
        self.appendix_btn.setEnabled(True)
        self.workbook_btn.setEnabled(True); self.pdf_btn.setEnabled(True); self.word_btn.setEnabled(True)
        self.detail_tabs.show()
        # Compartments (E6): computed once here, cached on the detail, read by the
        # Overview and the workbook/PDF/Word exports.
        if self._current_detail is not None:
            try:
                from .compartments import for_detail
                for_detail(result, self._current_detail, self._current_project, juris,
                           service=self._service)
            except Exception as e:  # noqa: BLE001 -- the extra table must not stop the analysis
                print(f"[Examen] compartments: {e}")
        taxonomy = self._load_taxonomy(tvks)
        fidelity = self._load_fidelity(tvks)
        self.overview_tab.set_result(result, self._current_detail, visits)
        self.habitat_tab.set_result(result, self._current_detail, fidelity)
        self.assemblage_tab.set_result(result)
        self.species_tab.set_result(result, self._current_detail, taxonomy)
        self.conservation_tab.set_result(result, self._current_detail)

    def _load_taxonomy(self, tvks):
        """Delegates to examen_data.load_taxonomy -- one lookup for tab and exports."""
        from .examen_data import load_taxonomy
        return load_taxonomy(tvks)

    def _load_fidelity(self, tvks):
        if not tvks: return {}
        try:
            from shared.repositories.pantheon_repository import PantheonRepository
            repo = PantheonRepository(); fid = repo.get_fidelity_scores(tvks); repo.close()
            by_index = {}
            for tvk, scores in fid.items():
                for idx, score in scores.items(): by_index.setdefault(idx, {})[tvk] = score
            return by_index
        except Exception: return {}

    def _on_import(self):
        from .import_species_dialog import ImportSpeciesDialog
        dlg = ImportSpeciesDialog(self)
        if dlg.exec():
            tvks, names = dlg.get_results()
            if tvks:
                self._current_detail = None; self._current_project = None
                self._current_site_name = "Imported List"
                # An imported list has no records, so no vice-county to read.
                self._jurisdiction, how = self._resolve_jurisdiction(None)
                self._run_analysis(tvks, names, f"Imported List ({len(tvks)} species)")

    def _on_export_appendix(self):
        if not self._current_result: return
        from .appendix_export import export_appendix
        export_appendix(self, self._current_site_name or "Site", self._current_result, self._current_detail,
                        jurisdiction=getattr(self, "_jurisdiction", "England"))

    def _on_export_pdf(self):
        """Write the PDF assessment report (backlog E3) -- the workbook, laid out."""
        if not self._current_result:
            return
        try:
            from .pdf_export import export_pdf, HAS_REPORTLAB
        except ImportError:
            HAS_REPORTLAB = False
        if not HAS_REPORTLAB:
            QMessageBox.warning(self, "Export PDF",
                                "The PDF report needs reportlab. In a terminal:\n\n"
                                "    py -3.14 -m pip install reportlab\n\nthen restart Examen.")
            return
        base = (self._current_site_name or "Assessment").replace(" \u2014 ", " ")
        base = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in base)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export assessment report (PDF)", f"{base.strip()} assessment.pdf", "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            export_pdf(self._current_result, self._current_detail, self._current_project, path,
                       jurisdiction=getattr(self, "_jurisdiction", "England"),
                       pooled_years=self._pool_years)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed", f"The PDF could not be written.\n\n{e}")
            return
        QMessageBox.information(self, "PDF exported", f"Written to:\n{path}")

    def _on_export_word(self):
        """Write the Word assessment report (backlog E4) -- the PDF's sections, editable."""
        if not self._current_result:
            return
        try:
            from .word_export import export_word, HAS_DOCX
        except ImportError:
            HAS_DOCX = False
        if not HAS_DOCX:
            QMessageBox.warning(self, "Export Word",
                                "The Word report needs python-docx. In a terminal:\n\n"
                                "    py -3.14 -m pip install python-docx\n\nthen restart Examen.")
            return
        base = (self._current_site_name or "Assessment").replace(" \u2014 ", " ")
        base = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in base)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export assessment report (Word)", f"{base.strip()} assessment.docx",
            "Word document (*.docx)")
        if not path:
            return
        if not path.lower().endswith(".docx"):
            path += ".docx"
        try:
            export_word(self._current_result, self._current_detail, self._current_project, path,
                        jurisdiction=getattr(self, "_jurisdiction", "England"),
                        pooled_years=self._pool_years)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed", f"The Word document could not be written.\n\n{e}")
            return
        QMessageBox.information(self, "Word report exported", f"Written to:\n{path}")

    def _on_export_workbook(self):
        """Write the full assessment workbook.

        Pooled analyses are still exportable -- the stamp says so, rather than
        the export refusing -- because a deliberately pooled site-wide list is a
        legitimate thing to assess, just not the same thing as a survey.
        """
        if not self._current_result:
            return
        from .workbook_export import export_workbook

        proj = self._current_project
        base = (self._current_site_name or "Assessment").replace(" \u2014 ", " ")
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
                            jurisdiction=getattr(self, "_jurisdiction", "England"),
                            pooled_years=self._pool_years)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed",
                                f"The workbook could not be written.\n\n{e}")
            return
        QMessageBox.information(
            self, "Workbook exported",
            f"Written to:\n{path}\n\nThe Summary sheet records the Codex "
            "version, survey scope and jurisdiction the figures were computed "
            "against.")

    def _export_csv(self):
        if not self._projects: return
        p, _ = QFileDialog.getSaveFileName(self, "Export", "project_analysis.csv", "CSV (*.csv)")
        if not p: return
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Project","Year","Client","Sites","Visits","Species","Key Species","% Key","SQI","Reliable","Rare","Scarce","Priority","First","Last"])
            for s in self._projects:
                w.writerow([s.project_name, s.survey_year or "all", s.client, s.site_count, s.visit_count, s.species_count,
                            s.key_species_count, s.key_species_pct, int(s.sqi) if s.sqi else "",
                            "Yes" if s.sqi_reliable else "No", s.rare_count, s.scarce_count, s.priority_count, s.first_date, s.last_date])

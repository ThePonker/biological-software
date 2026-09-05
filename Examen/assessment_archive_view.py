"""
Examen - Assessment Archive View

Browse frozen site assessments. Click to see frozen vs live comparison.
Select two snapshots for site-to-site comparison with Jaccard similarity.
Export historical data. Naturalist theme.
"""

import csv
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QSplitter, QScrollArea, QMessageBox, QFileDialog,
    QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

try:
    from shared.repositories.codex_repository import AnalysisMode
except ImportError:
    from enum import Enum
    class AnalysisMode(Enum):
        CODEX_FULL = "codex_full"
        PANTHEON_ONLY = "pantheon_only"

BG = "#f5f5f4"; SURFACE = "#ffffff"; TEXT_PRIMARY = "#1f2937"; TEXT_HEADING = "#4b5563"
TEXT_SECONDARY = "#6b7280"; TEXT_MUTED = "#9ca3af"; BORDER = "#d1d5db"; SEPARATOR = "#e5e7eb"
ACCENT = "#7c6c9f"; ACCENT_LIGHT = "#f0edf5"; ACCENT_DARK = "#5a4d78"
MOSS_GREEN = "#4a7c59"; RED_STATUS = "#a63d40"; AMBER = "#c2956e"; WARM_GRAY = "#8b8178"

BTN_ACCENT = ("QPushButton { background: " + ACCENT + "; color: white; border: none; "
    "padding: 6px 16px; border-radius: 4px; font-size: 12px; } QPushButton:hover { background: " + ACCENT_DARK + "; }")
BTN_OUTLINE = ("QPushButton { color: " + MOSS_GREEN + "; border: 1px solid " + MOSS_GREEN + "; "
    "padding: 6px 16px; border-radius: 4px; font-size: 12px; background: none; } QPushButton:hover { background: #e6f0ea; }"
    " QPushButton:disabled { color: #d1d5db; border-color: #d1d5db; }")
BTN_DELETE = ("QPushButton { color: " + RED_STATUS + "; border: 1px solid " + RED_STATUS + "; "
    "padding: 6px 16px; border-radius: 4px; font-size: 12px; background: none; } QPushButton:hover { background: #f5e6e6; }")


class AssessmentArchiveView(QWidget):

    def __init__(self, analysis_service, snapshot_mgr):
        super().__init__()
        self._service = analysis_service
        self._snapshots = snapshot_mgr
        self._snapshot_list = []
        self._setup_ui(); self._load_snapshots()

    def _setup_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(16,16,16,16); layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Frozen assessments"); title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: " + TEXT_HEADING + ";"); header.addWidget(title); header.addStretch()
        refresh_btn = QPushButton("Refresh"); refresh_btn.setStyleSheet(BTN_ACCENT)
        refresh_btn.clicked.connect(self._load_snapshots); header.addWidget(refresh_btn)
        self.compare_btn = QPushButton("Compare Sites"); self.compare_btn.setStyleSheet(BTN_OUTLINE)
        self.compare_btn.setEnabled(False); self.compare_btn.clicked.connect(self._on_compare); header.addWidget(self.compare_btn)
        self.export_btn = QPushButton("Export"); self.export_btn.setStyleSheet(BTN_OUTLINE)
        self.export_btn.setEnabled(False); self.export_btn.clicked.connect(self._on_export); header.addWidget(self.export_btn)
        self.delete_btn = QPushButton("Delete"); self.delete_btn.setStyleSheet(BTN_DELETE)
        self.delete_btn.setEnabled(False); self.delete_btn.clicked.connect(self._on_delete); header.addWidget(self.delete_btn)
        layout.addLayout(header)

        self.info_banner = QFrame()
        self.info_banner.setStyleSheet("QFrame { background: " + ACCENT_LIGHT + "; border: 1px solid " + BORDER + "; border-radius: 6px; }")
        bl = QVBoxLayout(self.info_banner); bl.setContentsMargins(16, 12, 16, 12)
        it = QLabel("Frozen assessments capture your report figures at the moment you sign off. "
                     "They preserve the species list, all computed metrics, and the Codex version used "
                     "\u2014 even if the underlying data updates later. Select two to compare sites.")
        it.setWordWrap(True); it.setStyleSheet("color: " + ACCENT_DARK + "; font-size: 12px; border: none;")
        bl.addWidget(it); layout.addWidget(self.info_banner)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.table = QTableWidget(); self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["Site", "Project", "Year", "Mode", "Species", "Key spp", "% Key", "SQI"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget { border: 1px solid " + BORDER + "; gridline-color: " + SEPARATOR + "; font-size: 12px; }"
            "QHeaderView::section { background: " + BG + "; border: none; border-bottom: 2px solid " + BORDER + "; "
            "padding: 6px; font-weight: bold; font-size: 11px; color: " + TEXT_HEADING + "; }")
        self.table.cellClicked.connect(self._on_snapshot_clicked)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.table)

        ds = QScrollArea(); ds.setWidgetResizable(True); ds.setStyleSheet("QScrollArea { border: none; }")
        dc = QWidget(); self.dl = QVBoxLayout(dc); self.dl.setContentsMargins(8,12,8,8); self.dl.setSpacing(10)
        self.detail_header = QLabel("Select a snapshot to compare")
        self.detail_header.setFont(QFont("Georgia", 13, QFont.Weight.Bold))
        self.detail_header.setStyleSheet("color: " + ACCENT_DARK + ";"); self.dl.addWidget(self.detail_header)
        self.compare_widget = QWidget(); self.compare_layout = QHBoxLayout(self.compare_widget)
        self.compare_layout.setSpacing(8); self.compare_layout.setContentsMargins(0,0,0,0)
        self.dl.addWidget(self.compare_widget); self.compare_widget.hide()
        self.species_table = QTableWidget(); self.species_table.setColumnCount(5)
        self.species_table.setHorizontalHeaderLabels(["Species", "Tier", "Status", "SQS", "Frozen date"])
        self.species_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.species_table.setAlternatingRowColors(True)
        self.species_table.setStyleSheet(
            "QTableWidget { border: 1px solid " + BORDER + "; gridline-color: " + SEPARATOR + "; font-size: 11px; }"
            "QHeaderView::section { background: " + BG + "; border: none; border-bottom: 2px solid " + BORDER + "; "
            "padding: 4px; font-weight: bold; font-size: 11px; color: " + TEXT_HEADING + "; }")
        self.dl.addWidget(self.species_table); self.dl.addStretch()
        ds.setWidget(dc); splitter.addWidget(ds)
        splitter.setStretchFactor(0, 1); splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)
        self.status_label = QLabel(""); self.status_label.setStyleSheet("color: " + TEXT_MUTED + "; font-size: 11px;")
        layout.addWidget(self.status_label)

    # ── Load snapshots ───────────────────────────────────────────
    def _load_snapshots(self):
        self.table.setRowCount(0); self.delete_btn.setEnabled(False)
        self.compare_btn.setEnabled(False); self.export_btn.setEnabled(False)
        try: self._snapshot_list = self._snapshots.get_snapshots()
        except Exception: self._snapshot_list = []
        if not self._snapshot_list:
            self.status_label.setText("No frozen assessments yet."); self.info_banner.show(); return
        self.info_banner.hide(); self.table.setRowCount(len(self._snapshot_list))
        for i, sn in enumerate(self._snapshot_list):
            self.table.setItem(i, 0, QTableWidgetItem(sn.site_name))
            self.table.setItem(i, 1, QTableWidgetItem(sn.project_name))
            yr = QTableWidgetItem(str(sn.survey_year)); yr.setTextAlignment(Qt.AlignmentFlag.AlignCenter); self.table.setItem(i, 2, yr)
            self.table.setItem(i, 3, QTableWidgetItem("Codex" if "codex" in sn.analysis_mode else "Pantheon"))
            for col, val in [(4, sn.species_count), (5, sn.key_species_count)]:
                it = QTableWidgetItem(str(val)); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter); self.table.setItem(i, col, it)
            p = QTableWidgetItem(f"{sn.key_species_pct}%"); p.setTextAlignment(Qt.AlignmentFlag.AlignCenter); self.table.setItem(i, 6, p)
            st = (str(int(sn.sqi)) if sn.sqi else "-") + ("*" if not sn.sqi_reliable else "")
            self.table.setItem(i, 7, QTableWidgetItem(st))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.status_label.setText(f"{len(self._snapshot_list)} frozen assessment(s)")

    def _on_selection_changed(self):
        rows = set(idx.row() for idx in self.table.selectedIndexes())
        n = len(rows)
        self.delete_btn.setEnabled(n >= 1); self.export_btn.setEnabled(n == 1)
        self.compare_btn.setEnabled(n == 2)

    # ── Single snapshot detail ───────────────────────────────────
    def _on_snapshot_clicked(self, row, col):
        if row >= len(self._snapshot_list): return
        sn = self._snapshot_list[row]
        full = self._snapshots.get_snapshot(sn.id)
        if not full: return
        self.detail_header.setText(f"{full.site_name} \u2014 {full.project_name} ({full.survey_year})" if full.project_name
                                   else f"{full.site_name} ({full.survey_year})")
        tvks = [sp[0] for sp in full.species if sp[0]]
        names = {sp[0]: sp[1] for sp in full.species if sp[0]}
        mode = AnalysisMode.PANTHEON_ONLY if "pantheon" in full.analysis_mode else AnalysisMode.CODEX_FULL
        live = None
        try:
            if tvks: live = self._service.analyse(tvks, names, mode)
        except Exception: pass
        self._build_comparison(full, live)
        self.species_table.setRowCount(len(full.species))
        for i, (tvk, name, status, tier, sqs) in enumerate(full.species):
            self.species_table.setItem(i, 0, QTableWidgetItem(name))
            ti = QTableWidgetItem(tier)
            if tier == "Rare": ti.setForeground(QColor(RED_STATUS))
            elif tier == "Scarce": ti.setForeground(QColor(AMBER))
            self.species_table.setItem(i, 1, ti)
            self.species_table.setItem(i, 2, QTableWidgetItem(status))
            si = QTableWidgetItem(str(sqs) if sqs else "-"); si.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.species_table.setItem(i, 3, si)
            self.species_table.setItem(i, 4, QTableWidgetItem(full.frozen_date[:10]))
        self.species_table.resizeColumnsToContents()
        self.species_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

    def _build_comparison(self, snap, live):
        while self.compare_layout.count():
            w = self.compare_layout.takeAt(0).widget()
            if w: w.deleteLater()
        fs = int(snap.sqi) if snap.sqi else 0; ls = int(live.overall_sqi.sqi) if live and live.overall_sqi else 0
        for title, fv, lv in [("Species", str(snap.species_count), str(live.total_species) if live else "?"),
                               ("Key spp", str(snap.key_species_count), str(live.key_species_count) if live else "?"),
                               ("% Key", f"{snap.key_species_pct}%", f"{live.key_species_pct}%" if live else "?"),
                               ("SQI", str(fs) or "-", str(ls) or "-"),
                               ("Rare", str(snap.rare_count), str(live.rare_count) if live else "?"),
                               ("Scarce", str(snap.scarce_count), str(live.scarce_count) if live else "?")]:
            self.compare_layout.addWidget(self._cmp_card(title, fv, lv))
        self.compare_widget.show()

    def _cmp_card(self, title, fv, lv):
        c = QFrame(); c.setStyleSheet("QFrame { background: "+SURFACE+"; border: 1px solid "+BORDER+"; border-radius: 6px; }")
        cl = QVBoxLayout(c); cl.setContentsMargins(10,8,10,8); cl.setSpacing(2)
        t = QLabel(title); t.setStyleSheet("color: "+TEXT_MUTED+"; font-size: 10px; border: none; background: none;"); cl.addWidget(t)
        r = QHBoxLayout(); r.setSpacing(6)
        f = QLabel(fv); f.setFont(QFont("Georgia", 14, QFont.Weight.Bold)); f.setStyleSheet("color: "+ACCENT_DARK+"; border: none; background: none;"); r.addWidget(f)
        a = QLabel("\u2192"); a.setStyleSheet("color: "+TEXT_MUTED+"; border: none; background: none;"); r.addWidget(a)
        l = QLabel(lv); l.setFont(QFont("Georgia", 14, QFont.Weight.Bold))
        l.setStyleSheet(f"color: {MOSS_GREEN if fv != lv else TEXT_MUTED}; border: none; background: none;"); r.addWidget(l)
        cl.addLayout(r)
        s = QLabel("Frozen \u2192 Live"); s.setStyleSheet("color: "+TEXT_MUTED+"; font-size: 9px; border: none; background: none;"); cl.addWidget(s)
        return c

    # ── Site comparison (Jaccard) ────────────────────────────────
    def _on_compare(self):
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        if len(rows) != 2: return
        s1 = self._snapshots.get_snapshot(self._snapshot_list[rows[0]].id)
        s2 = self._snapshots.get_snapshot(self._snapshot_list[rows[1]].id)
        if not s1 or not s2: return
        tvks1 = {sp[0] for sp in s1.species if sp[0]}
        tvks2 = {sp[0] for sp in s2.species if sp[0]}
        shared = tvks1 & tvks2; union = tvks1 | tvks2
        jaccard = round(len(shared) / len(union) * 100, 1) if union else 0
        msg = (f"Site 1: {s1.site_name} ({s1.survey_year}) -- {len(tvks1)} species\n"
               f"Site 2: {s2.site_name} ({s2.survey_year}) -- {len(tvks2)} species\n\n"
               f"Shared species: {len(shared)}\n"
               f"Jaccard similarity: {jaccard}%\n\n"
               f"Site 1 SQI: {int(s1.sqi) if s1.sqi else '-'}   Key: {s1.key_species_count} ({s1.key_species_pct}%)\n"
               f"Site 2 SQI: {int(s2.sqi) if s2.sqi else '-'}   Key: {s2.key_species_count} ({s2.key_species_pct}%)")
        QMessageBox.information(self, "Site Comparison", msg)

    # ── Historical export ────────────────────────────────────────
    def _on_export(self):
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        if len(rows) != 1: return
        sn = self._snapshots.get_snapshot(self._snapshot_list[rows[0]].id)
        if not sn: return
        safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in sn.site_name)
        path, _ = QFileDialog.getSaveFileName(self, "Export Frozen Assessment",
            f"{safe}_{sn.survey_year}_frozen.csv", "CSV (*.csv)")
        if not path: return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Site", sn.site_name, "Project", sn.project_name, "Year", sn.survey_year,
                         "Mode", sn.analysis_mode, "Frozen", sn.frozen_date])
            w.writerow(["SQI", int(sn.sqi) if sn.sqi else "", "Key Species", sn.key_species_count,
                         "% Key", sn.key_species_pct, "Rare", sn.rare_count, "Scarce", sn.scarce_count, "Priority", sn.priority_count])
            w.writerow([])
            w.writerow(["Species", "TVK", "Status", "Tier", "SQS"])
            for tvk, name, status, tier, sqs in sn.species:
                w.writerow([name, tvk, status, tier, sqs if sqs else ""])
        QMessageBox.information(self, "Examen", f"Exported: {path}")

    # ── Delete ───────────────────────────────────────────────────
    def _on_delete(self):
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=True)
        if not rows: return
        names = [self._snapshot_list[r].site_name for r in rows if r < len(self._snapshot_list)]
        reply = QMessageBox.question(self, "Examen", f"Delete {len(rows)} frozen assessment(s)?\n{', '.join(names)}\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            for r in rows:
                if r < len(self._snapshot_list):
                    try: self._snapshots.delete_snapshot(self._snapshot_list[r].id)
                    except Exception: pass
            self._load_snapshots()

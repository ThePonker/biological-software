"""
Examen — Assemblage Tab

Specific Assemblage Types (SATs) table with species counts, SQI,
% of national species pool, and Favourable Condition thresholds
where available.
"""

import json
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

BG = "#f5f5f4"; SURFACE = "#ffffff"; TEXT_HEADING = "#4b5563"
TEXT_SECONDARY = "#6b7280"; TEXT_MUTED = "#9ca3af"; BORDER = "#d1d5db"; SEPARATOR = "#e5e7eb"
MOSS_GREEN = "#4a7c59"; ACCENT_DARK = "#5a4d78"; RED_STATUS = "#a63d40"; AMBER = "#c2956e"

THRESHOLDS_PATH = Path(__file__).parent / "sat_thresholds.json"
_thresholds_cache = None


def _load_thresholds():
    global _thresholds_cache
    if _thresholds_cache is not None:
        return _thresholds_cache
    if THRESHOLDS_PATH.exists():
        try:
            with open(THRESHOLDS_PATH, "r", encoding="utf-8") as f:
                _thresholds_cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            _thresholds_cache = {}
    else:
        _thresholds_cache = {}
    return _thresholds_cache


class AssemblageTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self); layout.setContentsMargins(8, 12, 8, 8); layout.setSpacing(10)

        lbl = QLabel("Specific Assemblage Types (SATs)")
        lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl.setStyleSheet("color: " + TEXT_HEADING + ";"); layout.addWidget(lbl)

        info = QLabel("SATs represent ecologically restricted species assemblages indicative of "
                       "conservation value. Favourable Condition (FC) thresholds indicate the minimum "
                       "species count for SSSI-level quality.")
        info.setWordWrap(True)
        info.setStyleSheet("color: " + TEXT_SECONDARY + "; font-size: 11px;")
        layout.addWidget(info)

        self.table = QTableWidget(); self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Assemblage Type", "Species", "Scoring", "SQI", "% National Pool",
            "FC Threshold", "PtT %"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget { border: 1px solid " + BORDER + "; gridline-color: " + SEPARATOR + "; font-size: 11px; }"
            "QHeaderView::section { background: " + BG + "; border: none; border-bottom: 2px solid "
            + BORDER + "; padding: 5px; font-weight: bold; font-size: 11px; color: " + TEXT_HEADING + "; }")
        layout.addWidget(self.table, 1)

        self.summary = QLabel("")
        self.summary.setStyleSheet("color: " + TEXT_MUTED + "; font-size: 11px;")
        layout.addWidget(self.summary)

    def set_result(self, result, ref_counts=None):
        from .habitat_tab import _load_reference_counts
        refs = _load_reference_counts()
        sat_refs = refs.get("sat", {})
        thresholds = _load_thresholds()

        sat_map = {s.label: s for s in result.sat_sqi}
        rows = []
        for sat_name in sorted(result.sat_counts.keys()):
            count = result.sat_counts[sat_name]
            sqi_r = sat_map.get(sat_name)
            total_in_pantheon = sat_refs.get(sat_name, 0)
            pct_pool = round(count / total_in_pantheon * 100, 1) if total_in_pantheon else 0
            threshold = thresholds.get(sat_name, {}).get("threshold", 0)
            ptt = round(count / threshold * 100) if threshold else 0
            rows.append((sat_name, count, sqi_r, pct_pool, threshold, ptt))

        rows.sort(key=lambda x: -x[1])
        self.table.setRowCount(len(rows))
        fc_count = 0

        for i, (name, count, sqi_r, pct_pool, threshold, ptt) in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(name))
            ci = QTableWidgetItem(str(count)); ci.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 1, ci)

            if sqi_r:
                sc = QTableWidgetItem(str(sqi_r.species_with_sqs)); sc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, 2, sc)
                sqi_text = str(int(sqi_r.sqi)) if sqi_r.sqi else "-"
                if not sqi_r.reliable: sqi_text += "*"
                si = QTableWidgetItem(sqi_text); si.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if sqi_r.sqi >= 150: si.setForeground(QColor(MOSS_GREEN))
                elif sqi_r.sqi >= 125: si.setForeground(QColor(AMBER))
                self.table.setItem(i, 3, si)

            pi = QTableWidgetItem(f"{pct_pool}%" if pct_pool else "-")
            pi.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if pct_pool >= 21: pi.setForeground(QColor(MOSS_GREEN))
            elif pct_pool >= 10: pi.setForeground(QColor(AMBER))
            self.table.setItem(i, 4, pi)

            if threshold:
                ti = QTableWidgetItem(str(threshold)); ti.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, 5, ti)
                ptt_item = QTableWidgetItem(f"{ptt}%"); ptt_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if ptt >= 100:
                    ptt_item.setForeground(QColor(MOSS_GREEN))
                    ptt_item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                    fc_count += 1
                elif ptt >= 75: ptt_item.setForeground(QColor(AMBER))
                self.table.setItem(i, 6, ptt_item)
            else:
                self.table.setItem(i, 5, QTableWidgetItem("-"))
                self.table.setItem(i, 6, QTableWidgetItem("-"))

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        summary = f"{len(rows)} SATs represented"
        if fc_count: summary += f"  |  {fc_count} at Favourable Condition"
        self.summary.setText(summary)

"""
Examen — Habitat Tab

Broad Biotope → Habitat hierarchy with species counts, SQI per level,
% Representation (sample species / total Pantheon species for that habitat),
and fidelity scores (IEC, ERS, calcareous, acid mire etc.).
"""

import sqlite3
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QTableWidget,
    QTableWidgetItem,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
import paths

BG = "#f5f5f4"; SURFACE = "#ffffff"; TEXT_PRIMARY = "#1f2937"; TEXT_HEADING = "#4b5563"
TEXT_SECONDARY = "#6b7280"; TEXT_MUTED = "#9ca3af"; BORDER = "#d1d5db"; SEPARATOR = "#e5e7eb"
MOSS_GREEN = "#4a7c59"; ACCENT = "#7c6c9f"; ACCENT_DARK = "#5a4d78"
RED_STATUS = "#a63d40"; AMBER = "#c2956e"

_ref_cache = {}  # Cached reference counts {type: {name: count}}


def _load_reference_counts():
    """One-time load of total species per biotope/habitat/SAT in Pantheon."""
    global _ref_cache
    if _ref_cache:
        return _ref_cache
    if not paths.PANTHEON_DB.exists():
        return {}
    conn = sqlite3.connect(str(paths.PANTHEON_DB))
    c = conn.cursor()
    _ref_cache["biotope"] = {}
    c.execute("SELECT biotope, COUNT(DISTINCT tvk) FROM broad_biotope GROUP BY biotope")
    for r in c.fetchall(): _ref_cache["biotope"][r[0]] = r[1]
    _ref_cache["habitat"] = {}
    c.execute("SELECT habitat, COUNT(DISTINCT tvk) FROM habitats GROUP BY habitat")
    for r in c.fetchall(): _ref_cache["habitat"][r[0]] = r[1]
    _ref_cache["sat"] = {}
    c.execute("SELECT sat_name, COUNT(DISTINCT tvk) FROM specific_assemblage_types GROUP BY sat_name")
    for r in c.fetchall(): _ref_cache["sat"][r[0]] = r[1]
    conn.close()
    return _ref_cache


class HabitatTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self); layout.setContentsMargins(8, 12, 8, 8); layout.setSpacing(10)

        # Habitat hierarchy tree
        lbl = QLabel("Habitat hierarchy"); lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl.setStyleSheet("color: " + TEXT_HEADING + ";"); layout.addWidget(lbl)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["Biotope / Habitat", "Species", "Scoring", "SQI", "% National Pool"])
        self.tree.setAlternatingRowColors(True)
        hdr = self.tree.header()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 5): hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setStyleSheet(
            "QTreeWidget { border: 1px solid " + BORDER + "; font-size: 11px; }"
            "QHeaderView::section { background: " + BG + "; border: none; border-bottom: 2px solid "
            + BORDER + "; padding: 5px; font-weight: bold; font-size: 11px; color: " + TEXT_HEADING + "; }")
        layout.addWidget(self.tree, 2)

        # Fidelity scores
        flbl = QLabel("Fidelity indices"); flbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        flbl.setStyleSheet("color: " + TEXT_HEADING + ";"); layout.addWidget(flbl)

        self.fidelity_table = QTableWidget(); self.fidelity_table.setColumnCount(3)
        self.fidelity_table.setHorizontalHeaderLabels(["Index", "Species", "Scoring Species"])
        self.fidelity_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.fidelity_table.setAlternatingRowColors(True)
        self.fidelity_table.setMaximumHeight(180)
        self.fidelity_table.setStyleSheet(
            "QTableWidget { border: 1px solid " + BORDER + "; gridline-color: " + SEPARATOR + "; font-size: 11px; }"
            "QHeaderView::section { background: " + BG + "; border: none; border-bottom: 2px solid "
            + BORDER + "; padding: 5px; font-weight: bold; font-size: 11px; color: " + TEXT_HEADING + "; }")
        layout.addWidget(self.fidelity_table, 1)

    def set_result(self, result, detail=None, fidelity_data=None):
        self._build_tree(result)
        self._build_fidelity(fidelity_data or {})

    @staticmethod
    def _sqi_text(sqi):
        """SQI cell text. Withheld below the reliability threshold.

        A habitat with three scoring species was rendering "SQI 200*". The
        asterisk was honest, but the figure invites misreading in a report and
        Pantheon withholds it. Show the evidence instead.
        """
        if not sqi or not sqi.species_with_sqs:
            return "-"
        if not sqi.reliable:
            return f"({sqi.species_with_sqs} spp)"
        return str(int(sqi.sqi))

    @staticmethod
    def _sqi_colour(sqi):
        if not sqi or not sqi.reliable or not sqi.sqi:
            return None
        if sqi.sqi >= 150:
            return QColor(MOSS_GREEN)
        if sqi.sqi >= 125:
            return QColor(AMBER)
        return None

    def _fill(self, item, count, sqi, pct):
        item.setText(1, str(count))
        item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
        item.setText(2, str(sqi.species_with_sqs) if sqi else "0")
        item.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter)
        item.setText(3, self._sqi_text(sqi))
        item.setTextAlignment(3, Qt.AlignmentFlag.AlignCenter)
        col = self._sqi_colour(sqi)
        if col:
            item.setForeground(3, col)
        elif sqi and not sqi.reliable:
            item.setForeground(3, QColor(TEXT_MUTED))
        item.setText(4, f"{pct}%" if pct > 0 else "-")
        item.setTextAlignment(4, Qt.AlignmentFlag.AlignCenter)
        if pct >= 21:
            item.setForeground(4, QColor(MOSS_GREEN))
        elif pct >= 10:
            item.setForeground(4, QColor(AMBER))

    def _build_tree(self, result):
        """Biotope -> habitat, using only the pairs this sample holds.

        Previously the pairs came from a join across the whole of pantheon.db,
        so every habitat appeared under every biotope carrying the site-wide
        count -- "coastal" with one species listed "short sward & bare ground:
        41" beneath it.
        """
        self.tree.clear()
        refs = _load_reference_counts()
        bio_refs = refs.get("biotope", {})
        hab_refs = refs.get("habitat", {})

        bio_map = {s.label: s for s in result.biotope_sqi}
        pair_counts = getattr(result, "biotope_habitat_counts", {}) or {}
        pair_sqi = getattr(result, "biotope_habitat_sqi", {}) or {}

        for bio_name in sorted(result.biotope_counts.keys()):
            bio_count = result.biotope_counts.get(bio_name, 0)
            bio_total = bio_refs.get(bio_name, 0)
            pct = round(bio_count / bio_total * 100, 1) if bio_total else 0

            bio_item = QTreeWidgetItem()
            bio_item.setText(0, bio_name)
            bio_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
            self._fill(bio_item, bio_count, bio_map.get(bio_name), pct)

            habs = pair_counts.get(bio_name, {})
            for hab_name in sorted(habs, key=lambda h: -habs[h]):
                hab_count = habs[hab_name]
                hab_total = hab_refs.get(hab_name, 0)
                h_pct = round(hab_count / hab_total * 100, 1) if hab_total else 0
                hab_item = QTreeWidgetItem()
                hab_item.setText(0, hab_name)
                self._fill(hab_item, hab_count,
                           pair_sqi.get(bio_name, {}).get(hab_name), h_pct)
                bio_item.addChild(hab_item)

            self.tree.addTopLevelItem(bio_item)

        self.tree.expandAll()

    def _build_fidelity(self, fidelity_data):
        """Display fidelity indices. fidelity_data: {index_name: {tvk: score}}."""
        self.fidelity_table.setRowCount(0)
        if not fidelity_data:
            return
        # Summarise: index → count of species with that index
        rows = []
        for idx_name, tvk_scores in fidelity_data.items():
            total = len(tvk_scores)
            scoring = sum(1 for s in tvk_scores.values() if s and str(s) not in ("0", ""))
            rows.append((idx_name, total, scoring))
        rows.sort(key=lambda x: -x[1])
        self.fidelity_table.setRowCount(len(rows))
        for i, (name, total, scoring) in enumerate(rows):
            self.fidelity_table.setItem(i, 0, QTableWidgetItem(name))
            tc = QTableWidgetItem(str(total)); tc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.fidelity_table.setItem(i, 1, tc)
            sc = QTableWidgetItem(str(scoring)); sc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.fidelity_table.setItem(i, 2, sc)

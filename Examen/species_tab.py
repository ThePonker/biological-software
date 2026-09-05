"""
Examen — Species Tab

Full species table (all species, not just key) with filter controls
for biotope, tier, and key-species-only toggle.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

BG = "#f5f5f4"; SURFACE = "#ffffff"; TEXT_PRIMARY = "#1f2937"; TEXT_HEADING = "#4b5563"
TEXT_SECONDARY = "#6b7280"; TEXT_MUTED = "#9ca3af"; BORDER = "#d1d5db"; SEPARATOR = "#e5e7eb"
MOSS_GREEN = "#4a7c59"; ACCENT = "#7c6c9f"; ACCENT_DARK = "#5a4d78"
RED_STATUS = "#a63d40"; AMBER = "#c2956e"


class SpeciesTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_species = []  # Full list for filtering
        layout = QVBoxLayout(self); layout.setContentsMargins(8, 12, 8, 8); layout.setSpacing(8)

        # Filters
        filt = QHBoxLayout(); filt.setSpacing(8)
        self.key_only = QCheckBox("Key species only")
        self.key_only.toggled.connect(self._apply_filters)
        filt.addWidget(self.key_only)

        filt.addWidget(QLabel("Biotope:"))
        self.biotope_filter = QComboBox(); self.biotope_filter.addItem("All", "")
        self.biotope_filter.setMinimumWidth(150)
        self.biotope_filter.currentIndexChanged.connect(self._apply_filters)
        filt.addWidget(self.biotope_filter)

        filt.addWidget(QLabel("Tier:"))
        self.tier_filter = QComboBox()
        self.tier_filter.addItems(["All", "Rare", "Scarce", "Priority"])
        self.tier_filter.currentIndexChanged.connect(self._apply_filters)
        filt.addWidget(self.tier_filter)

        filt.addStretch()
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: " + TEXT_MUTED + "; font-size: 11px;")
        filt.addWidget(self.count_label)
        layout.addLayout(filt)

        # Species table
        self.table = QTableWidget(); self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Species", "Common Name", "Status", "SQS", "Tier",
            "Broad Biotope", "Habitat", "Family", "Order"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setStyleSheet(
            "QTableWidget { border: 1px solid " + BORDER + "; gridline-color: " + SEPARATOR + "; font-size: 11px; }"
            "QHeaderView::section { background: " + BG + "; border: none; border-bottom: 2px solid "
            + BORDER + "; padding: 5px; font-weight: bold; font-size: 11px; color: " + TEXT_HEADING + "; }")
        layout.addWidget(self.table, 1)

    def set_result(self, result, detail=None, taxonomy=None):
        """Populate from AnalysisResult + SiteDetail. taxonomy: {tvk: {common, family, order}}."""
        self._all_species = []
        tax = taxonomy or {}

        # Key species from result
        key_tvks = set()
        for k in result.key_species:
            t = tax.get(k.tvk, {})
            self._all_species.append({
                "name": k.species_name, "common": t.get("common", ""),
                "status": k.short_status, "sqs": k.sqs, "tier": k.tier,
                "biotope": k.broad_biotope, "habitat": k.habitat,
                "family": k.family or t.get("family", ""), "order": t.get("order", ""),
            })
            key_tvks.add(k.tvk)

        # Non-key species from detail
        if detail:
            for sp in detail.species_list:
                if sp.tvk in key_tvks or not sp.tvk:
                    continue
                t = tax.get(sp.tvk, {})
                self._all_species.append({
                    "name": sp.name, "common": t.get("common", ""),
                    "status": sp.status, "sqs": sp.sqs, "tier": sp.tier,
                    "biotope": sp.broad_biotope, "habitat": sp.habitat,
                    "family": t.get("family", ""), "order": t.get("order", ""),
                })

        # Populate biotope filter
        self.biotope_filter.blockSignals(True)
        self.biotope_filter.clear(); self.biotope_filter.addItem("All", "")
        biotopes = sorted(set(s["biotope"] for s in self._all_species if s["biotope"]))
        for b in biotopes: self.biotope_filter.addItem(b, b)
        self.biotope_filter.blockSignals(False)

        self._apply_filters()

    def _apply_filters(self):
        key_only = self.key_only.isChecked()
        bio_filter = self.biotope_filter.currentData() or ""
        tier_filter = self.tier_filter.currentText()

        filtered = []
        for sp in self._all_species:
            if key_only and not sp["tier"]: continue
            if bio_filter and bio_filter not in sp["biotope"]: continue
            if tier_filter != "All" and sp["tier"] != tier_filter: continue
            filtered.append(sp)

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(filtered))
        for i, sp in enumerate(filtered):
            self.table.setItem(i, 0, QTableWidgetItem(sp["name"]))
            self.table.setItem(i, 1, QTableWidgetItem(sp["common"]))
            si = QTableWidgetItem(sp["status"])
            if sp["tier"] == "Rare": si.setForeground(QColor(RED_STATUS))
            elif sp["tier"] == "Scarce": si.setForeground(QColor(AMBER))
            self.table.setItem(i, 2, si)
            sqs = QTableWidgetItem(str(sp["sqs"]) if sp["sqs"] else "")
            sqs.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 3, sqs)
            ti = QTableWidgetItem(sp["tier"])
            if sp["tier"] == "Rare": ti.setForeground(QColor(RED_STATUS))
            elif sp["tier"] == "Scarce": ti.setForeground(QColor(AMBER))
            elif sp["tier"] == "Priority": ti.setForeground(QColor(MOSS_GREEN))
            self.table.setItem(i, 4, ti)
            self.table.setItem(i, 5, QTableWidgetItem(sp["biotope"]))
            self.table.setItem(i, 6, QTableWidgetItem(sp["habitat"]))
            self.table.setItem(i, 7, QTableWidgetItem(sp["family"]))
            self.table.setItem(i, 8, QTableWidgetItem(sp["order"]))
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        total = len(self._all_species); shown = len(filtered)
        key = sum(1 for s in filtered if s["tier"])
        self.count_label.setText(f"{shown} of {total} species shown  |  {key} key")

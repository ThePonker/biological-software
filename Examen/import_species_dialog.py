"""
Examen - Import Species Dialog

Paste species names or load from CSV/Excel. Resolves against UKSI
to produce a TVK list for PantheonAnalysisService.analyse().
"""

import csv
import sqlite3
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QAbstractItemView, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
import paths

SURFACE = "#ffffff"
BG = "#f5f5f4"
TEXT_PRIMARY = "#1f2937"
TEXT_SECONDARY = "#6b7280"
TEXT_MUTED = "#9ca3af"
BORDER = "#d1d5db"
SEPARATOR = "#e5e7eb"
MOSS_GREEN = "#4a7c59"
ACCENT = "#7c6c9f"
ACCENT_DARK = "#5a4d78"
RED_STATUS = "#a63d40"
WARM_GRAY = "#8b8178"


class ImportSpeciesDialog(QDialog):
    """Paste or import species names, resolve to TVKs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Species List")
        self.setMinimumSize(700, 560)
        self._resolved: list[dict] = []  # [{name, tvk, common, family, matched}]
        self._setup_ui()

    def get_results(self) -> tuple[list[str], dict[str, str]]:
        """Return (tvk_list, {tvk: species_name}) for resolved species."""
        tvks = [r["tvk"] for r in self._resolved if r["tvk"]]
        names = {r["tvk"]: r["name"] for r in self._resolved if r["tvk"]}
        return tvks, names

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel("Import species list for analysis")
        header.setFont(QFont("Georgia", 13, QFont.Weight.Bold))
        header.setStyleSheet("color: " + ACCENT_DARK + ";")
        layout.addWidget(header)
        info = QLabel("Paste species names (one per line) or load from a CSV file. "
                       "Names are matched against UKSI to resolve TVKs.")
        info.setWordWrap(True)
        info.setStyleSheet("color: " + TEXT_SECONDARY + "; font-size: 11px;")
        layout.addWidget(info)

        # Input area
        input_row = QHBoxLayout()
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Paste species names here, one per line...\n\n"
                                          "e.g.\nLucanus cervus\nBombus terrestris\nRutpela maculata")
        self.text_edit.setStyleSheet(
            "QTextEdit { border: 1px solid " + BORDER + "; border-radius: 4px; "
            "font-size: 12px; padding: 6px; }")
        self.text_edit.setMaximumHeight(160)
        input_row.addWidget(self.text_edit, 1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)
        load_btn = QPushButton("Load CSV...")
        load_btn.setStyleSheet(
            "QPushButton { background: " + ACCENT + "; color: white; border: none; "
            "padding: 8px 14px; border-radius: 4px; } QPushButton:hover { background: " + ACCENT_DARK + "; }")
        load_btn.clicked.connect(self._on_load_csv)
        btn_col.addWidget(load_btn)
        resolve_btn = QPushButton("Resolve Names")
        resolve_btn.setStyleSheet(
            "QPushButton { background: " + MOSS_GREEN + "; color: white; border: none; "
            "padding: 8px 14px; border-radius: 4px; } QPushButton:hover { background: #3d6a4b; }")
        resolve_btn.clicked.connect(self._on_resolve)
        btn_col.addWidget(resolve_btn)
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(
            "QPushButton { color: " + WARM_GRAY + "; border: 1px solid " + WARM_GRAY + "; "
            "padding: 8px 14px; border-radius: 4px; } QPushButton:hover { background: #f0eeec; }")
        clear_btn.clicked.connect(self._on_clear)
        btn_col.addWidget(clear_btn)
        btn_col.addStretch()
        input_row.addLayout(btn_col)
        layout.addLayout(input_row)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Input Name", "Matched Name", "TVK", "Common Name", "Family"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget { border: 1px solid " + BORDER + "; gridline-color: " + SEPARATOR + "; font-size: 11px; }"
            "QHeaderView::section { background: " + BG + "; border: none; border-bottom: 2px solid "
            + BORDER + "; padding: 5px; font-weight: bold; font-size: 11px; }")
        layout.addWidget(self.table, 1)

        # Status + buttons
        bottom = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: " + TEXT_MUTED + "; font-size: 11px;")
        bottom.addWidget(self.status_label)
        bottom.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            "QPushButton { color: " + WARM_GRAY + "; border: 1px solid " + WARM_GRAY + "; "
            "padding: 6px 16px; border-radius: 4px; } QPushButton:hover { background: #f0eeec; }")
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)
        self.use_btn = QPushButton("Use for Analysis")
        self.use_btn.setEnabled(False)
        self.use_btn.setStyleSheet(
            "QPushButton { background: " + MOSS_GREEN + "; color: white; border: none; "
            "padding: 6px 16px; border-radius: 4px; } QPushButton:hover { background: #3d6a4b; }"
            "QPushButton:disabled { background: #d1d5db; color: #9ca3af; }")
        self.use_btn.clicked.connect(self.accept)
        bottom.addWidget(self.use_btn)
        layout.addLayout(bottom)

    def _on_load_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load species list", "", "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                reader = csv.reader(f)
                names = []
                for row in reader:
                    if not row:
                        continue
                    # Use first column, skip header-like rows
                    val = row[0].strip()
                    if val and val.lower() not in ("species", "species_name", "scientific_name", "name"):
                        names.append(val)
            self.text_edit.setPlainText("\n".join(names))
            self.status_label.setText(f"Loaded {len(names)} names from {Path(path).name}")
        except Exception as e:
            QMessageBox.warning(self, "Examen", f"Error reading file:\n{e}")

    def _on_resolve(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            return
        names = [n.strip() for n in text.splitlines() if n.strip()]
        if not names:
            return
        self._resolved = self._resolve_names(names)
        self._refresh_table()

    def _on_clear(self):
        self.text_edit.clear()
        self._resolved.clear()
        self.table.setRowCount(0)
        self.use_btn.setEnabled(False)
        self.status_label.setText("")

    def _resolve_names(self, names: list[str]) -> list[dict]:
        """Match input names against UKSI. Returns list of result dicts."""
        if not paths.UKSI_DB.exists():
            QMessageBox.warning(self, "Examen", "UKSI database not found.")
            return []
        conn = sqlite3.connect(str(paths.UKSI_DB))
        c = conn.cursor()
        results = []
        for name in names:
            # Exact match first
            c.execute("""SELECT t.scientific_name, t.tvk,
                                COALESCE(cn.common_name, '') as common, t.family
                         FROM taxa t LEFT JOIN common_names cn ON t.tvk = cn.tvk AND cn.preferred = 1
                         WHERE t.scientific_name = ? AND t.rank IN ('Species','Subspecies')
                         LIMIT 1""", (name,))
            row = c.fetchone()
            if row:
                results.append({"input": name, "name": row[0], "tvk": row[1],
                                "common": row[2], "family": row[3] or "", "matched": True})
                continue
            # Fuzzy: LIKE match
            c.execute("""SELECT t.scientific_name, t.tvk,
                                COALESCE(cn.common_name, '') as common, t.family
                         FROM taxa t LEFT JOIN common_names cn ON t.tvk = cn.tvk AND cn.preferred = 1
                         WHERE t.scientific_name LIKE ? AND t.rank IN ('Species','Subspecies')
                         ORDER BY t.sort_code LIMIT 1""", (f"%{name}%",))
            row = c.fetchone()
            if row:
                results.append({"input": name, "name": row[0], "tvk": row[1],
                                "common": row[2], "family": row[3] or "", "matched": True})
            else:
                results.append({"input": name, "name": "", "tvk": "", "common": "", "family": "", "matched": False})
        conn.close()
        return results

    def _refresh_table(self):
        self.table.setRowCount(len(self._resolved))
        matched = 0
        for i, r in enumerate(self._resolved):
            self.table.setItem(i, 0, QTableWidgetItem(r["input"]))
            name_item = QTableWidgetItem(r["name"])
            if not r["matched"]:
                name_item.setText("NOT FOUND")
                name_item.setForeground(QColor(RED_STATUS))
            self.table.setItem(i, 1, name_item)
            self.table.setItem(i, 2, QTableWidgetItem(r["tvk"]))
            self.table.setItem(i, 3, QTableWidgetItem(r["common"]))
            self.table.setItem(i, 4, QTableWidgetItem(r["family"]))
            if r["matched"]:
                matched += 1
        total = len(self._resolved)
        unmatched = total - matched
        self.status_label.setText(f"{matched} matched, {unmatched} unmatched of {total} names")
        self.use_btn.setEnabled(matched > 0)

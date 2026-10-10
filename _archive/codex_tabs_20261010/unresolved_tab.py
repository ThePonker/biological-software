"""Unresolved tab — view and manage species that failed UKSI resolution."""

import csv
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton
)

from . import theme

UNRESOLVED_PATH = Path("data/reviews/unresolved_species.csv")


class UnresolvedTab(QWidget):
    """View species that could not be resolved against UKSI."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("UNRESOLVED SPECIES")
        title.setStyleSheet(
            f"font-weight: 600; color: {theme.TEXT_HEADING}; "
            f"font-size: 11px; letter-spacing: 1px;"
        )
        header_row.addWidget(title)
        header_row.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 4px 12px;
                border: 1px solid {theme.BORDER};
                border-radius: {theme.RADIUS_SM};
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {theme.HOVER}; }}
        """)
        refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        # Info label
        self.info_label = QLabel(
            "Species listed here could not be matched to a UKSI taxon during import. "
            "They may need manual TVK mapping or represent taxonomy changes not yet in UKSI."
        )
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 12px;"
        )
        layout.addWidget(self.info_label)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Species Name", "Review", "Status", "Reason", "Notes"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {theme.BORDER};
                gridline-color: {theme.SEPARATOR};
                font-size: 12px;
            }}
            QTableWidget::item {{
                padding: 6px 8px;
            }}
            QHeaderView::section {{
                background-color: {theme.SURFACE_ALT};
                border: none;
                border-bottom: 1px solid {theme.BORDER};
                padding: 8px;
                font-weight: 600;
                font-size: 11px;
                color: {theme.TEXT_HEADING};
            }}
        """)
        layout.addWidget(self.table, 1)

        # Count label
        self.count_label = QLabel("")
        self.count_label.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 11px;"
        )
        layout.addWidget(self.count_label)

    def refresh(self):
        self.table.setRowCount(0)

        if not UNRESOLVED_PATH.exists():
            self.count_label.setText(
                "No unresolved species file found. All imports resolved successfully."
            )
            return

        entries = []
        try:
            with open(UNRESOLVED_PATH, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entries.append(row)
        except Exception as e:
            self.count_label.setText(f"Error reading file: {e}")
            return

        if not entries:
            self.count_label.setText("No unresolved species.")
            return

        self.table.setRowCount(len(entries))
        for i, entry in enumerate(entries):
            self.table.setItem(i, 0, QTableWidgetItem(
                entry.get("species_name", "")))
            self.table.setItem(i, 1, QTableWidgetItem(
                entry.get("review", "")))
            self.table.setItem(i, 2, QTableWidgetItem(
                entry.get("iucn_status", "")))
            self.table.setItem(i, 3, QTableWidgetItem(
                entry.get("reason", "")))
            self.table.setItem(i, 4, QTableWidgetItem(
                entry.get("notes", "")))

        self.count_label.setText(
            f"{len(entries)} unresolved species  |  "
            f"File: {UNRESOLVED_PATH}"
        )

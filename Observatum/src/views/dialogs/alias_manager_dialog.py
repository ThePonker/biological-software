"""
Species Alias Manager Dialog for Observatum V2.
Shows all saved species aliases in a table with delete capability.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt
from src.themes import theme
from src.services.species_alias_service import SpeciesAliasService


class AliasManagerDialog(QDialog):
    """Dialog to view and manage species aliases."""

    def __init__(self, db_manager=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.alias_service = SpeciesAliasService(db_manager=db_manager) if db_manager else None
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        t = theme()
        self.setWindowTitle("Species Alias Manager")
        self.setMinimumSize(800, 500)
        self.setStyleSheet(f"QDialog {{ background-color: {t.get('surface')}; }}")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel("Saved Species Aliases")
        header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {t.get('text_primary')};")
        layout.addWidget(header)

        desc = QLabel("These mappings are used during import to automatically resolve species names.")
        desc.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
        layout.addWidget(desc)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Input Name", "UKSI Name", "TVK", "Common Name", "Order", "Family"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                gridline-color: {t.get('border')};
            }}
            QTableWidget::item {{
                padding: 6px;
            }}
            QTableWidget::item:selected {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_primary')};
                padding: 8px;
                border: none;
                border-bottom: 1px solid {t.get('border')};
                font-weight: bold;
            }}
        """)
        layout.addWidget(self.table)

        # Count label
        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
        layout.addWidget(self.count_label)

        # Buttons
        btn_layout = QHBoxLayout()

        delete_btn = QPushButton("Delete Selected")
        delete_btn.setMinimumWidth(120)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('surface')};
                color: #a63d40;
                border: 1px solid #a63d40;
                border-radius: 4px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{ background-color: #fdf0f0; }}
        """)
        delete_btn.clicked.connect(self._delete_selected)
        btn_layout.addWidget(delete_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(90)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{ background-color: {t.get('hover')}; }}
        """)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _load_data(self):
        """Load aliases from database into table."""
        if not self.alias_service:
            self.count_label.setText("No database connection")
            return

        try:
            aliases = self.alias_service.get_all_aliases()
        except Exception as e:
            self.count_label.setText(f"Error: {e}")
            return

        self.table.setRowCount(len(aliases))
        for row, alias in enumerate(aliases):
            self.table.setItem(row, 0, QTableWidgetItem(alias.get("input_name", "")))
            self.table.setItem(row, 1, QTableWidgetItem(alias.get("uksi_name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(alias.get("uksi_tvk", "")))
            self.table.setItem(row, 3, QTableWidgetItem(alias.get("uksi_common_name", "")))
            self.table.setItem(row, 4, QTableWidgetItem(alias.get("uksi_order", "")))
            self.table.setItem(row, 5, QTableWidgetItem(alias.get("uksi_family", "")))

        self.count_label.setText(f"{len(aliases)} alias(es)")

    def _delete_selected(self):
        """Delete selected aliases."""
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return

        names = []
        for idx in selected:
            item = self.table.item(idx.row(), 0)
            if item:
                names.append(item.text())

        if not names:
            return

        reply = QMessageBox.question(
            self, "Delete Aliases",
            f"Delete {len(names)} alias(es)?\n\n" + "\n".join(names[:10]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        for name in names:
            if self.alias_service.delete_alias(name):
                deleted += 1

        self._load_data()

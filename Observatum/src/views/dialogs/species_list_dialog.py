"""Species List Dialog - Shows species with first/last recorded dates."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QTabWidget, QWidget, QScrollArea
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ...themes import theme
from ...utils.date_utils import format_date_display


class SpeciesListDialog(QDialog):
    """Dialog showing a list of species with first and last recorded dates."""

    def __init__(self, title: str, species_data: list, parent=None, show_families: bool = False):
        """Initialize the dialog.

        Args:
            title: Dialog title (e.g., "Species in Carabidae", "New Species in 2025")
            species_data: List of dicts with keys: species_name, first_date, last_date, (optional) family
            parent: Parent widget
            show_families: If True, add a "By Family" tab
        """
        super().__init__(parent)
        self._title = title
        self._species_data = species_data
        self._show_families = show_families
        self._letter_buttons = {}
        self._setup_ui()
        self._populate_table()
        self._update_letter_states()
        if show_families:
            self._populate_family_tab()

    def _setup_ui(self):
        """Set up the dialog UI."""
        t = theme()

        self.setWindowTitle(self._title)
        self.setMinimumSize(650, 500)
        self.resize(750, 1000)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {t.get('surface')};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header = QLabel(self._title)
        header.setFont(QFont(t.get('font_family', 'Segoe UI'), 14, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {t.get('text_primary')};")
        layout.addWidget(header)

        # Count label
        count_label = QLabel(f"{len(self._species_data)} species")
        count_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
        layout.addWidget(count_label)

        if self._show_families:
            # Tab widget for Species / By Family views
            self._tab_widget = QTabWidget()
            self._tab_widget.setStyleSheet(f"""
                QTabWidget::pane {{
                    border: 1px solid {t.get('border')};
                    border-radius: 4px;
                    background-color: {t.get('surface')};
                }}
                QTabBar::tab {{
                    background-color: {t.get('surface_alt')};
                    color: {t.get('text_primary')};
                    padding: 8px 16px;
                    border: 1px solid {t.get('border')};
                    border-bottom: none;
                    border-top-left-radius: 4px;
                    border-top-right-radius: 4px;
                    font-weight: bold;
                }}
                QTabBar::tab:selected {{
                    background-color: {t.get('surface')};
                    border-bottom: 2px solid {t.get('primary')};
                }}
                QTabBar::tab:hover {{
                    background-color: {t.get('hover')};
                }}
            """)

            # Species tab
            species_tab = QWidget()
            species_layout = QVBoxLayout(species_tab)
            species_layout.setContentsMargins(0, 8, 0, 0)
            self._build_alphabet_bar(species_layout)
            self.table = self._build_species_table()
            species_layout.addWidget(self.table)
            self._tab_widget.addTab(species_tab, "Species")

            # Family tab
            family_tab = QWidget()
            family_layout = QVBoxLayout(family_tab)
            family_layout.setContentsMargins(0, 8, 0, 0)
            self._family_scroll = QScrollArea()
            self._family_scroll.setWidgetResizable(True)
            self._family_scroll.setFrameShape(QFrame.Shape.NoFrame)
            self._family_scroll.setStyleSheet(f"""
                QScrollArea {{
                    background-color: {t.get('surface')};
                    border: none;
                }}
            """)
            self._family_content = QWidget()
            self._family_layout = QVBoxLayout(self._family_content)
            self._family_layout.setSpacing(16)
            self._family_layout.setContentsMargins(8, 8, 8, 8)
            self._family_scroll.setWidget(self._family_content)
            family_layout.addWidget(self._family_scroll)
            self._tab_widget.addTab(family_tab, "By Family")

            layout.addWidget(self._tab_widget)
        else:
            # No tabs - original layout
            self._build_alphabet_bar(layout)
            self.table = self._build_species_table()
            layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()
        
        # Export CSV button
        export_btn = QPushButton("Export CSV")
        export_btn.setMinimumWidth(100)
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get("surface")};
                color: {t.get("primary", "#4a7c59")};
                border: 1px solid {t.get("primary", "#4a7c59")};
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {t.get("primary", "#4a7c59")};
                color: white;
            }}
        """)
        export_btn.clicked.connect(self._export_csv)
        button_layout.addWidget(export_btn)
        button_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(100)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
                border-color: {t.get('text_secondary')};
            }}
            QPushButton:pressed {{
                background-color: {t.get('border')};
            }}
        """)
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def _export_csv(self):
        """Export species list to CSV."""
        from PySide6.QtWidgets import QFileDialog
        import csv, os
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Species List", 
            os.path.expanduser(f"~/Desktop/{self._title.replace(" ", "_")}.csv"),
            "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Species Name", "First Recorded", "Last Recorded"])
                for sp in self._species_data:
                    writer.writerow([
                        sp.get("species_name", ""),
                        sp.get("first_date", ""),
                        sp.get("last_date", "")
                    ])
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Exported", f"Exported {len(self._species_data)} species to:\n{path}")
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Export Failed", str(e))

    def _build_alphabet_bar(self, parent_layout):
        """Build the A-Z alphabet navigation bar."""
        t = theme()
        alphabet_frame = QFrame()
        alphabet_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface_alt')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 4px;
            }}
        """)
        alphabet_layout = QHBoxLayout(alphabet_frame)
        alphabet_layout.setSpacing(2)
        alphabet_layout.setContentsMargins(8, 6, 8, 6)

        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            btn = QPushButton(letter)
            btn.setFixedSize(26, 26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.get('surface')};
                    color: {t.get('text_primary')};
                    border: 1px solid {t.get('border')};
                    border-radius: 3px;
                    font-weight: bold;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: {t.get('hover')};
                    border-color: {t.get('primary')};
                }}
                QPushButton:pressed {{
                    background-color: {t.get('border')};
                }}
                QPushButton:disabled {{
                    background-color: {t.get('background')};
                    color: {t.get('text_muted')};
                    border-color: {t.get('border')};
                }}
            """)
            btn.clicked.connect(lambda checked, l=letter: self._scroll_to_letter(l))
            alphabet_layout.addWidget(btn)
            self._letter_buttons[letter] = btn

        alphabet_layout.addStretch()
        parent_layout.addWidget(alphabet_frame)

    def _build_species_table(self):
        """Build and return the species QTableWidget."""
        t = theme()
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Species Name", "First Recorded", "Last Recorded"])
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSortingEnabled(True)
        table.verticalHeader().setVisible(False)

        header_view = table.horizontalHeader()
        header_view.setStretchLastSection(True)
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSortIndicatorShown(True)

        table.setStyleSheet(self._table_stylesheet())
        return table

    def _table_stylesheet(self):
        """Return shared table stylesheet."""
        t = theme()
        return f"""
            QTableWidget {{
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                gridline-color: {t.get('border')};
            }}
            QTableWidget::item {{
                padding: 8px;
                color: {t.get('text_primary')};
            }}
            QTableWidget::item:selected {{
                background-color: {t.get('hover')};
                color: {t.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_primary')};
                padding: 8px;
                border: none;
                border-bottom: 2px solid {t.get('border')};
                border-right: 1px solid {t.get('border')};
                font-weight: bold;
            }}
            QHeaderView::section:hover {{
                background-color: {t.get('hover')};
            }}
            QTableWidget::item:alternate {{
                background-color: {t.get('surface_alt')};
            }}
            QScrollBar:vertical {{
                background-color: {t.get('surface')};
                width: 12px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background-color: {t.get('border')};
                border-radius: 4px;
                min-height: 30px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {t.get('text_secondary')};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background-color: {t.get('surface')};
                height: 12px;
                border: none;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {t.get('border')};
                border-radius: 4px;
                min-width: 30px;
                margin: 2px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {t.get('text_secondary')};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """

    def _populate_table(self):
        """Populate the table with species data."""
        t = theme()
        self.table.setRowCount(len(self._species_data))

        for row, species in enumerate(self._species_data):
            name = species.get('species_name', '')
            name_item = QTableWidgetItem(name)
            name_item.setFont(QFont(t.get('font_family', 'Segoe UI'), 10, QFont.Weight.Normal, italic=True))
            self.table.setItem(row, 0, name_item)

            first_date = species.get('first_date', '')
            first_item = QTableWidgetItem(self._format_date(first_date))
            first_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, first_item)

            last_date = species.get('last_date', '')
            if last_date and last_date != first_date:
                last_item = QTableWidgetItem(self._format_date(last_date))
            else:
                last_item = QTableWidgetItem('-')
            last_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, last_item)

    def _populate_family_tab(self):
        """Populate the By Family tab with species grouped by family."""
        t = theme()

        # Group species by family
        families = {}
        for sp in self._species_data:
            family = sp.get('family', 'Unknown') or 'Unknown'
            if family not in families:
                families[family] = []
            families[family].append(sp)

        # Sort families by species count (descending), then alphabetically
        sorted_families = sorted(families.items(), key=lambda x: (-len(x[1]), x[0]))

        for family_name, species_list in sorted_families:
            # Family header
            family_header = QLabel(f"{family_name} ({len(species_list)} species)")
            family_header.setFont(QFont(t.get('font_family', 'Segoe UI'), 11, QFont.Weight.Bold))
            family_header.setStyleSheet(f"""
                color: {t.get('text_primary')};
                background-color: {t.get('surface_alt')};
                padding: 8px 12px;
                border: 1px solid {t.get('border')};
                border-radius: 4px;
            """)
            self._family_layout.addWidget(family_header)

            # Species table for this family
            family_table = QTableWidget()
            family_table.setColumnCount(3)
            family_table.setHorizontalHeaderLabels(["Species Name", "First Recorded", "Last Recorded"])
            family_table.setAlternatingRowColors(True)
            family_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            family_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
            family_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            family_table.verticalHeader().setVisible(False)

            header_view = family_table.horizontalHeader()
            header_view.setStretchLastSection(True)
            header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

            family_table.setStyleSheet(self._table_stylesheet())

            # Sort species alphabetically within family
            species_sorted = sorted(species_list, key=lambda x: x.get('species_name', ''))
            family_table.setRowCount(len(species_sorted))

            for row, sp in enumerate(species_sorted):
                name = sp.get('species_name', '')
                name_item = QTableWidgetItem(name)
                name_item.setFont(QFont(t.get('font_family', 'Segoe UI'), 10, QFont.Weight.Normal, italic=True))
                family_table.setItem(row, 0, name_item)

                first_date = sp.get('first_date', '')
                first_item = QTableWidgetItem(self._format_date(first_date))
                first_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                family_table.setItem(row, 1, first_item)

                last_date = sp.get('last_date', '')
                if last_date and last_date != first_date:
                    last_item = QTableWidgetItem(self._format_date(last_date))
                else:
                    last_item = QTableWidgetItem('-')
                last_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                family_table.setItem(row, 2, last_item)

            # Set table height to fit content (max 300px)
            row_height = 30
            header_height = 30
            table_height = min(len(species_sorted) * row_height + header_height + 4, 300)
            family_table.setFixedHeight(table_height)

            self._family_layout.addWidget(family_table)

        self._family_layout.addStretch()

    def _format_date(self, date_str: str) -> str:
        """Format date string for display."""
        if not date_str:
            return '-'
        formatted = format_date_display(date_str, "user")
        return formatted if formatted else date_str

    def _update_letter_states(self):
        """Enable/disable letter buttons based on available species."""
        available_letters = set()
        for species in self._species_data:
            name = species.get('species_name', '')
            if name:
                first_letter = name[0].upper()
                if first_letter.isalpha():
                    available_letters.add(first_letter)

        for letter, btn in self._letter_buttons.items():
            btn.setEnabled(letter in available_letters)

    def _scroll_to_letter(self, letter: str):
        """Scroll table to first species starting with the given letter."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                name = item.text()
                if name and name[0].upper() == letter:
                    self.table.scrollToItem(item, QTableWidget.ScrollHint.PositionAtTop)
                    self.table.selectRow(row)
                    break

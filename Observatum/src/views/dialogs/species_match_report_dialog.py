"""
Species Match Report Dialog.

Shows a summary of how each unique species was matched during import validation.
Accessible from the confirmation page of the specimen import wizard.
"""

from typing import List, Dict, Tuple

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QAbstractItemView,
    QFrame, QFileDialog, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from ....themes import theme
from ....core.config import ButtonColors


class SpeciesMatchReportDialog(QDialog):
    """Shows species matching results grouped by match type."""

    def __init__(self, validated_rows, parent=None, uksi_model=None):
        super().__init__(parent)
        self.setWindowTitle("Species Matching Report")
        self.setMinimumSize(850, 550)
        self.resize(900, 600)

        self._rows = validated_rows
        self._uksi_model = uksi_model
        self._match_data = []
        self._analyse_matches()
        self._setup_ui()

    def _analyse_matches(self):
        """Analyse validated rows to build species-level match summary."""
        seen = {}  # original_name -> match info

        for row in self._rows:
            # Get original name from raw_data
            original = ''
            if hasattr(row, 'raw_data') and row.raw_data:
                # Try common CSV column names for species
                for key in ['species_name', 'Species', 'species', 'Scientific Name',
                            'scientific_name', 'Taxon', 'taxon', 'Species Name']:
                    val = row.raw_data.get(key, '').strip()
                    if val:
                        original = val
                        break

            if not original:
                continue

            # Skip if already processed this species
            if original.lower() in seen:
                seen[original.lower()]['count'] += 1
                continue

            matched = row.species_name or ''
            tvk = row.species_tvk or ''
            family = row.family or ''
            order = row.order_name or ''
            common = row.common_name or ''
            notes = row.import_notes or ''
            has_error = row.status.name == 'ERROR' if hasattr(row.status, 'name') else False

            # Determine match type
            match_type = self._classify_match(original, matched, tvk, notes, has_error)

            seen[original.lower()] = {
                'original': original,
                'matched': matched if matched != original else matched,
                'tvk': tvk,
                'family': family,
                'order': order,
                'common': common,
                'match_type': match_type,
                'notes': notes,
                'count': 1,
            }

        self._match_data = sorted(seen.values(), key=lambda x: (
            self._type_sort_order(x['match_type']), x['original'].lower()
        ))

    @staticmethod
    def _classify_match(original: str, matched: str, tvk: str,
                        notes: str, has_error: bool) -> str:
        """Classify the match type from available data."""
        if not tvk and has_error:
            return "Unmatched"
        if not tvk:
            return "Unmatched"

        notes_lower = notes.lower()
        if 'cf.' in notes_lower or 'cf. =' in notes_lower:
            return "cf. resolved"
        if 'agg' in notes_lower or 'sensu lato' in notes_lower:
            return "Aggregate"
        if 'bulk lookup' in notes_lower or 'resolved via' in notes_lower:
            return "Manual resolution"
        if 'alias' in notes_lower:
            return "Alias"

        # Compare original to matched (case-insensitive)
        if original.lower().strip() == matched.lower().strip():
            return "Direct"
        else:
            return "Synonym"

    @staticmethod
    def _type_sort_order(match_type: str) -> int:
        """Sort order for match types — problems first."""
        order = {
            "Unmatched": 0,
            "Manual resolution": 1,
            "cf. resolved": 2,
            "Aggregate": 3,
            "Alias": 4,
            "Synonym": 5,
            "Direct": 6,
        }
        return order.get(match_type, 5)

    def _setup_ui(self):
        t = theme()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel("Species Matching Report")
        title.setStyleSheet(
            f"color: {t.get('text_heading')}; font-size: 16px; font-weight: bold;"
        )
        layout.addWidget(title)

        # Summary counts
        summary_frame = QFrame()
        summary_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(12, 8, 12, 8)

        counts = {}
        total_specimens = 0
        for item in self._match_data:
            mt = item['match_type']
            counts[mt] = counts.get(mt, 0) + 1
            total_specimens += item['count']

        total_species = len(self._match_data)
        matched_species = sum(1 for m in self._match_data if m['match_type'] != 'Unmatched')

        summary_text = f"{matched_species}/{total_species} species matched"
        if total_specimens != total_species:
            summary_text += f" ({total_specimens:,} specimens)"

        summary_label = QLabel(summary_text)
        summary_label.setStyleSheet(
            f"color: {t.get('text_primary')}; font-size: 13px; font-weight: 600; border: none;"
        )
        summary_layout.addWidget(summary_label)
        summary_layout.addStretch()

        # Individual type counts
        type_colours = {
            "Direct": t.get('success'),
            "Synonym": "#2196F3",
            "Alias": "#9C27B0",
            "cf. resolved": "#FF9800",
            "Aggregate": "#FF9800",
            "Manual resolution": "#FF9800",
            "Unmatched": t.get('error'),
        }

        for mt in ["Direct", "Synonym", "Alias", "cf. resolved", "Aggregate",
                    "Manual resolution", "Unmatched"]:
            if mt in counts:
                chip = QLabel(f" {mt}: {counts[mt]} ")
                colour = type_colours.get(mt, t.get('text_secondary'))
                chip.setStyleSheet(
                    f"color: {colour}; font-size: 11px; font-weight: 600; border: none;"
                )
                summary_layout.addWidget(chip)

        layout.addWidget(summary_frame)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "CSV Name", "Matched To", "Family", "Order",
            "Common Name", "Match Type", "Specimens"
        ])
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._table.setColumnWidth(0, 180)
        self._table.setColumnWidth(1, 180)
        self._table.setColumnWidth(2, 120)
        self._table.setColumnWidth(3, 100)
        self._table.setColumnWidth(4, 140)
        self._table.setColumnWidth(5, 110)
        self._table.setColumnWidth(6, 60)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {t.get('border')};
                border-radius: 6px;
                background-color: {t.get('surface')};
                gridline-color: {t.get('border')};
                font-size: 12px;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                padding: 6px;
                border: none;
                border-bottom: 1px solid {t.get('border')};
                font-weight: 600;
                font-size: 11px;
            }}
        """)

        self._populate_table()
        self._table.setToolTip("Double-click a species to change its match")
        self._table.cellDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self._table)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        export_btn = QPushButton("Export CSV")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {ButtonColors.PRIMARY};
                border: 1px solid {ButtonColors.PRIMARY};
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {ButtonColors.PRIMARY};
                color: white;
            }}
        """)
        export_btn.clicked.connect(self._export_csv)
        btn_layout.addWidget(export_btn)

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ButtonColors.PRIMARY};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 20px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #3d6b4a;
            }}
        """)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _populate_table(self):
        """Fill the table with match data."""
        t = theme()
        self._table.setRowCount(len(self._match_data))

        type_colours = {
            "Direct": t.get('success'),
            "Synonym": "#2196F3",
            "Alias": "#9C27B0",
            "cf. resolved": "#FF9800",
            "Aggregate": "#FF9800",
            "Manual resolution": "#FF9800",
            "Unmatched": t.get('error'),
        }

        for row_idx, item in enumerate(self._match_data):
            # CSV Name
            csv_item = QTableWidgetItem(item['original'])
            self._table.setItem(row_idx, 0, csv_item)

            # Matched To
            matched_item = QTableWidgetItem(item['matched'] if item['match_type'] != 'Unmatched' else '—')
            if item['match_type'] == 'Unmatched':
                matched_item.setForeground(QColor(t.get('text_muted')))
            elif item['original'].lower() != item['matched'].lower():
                matched_item.setFont(QFont("", -1, QFont.Weight.Bold))
            self._table.setItem(row_idx, 1, matched_item)

            # Family
            self._table.setItem(row_idx, 2, QTableWidgetItem(item['family']))

            # Order
            self._table.setItem(row_idx, 3, QTableWidgetItem(item['order']))

            # Common Name
            self._table.setItem(row_idx, 4, QTableWidgetItem(item['common']))

            # Match Type
            type_item = QTableWidgetItem(item['match_type'])
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            colour = type_colours.get(item['match_type'], t.get('text_secondary'))
            type_item.setForeground(QColor(colour))
            type_item.setFont(QFont("", -1, QFont.Weight.Bold))
            self._table.setItem(row_idx, 5, type_item)

            # Specimen count
            count_item = QTableWidgetItem(str(item['count']))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row_idx, 6, count_item)

    def _on_row_double_clicked(self, row: int, col: int):
        """Open species search to re-match a species."""
        if row >= len(self._match_data):
            return

        item = self._match_data[row]
        original_name = item['original']

        if not self._uksi_model:
            return

        from .species_search_dialog import SpeciesSearchDialog
        dialog = SpeciesSearchDialog(
            parent=self,
            uksi_model=self._uksi_model,
            initial_text=original_name
        )
        dialog.setWindowTitle(f"Re-match: {original_name}")
        result = dialog.exec()
        selected = dialog.get_selected_species()
        if selected:
            self._apply_rematch(original_name, selected)

    def _apply_rematch(self, original_name: str, uksi_data: dict):
        """Apply a new species match to all rows with this original name."""
        new_name = uksi_data.get('scientific_name', '') or getattr(uksi_data, 'scientific_name', '')
        new_tvk = uksi_data.get('tvk', '') or getattr(uksi_data, 'tvk', '')
        new_common = uksi_data.get('common_name', '') or getattr(uksi_data, 'common_name', '')
        new_order = uksi_data.get('order_name', '') or getattr(uksi_data, 'order_name', '')
        new_family = uksi_data.get('family', '') or getattr(uksi_data, 'family', '')


        count = 0
        for row in self._rows:
            # Match by: current species_name on row, OR original CSV name in raw_data
            row_name = (row.species_name or '').strip()
            csv_name = ''
            if hasattr(row, 'raw_data') and row.raw_data:
                for key in ['species_name', 'Species', 'species', 'Scientific Name',
                            'scientific_name', 'Taxon', 'taxon', 'Species Name']:
                    val = row.raw_data.get(key, '').strip()
                    if val:
                        csv_name = val
                        break

            if count < 3 and csv_name and (
                    csv_name.lower() == original_name.lower() or
                    row_name.lower() == original_name.lower()):
                row.species_name = new_name
                row.species_tvk = new_tvk
                row.common_name = new_common
                row.order_name = new_order
                row.family = new_family
                row.import_notes = f"Re-matched: '{original_name}' → '{new_name}'"

                # Clear old match info and set new message
                row.error_message = ''
                row.warnings = [f"Re-matched to '{new_name}'"]

                # Update status
                from .validation_worker import RowStatus
                if row.species_tvk:
                    if row.warnings:
                        row.status = RowStatus.WARNING
                    else:
                        row.status = RowStatus.VALID

                count += 1


        # Re-analyse and refresh table
        self._match_data = []
        self._analyse_matches()
        self._table.setRowCount(0)
        self._populate_table()

        # Update summary
        # Find and update the summary label
        for child in self.findChildren(QLabel):
            if 'species matched' in (child.text() or ''):
                matched = sum(1 for m in self._match_data if m['match_type'] != 'Unmatched')
                total = len(self._match_data)
                child.setText(f"{matched}/{total} species matched ({count} specimens updated)")
                break

    def _export_csv(self):
        """Export the match report to CSV."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Species Match Report",
            "species_match_report.csv",
            "CSV Files (*.csv)"
        )
        if not path:
            return

        import csv
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                "CSV Name", "Matched To", "TVK", "Family", "Order",
                "Common Name", "Match Type", "Specimens", "Notes"
            ])
            for item in self._match_data:
                writer.writerow([
                    item['original'],
                    item['matched'] if item['match_type'] != 'Unmatched' else '',
                    item['tvk'],
                    item['family'],
                    item['order'],
                    item['common'],
                    item['match_type'],
                    item['count'],
                    item['notes'],
                ])

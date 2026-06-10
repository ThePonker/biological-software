"""
Wizard File Handlers Mixin for Specimen Import Wizard.

Contains file loading, column mapping, preview, and export methods.
"""

import csv
from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QFrame
)

from .validation_worker import RowStatus

from ...themes import theme


class WizardFileMixin:
    """Mixin providing file handling methods for SpecimenImportWizard."""
    
    def _browse_file(self):
        """Open file browser dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Specimen Data File",
            "",
            "Data Files (*.tsv *.csv *.txt);;All Files (*)"
        )
        
        if file_path:
            self._load_file(file_path)
    
    def _load_file(self, file_path: str):
        """Load and parse the selected file."""
        t = theme()
        
        self.file_path = file_path
        self.file_path_label.setText(file_path)
        self.file_path_label.setStyleSheet(f"""
            padding: 12px;
            background-color: {t.get('success_bg')};
            border: 1px solid {t.get('success')};
            border-radius: {t.get('radius_md')};
            color: {t.get('success_text')};
        """)
        
        try:
            # Detect delimiter
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                sample = f.read(4096)
            
            tab_count = sample.count('\t')
            comma_count = sample.count(',')
            delimiter = '\t' if tab_count > comma_count else ','
            
            # Read file
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                self.columns = reader.fieldnames or []
                self.raw_rows = list(reader)
            
            # Update UI
            row_count = len(self.raw_rows)
            self.file_info_label.setText(
                f"✓ Loaded {row_count} rows with {len(self.columns)} columns"
            )
            
            self._update_preview_table()
            self.next_btn.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{str(e)}")
            self.file_info_label.setText(f"Error: {str(e)}")
            self.file_info_label.setStyleSheet(f"color: {t.get('error')};")
    
    def _update_preview_table(self):
        """Update the preview table with first few rows."""
        preview_rows = self.raw_rows[:5]
        
        self.preview_table.setColumnCount(len(self.columns))
        self.preview_table.setRowCount(len(preview_rows))
        self.preview_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.preview_table.setHorizontalHeaderLabels(self.columns)
        
        for row_idx, row_data in enumerate(preview_rows):
            for col_idx, col_name in enumerate(self.columns):
                value = row_data.get(col_name, '')
                self.preview_table.setItem(row_idx, col_idx, QTableWidget, QTableWidgetItem(value))
        
        self.preview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
    
    def _setup_column_mapping(self):
        """Set up the column mapping UI based on loaded columns."""
        t = theme()
        
        # Clear existing mappings
        while self.mapping_layout.count():
            item = self.mapping_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.mapping_combos.clear()
        
        # Database fields to map
        db_fields = [
            ('species_name', 'Scientific Name *', True),
            ('date_collected', 'Date Collected *', True),
            ('grid_ref', 'Grid Reference *', True),
            ('site_name', 'Site/Location Name', False),
            ('collector', 'Collector', False),
            ('determiner', 'Determiner', False),
        ]
        
        # Create mapping rows
        for field_id, field_label, required in db_fields:
            row_layout = QHBoxLayout()
            
            label = QLabel(field_label)
            label.setMinimumWidth(150)
            if required:
                label.setStyleSheet("font-weight: 600;")
            row_layout.addWidget(label)
            
            arrow = QLabel("←")
            arrow.setStyleSheet(f"color: {t.get('text_muted')};")
            row_layout.addWidget(arrow)
            
            combo = QComboBox()
            combo.setMinimumWidth(200)
            combo.addItem("-- Not mapped --", "")
            
            # Auto-match columns
            best_match = self._find_best_column_match(field_id)
            
            for col in self.columns:
                combo.addItem(col, col)
            
            if best_match:
                idx = combo.findData(best_match)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            
            row_layout.addWidget(combo, 1)
            self.mapping_combos[field_id] = combo
            self.mapping_layout.addLayout(row_layout)
        
        # Add separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {t.get('border')}; margin: 16px 0;")
        self.mapping_layout.addWidget(sep)
        
        # Info about auto-populated fields
        auto_label = QLabel(
            "The following fields will be auto-populated:\n"
            "• Order, Family, Subfamily → from UKSI (based on species name)\n"
            "• Vice County → from Grid Reference"
        )
        auto_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-style: italic;")
        self.mapping_layout.addWidget(auto_label)
        
        self.mapping_layout.addStretch()
    
    def _find_best_column_match(self, field_id: str) -> Optional[str]:
        """Try to auto-match a database field to a file column."""
        patterns = {
            'species_name': ['scientific name', 'species', 'taxon', 'name'],
            'date_collected': ['date', 'date collected', 'collection date'],
            'grid_ref': ['grid ref', 'grid reference', 'gridref', 'gr'],
            'site_name': ['location', 'site', 'site name', 'locality'],
            'collector': ['collector', 'col', 'collected by', 'coll'],
            'determiner': ['determiner', 'det', 'determined by', 'identifier'],
        }
        
        search_patterns = patterns.get(field_id, [])
        
        for col in self.columns:
            col_lower = col.lower().strip()
            for pattern in search_patterns:
                if pattern in col_lower or col_lower in pattern:
                    return col
        
        return None
    
    def _get_column_mapping(self) -> Dict[str, str]:
        """Get the current column mapping from combos."""
        mapping = {}
        for field_id, combo in self.mapping_combos.items():
            col_name = combo.currentData()
            if col_name:
                mapping[field_id] = col_name
        return mapping
    
    def _export_problems(self):
        """Export problem rows to CSV for manual correction."""
        problems = [r for r in self.validated_rows
                    if r.status in (RowStatus.ERROR, RowStatus.WARNING)]
        
        if not problems:
            QMessageBox.information(self, "No Problems", "No problem rows to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Problem Rows",
            "specimen_import_problems.csv",
            "CSV Files (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['_Status', '_Row', '_Error'] + self.columns
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for row in problems:
                    output_row = {
                        '_Status': row.status.value,
                        '_Row': row.row_number,
                        '_Error': row.error_message,
                    }
                    output_row.update(row.raw_data)
                    writer.writerow(output_row)
            
            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported {len(problems)} problem rows to:\n{file_path}"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")

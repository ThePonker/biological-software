"""
Wizard File Mixin for Observation Import Wizard.

Contains file loading, iRecord format detection, column mapping,
and problem export methods.
"""

import csv
from typing import Dict, Optional

from PySide6.QtWidgets import (
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QHBoxLayout, QLabel, QComboBox, QFrame
)

from ..import_common.problem_export import ProblemExportMixin
from .validation_worker import ImportMode

from src.themes import theme


# iRecord column headers for auto-detection
IRECORD_REQUIRED_COLUMNS = {
    'ID', 'RecordKey', 'Taxon', 'TaxonVersionKey', 'Site name',
    'Latitude', 'Longitude', 'Date interpreted', 'Recorder',
    'Verification status 1'
}

# iRecord column mappings (CSV header -> internal display name)
IRECORD_COLUMN_MAP = {
    'ID': 'iRecord ID',
    'RecordKey': 'Record Key',
    'External key': 'External Key',
    'Source': 'Source',
    'Rank': 'Taxon Rank',
    'Taxon': 'Species Name',
    'Common name': 'Common Name',
    'Taxon group': 'Taxon Group',
    'Kingdom': 'Kingdom',
    'Order': 'Order',
    'Family': 'Family',
    'TaxonVersionKey': 'TVK',
    'Site name': 'Site Name',
    'Sensitive site': 'Sensitive Site',
    'Original map ref': 'Original Grid Ref',
    'Latitude': 'Latitude',
    'Longitude': 'Longitude',
    'Projection (input)': 'Projection',
    'Precision': 'Precision',
    'Output map ref': 'Grid Ref',
    'Projection (output)': 'Output Projection',
    'Sensitive output map ref': 'Sensitive Grid Ref',
    'Biotope': 'Biotope',
    'VC number': 'VC Number',
    'Vice County': 'Vice County',
    'Date interpreted': 'Date',
    'Date from': 'Date From',
    'Date to': 'Date To',
    'Date type': 'Date Type',
    'Sample method': 'Sample Method',
    'Recorder': 'Recorder',
    'Determiner': 'Determiner',
    'Recorder certainty': 'Certainty',
    'Sex': 'Sex',
    'Stage': 'Stage',
    'Count of sex or stage': 'Quantity',
    'Zero abundance': 'Zero Abundance',
    'Sensitive': 'Sensitive',
    'Comment': 'Comment',
    'Sample comment': 'Sample Comment',
    'Images': 'Images',
    'Input on date': 'Input Date',
    'Last edited on date': 'Last Edited',
    'Verification status 1': 'Verification Status',
    'Verification status 2': 'Verification Status 2',
    'Query': 'Query',
    'Verifier': 'Verifier',
    'Verified on': 'Verified On',
    'Licence': 'Licence',
    'Automated checks': 'Automated Checks',
}

# Personal template expected columns and their database field mappings
# Headings matched by WHOLE words, each heading once (IMP-11, 10 Oct 2026); '=x' must be the
# whole heading. 'name', 'gr', 'det', 'rec' and 'number' used to match inside other words.
PERSONAL_COLUMN_PATTERNS = {
    'species_name': ['species', 'species name', 'scientific name', 'taxon', 'taxon name', '=name'],
    'date': ['date', 'date collected', 'observation date', 'date observed'],
    'grid_ref': ['grid ref', 'grid reference', 'gridref', 'grid', '=gr', 'osgr'],
    'site_name': ['site name', 'site', 'location', 'locality', 'place'],
    'recorder': ['recorder', 'observer', 'recorded by', '=rec'],
    'determiner': ['determiner', '=det', 'determined by', 'identifier', 'identified by'],
    'sex': ['sex', 'gender'],
    'stage': ['stage', 'life stage', 'lifestage'],
    'quantity': ['quantity', 'count', '=number', '=qty', 'abundance'],
    'certainty': ['certainty', 'confidence', 'recorder certainty'],
    'method': ['method', 'sample method', 'sampling method', 'technique'],
    'comment': ['comment', 'comments', 'notes', 'remarks'],
}

# Database fields for personal template mapping UI
PERSONAL_DB_FIELDS = [
    ('species_name', 'Species Name *', True),
    ('date', 'Date *', True),
    ('grid_ref', 'Grid Reference *', True),
    ('site_name', 'Site/Location Name', False),
    ('recorder', 'Recorder *', True),
    ('determiner', 'Determiner', False),
    ('sex', 'Sex', False),
    ('stage', 'Stage', False),
    ('quantity', 'Quantity', False),
    ('certainty', 'Certainty', False),
    ('method', 'Sample Method', False),
    ('comment', 'Comment', False),
]


class WizardFileMixin(ProblemExportMixin):
    """Mixin providing file handling methods for ObservationImportWizard."""

    PROBLEMS_FILE_NAME = "observation_import_problems.csv"     # _export_problems: import_common (C4)
    
    def _browse_file(self):
        """Open file browser dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Observation Data File",
            "",
            "CSV Files (*.csv);;All Files (*)"
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
            # Detect encoding and delimiter
            file_encoding = "utf-8-sig"
            try:
                with open(file_path, "r", encoding="utf-8-sig") as f:
                    sample = f.read(4096)
            except UnicodeDecodeError:
                file_encoding = "latin-1"
                with open(file_path, "r", encoding="latin-1") as f:
                    sample = f.read(4096)

            tab_count = sample.count("\t")
            comma_count = sample.count(",")
            delimiter = "\t" if tab_count > comma_count else ","

            # Read file
            with open(file_path, "r", encoding=file_encoding) as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                self.columns = reader.fieldnames or []
                self.raw_rows = list(reader)
            
            # Check if this is an iRecord file
            self.is_irecord_format = self._detect_irecord_format()
            
            # Update UI
            row_count = len(self.raw_rows)
            format_note = " (iRecord format detected)" if self.is_irecord_format else ""
            self.file_info_label.setText(
                f"✓ Loaded {row_count} rows with {len(self.columns)} columns{format_note}"
            )
            self.file_info_label.setStyleSheet(f"color: {t.get('success')};")
            
            self._update_preview_table()
            self.next_btn.setEnabled(True)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{str(e)}")
            self.file_info_label.setText(f"Error: {str(e)}")
            self.file_info_label.setStyleSheet(f"color: {t.get('error')};")
            self.next_btn.setEnabled(False)
    
    def _detect_irecord_format(self) -> bool:
        """Check if the loaded file is in iRecord format."""
        if not self.columns:
            return False
        
        column_set = set(self.columns)
        matches = column_set.intersection(IRECORD_REQUIRED_COLUMNS)
        
        # If we have at least 7 of the required columns, it's iRecord
        return len(matches) >= 7
    
    def _update_preview_table(self):
        """Update the preview table with first few rows."""
        preview_rows = self.raw_rows[:5]
        
        # Limit columns shown in preview
        display_cols = self.columns[:10]
        
        self.preview_table.setColumnCount(len(display_cols))
        self.preview_table.setRowCount(len(preview_rows))
        self.preview_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.preview_table.setHorizontalHeaderLabels(display_cols)
        
        for row_idx, row_data in enumerate(preview_rows):
            for col_idx, col_name in enumerate(display_cols):
                value = row_data.get(col_name, '')
                # Truncate long values
                if len(value) > 50:
                    value = value[:47] + "..."
                self.preview_table.setItem(row_idx, col_idx, QTableWidgetItem(value))
        
        self.preview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
    
    def _setup_column_mapping(self):
        """Set up the column mapping UI based on loaded columns and import mode."""
        t = theme()
        
        # Clear existing mappings
        while self.mapping_layout.count():
            item = self.mapping_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
        
        self.mapping_combos.clear()
        
        # Get selected import mode
        selected_mode = self._get_selected_mode()
        
        if selected_mode == ImportMode.IRECORD_SYNC:
            self._setup_irecord_mapping()
        else:
            self._setup_personal_mapping()
    
    def _clear_layout(self, layout):
        """Recursively clear a layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
    
    def _setup_irecord_mapping(self):
        """Set up column mapping for iRecord format (auto-mapped, read-only display)."""
        t = theme()
        
        # Update instructions
        self.mapping_instructions.setText(
            "iRecord format detected. All columns are automatically mapped.\n"
            "Review the mappings below - no changes needed."
        )
        
        # Show auto-mapped columns in groups
        groups = [
            ("Identification", ['ID', 'RecordKey', 'Taxon', 'Common name', 'TaxonVersionKey']),
            ("Location", ['Site name', 'Output map ref', 'VC number', 'Vice County', 'Latitude', 'Longitude']),
            ("Date & Recorder", ['Date interpreted', 'Recorder', 'Determiner', 'Recorder certainty']),
            ("Occurrence", ['Sex', 'Stage', 'Count of sex or stage', 'Sample method']),
            ("Verification", ['Verification status 1', 'Verification status 2', 'Verifier', 'Verified on']),
            ("Other", ['Comment', 'Sample comment', 'Images', 'Sensitive']),
        ]
        
        for group_name, fields in groups:
            # Group header
            header = QLabel(group_name)
            header.setStyleSheet(f"font-weight: 600; color: {self._accent_dark}; margin-top: 8px;")
            self.mapping_layout.addWidget(header)
            
            # Fields in group
            for field in fields:
                if field in self.columns:
                    display_name = IRECORD_COLUMN_MAP.get(field, field)
                    row_layout = QHBoxLayout()
                    
                    csv_label = QLabel(field)
                    csv_label.setMinimumWidth(180)
                    csv_label.setStyleSheet(f"color: {t.get('text_secondary')};")
                    row_layout.addWidget(csv_label)
                    
                    arrow = QLabel("→")
                    arrow.setStyleSheet(f"color: {t.get('text_muted')};")
                    row_layout.addWidget(arrow)
                    
                    db_label = QLabel(display_name)
                    db_label.setStyleSheet(f"color: {t.get('success')}; font-weight: 500;")
                    row_layout.addWidget(db_label, 1)
                    
                    self.mapping_layout.addLayout(row_layout)
        
        self.mapping_layout.addStretch()
    
    def _setup_personal_mapping(self):
        """Set up column mapping for personal template format."""
        t = theme()
        
        # Update instructions
        self.mapping_instructions.setText(
            "Map your file columns to the observation database fields.\n"
            "Required fields are marked with *. Taxonomy will be auto-populated from UKSI."
        )
        
        # Create mapping rows for each database field
        for field_id, field_label, required in PERSONAL_DB_FIELDS:
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
            
            # Add all file columns
            for col in self.columns:
                combo.addItem(col, col)
            
            # Auto-match
            best_match = self._find_best_column_match(field_id)
            if best_match:
                idx = combo.findData(best_match)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            
            row_layout.addWidget(combo, 1)
            self.mapping_combos[field_id] = combo
            self.mapping_layout.addLayout(row_layout)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {t.get('border')}; margin: 16px 0;")
        self.mapping_layout.addWidget(sep)
        
        # Auto-populate info
        auto_label = QLabel(
            "The following fields will be auto-populated:\n"
            "• TVK, Common Name, Order, Family, Kingdom, Taxon Group → from UKSI\n"
            "• Vice County, VC Number → from Grid Reference"
        )
        auto_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-style: italic;")
        self.mapping_layout.addWidget(auto_label)
        
        self.mapping_layout.addStretch()
    
    def _find_best_column_match(self, field_id: str) -> Optional[str]:
        """The file column auto-matched to a field (whole words, each column once -- IMP-11)."""
        from shared.import_core import auto_map_columns
        return auto_map_columns(self.columns, PERSONAL_COLUMN_PATTERNS).get(field_id)
    
    def _get_column_mapping(self) -> Dict[str, str]:
        """Get the current column mapping from combos."""
        mapping = {}
        for field_id, combo in self.mapping_combos.items():
            col_name = combo.currentData()
            if col_name:
                mapping[field_id] = col_name
        return mapping

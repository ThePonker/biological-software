"""
Wizard File Mixin for Recording Scheme Import Wizard.

Contains file handling, CSV parsing, format detection,
and column mapping functionality.
"""

from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QFileDialog, QLabel, QComboBox, QHBoxLayout, QFrame, QTableWidget, QTableWidgetItem
)

from .validation_worker import (
    SchemeImportRow, SchemeImportMode, IRECORD_COLUMNS, NBN_ATLAS_COLUMNS
)
from src.themes import theme


# Database field mappings - organized by group
FIELD_GROUPS = {
    'Required': [
        ('species_name', 'Species Name *', True),
        ('date', 'Date *', True),
        ('grid_ref', 'Grid Reference *', True),
    ],
    'Location': [
        ('site_name', 'Site Name', False),
        ('vice_county', 'Vice County', False),
        ('vc_number', 'VC Number', False),
        ('latitude', 'Latitude', False),
        ('longitude', 'Longitude', False),
        ('country', 'Country', False),
        ('state_province', 'State/Province', False),
    ],
    'People': [
        ('recorder', 'Recorder', False),
        ('determiner', 'Determiner', False),
        ('verifier', 'Verifier', False),
    ],
    'Occurrence': [
        ('sex', 'Sex', False),
        ('stage', 'Life Stage', False),
        ('quantity', 'Quantity', False),
        ('method', 'Sample Method', False),
    ],
    'Taxonomy': [
        ('species_tvk', 'Species TVK', False),
        ('common_name', 'Common Name', False),
        ('taxon_rank', 'Taxon Rank', False),
        ('kingdom', 'Kingdom', False),
        ('phylum', 'Phylum', False),
        ('class_name', 'Class', False),
        ('order_name', 'Order', False),
        ('family', 'Family', False),
        ('genus', 'Genus', False),
        ('taxon_author', 'Taxon Author', False),
    ],
    'Verification': [
        ('verification_status', 'Verification Status', False),
        ('verification_status_2', 'Verification Status 2', False),
        ('verified_on', 'Verified On', False),
    ],
    'Comments': [
        ('comment', 'Comment', False),
        ('sample_comment', 'Sample Comment', False),
        ('biotope', 'Biotope', False),
    ],
    'Metadata': [
        ('source', 'Source', False),
        ('dataset_name', 'Dataset Name', False),
        ('licence', 'Licence', False),
        ('images', 'Images', False),
    ],
}

# iRecord column to database field mapping
IRECORD_FIELD_MAP = {
    'Taxon': 'species_name',
    'TaxonVersionKey': 'species_tvk',
    'Common name': 'common_name',
    'Rank': 'taxon_rank',
    'Kingdom': 'kingdom',
    'Order': 'order_name',
    'Family': 'family',
    'Taxon group': 'taxon_group',
    'Date interpreted': 'date',
    'Date from': 'date',
    'Output map ref': 'grid_ref',
    'Original map ref': 'grid_ref',
    'Site name': 'site_name',
    'Vice County': 'vice_county',
    'VC number': 'vc_number',
    'Latitude': 'latitude',
    'Longitude': 'longitude',
    'Recorder': 'recorder',
    'Determiner': 'determiner',
    'Sex': 'sex',
    'Stage': 'stage',
    'Count of sex or stage': 'quantity',
    'Sample method': 'method',
    'Verification status 1': 'verification_status',
    'Verification status 2': 'verification_status_2',
    'Verifier': 'verifier',
    'Verified on': 'verified_on',
    'Comment': 'comment',
    'Sample comment': 'sample_comment',
    'Biotope': 'biotope',
    'Source': 'source',
    'Licence': 'licence',
    'Images': 'images',
    'ID': 'irecord_id',
    'RecordKey': 'record_key',
    'External key': 'external_key',
}

# NBN Atlas column to database field mapping
# Supports both Darwin Core and human-readable column names
NBN_FIELD_MAP = {
    # Darwin Core format
    'scientificName': 'species_name',
    'taxonID': 'species_tvk',
    'scientificNameAuthorship': 'taxon_author',
    'kingdom': 'kingdom',
    'phylum': 'phylum',
    'class': 'class_name',
    'order': 'order_name',
    'family': 'family',
    'genus': 'genus',
    'eventDate': 'date',
    'gridReference': 'grid_ref',
    'locality': 'site_name',
    'county': 'vice_county',
    'countryCode': 'country',
    'decimalLatitude': 'latitude',
    'decimalLongitude': 'longitude',
    'coordinateUncertaintyInMeters': 'coordinate_uncertainty',
    'identifiedBy': 'determiner',
    'sex': 'sex',
    'lifeStage': 'stage',
    'individualCount': 'quantity',
    'organismQuantity': 'organism_quantity',
    'organismQuantityType': 'organism_quantity_type',
    'identificationVerificationStatus': 'verification_status',
    'occurrenceRemarks': 'comment',
    'datasetName': 'dataset_name',
    'datasetID': 'dataset_id',
    'dcterms:license': 'licence',
    'recordID': 'nbn_atlas_id',
    'occurrenceID': 'occurrence_id',
    'eventID': 'event_id',
    'collectionCode': 'collection_code',
    'institutionCode': 'institution_code',
    'dcterms:rightsHolder': 'rights_holder',
    'basisOfRecord': 'basis_of_record',
    'occurrenceStatus': 'occurrence_status',
    'identificationRemarks': 'identification_remarks',
    'locationID': 'location_id',
    'georeferenceVerificationStatus': 'georeference_verification_status',
    'vitality': 'vitality',
    # Human-readable format (alternative)
    'Scientific name': 'species_name',
    'Species ID (TVK)': 'species_tvk',
    'Common name': 'common_name',
    'Taxon Rank': 'taxon_rank',
    'Taxon author': 'taxon_author',
    'Kingdom': 'kingdom',
    'Phylum': 'phylum',
    'Class': 'class_name',
    'Order': 'order_name',
    'Family': 'family',
    'Genus': 'genus',
    'Event Date': 'date',
    'Grid reference': 'grid_ref',
    'Locality': 'site_name',
    'Country': 'country',
    'State/Province': 'state_province',
    'Latitude (WGS84)': 'latitude',
    'Longitude (WGS84)': 'longitude',
    'Recorder': 'recorder',
    'Determiner': 'determiner',
    'Sex': 'sex',
    'Life stage': 'stage',
    'Individual count': 'quantity',
    'Identification verification status': 'verification_status',
    'Occurrence remarks': 'comment',
    'Dataset name': 'dataset_name',
    'Licence': 'licence',
    'NBN Atlas record ID': 'nbn_atlas_id',
    'Occurrence ID': 'occurrence_id',
    'Survey key': 'collection_code',
    'Institution code': 'institution_code',
    'rightsHolder': 'rights_holder',
    'Basis of Record': 'basis_of_record',
}


class WizardFileMixin:
    """Mixin providing file handling methods for SchemeImportWizard."""

    def _browse_file(self):
        """Open file browser dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CSV File",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if file_path:
            self.file_path = file_path
            self.file_path_label.setText(file_path)
            self._load_file_preview()

    def _load_file_preview(self):
        """Load and preview the selected file."""
        if not self.file_path:
            return

        try:
            # One reader for every wizard (9 Oct 2026): a byte-order mark used to stay on
            # the first heading, so iRecord's 'ID' was never found and all 35,104 iRecord
            # IDs were lost; quoted comments with a line break were split in two.
            from shared.import_core import read_table_file
            self.columns, self.raw_rows, self._file_encoding = read_table_file(self.file_path)

            # Detect format
            detected_mode = self._detect_format()

            # Update file info
            self.file_info_label.setText(
                f"Found {len(self.raw_rows)} rows and {len(self.columns)} columns"
            )

            # Show format detection
            if detected_mode:
                mode_names = {
                    SchemeImportMode.IRECORD: "iRecord",
                    SchemeImportMode.NBN_ATLAS: "NBN Atlas",
                }
                self.format_detected_label.setText(
                    f"✓ Detected format: {mode_names.get(detected_mode, 'Unknown')}"
                )
                self.format_detected_label.setVisible(True)

                # Auto-select the detected mode
                for card in self.mode_cards:
                    if card.mode_id == detected_mode.value:
                        self._select_mode_card(card)
                        break
            else:
                self.format_detected_label.setVisible(False)

            # Update preview table
            self._update_preview_table()

        except Exception as e:
            self.file_info_label.setText(f"Error reading file: {str(e)}")

    def _detect_format(self) -> Optional[SchemeImportMode]:
        """Detect if file is iRecord or NBN Atlas format."""
        if not self.columns:
            return None

        column_set = set(self.columns)

        # Check for iRecord format
        irecord_matches = len(column_set & IRECORD_COLUMNS)
        if irecord_matches >= 10:  # Strong match
            return SchemeImportMode.IRECORD

        # Check for NBN Atlas format
        nbn_matches = len(column_set & NBN_ATLAS_COLUMNS)
        if nbn_matches >= 10:  # Strong match
            return SchemeImportMode.NBN_ATLAS

        return None

    def _update_preview_table(self):
        """Update the preview table with first 5 rows."""
        if not self.raw_rows or not self.columns:
            return

        # Limit columns to display (max 10 for readability)
        display_columns = self.columns[:10]
        self.preview_table.setColumnCount(len(display_columns))
        self.preview_table.setHorizontalHeaderLabels(display_columns)

        # Show first 5 rows
        preview_rows = self.raw_rows[:5]
        self.preview_table.setRowCount(len(preview_rows))
        self.preview_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        for i, row in enumerate(preview_rows):
            for j, col in enumerate(display_columns):
                value = row.get(col, '')
                # Truncate long values
                if len(value) > 50:
                    value = value[:47] + "..."
                item = QTableWidgetItem(value)
                self.preview_table.setItem(i, j, item)

        self.preview_table.resizeColumnsToContents()

    def _populate_mapping_page(self):
        """Populate the column mapping page based on selected mode."""
        # Clear existing mappings
        while self.mapping_layout.count():
            item = self.mapping_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.mapping_combos = {}

        import_mode = self._get_selected_mode()
        t = theme()

        # For iRecord and NBN Atlas, auto-mapping is used
        if import_mode in [SchemeImportMode.IRECORD, SchemeImportMode.NBN_ATLAS]:
            info_label = QLabel(
                "Columns will be automatically mapped based on the detected format.\n"
                "You can review the mapping below and adjust if needed."
            )
            info_label.setStyleSheet(f"color: {t.get('text_secondary')}; margin-bottom: 12px;")
            info_label.setWordWrap(True)
            self.mapping_layout.addWidget(info_label)

        # Get auto-mapping for the format
        auto_map = self._get_auto_mapping(import_mode)

        # Create mapping rows grouped by category
        for group_name, fields in FIELD_GROUPS.items():
            # Group header
            group_label = QLabel(group_name)
            group_label.setStyleSheet(f"""
                font-weight: 600;
                font-size: 13px;
                color: {self._accent};
                padding: 8px 0 4px 0;
                border-bottom: 1px solid {t.get('border')};
                margin-top: 8px;
            """)
            self.mapping_layout.addWidget(group_label)

            for db_field, display_name, required in fields:
                row_frame = QFrame()
                row_layout = QHBoxLayout(row_frame)
                row_layout.setContentsMargins(0, 4, 0, 4)
                row_layout.setSpacing(12)

                # Field label
                label = QLabel(display_name)
                label.setFixedWidth(150)
                label.setStyleSheet(f"color: {t.get('text_primary')};")
                row_layout.addWidget(label)

                # Combo box for column selection
                combo = QComboBox()
                combo.addItem("-- Not Mapped --", "")
                for col in self.columns:
                    combo.addItem(col, col)

                # Set auto-mapped value
                if db_field in auto_map:
                    mapped_col = auto_map[db_field]
                    idx = combo.findData(mapped_col)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)

                combo.setStyleSheet(f"""
                    QComboBox {{
                        background-color: {t.get('surface')};
                        border: 1px solid {t.get('border')};
                        border-radius: {t.get('radius_md')};
                        padding: 6px 12px;
                        min-width: 200px;
                    }}
                    QComboBox:hover {{ border-color: {self._accent}; }}
                    QComboBox::drop-down {{
                        border: none;
                        padding-right: 8px;
                    }}
                """)

                row_layout.addWidget(combo, 1)
                self.mapping_combos[db_field] = combo

                self.mapping_layout.addWidget(row_frame)

        self.mapping_layout.addStretch()

    def _get_auto_mapping(self, import_mode: SchemeImportMode) -> Dict[str, str]:
        """Get automatic column mapping for the format."""
        mapping = {}

        if import_mode == SchemeImportMode.IRECORD:
            # Map iRecord columns to database fields
            for csv_col, db_field in IRECORD_FIELD_MAP.items():
                if csv_col in self.columns:
                    mapping[db_field] = csv_col

        elif import_mode == SchemeImportMode.NBN_ATLAS:
            # Map NBN Atlas columns to database fields
            for csv_col, db_field in NBN_FIELD_MAP.items():
                if csv_col in self.columns:
                    mapping[db_field] = csv_col

        else:
            # Generic - attempt fuzzy matching
            mapping = self._fuzzy_match_columns()

        return mapping

    def _fuzzy_match_columns(self) -> Dict[str, str]:
        """Attempt to fuzzy match columns for generic CSV."""
        mapping = {}

        # Simple keyword matching
        keywords = {
            'species_name': ['species', 'taxon', 'scientific', 'name'],
            'date': ['date', 'when', 'observed'],
            'grid_ref': ['grid', 'gridref', 'reference', 'osgr'],
            'site_name': ['site', 'location', 'locality', 'place'],
            'recorder': ['recorder', 'observer', 'recorded by'],
            'quantity': ['count', 'quantity', 'number', 'abundance'],
            'sex': ['sex', 'gender'],
            'stage': ['stage', 'life stage', 'lifestage'],
            'comment': ['comment', 'notes', 'remarks'],
        }

        for db_field, kw_list in keywords.items():
            for col in self.columns:
                col_lower = col.lower()
                for kw in kw_list:
                    if kw in col_lower:
                        mapping[db_field] = col
                        break
                if db_field in mapping:
                    break

        return mapping

    def _get_column_mapping(self) -> Dict[str, str]:
        """Get the current column mapping from combos."""
        mapping = {}
        for db_field, combo in self.mapping_combos.items():
            csv_col = combo.currentData()
            if csv_col:
                mapping[db_field] = csv_col
        return mapping

    def _create_import_rows(self) -> List[SchemeImportRow]:
        """Create SchemeImportRow objects from raw data."""
        rows = []
        for i, raw in enumerate(self.raw_rows):
            row = SchemeImportRow(
                row_number=i + 1,
                raw_data=raw
            )
            rows.append(row)
        return rows

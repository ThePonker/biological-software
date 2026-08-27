"""
Scheme Record Model Component.

High-performance table model for recording scheme data.
Uses QAbstractTableModel for efficient handling of 100k+ records.
"""

from typing import Optional, List, Dict

from PySide6.QtCore import Qt, QSettings, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor, QFont

from ...themes import theme
from ...utils.date_utils import format_date_display
from ...services.vc_lookup_service import VCLookupService


class SchemeRecordModel(QAbstractTableModel):
    """High-performance table model for recording scheme data with checkbox support."""

    # All possible columns - Format: (key, header, width, mandatory)
    ALL_COLUMNS = [
        ('checkbox', '', 30, True),
        ('id', 'ID', 50, False),
        ('date', 'Date', 90, True),
        ('species_name', 'Species', 160, True),
        ('common_name', 'Common Name', 130, False),
        ('species_tvk', 'TVK', 120, False),
        ('kingdom', 'Kingdom', 80, False),
        ('taxon_group', 'Taxon Group', 100, False),
        ('order_name', 'Order', 90, False),
        ('family', 'Family', 100, False),
        ('subfamily', 'Subfamily', 100, False),
        ('genus', 'Genus', 100, False),
        ('taxon_author', 'Author', 100, False),
        ('phylum', 'Phylum', 80, False),
        ('class_name', 'Class', 80, False),
        ('taxon_rank', 'Rank', 70, False),
        ('site_name', 'Location', 120, True),
        ('site_name_local', 'Local Name', 120, False),
        ('grid_ref', 'Grid Ref', 80, True),
        ('grid_precision', 'Precision', 70, False),
        ('vice_county', 'Vice County', 130, False),
        ('vc_number', 'VC No.', 50, False),
        ('latitude', 'Latitude', 90, False),
        ('longitude', 'Longitude', 90, False),
        ('geodetic_datum', 'Datum', 70, False),
        ('location_id', 'Location ID', 100, False),
        ('location_remarks', 'Location Notes', 150, False),
        ('country', 'Country', 80, False),
        ('state_province', 'State/Province', 100, False),
        ('recorder', 'Recorder', 100, True),
        ('determiner', 'Determiner', 100, False),
        ('recorder_certainty', 'Certainty', 80, False),
        ('verification_status', 'Status', 90, False),
        ('verification_status_2', 'Status 2', 90, False),
        ('verifier', 'Verifier', 100, False),
        ('verified_on', 'Verified On', 90, False),
        ('georeference_verification_status', 'Geo Status', 80, False),
        ('automated_checks', 'Auto Checks', 100, False),
        ('sex', 'Sex', 60, False),
        ('stage', 'Stage', 70, False),
        ('quantity', 'Qty', 50, False),
        ('individual_count', 'Count', 50, False),
        ('organism_quantity', 'Org Qty', 70, False),
        ('organism_quantity_type', 'Qty Type', 80, False),
        ('zero_abundance', 'Zero Abund.', 80, False),
        ('method', 'Method', 100, False),
        ('basis_of_record', 'Basis', 100, False),
        ('occurrence_status', 'Occ Status', 80, False),
        ('biotope', 'Biotope', 100, False),
        ('comment', 'Comment', 150, False),
        ('internal_notes', 'Internal Notes', 150, False),
        ('import_notes', 'Import Notes', 150, False),
        ('sample_comment', 'Sample Notes', 150, False),
        ('source', 'Source', 70, False),
        ('irecord_id', 'iRecord ID', 80, False),
        ('record_key', 'Record Key', 100, False),
        ('external_key', 'External Key', 120, False),
        ('event_id', 'Event ID', 80, False),
        ('nbn_atlas_id', 'NBN ID', 100, False),
        ('occurrence_id', 'Occurrence ID', 100, False),
        ('collection_code', 'Collection', 80, False),
        ('dataset_name', 'Dataset', 120, False),
        ('institution_code', 'Institution', 100, False),
        ('record_type', 'Record Type', 100, False),
        ('project_name', 'Project', 120, False),
        ('client', 'Client', 100, False),
        ('embargo_status', 'Embargo', 80, False),
        ('embargo_until', 'Embargo Until', 100, False),
        ('licence', 'Licence', 100, False),
        ('rights_holder', 'Rights Holder', 120, False),
        ('sensitive', 'Sensitive', 70, False),
        ('sensitive_site', 'Sensitive Site', 100, False),
        ('sensitive_output_map_ref', 'Sensitive Ref', 100, False),
        ('images', 'Images', 80, False),
        ('date_type', 'Date Type', 70, False),
        ('input_on_date', 'Input Date', 90, False),
        ('last_edited_date', 'Edited Date', 90, False),
        ('sync_status', 'Sync Status', 80, False),
        ('never_upload_to_irecord', 'No Upload', 70, False),
        ('created_at', 'Created', 90, False),
        ('updated_at', 'Updated', 90, False),
    ]

    DEFAULT_VISIBLE = [
        'id', 'common_name', 'subfamily', 'vice_county', 'vc_number',
        'determiner', 'source', 'verification_status'
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._records: List[Dict] = []
        self._checked: set = set()  # Set of checked row indices
        self._visible_columns: set = set()
        self._column_order: List[str] = []
        self._columns: List[tuple] = []  # Cached current columns
        self._load_column_settings()
        self._show_common_names = True
        self._load_common_name_setting()
        self._update_columns()

    def _load_column_settings(self):
        """Load column visibility and order settings."""
        settings = QSettings()
        saved = settings.value("scheme/visible_columns", None)
        if saved:
            self._visible_columns = set(saved)
        else:
            self._visible_columns = set(self.DEFAULT_VISIBLE)

        for col in self.ALL_COLUMNS:
            if len(col) > 3 and col[3]:
                self._visible_columns.add(col[0])

        saved_order = settings.value("scheme/column_order", None)
        if saved_order:
            self._column_order = list(saved_order)
        else:
            self._column_order = [c[0] for c in self.ALL_COLUMNS if c[0] != 'checkbox']

    def save_column_settings(self):
        """Save column visibility and order settings."""
        settings = QSettings()
        settings.setValue("scheme/visible_columns", list(self._visible_columns))
        settings.setValue("scheme/column_order", self._column_order)

    def _load_common_name_setting(self):
        """Load common name visibility from settings."""
        settings = QSettings()
        self._show_common_names = settings.value(
            "display/common_names_recording_scheme", True, type=bool
        )
        if self._show_common_names:
            self._visible_columns.add('common_name')
        else:
            self._visible_columns.discard('common_name')

    def _update_columns(self):
        """Update cached columns list."""
        col_lookup = {col[0]: col for col in self.ALL_COLUMNS}
        result = [col_lookup['checkbox']]
        for col_key in self._column_order:
            if col_key in col_lookup:
                col = col_lookup[col_key]
                mandatory = len(col) > 3 and col[3]
                if mandatory or col_key in self._visible_columns:
                    result.append(col)
        for col in self.ALL_COLUMNS:
            if col[0] != 'checkbox' and col[0] not in self._column_order:
                mandatory = len(col) > 3 and col[3]
                if mandatory or col[0] in self._visible_columns:
                    result.append(col)
        self._columns = result

    def get_columns(self):
        """Get current visible columns in saved order."""
        return self._columns

    @property
    def COLUMNS(self):
        """Property for backwards compatibility."""
        return self.get_columns()

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._records)

    def columnCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._records)):
            return None

        row = index.row()
        col = index.column()
        col_key = self._columns[col][0]
        record = self._records[row]

        # Checkbox column
        if col_key == 'checkbox':
            if role == Qt.ItemDataRole.CheckStateRole:
                return Qt.CheckState.Checked if row in self._checked else Qt.CheckState.Unchecked
            return None

        # Get value
        value = self._get_record_value(record, col_key)

        # Format date
        if col_key == 'date' and value:
            value = format_date_display(str(value), "user")

        # Format VC number
        if col_key == 'vc_number' and value:
            try:
                vc_num = int(value)
                vc_name = VCLookupService.VC_NAMES.get(vc_num)
                if vc_name:
                    value = f"{vc_num} - {vc_name}"
            except (ValueError, TypeError):
                pass

        if role == Qt.ItemDataRole.DisplayRole:
            return str(value) if value else ''

        if role == Qt.ItemDataRole.UserRole:
            if col_key == 'id':
                return record
            return None

        if role == Qt.ItemDataRole.FontRole:
            if col_key == 'species_name':
                font = QFont()
                font.setItalic(True)
                return font
            return None

        if role == Qt.ItemDataRole.ForegroundRole:
            t = theme()
            if col_key == 'verification_status':
                status = value or ''
                if status == 'Accepted':
                    return QColor(t.get('success_text'))
                elif status in ['Pending', 'Unconfirmed']:
                    return QColor(t.get('warning_text'))
                elif status == 'Rejected':
                    return QColor(t.get('error_text'))
            if col_key == 'source':
                source = value or ''
                if source == 'iRecord':
                    return QColor(t.get('info_text'))
                elif source == 'NBN':
                    return QColor(t.get('info'))
                elif source == 'Email':
                    return QColor(t.get('success'))
            return None

        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False

        col_key = self._columns[index.column()][0]

        if col_key == 'checkbox' and role == Qt.ItemDataRole.CheckStateRole:
            row = index.row()
            if value == Qt.CheckState.Checked:
                self._checked.add(row)
            else:
                self._checked.discard(row)
            self.dataChanged.emit(index, index, [role])
            return True

        return False

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        col_key = self._columns[index.column()][0]
        base_flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

        if col_key == 'checkbox':
            return base_flags | Qt.ItemFlag.ItemIsUserCheckable

        return base_flags

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self._columns):
                return self._columns[section][1]
        return None

    def _get_record_value(self, record: Dict, col_key: str):
        """Get value from record, handling key name variations."""
        if col_key in record:
            return record[col_key]

        key_map = {
            'species_name': ['species', 'species_name', 'scientificName'],
            'common_name': ['common', 'common_name', 'commonName'],
            'site_name': ['location', 'site_name', 'siteName'],
            'grid_ref': ['gridRef', 'grid_ref', 'gridReference'],
            'vc_number': ['vc', 'vc_number', 'vcNumber'],
            'verification_status': ['verification', 'verification_status', 'status'],
            'subfamily': ['subfamily', 'subFamily'],
        }

        for alt_key in key_map.get(col_key, []):
            if alt_key in record:
                return record[alt_key]

        return None

    def set_records(self, records: List[Dict]):
        """Set recording scheme data."""
        self.beginResetModel()
        self._records = records
        self._checked.clear()
        self.endResetModel()

    def refresh_common_name_setting(self):
        """Refresh common name visibility from settings."""
        old = self._show_common_names
        self._load_common_name_setting()
        if old != self._show_common_names:
            self.beginResetModel()
            self._update_columns()
            self.endResetModel()
            return True
        return False

    def refresh_date_format(self):
        """Refresh date format by emitting dataChanged for date column."""
        date_col = None
        for i, col in enumerate(self._columns):
            if col[0] == 'date':
                date_col = i
                break
        if date_col is not None and self._records:
            self.dataChanged.emit(
                self.index(0, date_col),
                self.index(len(self._records) - 1, date_col),
                [Qt.ItemDataRole.DisplayRole]
            )

    def get_record_at_row(self, row: int) -> Optional[Dict]:
        """Get record data at specified row."""
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    def get_checked_rows(self) -> List[int]:
        """Get list of checked row indices."""
        return sorted(self._checked)

    def get_checked_records(self) -> List[Dict]:
        """Get list of checked record data."""
        return [self._records[row] for row in sorted(self._checked) if row < len(self._records)]

    def set_all_checked(self, checked: bool):
        """Check or uncheck all rows."""
        self.beginResetModel()
        if checked:
            self._checked = set(range(len(self._records)))
        else:
            self._checked.clear()
        self.endResetModel()

    def get_column_widths(self) -> List[int]:
        """Get list of column widths."""
        return [col[2] for col in self._columns]

    # Compatibility methods for code that expects QStandardItemModel
    def item(self, row, col):
        """Compatibility: Return None (no QStandardItem in this model)."""
        return None

    def appendRow(self, items):
        """Compatibility: Not used in QAbstractTableModel."""
        pass

    def removeRows(self, row, count, parent=QModelIndex()):
        """Remove rows from the model."""
        if count <= 0:
            return False
        self.beginRemoveRows(parent, row, row + count - 1)
        del self._records[row:row + count]
        # Update checked indices
        new_checked = set()
        for idx in self._checked:
            if idx < row:
                new_checked.add(idx)
            elif idx >= row + count:
                new_checked.add(idx - count)
        self._checked = new_checked
        self.endRemoveRows()
        return True
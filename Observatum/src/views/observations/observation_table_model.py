"""
Observation Table Model Component.

High-performance table model for observation data.
Uses QAbstractTableModel for efficient handling of 20k+ records.
"""

from typing import Optional, List, Dict

from PySide6.QtCore import Qt, QSettings, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtGui import QColor, QFont

from ...themes import theme
from ...core.config import TabColors
from ...utils.date_utils import format_date_display
from ...services.vc_lookup_service import VCLookupService

# Custom role for sortable date values
DATE_SORT_ROLE = Qt.ItemDataRole.UserRole + 100


class ObservationTableModel(QAbstractTableModel):
    """High-performance table model for observation data with checkbox support."""

    checked_changed = Signal()

    # All possible columns - Format: (key, header, width, mandatory)
    ALL_COLUMNS = [
        # Core display columns
        ('checkbox', '', 30, True),
        ('id', 'ID', 50, False),
        ('date', 'Date', 85, True),
        ('species_name', 'Species', 180, True),
        ('common_name', 'Common Name', 130, False),
        ('species_tvk', 'TVK', 120, False),

        # Taxonomy
        ('kingdom', 'Kingdom', 80, False),
        ('taxon_group', 'Taxon Group', 100, False),
        ('order_name', 'Order', 100, False),
        ('family', 'Family', 110, False),
        ('superfamily', 'Superfamily', 120, False),
        ('taxon_rank', 'Rank', 70, False),

        # Location
        ('site_name', 'Location', 130, True),
        ('site_name_local', 'Local Site', 120, False),
        ('grid_ref', 'Grid Ref', 80, True),
        ('grid_precision', 'Precision', 70, False),
        ('vice_county', 'Vice County', 130, False),
        ('vc_number', 'VC No.', 50, False),
        ('latitude', 'Latitude', 90, False),
        ('longitude', 'Longitude', 90, False),
        ('geodetic_datum', 'Datum', 70, False),

        # Who
        ('recorder', 'Recorder', 100, True),
        ('determiner', 'Determiner', 100, False),
        ('recorder_certainty', 'Certainty', 80, False),

        # Verification
        ('verification_status', 'Status', 90, False),
        ('verification_status_2', 'Status 2', 90, False),
        ('verifier', 'Verifier', 100, False),
        ('verified_on', 'Verified On', 90, False),
        ('automated_checks', 'Auto Checks', 100, False),

        # Occurrence details
        ('sex', 'Sex', 60, False),
        ('stage', 'Stage', 70, False),
        ('quantity', 'Qty', 35, False),
        ('zero_abundance', 'Zero Abund.', 80, False),
        ('method', 'Method', 100, False),
        ('basis_of_record', 'Basis', 100, False),
        ('occurrence_status', 'Occ Status', 80, False),
        ('biotope', 'Biotope', 100, False),

        # Notes
        ('comment', 'Comment', 150, False),
        ('internal_notes', 'Internal Notes', 150, False),
        ('sample_comment', 'Sample Notes', 150, False),
        ('import_notes', 'Import Notes', 180, False),

        # Source & Identity
        ('source', 'Source', 70, False),
        ('irecord_id', 'iRecord ID', 80, False),
        ('record_key', 'Record Key', 100, False),
        ('external_key', 'External Key', 120, False),
        ('observatum_key', 'Obs Key', 150, False),

        # Project/Commercial
        ('record_type', 'Type', 80, False),
        ('project_name', 'Project', 120, False),
        ('client', 'Client', 100, False),
        ('embargo_status', 'Embargo', 80, False),
        ('embargo_until', 'Embargo Until', 100, False),

        # Rights & Sensitivity
        ('sensitive', 'Sensitive', 70, False),
        ('sensitive_site', 'Sensitive Site', 100, False),
        ('sensitive_output_map_ref', 'Sensitive Ref', 100, False),
        ('images', 'Images', 80, False),

        # Dates & Sync
        ('date_type', 'Date Type', 70, False),
        ('input_on_date', 'Input Date', 90, False),
        ('last_edited_date', 'Last Edited', 120, False),
        ('sync_status', 'Sync Status', 80, False),
        ('never_upload_to_irecord', 'No Upload', 70, False),
        ('created_at', 'Created', 90, False),
        ('updated_at', 'Updated', 90, False),
        ('irecord_key', 'iRecord Key', 90, False),
        ('last_synced', 'Last Synced', 120, False),
    ]

    # Default visible columns (non-mandatory columns shown by default)
    DEFAULT_VISIBLE = [
        'date', 'species_name', 'common_name', 'taxon_group', 'taxon_rank',
        'order_name', 'family', 'kingdom', 'species_tvk',
        'site_name', 'grid_ref', 'vice_county', 'vc_number',
        'latitude', 'longitude',
        'recorder', 'determiner', 'recorder_certainty',
        'sex', 'stage', 'quantity',
        'method', 'biotope', 'comment', 'sample_comment',
        'verification_status', 'verification_status_2',
        'verifier', 'verified_on', 'automated_checks',
        'record_type',
        'images', 'sensitive', 'sensitive_site', 'sensitive_output_map_ref',
        'input_on_date', 'last_edited_date',
        'irecord_id', 'record_key', 'external_key', 'observatum_key',
        'internal_notes', 'import_notes', 'project_name', 'client', 'embargo_status',
        'embargo_until', 'sync_status', 'never_upload_to_irecord',
        'irecord_key', 'last_synced',
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._observations: List[Dict] = []
        self._checked: set = set()
        self._visible_columns: set = set()
        self._column_order: List[str] = []
        self._columns: List[tuple] = []
        self._italic_font: Optional[QFont] = None
        self._load_column_settings()
        self._show_common_names = True
        self._load_common_name_setting()
        self._update_columns()
    def _load_column_settings(self):
        """Load column visibility and order settings."""
        settings = QSettings()

        saved = settings.value("observations/visible_columns", None)
        if saved:
            self._visible_columns = set(saved)
        else:
            self._visible_columns = set(self.DEFAULT_VISIBLE)

        # Always include mandatory columns
        for col in self.ALL_COLUMNS:
            if len(col) > 3 and col[3]:
                self._visible_columns.add(col[0])

        saved_order = settings.value("observations/column_order", None)
        if saved_order:
            self._column_order = list(saved_order)
        else:
            self._column_order = [c[0] for c in self.ALL_COLUMNS if c[0] != 'checkbox']

    def _load_common_name_setting(self):
        """Load common name visibility from settings."""
        settings = QSettings()
        self._show_common_names = settings.value(
            "display/common_names_observations", True, type=bool
        )
        if self._show_common_names:
            self._visible_columns.add('common_name')
        else:
            self._visible_columns.discard('common_name')

    def _update_columns(self):
        """Rebuild the active columns list from settings."""
        col_lookup = {col[0]: col for col in self.ALL_COLUMNS}
        result = [col_lookup['checkbox']]

        for col_key in self._column_order:
            if col_key in col_lookup:
                col = col_lookup[col_key]
                mandatory = len(col) > 3 and col[3]
                if mandatory or col_key in self._visible_columns:
                    result.append(col)

        # Safety fallback for columns not in order
        for col in self.ALL_COLUMNS:
            if col[0] != 'checkbox' and col[0] not in self._column_order:
                mandatory = len(col) > 3 and col[3]
                if mandatory or col[0] in self._visible_columns:
                    result.append(col)

        self._columns = result

    def save_column_settings(self):
        """Save column visibility and order settings."""
        settings = QSettings()
        settings.setValue("observations/visible_columns", list(self._visible_columns))
        settings.setValue("observations/column_order", self._column_order)

    def get_columns(self):
        """Get current visible columns in saved order."""
        return self._columns

    @property
    def COLUMNS(self):
        """Property for backwards compatibility."""
        return self._columns

    # ── Qt Model Interface ──────────────────────────────────────

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._observations)

    def columnCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._observations)):
            return None

        row = index.row()
        col = index.column()
        col_key = self._columns[col][0]
        record = self._observations[row]

        # Checkbox column
        if col_key == 'checkbox':
            if role == Qt.ItemDataRole.CheckStateRole:
                return Qt.CheckState.Checked if row in self._checked else Qt.CheckState.Unchecked
            if role == Qt.ItemDataRole.DisplayRole:
                return "✓" if row in self._checked else ""
            if role == Qt.ItemDataRole.ForegroundRole:
                if row in self._checked:
                    return QColor("#4a7c59")
            if role == Qt.ItemDataRole.FontRole:
                if row in self._checked:
                    font = QFont()
                    font.setBold(True)
                    font.setPointSize(14)
                    return font
            if role == Qt.ItemDataRole.BackgroundRole:
                if row in self._checked:
                    return QColor("#e8f0ea")
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignCenter
            return None

        # Get value
        value = self._get_record_value(record, col_key)

        # Format date
        if col_key == 'date' and value:
            if role == DATE_SORT_ROLE:
                return str(value)
            value = format_date_display(str(value), "user")

        # Format VC number with name
        if col_key == 'vc_number' and value:
            if role == DATE_SORT_ROLE:
                return None
            try:
                vc_num = int(value)
                vc_name = VCLookupService.VC_NAMES.get(vc_num)
                if vc_name:
                    value = f"{vc_num} - {vc_name}"
            except (ValueError, TypeError):
                pass

        # Highlight entire row when checked
        if role == Qt.ItemDataRole.BackgroundRole:
            if row in self._checked:
                return QColor("#e8f0ea")
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            return str(value) if value else ''

        if role == DATE_SORT_ROLE and col_key == 'date':
            return self._get_record_value(record, 'date') or ''

        if role == Qt.ItemDataRole.UserRole and col_key == 'id':
            return record

        # Italicize species name
        if role == Qt.ItemDataRole.FontRole and col_key == 'species_name':
            if self._italic_font is None:
                self._italic_font = QFont()
                self._italic_font.setItalic(True)
            return self._italic_font

        # Color verification status
        if role == Qt.ItemDataRole.ForegroundRole and col_key == 'verification_status':
            t = theme()
            status = str(value) if value else ''
            if status == 'Accepted':
                return QColor(t.get('success_text'))
            elif status == 'Pending':
                return QColor(t.get('warning_text'))
            elif status == 'Rejected':
                return QColor(t.get('error_text'))

        # Color record type
        if role == Qt.ItemDataRole.ForegroundRole and col_key == 'record_type':
            record_type = str(value) if value else 'Personal'
            if record_type == 'Commercial':
                t = theme()
                purple = t.get('accent_purple') or TabColors.RECORDING_SCHEME
                return QColor(purple)

        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False

        col_key = self._columns[index.column()][0]

        if col_key == 'checkbox' and role == Qt.ItemDataRole.CheckStateRole:
            row = index.row()
            if value == Qt.CheckState.Checked or value == Qt.CheckState.Checked.value:
                self._checked.add(row)
            else:
                self._checked.discard(row)
            self.dataChanged.emit(index, index, [role])
            self.checked_changed.emit()
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

    # ── Helper Methods ──────────────────────────────────────────

    def _get_record_value(self, record, key):
        """Get value from record dict or object."""
        if isinstance(record, dict):
            return record.get(key, '')
        return getattr(record, key, '')

    # ── Public API ──────────────────────────────────────────────

    def set_observations(self, observations: List):
        """Set observation data."""
        self.beginResetModel()
        self._observations = observations
        self._checked.clear()
        self.endResetModel()

    def set_observations_fast(self, observations: List, table_view=None, sort_proxy=None):
        """Set observation data. If first_load, assumes proxy is not yet connected."""

        self.beginResetModel()
        self._observations = observations
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
        if date_col is not None and self._observations:
            self.dataChanged.emit(
                self.index(0, date_col),
                self.index(len(self._observations) - 1, date_col),
                [Qt.ItemDataRole.DisplayRole]
            )

    def get_observation_at_row(self, row: int) -> Optional[Dict]:
        """Get observation data at specified row."""
        if 0 <= row < len(self._observations):
            obs = self._observations[row]
            return obs if isinstance(obs, dict) else obs.to_dict()
        return None

    def get_checked_rows(self) -> List[int]:
        """Get list of checked row indices."""
        return sorted(self._checked)

    def get_checked_observations(self) -> List[Dict]:
        """Get list of checked observation data."""
        observations = []
        for row in self.get_checked_rows():
            obs = self.get_observation_at_row(row)
            if obs:
                observations.append(obs)
        return observations

    def set_all_checked(self, checked: bool):
        """Check or uncheck all rows."""
        if checked:
            self._checked = set(range(len(self._observations)))
        else:
            self._checked.clear()
        if self._observations:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(len(self._observations) - 1, 0),
                [Qt.ItemDataRole.CheckStateRole]
            )

    def get_column_widths(self) -> List[int]:
        """Get list of column widths."""
        return [col[2] for col in self._columns]

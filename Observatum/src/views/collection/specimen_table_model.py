"""
Specimen Table Model Component.

Table model for specimen collection data with checkbox support.
Matches the Observation Data tab layout for consistency.
"""

from typing import Optional, List, Any

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor

from ...themes import theme
from ...utils.date_utils import format_date_display
from ...services.vc_lookup_service import VCLookupService


class SpecimenTableModel(QStandardItemModel):
    """Table model for specimen collection data with checkbox support."""

    # All possible columns - visibility controlled by settings
    # Format: (key, header, width, mandatory)
    # Mandatory columns cannot be hidden: date, species_name, site_name, grid_ref, collector, determiner
    ALL_COLUMNS = [
        ('checkbox', '', 30, True),
        ('id', 'ID', 50, False),
        ('specimen_code', 'Specimen Code', 100, False),
        ('date_collected', 'Date', 85, True),
        ('species_name', 'Species', 160, True),
        ('species_tvk', 'TVK', 120, False),
        ('common_name', 'Common Name', 130, False),
        ('order_name', 'Order', 90, False),
        ('family', 'Family', 100, False),
        ('subfamily', 'Subfamily', 100, False),
        ('superfamily', 'Superfamily', 120, False),
        ('site_name', 'Location', 120, True),
        ('site_name_local', 'Local Site', 120, False),
        ('grid_ref', 'Grid Ref', 75, True),
        ('vice_county', 'Vice County', 130, False),
        ('vc_number', 'VC No.', 50, False),
        ('collector', 'Collector', 90, True),
        ('determiner', 'Determiner', 90, True),
        ('sex', 'Sex', 60, False),
        ('preparation_type', 'Prep Type', 80, False),
        ('storage_location', 'Storage', 100, False),
        ('drawer_number', 'Drawer', 70, False),
        ('condition', 'Condition', 80, False),
        ('label_data', 'Label Data', 150, False),
        ('notes', 'Notes', 150, False),
        ('import_notes', 'Import Notes', 150, False),
        ('observation_id', 'Obs ID', 60, False),
        ('created_at', 'Created', 85, False),
        ('updated_at', 'Updated', 85, False),
    ]

    # Default visible columns (non-mandatory columns that show by default)
    # Default: show all columns initially (user can hide via settings)
    DEFAULT_VISIBLE = [
        'id', 'specimen_code', 'species_tvk', 'common_name', 'order_name', 
        'family', 'subfamily', 'vice_county', 'vc_number', 'sex', 
        'preparation_type', 'storage_location', 'drawer_number', 'condition',
        'label_data', 'notes', 'import_notes', 'observation_id', 
        'created_at', 'updated_at'
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._specimens: List[Any] = []
        self._visible_columns: set = set()
        self._column_order: List[str] = []
        self._load_column_settings()
        self._show_common_names = True
        self._load_common_name_setting()
        self._setup_headers()

    def _load_column_settings(self):
        """Load column visibility and order settings."""
        settings = QSettings()
        
        # Get saved visible columns or use defaults
        saved = settings.value("collection/visible_columns", None)
        if saved:
            self._visible_columns = set(saved)
        else:
            # Default: mandatory + default visible
            self._visible_columns = set(self.DEFAULT_VISIBLE)
        
        # Always include mandatory columns
        for col in self.ALL_COLUMNS:
            if col[3]:  # mandatory
                self._visible_columns.add(col[0])
        
        # Load column order
        saved_order = settings.value("collection/column_order", None)
        if saved_order:
            self._column_order = list(saved_order)
        else:
            # Default order from ALL_COLUMNS (excluding checkbox)
            self._column_order = [c[0] for c in self.ALL_COLUMNS if c[0] != 'checkbox']


    def _load_common_name_setting(self):
        """Load common name visibility from settings."""
        settings = QSettings()
        self._show_common_names = settings.value(
            "display/common_names_insect_collection", True, type=bool
        )
        # Toggle common_name column visibility
        if self._show_common_names:
            self._visible_columns.add('common_name')
        else:
            self._visible_columns.discard('common_name')

    def save_column_settings(self):
        """Save column visibility and order settings."""
        settings = QSettings()
        settings.setValue("collection/visible_columns", list(self._visible_columns))
        settings.setValue("collection/column_order", self._column_order)

    def set_column_visible(self, col_key: str, visible: bool):
        """Set visibility for a column."""
        # Find if column is mandatory
        for col in self.ALL_COLUMNS:
            if col[0] == col_key:
                if col[3]:  # mandatory - always visible
                    return False
                break
        if visible:
            self._visible_columns.add(col_key)
        else:
            self._visible_columns.discard(col_key)
        self.save_column_settings()
        return True

    def is_column_visible(self, col_key: str) -> bool:
        """Check if column is visible."""
        return col_key in self._visible_columns

    def get_columns(self):
        """Get current visible columns in saved order."""
        # Build lookup for column metadata
        col_lookup = {col[0]: col for col in self.ALL_COLUMNS}
        
        # Start with checkbox (always first)
        result = [col_lookup['checkbox']]
        
        # Add columns in saved order
        for col_key in self._column_order:
            if col_key in col_lookup:
                col = col_lookup[col_key]
                # Include if mandatory or in visible set
                if col[3] or col_key in self._visible_columns:
                    result.append(col)
        
        # Add any columns not in order (safety fallback)
        for col in self.ALL_COLUMNS:
            if col[0] != 'checkbox' and col[0] not in self._column_order:
                if col[3] or col[0] in self._visible_columns:
                    result.append(col)
        
        return result

    @property
    def COLUMNS(self):
        """Property for backwards compatibility."""
        return self.get_columns()

    def _setup_headers(self):
        """Set up table headers."""
        columns = self.get_columns()
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels([col[1] for col in columns])

    def refresh_common_name_setting(self):
        """Refresh common name visibility from settings and rebuild table."""
        old_setting = self._show_common_names
        self._load_common_name_setting()
        if old_setting != self._show_common_names:
            # Setting changed, need to rebuild
            specimens = self._specimens.copy()
            self._setup_headers()
            self.set_specimens(specimens)
            return True
        return False

    def refresh_date_format(self):
        """Refresh date format by rebuilding table with current data."""
        if self._specimens:
            specimens = self._specimens.copy()
            self.set_specimens(specimens)

    def set_specimens(self, specimens: List[Any]):
        """Set specimen data. Accepts list of Specimen objects or dicts.

        The rows are built with the model's signals off and then announced as one reset:
        each appendRow told the sort proxy and the view about one row, and the proxy
        re-sorted as it went (0.5-0.9 s of each reload for 2,745 specimens -- speed
        review 10 Oct 2026). The proxy re-sorts once, on its current column, after it."""
        was_blocked = self.blockSignals(True)
        try:
            self._fill_rows(specimens)
        finally:
            self.blockSignals(was_blocked)
        self.beginResetModel()
        self.endResetModel()

    def _fill_rows(self, specimens: List[Any]):
        t = theme()
        self._specimens = specimens
        self.removeRows(0, self.rowCount())

        columns = self.get_columns()

        for specimen in specimens:
            row_items = []
            for col_key, _, _, _ in columns:
                if col_key == 'checkbox':
                    item = QStandardItem()
                    item.setCheckable(True)
                    item.setCheckState(Qt.CheckState.Unchecked)
                else:
                    # Map specimen keys to column keys
                    value = self._get_specimen_value(specimen, col_key)
                    
                    # Format date using user's preferred format
                    raw_date = None
                    if col_key == 'date_collected' and value:
                        raw_date = str(value)  # Keep ISO for sorting
                        value = format_date_display(str(value), "user")
                    
                    # Look up VC full name for display
                    if col_key == 'vc_number' and value:
                        try:
                            vc_num = int(value)
                            vc_name = VCLookupService.VC_NAMES.get(vc_num)
                            if vc_name:
                                value = f"{vc_num} - {vc_name}"
                        except (ValueError, TypeError):
                            pass
                    
                    item = QStandardItem(str(value) if value else '')

                    # Store ISO date for correct chronological sorting
                    if col_key == 'date_collected' and raw_date:
                        # Convert DD/MM/YYYY to YYYY-MM-DD for sort
                        iso = raw_date
                        if '/' in raw_date:
                            parts = raw_date.split('/')
                            if len(parts) == 3 and len(parts[2]) == 4:
                                iso = f'{parts[2]}-{parts[1]}-{parts[0]}'
                        item.setData(iso, Qt.ItemDataRole.UserRole + 1)

                item.setEditable(False)

                # Store full specimen in ID column
                if col_key == 'id':
                    item.setData(specimen, Qt.ItemDataRole.UserRole)

                # Italicize species name
                if col_key == 'species_name':
                    font = item.font()
                    font.setItalic(True)
                    item.setFont(font)

                # Style import_notes with warning color if present
                if col_key == 'import_notes' and value:
                    item.setForeground(QColor(t.get('warning_text')))

                row_items.append(item)

            self.appendRow(row_items)


    def add_specimen(self, specimen):
        """Add a single specimen to the table without clearing existing data."""
        t = theme()
        self._specimens.append(specimen)
        columns = self.get_columns()
        
        row_items = []
        for col_key, _, _, _ in columns:
            if col_key == 'checkbox':
                item = QStandardItem()
                item.setCheckable(True)
                item.setCheckState(Qt.CheckState.Unchecked)
            else:
                value = self._get_specimen_value(specimen, col_key)
                raw_date = None
                if col_key == 'date_collected' and value:
                    raw_date = str(value)
                    value = format_date_display(str(value), "user")
                if col_key == 'vc_number' and value:
                    try:
                        vc_num = int(value)
                        vc_name = VCLookupService.VC_NAMES.get(vc_num)
                        if vc_name:
                            value = f"{vc_num} - {vc_name}"
                    except (ValueError, TypeError):
                        pass
                item = QStandardItem(str(value) if value else '')
            item.setEditable(False)
            if col_key == 'id':
                item.setData(specimen, Qt.ItemDataRole.UserRole)
                if col_key == 'date_collected' and raw_date:
                    item.setData(raw_date, Qt.ItemDataRole.UserRole + 1)
            if col_key == 'species_name':
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
            if col_key == 'import_notes' and value:
                item.setForeground(QColor(t.get('warning_text')))
            row_items.append(item)
        self.appendRow(row_items)

    def _get_specimen_value(self, specimen: Any, col_key: str):
        """
        Get value from specimen, handling both dict and dataclass objects.

        Args:
            specimen: Either a dict or a Specimen dataclass object
            col_key: The column/attribute key to retrieve

        Returns:
            The value or None if not found
        """
        # Key variations to try
        key_map = {
            'species_name': ['species_name', 'species', 'scientificName'],
            'common_name': ['common_name', 'common', 'commonName'],
            'order_name': ['order_name', 'order', 'orderName'],
            'site_name': ['site_name', 'location', 'siteName'],
            'grid_ref': ['grid_ref', 'gridRef', 'gridReference'],
            'vc_number': ['vc_number', 'vc', 'vcNumber'],
            'date': ['date_collected', 'date', 'dateCollected'],
            'import_notes': ['import_notes', 'importNotes'],
        }

        # Get list of keys to try (primary key first, then alternatives)
        keys_to_try = [col_key] + key_map.get(col_key, [])

        # Handle dict-style access
        if isinstance(specimen, dict):
            for key in keys_to_try:
                if key in specimen:
                    return specimen[key]
            return None

        # Handle dataclass/object-style access
        else:
            for key in keys_to_try:
                if hasattr(specimen, key):
                    return getattr(specimen, key, None)
            return None

    def get_specimen_at_row(self, row: int) -> Optional[Any]:
        """Get specimen data at specified row."""
        if 0 <= row < len(self._specimens):
            return self._specimens[row]
        return None

    def get_checked_rows(self) -> List[int]:
        """Get list of checked row indices."""
        checked = []
        for row in range(self.rowCount()):
            item = self.item(row, 0)  # Checkbox column
            if item and item.checkState() == Qt.CheckState.Checked:
                checked.append(row)
        return checked

    def get_checked_specimens(self) -> List[Any]:
        """Get list of checked specimen data."""
        specimens = []
        for row in self.get_checked_rows():
            specimen = self.get_specimen_at_row(row)
            if specimen:
                specimens.append(specimen)
        return specimens

    def set_all_checked(self, checked: bool):
        """Check or uncheck all rows."""
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item:
                item.setCheckState(state)

    def get_column_index(self, field_name: str) -> int:
        """Get column index by field name. Returns -1 if not found."""
        for i, (key, *_) in enumerate(self.ALL_COLUMNS):
            if key == field_name:
                return i
        return -1

    def get_column_widths(self) -> List[int]:
        """Get list of column widths."""
        return [col[2] for col in self.get_columns()]

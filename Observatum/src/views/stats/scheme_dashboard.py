"""
Recording Scheme Dashboard Component - Enhanced Version.

Dashboard for scheme organisers showing:
- Total records/species (stat cards)
- Geographic coverage with interactive VC map (choropleth)
- Vice county breakdown (sortable table)
- County firsts (activity feed cards)
- Species list with filter chips (searchable)
- Recording gaps (tiered by severity)
- Monthly distribution

NO gamification - this is a scheme organiser tool.
"""

from PySide6.QtWidgets import (
    QDialog, QTabWidget,
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QGridLayout, QTableView,
    QLineEdit, QPushButton, QButtonGroup, QComboBox, QCompleter
)
from PySide6.QtCore import Signal, Qt, QMargins, QSortFilterProxyModel, QAbstractTableModel, QModelIndex, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath

try:
    from PySide6.QtCharts import QChart, QChartView, QBarSeries, QBarSet, QValueAxis, QBarCategoryAxis
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False

from .stat_widgets import StatCard, MonthlyActivityChart
from ...themes import theme
from ...core.config import TabColors
from ...services.recording_scheme_stats_service import get_recording_scheme_stats


class SortableTableModel(QAbstractTableModel):
    """Generic sortable table model with proper numeric sorting."""
    
    # Columns that contain dates (will be formatted for display)
    DATE_COLUMNS = {"First Record", "Date", "first_date", "date", "Last Recorded"}

    def __init__(self, headers, parent=None):
        super().__init__(parent)
        self._headers = headers
        self._data = []
        # Import date formatter
        from ...utils.date_utils import format_date_for_display
        self._format_date = format_date_for_display
    
    def rowCount(self, parent=QModelIndex()):
        return len(self._data)
    
    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)
    
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._data):
            return None
        
        value = self._data[index.row()][index.column()]
        
        if role == Qt.ItemDataRole.DisplayRole:
            if isinstance(value, (int, float)):
                return f"{int(value):,}"
            # Format dates for display
            if self._headers[index.column()] in self.DATE_COLUMNS and value:
                return self._format_date(value)
            return str(value) if value is not None else ""
        
        if role == Qt.ItemDataRole.UserRole:
            return value
        
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if index.column() > 0:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        
        return None
    
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._headers[section]
        return None
    
    def set_data(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()


class NumericSortProxyModel(QSortFilterProxyModel):
    """Proxy model that sorts using UserRole for proper numeric sorting."""
    
    def lessThan(self, left, right):
        left_data = self.sourceModel().data(left, Qt.ItemDataRole.UserRole)
        right_data = self.sourceModel().data(right, Qt.ItemDataRole.UserRole)
        
        if left_data is None:
            return True
        if right_data is None:
            return False
        
        if isinstance(left_data, (int, float)) and isinstance(right_data, (int, float)):
            return left_data < right_data
        
        return str(left_data).lower() < str(right_data).lower()


class SortableTable(QFrame):
    """Reusable sortable table widget."""
    
    species_selected = Signal(str)  # Emits species name when double-clicked

    def __init__(self, title: str, headers: list, parent=None):
        super().__init__(parent)
        self._title = title
        self._headers = headers
        self._setup_ui()

    def _setup_ui(self):
        t = theme()

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: none;
                border-radius: {t.get('radius_lg')};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        title_label = QLabel(self._title)
        title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: {t.font_size('lg')};
            color: {t.get('text_heading')};
        """)
        layout.addWidget(title_label)

        self._model = SortableTableModel(self._headers)
        self._proxy = NumericSortProxyModel()
        self._proxy.setSourceModel(self._model)

        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(self._headers)):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        self.table.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        # Height controlled by parent frame, not internal table
        self._apply_table_style()
        layout.addWidget(self.table)

    def _on_row_double_clicked(self, index):
        """Handle double-click on a row to navigate to filtered data."""
        source_index = self._proxy.mapToSource(index)
        row = source_index.row()
        if row >= 0 and row < self._model.rowCount():
            species_name = self._model._data[row][0]  # First column is species
            self.species_selected.emit(species_name)

    def _on_cell_clicked(self, index):
        """Handle single click - check if VCs column was clicked."""
        source_index = self._proxy.mapToSource(index)
        col = source_index.column()
        row = source_index.row()
        # Column 2 is VCs
        if col == 2 and row >= 0 and row < self._model.rowCount():
            species_name = self._model._data[row][0]  # First column is species
            self.vc_count_clicked.emit(species_name)

    def _apply_table_style(self):
        t = theme()
        self.table.setStyleSheet(f"""
            QTableView {{
                background-color: {t.get('surface')};
                border: none;
                outline: none;
                selection-background-color: transparent;
            }}
            QTableView::item {{
                padding: 6px 8px;
            }}
            QTableView::item:hover {{
                background-color: {t.get('hover')};
            }}
            QTableView::item:selected {{
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
                color: {t.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_secondary')};
                border: none;
                padding: 8px;
                font-weight: 600;
            }}
            QHeaderView::section:hover {{
                background-color: {t.get('hover')};
            }}
        """)

    def set_data(self, data: list, keys: list):
        rows = []
        for item in data:
            row = [item.get(key, '') for key in keys]
            rows.append(row)
        self._model.set_data(rows)

    def apply_theme(self):
        t = theme()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: none;
                border-radius: {t.get('radius_lg')};
            }}
        """)
        self._apply_table_style()



# ============================================================================
# VICE COUNTY EXPLORER
# ============================================================================

class VCExplorer(QFrame):
    """Vice County Explorer with dropdown selector and summary stats."""
    
    view_details_clicked = Signal(int)  # Emits vc_number
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._vc_data = []  # List of {vc_number, vc_name, species, records}
        self._selected_vc = None
        self._setup_ui()
    
    def _setup_ui(self):
        t = theme()
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: none;
                border-radius: {t.get('radius_lg')};
            }}
        """)
        
        self.setMinimumHeight(300)
        self.setMaximumHeight(400)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        title_label = QLabel("Vice County Explorer")
        title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: {t.font_size('lg')};
            color: {t.get('text_heading')};
        """)
        layout.addWidget(title_label)
        
        # VC Selector row
        selector_row = QHBoxLayout()
        selector_row.setSpacing(8)
        
        vc_label = QLabel("Select VC:")
        vc_label.setStyleSheet(f"color: {t.get('text_secondary')};")
        selector_row.addWidget(vc_label)
        
        self.vc_combo = QComboBox()
        self.vc_combo.setMinimumWidth(250)
        self.vc_combo.setEditable(True)
        self.vc_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.vc_combo.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.vc_combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.vc_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {t.get('surface_alt')};
                border: none;
                border-radius: {t.get('radius_sm')};
                padding: 6px 10px;
                color: {t.get('text_primary')};
            }}
            QComboBox:focus {{
                border-color: {TabColors.RECORDING_SCHEME};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
        """)
        self.vc_combo.currentIndexChanged.connect(self._on_vc_selected)
        # Select all text when clicking in the combo box for easy replacement
        self.vc_combo.lineEdit().mousePressEvent = lambda e: (self.vc_combo.lineEdit().selectAll(), e.accept())
        selector_row.addWidget(self.vc_combo)
        
        # Clear button
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedWidth(60)
        self.clear_btn.setToolTip("Clear search")
        self.clear_btn.clicked.connect(self._on_clear_search)
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_secondary')};
                border: none;
                border-radius: {t.get('radius_sm')};
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background-color: {t.get('surface_alt')};
            }}
        """)
        selector_row.addWidget(self.clear_btn)
        
        selector_row.addStretch()
        layout.addLayout(selector_row)
        
        # Summary stats panel
        self.summary_frame = QFrame()
        self.summary_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface_alt')};
                border: none;
                border-radius: {t.get('radius_md')};
                padding: 12px;
            }}
        """)
        summary_layout = QVBoxLayout(self.summary_frame)
        summary_layout.setSpacing(8)
        
        self.vc_title_label = QLabel("No vice county selected")
        self.vc_title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: {t.font_size('md')};
            color: {t.get('text_heading')};
        """)
        summary_layout.addWidget(self.vc_title_label)
        
        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(24)
        
        self.species_stat = QLabel("Species: -")
        self.species_stat.setStyleSheet(f"color: {t.get('text_primary')};")
        stats_row.addWidget(self.species_stat)
        
        self.records_stat = QLabel("Records: -")
        self.records_stat.setStyleSheet(f"color: {t.get('text_primary')};")
        stats_row.addWidget(self.records_stat)
        
        stats_row.addStretch()
        summary_layout.addLayout(stats_row)
        
        layout.addWidget(self.summary_frame)
        
        # View Details button
        self.view_btn = QPushButton("View VC Details...")
        self.view_btn.setEnabled(False)
        self.view_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {TabColors.RECORDING_SCHEME};
                color: white;
                border: none;
                border-radius: {t.get('radius_sm')};
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {TabColors.RECORDING_SCHEME_DARK};
            }}
            QPushButton:disabled {{
                background-color: {t.get('border')};
                color: {t.get('text_secondary')};
            }}
        """)
        self.view_btn.clicked.connect(self._on_view_details)
        layout.addWidget(self.view_btn)
        
        layout.addStretch()
    
    def _on_vc_selected(self, index):
        """Handle VC selection change."""
        if index < 0 or index >= len(self._vc_data):
            self._selected_vc = None
            self._update_summary(None)
            return

        vc_info = self._vc_data[index]
        self._selected_vc = vc_info['vc_number']
        self._update_summary(vc_info)

    def _on_clear_search(self):
        """Clear the search and reset display."""
        self.vc_combo.setCurrentIndex(-1)
        self.vc_combo.lineEdit().clear()
        self.vc_title_label.setText("No vice county selected")
        self.species_stat.setText("Species: --")
        self.records_stat.setText("Records: --")

    def _update_summary(self, vc_info):
        """Update the summary panel with VC info."""
        t = theme()
        
        if vc_info is None:
            self.vc_title_label.setText("No vice county selected")
            self.species_stat.setText("Species: -")
            self.records_stat.setText("Records: -")
            self.view_btn.setEnabled(False)
            return
        
        vc_name = vc_info.get('vc_name', f"VC{vc_info['vc_number']}")
        self.vc_title_label.setText(f"VC{vc_info['vc_number']} - {vc_name}")
        self.species_stat.setText(f"Species: {vc_info.get('species', 0):,}")
        self.records_stat.setText(f"Records: {vc_info.get('records', 0):,}")
        self.view_btn.setEnabled(True)
    
    def _on_view_details(self):
        """Emit signal to open details dialog."""
        if self._selected_vc is not None:
            self.view_details_clicked.emit(self._selected_vc)
    
    def set_data(self, vc_data: list):
        """Set the VC data and populate dropdown."""
        self._vc_data = sorted(vc_data, key=lambda x: x.get('vc_number', 0))
        
        # Block signals while updating
        self.vc_combo.blockSignals(True)
        self.vc_combo.clear()
        
        for vc in self._vc_data:
            vc_num = vc.get('vc_number', 0)
            vc_name = vc.get('vc_name', f"VC{vc_num}")
            self.vc_combo.addItem(f"VC{vc_num} - {vc_name}")
        
        self.vc_combo.blockSignals(False)
        
        # Don't auto-select - start with empty state
        self.vc_combo.setCurrentIndex(-1)
        self.vc_title_label.setText("No vice county selected")
        self.species_stat.setText("Species: --")
        self.records_stat.setText("Records: --")
    
    def apply_theme(self):
        t = theme()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: none;
                border-radius: {t.get('radius_lg')};
            }}
        """)


# ============================================================================
# ENHANCED COMPONENT 1: Activity Feed for County Firsts
# ============================================================================

class CountyFirstsTable(QFrame):
    """Simple table showing recent county first records."""
    
    species_selected = Signal(str)  # Emits species name when double-clicked
    species_vc_selected = Signal(str, int)  # Emits species name and VC number
    record_selected = Signal(int)  # Emits record_id when clicked to navigate to specific record

    def __init__(self, title: str = "Recent County Firsts", parent=None):
        super().__init__(parent)
        self._title = title
        self._setup_ui()

    def _setup_ui(self):
        t = theme()

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: none;
                border-radius: {t.get('radius_lg')};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Header
        title_label = QLabel(self._title)
        title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: {t.font_size('lg')};
            color: {t.get('text_heading')};
        """)
        layout.addWidget(title_label)

        # Table
        self._headers = ["Date", "Species", "VC", "County"]
        self._model = SortableTableModel(self._headers)
        self._proxy = NumericSortProxyModel()
        self._proxy.setSourceModel(self._model)

        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        # Default sort by date descending (newest first)
        self.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        self.table.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        # Height controlled by parent frame, not internal table
        self._apply_table_style()
        layout.addWidget(self.table)

    def _on_row_double_clicked(self, index):
        """Handle double-click on a row to navigate to the specific record."""
        source_index = self._proxy.mapToSource(index)
        row = source_index.row()
        if row >= 0 and row < self._model.rowCount():
            # Get the record_id for this row and emit navigation signal
            if hasattr(self, '_record_ids') and row < len(self._record_ids):
                record_id = self._record_ids[row]
                if record_id:
                    self.record_selected.emit(record_id)
                    return
            # Fallback to species/vc selection if no record_id
            species_name = self._model._data[row][1]  # Second column is species (Date, Species, VC, County)
            vc_str = self._model._data[row][2]  # Third column is VC (e.g., "VC55")
            try:
                vc_number = int(vc_str.replace("VC", ""))
            except:
                vc_number = 0
            self.species_vc_selected.emit(species_name, vc_number)

    def _apply_table_style(self):
        t = theme()
        self.table.setStyleSheet(f"""
            QTableView {{
                background-color: {t.get('surface')};
                alternate-background-color: {t.get('surface_alt')};
                border: none;
                gridline-color: transparent;
                selection-background-color: transparent;
                outline: 0;
            }}
            QTableView::item {{
                padding: 6px 8px;
                color: {t.get('text_primary')};
            }}
            QTableView::item:selected {{
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
                color: {t.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface')};
                color: {t.get('text_secondary')};
                font-weight: 600;
                padding: 8px;
                border: none;
                border-bottom: 1px solid {t.get('border')};
            }}
        """)

    def set_data(self, firsts: list):
        """Set the county firsts data."""
        from ...utils.date_utils import format_date_for_display
        
        self._record_ids = []  # Store record IDs for navigation
        rows = []
        for item in firsts:
            date_raw = item.get('date', '')  # Keep raw ISO date for proper sorting
            species = str(item.get('species', ''))
            vc_num = item.get('vc_number', 0)
            record_id = item.get('record_id')
            from ...core.vc_shortnames import get_short_name
            vc_name = get_short_name(vc_num)
            rows.append([date_raw, species, f"VC{vc_num}", vc_name])
            self._record_ids.append(record_id)
        
        self._model.set_data(rows)

    def apply_theme(self):
        t = theme()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: none;
                border-radius: {t.get('radius_lg')};
            }}
        """)
        self._apply_table_style()

# ============================================================================
# ENHANCED COMPONENT 2: Species List with Filter Chips
# ============================================================================

class FilterChip(QPushButton):
    """Toggleable filter chip button."""
    
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self._setup_style()
        self.toggled.connect(self._on_toggled)
    
    def _setup_style(self):
        t = theme()
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_secondary')};
                border: none;
                border-radius: 12px;
                padding: 4px 12px;
                font-size: {t.font_size('sm')};
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
            }}
            QPushButton:checked {{
                background-color: {TabColors.RECORDING_SCHEME};
                color: white;
                border-color: {TabColors.RECORDING_SCHEME};
            }}
        """)
    
    def _on_toggled(self, checked):
        self._setup_style()


class SearchableSpeciesTable(QFrame):
    """Species table with search and filter chips."""
    
    species_selected = Signal(str)  # Emits species name when double-clicked
    vc_count_clicked = Signal(str)  # Emits species name when VCs column clicked

    def __init__(self, title: str = "Species List", parent=None):
        super().__init__(parent)
        self._title = title
        self._all_data = []
        self._setup_ui()

    def _setup_ui(self):
        t = theme()

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: none;
                border-radius: {t.get('radius_lg')};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Header row with title and search
        header_row = QHBoxLayout()
        
        title_label = QLabel(self._title)
        title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: {t.font_size('lg')};
            color: {t.get('text_heading')};
        """)
        header_row.addWidget(title_label)
        header_row.addStretch()
        
        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search species...")
        self.search_box.setFixedWidth(180)
        self.search_box.setStyleSheet(f"""
            QLineEdit {{
                background-color: {t.get('surface_alt')};
                border: none;
                border-radius: {t.get('radius_sm')};
                padding: 6px 10px;
                color: {t.get('text_primary')};
            }}
            QLineEdit:focus {{
                border-color: {TabColors.RECORDING_SCHEME};
            }}
        """)
        self.search_box.textChanged.connect(self._apply_filters)
        header_row.addWidget(self.search_box)
        
        layout.addLayout(header_row)
        
        # Search controls row
        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)
        
        # Clear button for search
        self.clear_search_btn = QPushButton("Clear")
        self.clear_search_btn.setFixedWidth(60)
        self.clear_search_btn.setToolTip("Clear search")
        self.clear_search_btn.clicked.connect(self._on_clear_search)
        self.clear_search_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_secondary')};
                border: none;
                border-radius: {t.get('radius_sm')};
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background-color: {t.get('surface_alt')};
            }}
        """)
        controls_row.addWidget(self.clear_search_btn)
        
        controls_row.addStretch()
        
        self.results_label = QLabel("")
        self.results_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')};")
        controls_row.addWidget(self.results_label)
        layout.addLayout(controls_row)

        # Model and proxy
        self._headers = ["Species", "Records", "VCs"]
        self._model = SortableTableModel(self._headers)
        self._proxy = NumericSortProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(0)

        # Table view
        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        self.table.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        self.table.clicked.connect(self._on_cell_clicked)
        # Height controlled by parent frame, not internal table
        self._apply_table_style()
        layout.addWidget(self.table)

    def _on_row_double_clicked(self, index):
        """Handle double-click on a row to navigate to filtered data."""
        source_index = self._proxy.mapToSource(index)
        row = source_index.row()
        if row >= 0 and row < self._model.rowCount():
            species_name = self._model._data[row][0]  # First column is species
            self.species_selected.emit(species_name)

    def _on_cell_clicked(self, index):
        """Handle single click - check if VCs column was clicked."""
        source_index = self._proxy.mapToSource(index)
        col = source_index.column()
        row = source_index.row()
        # Column 2 is VCs
        if col == 2 and row >= 0 and row < self._model.rowCount():
            species_name = self._model._data[row][0]  # First column is species
            self.vc_count_clicked.emit(species_name)

    def _apply_table_style(self):
        t = theme()
        self.table.setStyleSheet(f"""
            QTableView {{
                background-color: {t.get('surface')};
                border: none;
                outline: none;
                selection-background-color: transparent;
            }}
            QTableView::item {{
                padding: 6px 8px;
            }}
            QTableView::item:hover {{
                background-color: {t.get('hover')};
            }}
            QTableView::item:selected {{
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
                color: {t.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_secondary')};
                border: none;
                padding: 8px;
                font-weight: 600;
            }}
            QHeaderView::section:hover {{
                background-color: {t.get('hover')};
            }}
        """)

    def _on_clear_search(self):
        """Clear the search box."""
        self.search_box.clear()

    def _apply_filters(self):
        """Apply search filter."""
        search_text = self.search_box.text().lower()

        filtered_data = []
        for item in self._all_data:
            species = item.get('species', '').lower()
            records = item.get('records', 0)
            vc_count = item.get('vc_count', 0)

            # Search filter
            if search_text and search_text not in species:
                continue

            # Capitalize only genus (first word), keep rest lowercase
            parts = species.split(' ', 1)
            if len(parts) > 1:
                formatted = parts[0].capitalize() + ' ' + parts[1].lower()
            else:
                formatted = species.capitalize()
            filtered_data.append([formatted, records, vc_count])

        self._model.set_data(filtered_data)
        self.results_label.setText(f"{len(filtered_data)} of {len(self._all_data)} species")

    def set_data(self, data: list):
        """Set species data. data is list of dicts with species, records, vc_count."""
        self._all_data = data
        self._apply_filters()

    def apply_theme(self):
        t = theme()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: none;
                border-radius: {t.get('radius_lg')};
            }}
        """)
        self._apply_table_style()


# ============================================================================
# ENHANCED COMPONENT 3: Tiered Recording Gaps
# ============================================================================

class RecordingGapsTable(QFrame):
    """Table showing species that need recording attention."""
    
    species_selected = Signal(str)  # Emits species name when double-clicked

    def __init__(self, title: str = "Recording Gaps", parent=None):
        super().__init__(parent)
        self._title = title
        self._setup_ui()

    def _setup_ui(self):
        t = theme()

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: none;
                border-radius: {t.get('radius_lg')};
            }}
        """)

        self.setMinimumHeight(400)
        self.setMaximumHeight(600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Header
        title_label = QLabel(self._title)
        title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: {t.font_size('lg')};
            color: {t.get('text_heading')};
        """)
        layout.addWidget(title_label)

        # Subtitle
        subtitle = QLabel("Species not recorded in 3+ years")
        subtitle.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')};")
        layout.addWidget(subtitle)

        # Table
        self._headers = ["Species", "Last Recorded", "Years Ago"]
        self._model = SortableTableModel(self._headers)
        self._proxy = NumericSortProxyModel()
        self._proxy.setSourceModel(self._model)

        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        self.table.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_table_style()
        layout.addWidget(self.table)

    def _on_row_double_clicked(self, index):
        """Handle double-click on a row to navigate to filtered data."""
        source_index = self._proxy.mapToSource(index)
        row = source_index.row()
        if row >= 0 and row < self._model.rowCount():
            species_name = self._model._data[row][0]  # First column is species (Species, Last Recorded, Years Ago)
            self.species_selected.emit(species_name)

    def _apply_table_style(self):
        t = theme()
        self.table.setStyleSheet(f"""
            QTableView {{
                background-color: {t.get('surface')};
                alternate-background-color: {t.get('surface_alt')};
                border: none;
                gridline-color: transparent;
                selection-background-color: transparent;
                outline: 0;
            }}
            QTableView::item {{
                padding: 6px 8px;
                color: {t.get('text_primary')};
            }}
            QTableView::item:selected {{
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
                color: {t.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface')};
                color: {t.get('text_secondary')};
                font-weight: 600;
                padding: 8px;
                border: none;
                border-bottom: 1px solid {t.get('border')};
            }}
        """)

    def set_data(self, gaps: list):
        """Set the recording gaps data."""
        rows = []
        for item in gaps:
            species = item.get('species', '')
            last_recorded = item.get('last_recorded', '')  # Raw date for proper sorting
            years_ago = item.get('years_ago', 0)
            rows.append([species, last_recorded, years_ago])
        
        self._model.set_data(rows)

    def apply_theme(self):
        t = theme()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: none;
                border-radius: {t.get('radius_lg')};
            }}
        """)
        self._apply_table_style()


    def _apply_table_style(self):
        t = theme()
        self.table.setStyleSheet(f"""
            QTableView {{
                background-color: {t.get('surface')};
                alternate-background-color: {t.get('surface_alt')};
                border: none;
                gridline-color: transparent;
                selection-background-color: transparent;
                outline: 0;
            }}
            QTableView::item {{
                padding: 6px 8px;
                color: {t.get('text_primary')};
            }}
            QTableView::item:selected {{
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
                color: {t.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface')};
                color: {t.get('text_secondary')};
                font-weight: 600;
                padding: 8px;
                border: none;
                border-bottom: 1px solid {t.get('border')};
            }}
        """)

    def set_data(self, gaps: list):
        """Set the recording gaps data."""
        rows = []
        for item in gaps:
            species = item.get('species', '')
            last_recorded = item.get('last_recorded', '')  # Raw date for proper sorting
            years_ago = item.get('years_ago', 0)
            rows.append([species, last_recorded, years_ago])
        
        self._model.set_data(rows)

    def apply_theme(self):
        t = theme()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: none;
                border-radius: {t.get('radius_lg')};
            }}
        """)
        self._apply_table_style()


class VCDetailsDialog(QDialog):
    """Dialog showing detailed stats for a specific Vice County."""
    
    def __init__(self, vc_number: int, vc_name: str, stats_data: dict, parent=None):
        super().__init__(parent)
        self.vc_number = vc_number
        self.vc_name = vc_name
        self.stats_data = stats_data
        self._setup_ui()
        self.apply_theme()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle(f"VC{self.vc_number} - {self.vc_name}")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header with VC name
        header = QLabel(f"VC{self.vc_number} - {self.vc_name}")
        header.setObjectName("vc_details_header")
        layout.addWidget(header)
        
        # Stats summary row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        
        species_count = self.stats_data.get('species', 0)
        records_count = self.stats_data.get('records', 0)
        
        self.species_card = StatCard("Species", str(species_count), "")
        self.records_card = StatCard("Records", str(records_count), "")
        stats_row.addWidget(self.species_card)
        stats_row.addWidget(self.records_card)
        stats_row.addStretch()
        layout.addLayout(stats_row)
        
        # Tab widget for different views
        self.tabs = QTabWidget()
        
        # Tab 1: Species List
        self.species_tab = QWidget()
        species_layout = QVBoxLayout(self.species_tab)
        self.species_table = SortableTable("Species in this Vice County", ["Species", "Common Name", "Records", "First Record"])
        species_layout.addWidget(self.species_table)
        self.tabs.addTab(self.species_tab, "Species List")
        
        # Tab 2: County Firsts
        self.firsts_tab = QWidget()
        firsts_layout = QVBoxLayout(self.firsts_tab)
        self.firsts_table = SortableTable("County Firsts", ["Date", "Species", "Common Name", "Recorder"])
        firsts_layout.addWidget(self.firsts_table)
        self.tabs.addTab(self.firsts_tab, "County Firsts")
        
        # Tab 3: Records Over Time
        self.timeline_tab = QWidget()
        timeline_layout = QVBoxLayout(self.timeline_tab)
        self.timeline_chart = MonthlyActivityChart("Records Over Time")
        timeline_layout.addWidget(self.timeline_chart)
        self.tabs.addTab(self.timeline_tab, "Timeline")

        # Tab 4: Recording Gaps
        self.gaps_tab = QWidget()
        gaps_layout = QVBoxLayout(self.gaps_tab)
        self.gaps_table = SortableTable(
            "Recording Gaps (3+ years)",
            ["Species", "Common Name", "Last Recorded", "Years Ago"]
        )
        gaps_layout.addWidget(self.gaps_table)
        self.tabs.addTab(self.gaps_tab, "Recording Gaps")
        
        layout.addWidget(self.tabs)
        

        # Export CSV button
        export_btn = QPushButton("Export CSV")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.clicked.connect(self._export_active_tab)
        # Close button
        button_row = QHBoxLayout()
        button_row.addWidget(export_btn)
        button_row.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        button_row.addWidget(self.close_btn)
        layout.addLayout(button_row)
        
        # Populate data
        self._populate_data()
    
    def _export_active_tab(self):
        """Export the currently active tab data to CSV."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import csv, os
        tab_index = self.tabs.currentIndex()
        tab_names = ["Species", "County_Firsts", "Timeline", "Recording_Gaps"]
        tables = [self.species_table, self.firsts_table, None, self.gaps_table]
        tab_name = tab_names[tab_index] if tab_index < len(tab_names) else "data"
        tbl = tables[tab_index] if tab_index < len(tables) else None
        if tbl is None:
            QMessageBox.information(self, "Export", "This tab cannot be exported.")
            return
        # Extract data from SortableTable model
        model = tbl._model
        headers = model._headers
        data = model._data
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV",
            os.path.expanduser(f"~/Desktop/{tab_name}_{self.windowTitle().replace(" ", "_")}.csv"),
            "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for row in data:
                    writer.writerow(row)
            QMessageBox.information(self, "Exported", f"Exported {len(data)} rows to:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))

    def _populate_data(self):
        """Populate tables with VC-specific data."""
        # Species list
        species_list = self.stats_data.get('species_list', [])
        if species_list:
            self.species_table.set_data(species_list, ['species_name', 'common_name', 'record_count', 'first_date'])
        
        # County firsts
        firsts_list = self.stats_data.get('county_firsts', [])
        if firsts_list:
            self.firsts_table.set_data(firsts_list, ['date', 'species_name', 'common_name', 'recorder'])
        
        # Timeline data
        monthly_data = self.stats_data.get('monthly_records', [])
        if monthly_data:
            self.timeline_chart.set_data(monthly_data)

        # Recording gaps
        gaps_list = self.stats_data.get('recording_gaps', [])
        if gaps_list:
            self.gaps_table.set_data(gaps_list, ['species_name', 'common_name', 'last_recorded', 'years_ago'])
    
    def apply_theme(self):
        """Apply current theme to the dialog."""
        from ...themes import theme
        from ...core.config import ButtonColors
        t = theme()
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {t.get('background')};
            }}
            QLabel#vc_details_header {{
                font-size: 18px;
                font-weight: bold;
                color: {t.get('text_primary')};
                padding: 8px 0;
            }}
            QTabWidget::pane {{
                border: none;
                background-color: {t.get('surface')};
                border-radius: 4px;
            }}
            QTabBar::tab {{
                background-color: {t.get('surface')};
                color: {t.get('text_secondary')};
                padding: 8px 16px;
                border: none;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{
                background-color: {t.get('background')};
                color: {t.get('text_primary')};
            }}
            QPushButton {{
                background-color: transparent;
                color: {ButtonColors.SECONDARY};
                border: 1px solid {ButtonColors.SECONDARY};
                padding: 8px 24px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {ButtonColors.SECONDARY};
                color: #ffffff;
            }}
        """)
        
        self.species_card.apply_theme()
        self.records_card.apply_theme()
        self.species_table.apply_theme()
        self.firsts_table.apply_theme()
        self.timeline_chart.apply_theme()

class SchemeDashboard(QScrollArea):
    """Dashboard for recording scheme organisers."""
    
    species_selected = Signal(str)  # Emits species name to navigate to filtered data
    species_vc_selected = Signal(str, int)  # Emits species name and VC number
    data_filters_changed = Signal()  # Emitted when exclusion filters toggled
    record_selected = Signal(int)  # Emits record_id when clicked to navigate to specific record
    vc_details_requested = Signal(str)  # Emits species name to show VC details dialog

    def __init__(self, parent=None):
        super().__init__(parent)
        t = theme()

        self.setWidgetResizable(True)
        self.setStyleSheet(f"QScrollArea {{ border: none; background-color: {t.get('background')}; }}")

        container = QWidget()
        self.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(24)

        # Row 1: Stat Cards
        self._setup_stats_cards(layout)

        # Filter chips row (genus-only, s.s., s.l., aggregates)
        self._setup_filter_chips(layout)

        # Row 2: Vice County table (sortable) + County Firsts (activity feed)
        self._setup_vc_row(layout)

        # Row 3: Species List (searchable with chips) + Recording Gaps (tiered)
        self._setup_species_gaps_row(layout)

        # Row 4: Monthly Distribution
        self._setup_monthly_chart(layout)

        # Row 5: Full VC Table (to be tidied later)
        self._setup_vc_table(layout)

        layout.addStretch()

    def _setup_stats_cards(self, layout):
        """Set up stat cards."""
        accent = TabColors.RECORDING_SCHEME

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        self.total_species_card = StatCard("Total Species", "0", "scheme records", accent)
        cards_layout.addWidget(self.total_species_card)

        self.total_records_card = StatCard("Total Records", "0", "scheme records", accent)
        cards_layout.addWidget(self.total_records_card)

        self.hectads_card = StatCard("Hectads", "0", "10km squares", accent)
        cards_layout.addWidget(self.hectads_card)

        self.tetrads_card = StatCard("Tetrads", "0", "2km squares", accent)
        cards_layout.addWidget(self.tetrads_card)

        self.vcs_card = StatCard("Vice Counties", "0", "covered", accent)
        cards_layout.addWidget(self.vcs_card)

        layout.addLayout(cards_layout)

    def _setup_filter_chips(self, layout):
        """Set up filter chips for excluding genus-only, s.s., s.l., aggregates."""
        from PySide6.QtCore import QSettings
        t = theme()
        
        chips_row = QHBoxLayout()
        chips_row.setSpacing(12)
        
        # Label
        filter_label = QLabel("Exclude:")
        filter_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')};")
        chips_row.addWidget(filter_label)
        
        # Load saved settings
        settings = QSettings()
        
        # Genus-only filter
        self.filter_genus = FilterChip("Genus-only")
        self.filter_genus.setChecked(settings.value("stats/scheme_exclude_genus", False, type=bool))
        self.filter_genus.toggled.connect(self._on_filter_changed)
        chips_row.addWidget(self.filter_genus)
        
        # s.s. filter
        self.filter_ss = FilterChip("s.s.")
        self.filter_ss.setChecked(settings.value("stats/scheme_exclude_ss", False, type=bool))
        self.filter_ss.toggled.connect(self._on_filter_changed)
        chips_row.addWidget(self.filter_ss)
        
        # s.l. filter
        self.filter_sl = FilterChip("s.l.")
        self.filter_sl.setChecked(settings.value("stats/scheme_exclude_sl", False, type=bool))
        self.filter_sl.toggled.connect(self._on_filter_changed)
        chips_row.addWidget(self.filter_sl)
        
        # Aggregates filter
        self.filter_agg = FilterChip("Aggregates")
        self.filter_agg.setChecked(settings.value("stats/scheme_exclude_agg", False, type=bool))
        self.filter_agg.toggled.connect(self._on_filter_changed)
        chips_row.addWidget(self.filter_agg)

        # Family-only filter (names ending in -idae/-inae)
        self.filter_family = FilterChip("Family-only")
        self.filter_family.setChecked(settings.value("stats/scheme_exclude_family", False, type=bool))
        self.filter_family.toggled.connect(self._on_filter_changed)
        chips_row.addWidget(self.filter_family)
        
        chips_row.addStretch()
        layout.addLayout(chips_row)

    def _on_filter_changed(self):
        """Handle filter chip toggle - save to settings and refresh."""
        from PySide6.QtCore import QSettings
        settings = QSettings()
        settings.setValue("stats/scheme_exclude_genus", self.filter_genus.isChecked())
        settings.setValue("stats/scheme_exclude_ss", self.filter_ss.isChecked())
        settings.setValue("stats/scheme_exclude_sl", self.filter_sl.isChecked())
        settings.setValue("stats/scheme_exclude_agg", self.filter_agg.isChecked())
        settings.setValue("stats/scheme_exclude_family", self.filter_family.isChecked())
        # Invalidate cache so refresh recomputes with new filter settings
        from .scheme_dashboard import get_recording_scheme_stats
        stats_svc = get_recording_scheme_stats()
        stats_svc.invalidate()
        self.refresh()
        self.data_filters_changed.emit()

    def _setup_vc_row(self, layout):
        """Vice County Explorer and county firsts activity feed."""
        row = QHBoxLayout()
        row.setSpacing(24)

        # VC Explorer with dropdown selector
        self.vc_explorer = VCExplorer()
        self.vc_explorer.view_details_clicked.connect(self._on_vc_details_clicked)
        row.addWidget(self.vc_explorer)

        # County firsts activity feed
        self.firsts_feed = CountyFirstsTable("Recent County Firsts")
        row.addWidget(self.firsts_feed)

        layout.addLayout(row)

    def _on_vc_table_row_clicked(self, index):
        """Handle click on All Vice Counties table row ? open VC details dialog."""
        try:
            source_index = self.vc_table._proxy.mapToSource(index)
            row = source_index.row()
            vc_index = self.vc_table._model.index(row, 0)
            vc_text = self.vc_table._model.data(vc_index)
            if vc_text:
                vc_number = int(vc_text)
                self._on_vc_details_clicked(vc_number)
        except Exception as e:
            print(f"[SchemeDashboard] Error handling VC table click: {e}")

    def _on_vc_details_clicked(self, vc_number):
        """Handle click on View VC Details button."""
        # Get VC name from the data
        vc_name = ""
        vc_stats = {"species": 0, "records": 0, "species_list": [], "county_firsts": [], "monthly_records": []}
        
        # Find VC data from stats service
        try:
            from ...models.database import get_database
            from ...services.recording_scheme_stats_service import get_recording_scheme_stats
            
            stats_service = get_recording_scheme_stats()
            
            # Get VC-specific stats
            vc_stats = stats_service.get_vc_details(vc_number)
            vc_name = vc_stats.get("vc_name", f"Vice County {vc_number}")
        except Exception as e:
            print(f"[SchemeDashboard] Error getting VC stats: {e}")
            vc_name = f"Vice County {vc_number}"
        
        dialog = VCDetailsDialog(vc_number, vc_name, vc_stats, self)
        dialog.exec()

    def _setup_species_gaps_row(self, layout):
        """Species list (searchable with chips) and recording gaps (tiered)."""
        row = QHBoxLayout()
        row.setSpacing(24)

        # Searchable species list with filter chips
        self.species_table = SearchableSpeciesTable("Species List")
        row.addWidget(self.species_table)

        # Tiered recording gaps
        self.gaps_display = RecordingGapsTable("Recording Gaps")
        row.addWidget(self.gaps_display)
        
        # Connect species selection signals from all tables
        self.species_table.species_selected.connect(self._on_species_selected)
        self.species_table.vc_count_clicked.connect(self._on_vc_count_clicked)
        self.firsts_feed.species_vc_selected.connect(self._on_species_vc_selected)
        self.firsts_feed.record_selected.connect(self._on_record_selected)
        self.gaps_display.species_selected.connect(self._on_species_selected)

        layout.addLayout(row)

    def _setup_monthly_chart(self, layout):
        """Monthly distribution chart with species filter."""
        self.monthly_chart = MonthlyActivityChart("Monthly Distribution of Records", show_species_filter=True)
        self.monthly_chart.species_changed.connect(self._on_monthly_species_changed)
        layout.addWidget(self.monthly_chart)

    def _on_monthly_species_changed(self, species_name: str):
        """Handle species filter change for monthly chart."""
        from ...services.recording_scheme_stats_service import get_recording_scheme_stats
        stats_service = get_recording_scheme_stats()
        if species_name:
            # Get monthly counts for specific species
            monthly_counts = stats_service.get_monthly_counts_by_species(species_name)
        else:
            # Get all species monthly counts
            monthly_counts = stats_service.get('monthly_counts', [])
        if monthly_counts and len(monthly_counts) == 12:
            self.monthly_chart.set_data(monthly_counts)

    def _setup_vc_table(self, layout):
        """Full VC table at bottom - to be tidied in later phase."""
        self.vc_table = SortableTable("All Vice Counties", ["VC", "Name", "Species", "Records"])
        self.vc_table.setMinimumHeight(750)
        self.vc_table.setMaximumHeight(1200)
        self.vc_table.table.clicked.connect(self._on_vc_table_row_clicked)
        layout.addWidget(self.vc_table)

    def refresh(self):
        """Refresh the dashboard with data from the stats service."""
        try:
            from ...models.database import get_database
            stats_service = get_recording_scheme_stats()
            stats_service.initialize(get_database())
            stats = stats_service.get_all()  # Uses cache if valid

            # Stat cards
            self.total_species_card.set_value(f"{stats.get('total_species', 0):,}", "scheme records")
            self.total_records_card.set_value(f"{stats.get('total_records', 0):,}", "scheme records")
            self.hectads_card.set_value(f"{stats.get('hectads_count', 0):,}", "10km squares")
            self.tetrads_card.set_value(f"{stats.get('tetrads_count', 0):,}", "2km squares")
            self.vcs_card.set_value(f"{stats.get('unique_vice_counties', 0):,}", "covered")

            # Monthly chart
            monthly_counts = stats.get('monthly_counts', [])
            if monthly_counts and len(monthly_counts) == 12:
                self.monthly_chart.set_data(monthly_counts)

            # VC table (sortable)
            records_by_vc = stats.get('records_by_vc', [])
            if records_by_vc:
                self.vc_explorer.set_data(records_by_vc)
                self.vc_table.set_data(records_by_vc, ['vc_number', 'vc_name', 'species', 'records'])

            # Species list (searchable with chips)
            species_list = stats.get('species_list', [])
            if species_list:
                self.species_table.set_data(species_list)
                # Populate monthly chart species filter
                species_names = [s.get('species', s.get('species_name', '')) for s in species_list]
                self.monthly_chart.set_species_list(species_names)

            # County firsts (activity feed)
            county_firsts = stats.get('county_firsts', [])
            if county_firsts:
                self.firsts_feed.set_data(county_firsts)

            # Recording gaps (tiered)
            recording_gaps = stats.get('recording_gaps', [])
            if recording_gaps:
                self.gaps_display.set_data(recording_gaps)

        except Exception as e:
            print(f"[SchemeDashboard] Error refreshing: {e}")
            import traceback
            traceback.print_exc()

    def _on_species_selected(self, species_name: str):
        """Handle species selection from any table - emit to parent for navigation."""
        self.species_selected.emit(species_name)

    def _on_species_vc_selected(self, species_name: str, vc_number: int):
        """Handle species+VC selection from county firsts - emit to parent for navigation."""
        self.species_vc_selected.emit(species_name, vc_number)

    def _on_record_selected(self, record_id: int):
        """Handle record selection from county firsts - emit to parent for navigation."""
        self.record_selected.emit(record_id)

    def _on_vc_count_clicked(self, species_name: str):
        """Handle VC count click - show dialog with VCs for this species."""
        self._show_species_vc_dialog(species_name)

    def _show_species_vc_dialog(self, species_name: str):
        """Show a dialog listing all VCs where this species has been recorded."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton
        from PySide6.QtCore import Qt
        from ...services.recording_scheme_stats_service import get_recording_scheme_stats
        from ...models.database import get_database
        
        # Query VCs for this species
        try:
            stats_service = get_recording_scheme_stats()
            stats_service.initialize(get_database())
            
            query = """
                SELECT 
                    vc_number,
                    COUNT(*) as record_count,
                    MIN(date) as first_date,
                    MAX(date) as last_date
                FROM recording_scheme
                WHERE species_name = ?
                AND vc_number IS NOT NULL
                GROUP BY vc_number
                ORDER BY vc_number
            """
            results = stats_service._db.execute_main(query, (species_name,))
            
            if not results:
                return
            
            # Create dialog
            t = theme()
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Vice Counties for {species_name}")
            dialog.setMinimumSize(700, 450)
            dialog.setStyleSheet(f"background-color: {t.get('surface')};")
            
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(16)
            
            # Header
            header = QLabel(f"<b>{species_name}</b><br><span style='color: {t.get("text_secondary")}'>Recorded in {len(results)} Vice Counties</span>")
            header.setStyleSheet(f"font-size: 16px; color: {t.get('text_primary')};")
            layout.addWidget(header)
            
            # Table
            table = QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["VC", "County Name", "Records", "First Record", "Last Record"])
            table.cellClicked.connect(lambda row, col: self._on_vc_table_cell_clicked(row, col, table, species_name))
            table.setRowCount(len(results))
            table.setAlternatingRowColors(True)
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setSortingEnabled(True)
            table.horizontalHeader().setSortIndicatorShown(True)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            table.setStyleSheet(f"""
                QTableWidget {{
                    background-color: {t.get('surface')};
                    alternate-background-color: {t.get('surface_alt')};
                    border: 1px solid {t.get('border')};
                    border-radius: 4px;
                    gridline-color: {t.get('border')};
                    color: {t.get('text_primary')};
                    selection-background-color: #e8e0f0;
                    selection-color: {t.get('text_primary')};
                    outline: 0;
                }}
                QTableWidget::item {{
                    padding: 4px 8px;
                    border: none;
                }}
                QTableWidget::item:selected {{
                    background-color: #e8e0f0;
                    color: {t.get('text_primary')};
                }}
                QTableWidget::item:hover {{
                    background-color: {t.get('surface_alt')};
                }}
                QHeaderView::section {{
                    background-color: {t.get('surface')};
                    color: {t.get('text_secondary')};
                    padding: 8px;
                    border: none;
                    border-bottom: 1px solid {t.get('border')};
                    font-weight: 600;
                }}
            """)
            table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            table.setShowGrid(False)
            
            from ...core.vc_shortnames import get_short_name
            
            for row_idx, row in enumerate(results):
                vc_num = row['vc_number']
                vc_name = get_short_name(vc_num)
                record_count = row['record_count']
                first_date = row['first_date'] or ''
                last_date = row['last_date'] or ''
                
                table.setItem(row_idx, 0, QTableWidgetItem(f"VC{vc_num}"))
                table.setItem(row_idx, 1, QTableWidgetItem(vc_name))
                
                count_item = QTableWidgetItem(str(record_count))
                count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_idx, 2, count_item)
                
                # Format dates as dd/mm/yyyy
                def format_date(d):
                    if not d or len(d) < 10:
                        return ''
                    # Input is YYYY-MM-DD, output dd/mm/yyyy
                    return f"{d[8:10]}/{d[5:7]}/{d[:4]}"
                
                table.setItem(row_idx, 3, QTableWidgetItem(format_date(first_date)))
                table.setItem(row_idx, 4, QTableWidgetItem(format_date(last_date)))
            
            layout.addWidget(table, 1)
            
            # Export CSV button
            def _do_export(_tbl=table, _dlg=dialog):
                from PySide6.QtWidgets import QFileDialog, QMessageBox
                import csv, os
                headers = [_tbl.horizontalHeaderItem(c).text() for c in range(_tbl.columnCount())]
                path, _ = QFileDialog.getSaveFileName(_dlg, "Export CSV",
                    os.path.expanduser("~/Desktop/export.csv"), "CSV Files (*.csv)")
                if not path:
                    return
                try:
                    with open(path, "w", newline="", encoding="utf-8-sig") as f:
                        writer = csv.writer(f)
                        writer.writerow(headers)
                        for r in range(_tbl.rowCount()):
                            writer.writerow([_tbl.item(r, c).text() if _tbl.item(r, c) else "" for c in range(_tbl.columnCount())])
                    QMessageBox.information(_dlg, "Exported", f"Exported {_tbl.rowCount()} rows to:\n{path}")
                except Exception as e:
                    QMessageBox.warning(_dlg, "Export Failed", str(e))
            export_btn = QPushButton("Export CSV")
            export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            export_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {{t.get("surface")}};
                    color: {{t.get("primary", "#4a7c59")}};
                    border: 1px solid {{t.get("primary", "#4a7c59")}};
                    border-radius: 4px;
                    padding: 8px 20px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {{t.get("primary", "#4a7c59")}};
                    color: white;
                }}
            """)
            export_btn.clicked.connect(_do_export)

            btn_row = QHBoxLayout()
            btn_row.addWidget(export_btn)
            btn_row.addStretch()
            # Close button
            close_btn = QPushButton("Close")
            close_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.get('surface')};
                    color: {t.get('text_primary')};
                    border: 1px solid {t.get('border')};
                    padding: 8px 24px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: {t.get('surface_alt')};
                }}
            """)
            close_btn.clicked.connect(dialog.accept)
            btn_row.addWidget(close_btn)
            layout.addLayout(btn_row)
            
            dialog.exec()
            
        except Exception as e:
            print(f"Error showing VC details: {e}")
            import traceback
            traceback.print_exc()

    def _on_vc_table_cell_clicked(self, row: int, col: int, table, species_name: str):
        """Handle click on VC table - if Records column, show records dialog."""
        if col == 2:  # Records column
            vc_item = table.item(row, 0)
            if vc_item:
                vc_text = vc_item.text()  # e.g., "VC21"
                vc_number = int(vc_text.replace("VC", ""))
                self._show_species_vc_records_dialog(species_name, vc_number)

    def _show_species_vc_records_dialog(self, species_name: str, vc_number: int):
        """Show dialog with all records for a species in a specific VC."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton
        from PySide6.QtCore import Qt
        from ...services.recording_scheme_stats_service import get_recording_scheme_stats
        from ...models.database import get_database
        from ...core.vc_shortnames import get_short_name
        
        try:
            stats_service = get_recording_scheme_stats()
            stats_service.initialize(get_database())
            
            query = """
                SELECT 
                    id, date, site_name, grid_ref, recorder, 
                    determiner, verification_status, source
                FROM recording_scheme
                WHERE species_name = ?
                AND vc_number = ?
                ORDER BY date DESC
            """
            results = stats_service._db.execute_main(query, (species_name, vc_number))
            
            if not results:
                return
            
            # Create dialog
            t = theme()
            vc_name = get_short_name(vc_number)
            
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Records for {species_name} in VC{vc_number}")
            dialog.setMinimumSize(900, 500)
            dialog.setStyleSheet(f"background-color: {t.get('surface')};")
            
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(16)
            
            # Header
            header = QLabel(f"<b>{species_name}</b><br><span style='color: {t.get("text_secondary")}'>VC{vc_number} - {vc_name} ({len(results)} records)</span>")
            header.setStyleSheet(f"font-size: 16px; color: {t.get('text_primary')};")
            layout.addWidget(header)
            
            # Table
            table = QTableWidget()
            table.setColumnCount(6)
            table.setHorizontalHeaderLabels(["Date", "Location", "Grid Ref", "Recorder", "Status", "Source"])
            table.setRowCount(len(results))
            table.setAlternatingRowColors(True)
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setSortingEnabled(True)
            table.horizontalHeader().setSortIndicatorShown(True)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            table.setStyleSheet(f"""
                QTableWidget {{
                    background-color: {t.get('surface')};
                    alternate-background-color: {t.get('surface_alt')};
                    border: 1px solid {t.get('border')};
                    border-radius: 4px;
                    gridline-color: {t.get('border')};
                    color: {t.get('text_primary')};
                    selection-background-color: #e8e0f0;
                    selection-color: {t.get('text_primary')};
                    outline: 0;
                }}
                QTableWidget::item {{
                    padding: 4px 8px;
                    border: none;
                }}
                QTableWidget::item:selected {{
                    background-color: #e8e0f0;
                    color: {t.get('text_primary')};
                }}
                QTableWidget::item:hover {{
                    background-color: {t.get('surface_alt')};
                }}
                QHeaderView::section {{
                    background-color: {t.get('surface')};
                    color: {t.get('text_secondary')};
                    padding: 8px;
                    border: none;
                    border-bottom: 1px solid {t.get('border')};
                    font-weight: 600;
                }}
            """)
            table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            table.setShowGrid(False)
            
            # Store record IDs for click handling
            record_ids = []
            
            for row_idx, row in enumerate(results):
                record_id = row['id']
                record_ids.append(record_id)
                
                date_raw = row['date'] or ''
                # Format date as dd/mm/yyyy
                def format_date(d):
                    if not d or len(d) < 10:
                        return ''
                    return f"{d[8:10]}/{d[5:7]}/{d[:4]}"
                
                location = row['site_name'] or ''
                grid_ref = row['grid_ref'] or ''
                recorder = row['recorder'] or ''
                status = row['verification_status'] or ''
                source = row['source'] or ''
                
                table.setItem(row_idx, 0, QTableWidgetItem(format_date(date_raw)))
                table.setItem(row_idx, 1, QTableWidgetItem(location))
                table.setItem(row_idx, 2, QTableWidgetItem(grid_ref))
                table.setItem(row_idx, 3, QTableWidgetItem(recorder))
                table.setItem(row_idx, 4, QTableWidgetItem(status))
                table.setItem(row_idx, 5, QTableWidgetItem(source))
            
            # Connect double-click to open record detail
            table.doubleClicked.connect(lambda idx: self._on_record_table_double_clicked(idx, record_ids, species_name, vc_number))
            
            layout.addWidget(table, 1)
            
            # Info label
            info_label = QLabel("Double-click a row to view full record details")
            info_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
            layout.addWidget(info_label)
            
            # Export CSV button
            def _do_export(_tbl=table, _dlg=dialog):
                from PySide6.QtWidgets import QFileDialog, QMessageBox
                import csv, os
                headers = [_tbl.horizontalHeaderItem(c).text() for c in range(_tbl.columnCount())]
                path, _ = QFileDialog.getSaveFileName(_dlg, "Export CSV",
                    os.path.expanduser("~/Desktop/export.csv"), "CSV Files (*.csv)")
                if not path:
                    return
                try:
                    with open(path, "w", newline="", encoding="utf-8-sig") as f:
                        writer = csv.writer(f)
                        writer.writerow(headers)
                        for r in range(_tbl.rowCount()):
                            writer.writerow([_tbl.item(r, c).text() if _tbl.item(r, c) else "" for c in range(_tbl.columnCount())])
                    QMessageBox.information(_dlg, "Exported", f"Exported {_tbl.rowCount()} rows to:\n{path}")
                except Exception as e:
                    QMessageBox.warning(_dlg, "Export Failed", str(e))
            export_btn = QPushButton("Export CSV")
            export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            export_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {{t.get("surface")}};
                    color: {{t.get("primary", "#4a7c59")}};
                    border: 1px solid {{t.get("primary", "#4a7c59")}};
                    border-radius: 4px;
                    padding: 8px 20px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {{t.get("primary", "#4a7c59")}};
                    color: white;
                }}
            """)
            export_btn.clicked.connect(_do_export)

            btn_row = QHBoxLayout()
            btn_row.addWidget(export_btn)
            btn_row.addStretch()
            # Close button
            close_btn = QPushButton("Close")
            close_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.get('surface')};
                    color: {t.get('text_primary')};
                    border: 1px solid {t.get('border')};
                    padding: 8px 24px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: {t.get('surface_alt')};
                }}
            """)
            close_btn.clicked.connect(dialog.accept)
            btn_row.addWidget(close_btn)
            layout.addLayout(btn_row)
            
            dialog.exec()
            
        except Exception as e:
            print(f"Error showing records for {species_name} in VC{vc_number}: {e}")
            import traceback
            traceback.print_exc()

    def _on_record_table_double_clicked(self, index, record_ids: list, species_name: str, vc_number: int):
        """Handle double-click on a record row to show full detail dialog."""
        from ...services.recording_scheme_stats_service import get_recording_scheme_stats
        from ...models.database import get_database
        from ..dialogs import SchemeRecordDetailDialog
        
        row = index.row()
        if row >= 0 and row < len(record_ids):
            record_id = record_ids[row]
            
            try:
                stats_service = get_recording_scheme_stats()
                stats_service.initialize(get_database())
                
                query = "SELECT * FROM recording_scheme WHERE id = ?"
                results = stats_service._db.execute_main(query, (record_id,))
                
                if results:
                    row_data = results[0]
                    record = dict(row_data)
                    record['species'] = record.get('species_name', '')
                    record['common'] = record.get('common_name', '')
                    record['location'] = record.get('site_name', '')
                    record['gridRef'] = record.get('grid_ref', '')
                    record['vc'] = record.get('vc_number', '')
                    record['verification'] = record.get('verification_status', '')
                    
                    dialog = SchemeRecordDetailDialog(record, parent=self)
                    dialog.exec()
                    
            except Exception as e:
                print(f"Error showing record detail: {e}")
                import traceback
                traceback.print_exc()

    def apply_theme(self):
        """Apply the current theme to all components."""
        t = theme()
        self.setStyleSheet(f"QScrollArea {{ border: none; background-color: {t.get('background')}; }}")

        self.total_species_card.apply_theme()
        self.total_records_card.apply_theme()
        self.hectads_card.apply_theme()
        self.tetrads_card.apply_theme()
        self.vcs_card.apply_theme()
        self.vc_explorer.apply_theme()
        self.species_table.apply_theme()
        self.firsts_feed.apply_theme()
        self.gaps_display.apply_theme()
        self.monthly_chart.apply_theme()
        self.vc_table.apply_theme()
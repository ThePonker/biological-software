"""
Insect Collection Stats Dashboard Component.

Dashboard for collection managers showing:
- Total specimens/species
- Specimens by Order/Family (clickable to filter)
- Year by year breakdown
- Storage location breakdown
- Recent additions
"""

from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Signal, Qt

from .stat_widgets import StatCard
from ...themes import theme
from ...utils.date_utils import format_date_display
from ...core.config import TabColors
from ...services.specimen_stats_service import get_specimen_stats
from ...views.dialogs.species_list_dialog import SpeciesListDialog


class ClickableDataTable(QFrame):
    """Reusable data table widget with clickable rows."""
    
    row_clicked = Signal(str, str)  # (filter_type, value)
    species_clicked = Signal(str, str)  # (filter_type, value) when species column clicked
    
    def __init__(self, title: str, columns: list, filter_type: str = None, parent=None):
        super().__init__(parent)
        self._title = title
        self._columns = columns
        self._filter_type = filter_type
        self._setup_ui()
    
    def _setup_ui(self):
        t = theme()
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        title_label = QLabel(self._title)
        title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: {t.font_size('lg')};
            color: {t.get('text_heading')};
        """)
        layout.addWidget(title_label)
        
        self.table = QTableWidget()
        self.table.setColumnCount(len(self._columns))
        self.table.setHorizontalHeaderLabels(self._columns)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(self._columns)):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        
        # Make clickable
        if self._filter_type:
            self.table.setCursor(Qt.CursorShape.PointingHandCursor)
            self.table.cellClicked.connect(self._on_cell_clicked)
        
        # Disable selection styling - just hover
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {t.get('surface')};
                border: none;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QTableWidget::item:hover {{
                background-color: {t.get('hover')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_secondary')};
                border: none;
                padding: 6px;
                font-weight: 600;
            }}
        """)
        layout.addWidget(self.table)
    
    def _on_cell_clicked(self, row, col):
        """Handle cell click."""
        item = self.table.item(row, 0)
        if item and self._filter_type:
            name = item.text()
            # Column 2 is Species - emit species_clicked signal
            if col == 2:
                self.species_clicked.emit(self._filter_type, name)
            else:
                self.row_clicked.emit(self._filter_type, name)
            self.table.clearSelection()
    
    def set_data(self, data: list, key_field: str, value_fields: list = None, max_rows: int = None):
        """Set table data."""
        if value_fields is None:
            value_fields = ['specimens', 'species']
        
        if max_rows:
            data = data[:max_rows]
        
        self.table.setRowCount(len(data))
        
        for row, item in enumerate(data):
            name_item = QTableWidgetItem(str(item.get(key_field, '')))
            self.table.setItem(row, 0, name_item)
            
            for col, field in enumerate(value_fields, start=1):
                val = item.get(field, 0)
                cell = QTableWidgetItem(f"{val:,}" if isinstance(val, int) else str(val))
                cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, col, cell)
        
        # Resize to fit content
        self.table.resizeRowsToContents()
        self.table.setMinimumHeight(180)
    
    def apply_theme(self):
        t = theme()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
        """)


class SimpleBreakdownTable(QFrame):
    """Simple two-column breakdown table."""
    
    row_clicked = Signal(str, str)  # (filter_type, value)
    
    def __init__(self, title: str, key_header: str = "Category", value_header: str = "Count", filter_type: str = None, parent=None):
        super().__init__(parent)
        self._filter_type = filter_type
        self._title = title
        self._key_header = key_header
        self._value_header = value_header
        self._setup_ui()
    
    def _setup_ui(self):
        t = theme()
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        title_label = QLabel(self._title)
        title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: {t.font_size('lg')};
            color: {t.get('text_heading')};
        """)
        layout.addWidget(title_label)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels([self._key_header, self._value_header])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        
        # Make clickable if filter_type provided
        if self._filter_type:
            self.table.setCursor(Qt.CursorShape.PointingHandCursor)
            self.table.cellClicked.connect(self._on_cell_clicked)
        
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {t.get('surface')};
                border: none;
                outline: none;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
            }}
            QTableWidget::item:hover {{
                background-color: {t.get('hover')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_secondary')};
                border: none;
                padding: 6px;
                font-weight: 600;
            }}
        """)
        layout.addWidget(self.table)
    
    def _on_cell_clicked(self, row: int, column: int):
        """Handle cell click to filter by this value."""
        key_item = self.table.item(row, 0)
        if key_item and self._filter_type:
            value = key_item.text()
            self.row_clicked.emit(self._filter_type, value)
            self.table.clearSelection()

    def set_data(self, data: list, key_field: str, value_field: str = 'count'):
        """Set table data."""
        self.table.setRowCount(len(data))
        for row, item in enumerate(data):
            key_item = QTableWidgetItem(str(item.get(key_field, '')))
            self.table.setItem(row, 0, key_item)
            
            val = item.get(value_field, 0)
            val_item = QTableWidgetItem(f"{val:,}" if isinstance(val, int) else str(val))
            val_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 1, val_item)
        
        self.table.resizeRowsToContents()
        self.table.setMinimumHeight(180)
    
    def apply_theme(self):
        t = theme()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
        """)


class YearBreakdownTable(QFrame):
    """Table showing specimens and new species by year."""
    
    year_clicked = Signal(str)  # Emits the year when a row is clicked
    species_clicked = Signal(str)  # Emits year when species column clicked
    new_species_clicked = Signal(str)  # Emits year when new species column clicked
    
    def __init__(self, title: str = "Specimens and Species by Year", parent=None):
        super().__init__(parent)
        self._title = title
        self._setup_ui()
    
    def _setup_ui(self):
        t = theme()
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        title_label = QLabel(self._title)
        title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: {t.font_size('lg')};
            color: {t.get('text_heading')};
        """)
        layout.addWidget(title_label)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['Year', 'Specimens', 'Species', 'New Species'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 4):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setSortingEnabled(True)
        self.table.cellClicked.connect(self._on_row_clicked)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {t.get('surface')};
                border: none;
                outline: none;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
            }}
            QTableWidget::item:hover {{
                background-color: {t.get('hover')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_secondary')};
                border: none;
                padding: 6px;
                font-weight: 600;
            }}
        """)
        layout.addWidget(self.table)
    
    def set_data(self, by_year: list, new_by_year: list):
        """Set table data."""
        new_lookup = {item['year']: item['new_species'] for item in new_by_year}
        
        self.table.setRowCount(len(by_year))
        for row, item in enumerate(by_year):
            year = item.get('year', '')
            
            year_item = QTableWidgetItem(str(year))
            self.table.setItem(row, 0, year_item)
            
            specimens = item.get('specimens', 0)
            spec_item = QTableWidgetItem(f"{specimens:,}")
            spec_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 1, spec_item)
            
            species = item.get('species', 0)
            species_item = QTableWidgetItem(f"{species:,}")
            species_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, species_item)
            
            new_species = new_lookup.get(year, 0)
            new_item = QTableWidgetItem(f"{new_species:,}")
            new_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 3, new_item)
        
        self.table.resizeRowsToContents()
        self.table.setMinimumHeight(180)
    

    def _on_row_clicked(self, row: int, column: int):
        """Handle click on a row - different signals for different columns."""
        year_item = self.table.item(row, 0)
        if year_item:
            year = year_item.text()
            # Column 2 is Species, Column 3 is New Species
            if column == 2:
                self.species_clicked.emit(year)
            elif column == 3:
                self.new_species_clicked.emit(year)
            else:
                self.year_clicked.emit(year)
            self.table.clearSelection()

    def apply_theme(self):
        t = theme()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
        """)


class RecentSpecimensList(QFrame):
    """List showing recently added specimens."""
    
    view_more_clicked = Signal()
    specimen_clicked = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        t = theme()
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Header
        header = QHBoxLayout()
        title_label = QLabel("Recent Additions")
        title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: {t.font_size('lg')};
            color: {t.get('text_heading')};
        """)
        header.addWidget(title_label)
        header.addStretch()
        
        view_more = QLabel("View more →")
        view_more.setStyleSheet(f"color: {TabColors.COLLECTION}; font-size: {t.font_size('sm')};")
        view_more.setCursor(Qt.CursorShape.PointingHandCursor)
        view_more.mousePressEvent = lambda e: self.view_more_clicked.emit()
        header.addWidget(view_more)
        layout.addLayout(header)
        
        # List container
        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(6)
        layout.addWidget(self.list_widget)
        layout.addStretch()
    
    def set_data(self, specimens: list):
        """Set specimens list data."""
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        t = theme()
        
        for specimen in specimens[:10]:
            specimen_id = specimen.get('id')
            
            item = QFrame()
            item.setCursor(Qt.CursorShape.PointingHandCursor)
            item.setStyleSheet(f"""
                QFrame {{
                    background-color: {t.get('surface_alt')};
                    border-radius: {t.get('radius_sm')};
                }}
                QFrame:hover {{
                    background-color: {t.get('hover')};
                }}
            """)
            
            if specimen_id:
                item.mousePressEvent = lambda e, sid=specimen_id: self.specimen_clicked.emit(sid)
            
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(8, 6, 8, 6)
            
            species_label = QLabel(specimen.get('species', ''))
            species_label.setStyleSheet(f"font-style: italic; color: {t.get('text_primary')};")
            item_layout.addWidget(species_label)
            item_layout.addStretch()
            
            if specimen.get('date'):
                # Format date as DD/MM/YYYY - dates stored as "D MMM YY"
                date_str = specimen['date']
                formatted = format_date_display(date_str, "user")
                if formatted:
                    date_str = formatted
                date_label = QLabel(date_str)
                date_label.setStyleSheet(f"color: {t.get('text_muted')}; font-size: {t.font_size('sm')};")
                item_layout.addWidget(date_label)
            
            self.list_layout.addWidget(item)
    
    def apply_theme(self):
        t = theme()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
        """)


class CollectionStatsDashboard(QScrollArea):
    """Dashboard for insect collection statistics."""

    view_all_specimens_requested = Signal()
    filter_by_order_requested = Signal(str)
    filter_by_family_requested = Signal(str)
    filter_by_year_requested = Signal(str)
    filter_by_condition_requested = Signal(str)
    filter_by_prep_type_requested = Signal(str)
    filter_by_storage_requested = Signal(str)
    specimen_detail_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = None
        t = theme()

        self.setWidgetResizable(True)
        self.setStyleSheet(f"QScrollArea {{ border: none; background-color: {t.get('background')}; }}")

        container = QWidget()
        self.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Row 1: Stat Cards
        self._setup_stats_cards(layout)

        # Row 2: Order + Family + Recent Additions (3 columns)
        self._setup_main_row(layout)

        # Row 4: Condition + Prep type + Storage
        self._setup_bottom_row(layout)

        layout.addStretch()

    def _setup_stats_cards(self, layout):
        """Set up stat cards."""
        accent = TabColors.COLLECTION
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        self.total_specimens_card = StatCard("Total Specimens", "0", "in collection", accent)
        cards_layout.addWidget(self.total_specimens_card)

        self.total_species_card = StatCard("Total Species", "0", "represented", accent)
        cards_layout.addWidget(self.total_species_card)

        self.orders_card = StatCard("Orders", "0", "represented", accent)
        cards_layout.addWidget(self.orders_card)

        self.families_card = StatCard("Families", "0", "represented", accent)
        cards_layout.addWidget(self.families_card)

        self.vcs_card = StatCard("Vice Counties", "0", "sourced from", accent)
        cards_layout.addWidget(self.vcs_card)

        layout.addLayout(cards_layout)

    def _setup_main_row(self, layout):
        """Order + Family + Recent Additions."""
        row = QHBoxLayout()
        row.setSpacing(16)

        self.order_table = ClickableDataTable(
            "Specimens & Species by Order", 
            ["Order", "Specimens", "Species"],
            filter_type="order"
        )
        self.order_table.row_clicked.connect(self._on_order_clicked)
        self.order_table.species_clicked.connect(self._on_order_species_clicked)
        row.addWidget(self.order_table, 1)

        self.family_table = ClickableDataTable(
            "Specimens & Species by Family", 
            ["Family", "Specimens", "Species"],
            filter_type="family"
        )
        self.family_table.row_clicked.connect(self._on_family_clicked)
        self.family_table.species_clicked.connect(self._on_family_species_clicked)
        row.addWidget(self.family_table, 1)

        self.recent_list = RecentSpecimensList()
        self.recent_list.view_more_clicked.connect(self.view_all_specimens_requested.emit)
        self.recent_list.specimen_clicked.connect(self.specimen_detail_requested.emit)
        row.addWidget(self.recent_list, 1)

        layout.addLayout(row)


    def _setup_bottom_row(self, layout):
        """Year breakdown, Condition, prep type, and storage."""
        row = QHBoxLayout()
        row.setSpacing(16)

        self.year_table = YearBreakdownTable("Specimens and Species by Year")
        self.year_table.year_clicked.connect(self._on_year_clicked)
        self.year_table.species_clicked.connect(self._on_year_species_clicked)
        self.year_table.new_species_clicked.connect(self._on_year_new_species_clicked)
        row.addWidget(self.year_table)

        self.condition_table = SimpleBreakdownTable("Condition", "Condition", "Count", filter_type="condition")
        self.condition_table.row_clicked.connect(self._on_condition_clicked)
        row.addWidget(self.condition_table)

        self.prep_table = SimpleBreakdownTable("Preparation Type", "Type", "Count", filter_type="prep_type")
        self.prep_table.row_clicked.connect(self._on_prep_type_clicked)
        row.addWidget(self.prep_table)

        self.storage_table = SimpleBreakdownTable("Storage Locations", "Location", "Specimens", filter_type="storage")
        self.storage_table.row_clicked.connect(self._on_storage_clicked)
        row.addWidget(self.storage_table)

        layout.addLayout(row)

    def _on_year_clicked(self, year: str):
        """Handle year row click."""
        self.filter_by_year_requested.emit(year)

    def _on_order_species_clicked(self, filter_type: str, order_name: str):
        """Handle species column click in order table."""
        self._show_species_dialog(f"Species in {order_name}", 'order', order_name)

    def _on_family_species_clicked(self, filter_type: str, family_name: str):
        """Handle species column click in family table."""
        self._show_species_dialog(f"Species in {family_name}", 'family', family_name)

    def _on_year_species_clicked(self, year: str):
        """Handle species column click in year table."""
        self._show_species_dialog(f"Species in {year}", 'year', year)

    def _on_year_new_species_clicked(self, year: str):
        """Handle new species column click in year table."""
        self._show_species_dialog(f"New Species in {year}", 'new_species_year', year)

    def _show_species_dialog(self, title: str, filter_type: str, filter_value: str):
        """Show dialog with species list."""
        from ...models.database import get_database
        
        # Get species data from service
        service = get_specimen_stats()
        service.initialize(get_database())
        species_data = service.get_species_list(filter_type, filter_value)
        
        if species_data:
            dialog = SpeciesListDialog(title, species_data, parent=self)
            dialog.exec()
        else:
            # No data - could show a message, but for now just do nothing
            pass

    def _on_condition_clicked(self, filter_type: str, value: str):
        """Handle condition row click."""
        self.filter_by_condition_requested.emit(value)

    def _on_prep_type_clicked(self, filter_type: str, value: str):
        """Handle preparation type row click."""
        self.filter_by_prep_type_requested.emit(value)

    def _on_storage_clicked(self, filter_type: str, value: str):
        """Handle storage location row click."""
        self.filter_by_storage_requested.emit(value)

    def _on_order_clicked(self, filter_type: str, value: str):
        self.filter_by_order_requested.emit(value)

    def _on_family_clicked(self, filter_type: str, value: str):
        self.filter_by_family_requested.emit(value)

    def initialize(self, db):
        self._db = db

    def clear_all_selections(self):
        """Clear selections from all tables."""
        if hasattr(self, 'order_table') and hasattr(self.order_table, 'table'):
            self.order_table.table.clearSelection()
        if hasattr(self, 'family_table') and hasattr(self.family_table, 'table'):
            self.family_table.table.clearSelection()
        if hasattr(self, 'year_table') and hasattr(self.year_table, 'table'):
            self.year_table.table.clearSelection()
        if hasattr(self, 'condition_table') and hasattr(self.condition_table, 'table'):
            self.condition_table.table.clearSelection()
        if hasattr(self, 'prep_table') and hasattr(self.prep_table, 'table'):
            self.prep_table.table.clearSelection()
        if hasattr(self, 'storage_table') and hasattr(self.storage_table, 'table'):
            self.storage_table.table.clearSelection()

    def showEvent(self, event):
        """Clear selections when dashboard becomes visible."""
        super().showEvent(event)
        self.clear_all_selections()

    def refresh(self):
        """Refresh the dashboard."""
        self.clear_all_selections()
        try:
            from ...models.database import get_database
            stats_service = get_specimen_stats()
            stats_service.initialize(get_database())
            stats_service.refresh()
            stats = stats_service.get_all()
            
            # Stat cards
            self.total_specimens_card.set_value(f"{stats.get('total_specimens', 0):,}", "in collection")
            self.total_species_card.set_value(f"{stats.get('total_species', 0):,}", "represented")
            
            specimens_by_order = stats.get('specimens_by_order', [])
            self.orders_card.set_value(f"{len(specimens_by_order):,}", "represented")
            
            specimens_by_family = stats.get('specimens_by_family', [])
            self.families_card.set_value(f"{len(specimens_by_family):,}", "represented")
            
            self.vcs_card.set_value(f"{stats.get('unique_vice_counties', 0):,}", "sourced from")

            # Order table - all orders (usually few)
            if specimens_by_order:
                self.order_table.set_data(specimens_by_order, 'label', ['specimens', 'species'])

            # Family table - top 15
            if specimens_by_family:
                self.family_table.set_data(specimens_by_family, 'family', ['specimens', 'species'], max_rows=15)

            # Year by year
            by_year = stats.get('specimens_by_year', [])
            new_by_year = stats.get('new_species_by_year', [])
            if by_year:
                self.year_table.set_data(by_year, new_by_year)

            # Storage
            specimens_by_storage = stats.get('specimens_by_storage', [])
            if specimens_by_storage:
                self.storage_table.set_data(specimens_by_storage, 'location', 'count')

            # Condition
            specimens_by_condition = stats.get('specimens_by_condition', [])
            if specimens_by_condition:
                self.condition_table.set_data(specimens_by_condition, 'condition', 'count')

            # Prep type
            specimens_by_prep = stats.get('specimens_by_prep_type', [])
            if specimens_by_prep:
                self.prep_table.set_data(specimens_by_prep, 'prep_type', 'count')

            # Recent additions
            recent = stats.get('recent_specimens', [])
            if recent:
                self.recent_list.set_data(recent)

        except Exception as e:
            print(f"[CollectionStatsDashboard] Error refreshing: {e}")
            import traceback
            traceback.print_exc()

    def apply_theme(self):
        t = theme()
        self.setStyleSheet(f"QScrollArea {{ border: none; background-color: {t.get('background')}; }}")
        self.total_specimens_card.apply_theme()
        self.total_species_card.apply_theme()
        self.orders_card.apply_theme()
        self.families_card.apply_theme()
        self.vcs_card.apply_theme()
        self.order_table.apply_theme()
        self.family_table.apply_theme()
        self.recent_list.apply_theme()
        self.year_table.apply_theme()
        self.condition_table.apply_theme()
        self.prep_table.apply_theme()
        self.storage_table.apply_theme()

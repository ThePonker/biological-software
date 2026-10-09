"""
Column Selector Dialog - Two-Panel Interface.

A reusable dialog for selecting and ordering table columns.
Used by Insect Collection, Observation Data, and Recording Scheme tabs.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from ...themes import theme
from ...core.config import TabColors


class ColumnSelectorDialog(QDialog):
    """Two-panel dialog for selecting and ordering columns."""
    
    columns_changed = Signal()
    
    def __init__(self, table_model, tab_color=None, parent=None):
        """
        Initialize the column selector dialog.
        
        Args:
            table_model: Model with ALL_COLUMNS, _visible_columns, _column_order
            tab_color: Theme color for this tab (e.g., TabColors.COLLECTION)
            parent: Parent widget
        """
        super().__init__(parent)
        self._table_model = table_model
        self._tab_color = tab_color or TabColors.COLLECTION
        self._setup_ui()
        self._load_columns()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        t = theme()
        self.setWindowTitle("Configure Columns")
        self.setMinimumWidth(550)
        self.setMinimumHeight(500)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Header
        header = QLabel("Select and arrange columns to display:")
        header.setStyleSheet(f"color: {t.get('text_primary')}; font-size: {t.font_size('sm')};")
        layout.addWidget(header)
        
        # Main panels area
        panels_layout = QHBoxLayout()
        panels_layout.setSpacing(8)
        
        # Left panel - Available columns
        left_panel = QVBoxLayout()
        left_label = QLabel("Available Columns")
        left_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-weight: 600;")
        left_panel.addWidget(left_label)
        
        self._available_list = QListWidget()
        self._available_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._available_list.setStyleSheet(self._get_list_style())
        self._available_list.itemDoubleClicked.connect(self._on_add_clicked)
        left_panel.addWidget(self._available_list)
        
        panels_layout.addLayout(left_panel)
        
        # Center buttons - Add/Remove
        center_buttons = QVBoxLayout()
        center_buttons.setSpacing(6)
        center_buttons.addStretch()
        
        add_btn = QPushButton("Add →")
        add_btn.setFixedWidth(100)
        add_btn.setStyleSheet(self._get_action_btn_style())
        add_btn.clicked.connect(self._on_add_clicked)
        center_buttons.addWidget(add_btn)
        
        remove_btn = QPushButton("← Remove")
        remove_btn.setFixedWidth(100)
        remove_btn.setStyleSheet(self._get_action_btn_style())
        remove_btn.clicked.connect(self._on_remove_clicked)
        center_buttons.addWidget(remove_btn)
        
        center_buttons.addSpacing(16)
        
        add_all_btn = QPushButton("Add All »")
        add_all_btn.setFixedWidth(100)
        add_all_btn.setStyleSheet(self._get_secondary_btn_style())
        add_all_btn.clicked.connect(self._on_add_all_clicked)
        center_buttons.addWidget(add_all_btn)
        
        remove_all_btn = QPushButton("« Remove All")
        remove_all_btn.setFixedWidth(100)
        remove_all_btn.setStyleSheet(self._get_secondary_btn_style())
        remove_all_btn.clicked.connect(self._on_remove_all_clicked)
        center_buttons.addWidget(remove_all_btn)
        
        center_buttons.addStretch()
        panels_layout.addLayout(center_buttons)
        
        # Right panel - Displayed columns
        right_panel = QVBoxLayout()
        right_label = QLabel("Displayed Columns (in order)")
        right_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-weight: 600;")
        right_panel.addWidget(right_label)
        
        right_content = QHBoxLayout()
        
        self._displayed_list = QListWidget()
        self._displayed_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._displayed_list.setStyleSheet(self._get_list_style())
        self._displayed_list.itemDoubleClicked.connect(self._on_remove_clicked)
        right_content.addWidget(self._displayed_list)
        
        # Up/Down buttons for displayed list
        order_buttons = QVBoxLayout()
        order_buttons.setSpacing(6)
        order_buttons.addStretch()
        
        up_btn = QPushButton("▲")
        up_btn.setFixedSize(32, 32)
        up_btn.setStyleSheet(self._get_arrow_btn_style())
        up_btn.setToolTip("Move selected column up")
        up_btn.clicked.connect(self._on_move_up)
        order_buttons.addWidget(up_btn)
        
        down_btn = QPushButton("▼")
        down_btn.setFixedSize(32, 32)
        down_btn.setStyleSheet(self._get_arrow_btn_style())
        down_btn.setToolTip("Move selected column down")
        down_btn.clicked.connect(self._on_move_down)
        order_buttons.addWidget(down_btn)
        
        order_buttons.addStretch()
        right_content.addLayout(order_buttons)
        
        right_panel.addLayout(right_content)
        panels_layout.addLayout(right_panel)
        
        layout.addLayout(panels_layout)
        
        # Legend
        legend = QLabel("* = Mandatory column (cannot be removed)")
        legend.setStyleSheet(f"color: {t.get('text_muted')}; font-size: {t.font_size('xs')}; font-style: italic;")
        layout.addWidget(legend)
        
        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        reset_btn = QPushButton("Reset Defaults")
        reset_btn.setStyleSheet(self._get_secondary_btn_style())
        reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(reset_btn)
        
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(self._get_secondary_btn_style())
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet(self._get_primary_btn_style())
        apply_btn.clicked.connect(self._apply_changes)
        btn_layout.addWidget(apply_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_columns(self):
        """Load columns into the two lists."""
        self._available_list.clear()
        self._displayed_list.clear()
        
        # Build column lookup (key -> (header, mandatory))
        col_lookup = {}
        for col in self._table_model.ALL_COLUMNS:
            col_key = col[0]
            col_header = col[1]
            mandatory = col[3] if len(col) > 3 else False
            if col_key != 'checkbox':
                col_lookup[col_key] = (col_header, mandatory)
        
        # Get current visible columns and order
        visible = getattr(self._table_model, '_visible_columns', set())
        current_order = getattr(self._table_model, '_column_order', None)
        
        if not current_order:
            current_order = [c[0] for c in self._table_model.ALL_COLUMNS if c[0] != 'checkbox']
        
        # Displayed columns (in order)
        displayed_keys = set()
        for col_key in current_order:
            if col_key in col_lookup:
                col_header, mandatory = col_lookup[col_key]
                if mandatory or col_key in visible:
                    self._add_to_displayed(col_key, col_header, mandatory)
                    displayed_keys.add(col_key)
        
        # Available columns (not displayed)
        for col_key, (col_header, mandatory) in col_lookup.items():
            if col_key not in displayed_keys and not mandatory:
                self._add_to_available(col_key, col_header)
    
    def _add_to_available(self, col_key: str, col_header: str):
        """Add a column to the available list."""
        item = QListWidgetItem(col_header)
        item.setData(Qt.ItemDataRole.UserRole, col_key)
        self._available_list.addItem(item)
    
    def _add_to_displayed(self, col_key: str, col_header: str, mandatory: bool):
        """Add a column to the displayed list."""
        t = theme()
        display_text = f"{col_header} *" if mandatory else col_header
        item = QListWidgetItem(display_text)
        item.setData(Qt.ItemDataRole.UserRole, col_key)
        item.setData(Qt.ItemDataRole.UserRole + 1, mandatory)
        
        if mandatory:
            item.setForeground(QColor(self._tab_color))
        
        self._displayed_list.addItem(item)
    
    def _on_add_clicked(self, item=None):
        """Move selected columns from available to displayed."""
        selected = self._available_list.selectedItems()
        if not selected:
            return
        
        for item in selected:
            col_key = item.data(Qt.ItemDataRole.UserRole)
            col_header = item.text()
            
            # Remove from available
            row = self._available_list.row(item)
            self._available_list.takeItem(row)
            
            # Add to displayed
            self._add_to_displayed(col_key, col_header, False)
    
    def _on_remove_clicked(self, item=None):
        """Move selected columns from displayed to available."""
        selected = self._displayed_list.selectedItems()
        if not selected:
            return
        
        for item in selected:
            mandatory = item.data(Qt.ItemDataRole.UserRole + 1)
            if mandatory:
                continue  # Can't remove mandatory columns
            
            col_key = item.data(Qt.ItemDataRole.UserRole)
            col_header = item.text().rstrip(' *')
            
            # Remove from displayed
            row = self._displayed_list.row(item)
            self._displayed_list.takeItem(row)
            
            # Add to available (sorted position)
            self._add_to_available(col_key, col_header)
        
        # Sort available list alphabetically
        self._available_list.sortItems()
    
    def _on_add_all_clicked(self):
        """Move all available columns to displayed."""
        while self._available_list.count() > 0:
            item = self._available_list.takeItem(0)
            col_key = item.data(Qt.ItemDataRole.UserRole)
            col_header = item.text()
            self._add_to_displayed(col_key, col_header, False)
    
    def _on_remove_all_clicked(self):
        """Remove all non-mandatory columns from displayed."""
        items_to_remove = []
        for i in range(self._displayed_list.count()):
            item = self._displayed_list.item(i)
            mandatory = item.data(Qt.ItemDataRole.UserRole + 1)
            if not mandatory:
                items_to_remove.append(item)
        
        for item in items_to_remove:
            col_key = item.data(Qt.ItemDataRole.UserRole)
            col_header = item.text().rstrip(' *')
            
            row = self._displayed_list.row(item)
            self._displayed_list.takeItem(row)
            
            self._add_to_available(col_key, col_header)
        
        self._available_list.sortItems()
    
    def _on_move_up(self):
        """Move selected displayed column up."""
        current_row = self._displayed_list.currentRow()
        if current_row <= 0:
            return
        
        item = self._displayed_list.takeItem(current_row)
        self._displayed_list.insertItem(current_row - 1, item)
        self._displayed_list.setCurrentRow(current_row - 1)
    
    def _on_move_down(self):
        """Move selected displayed column down."""
        current_row = self._displayed_list.currentRow()
        if current_row < 0 or current_row >= self._displayed_list.count() - 1:
            return
        
        item = self._displayed_list.takeItem(current_row)
        self._displayed_list.insertItem(current_row + 1, item)
        self._displayed_list.setCurrentRow(current_row + 1)
    
    def _reset_defaults(self):
        """Reset to default column settings."""
        # Reset model to defaults
        self._table_model._visible_columns = set(self._table_model.DEFAULT_VISIBLE)
        for col in self._table_model.ALL_COLUMNS:
            if len(col) > 3 and col[3]:  # mandatory
                self._table_model._visible_columns.add(col[0])
        
        # Reset order to default
        self._table_model._column_order = [
            c[0] for c in self._table_model.ALL_COLUMNS if c[0] != 'checkbox'
        ]
        
        # Reload dialog
        self._load_columns()
    
    def _apply_changes(self):
        """Apply changes to the table model."""
        new_visible = set()
        new_order = []
        
        # Collect displayed columns
        for i in range(self._displayed_list.count()):
            item = self._displayed_list.item(i)
            col_key = item.data(Qt.ItemDataRole.UserRole)
            new_visible.add(col_key)
            new_order.append(col_key)
        
        # Add non-displayed columns to order (at end, preserving their relative order)
        for i in range(self._available_list.count()):
            item = self._available_list.item(i)
            col_key = item.data(Qt.ItemDataRole.UserRole)
            new_order.append(col_key)
        
        # Update model
        self._table_model._visible_columns = new_visible
        self._table_model._column_order = new_order
        self._table_model.save_column_settings()
        
        self.columns_changed.emit()
        self.accept()
    
    # === Styles ===
    
    def _get_list_style(self) -> str:
        """Style for list widgets."""
        t = theme()
        return f"""
            QListWidget {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
                padding: 4px;
                font-size: {t.font_size('sm')};
            }}
            QListWidget::item {{
                padding: 6px 8px;
                border-radius: 3px;
            }}
            QListWidget::item:selected {{
                background-color: {self._tab_color};
                color: white;
            }}
            QListWidget::item:hover:!selected {{
                background-color: {t.get('hover')};
            }}
        """
    
    def _get_primary_btn_style(self) -> str:
        """Primary button style."""
        t = theme()
        return f"""
            QPushButton {{
                background-color: #4a7c59;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: {t.get('radius_sm')};
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #3d6b4a;
            }}
        """
    
    def _get_secondary_btn_style(self) -> str:
        """Secondary button style."""
        t = theme()
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_primary')};
                border: 1px solid {t.get('border')};
                padding: 8px 16px;
                border-radius: {t.get('radius_sm')};
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
            }}
        """
    
    def _get_action_btn_style(self) -> str:
        """Action button style (Add/Remove)."""
        t = theme()
        return f"""
            QPushButton {{
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
                border: 1px solid {t.get('border')};
                padding: 6px 12px;
                border-radius: {t.get('radius_sm')};
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {self._tab_color};
                color: white;
                border-color: {self._tab_color};
            }}
        """
    
    def _get_arrow_btn_style(self) -> str:
        """Arrow button style."""
        t = theme()
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_secondary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
                color: {self._tab_color};
            }}
        """

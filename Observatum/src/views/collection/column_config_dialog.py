"""
Column Configuration Dialog for Insect Collection.
Allows users to show/hide and reorder columns.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QScrollArea, QWidget, QFrame
)
from PySide6.QtCore import Qt, Signal
from ...themes import theme
from ...core.config import TabColors


class ColumnConfigDialog(QDialog):
    """Dialog for configuring column visibility and order."""
    
    columns_changed = Signal()
    
    def __init__(self, table_model, parent=None):
        super().__init__(parent)
        self._table_model = table_model
        self._column_widgets = []
        self._setup_ui()
        self._load_current_settings()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        t = theme()
        self.setWindowTitle("Configure Columns")
        self.setMinimumWidth(350)
        self.setMinimumHeight(450)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Header
        header = QLabel("Select columns to display and arrange their order:")
        header.setStyleSheet(f"color: {t.get('text_primary')}; font-size: {t.font_size('sm')};")
        header.setWordWrap(True)
        layout.addWidget(header)
        
        # Scroll area for columns
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
                background-color: {t.get('surface')};
            }}
        """)
        
        self._columns_container = QWidget()
        self._columns_layout = QVBoxLayout(self._columns_container)
        self._columns_layout.setSpacing(4)
        self._columns_layout.setContentsMargins(8, 8, 8, 8)
        
        scroll.setWidget(self._columns_container)
        layout.addWidget(scroll, 1)
        
        # Legend
        legend = QLabel("* = Mandatory column (cannot be hidden)")
        legend.setStyleSheet(f"color: {t.get('text_muted')}; font-size: {t.font_size('xs')}; font-style: italic;")
        layout.addWidget(legend)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        reset_btn = QPushButton("Reset Defaults")
        reset_btn.setStyleSheet(self._get_secondary_style())
        reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(reset_btn)
        
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(self._get_secondary_style())
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet(self._get_primary_style())
        apply_btn.clicked.connect(self._apply_changes)
        btn_layout.addWidget(apply_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_current_settings(self):
        """Load current column settings into the dialog."""
        # Clear existing widgets
        for w in self._column_widgets:
            w['container'].deleteLater()
        self._column_widgets.clear()
        
        # Build lookup for column metadata
        col_lookup = {}
        for col_key, col_header, col_width, mandatory in self._table_model.ALL_COLUMNS:
            if col_key != 'checkbox':
                col_lookup[col_key] = (col_header, mandatory)
        
        visible = self._table_model._visible_columns
        
        # Load in CURRENT ORDER from model
        current_order = getattr(self._table_model, '_column_order', None)
        if current_order:
            ordered_keys = [k for k in current_order if k in col_lookup]
        else:
            ordered_keys = list(col_lookup.keys())
        
        # Add any columns not in order (safety fallback)
        for key in col_lookup:
            if key not in ordered_keys:
                ordered_keys.append(key)
        
        # Create rows in current order
        for col_key in ordered_keys:
            col_header, mandatory = col_lookup[col_key]
            is_visible = col_key in visible or mandatory
            self._add_column_row(col_key, col_header, mandatory, is_visible)
        
        self._columns_layout.addStretch()
        self._connect_button_signals()
    
    def _add_column_row(self, col_key: str, col_header: str, mandatory: bool, visible: bool):
        """Add a row for column configuration."""
        t = theme()
        
        container = QFrame()
        container.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_sm')};
                padding: 4px;
            }}
            QFrame:hover {{
                background-color: {t.get('hover')};
            }}
        """)
        
        row = QHBoxLayout(container)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(8)
        
        # Checkbox
        cb = QCheckBox()
        cb.setChecked(visible)
        cb.setStyleSheet(f'''
            QCheckBox {{
                spacing: 5px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {t.get('border')};
                border-radius: 3px;
                background-color: {t.get('surface')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {TabColors.COLLECTION};
                border-color: {TabColors.COLLECTION};
            }}
            QCheckBox::indicator:disabled {{
                background-color: {TabColors.COLLECTION};
                border-color: {TabColors.COLLECTION};
            }}
        ''')
        if mandatory:
            cb.setEnabled(False)
            cb.setToolTip("This column cannot be hidden")
        row.addWidget(cb)
        
        # Label
        label_text = f"{col_header} *" if mandatory else col_header
        label = QLabel(label_text)
        label.setStyleSheet(f"""
            color: {t.get('text_primary') if not mandatory else TabColors.COLLECTION};
            font-size: {t.font_size('sm')};
            background: transparent;
        """)
        row.addWidget(label, 1)
        
        # Up button
        up_btn = QPushButton("Up")
        up_btn.setFixedSize(32, 24)
        up_btn.setStyleSheet(self._get_arrow_style())
        up_btn.setProperty("col_key", col_key)
        row.addWidget(up_btn)
        
        # Down button
        down_btn = QPushButton("Dn")
        down_btn.setFixedSize(32, 24)
        down_btn.setStyleSheet(self._get_arrow_style())
        down_btn.setProperty("col_key", col_key)
        row.addWidget(down_btn)
        
        self._columns_layout.addWidget(container)
        
        self._column_widgets.append({
            'key': col_key,
            'header': col_header,
            'mandatory': mandatory,
            'checkbox': cb,
            'container': container,
            'up_btn': up_btn,
            'down_btn': down_btn
        })
    
    def _connect_button_signals(self):
        """Connect up/down buttons after all widgets are created."""
        for w in self._column_widgets:
            w['up_btn'].clicked.connect(self._on_move_up_clicked)
            w['down_btn'].clicked.connect(self._on_move_down_clicked)

    def _on_move_up_clicked(self):
        """Handle up button click."""
        btn = self.sender()
        col_key = btn.property("col_key")
        if col_key:
            self._move_item(col_key, -1)

    def _on_move_down_clicked(self):
        """Handle down button click."""
        btn = self.sender()
        col_key = btn.property("col_key")
        if col_key:
            self._move_item(col_key, 1)

    def _move_item(self, col_key: str, direction: int):
        """Move a column up (-1) or down (+1) in the order."""
        # Find current index
        idx = -1
        for i, w in enumerate(self._column_widgets):
            if w['key'] == col_key:
                idx = i
                break
        
        if idx < 0:
            return
        
        new_idx = idx + direction
        
        # Check bounds
        if new_idx < 0 or new_idx >= len(self._column_widgets):
            return
        
        # Swap in list
        self._column_widgets[idx], self._column_widgets[new_idx] = \
            self._column_widgets[new_idx], self._column_widgets[idx]
        
        # Rebuild layout order
        self._rebuild_layout()
    
    def _rebuild_layout(self):
        """Rebuild the layout to match widget list order."""
        # Remove all widgets from layout
        for w in self._column_widgets:
            self._columns_layout.removeWidget(w['container'])
        
        # Remove stretch
        while self._columns_layout.count() > 0:
            item = self._columns_layout.takeAt(0)
        
        # Re-add in correct order
        for w in self._column_widgets:
            self._columns_layout.addWidget(w['container'])
        
        # Add stretch at end
        self._columns_layout.addStretch()
    
    def _reset_defaults(self):
        """Reset to default column settings."""
        self._table_model._visible_columns = set(self._table_model.DEFAULT_VISIBLE)
        for col in self._table_model.ALL_COLUMNS:
            if col[3]:  # mandatory
                self._table_model._visible_columns.add(col[0])
        
        # Reset order to default
        self._table_model._column_order = [c[0] for c in self._table_model.ALL_COLUMNS if c[0] != 'checkbox']
        
        self._load_current_settings()
    
    def _apply_changes(self):
        """Apply the column changes."""
        new_visible = set()
        new_order = []
        
        for w in self._column_widgets:
            if w['checkbox'].isChecked() or w['mandatory']:
                new_visible.add(w['key'])
            new_order.append(w['key'])
        
        self._table_model._visible_columns = new_visible
        self._table_model._column_order = new_order
        self._table_model.save_column_settings()
        
        self.columns_changed.emit()
        self.accept()
    
    def _get_primary_style(self) -> str:
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
    
    def _get_secondary_style(self) -> str:
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
    
    def _get_arrow_style(self) -> str:
        """Arrow button style."""
        t = theme()
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_secondary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
                color: {TabColors.COLLECTION};
            }}
        """

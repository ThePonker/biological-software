"""
Collection Toolbar Component.

Toolbar with filter toggle and action buttons for the Insect Collection tab.
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Signal

from ...core.config import TabColors
from ...themes import theme
from ..components.filter_styles import get_clear_button_style


class CollectionToolbar(QFrame):
    """Toolbar with filter toggle and action buttons."""
    
    filters_toggled = Signal(bool)
    clear_filters_requested = Signal()
    export_requested = Signal()
    export_selected_requested = Signal()
    add_specimen_requested = Signal()
    import_requested = Signal()
    columns_requested = Signal()
    wizard_toggled = Signal(bool)  # Placeholder for future
    sidebar_toggled = Signal()
    drawer_assign_requested = Signal()   # "Drawer in hand" (A1, 8 Oct 2026)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filters_visible = False
        self._selected_count = 0
        self._setup_ui()
    
    def _setup_ui(self):
        t = theme()
        
        self.setStyleSheet(f"background-color: {t.get('surface')}; border-bottom: 1px solid {t.get('border')};")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        
        # Filter toggle (Collection Gold when checked - tab theme)
        self.filter_btn = QPushButton("▾ Show Filters")
        self.filter_btn.setStyleSheet(self._get_filter_button_style())
        self.filter_btn.setCheckable(True)
        self.filter_btn.setChecked(False)
        self.filter_btn.clicked.connect(self._on_filter_toggled)
        layout.addWidget(self.filter_btn)

        # Sidebar toggle
        self.sidebar_btn = QPushButton("☰ Systematics")
        self.sidebar_btn.setToolTip("Toggle taxonomic sidebar")
        self.sidebar_btn.setCheckable(True)
        self.sidebar_btn.setStyleSheet(self._get_filter_button_style())
        self.sidebar_btn.clicked.connect(self.sidebar_toggled.emit)
        layout.addWidget(self.sidebar_btn)

        # Filter Wizard toggle
        self.wizard_btn = QPushButton("Filter Wizard")
        self.wizard_btn.setCheckable(True)
        self.wizard_btn.setChecked(False)
        self.wizard_btn.setStyleSheet(self._get_wizard_button_style())
        self.wizard_btn.clicked.connect(self._on_wizard_toggled)
        layout.addWidget(self.wizard_btn)

        
        # Clear Filters button (red hover effect)
        self.clear_filters_btn = QPushButton("Clear Filters")
        self.clear_filters_btn.setStyleSheet(get_clear_button_style())
        self.clear_filters_btn.clicked.connect(self.clear_filters_requested.emit)
        layout.addWidget(self.clear_filters_btn)

        # Add specimen button (Moss Green - primary action, left side)
        self.add_btn = QPushButton("+ Add Specimen")
        self.add_btn.setStyleSheet(self._get_primary_button_style())
        self.add_btn.clicked.connect(self.add_specimen_requested.emit)
        layout.addWidget(self.add_btn)

        # Record which drawer specimens are in -- tick them off a drawer in hand
        self.drawer_btn = QPushButton("Drawer in hand…")
        self.drawer_btn.setToolTip("Take a drawer out, tick each specimen in it, and record the\n"
                                   "storage location and drawer on those specimens.")
        self.drawer_btn.setStyleSheet(self._get_secondary_button_style())
        self.drawer_btn.clicked.connect(self.drawer_assign_requested.emit)
        layout.addWidget(self.drawer_btn)
        
        layout.addStretch()
        
        # Selection info
        self.selection_info = QLabel()
        self.selection_info.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')};")
        self.selection_info.hide()
        layout.addWidget(self.selection_info)
        
        # Export selected button (Warm Gray outlined)
        self.export_selected_btn = QPushButton("Export Selected")
        self.export_selected_btn.setStyleSheet(self._get_secondary_button_style())
        self.export_selected_btn.clicked.connect(self.export_selected_requested.emit)
        self.export_selected_btn.setEnabled(False)
        layout.addWidget(self.export_selected_btn)
        
        # Separator
        self.sep2 = QFrame()
        self.sep2.setFixedWidth(1)
        self.sep2.setStyleSheet(f"background-color: {t.get('separator')};")
        # self.sep2.hide()  # Not needed - button always visible
        layout.addWidget(self.sep2)
        
        # Count label (species • specimens)
        self.count_label = QLabel()
        self.count_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')}; margin-right: 12px;")
        layout.addWidget(self.count_label)
        
        # Columns button (Warm Gray outlined)
        self.columns_btn = QPushButton("Columns")
        self.columns_btn.setStyleSheet(self._get_secondary_button_style())
        self.columns_btn.clicked.connect(self.columns_requested.emit)
        self.columns_btn.setToolTip("Configure visible columns")
        layout.addWidget(self.columns_btn)

        # Export all button (Warm Gray outlined)
        self.export_btn = QPushButton("Export All")
        self.export_btn.setStyleSheet(self._get_secondary_button_style())
        self.export_btn.clicked.connect(self.export_requested.emit)
        layout.addWidget(self.export_btn)
        
        # Import button (Moss Green - primary action)
        self.import_btn = QPushButton("+ Import Data")
        self.import_btn.setStyleSheet(self._get_primary_button_style())
        self.import_btn.clicked.connect(self.import_requested.emit)
        layout.addWidget(self.import_btn)

    
    def _get_wizard_button_style(self) -> str:
        """Get wizard toggle button style with Collection accent."""
        t = theme()
        checked = getattr(self, 'wizard_btn', None) and self.wizard_btn.isChecked()
        color = TabColors.COLLECTION
        if checked:
            return f"""
                QPushButton {{
                    padding: 6px 12px;
                    border: 1px solid {color};
                    border-radius: {t.get('radius_sm')};
                    background: {color};
                    color: white;
                    font-size: {t.font_size('sm')};
                    font-weight: 500;
                }}
                QPushButton:hover {{ background-color: #7a7168; }}
            """
        return f"""
            QPushButton {{
                padding: 6px 12px;
                border: 1px solid {color};
                border-radius: {t.get('radius_sm')};
                background: transparent;
                color: {color};
                font-size: {t.font_size('sm')};
                font-weight: 500;
            }}
            QPushButton:hover {{ background-color: {color}20; }}
        """

    def _on_wizard_toggled(self, checked: bool):
        """Handle wizard toggle."""
        self.wizard_btn.setStyleSheet(self._get_wizard_button_style())
        self.wizard_toggled.emit(checked)

    def set_wizard_visible(self, visible: bool):
        """Set wizard button state without emitting signal."""
        self.wizard_btn.setChecked(visible)
        self.wizard_btn.setStyleSheet(self._get_wizard_button_style())

    def _get_filter_button_style(self) -> str:
        """Get filter toggle button style with Collection Gold when checked (tab theme)."""
        t = theme()
        return f"""
            QPushButton {{
                padding: 6px 12px;
                border: 1px solid {t.get('separator')};
                border-radius: {t.get('radius_sm')};
                background: {t.get('surface')};
                color: {t.get('text_secondary')};
                font-size: {t.font_size('sm')};
            }}
            QPushButton:hover {{ background-color: {t.get('surface_alt')}; }}
            QPushButton:checked {{
                background-color: {TabColors.COLLECTION_LIGHT};
                border-color: {TabColors.COLLECTION};
                color: {TabColors.COLLECTION};
            }}
        """
    
    def _get_secondary_button_style(self) -> str:
        """Get secondary button style (Warm Gray outlined)."""
        t = theme()
        return f"""
            QPushButton {{
                padding: 6px 12px;
                border: 1px solid {t.get('separator')};
                border-radius: {t.get('radius_sm')};
                background: {t.get('surface')};
                color: {t.get('text_secondary')};
                font-size: {t.font_size('sm')};
            }}
            QPushButton:hover {{ 
                background-color: {t.get('surface_alt')}; 
                border-color: {t.get('text_secondary')};
            }}
        """
    
    def _get_primary_button_style(self) -> str:
        """Get primary button style (Moss Green - for Save/Add/Create actions)."""
        t = theme()
        return f"""
            QPushButton {{
                padding: 6px 12px;
                border: none;
                border-radius: {t.get('radius_sm')};
                background-color: {t.get('success')};
                color: white;
                font-size: {t.font_size('sm')};
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {t.get('success_hover')}; }}
        """
    
    def _get_disabled_button_style(self) -> str:
        """Get disabled button style for placeholder buttons."""
        t = theme()
        return f"""
            QPushButton {{
                padding: 6px 12px;
                border: 1px solid {t.get('separator')};
                border-radius: {t.get('radius_sm')};
                background: {t.get('surface')};
                color: {t.get('text_muted')};
                font-size: {t.font_size('sm')};
            }}
            QPushButton:disabled {{
                color: {t.get('text_muted')};
                background: {t.get('surface_alt')};
            }}
        """

    def _on_filter_toggled(self, checked: bool):
        self.filter_btn.setText("▴ Hide Filters" if checked else "▾ Show Filters")
        self._filters_visible = checked
        self.filters_toggled.emit(checked)
    
    def set_filters_visible(self, visible: bool):
        """Set the filter button state without emitting signal.
        
        Used when filter bar is shown programmatically (e.g., cross-tab navigation).
        
        Args:
            visible: Whether filters should be shown
        """
        self._filters_visible = visible
        self.filter_btn.setChecked(visible)
        self.filter_btn.setText("▴ Hide Filters" if visible else "▾ Show Filters")
    
    def set_count(self, count: int, filtered: bool = False):
        """Update the specimen count display - kept for API compatibility."""
        pass
    
    def set_counts(self, species_count: int, specimen_count: int):
        """Set the counts display."""
        self.count_label.setText(f"{species_count} species • {specimen_count} specimens")
    
    def set_selected_count(self, count: int):
        """Update the selection count display."""
        self._selected_count = count
        if count > 0:
            self.selection_info.setText(f"{count} selected")
            self.selection_info.show()
            self.export_selected_btn.setEnabled(True)
            # self.sep2.show()  # Not needed - button always visible
        else:
            self.selection_info.hide()
            self.export_selected_btn.setEnabled(False)
            # self.sep2.hide()  # Not needed - button always visible
    
    def apply_theme(self):
        """Apply the current theme."""
        t = theme()
        self.setStyleSheet(f"background-color: {t.get('surface')}; border-bottom: 1px solid {t.get('border')};")
        self.filter_btn.setStyleSheet(self._get_filter_button_style())
        self.clear_filters_btn.setStyleSheet(get_clear_button_style())
        self.count_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')}; margin-right: 12px;")
        self.selection_info.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')};")
        self.export_selected_btn.setStyleSheet(self._get_secondary_button_style())
        self.export_btn.setStyleSheet(self._get_secondary_button_style())
        self.import_btn.setStyleSheet(self._get_primary_button_style())
        self.add_btn.setStyleSheet(self._get_primary_button_style())
        self.sep2.setStyleSheet(f"background-color: {t.get('separator')};")

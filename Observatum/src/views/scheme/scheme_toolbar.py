"""
Scheme Toolbar Component.

Toolbar for Recording Scheme tab (renamed from ViewSelector) with filter toggle and actions.
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Signal

from ...core.config import TabColors
from ...themes import theme
from ..components.filter_styles import get_clear_button_style


class SchemeToolbar(QFrame):
    """Toolbar with filter toggle and actions for Recording Scheme tab."""
    
    filters_toggled = Signal(bool)
    clear_filters_requested = Signal()
    export_requested = Signal()
    export_selected_requested = Signal()
    import_requested = Signal()
    columns_requested = Signal()
    wizard_toggled = Signal(bool)  # Placeholder for future
    
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
        
        # Filter toggle (Recording Scheme purple when checked - tab theme)
        self.filter_btn = QPushButton("▾ Show Filters")
        self.filter_btn.setStyleSheet(self._get_filter_button_style())
        self.filter_btn.setCheckable(True)
        self.filter_btn.setChecked(False)  # Closed by default
        self.filter_btn.clicked.connect(self._on_filter_toggled)
        layout.addWidget(self.filter_btn)

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

        # Invisible placeholder for alignment with Insect Collection tab
        self.add_placeholder = QPushButton("+ Add Specimen")
        self.add_placeholder.setStyleSheet(self._get_primary_button_style())
        self.add_placeholder.setVisible(False)
        layout.addWidget(self.add_placeholder)
        
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
        
        # Count label (records • species)
        self.count_label = QLabel()
        self.count_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')}; margin-right: 12px;")
        layout.addWidget(self.count_label)
        
        # Columns button (secondary)
        self.columns_btn = QPushButton("Columns")
        self.columns_btn.setStyleSheet(self._get_secondary_button_style())
        self.columns_btn.clicked.connect(self.columns_requested.emit)
        layout.addWidget(self.columns_btn)
        
        # Export all button (Warm Gray outlined)
        self.export_btn = QPushButton("Export All")
        self.export_btn.setStyleSheet(self._get_secondary_button_style())
        self.export_btn.clicked.connect(self.export_requested.emit)
        layout.addWidget(self.export_btn)
        
        # Import button (Moss Green - primary action, matching other tabs)
        self.import_btn = QPushButton("+ Import Data")
        self.columns_btn.setStyleSheet(self._get_secondary_button_style())
        self.import_btn.setStyleSheet(self._get_primary_button_style())
        self.import_btn.clicked.connect(self.import_requested.emit)
        layout.addWidget(self.import_btn)
    
    def _get_wizard_button_style(self) -> str:
        """Get wizard toggle button style with Recording Scheme accent."""
        t = theme()
        checked = getattr(self, 'wizard_btn', None) and self.wizard_btn.isChecked()
        color = TabColors.RECORDING_SCHEME
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
                QPushButton:hover {{ background-color: #5a7888; }}
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
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
                border-color: {TabColors.RECORDING_SCHEME};
                color: {TabColors.RECORDING_SCHEME};
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
        """Get primary button style (Moss Green - for Save/Add/Create/Import actions)."""
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
        """Handle filter toggle."""
        self.filter_btn.setText("▴ Hide Filters" if checked else "▾ Show Filters")
        self._filters_visible = checked
        self.filters_toggled.emit(checked)
    
    def set_filters_visible(self, visible: bool):
        """Set the filter button state without emitting signal.
        
        Used when filter bar is shown programmatically.
        
        Args:
            visible: Whether filters should be shown
        """
        self._filters_visible = visible
        self.filter_btn.setChecked(visible)
        self.filter_btn.setText("▴ Hide Filters" if visible else "▾ Show Filters")
    
    def set_record_count(self, count: int, filtered: bool = False):
        """Set record count display - kept for API compatibility."""
        pass
    
    def set_counts(self, record_count: int, species_count: int):
        """Set the counts display."""
        self.count_label.setText(f"{record_count} records • {species_count} species")
    
    def set_selected_count(self, count: int):
        """Set selected count display."""
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
        """Apply the current theme to all components."""
        t = theme()
        
        self.setStyleSheet(f"background-color: {t.get('surface')}; border-bottom: 1px solid {t.get('border')};")
        
        # Update all styled elements
        self.filter_btn.setStyleSheet(self._get_filter_button_style())
        self.clear_filters_btn.setStyleSheet(get_clear_button_style())
        self.count_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')}; margin-right: 12px;")
        self.selection_info.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')};")
        self.export_selected_btn.setStyleSheet(self._get_secondary_button_style())
        self.export_btn.setStyleSheet(self._get_secondary_button_style())
        self.columns_btn.setStyleSheet(self._get_secondary_button_style())
        self.import_btn.setStyleSheet(self._get_primary_button_style())
        self.sep2.setStyleSheet(f"background-color: {t.get('separator')};")

"""
Observation Toolbar Component.

Toolbar with Show Filters toggle and action buttons.
Uses centralized TabColors from config for consistent theming.
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, Signal

from ...core.config import TabColors
from ...themes import theme
from ..components.filter_styles import get_clear_button_style


class ObservationToolbar(QFrame):
    """Toolbar with filters toggle and actions."""
    
    filters_toggled = Signal(bool)
    wizard_toggled = Signal(bool)
    clear_filters_requested = Signal()
    export_requested = Signal()
    export_selected_requested = Signal()
    delete_selected_requested = Signal()
    import_requested = Signal()
    columns_requested = Signal()
    mark_commercial_requested = Signal()
    select_all_requested = Signal(bool)  # True=select, False=deselect
    
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
        
        # Filter toggle button (Observation sage green when checked - tab theme)
        self.filter_btn = QPushButton("▾ Show Filters")
        self.filter_btn.setStyleSheet(self._get_filter_button_style())
        self.filter_btn.setCheckable(True)
        self.filter_btn.setChecked(False)
        self.filter_btn.clicked.connect(self._on_filter_toggled)
        layout.addWidget(self.filter_btn)

        # Filter Wizard toggle button
        self.wizard_btn = QPushButton("Filter Wizard")
        self.wizard_btn.setStyleSheet(self._get_wizard_button_style())
        self.wizard_btn.setCheckable(True)
        self.wizard_btn.setChecked(False)
        self.wizard_btn.clicked.connect(self._on_wizard_toggled)
        layout.addWidget(self.wizard_btn)

        
        # Clear Filters button (red hover effect)
        self.clear_filters_btn = QPushButton("Clear Filters")
        self.clear_filters_btn.setStyleSheet(get_clear_button_style())
        self.clear_filters_btn.clicked.connect(self.clear_filters_requested.emit)
        # Not shown (Wil, 10 Oct 2026): the filter bar's Clear All, beside Species, does the
        # same (bar + wizard + saved choice, one reload). Kept as an object for the signal.
        self.clear_filters_btn.setVisible(False)

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

        # Delete selected button (red outlined)
        self.delete_selected_btn = QPushButton("Delete Selected")
        self.delete_selected_btn.setStyleSheet(self._get_delete_button_style())
        self.delete_selected_btn.clicked.connect(self.delete_selected_requested.emit)
        self.delete_selected_btn.setEnabled(False)
        layout.addWidget(self.delete_selected_btn)

        # Mark as Commercial button (shown when rows selected)
        self.mark_commercial_btn = QPushButton("Mark as Commercial")
        self.mark_commercial_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mark_commercial_btn.setStyleSheet(self._get_secondary_button_style())
        self.mark_commercial_btn.clicked.connect(self.mark_commercial_requested.emit)
        self.mark_commercial_btn.setEnabled(False)
        layout.addWidget(self.mark_commercial_btn)

        # Select All / Deselect All toggle button
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_all_btn.setStyleSheet(self._get_secondary_button_style())
        self.select_all_btn.clicked.connect(self._toggle_select_all)
        layout.addWidget(self.select_all_btn)
        
        # Separator (hidden by default, shown when export selected is visible)
        self.sep = QFrame()
        self.sep.setFixedWidth(1)
        self.sep.setStyleSheet(f"background-color: {t.get('separator')};")
        # self.sep.hide()  # Not needed - button always visible
        layout.addWidget(self.sep)
        
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

        # Import Data button (Moss Green - primary action)
        self.import_btn = QPushButton("+ Import Data")
        self.import_btn.setStyleSheet(self._get_primary_button_style())
        self.import_btn.clicked.connect(self.import_requested.emit)
        layout.addWidget(self.import_btn)
    
    def _get_filter_button_style(self) -> str:
        """Get filter toggle button style with Observation sage green when checked (tab theme)."""
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
                background-color: {TabColors.OBSERVATION_LIGHT};
                border-color: {TabColors.OBSERVATION};
                color: {TabColors.OBSERVATION};
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
    

    def _get_delete_button_style(self) -> str:
        """Get delete button style (red outlined for destructive action)."""
        t = theme()
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('error')};
                border: 1px solid {t.get('error')};
                border-radius: 4px;
                padding: 6px 12px;
                font-size: {t.font_size('sm')};
            }}
            QPushButton:hover {{
                background-color: {t.get('error')};
                color: white;
            }}
            QPushButton:pressed {{
                background-color: {t.get('error_dark', '#8b2d2d')};
            }}
        """
    def _toggle_select_all(self):
        """Toggle between select all and deselect all."""
        if self.select_all_btn.text() == "Select All":
            self.select_all_btn.setText("Deselect All")
            self.select_all_requested.emit(True)
        else:
            self.select_all_btn.setText("Select All")
            self.select_all_requested.emit(False)

    def _on_filter_toggled(self, checked: bool):
        """Handle filter toggle."""
        self.filter_btn.setText("▴ Hide Filters" if checked else "▾ Show Filters")
        self._filters_visible = checked
        self.filters_toggled.emit(checked)
    
    def _get_wizard_button_style(self) -> str:
        """Get the style for wizard toggle button."""
        t = theme()
        checked = getattr(self, 'wizard_btn', None) and self.wizard_btn.isChecked()
        if checked:
            return f"""
                QPushButton {{
                    padding: 6px 12px;
                    border: 1px solid {TabColors.OBSERVATION};
                    border-radius: {t.get('radius_sm')};
                    background: {TabColors.OBSERVATION};
                    color: white;
                    font-size: {t.font_size('sm')};
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {TabColors.OBSERVATION_DARK};
                }}
            """
        return f"""
            QPushButton {{
                padding: 6px 12px;
                border: 1px solid {TabColors.OBSERVATION};
                border-radius: {t.get('radius_sm')};
                background: transparent;
                color: {TabColors.OBSERVATION};
                font-size: {t.font_size('sm')};
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {TabColors.OBSERVATION}20;
            }}
        """

    def _on_wizard_toggled(self, checked: bool):
        """Handle wizard toggle."""
        self.wizard_btn.setStyleSheet(self._get_wizard_button_style())
        self.wizard_toggled.emit(checked)

    def set_wizard_visible(self, visible: bool):
        """Set wizard button state without emitting signal."""
        self.wizard_btn.setChecked(visible)
        self.wizard_btn.setStyleSheet(self._get_wizard_button_style())

    def set_filters_visible(self, visible: bool):
        """Set filter button state without emitting signal."""
        self._filters_visible = visible
        self.filter_btn.setChecked(visible)
        self.filter_btn.setText("▴ Hide Filters" if visible else "▾ Show Filters")
    
    def set_record_count(self, count: int, filtered: bool = False):
        """Set record count display - kept for API compatibility."""
        pass
    
    def set_counts(self, record_count: int, species_count: int):
        """Set the counts display."""
        from ...utils.text import counted
        self.count_label.setText(f"{counted(record_count, 'record')} • {counted(species_count, 'species', 'species')}")
    
    def set_selected_count(self, count: int):
        """Set selected count display."""
        self._selected_count = count
        if count > 0:
            self.selection_info.setText(f"{count} selected")
            self.selection_info.show()
            # Any tick at all: the button clears them in one click (Wil, 9 Oct) --
            # it used to stay "Select All" after ticking single records, so clearing
            # needed Select All then Deselect All.
            self.select_all_btn.setText("Deselect All")
            self.export_selected_btn.setEnabled(True)
            self.delete_selected_btn.setEnabled(True)
            self.mark_commercial_btn.setEnabled(True)
        else:
            self.selection_info.hide()
            self.export_selected_btn.setEnabled(False)
            self.delete_selected_btn.setEnabled(False)
            self.mark_commercial_btn.setEnabled(False)
            self.select_all_btn.setText("Select All")
    
    def apply_theme(self):
        """Apply the current theme."""
        t = theme()
        self.setStyleSheet(f"background-color: {t.get('surface')}; border-bottom: 1px solid {t.get('border')};")
        self.filter_btn.setStyleSheet(self._get_filter_button_style())
        self.clear_filters_btn.setStyleSheet(get_clear_button_style())
        self.count_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')}; margin-right: 12px;")
        self.selection_info.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')};")
        self.export_selected_btn.setStyleSheet(self._get_secondary_button_style())
        self.columns_btn.setStyleSheet(self._get_secondary_button_style())
        self.import_btn.setStyleSheet(self._get_primary_button_style())
        self.export_btn.setStyleSheet(self._get_secondary_button_style())
        self.sep.setStyleSheet(f"background-color: {t.get('separator')};")

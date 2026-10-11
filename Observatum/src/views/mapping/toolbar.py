"""
Map Toolbar component for Observatum V2.

Provides map view controls including:
- View toggle (National/County)
- Grid size selection
- Filter panel toggle
- Export button, with the extent of the atlas page: Full extent (all GB in National view,
  the whole county in County view; the default) or Current view (L14/L32, 10 Oct 2026)
(Style and Period sit above the map, display_bar.py. The data sources are tick boxes in the
filter panel, source_picker.py -- L8, 10 Oct 2026; they were a drop-down here.)
"""

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QComboBox
)
from PySide6.QtCore import Signal

from ...themes import theme
from ...core.config import TabColors
from shared.maps.grid_squares import GRID_LABELS

EXPORT_EXTENTS = [("full", "Full extent"), ("current", "Current view")]


class MapToolbar(QFrame):
    """Toolbar with map controls."""

    view_changed = Signal(str)         # 'national' or 'county'
    grid_changed = Signal(str)
    filters_toggled = Signal(bool)
    export_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filters_visible = True
        self._accent = TabColors.MAPPING
        self._accent_light = TabColors.MAPPING_LIGHT
        self._accent_dark = TabColors.MAPPING_DARK
        self._setup_ui()

    def _setup_ui(self):
        t = theme()
        self.setStyleSheet(
            f"background-color: {t.get('surface')}; "
            f"border-bottom: 1px solid {t.get('border')};"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(16)

        # View toggle
        view_group = QHBoxLayout()
        view_group.setSpacing(8)

        view_label = QLabel("View:")
        view_label.setStyleSheet(
            f"color: {t.get('text_heading')}; font-size: 12px;"
        )
        view_group.addWidget(view_label)

        self.national_btn = QPushButton("National")
        self.national_btn.setCheckable(True)
        self.national_btn.setChecked(True)
        self.national_btn.clicked.connect(lambda: self._set_view("national"))
        view_group.addWidget(self.national_btn)

        self.county_btn = QPushButton("County")
        self.county_btn.setCheckable(True)
        self.county_btn.clicked.connect(lambda: self._set_view("county"))
        view_group.addWidget(self.county_btn)

        self._update_view_buttons()
        layout.addLayout(view_group)

        # Grid size
        grid_group = QHBoxLayout()
        grid_group.setSpacing(8)

        grid_label = QLabel("Grid:")
        grid_label.setStyleSheet(
            f"color: {t.get('text_heading')}; font-size: 12px;"
        )
        grid_group.addWidget(grid_label)

        self.grid_combo = QComboBox()
        for size, text in GRID_LABELS.items():   # hectad / tetrad / monad (H3)
            self.grid_combo.addItem(text, size)
        self.grid_combo.setCurrentIndex(0)
        self.grid_combo.currentTextChanged.connect(self.grid_changed.emit)
        grid_group.addWidget(self.grid_combo)

        layout.addLayout(grid_group)

        layout.addStretch()

        # Filter toggle
        self.filter_btn = QPushButton("\u25C2 Hide Filters")
        self.filter_btn.setCheckable(True)
        self.filter_btn.setChecked(True)
        self.filter_btn.clicked.connect(self._on_filter_toggled)
        self._style_filter_button()
        layout.addWidget(self.filter_btn)

        # Export: the page's extent, then the button
        self.extent_combo = QComboBox()
        for key, text in EXPORT_EXTENTS:
            self.extent_combo.addItem(text, key)
        self.extent_combo.setToolTip(
            "What the atlas PNG covers. Full extent: all of GB (National view) or the whole "
            "county (County view), whatever the zoom. Current view: what is on screen now.")
        layout.addWidget(self.extent_combo)

        self.export_btn = QPushButton("Export Atlas PNG")
        self.export_btn.setToolTip("Save the map as an A4 page at 300 dpi")
        self.export_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 12px;
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
                font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {t.get('hover')}; }}
        """)
        self.export_btn.clicked.connect(self.export_requested.emit)
        layout.addWidget(self.export_btn)

    def set_view(self, view: str):
        """Switch National / County as the buttons do (view_changed is emitted)."""
        if view != self.get_view():
            self._set_view(view)

    def _set_view(self, view: str):
        """Set the current view mode."""
        self.national_btn.setChecked(view == "national")
        self.county_btn.setChecked(view == "county")
        self._update_view_buttons()
        self.view_changed.emit(view)

    def _update_view_buttons(self):
        """Update view button styles based on state."""
        t = theme()
        for btn, checked in [
            (self.national_btn, self.national_btn.isChecked()),
            (self.county_btn, self.county_btn.isChecked()),
        ]:
            if checked:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {self._accent};
                        color: white;
                        border: none;
                        padding: 6px 12px;
                        font-size: 12px;
                        font-weight: 600;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {t.get('surface')};
                        color: {t.get('text_heading')};
                        border: 1px solid {t.get('border')};
                        padding: 6px 12px;
                        font-size: 12px;
                    }}
                    QPushButton:hover {{
                        background-color: {t.get('hover')};
                    }}
                """)

    def _on_filter_toggled(self, checked: bool):
        """Handle filter panel toggle."""
        self._filters_visible = checked
        self.filter_btn.setText(
            "\u25C2 Hide Filters" if checked else "\u25B8 Show Filters"
        )
        self._style_filter_button()
        self.filters_toggled.emit(checked)

    def _style_filter_button(self):
        """Style the filter toggle button based on state."""
        t = theme()
        if self.filter_btn.isChecked():
            self.filter_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self._accent_light};
                    color: {self._accent_dark};
                    border: 1px solid {self._accent};
                    border-radius: {t.get('radius_sm')};
                    padding: 6px 12px;
                    font-size: 12px;
                }}
            """)
        else:
            self.filter_btn.setStyleSheet(f"""
                QPushButton {{
                    border: 1px solid {t.get('border')};
                    border-radius: {t.get('radius_sm')};
                    padding: 6px 12px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {t.get('hover')};
                }}
            """)

    def export_extent(self) -> str:
        """'full' (the default) or 'current'."""
        return self.extent_combo.currentData() or "full"

    def get_view(self) -> str:
        """Get the current view mode."""
        return "national" if self.national_btn.isChecked() else "county"

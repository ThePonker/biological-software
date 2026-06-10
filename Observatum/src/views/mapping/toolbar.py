"""
Map Toolbar component for Observatum V2.

Provides map view controls including:
- View toggle (National/County)
- Grid size selection
- Data source selection
- Time period preset selection
- Filter panel toggle
- Export button
"""

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QComboBox
)
from PySide6.QtCore import Signal

from ...themes import theme
from ...core.config import TabColors


class MapToolbar(QFrame):
    """Toolbar with map controls."""

    view_changed = Signal(str)         # 'national' or 'county'
    grid_changed = Signal(str)
    data_source_changed = Signal(str)
    time_period_changed = Signal(str)  # 'default', 'brc', 'decade'
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
        self.grid_combo.addItems(["10km", "1km"])
        self.grid_combo.setCurrentText("10km")
        self.grid_combo.currentTextChanged.connect(self.grid_changed.emit)
        grid_group.addWidget(self.grid_combo)

        layout.addLayout(grid_group)

        # Data source
        data_group = QHBoxLayout()
        data_group.setSpacing(8)

        data_label = QLabel("Data:")
        data_label.setStyleSheet(
            f"color: {t.get('text_heading')}; font-size: 12px;"
        )
        data_group.addWidget(data_label)

        self.data_combo = QComboBox()
        self.data_combo.addItem("Personal Records", "personal")
        self.data_combo.addItem("Recording Scheme", "scheme")
        self.data_combo.addItem("All Records", "all")
        self.data_combo.currentIndexChanged.connect(
            lambda: self.data_source_changed.emit(
                self.data_combo.currentData()
            )
        )
        data_group.addWidget(self.data_combo)

        layout.addLayout(data_group)

        # Time period
        time_group = QHBoxLayout()
        time_group.setSpacing(8)

        time_label = QLabel("Period:")
        time_label.setStyleSheet(
            f"color: {t.get('text_heading')}; font-size: 12px;"
        )
        time_group.addWidget(time_label)

        self.time_combo = QComboBox()
        self.time_combo.addItem("Pre-2000 / 2000–19 / 2020+", "default")
        self.time_combo.addItem("Pre-1970 / 1970–99 / 2000+", "brc")
        self.time_combo.setCurrentIndex(0)
        self.time_combo.currentIndexChanged.connect(
            lambda: self.time_period_changed.emit(
                self.time_combo.currentData()
            )
        )
        time_group.addWidget(self.time_combo)

        layout.addLayout(time_group)

        layout.addStretch()

        # Filter toggle
        self.filter_btn = QPushButton("\u25C2 Hide Filters")
        self.filter_btn.setCheckable(True)
        self.filter_btn.setChecked(True)
        self.filter_btn.clicked.connect(self._on_filter_toggled)
        self._style_filter_button()
        layout.addWidget(self.filter_btn)

        # Export button
        self.export_btn = QPushButton("Export Image")
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

    def get_view(self) -> str:
        """Get the current view mode."""
        return "national" if self.national_btn.isChecked() else "county"

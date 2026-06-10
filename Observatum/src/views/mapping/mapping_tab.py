"""
Mapping Tab View for Observatum V2.

Main orchestrator that composes the mapping interface from:
- MapToolbar: View/grid/data source/time period controls
- MapFilterPanel: Species search and filters
- MapWidget: Leaflet map visualization
- MapHeader: Current configuration display
- MapDataService: Data aggregation

Signals flow:
  User selects species → filter_panel.species_selected
  → _on_species_selected → MapDataService.aggregate_species
  → MapWidget.set_species (grid data sent to Leaflet)
"""

from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame

from .toolbar import MapToolbar
from .filter_panel import MapFilterPanel
from .map_widget import MapWidget
from .header import MapHeader

from ...themes import theme
from ...services.map_data_service import MapDataService
import paths


# Path to pre-converted VC boundaries GeoJSON
_VC_GEOJSON = paths.VC_GEOJSON


class MappingTab(QWidget):
    """Mapping tab for distribution visualization."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data_service = MapDataService()
        self._current_species = None
        self._current_grid_data = []
        self._vc_loaded = False
        self._setup_ui()
        self._connect_signals()
        self._initial_update()

    def _setup_ui(self):
        """Set up the UI layout."""
        t = theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        self.toolbar = MapToolbar()
        layout.addWidget(self.toolbar)

        # Main content area
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)

        # Filter panel (left side)
        self.filter_panel = MapFilterPanel()
        content.addWidget(self.filter_panel)

        # Map area (right side)
        map_container = QWidget()
        map_layout = QVBoxLayout(map_container)
        map_layout.setContentsMargins(16, 16, 16, 16)
        map_layout.setSpacing(0)

        # Map card with border
        map_card = QFrame()
        map_card.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)
        card_layout = QVBoxLayout(map_card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # Header showing current config
        self.map_header = MapHeader()
        card_layout.addWidget(self.map_header)

        # Map widget (Leaflet)
        self.map_widget = MapWidget()
        card_layout.addWidget(self.map_widget, 1)

        map_layout.addWidget(map_card, 1)
        content.addWidget(map_container, 1)

        layout.addLayout(content, 1)

    def _connect_signals(self):
        """Connect signals between components."""
        # Toolbar signals
        self.toolbar.view_changed.connect(self._on_view_changed)
        self.toolbar.grid_changed.connect(self._on_grid_changed)
        self.toolbar.data_source_changed.connect(self._on_data_changed)
        self.toolbar.filters_toggled.connect(self._on_filters_toggled)
        self.toolbar.export_requested.connect(self._on_export)

        # Time period signal (if toolbar has been updated with this)
        if hasattr(self.toolbar, "time_period_changed"):
            self.toolbar.time_period_changed.connect(self._on_time_period_changed)

        # Filter panel signals
        self.filter_panel.species_selected.connect(self._on_species_selected)
        self.filter_panel.species_cleared.connect(self._on_species_cleared)
        self.filter_panel.generate_requested.connect(self._generate_map)

        # Map widget signals
        self.map_widget.grid_clicked.connect(self._on_grid_clicked)

    def _initial_update(self):
        """Initial UI update after construction."""
        self._update_header()
        self._load_vc_boundaries()

        # Set initial band config
        colors, labels = self._data_service.get_band_config()
        self.map_widget.set_band_config(colors, labels)

    # -------------------------------------------------------------------------
    # VC boundaries
    # -------------------------------------------------------------------------

    def _load_vc_boundaries(self):
        """Load vice county boundaries if the GeoJSON file exists."""
        if _VC_GEOJSON.exists() and not self._vc_loaded:
            self.map_widget.load_vc_boundaries(str(_VC_GEOJSON))
            self._vc_loaded = True

    # -------------------------------------------------------------------------
    # Species selection and map generation
    # -------------------------------------------------------------------------

    def _on_species_selected(self, species: dict):
        """Handle species selection from the filter panel."""
        self._current_species = species
        self._generate_map()

    def _on_species_cleared(self):
        """Handle species cleared."""
        self._current_species = None
        self._current_grid_data = []
        self.map_widget.clear_species()
        self.map_header.set_species(None)
        self.filter_panel.set_grid_squares([])
        self._update_header()

    def _generate_map(self):
        """Generate/refresh the map with current settings."""
        species_name = None
        if self._current_species:
            species_name = self._current_species.get(
                "scientific_name",
                self._current_species.get("species_name", "")
            )

        grid_size = self.toolbar.grid_combo.currentText().lower().replace(" ", "")
        data_source = self.toolbar.data_combo.currentData() or "personal"

        # Get date range from filter panel
        date_from = self.filter_panel.date_from.text().strip() or None
        date_to = self.filter_panel.date_to.text().strip() or None

        # Aggregate data
        self._current_grid_data = self._data_service.aggregate_species(
            species_name, grid_size, data_source, date_from, date_to
        )

        # Update map
        display_name = species_name or "All records"
        self.map_widget.set_species(display_name, self._current_grid_data)

        # Update header and grid list
        if self._current_species:
            self.map_header.set_species(self._current_species)
        self._update_header()
        self.filter_panel.set_grid_squares(self._current_grid_data)

        # VC gap analysis — highlight VCs with records
        if species_name:
            vc_data = self._data_service.vc_summary(species_name, data_source)
            recorded_vcs = [v["vc_number"] for v in vc_data if v["has_records"]]
            self.map_widget.highlight_vcs(recorded_vcs)
        else:
            self.map_widget.reset_vc_styles()

    # -------------------------------------------------------------------------
    # Toolbar handlers
    # -------------------------------------------------------------------------

    def _on_view_changed(self, view: str):
        """Handle view mode change."""
        self.map_widget.set_view_mode(view)
        if view == "county":
            self._zoom_to_selected_vc()
        self._update_header()

    def _zoom_to_selected_vc(self):
        """Zoom to the VC selected in the filter panel combo."""
        vc_text = self.filter_panel.vc_combo.currentText()
        if not vc_text:
            return
        try:
            vc_part = vc_text.split("-")[0].strip()
            vc_num = int(vc_part.replace("VC", "").strip())
            # Reset to GB first to avoid bad zoom state, then zoom to VC
            self.map_widget.fit_to_gb()
            from PySide6.QtCore import QTimer
            QTimer.singleShot(300, lambda: self.map_widget.zoom_to_vc(vc_num))
        except (ValueError, IndexError):
            pass

    def _on_grid_changed(self, grid: str):
        """Handle grid size change — regenerate with new resolution."""
        if self._current_species:
            self._generate_map()
        self._update_header()

    def _on_data_changed(self, data: str):
        """Handle data source change — regenerate."""
        if self._current_species:
            self._generate_map()
        self._update_header()

    def _on_filters_toggled(self, visible: bool):
        """Handle filter panel toggle."""
        self.filter_panel.setVisible(visible)

    def _on_time_period_changed(self, preset: str):
        """Handle time period preset change."""
        if preset == "brc":
            self._data_service.set_bands([
                {"name": "historical", "label": "Pre-1970", "max_year": 1969},
                {"name": "recent", "label": "1970–1999", "max_year": 1999},
                {"name": "current", "label": "2000+", "max_year": 9999},
            ])
        elif preset == "decade":
            # Could generate decade bands dynamically
            pass
        else:
            # Default
            self._data_service.set_bands([
                {"name": "historical", "label": "Pre-2000", "max_year": 1999},
                {"name": "recent", "label": "2000–2019", "max_year": 2019},
                {"name": "current", "label": "2020+", "max_year": 9999},
            ])

        colors, labels = self._data_service.get_band_config()
        self.map_widget.set_band_config(colors, labels)

        if self._current_species:
            self._generate_map()

    def _on_export(self):
        """Handle export request — future: trigger atlas_renderer."""
        # TODO: Wire to atlas_renderer.py for static BRC-style export
        print("[MappingTab] Export not yet implemented")

    # -------------------------------------------------------------------------
    # Grid click
    # -------------------------------------------------------------------------

    def _on_grid_clicked(self, grid_ref: str):
        """Handle click on a grid square in the map."""
        # Could show a detail popup or navigate to records
        print(f"[MappingTab] Grid clicked: {grid_ref}")

    # -------------------------------------------------------------------------
    # Header
    # -------------------------------------------------------------------------

    def _update_header(self):
        """Update the map header with current config."""
        view = self.toolbar.get_view()
        grid = self.toolbar.grid_combo.currentText()
        data = self.toolbar.data_combo.currentData()
        self.map_header.set_config(view, grid, data)
        self.map_header.set_grid_count(len(self._current_grid_data))

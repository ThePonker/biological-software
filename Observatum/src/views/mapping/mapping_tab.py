"""
Mapping Tab View for Observatum V2.

Main orchestrator that composes the mapping interface from:
- MapToolbar: View/grid/data source/time period controls
- MapFilterPanel: Species search (scientific or common name) and filters
- GridMap: native QPainter map of hectad / tetrad / monad squares (shared/maps)
- MapHeader: Current configuration display
- map_square_service: records -> squares (read-only); MapDataService: bands, VC summary

Backlog H1-H6 (9 Oct 2026): the Leaflet/WebEngine map (map_widget.py) is no longer used
here -- it needed QtWebEngine and an HTML page that is not in the project. The native map
uses the Data Entry map parts, now in shared/maps.

Signals flow:
  User selects species -> filter_panel.species_selected -> _generate_map
  -> map_square_service.fetch_records + squares_for -> GridMap.set_squares
  Click a square (map or list) -> _on_grid_clicked -> SquareRecordsDialog
"""

import os
from datetime import date

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QFileDialog, QMessageBox

from .toolbar import MapToolbar
from .filter_panel import MapFilterPanel
from .header import MapHeader
from .square_records_dialog import SquareRecordsDialog
from .square_style import colour_squares, style_key

from ...themes import theme
from ...core.config import TabColors
from ...services.map_data_service import MapDataService
from ...services import map_square_service as squares_svc
from shared.maps.grid_map import GridMap
from shared.maps.grid_squares import GRID_LABELS, HECTAD
import paths


class MappingTab(QWidget):
    """Mapping tab for distribution visualization."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data_service = MapDataService()
        self._current_species = None
        self._current_grid_data = []
        self._records = []
        self._squares = {}
        self._legend = []
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

        # Native grid-square map
        geojson = str(paths.VC_GEOJSON) if paths.VC_GEOJSON.exists() else None
        self.map_widget = GridMap(geojson_path=geojson, maps_dir=str(paths.MAPS_DIR))
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
        self.toolbar.time_period_changed.connect(self._on_time_period_changed)

        # Filter panel signals
        self.filter_panel.species_selected.connect(self._on_species_selected)
        self.filter_panel.species_cleared.connect(self._on_species_cleared)
        self.filter_panel.generate_requested.connect(self._generate_map)
        self.filter_panel.square_clicked.connect(self._on_grid_clicked)
        self.filter_panel.style_combo.currentIndexChanged.connect(self._restyle)

        # Map signals
        self.map_widget.square_clicked.connect(self._on_grid_clicked)

    def _initial_update(self):
        """Initial UI update after construction."""
        self._update_header()
        self.map_widget.set_message(
            "Choose a species, or press Generate Map to map all your records.")

    # -------------------------------------------------------------------------
    # Species selection and map generation
    # -------------------------------------------------------------------------

    def _grid_size(self) -> int:
        return self.toolbar.grid_combo.currentData() or HECTAD

    def _on_species_selected(self, species: dict):
        """Handle species selection from the filter panel."""
        self._current_species = species
        self._generate_map()

    def _on_species_cleared(self):
        """Handle species cleared."""
        self._current_species = None
        self._current_grid_data = []
        self._records = []
        self._squares = {}
        self.map_widget.clear_squares()
        self.map_widget.highlight_vcs([])
        self.map_widget.set_message("")
        self.map_header.set_species(None)
        self.filter_panel.set_grid_squares([])
        self._update_header()

    def _generate_map(self):
        """Generate/refresh the map with current settings."""
        size = self._grid_size()
        data_source = self.toolbar.data_combo.currentData() or "personal"
        date_from = self.filter_panel.date_from.text().strip() or None
        date_to = self.filter_panel.date_to.text().strip() or None

        self._records = squares_svc.fetch_records(
            self._current_species, data_source, date_from, date_to)
        squares, coarse, unparsed = squares_svc.squares_for(
            self._records, size, self._data_service.year_to_band)
        self._squares = squares
        self._current_grid_data = [{"grid": k, **v} for k, v in squares.items()]
        self._restyle()
        self.map_widget.set_message(self._left_out_text(len(self._records), coarse, unparsed))

        if self._current_species:
            self.map_header.set_species(self._current_species)
        self._update_header()
        self.filter_panel.set_grid_squares(self._current_grid_data)
        if self.toolbar.get_view() == "county":
            self._zoom_to_selected_vc()

        # VC gap analysis -- tint VCs with records (needs the VC boundary file)
        species_name = (self._current_species or {}).get("scientific_name")
        if species_name:
            vc_data = self._data_service.vc_summary(species_name, data_source)
            self.map_widget.highlight_vcs([v["vc_number"] for v in vc_data if v["has_records"]])
        else:
            self.map_widget.highlight_vcs([])

    def _left_out_text(self, total, coarse, unparsed) -> str:
        """Say what the map leaves out, so an empty or thin map explains itself."""
        if not total:
            return "No records with a grid reference match these filters."
        grid = GRID_LABELS[self._grid_size()].split(" (")[0].lower()
        parts = []
        if coarse:
            parts.append(f"{coarse} record{'s' if coarse != 1 else ''} too coarse for a {grid}")
        if unparsed:
            parts.append(f"{unparsed} not on the GB grid (Irish, Channel Islands or lat/long)")
        return ("Not mapped: " + "; ".join(parts) + ".") if parts else ""

    def _restyle(self, *_args):
        """Colour the squares for the chosen display style and refresh the map."""
        squares = self._squares
        colors, labels = self._data_service.get_band_config()
        style = style_key(self.filter_panel.style_combo.currentText())
        self._legend = colour_squares(squares, style, colors, labels,
                                      TabColors.MAPPING_LIGHT, TabColors.MAPPING_DARK)
        self.map_widget.set_squares(squares, self._grid_size())

    # -------------------------------------------------------------------------
    # Toolbar handlers
    # -------------------------------------------------------------------------

    def _on_view_changed(self, view: str):
        """Handle view mode change."""
        if view == "county":
            self._zoom_to_selected_vc()
        else:
            self.map_widget.fit_to_gb()
        self._update_header()

    def _zoom_to_selected_vc(self):
        """Zoom to the VC selected in the filter panel, else to the mapped squares."""
        vc_text = self.filter_panel.vc_combo.currentText()
        try:
            vc_num = int(vc_text.split("-")[0].strip().replace("VC", "").strip())
        except (ValueError, IndexError):
            vc_num = None
        ext = self.map_widget.vc_extent(vc_num) if vc_num else None
        if ext:
            self.map_widget.set_extent(ext)
        else:
            self.map_widget.fit_to_squares()

    def _on_grid_changed(self, grid: str):
        """Handle grid size change -- regenerate with new resolution."""
        if self._current_species or self._records:
            self._generate_map()
        self._update_header()

    def _on_data_changed(self, data: str):
        """Handle data source change -- regenerate."""
        if self._current_species or self._records:
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
        else:
            self._data_service.set_bands([
                {"name": "historical", "label": "Pre-2000", "max_year": 1999},
                {"name": "recent", "label": "2000–2019", "max_year": 2019},
                {"name": "current", "label": "2020+", "max_year": 9999},
            ])
        if self._current_species or self._records:
            self._generate_map()

    # -------------------------------------------------------------------------
    # Atlas export (H5)
    # -------------------------------------------------------------------------

    def _title(self) -> str:
        sp = self._current_species
        if not sp:
            return "All records"
        common = sp.get("common_name") or ""
        return sp.get("scientific_name", "") + (f" ({common})" if common else "")

    def _on_export(self):
        """Save the map as shown as an A4 page at 300 dpi."""
        if not self._squares:
            QMessageBox.information(self, "Export Atlas PNG", "Generate a map first.")
            return
        sp = (self._current_species or {}).get("scientific_name") or "All records"
        grid = GRID_LABELS[self._grid_size()].split(" (")[0]
        default = os.path.join(os.path.expanduser("~"),
                               f"{sp.replace(' ', '_')}_{grid}_{date.today():%Y%m%d}.png")
        path, _f = QFileDialog.getSaveFileName(self, "Export Atlas PNG", default, "PNG image (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        n_sq, n_rec = len(self._squares), sum(s["count"] for s in self._squares.values())
        img = self.map_widget.render_sheet(
            self._title(), subtitle=self.map_header.subtitle.text(), legend=self._legend,
            footer=f"{n_sq} {grid.lower()}s from {n_rec} records.")
        if img.save(path, "PNG"):
            QMessageBox.information(self, "Export Atlas PNG",
                                    f"Saved {img.width()} × {img.height()} px (A4, 300 dpi):\n{path}")
        else:
            QMessageBox.warning(self, "Export Atlas PNG", f"Could not save:\n{path}")

    # -------------------------------------------------------------------------
    # Grid click (H4)
    # -------------------------------------------------------------------------

    def _on_grid_clicked(self, grid_ref: str):
        """Show the records in a clicked square (map or list)."""
        size = self._grid_size()
        recs = squares_svc.records_in_square(self._records, grid_ref, size)
        self.map_widget.set_selected(grid_ref)
        sp = (self._current_species or {}).get("scientific_name", "")
        SquareRecordsDialog(grid_ref, GRID_LABELS[size], recs, sp, self).exec()

    # -------------------------------------------------------------------------
    # Header
    # -------------------------------------------------------------------------

    def _update_header(self):
        """Update the map header with current config."""
        view = self.toolbar.get_view()
        grid = GRID_LABELS[self._grid_size()].split(" (")[1].rstrip(")")
        data = self.toolbar.data_combo.currentData()
        self.map_header.set_config(view, grid, data)
        self.map_header.set_grid_count(len(self._current_grid_data))

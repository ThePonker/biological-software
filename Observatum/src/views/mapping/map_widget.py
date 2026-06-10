"""
Map Widget component for Observatum V2.

QWebEngineView-based map widget displaying species distribution data
via Leaflet.js. Replaces the previous QGraphicsView mockup.

Communicates with the embedded Leaflet map via:
  - Python → JS: page().runJavaScript() for data updates
  - JS → Python: QWebChannel bridge for click events
"""

import json
from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import Qt, QUrl, QObject, Slot, Signal


# Path to the Leaflet HTML template (same directory as this file)
_HTML_PATH = Path(__file__).parent / "map_leaflet.html"


class MapBridge(QObject):
    """
    Bridge object exposed to JavaScript via QWebChannel.
    JS calls methods on this object; they emit Qt signals.
    """

    grid_clicked = Signal(str)  # Emitted when a grid square is clicked

    @Slot(str)
    def gridClicked(self, grid_ref: str):
        """Called from JS when a grid square is clicked."""
        self.grid_clicked.emit(grid_ref)


class MapWidget(QWidget):
    """
    Map widget embedding a Leaflet map via QWebEngineView.

    Public API (called by MappingTab orchestrator):
        set_species(name, grid_data)  — display grid squares for a species
        clear_species()               — clear all grid squares
        load_vc_boundaries(geojson)   — load vice county overlay
        set_vc_visibility(visible)    — toggle VC boundary visibility
        highlight_vcs(vc_numbers)     — highlight specific VCs (gap analysis)
        set_band_config(colors, labels) — set time period colours/labels
        fit_to_gb()                   — reset view to GB extent
        fit_bounds(sw, ne)            — zoom to specific bounds

    Signals:
        grid_clicked(str)             — emitted when user clicks a grid square
    """

    grid_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loaded = False
        self._pending_calls = []  # JS calls queued before page loads

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Web view
        self._web_view = QWebEngineView()
        layout.addWidget(self._web_view)

        # Bridge for JS → Python communication
        self._bridge = MapBridge()
        self._bridge.grid_clicked.connect(self.grid_clicked.emit)

        # Web channel
        self._channel = QWebChannel()
        self._channel.registerObject("bridge", self._bridge)
        self._web_view.page().setWebChannel(self._channel)

        # Allow loading OSM tiles from local file:// context
        settings = self._web_view.page().settings()
        from PySide6.QtWebEngineCore import QWebEngineSettings
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        # Load HTML
        self._web_view.loadFinished.connect(self._on_load_finished)
        if _HTML_PATH.exists():
            self._web_view.setUrl(QUrl.fromLocalFile(str(_HTML_PATH)))
        else:
            print(f"[MapWidget] WARNING: HTML template not found: {_HTML_PATH}")

    # -------------------------------------------------------------------------
    # Private
    # -------------------------------------------------------------------------

    def _on_load_finished(self, ok: bool):
        """Called when the Leaflet HTML page has loaded."""
        if ok:
            self._loaded = True
            # Execute any queued JS calls
            for js_code in self._pending_calls:
                self._web_view.page().runJavaScript(js_code)
            self._pending_calls.clear()
        else:
            print("[MapWidget] WARNING: Failed to load map HTML")

    def _run_js(self, js_code: str):
        """Run JavaScript in the map page. Queues if page not yet loaded."""
        if self._loaded:
            self._web_view.page().runJavaScript(js_code)
        else:
            self._pending_calls.append(js_code)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def set_species(self, species_name: str, grid_data: list):
        """
        Display grid squares for a species.

        Args:
            species_name: Display name for legend
            grid_data: List of dicts with keys:
                grid, sw_lat, sw_lon, ne_lat, ne_lon,
                count, band, years, species_list (optional)
        """
        self._run_js(f"setSpeciesName({json.dumps(species_name)})")
        self._run_js(f"updateGridSquares({json.dumps(grid_data)})")

    def clear_species(self):
        """Clear all grid squares and show the 'select species' overlay."""
        self._run_js("clearGridSquares()")

    def load_vc_boundaries(self, geojson_path: str):
        """
        Load vice county boundaries from a GeoJSON file.

        Args:
            geojson_path: Absolute path to the WGS84 GeoJSON file
        """
        try:
            with open(geojson_path, "r", encoding="utf-8") as f:
                geojson = json.load(f)
            self._run_js(f"loadVCBoundaries({json.dumps(geojson)})")
        except Exception as e:
            print(f"[MapWidget] Error loading VC boundaries: {e}")

    def set_vc_visibility(self, visible: bool):
        """Toggle vice county boundary visibility."""
        self._run_js(f"setVCVisibility({'true' if visible else 'false'})")

    def highlight_vcs(self, vc_numbers: list, color: str = "#c2956e"):
        """
        Highlight specific VCs (e.g., those with records).

        Args:
            vc_numbers: List of VC numbers to highlight
            color: Fill colour for highlighted VCs
        """
        self._run_js(
            f"highlightVCs({json.dumps(vc_numbers)}, {json.dumps(color)})"
        )

    def reset_vc_styles(self):
        """Reset all VC polygons to default styling."""
        self._run_js("resetVCStyles()")

    def set_band_config(self, colors: dict, labels: dict):
        """
        Set time period band colours and labels.

        Args:
            colors: {"historical": "#hex", "recent": "#hex", "current": "#hex"}
            labels: {"historical": "Pre-2000", "recent": "2000-2019", "current": "2020+"}
        """
        self._run_js(f"setBandColors({json.dumps(colors)})")
        self._run_js(f"setBandLabels({json.dumps(labels)})")

    def fit_to_gb(self):
        """Reset map view to show all of GB."""
        self._run_js("fitToGB()")

    def fit_bounds(self, sw_lat: float, sw_lon: float,
                   ne_lat: float, ne_lon: float):
        """Zoom map to specific bounds."""
        self._run_js(
            f"fitBounds({sw_lat}, {sw_lon}, {ne_lat}, {ne_lon})"
        )

    def set_map_view(self, lat: float, lon: float, zoom: int):
        """Set map centre and zoom level."""
        self._run_js(f"setMapView({lat}, {lon}, {zoom})")

    def get_grid_squares(self) -> list:
        """
        Compatibility stub — the old mockup returned hardcoded grids.
        Grid data now lives in map_data_service, not the widget.
        """
        return []


    def zoom_to_vc(self, vc_number: int):
        """Zoom map to a specific vice county and highlight it."""
        self._run_js(f"zoomToVC({vc_number})")

    def zoom_to_national(self):
        """Reset to national view with all VCs styled normally."""
        self._run_js("zoomToNational()")

    def set_view_mode(self, mode: str):
        """
        Handle view mode change (national/county).
        For national: fit to GB and reset VC styles.
        For county: caller should call zoom_to_vc() separately.
        """
        if mode == "national":
            self.zoom_to_national()

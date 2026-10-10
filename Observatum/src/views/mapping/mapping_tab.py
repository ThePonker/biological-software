"""
Mapping Tab View for Observatum V2.

Main orchestrator that composes the mapping interface from:
- MapToolbar: View / grid / data source, filter toggle, atlas export
- MapFilterPanel: what to map (rank picker + several taxa as chips) and the filters
- MapHeader + MapDisplayBar: what is shown; Style, Period and the on-screen legend
- GridMap: native QPainter map of hectad / tetrad / monad squares (shared/maps)
- map_selection.fetch: selection + source + filters -> records, through one query builder
- map_square_service: records -> squares, time-period bands

Backlog H1-H6 (9 Oct 2026): native map. Backlog item 4 (10 Oct 2026, review SRCH18 and
MAP1-9/13/14): several taxa of any rank or taxon groups, species-richness style, the
suite's source split with the embargo rule, real VC / recorder / site filters, legend.

Signals flow:
  chips change / Generate -> _generate_map -> map_selection.fetch -> squares_for
  -> colour_squares -> GridMap.set_squares + legend
  Click a square (map or list) -> _on_grid_clicked -> SquareRecordsDialog
  Chip colour swatch -> colours_changed -> _restyle (no new query)
  Vice County chosen -> County view zoomed to it; "All vice-counties" -> National view

10 Oct 2026 (Wil's testing): each chosen taxon has its own colour (By taxon style, the
default once a second taxon is chosen; a square holding several is split between their
colours); one taxon's Presence map uses its colour.
"""

import os
import re
import time
from datetime import date

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QFileDialog, QMessageBox

from .toolbar import MapToolbar
from .filter_panel import MapFilterPanel
from .header import MapHeader, selection_title
from .display_bar import MapDisplayBar
from .selection_box import MapSelectionBox
from .square_records_dialog import SquareRecordsDialog
from .square_style import band_colours, colour_squares

from ...themes import theme
from ...core.config import TabColors
from ...services import map_selection
from ...services import map_square_service as squares_svc
from shared.maps.grid_map import GridMap
from shared.maps.grid_squares import GRID_LABELS, HECTAD
import paths


def safe_filename(text: str) -> str:
    """A file name from a map title: no / \\ : * ? " < > | (MAP14), spaces as underscores."""
    name = re.sub(r'[\\/:*?"<>|]+', "-", text or "map")
    name = re.sub(r"\s+", "_", name.strip()).strip("._-")
    return name[:120] or "map"


class MappingTab(QWidget):
    """Mapping tab for distribution visualization."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bands = squares_svc.BAND_PRESETS["default"]
        self._records = []
        self._squares = {}
        self._legend = []
        self._result = None
        self._mapped_selection = []
        self.last_timing = None            # (fetch s, squares s) of the last map, for checks
        self._setup_ui()
        self._connect_signals()
        self._initial_update()

    def _setup_ui(self):
        """Set up the UI layout."""
        t = theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toolbar = MapToolbar()
        layout.addWidget(self.toolbar)

        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)

        self.filter_panel = MapFilterPanel()
        content.addWidget(self.filter_panel)

        map_container = QWidget()
        map_layout = QVBoxLayout(map_container)
        map_layout.setContentsMargins(16, 16, 16, 16)
        map_layout.setSpacing(0)

        map_card = QFrame()
        map_card.setObjectName("mapCard")         # its border only, not every label's
        map_card.setStyleSheet(f"""
            QFrame#mapCard {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)
        card_layout = QVBoxLayout(map_card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.map_header = MapHeader()
        card_layout.addWidget(self.map_header)
        self.display_bar = MapDisplayBar()
        card_layout.addWidget(self.display_bar)

        geojson = str(paths.VC_GEOJSON) if paths.VC_GEOJSON.exists() else None
        self.map_widget = GridMap(geojson_path=geojson, maps_dir=str(paths.MAPS_DIR))
        card_layout.addWidget(self.map_widget, 1)

        map_layout.addWidget(map_card, 1)
        content.addWidget(map_container, 1)
        layout.addLayout(content, 1)

    def _connect_signals(self):
        """Connect signals between components."""
        self.toolbar.view_changed.connect(self._on_view_changed)
        self.toolbar.grid_changed.connect(self._on_grid_changed)
        self.toolbar.data_source_changed.connect(self._on_data_changed)
        self.toolbar.filters_toggled.connect(self._on_filters_toggled)
        self.toolbar.export_requested.connect(self._on_export)

        self.filter_panel.selection_changed.connect(self._on_selection_changed)
        self.filter_panel.generate_requested.connect(self._generate_map)
        self.filter_panel.square_clicked.connect(self._on_grid_clicked)
        self.filter_panel.selection_box.colours_changed.connect(self._restyle)
        self.filter_panel.vc_combo.currentIndexChanged.connect(self._on_vc_changed)

        self.display_bar.style_changed.connect(self._restyle)
        self.display_bar.period_changed.connect(self._on_period_changed)

        self.map_widget.square_clicked.connect(self._on_grid_clicked)

    def _initial_update(self):
        self._update_header()
        self.map_widget.set_message(
            "Choose species, genera, families, orders or groups, or press Generate Map to "
            "map every record of the chosen data.")

    # -------------------------------------------------------------------------
    # Selection and map generation
    # -------------------------------------------------------------------------

    def _grid_size(self) -> int:
        return self.toolbar.grid_combo.currentData() or HECTAD

    def _source(self) -> str:
        return self.toolbar.data_combo.currentData() or "personal"

    def _year_to_band(self, year):
        return squares_svc.year_to_band(year, self._bands)

    def _on_selection_changed(self, chips: list):
        # By taxon once there are two taxa to tell apart; back to Presence below two (with
        # one taxon, Presence is drawn in its colour). Another style chosen is left alone.
        style = self.display_bar.style()
        if len(chips) > 1 and style == "presence":
            self.display_bar.set_style("taxon", emit=False)
        elif len(chips) < 2 and style == "taxon":
            self.display_bar.set_style("presence", emit=False)
        if chips:
            self._generate_map()
        else:
            self._clear_map()

    def _clear_map(self):
        self._records, self._squares, self._result = [], {}, None
        self._mapped_selection = []
        self.map_widget.clear_squares()
        self.map_widget.highlight_vcs([])
        self.map_widget.set_message("")
        self.map_header.set_selection([])
        self.filter_panel.set_grid_squares([])
        self.display_bar.set_legend([])
        self._legend = []
        self._update_header()

    def _generate_map(self):
        """Generate/refresh the map with current settings."""
        filters, error = self.filter_panel.filters()
        if filters is None:                         # MAP3: say so rather than ignore it
            self.map_widget.set_message(error)
            return
        selection = self.filter_panel.selection()
        size = self._grid_size()
        t0 = time.perf_counter()
        self._result = map_selection.fetch(selection, self._source(), filters)
        t1 = time.perf_counter()
        self._records = self._result.records
        squares, coarse, unparsed = squares_svc.squares_for(self._records, size, self._year_to_band)
        self.last_timing = (t1 - t0, time.perf_counter() - t1)
        self._squares = squares
        self._mapped_selection = selection
        self._name_taxa(squares, selection)
        self._restyle()
        self.map_widget.set_message(self._left_out_text(len(self._records), coarse, unparsed))
        self.map_header.set_selection(selection)
        self.filter_panel.set_chip_counts(self._result.chip_counts if selection else None)
        self._update_header()
        self.filter_panel.set_grid_squares([{"grid": k, **v} for k, v in squares.items()])
        if self.toolbar.get_view() == "county":
            self._zoom_to_selected_vc()
        # MAP4: tint the VCs of the records on the map (same filters, by VC number)
        self.map_widget.highlight_vcs(sorted({r["vc"] for r in self._records if r.get("vc")}))

    def _left_out_text(self, total, coarse, unparsed) -> str:
        """Say what the map leaves out, so an empty or thin map explains itself."""
        if not total:
            return "No records with a grid reference match these filters."
        grid = GRID_LABELS[self._grid_size()].split(" (")[0].lower()
        parts = []
        if coarse:
            parts.append(f"{coarse:,} record{'s' if coarse != 1 else ''} too coarse for a {grid}")
        if unparsed:
            parts.append(f"{unparsed:,} not on the GB grid (Irish, Channel Islands or lat/long)")
        return ("Not mapped: " + "; ".join(parts) + ".") if parts else ""

    @staticmethod
    def _chip_name(chip: dict) -> str:
        return chip.get("scientific_name") or chip.get("label") or "?"

    def _name_taxa(self, squares, selection):
        """With several taxa chosen, each square says which of them it holds (tooltip,
        square list, records dialog)."""
        if len(selection) < 2:
            return
        for sq in squares.values():
            names = [self._chip_name(selection[i]) for i in sq.get("chips") or ()
                     if 0 <= i < len(selection)]
            sq["taxa"] = ", ".join(names)
            if names:
                sq["tip"] = f"{sq.get('tip', '')}\nTaxa: {sq['taxa']}"

    def _taxa_colours(self):
        """[(name, colour)] for the mapped chips, with their colours as they are now."""
        live = {MapSelectionBox._key(c): c.get("colour") for c in self.filter_panel.selection()}
        return [(self._chip_name(c), live.get(MapSelectionBox._key(c)) or c.get("colour")
                 or TabColors.MAPPING_DARK) for c in self._mapped_selection]

    def _restyle(self, *_args):
        """Colour the squares for the chosen display style and refresh map and legend."""
        squares = self._squares
        labels = squares_svc.band_labels(self._bands)
        colours = band_colours(list(labels), theme().get('text_muted'))
        self._legend = colour_squares(squares, self.display_bar.style(), colours, labels,
                                      TabColors.MAPPING_LIGHT, TabColors.MAPPING_DARK,
                                      taxa=self._taxa_colours())
        self.display_bar.set_legend(self._legend)
        self.map_widget.set_squares(squares, self._grid_size())

    # -------------------------------------------------------------------------
    # Toolbar and display handlers
    # -------------------------------------------------------------------------

    def _on_view_changed(self, view: str):
        if view == "county":
            self._zoom_to_selected_vc()
        else:
            self.map_widget.fit_to_gb()
        self._update_header()

    def _on_vc_changed(self, *_a):
        """A vice-county chosen in the filters: show it (County view, zoomed to it) and map
        its records; "All vice-counties" goes back to National view. The VC stays a filter."""
        vc = self.filter_panel.vc_combo.currentData()
        view = "county" if vc else "national"
        if self.toolbar.get_view() != view:
            self.toolbar.set_view(view)          # -> _on_view_changed zooms
        elif vc:
            self._zoom_to_selected_vc()
        if self._has_map():
            self._generate_map()

    def _zoom_to_selected_vc(self):
        """Zoom to the VC chosen in the filter panel, else to the mapped squares."""
        vc_num = self.filter_panel.vc_combo.currentData()
        ext = self.map_widget.vc_extent(vc_num) if vc_num else None
        if ext:
            self.map_widget.set_extent(ext)
        else:
            self.map_widget.fit_to_squares()

    def _has_map(self) -> bool:
        return self._result is not None

    def _on_grid_changed(self, _grid: str):
        if self._has_map():
            self._generate_map()
        self._update_header()

    def _on_data_changed(self, data: str):
        self.filter_panel.set_source(data)
        if self._has_map():
            self._generate_map()
        self._update_header()

    def _on_filters_toggled(self, visible: bool):
        self.filter_panel.setVisible(visible)

    def _on_period_changed(self, preset: str):
        """Period only recolours: re-band the squares, no new query."""
        self._bands = squares_svc.BAND_PRESETS.get(preset, squares_svc.BAND_PRESETS["default"])
        for sq in self._squares.values():
            sq["band"] = self._year_to_band(sq.get("last_year"))
        self._restyle()

    # -------------------------------------------------------------------------
    # Atlas export (H5)
    # -------------------------------------------------------------------------

    def _title(self) -> str:
        return selection_title(self._mapped_selection) if self._mapped_selection else "All records"

    def _on_export(self):
        """Save the map as shown as an A4 page at 300 dpi."""
        if not self._squares:
            QMessageBox.information(self, "Export Atlas PNG", "Generate a map first.")
            return
        grid = GRID_LABELS[self._grid_size()].split(" (")[0]
        default = os.path.join(os.path.expanduser("~"),
                               f"{safe_filename(self._title())}_{grid}_{date.today():%Y%m%d}.png")
        path, _f = QFileDialog.getSaveFileName(self, "Export Atlas PNG", default, "PNG image (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        img = self.render_atlas()
        if img.save(path, "PNG"):
            QMessageBox.information(self, "Export Atlas PNG",
                                    f"Saved {img.width()} × {img.height()} px (A4, 300 dpi):\n{path}")
        else:
            QMessageBox.warning(self, "Export Atlas PNG", f"Could not save:\n{path}")

    def render_atlas(self):
        """The atlas page for the map as shown (QImage)."""
        grid = GRID_LABELS[self._grid_size()].split(" (")[0]
        n_sq = len(self._squares)
        n_rec = sum(s["count"] for s in self._squares.values())
        n_sp = len({r["species"] for r in self._records if r.get("species") and r.get("square")})
        return self.map_widget.render_sheet(
            self._title(), subtitle=self.map_header.subtitle.text(), legend=self._legend,
            footer=f"{n_sq:,} {grid.lower()}s, {n_rec:,} records, {n_sp:,} species.")

    # -------------------------------------------------------------------------
    # Grid click (H4)
    # -------------------------------------------------------------------------

    def _on_grid_clicked(self, grid_ref: str):
        """Show the records in a clicked square (map or list)."""
        size = self._grid_size()
        recs = squares_svc.records_in_square(self._records, grid_ref, size)
        self.map_widget.set_selected(grid_ref)
        title = selection_title(self._mapped_selection) if self._mapped_selection else ""
        title = (self._squares.get(grid_ref) or {}).get("taxa") or title
        SquareRecordsDialog(grid_ref, GRID_LABELS[size], recs, title, self).exec()

    # -------------------------------------------------------------------------
    # Header
    # -------------------------------------------------------------------------

    def _note(self) -> str:
        """What the map holds back or folds together, in words (the subtitle and the PNG)."""
        r = self._result
        if r is None:
            return ""
        parts = []
        filters, _e = self.filter_panel.filters()
        if r.embargoed:
            if filters and filters.include_embargoed:
                parts.append(f"includes {r.embargoed:,} embargoed")
            else:
                parts.append(f"{r.embargoed:,} embargoed not shown")
        if r.merged:
            parts.append(f"{r.merged:,} duplicate records shown once")
        return ", ".join(parts)

    def _update_header(self):
        view = self.toolbar.get_view()
        grid = GRID_LABELS[self._grid_size()].split(" (")[1].rstrip(")")
        self.map_header.set_config(view, grid, self._source(), self._note())
        self.map_header.set_grid_count(len(self._squares),
                                       len(self._records) if self._result is not None else None)

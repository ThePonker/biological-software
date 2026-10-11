"""The Mapping tab's atlas export (H5): an A4 page at 300 dpi, saved as PNG.

Round 2 (10 Oct 2026): the page covers the full extent (all GB in National view, the whole
county in County view; the default) or the current view, chosen beside the button (L14/L32);
the clicked square's outline is never printed (L13/L31, shared/maps/grid_map.render_sheet);
with no taxon chosen the title is "All records (no taxon chosen)" (L33). Split out of
mapping_tab.py to keep it under 400 lines.
"""
import os
import re
from datetime import date

from PySide6.QtWidgets import QFileDialog, QMessageBox

from shared.maps.grid_squares import GRID_LABELS
from .header import selection_title


def safe_filename(text: str) -> str:
    """A file name from a map title: no / \\ : * ? " < > | (MAP14), spaces as underscores."""
    name = re.sub(r'[\\/:*?"<>|]+', "-", text or "map")
    name = re.sub(r"\s+", "_", name.strip()).strip("._-")
    return name[:120] or "map"


class AtlasExportMixin:
    """For MappingTab: needs _squares, _records, _mapped_selection, _grid_size(), _legend,
    map_header, map_widget and toolbar.export_extent()."""

    # -------------------------------------------------------------------------
    # Atlas export (H5)
    # -------------------------------------------------------------------------

    def _title(self) -> str:
        return selection_title(self._mapped_selection)

    def _on_export(self):
        """Save the map as an A4 page at 300 dpi: the full extent or the current view."""
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
        img = self.render_atlas(self.toolbar.export_extent())
        if img.save(path, "PNG"):
            QMessageBox.information(self, "Export Atlas PNG",
                                    f"Saved {img.width()} × {img.height()} px (A4, 300 dpi):\n{path}")
        else:
            QMessageBox.warning(self, "Export Atlas PNG", f"Could not save:\n{path}")

    def render_atlas(self, extent: str = "full"):
        """The atlas page (QImage). extent: 'full' (all GB in National view, the whole county
        in County view) or 'current' (what is on screen). The clicked square's outline is
        never printed (L13/L31)."""
        grid = GRID_LABELS[self._grid_size()].split(" (")[0]
        n_sq = len(self._squares)
        n_rec = sum(s["count"] for s in self._squares.values())
        n_sp = len({r["species"] for r in self._records if r.get("species") and r.get("square")})
        return self.map_widget.render_sheet(
            self._title(), subtitle=self.map_header.subtitle.text(), legend=self._legend,
            footer=f"{n_sq:,} {grid.lower()}s, {n_rec:,} records, {n_sp:,} species.",
            extent=extent)

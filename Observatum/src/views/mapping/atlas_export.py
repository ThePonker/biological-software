"""The Mapping tab's atlas export (H5): an A4 page at 300 dpi, saved as PNG.

Round 2 (10 Oct 2026): the page covers the full extent (all GB in National view, the whole
county in County view; the default) or the current view, chosen beside the button (L14/L32);
the clicked square's outline is never printed (L13/L31, shared/maps/grid_map.render_sheet);
with no taxon chosen the title is "All records (no taxon chosen)" (L33). Split out of
mapping_tab.py to keep it under 400 lines.

R9-6 (11 Oct 2026): a "Current view" page zoomed in counts only what it shows: the squares
drawn on the page (wholly or in part) and the records and species in them, "(in view)". A
full-extent page keeps the whole map's figures and wording.
"""
import os
import re
from datetime import date

from PySide6.QtWidgets import QFileDialog, QMessageBox

from shared.maps import map_stats
from shared.maps.extras_panel import Extras
from shared.maps.grid_squares import GRID_LABELS
from .header import selection_title


EXPORT_OPTIONS = (("counts", "Counts (records, species, squares, vice counties, recorders)"),
                  ("first_last", "First and last record"),
                  ("phenology", "Phenology chart (records by month)"),
                  ("decades", "Records by decade"),
                  ("layer_legend", "Layer legend"))
EXPORT_DEFAULTS = {"counts": False, "first_last": False, "phenology": False, "decades": False,
                   "layer_legend": True}
EXTRAS_OPTIONS = tuple(k for k, _t in EXPORT_OPTIONS if k != "layer_legend")   # the extras panel's ticks
EXPORT_DPI = 300


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
        """Open the map export preview (what goes on the page, a live preview); its Export PNG
        button saves the page through _export_png."""
        if not self._squares:
            QMessageBox.information(self, "Export Atlas PNG", "Generate a map first.")
            return
        from .export_preview import ExportPreviewDialog
        ExportPreviewDialog(self, self).exec()

    def _export_png(self, extent: str, options: dict, parent=None) -> bool:
        """Ask for a file name and save the A4 page at 300 dpi; True if saved."""
        parent = parent or self
        grid = GRID_LABELS[self._grid_size()].split(" (")[0]
        default = os.path.join(os.path.expanduser("~"),
                               f"{safe_filename(self._title())}_{grid}_{date.today():%Y%m%d}.png")
        path, _f = QFileDialog.getSaveFileName(parent, "Export Atlas PNG", default, "PNG image (*.png)")
        if not path:
            return False
        if not path.lower().endswith(".png"):
            path += ".png"
        img = self.render_atlas(extent, options)
        if img.save(path, "PNG"):
            QMessageBox.information(parent, "Export Atlas PNG",
                                    f"Saved {img.width()} × {img.height()} px (A4, 300 dpi):\n{path}")
            return True
        QMessageBox.warning(parent, "Export Atlas PNG", f"Could not save:\n{path}")
        return False

    def render_atlas(self, extent: str = "full", options: dict = None, dpi: int = 300):
        """The atlas page (QImage). extent: 'full' (all GB in National view, the whole county
        in County view) or 'current' (what is on screen). The clicked square's outline is
        never printed (L13/L31). options: which extras go on the page (EXPORT_OPTIONS keys);
        none ticked leaves the page as it always was."""
        footer, extras, groups = "", None, ()
        # The figures come from the 300 dpi page's box whatever `dpi` is drawn at, so a preview
        # and the export say the same (text wraps a little differently at other resolutions).
        for _pass in range(3):      # footer and extras count what the box shows; the box depends on them
            _ext, shown = self.map_widget.sheet_view(extent, dpi=EXPORT_DPI, legend=self._legend,
                                                     footer=footer, extras=extras,
                                                     layer_groups=groups)
            footer, new = self.atlas_footer(extent, shown), self.export_extras(options, extent, shown)
            new_groups = (self.map_widget.layer_legend_groups(shown)
                          if (options or {}).get("layer_legend") else ())
            if new == extras and new_groups == groups and _pass:
                break
            extras, groups = new, new_groups
        return self.map_widget.render_sheet(
            self._title(), subtitle=self.map_header.subtitle.text(), legend=self._legend,
            footer=footer, extent=extent, dpi=dpi, extras=extras, layer_groups=groups)

    def _page_squares(self, extent: str, shown):
        """(the squares the page counts, whether it is a zoomed 'current' page): all the map's
        squares, or on a zoomed Current view page only those in view (R9-6)."""
        in_view = (extent == "current" and shown is not None
                   and self.map_widget.resolve_extent("current") != self.map_widget.full_extent())
        return (set(self.map_widget.squares_in(shown)) if in_view else set(self._squares)), in_view

    def export_stats(self, extent: str = "full", shown=None):
        """map_stats figures for the page: the records the map is drawn from, in its squares."""
        squares, _v = self._page_squares(extent, shown)
        return map_stats.compute(self._records, squares)

    def export_extras(self, options: dict, extent: str = "full", shown=None):
        """The page's extras panel for the ticked options, or None when nothing is ticked."""
        opts = options or {}
        if not any(opts.get(k) for k in EXTRAS_OPTIONS):
            return None
        squares, in_view = self._page_squares(extent, shown)
        st = map_stats.compute(self._records, squares)
        grid = GRID_LABELS[self._grid_size()].split("(")[1].rstrip(")")
        lines = []
        if opts.get("counts"):
            lines.append(map_stats.counts_line(st, grid, in_view))
        if opts.get("first_last"):
            lines.append(map_stats.first_last_line(st, in_view))
        if opts.get("decades"):
            lines.append(map_stats.decades_line(st, in_view))
        if (opts.get("first_last") or opts.get("decades")) and st.ranged:
            lines.append(map_stats.range_note(st))
        ex = Extras(lines=lines)
        if opts.get("phenology"):
            ex.months = tuple(st.months)
            ex.chart_title = "Records by month" + (" (in view)" if in_view else "")
            ex.chart_note = map_stats.month_note(st)
        return ex

    def atlas_footer(self, extent: str = "full", shown=None) -> str:
        """"n hectads, n records, n species." for the whole map; on a zoomed "current" page
        (shown: the OSGB box the page's map shows) only the squares on the page, their
        records and species, "(in view)" (R9-6)."""
        grid = GRID_LABELS[self._grid_size()].split(" (")[0].lower()
        squares, in_view = self._page_squares(extent, shown)
        n_rec = sum(self._squares[s]["count"] for s in squares)
        n_sp = len({r["species"] for r in self._records
                    if r.get("species") and r.get("square") in squares})
        tail = " (in view)" if in_view else ""
        return f"{len(squares):,} {grid}s, {n_rec:,} records, {n_sp:,} species{tail}."

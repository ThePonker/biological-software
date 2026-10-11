"""Batch maps -- the pages (R9-7, 11 Oct 2026). Draws services/batch_maps.TaxonMap results with
the Mapping tab's own parts: GridMap.render_sheet (the atlas page: title, map, legend, footer),
square_style.colour_squares (the Style list), map_notes.map_note (the subtitle's note) and the
footer wording of atlas_export.render_atlas. Plus the spread-over-time pages
(services/batch_spread.py): a date-class map and cumulative frames, with an optional GIF.

Needs a QApplication (offscreen is fine: ensure_app()). Writes PNG / GIF files only.
"""
from __future__ import annotations

import os
from datetime import date
from typing import List, Optional, Sequence

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter

import paths
from shared.maps.grid_map import GridMap
from shared.maps.grid_squares import GB_LAND, GRID_LABELS

from ...core.config import TabColors
from ...services import batch_spread as spread
from ...services import map_square_service as squares_svc
from ...services.batch_maps import BatchSettings, TaxonMap, area_label, file_name
from ...themes import theme
from .header import selection_title
from .map_notes import map_note
from .source_picker import sources_label
from .square_style import band_colours, colour_squares


def ensure_app():
    """The running QApplication, or a new one (offscreen when there is no display)."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        if not os.environ.get("DISPLAY") and os.name != "nt":
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication([])
    return app


class BatchRenderer:
    """One GridMap (never shown), reused for every page of a batch."""

    def __init__(self, settings: BatchSettings):
        ensure_app()
        self.settings = settings
        geojson = str(paths.VC_GEOJSON) if paths.VC_GEOJSON.exists() else None
        self.map = GridMap(geojson_path=geojson, maps_dir=str(paths.MAPS_DIR))
        self.map.resize(900, 1100)

    # ---------------------------------------------------------------- words
    def extent(self, vcs: Sequence[int]):
        """All GB, or the VC (the tab's County view), or the box round several VCs."""
        boxes = [b for b in (self.map.vc_extent(v) for v in vcs) if b]
        if not boxes:
            return GB_LAND
        return (min(b[0] for b in boxes), min(b[1] for b in boxes),
                max(b[2] for b in boxes), max(b[3] for b in boxes))

    def subtitle(self, tm: TaxonMap, extra: str = "") -> str:
        """header.set_config's line (view, grid, sources, note), then the batch's own filters."""
        s = self.settings
        view = "County distribution" if tm.vcs else "National distribution"
        grid = GRID_LABELS[tm.size].split(" (")[1].rstrip(")")
        text = f"{view} • {grid} grid • {sources_label(list(s.source_keys()))}"
        note = map_note(tm.result, s.filters(tm.vcs))
        bits = [note] if note else []
        if tm.vcs:
            bits.append(area_label(tm.vcs))
        if s.date_from or s.date_to:
            bits.append(f"{s.date_from or '…'} to {s.date_to or '…'}")
        if extra:
            bits.append(extra)
        return text + "".join(f" • {b}" for b in bits)

    @staticmethod
    def footer(tm: TaxonMap, squares=None) -> str:
        """atlas_export.render_atlas's footer: squares, records, species."""
        squares = tm.squares if squares is None else squares
        grid = GRID_LABELS[tm.size].split(" (")[0]
        n_rec = sum(s["count"] for s in squares.values())
        keys = set(squares)
        n_sp = len({r["species"] for r in tm.result.records
                    if r.get("species") and r.get("square") in keys})
        return f"{len(squares):,} {grid.lower()}s, {n_rec:,} records, {n_sp:,} species."

    # ---------------------------------------------------------------- pages
    def page(self, tm: TaxonMap, squares, legend, title_extra: str = "",
             stamp: str = "", footer_extra: str = "") -> QImage:
        """One atlas page. title_extra follows the taxon in the title ('first record by
        date'); the subtitle stays the tab's line, which is long already."""
        m = self.map
        m.set_squares(squares, tm.size)
        m.set_selected(None)
        m.highlight_vcs(sorted({r["vc"] for r in tm.result.records if r.get("vc")}))  # MAP4
        m.set_extent(self.extent(tm.vcs))
        title = selection_title([tm.chip]) + (f" — {title_extra}" if title_extra else "")
        img = m.render_sheet(title, subtitle=self.subtitle(tm),
                             legend=legend,
                             footer=self.footer(tm, squares) + (f" {footer_extra}" if footer_extra else ""),
                             dpi=self.settings.dpi, extent="full")
        if stamp:
            _stamp(img, stamp, self.settings.dpi)
        return img

    def styled(self, tm: TaxonMap):
        """(squares, legend) in the batch's Style, as the tab's _restyle colours them."""
        s = self.settings
        bands = squares_svc.BAND_PRESETS.get(s.period, squares_svc.BAND_PRESETS["default"])
        labels = squares_svc.band_labels(bands)
        colours = band_colours(list(labels), theme().get('text_muted'))
        name = tm.chip.get("scientific_name") or tm.chip.get("label") or "?"
        legend = colour_squares(tm.squares, s.style, colours, labels, TabColors.MAPPING_LIGHT,
                                TabColors.MAPPING_DARK, taxa=[(name, s.colour)])
        return tm.squares, legend

    def save_map(self, tm: TaxonMap, out_dir: str) -> str:
        """The taxon's map page; sets tm.file."""
        squares, legend = self.styled(tm)
        path = os.path.join(out_dir, file_name(tm.chip, self.settings, tm.vcs))
        _save(self.page(tm, squares, legend), path)
        tm.file = path
        return path

    def save_date_classes(self, tm: TaxonMap, out_dir: str,
                          breaks: Sequence[int] = spread.DEFAULT_BREAKS, by: str = "first") -> str:
        squares = {k: dict(v) for k, v in tm.squares.items()}
        legend = spread.colour_by_date_class(squares, breaks, by, theme().get('text_muted'))
        word = "first record" if by == "first" else "latest record"
        path = os.path.join(out_dir, file_name(tm.chip, self.settings, tm.vcs, f"dateclass-{by}"))
        _save(self.page(tm, squares, legend, f"date of {word}"), path)
        return path

    def save_frames(self, tm: TaxonMap, out_dir: str, step: str = "decade",
                    start: Optional[int] = None, gif: bool = True) -> List[str]:
        """Numbered cumulative frames (…_f01_1950s.png), and …_spread.gif if Pillow is there."""
        fr, undated_only = spread.frames(tm.squares, step, start)
        out = []
        for i, f in enumerate(fr, 1):
            squares, legend = spread.frame_squares(tm.squares, f)
            note = (f"{undated_only:,} undated-only square{'s' if undated_only != 1 else ''} "
                    "not shown.") if undated_only else ""
            suffix = f"f{i:02d}_{f['label'].replace(' ', '')}"
            path = os.path.join(out_dir, file_name(tm.chip, self.settings, tm.vcs, suffix))
            _save(self.page(tm, squares, legend, f"recorded to {min(f['to'], date.today().year)}", stamp=f["label"],
                            footer_extra=note), path)
            out.append(path)
        if gif and out:
            g = make_gif(out, os.path.join(out_dir, file_name(tm.chip, self.settings, tm.vcs,
                                                              f"spread-{step}", ".gif")))
            if g:
                out.append(g)
        return out


def _save(img: QImage, path: str):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if not img.save(path, "PNG"):
        raise OSError(f"Could not save {path}")


def _stamp(img: QImage, text: str, dpi: int):
    """The period in large type at the map's top right (frames)."""
    mm = dpi / 25.4
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    f = QFont()
    f.setPointSize(28)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(theme().get('text_primary') or "#1f2937"))
    box = QRectF(img.width() - 12 * mm - 80 * mm, 12 * mm + 22 * mm, 78 * mm, 16 * mm)
    p.drawText(box, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), text)
    p.end()


def pillow_available() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except Exception:
        return False


def make_gif(frames: Sequence[str], path: str, width: int = 900, ms: int = 900,
             hold_last_ms: int = 3000) -> Optional[str]:
    """An animated GIF of the frame PNGs, scaled to `width` px; None without Pillow."""
    try:
        from PIL import Image
    except Exception:
        return None
    imgs = []
    for fp in frames:
        with Image.open(fp) as im:
            im = im.convert("RGB")
            h = round(im.height * width / im.width)
            imgs.append(im.resize((width, h), Image.LANCZOS).convert(
                "P", palette=Image.ADAPTIVE, colors=128))
    durations = [ms] * (len(imgs) - 1) + [hold_last_ms]
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=durations, loop=0,
                 optimize=True)
    return path

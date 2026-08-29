"""Species distribution mini-map: 'everywhere I hold this species'.

Draws a solid GB silhouette (from the VC polygons, filled + same-colour stroked so county
slivers close into one landmass) with a dot per unique ~2 km square where the matched species
occurs across observatum.db -- personal + commercial observations, specimens, and recording
scheme. Display only; queries are read-only and fail soft.
"""
from __future__ import annotations

import sqlite3
from typing import List, Optional, Set, Tuple

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPolygonF
from PySide6.QtWidgets import QWidget

from DataEntry import theme
from DataEntry.vc_map import load_vc_polygons

_DEDUP_M = 1000  # collapse points to a 1 km grid so dots don't overplot
# vector basemap palette
_SEA_C   = "#dbe9f4"; _LAND_C = "#e7ece3"; _COAST_C = "#9fb0a0"
_VCLINE_C = "#c2ccc1"; _GRID100_C = "#c8d2cb"; _GRID10_C = "#b9c6bd"

SOURCE_ORDER = ["personal", "commercial", "collection", "rs", "staging"]
SOURCE_LABELS = {"personal": "Personal", "commercial": "Commercial",
                 "collection": "Insect Collection", "rs": "Recording scheme",
                 "staging": "Data Entry (staged)"}
def source_colours():
    return {"personal": theme.MOSS, "commercial": theme.SLATE,
            "collection": theme.CLAY, "rs": theme.PURPLE,
            "staging": getattr(theme, "GOLD", "#b8860b")}
_MOSAIC_CACHE = {}  # mosaic path -> (cropped QImage, tight OSGB extent)


class DistributionService:
    """Find every ~2 km square holding a species' TVK across observatum.db tables.

    Schema-agnostic: introspects each candidate table for a TVK-like and a grid-ref-like column,
    so it works whatever the exact column names are.
    """

    _TABLES = ("observations", "specimens", "recording_scheme")

    def __init__(self, main_conn: sqlite3.Connection, vc_service=None):
        self._conn = main_conn
        self._vc = vc_service
        self._plan = self._discover()

    def _discover(self):
        # locate the observations / specimens / recording_scheme tables + key columns
        self._obs = self._spec = self._rs = None
        for tbl in self._TABLES:
            try:
                cols = [r[1] for r in self._conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
            except sqlite3.Error:
                continue
            if not cols:
                continue
            tvk_col = next((c for c in cols if c.lower() == "species_tvk"), None) \
                or next((c for c in cols if "tvk" in c.lower()), None)
            grid_col = next((c for c in cols if c.lower() in ("grid_ref", "grid_reference",
                                                              "gridref", "os_grid_ref")), None) \
                or next((c for c in cols if "grid" in c.lower()), None)
            if not (tvk_col and grid_col):
                continue
            if tbl == "specimens" or "specimen" in tbl:
                self._spec = (tbl, tvk_col, grid_col)
            elif "recording" in tbl:
                self._rs = (tbl, tvk_col, grid_col)
            else:
                rt = next((c for c in cols if c.lower() == "record_type"), None)
                self._obs = (tbl, tvk_col, grid_col, rt)

        # entry_staging: uncommitted Data Entry rows (all jobs)
        self._stage = None
        try:
            scols = [r[1] for r in
                     self._conn.execute("PRAGMA table_info(entry_staging)").fetchall()]
            if "species_tvk" in scols and "grid_ref" in scols:
                self._stage = ("entry_staging", "species_tvk", "grid_ref")
        except sqlite3.Error:
            self._stage = None
        return []


    # source priority: lower rank wins when a square has more than one source
    _RANK = {"personal": 0, "commercial": 1, "collection": 2, "rs": 3, "staging": 4}

    def squares_by_source(self, tvk, enabled):
        """Return {(e,n): source} -- one entry per 1 km square, coloured by highest-priority
        enabled source present. `enabled` is a dict of the four source keys -> bool."""
        best = {}
        if not tvk or self._vc is None:
            return {}

        def consider(src, gr):
            try:
                parsed = self._vc.parse_grid_ref(str(gr).strip())
            except Exception:
                parsed = None
            if not parsed:
                return
            e, n = float(parsed[0]), float(parsed[1])
            key = (int(e // _DEDUP_M), int(n // _DEDUP_M))
            r = self._RANK[src]
            cur = best.get(key)
            if cur is None or r < cur[0]:
                best[key] = (r, e, n, src)

        # observations -> personal / commercial (by record_type)
        if self._obs and (enabled.get("personal") or enabled.get("commercial")):
            tbl, tvkc, gridc, rtc = self._obs
            sel = f"{gridc}, {rtc}" if rtc else gridc
            try:
                rows = self._conn.execute(
                    f"SELECT {sel} FROM {tbl} WHERE {tvkc}=? AND {gridc} IS NOT NULL "
                    f"AND {gridc}!=''", (tvk,)).fetchall()
            except sqlite3.Error:
                rows = []
            for row in rows:
                gr = row[0]
                rt = (str(row[1]).strip().lower() if rtc and len(row) > 1 and row[1] else "")
                src = "commercial" if rt.startswith("comm") else "personal"
                if enabled.get(src):
                    consider(src, gr)
        # specimens -> insect collection
        if self._spec and enabled.get("collection"):
            tbl, tvkc, gridc = self._spec
            try:
                rows = self._conn.execute(
                    f"SELECT {gridc} FROM {tbl} WHERE {tvkc}=? AND {gridc} IS NOT NULL "
                    f"AND {gridc}!=''", (tvk,)).fetchall()
            except sqlite3.Error:
                rows = []
            for (gr,) in rows:
                consider("collection", gr)
        # recording scheme
        if self._rs and enabled.get("rs"):
            tbl, tvkc, gridc = self._rs
            try:
                rows = self._conn.execute(
                    f"SELECT {gridc} FROM {tbl} WHERE {tvkc}=? AND {gridc} IS NOT NULL "
                    f"AND {gridc}!=''", (tvk,)).fetchall()
            except sqlite3.Error:
                rows = []
            for (gr,) in rows:
                consider("rs", gr)

        # data entry staging -- uncommitted, all jobs
        if getattr(self, "_stage", None) and enabled.get("staging"):
            tbl, tvkc, gridc = self._stage
            try:
                rows = self._conn.execute(
                    f"SELECT {gridc} FROM {tbl} WHERE {tvkc}=? AND {gridc} IS NOT NULL "
                    f"AND {gridc}!=''", (tvk,)).fetchall()
            except sqlite3.Error:
                rows = []
            for (gr,) in rows:
                consider("staging", gr)
        return {k: (v[1], v[2], v[3]) for k, v in best.items()}


from DataEntry._panzoom import PanZoomMixin

_OUTLINE_CACHE = {}

def _load_gb_outline(maps_dir):
    """Load the complete GB coastline (OSGB rings) from data/maps/gb_outline.json.

    Returns (rings_dict, bounds) where rings_dict is {0: [ring, ring, ...]} of (E,N) rings.
    Cached. Empty dict if the file is missing.
    """
    import json, os as _os
    if not maps_dir:
        return {}, (0.0, 0.0, 700000.0, 1300000.0)
    path = _os.path.join(maps_dir, "gb_outline.json")
    if path in _OUTLINE_CACHE:
        return _OUTLINE_CACHE[path]
    if not _os.path.exists(path):
        return {}, (0.0, 0.0, 700000.0, 1300000.0)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        rings = [[(float(e), float(n)) for e, n in r] for r in data.get("rings", [])]
        b = data.get("bounds") or [0, 0, 700000, 1300000]
        result = ({0: rings}, (float(b[0]), float(b[1]), float(b[2]), float(b[3])))
    except Exception:
        result = ({}, (0.0, 0.0, 700000.0, 1300000.0))
    _OUTLINE_CACHE[path] = result
    return result


class DistributionMiniMap(PanZoomMixin, QWidget):
    """Solid GB with a dot per unique square for the current species."""

    def __init__(self, geojson_path: Optional[str], service: Optional[DistributionService] = None,
                 resizable: bool = False, tiles_dir: Optional[str] = None,
                 maps_dir: Optional[str] = None, parent=None):
        super().__init__(parent)
        self._service = service
        self._dots = []            # list of (e, n, source)
        self._count = 0
        self._tvk = None
        self._enabled = {k: True for k in SOURCE_ORDER}
        self._land_pix = None
        self._land_size = None
        self._mosaic = None
        self._extent = None
        self._rings = {}
        from PySide6.QtGui import QColor
        self._sea = QColor(220, 233, 244)  # pale sea-blue (used when mosaic present)

        # Clean VECTOR GB basemap: complete detailed coastline (data/maps/gb_outline.json).
        self._rings, self._bounds = _load_gb_outline(maps_dir)
        if not self._rings:  # fallback: VC polygons (incomplete, but better than nothing)
            self._rings, self._bounds = load_vc_polygons(geojson_path, tol=0) \
                if geojson_path else ({}, (0.0, 0.0, 700000.0, 1300000.0))
        self._extent = self._bounds

        minE, minN, maxE, maxN = self._extent
        aspect = (maxE - minE) / (maxN - minN) if (maxN - minN) else 0.55
        if resizable:
            from PySide6.QtWidgets import QSizePolicy
            self.setMinimumSize(max(150, int(320 * aspect)), 320)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._init_panzoom(True)
        else:
            H = 148  # match the location map's height; width follows GB's proportions
            self.setFixedSize(max(90, int(H * aspect)), H)
            self._init_panzoom(False)
        self.setToolTip("Every ~2 km square where you hold this species (all your records).")

    # GB land bounding box in OSGB metres (from the VC boundary extent) -- deterministic crop.
    _GB_LAND = (13000.0, 5000.0, 654000.0, 1211000.0)

    @staticmethod
    def _crop_land(img, full_extent):
        """Crop the national-box mosaic to GB's land bbox (trims sea margins predictably)."""
        w, h = img.width(), img.height()
        minE, minN, maxE, maxN = full_extent
        lE0, lN0, lE1, lN1 = DistributionMiniMap._GB_LAND
        x0 = int((lE0 - minE) / (maxE - minE) * w)
        x1 = int((lE1 - minE) / (maxE - minE) * w)
        y0 = int((maxN - lN1) / (maxN - minN) * h)
        y1 = int((maxN - lN0) / (maxN - minN) * h)
        x0 = max(0, min(x0, w - 1)); x1 = max(x0 + 1, min(x1, w))
        y0 = max(0, min(y0, h - 1)); y1 = max(y0 + 1, min(y1, h))
        cropped = img.copy(x0, y0, x1 - x0, y1 - y0)
        return cropped, (lE0, lN0, lE1, lN1)

    _SEA = _SEA_C; _LAND = _LAND_C; _COAST = _COAST_C
    _VCLINE = _VCLINE_C; _GRID100 = _GRID100_C; _GRID10 = _GRID10_C

    def has_data(self) -> bool:
        return bool(self._rings)

    @staticmethod
    def _sample_sea(img):
        """Grab the OS sea-blue from a known-sea pixel (top-left corner of the GB box)."""
        from PySide6.QtGui import QColor
        try:
            c = QColor(img.pixel(3, 3))
            if c.red() > 245 and c.green() > 245 and c.blue() > 245:
                return QColor(220, 233, 244)  # near-white corner -> sensible pale blue
            return c
        except Exception:
            return QColor(220, 233, 244)

    def resizeEvent(self, ev):
        self._land_pix = None  # invalidate cached land on resize
        super().resizeEvent(ev)

    def has_data(self) -> bool:
        return bool(self._rings) or self._mosaic is not None

    def update_for_species(self, tvk, enabled=None):
        self._tvk = tvk
        if enabled is not None:
            self._enabled = dict(enabled)
        if self._service and tvk:
            d = self._service.squares_by_source(tvk, self._enabled)
            self._dots = [(e, n, s) for (e, n, s) in d.values()]
        else:
            self._dots = []
        self._count = len(self._dots)
        self.update()

    def refresh(self):
        """Recompute with the last species + current source flags (for live pop-outs)."""
        self.update_for_species(self._tvk, self._enabled)

    def clear(self):
        self._dots = []
        self._count = 0
        self.update()

    def _to_px(self, e, n):
        minE, minN, maxE, maxN = self._extent
        pad = 5
        availw = self.width() - 2 * pad
        availh = self.height() - 2 * pad
        s = min(availw / (maxE - minE), availh / (maxN - minN))
        offx = pad + (availw - (maxE - minE) * s) / 2.0   # centre horizontally
        offy = pad + (availh - (maxN - minN) * s) / 2.0   # centre vertically
        return offx + (e - minE) * s, self.height() - offy - (n - minN) * s

    def _build_land_pixmap(self):
        from PySide6.QtGui import QPixmap
        pm = QPixmap(self.size())
        pm.fill(QColor(self._SEA))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # land fill + coastline
        land = QColor(self._LAND)
        coast = QColor(self._COAST)
        polys = []
        for _vc, rings in self._rings.items():
            for ring in rings:
                polys.append(QPolygonF([QPointF(*self._to_px(e, n)) for e, n in ring]))
        p.setPen(QPen(land, 0.8)); p.setBrush(QBrush(land))
        for poly in polys:
            p.drawPolygon(poly)
        # vice-county boundaries (thin) -- fade in a touch with zoom
        z = getattr(self, "_zoom", 1.0)
        vc_w = 0.35 + 0.20 * min(z, 4.0)
        p.setPen(QPen(QColor(self._VCLINE), vc_w)); p.setBrush(Qt.BrushStyle.NoBrush)
        for poly in polys:
            p.drawPolyline(poly)
        # coastline on top of the land edge
        p.setPen(QPen(coast, 0.7)); p.setBrush(Qt.BrushStyle.NoBrush)
        for poly in polys:
            p.drawPolyline(poly)
        # faint national grid: 100 km always; 10 km fades in when zoomed
        self._draw_grid(p, z)
        p.end()
        self._land_pix = pm
        self._land_size = self.size()

    def _draw_grid(self, p, z):
        minE, minN, maxE, maxN = self._extent
        def vline(E, col, w):
            x0, y0 = self._to_px(E, minN); x1, y1 = self._to_px(E, maxN)
            p.setPen(QPen(col, w)); p.drawLine(int(x0), int(y0), int(x1), int(y1))
        def hline(N, col, w):
            x0, y0 = self._to_px(minE, N); x1, y1 = self._to_px(maxE, N)
            p.setPen(QPen(col, w)); p.drawLine(int(x0), int(y0), int(x1), int(y1))
        g100 = QColor(self._GRID100)
        for E in range(0, 700001, 100000):
            if minE - 1 <= E <= maxE + 1: vline(E, g100, 0.5)
        for N in range(0, 1300001, 100000):
            if minN - 1 <= N <= maxN + 1: hline(N, g100, 0.5)
        if z >= 2.2:  # 10 km lines only once zoomed in, faded by zoom
            a = int(min(60, (z - 2.2) * 40))
            g10 = QColor(self._GRID10); g10.setAlpha(a)
            for E in range(0, 700001, 10000):
                if E % 100000 and minE <= E <= maxE: vline(E, g10, 0.3)
            for N in range(0, 1300001, 10000):
                if N % 100000 and minN <= N <= maxN: hline(N, g10, 0.3)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._land_pix is None or self._land_size != self.size():
            self._build_land_pixmap()
        p.save(); self._apply_pan_zoom(p)
        p.drawPixmap(0, 0, self._land_pix)
        if self._dots:
            cols = source_colours()
            p.setPen(QPen(QColor(theme.PAPER), 0.6))
            for e, n, src in self._dots:
                x, y = self._to_px(e, n)
                p.setBrush(QBrush(QColor(cols.get(src, theme.CLAY))))
                p.drawEllipse(int(x - 2.5), int(y - 2.5), 5, 5)
        p.restore()
        f = p.font(); f.setPointSize(6); p.setFont(f)
        if self._mosaic is not None:
            p.setPen(QColor(80, 80, 80))
            p.drawText(6, 12, "\u00a9 Crown copyright OS")
        p.end()

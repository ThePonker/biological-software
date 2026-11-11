"""Home > "Where I've recorded" (Round 19): the suite's GridMap (shared/maps) showing the 10 km
squares that hold your records, shaded by number of records (1-9, 10-99, 100+).

Show: This year (default) / All years / Selected species (the one chosen in the species card).
The squares are one aggregate query (home_data.hectad_squares) run off the GUI thread. Click a
square -> its records in the Mapping tab's SquareRecordsDialog. "Open in Mapping" -> signal.
"""
from datetime import date
from typing import Dict

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout

from shared.maps.grid_squares import GRID_LABELS, HECTAD
from shared.text_sizes import font_css
from . import home_data as hd
from .card import Card
from .home_widgets import link_button
from .home_worker import JobRunner
from ...themes import theme

MODES = ((hd.THIS_YEAR, "This year"), (hd.ALL_YEARS, "All years"), (hd.SELECTED, "Selected species"))


def class_colours() -> list:
    """The three shades, light to dark, mixed from the theme's observation greens with the
    Mapping tab's own colour mixer."""
    from ..mapping.square_style import _mix
    t = theme()
    light, dark = t.get("accent_observation_light"), t.get("accent_observation_dark")
    return [_mix(light, dark, k) for k in (0.45, 0.72, 1.0)]


def count_line(n: int, mode: str, year: int, name: str = "") -> str:
    sq = f"{n:,} ten-km square{'' if n == 1 else 's'}"
    if mode == hd.THIS_YEAR:
        return f"{sq} in {year}"
    if mode == hd.SELECTED:
        return f"{sq} for {name}" if name else "Choose a species in the species card"
    return f"{sq}, all years"


class HomeMapCard(Card):
    open_mapping_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__("Where I've recorded", parent)
        self._db_path = None
        self._species: Dict[str, str] = {"tvk": "", "name": ""}
        self._squares: dict = {}
        self._jobs = JobRunner(self)
        self._dialog_jobs = JobRunner(self)
        t = theme()
        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {t.get('text_primary')}; font-size: {font_css('body')};"
                                       " border: none; background: transparent;")
        self.mode_combo = QComboBox()
        for key, text in MODES:
            self.mode_combo.addItem(text, key)
        self.mode_combo.currentIndexChanged.connect(self.reload)
        show = QLabel("Show")
        show.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {font_css('small')};"
                           " border: none; background: transparent;")
        self.add_header_widget(show)
        self.add_header_widget(self.mode_combo)
        self.add_widget(self.count_label)

        # The map widget (and the shared map modules it imports) is built just after Home
        # appears, not inside its constructor: Home's start-up does not wait for it
        self.map_widget = None
        self._map_slot = QVBoxLayout()
        self._map_slot.setContentsMargins(0, 0, 0, 0)
        self.add_layout(self._map_slot)
        self._main_layout.setStretchFactor(self._map_slot, 1)
        QTimer.singleShot(0, self.ensure_map)

        self.key_row = QHBoxLayout()
        self.key_row.setSpacing(6)
        self._swatches = []
        for _i, (_lo, _hi, label) in enumerate(hd.CLASSES):
            box = QFrame()
            box.setFixedSize(12, 12)
            self._swatches.append(box)
            lab = QLabel(label)
            lab.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {font_css('caption')};"
                              " border: none; background: transparent;")
            self.key_row.addWidget(box)
            self.key_row.addWidget(lab)
        self.key_row.addStretch()
        self.open_btn = link_button("Open in Mapping →", t.get("accent_mapping_dark"))
        self.open_btn.clicked.connect(self.open_mapping_clicked.emit)
        self.key_row.addWidget(self.open_btn)
        self.add_layout(self.key_row)       # swatches are coloured in ensure_map (mapping import)

    def ensure_map(self):
        """Build the GridMap if it is not built yet (a no-op afterwards)."""
        if self.map_widget is not None:
            return
        import paths
        from shared.maps.grid_map import GridMap
        geojson = str(paths.VC_GEOJSON) if paths.VC_GEOJSON.exists() else None
        self.map_widget = GridMap(geojson_path=geojson, maps_dir=str(paths.MAPS_DIR))
        self.map_widget.setMinimumSize(200, 240)
        self.map_widget.set_vc_labels(False)       # numbers over the squares are clutter here
        self.map_widget.square_clicked.connect(self._on_square_clicked)
        self._map_slot.addWidget(self.map_widget)
        self._paint_key()
        if self._squares:
            self.map_widget.set_squares(self._squares, HECTAD)

    # ------------------------------------------------------------------ data
    def mode(self) -> str:
        return self.mode_combo.currentData()

    def set_database(self, db_path):
        self._db_path = db_path

    def set_species(self, tvk: str, name: str):
        """The species chosen in the species card (the map follows it in Selected species mode)."""
        self._species = {"tvk": tvk or "", "name": name or ""}
        if self.mode() == hd.SELECTED:
            self.reload()

    def reload(self, *_a):
        """Read the squares again (off the GUI thread) and draw them."""
        if not self._db_path:
            return
        mode, sp, year, path = self.mode(), dict(self._species), date.today().year, self._db_path
        if mode == hd.SELECTED and not sp["tvk"]:
            self._show({}, mode, year, sp)
            return
        self._jobs.start(lambda: hd.hectad_squares(path, mode, year, sp["tvk"], sp["name"]),
                         lambda sq: self._show(sq, mode, year, sp))

    def _show(self, squares: dict, mode: str, year: int, sp: dict):
        cols = class_colours()
        self._squares = {k: dict(v, fill=cols[v["class"]]) for k, v in squares.items()}
        self._mode_shown = (mode, year, dict(sp))
        if self.map_widget is not None:
            self.map_widget.set_squares(self._squares, HECTAD)
        self.count_label.setText(count_line(len(self._squares), mode, year, sp["name"]))

    # ------------------------------------------------------------------ clicks
    def _on_square_clicked(self, label: str):
        if not self._db_path:
            return
        mode, year, sp = getattr(self, "_mode_shown", (self.mode(), date.today().year, self._species))
        path = self._db_path
        self._dialog_jobs.start(lambda: hd.square_records(path, label, mode, year, sp["tvk"], sp["name"]),
                                lambda recs: self._open_dialog(label, recs, sp["name"] if mode == hd.SELECTED else ""))

    def _open_dialog(self, label: str, recs: list, species_text: str):
        from ..mapping.square_records_dialog import SquareRecordsDialog
        SquareRecordsDialog(label, GRID_LABELS[HECTAD], recs, species_text, self).exec()

    # ------------------------------------------------------------------ look
    def _paint_key(self):
        for box, col in zip(self._swatches, class_colours()):
            box.setStyleSheet(f"background: {col}; border: none;")

    def apply_theme(self):
        super().apply_theme()
        self._paint_key()
        if hasattr(self, "_mode_shown"):
            self._show(self._squares_as_counts(), *self._mode_shown)

    def _squares_as_counts(self) -> dict:
        return {k: {"count": v["count"], "class": v["class"]} for k, v in self._squares.items()}


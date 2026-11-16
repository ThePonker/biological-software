"""Home > "Where I've recorded" (Round 19; recorded-or-not and the year choice, Round 20): the suite's
GridMap (shared/maps) showing the 10 km squares that hold your records, all in one colour.

Show: This year (default) / All years / Selected species (the one chosen in the species card) /
then every year with a Personal record (newest first, apart from this year). The squares are one
aggregate query (home_data.hectad_squares) run off the GUI thread, with the list of years. Click a
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


def recorded_colour() -> str:
    """The one colour of every square with a record: the darkest of the theme's observation greens."""
    return theme().get("accent_observation_dark")


def count_line(n: int, mode: str, year: int, name: str = "") -> str:
    sq = f"{n:,} ten-km square{'' if n == 1 else 's'}"
    if mode == hd.THIS_YEAR:
        return f"{sq} in {year}"
    if mode == hd.SELECTED:
        return f"{sq} for {name}" if name else "Choose a species in the species card"
    return f"{sq} in all years"


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
        self._fill_combo([], hd.THIS_YEAR)
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
        self.swatch = QFrame()
        self.swatch.setFixedSize(12, 12)
        lab = QLabel("Recorded")
        lab.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {font_css('caption')};"
                          " border: none; background: transparent;")
        self.key_row.addWidget(self.swatch)
        self.key_row.addWidget(lab)
        self.key_row.addStretch()
        self.open_btn = link_button("Open in Mapping →", t.get("accent_mapping_dark"))
        self.open_btn.clicked.connect(self.open_mapping_clicked.emit)
        self.key_row.addWidget(self.open_btn)
        self.add_layout(self.key_row)       # the swatch is coloured in ensure_map

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
    def _fill_combo(self, years, choice: str):
        """The Show list: This year, All years, Selected species, a separator, then each year
        (newest first, not this year); `choice` is selected again when it is still offered."""
        combo = self.mode_combo
        combo.blockSignals(True)
        combo.clear()
        for key, text in MODES:
            combo.addItem(text, key)
        this_year = date.today().year
        years = [y for y in years if y != this_year]
        if years:
            combo.insertSeparator(combo.count())
            for y in years:
                combo.addItem(str(y), f"{hd.YEAR_PREFIX}{y}")
        i = combo.findData(choice)
        combo.setCurrentIndex(i if i >= 0 else 0)      # a year no longer in the data: This year
        combo.blockSignals(False)

    def choice(self) -> str:
        return self.mode_combo.currentData() or hd.THIS_YEAR

    def mode(self) -> str:
        return hd.choice_mode(self.choice())[0]

    def set_database(self, db_path):
        self._db_path = db_path

    def set_species(self, tvk: str, name: str):
        """The species chosen in the species card (the map follows it in Selected species mode)."""
        self._species = {"tvk": tvk or "", "name": name or ""}
        if self.mode() == hd.SELECTED:
            self.reload()

    def reload(self, *_a):
        """Read the years and the squares again (off the GUI thread) and draw them."""
        if not self._db_path:
            return
        choice, sp, path = self.choice(), dict(self._species), self._db_path
        mode, year = hd.choice_mode(choice)
        if mode == hd.SELECTED and not sp["tvk"]:
            self._show({}, mode, year, sp)
            return

        def read():
            years = hd.map_years(path)
            eff = choice
            if choice.startswith(hd.YEAR_PREFIX) and year not in years:
                eff = hd.THIS_YEAR                        # the remembered year has no records now
            m, y = hd.choice_mode(eff)
            return years, eff, hd.hectad_squares(path, m, y, sp["tvk"], sp["name"])

        self._jobs.start(read, lambda out: self._loaded(out, sp))

    def _loaded(self, out, sp: dict):
        years, choice, squares = out
        self._fill_combo(years, choice)
        mode, year = hd.choice_mode(choice)
        self._show(squares, mode, year, sp)

    def _show(self, squares: dict, mode: str, year: int, sp: dict):
        fill = recorded_colour()
        self._squares = {k: dict(v, fill=fill) for k, v in squares.items()}
        self._mode_shown = (mode, year, dict(sp))
        if self.map_widget is not None:
            self.map_widget.set_squares(self._squares, HECTAD)
        self.count_label.setText(count_line(len(self._squares), mode, year, sp["name"]))

    # ------------------------------------------------------------------ clicks
    def _on_square_clicked(self, label: str):
        if not self._db_path:
            return
        mode, year, sp = getattr(self, "_mode_shown", (*hd.choice_mode(self.choice()), self._species))
        path = self._db_path
        self._dialog_jobs.start(lambda: hd.square_records(path, label, mode, year, sp["tvk"], sp["name"]),
                                lambda recs: self._open_dialog(label, recs, sp["name"] if mode == hd.SELECTED else ""))

    def _open_dialog(self, label: str, recs: list, species_text: str):
        from ..mapping.square_records_dialog import SquareRecordsDialog
        SquareRecordsDialog(label, GRID_LABELS[HECTAD], recs, species_text, self).exec()

    # ------------------------------------------------------------------ look
    def _paint_key(self):
        self.swatch.setStyleSheet(f"background: {recorded_colour()}; border: none;")

    def apply_theme(self):
        super().apply_theme()
        self._paint_key()
        if hasattr(self, "_mode_shown"):
            self._show(self._squares_as_counts(), *self._mode_shown)

    def _squares_as_counts(self) -> dict:
        return {k: {"count": v["count"]} for k, v in self._squares.items()}

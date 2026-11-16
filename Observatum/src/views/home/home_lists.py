"""Home's "Last 10 new species" list (Round 19; the Notable records list left in Round 20): a Card
whose rows scroll inside it; the data comes from home_data."""
from typing import List

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from shared.text_sizes import font_css
from .card import Card
from .home_widgets import link_button, note_label
from ...core.config import Defaults, Settings
from ...themes import theme


def _scroller(inner: QWidget) -> QScrollArea:
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setFrameShape(QFrame.Shape.NoFrame)
    sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sc.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }")
    sc.setWidget(inner)
    return sc


def _name_html(row: dict, show_common: bool) -> str:
    t = theme()
    sci, common = row.get("species_name", ""), row.get("common_name", "")
    if common and show_common:
        return f"{common} <i style='color:{t.get('text_secondary')}'>{sci}</i>"
    return f"<i>{sci}</i>"


def _show_common_names() -> bool:
    return QSettings().value(Settings.COMMON_NAMES_HOME, Defaults.SHOW_COMMON_NAMES, type=bool)


class NewSpeciesCard(Card):
    """The ten species whose first record is the most recent, newest first."""
    species_selected = Signal(dict)
    view_all_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__("Last 10 new species", parent)
        self._rows: List[dict] = []
        self.view_all_btn = link_button("View all")
        self.view_all_btn.clicked.connect(self.view_all_clicked.emit)
        self.add_header_widget(self.view_all_btn)
        self.add_widget(note_label("Firsts for your list, any group"))
        self._body = QWidget()
        self._lay = QVBoxLayout(self._body)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(9)
        self._lay.addStretch()
        self.add_widget(_scroller(self._body))
        self._main_layout.setStretchFactor(self._main_layout.itemAt(self._main_layout.count() - 1).widget(), 1)

    def update_species(self, rows: List[dict]):
        self._rows = rows
        while self._lay.count() > 1:
            w = self._lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        t, common = theme(), _show_common_names()
        for i, r in enumerate(rows):
            lab = QLabel(f"{_name_html(r, common)}<br><span style='color:{t.get('text_secondary')};"
                         f"font-size:{font_css('caption')}'>"
                         + " · ".join(x for x in (r["group"], r["short_date"], r["site_name"]) if x)
                         + "</span>")
            lab.setWordWrap(True)
            lab.setTextFormat(Qt.TextFormat.RichText)
            lab.setCursor(Qt.CursorShape.PointingHandCursor)
            lab.setToolTip(f"{r['species_name']}\nFirst recorded {r['date']}")
            lab.setStyleSheet(f"color: {t.get('text_primary')}; font-size: {font_css('body')};"
                              " border: none; background: transparent;")
            lab.mousePressEvent = lambda _e, row=r: self.species_selected.emit(
                {"species_name": row["species_name"], "scientific_name": row["species_name"],
                 "common_name": row["common_name"], "species_tvk": row["species_tvk"],
                 "tvk": row["species_tvk"]})
            self._lay.insertWidget(i, lab)

    def refresh_common_name_setting(self):
        if self._rows:
            self.update_species(self._rows)

    def apply_theme(self):
        super().apply_theme()
        if self._rows:
            self.update_species(self._rows)

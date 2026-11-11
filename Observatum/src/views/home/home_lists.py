"""Home's two lists (Round 19): "Last 10 new species" and "Notable records". Each is a Card
whose rows scroll inside it; the data comes from home_data (notable ones off the GUI thread)."""
from typing import List

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QScrollArea, QVBoxLayout, QWidget)

from shared.repositories.codex_repository import NOTABLE_STATUS_ORDER
from shared.text_sizes import font_css
from . import home_data as hd
from .card import Card
from .home_widgets import link_button, note_label, pill_button
from .home_worker import JobRunner
from ...core.config import Defaults, Settings
from ...themes import theme

RARE_BADGES = frozenset(NOTABLE_STATUS_ORDER[:6])        # CR EN VU RDB1 RDB2 NR: the red badges


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


class NotableCard(Card):
    """Your records of the year of notable species: newest first or highest status first."""
    all_clicked = Signal(list)          # ids of every notable record this year

    def __init__(self, parent=None):
        super().__init__("Notable records", parent)
        self._db_path = None
        self._data = {"total": 0, "ids": [], "rows": []}
        self._jobs = JobRunner(self)
        self.all_btn = link_button("")
        self.all_btn.clicked.connect(lambda: self.all_clicked.emit(list(self._data["ids"])))
        self.add_header_widget(self.all_btn)
        self.add_widget(note_label(
            f"Your {hd.date.today().year} records of species notable for rarity or threat, "
            "Nationally Scarce or rarer, Red List VU–CR"))
        pills = QHBoxLayout()
        pills.setSpacing(6)
        self.newest_btn, self.highest_btn = pill_button("Newest"), pill_button("Highest status")
        self.personal_btn = pill_button("Personal only")
        group = QButtonGroup(self)
        group.setExclusive(True)
        for b in (self.newest_btn, self.highest_btn):
            group.addButton(b)
            pills.addWidget(b)
        pills.addWidget(self.personal_btn)
        pills.addStretch()
        self.newest_btn.setChecked(True)
        self.add_layout(pills)
        for b in (self.newest_btn, self.highest_btn, self.personal_btn):
            b.clicked.connect(self.reload)
        self._body = QWidget()
        self._grid = QGridLayout(self._body)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(10)
        self._grid.setVerticalSpacing(10)
        self._grid.setColumnStretch(1, 1)
        self._grid.setRowStretch(0, 1)
        self.scroll = _scroller(self._body)
        self.add_widget(self.scroll)
        self._main_layout.setStretchFactor(self.scroll, 1)
        self._set_all_text()

    def sort_mode(self) -> str:
        return hd.HIGHEST if self.highest_btn.isChecked() else hd.NEWEST

    def set_database(self, db_path):
        self._db_path = db_path

    def reload(self, *_a):
        if not self._db_path:
            return
        path, sort, pers = self._db_path, self.sort_mode(), self.personal_btn.isChecked()
        self._jobs.start(lambda: hd.notable_records(path, personal_only=pers, sort=sort), self.show_data)

    def show_data(self, data: dict):
        self._data = data
        t, common = theme(), _show_common_names()
        while self._grid.count():
            w = self._grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        for i, r in enumerate(data["rows"]):
            rare = r["status"] in RARE_BADGES
            bg, fg = (t.get("danger_bg"), t.get("danger_text")) if rare else (t.get("warning_bg"), t.get("warning_text"))
            badge = QLabel(r["status"])
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedWidth(56)
            badge.setStyleSheet(f"background: {bg}; color: {fg}; font-size: {font_css('caption')};"
                                " font-weight: 600; border-radius: 4px; padding: 2px 0; border: none;")
            more = f"{r['n']} records" if r.get("n", 1) > 1 else ""
            where = " · ".join(x for x in (r["site_name"], r["grid_ref"], more) if x)
            name = QLabel(f"{_name_html(r, common)}<br><span style='color:{t.get('text_secondary')};"
                          f"font-size:{font_css('caption')}'>{where}</span>")
            name.setWordWrap(True)
            name.setTextFormat(Qt.TextFormat.RichText)
            name.setStyleSheet(f"color: {t.get('text_primary')}; font-size: {font_css('body')};"
                               " border: none; background: transparent;")
            date = QLabel(r["short_date"])
            date.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {font_css('caption')};"
                               " border: none; background: transparent;")
            date.setToolTip(r["date"])
            self._grid.addWidget(badge, i, 0, Qt.AlignmentFlag.AlignTop)
            self._grid.addWidget(name, i, 1)
            self._grid.addWidget(date, i, 2, Qt.AlignmentFlag.AlignTop)
        self._grid.setRowStretch(len(data["rows"]), 1)
        self._set_all_text()

    def _set_all_text(self):
        self.all_btn.setText(f"All {self._data['total']:,} records")
        self.all_btn.setVisible(self._data["total"] > 0)

    def apply_theme(self):
        super().apply_theme()
        self.show_data(self._data)

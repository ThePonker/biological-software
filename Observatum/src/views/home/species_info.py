"""
Species card for Home (Round 19 layout; the old Species Info panel, re-laid out).

A search box (the suite's SpeciesSearch, as Quick Entry used) and, for the chosen species: name,
family, status and SQS (Codex, via species_status), your records with a "view" link, first / last
record, in the collection or not, "Species profile" and "Open in Species lookup".
"""

from typing import Dict, Optional

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from shared.text_sizes import font_css
from .card import Card
from .home_widgets import link_button
from ..components.species_search import SpeciesSearch
from ...core.config import Defaults, Settings, TabColors
from ...themes import theme


def _first_last(species: Dict) -> str:
    first, last = (species.get('first_date') or '')[:10], (species.get('last_date') or '')[:10]
    if not first:
        return "–"
    from .home_data import short_date
    fmt = lambda d: f"{short_date(d)} {d[:4]}"      # noqa: E731
    return fmt(first) if first == last or not last else f"{fmt(first)} / {fmt(last)}"


class SpeciesInfoPanel(Card):
    """Search plus the details of the chosen species."""

    view_specimens_clicked = Signal(str)  # Emits species TVK
    view_records_clicked = Signal(str)  # Emits species name for filtering observations
    profile_clicked = Signal(dict)  # Emits species data for the profile dialog
    lookup_clicked = Signal(str, str)  # (scientific name, TVK): Stats > Species lookup (Q55)
    species_chosen = Signal(dict)  # picked in the search box

    def __init__(self, parent=None):
        super().__init__("Species", parent)
        self._current_species: Optional[Dict] = None
        self._current_profile: str = ""
        self._show_common_names = True
        self._load_common_name_setting()
        self._setup_ui()

    def _load_common_name_setting(self):
        self._show_common_names = QSettings().value(
            Settings.COMMON_NAMES_HOME, Defaults.SHOW_COMMON_NAMES, type=bool)

    # ------------------------------------------------------------------ build
    def _setup_ui(self):
        self.clear_btn = link_button("Clear", theme().get('text_secondary'))
        self.clear_btn.clicked.connect(self.clear)
        self.clear_btn.setVisible(False)
        self.add_header_widget(self.clear_btn)

        self.search = SpeciesSearch()
        self.search.species_selected.connect(self.species_chosen.emit)
        self.search.search_cleared.connect(lambda: self.set_species(None))
        self.add_widget(self.search)

        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(self.content)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        top = QHBoxLayout()
        self.name_label = QLabel()
        self.name_label.setWordWrap(True)
        top.addWidget(self.name_label, 1)
        self.profile_btn = link_button("Species profile →")
        self.profile_btn.clicked.connect(self._on_profile_clicked)
        top.addWidget(self.profile_btn, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)
        self.common_name_label = QLabel()
        lay.addWidget(self.common_name_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        self._captions = []
        self.family_value = self._cell(grid, 0, 0, "Family")
        self.status_value = self._cell(grid, 0, 1, "Status")
        self.sqs_value = self._cell(grid, 0, 2, "SQS")
        self.records_value = self._cell(grid, 1, 0, "Your records")
        self.view_records_btn = link_button("view", TabColors.OBSERVATION)
        self.view_records_btn.clicked.connect(self._on_view_records)
        self.view_records_btn.setVisible(False)
        grid.itemAtPosition(1, 0).widget().layout().itemAt(1).layout().insertWidget(1, self.view_records_btn)
        self.first_last_value = self._cell(grid, 1, 1, "First / last")
        self.collection_status = self._cell(grid, 1, 2, "Collection")
        self.view_specimens_btn = link_button("view", TabColors.COLLECTION)
        self.view_specimens_btn.clicked.connect(self._on_view_specimens)
        self.view_specimens_btn.setVisible(False)
        grid.itemAtPosition(1, 2).widget().layout().itemAt(1).layout().insertWidget(1, self.view_specimens_btn)
        for c in range(3):
            grid.setColumnStretch(c, 1)
        lay.addLayout(grid)

        self.lookup_btn = link_button("Open in Species lookup →", TabColors.STATS)
        self.lookup_btn.setToolTip("Every count for this species: records, scheme, specimens, phenology")
        self.lookup_btn.clicked.connect(self._on_lookup)
        lay.addWidget(self.lookup_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.content.setVisible(False)
        self.add_widget(self.content)

        self.placeholder = QLabel("Search for a species to see its details")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setWordWrap(True)
        self.add_widget(self.placeholder)
        self._style()

    def _cell(self, grid, row, col, caption) -> QLabel:
        """A caption over a value (a row for the value, so a link can sit beside it)."""
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(1)
        cap = QLabel(caption)
        self._captions.append(cap)
        v.addWidget(cap)
        h = QHBoxLayout()
        h.setSpacing(6)
        val = QLabel("–")
        val.setWordWrap(True)
        h.addWidget(val)
        h.addStretch()
        v.addLayout(h)
        grid.addWidget(box, row, col)
        return val

    def _style(self):
        t = theme()
        base = "border: none; background: transparent;"
        self.name_label.setStyleSheet(f"font-size: {font_css('title')}; font-weight: 600; font-style: italic;"
                                      f" color: {t.get('text_primary')}; {base}")
        self.common_name_label.setStyleSheet(f"color: {t.get('text_primary')}; font-size: {font_css('body')}; {base}")
        for cap in self._captions:
            cap.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {font_css('caption')}; {base}")
        for val in (self.family_value, self.status_value, self.sqs_value, self.records_value,
                    self.first_last_value, self.collection_status):
            val.setStyleSheet(f"color: {t.get('text_primary')}; font-size: {font_css('body')}; {base}")
        self.placeholder.setStyleSheet(f"color: {t.get('text_muted')}; font-style: italic; padding: 24px; {base}")

    # ------------------------------------------------------------------ content
    def clear(self):
        self.search.clear()          # emits search_cleared -> set_species(None)
        self.set_species(None)

    def _show_status(self, tvk):
        from .species_status import lookup
        status, sqs = lookup(tvk)
        self.status_value.setText(status)
        self.sqs_value.setText(sqs)

    def set_species(self, species_data: Optional[Dict]):
        """Update the displayed species (None: empty card)."""
        self._current_species = species_data
        if not species_data:
            self.content.setVisible(False)
            self.placeholder.setVisible(True)
            self.clear_btn.setVisible(False)
            return
        self.content.setVisible(True)
        self.placeholder.setVisible(False)
        self.clear_btn.setVisible(True)

        self.name_label.setText(species_data.get('scientific_name', 'Unknown'))
        common = species_data.get('common_name', '')
        self.common_name_label.setVisible(bool(self._show_common_names and common))
        self.common_name_label.setText(common)
        self.family_value.setText(species_data.get('family') or '–')
        self._show_status(species_data.get('tvk') or species_data.get('species_tvk'))

        n = species_data.get('record_count', 0)
        self.records_value.setText(f"{n:,}")
        self.view_records_btn.setVisible(n > 0)
        self.first_last_value.setText(_first_last(species_data))
        if species_data.get('in_collection', False):
            self.collection_status.setText(f"{species_data.get('specimen_count', 0):,} held")
            self.view_specimens_btn.setVisible(True)
        else:
            self.collection_status.setText("Not held")
            self.view_specimens_btn.setVisible(False)
        self._load_profile(species_data.get('tvk'))

    def _load_profile(self, tvk: str):
        """_current_profile holds YOUR account only (the one shared reader)."""
        self._current_profile = ""
        if not tvk:
            return
        try:
            from shared.species_accounts import get_species_accounts
            self._current_profile = get_species_accounts(tvk).own or ""
        except Exception as e:
            print(f"Error loading profile: {e}")

    def set_profile(self, profile_text: str):
        """Your account was edited in the profile dialog."""
        self._current_profile = profile_text

    def refresh_common_name_setting(self):
        old = self._show_common_names
        self._load_common_name_setting()
        if old != self._show_common_names and self._current_species:
            self.set_species(self._current_species)

    # ------------------------------------------------------------------ clicks
    def _on_view_records(self):
        if self._current_species:
            name = self._current_species.get('species_name') or self._current_species.get('scientific_name', '')
            if name:
                self.view_records_clicked.emit(name)

    def _on_lookup(self):
        if self._current_species:
            name = (self._current_species.get('scientific_name')
                    or self._current_species.get('species_name') or '')
            tvk = self._current_species.get('tvk') or self._current_species.get('species_tvk') or ''
            if name:
                self.lookup_clicked.emit(name, tvk)

    def _on_view_specimens(self):
        if self._current_species:
            tvk = self._current_species.get('tvk') or self._current_species.get('species_tvk')
            if tvk:
                self.view_specimens_clicked.emit(tvk)

    def _on_profile_clicked(self):
        if self._current_species:
            self.profile_clicked.emit(self._current_species)

    def apply_theme(self):
        super().apply_theme()
        self._style()
        if self._current_species:
            self.set_species(self._current_species)


__all__ = ["SpeciesInfoPanel"]

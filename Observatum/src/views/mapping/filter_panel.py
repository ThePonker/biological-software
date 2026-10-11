"""
Map Filter Panel component for Observatum V2.

What to map (rank picker + several taxa as chips, selection_box.py), the data sources (tick
boxes, source_picker.py), then the filters: date range, quick date presets, vice-county,
recorder, site, Commercial project and the embargo switch; the Generate button and the list
of mapped squares.

Backlog item 4 (10 Oct 2026): the date boxes read 2020, 06/2020, 01/06/2020 or ISO and say
when they can't (MAP3); the Vice County list is one entry per VC and filters (MAP8); Quick
Select runs to the current year (MAP13); recorder and site filters; Display Style and Period
moved above the map (display_bar.py).

Round 2 (10 Oct evening): data sources as tick boxes (L8); the date error goes as soon as the
dates are put right or emptied (L9); one Clear all for the whole panel (L33); the panel
follows the width the tab's divider gives it and never scrolls sideways (L11, L30: its left
edge was clipped in full screen); "Include 2 km (tetrad) grid refs" (decision 10).
"""
from datetime import date
from typing import List, Optional, Tuple

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QCompleter, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout,
                               QWidget)

from shared.import_core import date_bounds
from ...core.config import TabColors
from ...services.map_selection import MapFilters, distinct_values, vc_choices
from ...themes import theme
from ..components.filter_styles import get_clear_button_style
from .selection_box import MapSelectionBox
from .source_picker import MapSourcePicker
from .square_list import MapSquareList

TETRAD_SETTING = "mapping/include_tetrad_refs"     # decision 10: on by default (the maps already showed them since 9 Oct)


def quick_presets(today: Optional[date] = None) -> List[Tuple[str, str, str]]:
    """[(button text, from, to)]: this year, the two before, the last five years, all (MAP13)."""
    y = (today or date.today()).year
    return [(str(y), str(y), str(y)), (str(y - 1), str(y - 1), str(y - 1)),
            (str(y - 2), str(y - 2), str(y - 2)),
            (f"{y - 5}–{str(y)[2:]}", str(y - 5), str(y)), ("All", "", "")]


def include_tetrads() -> bool:
    """The saved "Include 2 km (tetrad) grid refs" choice (default on)."""
    try:
        return QSettings().value(TETRAD_SETTING, True, type=bool)
    except Exception:
        return False


class MapFilterPanel(QFrame):
    """Side panel: what to map, and the filters."""

    selection_changed = Signal(list)
    sources_changed = Signal(list)
    generate_requested = Signal()
    cleared = Signal()             # Clear all: everything back to the start, in one go
    tetrads_changed = Signal(bool)
    square_clicked = Signal(str)   # a row in the grid-square list (H4)

    MIN_WIDTH = 310                # the divider can't squeeze it below this (the source boxes)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accent = TabColors.MAPPING
        self._accent_light = TabColors.MAPPING_LIGHT
        self._accent_dark = TabColors.MAPPING_DARK
        self._setup_ui()

    # ---------------------------------------------------------------- layout
    def _label(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {theme().get('text_secondary')};")
        return lab

    def _setup_ui(self):
        t = theme()
        self.setMinimumWidth(self.MIN_WIDTH)
        self.setObjectName("mapFilterPanel")       # the border is the panel's, not every label's
        self.setStyleSheet(f"QFrame#mapFilterPanel {{ background-color: {t.get('surface')}; "
                           f"border-right: 1px solid {t.get('border')}; }}")
        self.scroll = scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        # L30: the contents take the viewport's width, never more. (A minimum width wider than
        # the panel let it scroll sideways, e.g. when a box got the focus: the left edge was
        # cut off -- "ap", "ice County".) Height still scrolls rather than squashing.
        container.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        head = QHBoxLayout()
        title = QLabel("MAP FILTERS")
        title.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: 11px; letter-spacing: 1px;")
        head.addWidget(title)
        head.addStretch()
        self.clear_all_btn = QPushButton("Clear all")
        self.clear_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_all_btn.setToolTip("Taxa, data sources, dates, vice-county, recorder, site, "
                                      "project and the embargo box back to the start")
        self.clear_all_btn.setStyleSheet(get_clear_button_style())
        self.clear_all_btn.clicked.connect(self.clear_all)
        head.addWidget(self.clear_all_btn)
        layout.addLayout(head)

        self.selection_box = MapSelectionBox()
        self.selection_box.selection_changed.connect(self.selection_changed.emit)
        layout.addWidget(self.selection_box)

        self.source_picker = MapSourcePicker()
        self.source_picker.sources_changed.connect(self._on_sources)
        layout.addWidget(self.source_picker)

        self._setup_dates(layout)
        self._setup_place_and_people(layout)
        self._setup_commercial(layout)
        self._setup_generate_button(layout)
        self.square_list = MapSquareList()
        self.square_list.square_clicked.connect(self.square_clicked.emit)
        layout.addWidget(self.square_list)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _setup_dates(self, layout: QVBoxLayout):
        t = theme()
        group = QVBoxLayout()
        group.setSpacing(4)
        group.addWidget(self._label("Date Range"))
        row = QHBoxLayout()
        self.date_from = QLineEdit()
        self.date_from.setPlaceholderText("From")
        self.date_to = QLineEdit()
        self.date_to.setPlaceholderText("To")
        for box in (self.date_from, self.date_to):
            box.setMinimumHeight(28)
            box.setClearButtonEnabled(True)
            box.setToolTip("A year (2020), a month (06/2020) or a day (01/06/2020 or 2020-06-01)")
            box.returnPressed.connect(self.generate_requested.emit)
            box.textChanged.connect(self._refresh_date_error)
            row.addWidget(box)
        group.addLayout(row)
        self.date_error = QLabel("")
        self.date_error.setWordWrap(True)
        self.date_error.setStyleSheet(f"color: {t.get('error')}; font-size: 11px;")
        self.date_error.hide()
        group.addWidget(self.date_error)

        group.addWidget(self._label("Quick Select"))
        presets = QHBoxLayout()
        presets.setSpacing(4)
        self.preset_buttons = []
        for text, d_from, d_to in quick_presets():
            btn = QPushButton(text)
            btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 4px 6px;
                    border: 1px solid {t.get('border')};
                    border-radius: {t.get('radius_sm')};
                    font-size: 11px;
                }}
                QPushButton:hover {{ background-color: {t.get('hover')}; }}
            """)
            btn.clicked.connect(lambda _c=False, a=d_from, b=d_to: self._on_date_preset(a, b))
            presets.addWidget(btn)
            self.preset_buttons.append(btn)
        group.addLayout(presets)
        layout.addLayout(group)

    @staticmethod
    def _narrow(combo: QComboBox):
        """A combo as wide as the panel lets it be, not as wide as its longest entry (L30)."""
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(10)
        combo.setMinimumHeight(28)

    def _setup_place_and_people(self, layout: QVBoxLayout):
        group = QVBoxLayout()
        group.setSpacing(4)
        group.addWidget(self._label("Vice County"))
        self.vc_combo = QComboBox()
        self._narrow(self.vc_combo)
        self._populate_vc_combo()
        group.addWidget(self.vc_combo)

        group.addWidget(self._label("Recorder / collector"))
        self.recorder_edit = self._completing_edit("Part of a name, e.g. Heeney", "recorder")
        group.addWidget(self.recorder_edit)
        group.addWidget(self._label("Site"))
        self.site_edit = self._completing_edit("Part of a site name", "site")
        group.addWidget(self.site_edit)
        layout.addLayout(group)

    def _completing_edit(self, placeholder: str, kind: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setMinimumHeight(28)
        edit.setPlaceholderText(placeholder)
        edit.setClearButtonEnabled(True)
        edit.setToolTip("Records whose value contains this text (any case)")
        try:
            comp = QCompleter(distinct_values(kind), edit)
            comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            comp.setFilterMode(Qt.MatchFlag.MatchContains)
            edit.setCompleter(comp)
        except Exception as e:
            print(f"[FilterPanel] {kind} list not loaded: {e}")
        edit.returnPressed.connect(self.generate_requested.emit)
        return edit

    def _populate_vc_combo(self):
        """One entry per vice-county number held by the records, named from vc_lookup (MAP8)."""
        self.vc_combo.clear()
        self.vc_combo.addItem("All vice-counties", None)
        try:
            for num, text in vc_choices():
                self.vc_combo.addItem(text, num)
        except Exception as e:
            print(f"[FilterPanel] Error loading VCs: {e}")

    def _setup_commercial(self, layout: QVBoxLayout):
        group = QVBoxLayout()
        group.setSpacing(4)
        group.addWidget(self._label("Commercial project"))
        self.project_combo = QComboBox()
        self._narrow(self.project_combo)
        self.project_combo.addItem("All projects", "")
        try:
            for p in distinct_values("project"):
                self.project_combo.addItem(p, p)
        except Exception as e:
            print(f"[FilterPanel] projects not loaded: {e}")
        self.project_combo.setToolTip("Tick Commercial under Data sources to map one project")
        group.addWidget(self.project_combo)
        self.embargo_check = QCheckBox("Include embargoed records")
        self.embargo_check.setToolTip(
            "Commercial records under an active embargo are left off every map (and its atlas "
            "PNG) unless this is ticked. Ticked, the map's subtitle and the PNG say so.")
        group.addWidget(self.embargo_check)
        self.tetrad_check = QCheckBox("Include 2 km (tetrad) grid refs")
        self.tetrad_check.setToolTip(
            "Records with a 2 km tetrad grid ref (e.g. SP46Q; Recording Scheme only) are mapped "
            "on hectad and tetrad maps, never on 1 km maps. Off: they are left off and the map "
            "says how many. Remembered.")
        self.tetrad_check.setStyleSheet(f"color: {theme().get('text_secondary')}; font-size: 11px;")
        self.tetrad_check.setChecked(include_tetrads())
        self.tetrad_check.toggled.connect(self._on_tetrads)
        group.addWidget(self.tetrad_check)
        layout.addLayout(group)
        self._on_sources(self.source_picker.sources(), emit=False)

    def _on_sources(self, sources: list, emit: bool = True):
        """The project list applies to Commercial; the embargo box to Commercial and the
        Collection (a specimen whose observation is embargoed is held back with it)."""
        self.project_combo.setEnabled("commercial" in sources)
        self.embargo_check.setEnabled(bool({"commercial", "collection"} & set(sources)))
        if emit:
            self.sources_changed.emit(list(sources))

    def _on_tetrads(self, on: bool):
        try:
            QSettings().setValue(TETRAD_SETTING, bool(on))
        except Exception as e:
            print(f"[FilterPanel] tetrad setting not saved: {e}")
        self.tetrads_changed.emit(bool(on))

    def _setup_generate_button(self, layout: QVBoxLayout):
        t = theme()
        self.generate_btn = QPushButton("Generate Map")
        self.generate_btn.setMinimumHeight(36)
        self.generate_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._accent};
                color: white;
                border: none;
                border-radius: {t.get('radius_md')};
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {self._accent_dark}; }}
        """)
        self.generate_btn.clicked.connect(self.generate_requested.emit)
        layout.addWidget(self.generate_btn)

    # ---------------------------------------------------------------- values
    def _on_date_preset(self, d_from: str, d_to: str):
        self.date_from.setText(d_from)
        self.date_to.setText(d_to)
        self.generate_requested.emit()

    def selection(self) -> List[dict]:
        return self.selection_box.selection()

    def sources(self) -> List[str]:
        return self.source_picker.sources()

    def include_tetrads(self) -> bool:
        return self.tetrad_check.isChecked()

    def clear_all(self):
        """L33: taxa, sources, dates, vice-county, recorder, site, project and the embargo box
        back to the start in one go; then one `cleared` (no signal per box). The tetrad
        choice is a setting, not a filter: it stays."""
        widgets = (self.selection_box, self.source_picker, self.date_from, self.date_to,
                   self.vc_combo, self.recorder_edit, self.site_edit, self.project_combo,
                   self.embargo_check)
        for w in widgets:
            w.blockSignals(True)
        try:
            self.selection_box.clear(emit=False)
            self.source_picker.reset(emit=False)
            for box in (self.date_from, self.date_to, self.recorder_edit, self.site_edit):
                box.clear()
            self.vc_combo.setCurrentIndex(0)
            self.project_combo.setCurrentIndex(0)
            self.embargo_check.setChecked(False)
        finally:
            for w in widgets:
                w.blockSignals(False)
        self._on_sources(self.source_picker.sources(), emit=False)
        self.date_error.clear()
        self.date_error.hide()
        self.cleared.emit()

    def _date_problems(self):
        """([what is wrong], {'From': iso or None, 'To': iso or None})."""
        bad = []
        bounds = {}
        for name, box, end in (("From", self.date_from, False), ("To", self.date_to, True)):
            text = box.text().strip()
            if not text:
                bounds[name] = None
                continue
            b = date_bounds(text)
            if b is None:
                bad.append(f"{name} date '{text}' not understood: use 2020, 06/2020 or 01/06/2020.")
                bounds[name] = None
            else:
                bounds[name] = b[1] if end else b[0]
        if bounds["From"] and bounds["To"] and bounds["From"] > bounds["To"]:
            bad.append("The From date is after the To date.")
        return bad, bounds

    def _refresh_date_error(self, *_a):
        """L9: as the dates are edited, an error already shown is updated, and goes as soon
        as the dates are right or empty (new errors still wait for Generate / Enter)."""
        if not self.date_error.text():
            return
        bad, _b = self._date_problems()
        self.date_error.setText(" ".join(bad))
        self.date_error.setVisible(bool(bad))

    def filters(self) -> Tuple[Optional[MapFilters], str]:
        """(MapFilters, '') or (None, what is wrong) -- an unreadable date stops the map
        rather than being ignored (MAP3)."""
        bad, bounds = self._date_problems()
        self.date_error.setText(" ".join(bad))
        self.date_error.setVisible(bool(bad))
        if bad:
            return None, " ".join(bad)
        return MapFilters(date_from=bounds["From"], date_to=bounds["To"],
                          vc=self.vc_combo.currentData(),
                          recorder=self.recorder_edit.text(), site=self.site_edit.text(),
                          project=(self.project_combo.currentData() or "")
                          if self.project_combo.isEnabled() else "",
                          include_embargoed=self.embargo_check.isEnabled()
                          and self.embargo_check.isChecked()), ""

    def set_chip_counts(self, counts):
        self.selection_box.set_counts(counts)

    def set_grid_squares(self, squares: list):
        """The list of mapped squares under the Generate button (square_list.py)."""
        self.square_list.set_squares(squares)

"""
Map Filter Panel component for Observatum V2.

What to map (rank picker + several taxa as chips, selection_box.py), then the filters:
date range, quick date presets, vice-county, recorder, site, Commercial project and the
embargo switch; the Generate button and the list of mapped squares.

Backlog item 4 (10 Oct 2026): the date boxes read 2020, 06/2020, 01/06/2020 or ISO and say
when they can't (MAP3); the Vice County list is one entry per VC and filters (MAP8); Quick
Select runs to the current year (MAP13); recorder and site filters; Display Style and Period
moved above the map (display_bar.py).
"""
from datetime import date
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QCompleter, QFrame, QHBoxLayout, QLabel,
                               QLayout, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from shared.import_core import date_bounds
from ...core.config import TabColors
from ...services.map_selection import MapFilters, distinct_values, vc_choices
from ...themes import theme
from .selection_box import MapSelectionBox


def quick_presets(today: Optional[date] = None) -> List[Tuple[str, str, str]]:
    """[(button text, from, to)]: this year, the two before, the last five years, all (MAP13)."""
    y = (today or date.today()).year
    return [(str(y), str(y), str(y)), (str(y - 1), str(y - 1), str(y - 1)),
            (str(y - 2), str(y - 2), str(y - 2)),
            (f"{y - 5}–{str(y)[2:]}", str(y - 5), str(y)), ("All", "", "")]


class MapFilterPanel(QFrame):
    """Side panel: what to map, and the filters."""

    selection_changed = Signal(list)
    generate_requested = Signal()
    square_clicked = Signal(str)   # a row in the grid-square list (H4)

    GRID_LIST_MAX = 200            # rows shown; the rest are summarised in one line

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
        self.setFixedWidth(300)
        self.setObjectName("mapFilterPanel")       # the border is the panel's, not every label's
        self.setStyleSheet(f"QFrame#mapFilterPanel {{ background-color: {t.get('surface')}; "
                           f"border-right: 1px solid {t.get('border')}; }}")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        layout = QVBoxLayout(container)
        # scroll rather than squash the chips and the square list when the panel is full
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        title = QLabel("MAP FILTERS")
        title.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: 11px; letter-spacing: 1px;")
        layout.addWidget(title)

        self.selection_box = MapSelectionBox()
        self.selection_box.selection_changed.connect(self.selection_changed.emit)
        layout.addWidget(self.selection_box)

        self._setup_dates(layout)
        self._setup_place_and_people(layout)
        self._setup_commercial(layout)
        self._setup_generate_button(layout)
        self._setup_grid_list(layout)
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
            box.setToolTip("A year (2020), a month (06/2020) or a day (01/06/2020 or 2020-06-01)")
            box.returnPressed.connect(self.generate_requested.emit)
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

    def _setup_place_and_people(self, layout: QVBoxLayout):
        group = QVBoxLayout()
        group.setSpacing(4)
        group.addWidget(self._label("Vice County"))
        self.vc_combo = QComboBox()
        self.vc_combo.setMinimumHeight(28)
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
        self.project_combo.setMinimumHeight(28)
        self.project_combo.addItem("All projects", "")
        try:
            for p in distinct_values("project"):
                self.project_combo.addItem(p, p)
        except Exception as e:
            print(f"[FilterPanel] projects not loaded: {e}")
        self.project_combo.setToolTip("Choose Data: Commercial records to map one project")
        group.addWidget(self.project_combo)
        self.embargo_check = QCheckBox("Include embargoed records")
        self.embargo_check.setToolTip(
            "Commercial records under an active embargo are left off every map (and its atlas "
            "PNG) unless this is ticked.")
        group.addWidget(self.embargo_check)
        layout.addLayout(group)
        self.set_source("personal")

    def set_source(self, source: str):
        """The toolbar's data source: the project list applies to Commercial only."""
        self.project_combo.setEnabled(source == "commercial")
        self.embargo_check.setEnabled(source in ("commercial", "collection", "all"))

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

    def _setup_grid_list(self, layout: QVBoxLayout):
        t = theme()
        group = QVBoxLayout()
        group.setSpacing(8)
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {t.get('separator')};")
        group.addWidget(sep)
        self.grid_title = QLabel("GRID SQUARES (0)")
        self.grid_title.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: 11px; letter-spacing: 1px;")
        group.addWidget(self.grid_title)
        self.grid_list = QVBoxLayout()
        self.grid_list.setSpacing(4)
        group.addLayout(self.grid_list)
        layout.addLayout(group)

    # ---------------------------------------------------------------- values
    def _on_date_preset(self, d_from: str, d_to: str):
        self.date_from.setText(d_from)
        self.date_to.setText(d_to)
        self.generate_requested.emit()

    def selection(self) -> List[dict]:
        return self.selection_box.selection()

    def filters(self) -> Tuple[Optional[MapFilters], str]:
        """(MapFilters, '') or (None, what is wrong) -- an unreadable date stops the map
        rather than being ignored (MAP3)."""
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
        """Update the grid squares list (most records first). Click a row to see its records."""
        t = theme()
        while self.grid_list.count():
            item = self.grid_list.takeAt(0)
            if item.widget():
                item.widget().hide()          # gone now, not at the next event loop
                item.widget().deleteLater()
        self.grid_title.setText(f"GRID SQUARES ({len(squares):,})")
        ordered = sorted(squares, key=lambda sq: (-sq['count'], sq['grid']))
        for sq in ordered[:self.GRID_LIST_MAX]:
            row = QHBoxLayout()
            row.setContentsMargins(4, 2, 4, 2)
            grid_label = QLabel(sq['grid'])
            grid_label.setStyleSheet(f"font-family: monospace; color: {t.get('text_heading')};")
            row.addWidget(grid_label)
            row.addStretch()
            n, k = sq['count'], sq.get('species', 0)
            count_label = QLabel(f"{n:,} record{'s' if n != 1 else ''} · {k} sp.")
            count_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px;")
            row.addWidget(count_label)
            container = QFrame()
            container.setLayout(row)
            container.setCursor(Qt.CursorShape.PointingHandCursor)
            container.setToolTip((f"{sq['taxa']}: " if sq.get('taxa') else "")
                                + "Show the records in this square")
            container.setStyleSheet(f"QFrame:hover {{ background-color: {self._accent_light}; }}")
            container.mousePressEvent = lambda e, g=sq['grid']: self.square_clicked.emit(g)
            self.grid_list.addWidget(container)
        if len(ordered) > self.GRID_LIST_MAX:
            more = QLabel(f"… and {len(ordered) - self.GRID_LIST_MAX:,} more "
                          f"(click them on the map)")
            more.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px;")
            self.grid_list.addWidget(more)

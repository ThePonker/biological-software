"""Drawer in hand -- the specimen list and the "Show" choice (split out of
drawer_assign_dialog.py, 13 Oct 2026, Round 10 C: F74, F75).

SpecimenList is the middle list: a tick column first, drawn by the suite's TickDelegate in
the Insect Collection gold (the tree's own check boxes drew nothing on Wil's PC when
ticked), then Species, Date, Site, Sex, Drawer now; the same row look as the Insect
Collection table (24 px rows, alternate shading, gold highlight). Genus headings are plain
rows across the list with no tick box.

ShowChoice replaces the two check boxes "Not yet in a drawer" / "Already in a drawer" with
one row of three radio buttons: Not yet in a drawer (the default), All specimens, Only this
drawer. Whatever is chosen, the specimens recorded in the drawer in hand are always shown.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QRadioButton, QVBoxLayout, QStyledItemDelegate, QTreeWidget,
    QTreeWidgetItem, QWidget,
)

from shared.tick_mark import radio_qss

from ...themes import theme
from ..components import tick_column

COL_TICK, COL_SPECIES, COL_DATE, COL_SITE, COL_SEX, COL_NOW = range(6)
HEADERS = ["", "Species", "Date", "Site", "Sex", "Drawer now"]
ROLE_ID = Qt.ItemDataRole.UserRole          # the specimen id, on the tick column
ACCENT = "accent_collection"

FREE, ALL, THIS = "free", "all", "this"
CHOICES = [(FREE, "Not yet in a drawer", "Specimens not recorded in any drawer"),
           (ALL, "All specimens", "Every specimen, including those in other drawers"),
           (THIS, "Only this drawer", "Just the specimens recorded in the drawer in hand")]


class _Tick(tick_column.TickDelegate):
    """The suite's tick box on specimen rows; a genus heading (no id) is plain text."""

    def paint(self, painter, option, index):
        if index.data(ROLE_ID) is None:
            QStyledItemDelegate.paint(self, painter, option, index)
            return
        super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):
        if index.data(ROLE_ID) is None:
            return False
        return super().editorEvent(event, model, option, index)


class SpecimenList(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        t = theme()
        self.setColumnCount(len(HEADERS))
        self.setHeaderLabels(HEADERS)
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setAlternatingRowColors(True)
        self.setIndentation(0)
        self.tick_delegate = _Tick(self, ACCENT)
        self.setItemDelegateForColumn(COL_TICK, self.tick_delegate)
        h = self.header()
        h.setSectionResizeMode(COL_TICK, QHeaderView.ResizeMode.Fixed)
        h.resizeSection(COL_TICK, 30)
        h.setSectionResizeMode(COL_SPECIES, QHeaderView.ResizeMode.Stretch)
        self._head_font = QFont()
        self._head_font.setBold(True)
        self._head_font.setItalic(True)
        self._head_fg = QBrush(QColor(t.get(f"{ACCENT}_dark")))
        self._head_bg = QBrush(QColor(t.get(f"{ACCENT}_light")))
        self.setStyleSheet(f"""
            QTreeView {{
                border: 1px solid {t.get('border')};
                background-color: {t.get('surface')};
                alternate-background-color: {t.get('surface_alt')};
                outline: none;
            }}
            QTreeView::item {{ height: 24px; padding: 0 6px; border: none; }}
            QTreeView::item:hover {{ background-color: {t.get(f'{ACCENT}_light')}; }}
            QTreeView::item:selected {{
                background-color: {t.get(f'{ACCENT}_light')};
                color: {t.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                padding: 6px;
                border: none;
                border-bottom: 1px solid {t.get('border')};
                font-weight: 600;
            }}
        """)

    def add_heading(self, genus: str) -> QTreeWidgetItem:
        h = QTreeWidgetItem([""] * len(HEADERS))
        h.setText(COL_SPECIES, genus or "(no genus)")
        h.setFont(COL_SPECIES, self._head_font)
        h.setForeground(COL_SPECIES, self._head_fg)
        h.setFlags(Qt.ItemFlag.ItemIsEnabled)
        for c in range(len(HEADERS)):
            h.setBackground(c, self._head_bg)
        self.addTopLevelItem(h)
        return h

    def add_specimen(self, s: dict) -> QTreeWidgetItem:
        it = QTreeWidgetItem(["", s["species_name"] or "", s.get("date_collected") or "",
                              s.get("site_name") or "", s.get("sex") or "", ""])
        f = it.font(COL_SPECIES)
        f.setItalic(True)
        it.setFont(COL_SPECIES, f)
        it.setData(COL_TICK, ROLE_ID, s["id"])
        it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsUserCheckable)
        self.addTopLevelItem(it)
        return it

    def fit_columns(self):
        for c in range(COL_DATE, len(HEADERS)):
            self.resizeColumnToContents(c)

    def specimen_ids(self) -> list:
        """Ids of the specimen rows, in list order (headings skipped)."""
        out = []
        for i in range(self.topLevelItemCount()):
            sid = self.topLevelItem(i).data(COL_TICK, ROLE_ID)
            if sid is not None:
                out.append(sid)
        return out


class ShowChoice(QWidget):
    """'Show:' and three radio buttons; value() is FREE, ALL or THIS."""
    changed = Signal(str)

    def __init__(self, parent=None, vertical: bool = False):
        super().__init__(parent)
        t = theme()
        self.setStyleSheet(f"QRadioButton {{ color: {t.get('text_primary')}; spacing: 6px; }}"
                           + radio_qss(fill=t.get(ACCENT), mark=t.get("button_primary_text"),
                                       border=t.get("border_strong"), background=t.get("surface")))
        # Vertical in the left pane keeps Drawer in hand within a laptop's width (R10 fix)
        lay = QVBoxLayout(self) if vertical else QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(4 if vertical else 10)
        lay.addWidget(QLabel("Show:"))
        self._buttons = {}
        for value, label, tip in CHOICES:
            b = QRadioButton(label)
            b.setToolTip(f"{tip}. The specimens in the drawer in hand always show.")
            b.toggled.connect(lambda on, v=value: on and self.changed.emit(v))
            self._buttons[value] = b
            lay.addWidget(b)
        if not vertical:
            lay.addStretch(1)
        self._buttons[FREE].setChecked(True)

    def value(self) -> str:
        return next(v for v, b in self._buttons.items() if b.isChecked())

    def set(self, value: str):
        self._buttons[value].setChecked(True)

    def shows(self, placed: bool) -> bool:
        """Whether a specimen outside the drawer in hand is shown under the choice."""
        v = self.value()
        return v == ALL or (v == FREE and not placed)

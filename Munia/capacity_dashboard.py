"""Capacity dashboard — field days Apr-Mar grid, micro/report side-by-side."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QLabel, QFrame, QHeaderView, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QBrush
from Munia.theme import (
    STONE_LIGHT, STONE_BORDER, BODY_FAMILY, HEADING_FAMILY,
    TEXT_DARK, TEXT_MID, TEXT_LIGHT, MOSS_GREEN, DUSTY_PURPLE,
    AMBER, FADED_CRIMSON, WARM_GRAY_LIGHT
)
from Munia import munia_data as db
from Munia.munia_data import BIZ_MONTHS, BIZ_LABELS

FIELD_ROWS = ["Budget", "Quoted", "Accepted", "Remaining"]
TABLE_STYLE = (
    f"QTableWidget {{ background: {STONE_LIGHT}; border: 1px solid {STONE_BORDER}; "
    f'gridline-color: {STONE_BORDER}; font-family: "{BODY_FAMILY}"; font-size: 12px; }}'
    f"QTableWidget::item {{ padding: 2px 4px; }}"
    f"QHeaderView::section {{ background: {WARM_GRAY_LIGHT}; "
    f'font-family: "{BODY_FAMILY}"; font-size: 11px; font-weight: 600; '
    f"color: {TEXT_DARK}; border: none; "
    f"border-bottom: 1px solid {STONE_BORDER}; padding: 4px; }}")
# Season tints by display column (1-indexed: col 1=Apr .. col 12=Mar)
SEASON_TINT = {}
for _c in (1, 2, 3, 4):     SEASON_TINT[_c] = "#edf5ef"   # Apr-Jul green
for _c in (5, 6, 7):        SEASON_TINT[_c] = "#eee9f3"   # Aug-Oct purple
for _c in (8, 9):           SEASON_TINT[_c] = "#f7f0e0"   # Nov-Dec amber


class CapacityDashboard(QWidget):
    """Capacity overview — field monthly grid (Apr-Mar) + micro/report."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        field_lbl = QLabel("Field Days")
        field_lbl.setStyleSheet(
            f'font-family: "{HEADING_FAMILY}"; font-size: 14px; '
            f"font-weight: bold; color: {MOSS_GREEN}; margin: 0; padding: 0;")
        layout.addWidget(field_lbl)
        self.field_table = QTableWidget(4, 14)
        labels = [""] + BIZ_LABELS + ["Total"]
        self.field_table.setHorizontalHeaderLabels(labels)
        self.field_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.field_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.field_table.setFocusPolicy(Qt.NoFocus)
        self.field_table.verticalHeader().setVisible(False)
        self.field_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.field_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        hdr = self.field_table.horizontalHeader()
        self.field_table.setColumnWidth(0, 95)
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        for i in range(1, 14):
            hdr.setSectionResizeMode(i, QHeaderView.Stretch)
        for row, label in enumerate(FIELD_ROWS):
            item = QTableWidgetItem(f"  {label}")
            item.setFlags(Qt.ItemIsEnabled)
            is_budget = row == 0
            item.setFont(QFont(BODY_FAMILY, 10, QFont.Bold if is_budget else QFont.Normal))
            item.setForeground(QBrush(QColor(MOSS_GREEN if is_budget else TEXT_MID)))
            self.field_table.setItem(row, 0, item)
        self.field_table.setFixedHeight(164)
        self.field_table.setStyleSheet(TABLE_STYLE)
        layout.addWidget(self.field_table)
        layout.addSpacing(8)
        mr_row = QHBoxLayout()
        mr_row.setSpacing(12)
        micro_col = QVBoxLayout()
        micro_col.setSpacing(2)
        micro_lbl = QLabel("Microscope Days")
        micro_lbl.setStyleSheet(
            f'font-family: "{HEADING_FAMILY}"; font-size: 14px; '
            f"font-weight: bold; color: {DUSTY_PURPLE}; margin: 0; padding: 0;")
        micro_col.addWidget(micro_lbl)
        self.micro_row = _CompactCard(DUSTY_PURPLE)
        micro_col.addWidget(self.micro_row)
        mr_row.addLayout(micro_col, 1)
        report_col = QVBoxLayout()
        report_col.setSpacing(2)
        report_lbl = QLabel("Report Days")
        report_lbl.setStyleSheet(
            f'font-family: "{HEADING_FAMILY}"; font-size: 14px; '
            f"font-weight: bold; color: {AMBER}; margin: 0; padding: 0;")
        report_col.addWidget(report_lbl)
        self.report_row = _CompactCard(AMBER)
        report_col.addWidget(self.report_row)
        mr_row.addLayout(report_col, 1)
        layout.addLayout(mr_row)

    def refresh(self, conn, year: int):
        field_cap = db.get_field_capacity(conn, year)
        cap_map = {c["month"]: c["field_budget"] for c in field_cap}
        f_quoted = db.get_field_totals_by_month(conn, year, ("quoted",))
        f_accepted = db.get_field_totals_by_month(conn, year, ("accepted",))
        totals = [0.0, 0.0, 0.0, 0.0]
        for col_idx, cal_month in enumerate(BIZ_MONTHS):
            display_col = col_idx + 1  # +1 for label column
            b = cap_map.get(cal_month, 0)
            q = f_quoted.get(cal_month, 0)
            a = f_accepted.get(cal_month, 0)
            rem = b - q - a
            vals = [b, q, a, rem]
            for si in range(4):
                totals[si] += vals[si]
            for si, val in enumerate(vals):
                self._set_field_cell(si, display_col, val, si)
        for si, val in enumerate(totals):
            self._set_field_cell(si, 13, val, si, bold=True)
        ann = db.get_annual_capacity(conn, year)
        q_ann = db.get_annual_totals(conn, year, ("quoted",))
        a_ann = db.get_annual_totals(conn, year, ("accepted",))
        self.micro_row.refresh(ann.get("micro_budget", 0),
                               q_ann.get("micro", 0), a_ann.get("micro", 0))
        self.report_row.refresh(ann.get("report_budget", 0),
                                q_ann.get("report", 0), a_ann.get("report", 0))

    def _set_field_cell(self, row, col, value, sub_idx, bold=False):
        if value == 0 and sub_idx != 3:
            text, fg = "\u2014", QColor(TEXT_LIGHT)
        else:
            text = f"{value:g}"
            if sub_idx == 0:
                fg = QColor(MOSS_GREEN)
            elif sub_idx == 3:
                fg = QColor(FADED_CRIMSON) if value < 0 else QColor(TEXT_DARK)
            else:
                fg = QColor(TEXT_MID)
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setFlags(Qt.ItemIsEnabled)
        item.setForeground(QBrush(fg))
        font_wt = QFont.Bold if (bold or sub_idx == 0) else QFont.Normal
        item.setFont(QFont(BODY_FAMILY, 10, font_wt))
        if sub_idx == 3 and value < 0:
            item.setBackground(QBrush(QColor("#fef2f2")))
        elif col in SEASON_TINT:
            item.setBackground(QBrush(QColor(SEASON_TINT[col])))
        self.field_table.setItem(row, col, item)


class _CompactCard(QFrame):
    """Single-line card: Budget: X  Quoted: X  Accepted: X  Remaining: X"""
    def __init__(self, colour: str, parent=None):
        super().__init__(parent)
        self._colour = colour
        self.setFixedHeight(32)
        self.setStyleSheet(
            f"QFrame {{ background: {STONE_LIGHT}; "
            f"border: 1px solid {STONE_BORDER}; border-radius: 4px; }}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(16)
        self.budget_lbl = self._make("Budget: 0")
        self.quoted_lbl = self._make("Quoted: 0")
        self.accepted_lbl = self._make("Accepted: 0")
        self.remain_lbl = self._make("Remaining: 0", bold=True)
        for w in (self.budget_lbl, self.quoted_lbl, self.accepted_lbl, self.remain_lbl):
            layout.addWidget(w)
        layout.addStretch()
    def _make(self, text, bold=False):
        lbl = QLabel(text)
        wt = "bold" if bold else "normal"
        lbl.setStyleSheet(
            f'font-family: "{BODY_FAMILY}"; font-size: 11px; '
            f"font-weight: {wt}; color: {TEXT_MID};")
        return lbl
    def refresh(self, budget, quoted, accepted):
        remaining = budget - quoted - accepted
        self.budget_lbl.setText(f"Budget: {budget:g}")
        self.quoted_lbl.setText(f"Quoted: {quoted:g}")
        self.accepted_lbl.setText(f"Accepted: {accepted:g}")
        col = FADED_CRIMSON if remaining < 0 else TEXT_DARK
        self.remain_lbl.setText(f"Remaining: {remaining:g}")
        self.remain_lbl.setStyleSheet(
            f'font-family: "{BODY_FAMILY}"; font-size: 11px; '
            f"font-weight: bold; color: {col};")

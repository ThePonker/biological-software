"""Examen -- a small read-only table for a (heads, rows, notes) figure block.

Used on screen for the taxonomic summary (E8b) and the compartment table (E6): the
same rows the workbook and the reports lay out, so the screen shows what the export
will say.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QFrame, QHeaderView, QLabel, QTableWidget, QTableWidgetItem,
                               QVBoxLayout)

BG = "#f5f5f4"; SURFACE = "#ffffff"; TEXT_HEADING = "#4b5563"; TEXT_MUTED = "#9ca3af"
BORDER = "#d1d5db"; SEPARATOR = "#e5e7eb"; RED_STATUS = "#a63d40"

TABLE_STYLE = (
    "QTableWidget { border: 1px solid " + BORDER + "; gridline-color: " + SEPARATOR
    + "; font-size: 11px; background: " + SURFACE + "; }"
    "QHeaderView::section { background: " + BG + "; border: none; border-bottom: 2px solid "
    + BORDER + "; padding: 4px; font-weight: bold; font-size: 11px; color: " + TEXT_HEADING + "; }")


def figure_block(title, table, bold_rows=(), flag_col=None, head_tips=None):
    """A framed title + table + notes. table: (heads, rows, notes).

    bold_rows: first-cell values whose row is bold (totals). flag_col: column whose
    non-empty text marks a row to show in the warning colour. head_tips: {heading: tooltip}.
    """
    heads, rows, notes = table
    frame = QFrame()
    frame.setStyleSheet("QFrame { background: " + SURFACE + "; border: 1px solid "
                        + BORDER + "; border-radius: 6px; }")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(12, 10, 12, 10)
    lay.setSpacing(6)

    t = QLabel(title)
    t.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
    t.setStyleSheet("color: " + TEXT_HEADING + "; border: none;")
    lay.addWidget(t)

    tbl = QTableWidget(len(rows), len(heads))
    tbl.setHorizontalHeaderLabels(heads)
    tbl.verticalHeader().setVisible(False)
    tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tbl.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
    tbl.setStyleSheet(TABLE_STYLE)
    bold = QFont("Segoe UI", 9, QFont.Weight.Bold)
    for i, row in enumerate(rows):
        flagged = flag_col is not None and flag_col < len(row) and row[flag_col]
        for j in range(len(heads)):
            v = row[j] if j < len(row) else ""
            it = QTableWidgetItem("" if v is None else str(v))
            if j > 0 and (isinstance(v, (int, float)) or (isinstance(v, str) and v.endswith("%"))):
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if row and row[0] in bold_rows:
                it.setFont(bold)
            if flagged:
                it.setForeground(QColor(RED_STATUS))
            tbl.setItem(i, j, it)
    for j, h in enumerate(heads):
        if head_tips and h in head_tips:
            tbl.horizontalHeaderItem(j).setToolTip(head_tips[h])
    tbl.resizeColumnsToContents()
    tbl.horizontalHeader().setSectionResizeMode(len(heads) - 1, QHeaderView.ResizeMode.Stretch)
    # Fit the rows: no inner scroll bar for a table of this size.
    h = tbl.horizontalHeader().sizeHint().height() + sum(tbl.rowHeight(i) for i in range(len(rows))) + 4
    tbl.setFixedHeight(h)
    lay.addWidget(tbl)

    for n in notes:
        lbl = QLabel(n)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: " + TEXT_MUTED + "; font-size: 10px; font-style: italic; border: none;")
        lay.addWidget(lbl)
    return frame

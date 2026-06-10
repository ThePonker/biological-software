"""Projects panel — project pipeline table with multi-year support."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont
from Munia.theme import (
    STONE_LIGHT, STONE_BORDER, BODY_FAMILY,
    TEXT_DARK, TEXT_MID, TEXT_LIGHT, WARM_GRAY_LIGHT,
    MOSS_GREEN, DUSTY_PURPLE, AMBER, FADED_CRIMSON, WARM_GRAY
)
from Munia import munia_data as db

class _SortItem(QTableWidgetItem):
    """Table item that sorts by UserRole data instead of display text."""
    def __lt__(self, other):
        return (self.data(Qt.UserRole) or "") < (other.data(Qt.UserRole) or "")

COLUMNS = [
    ("Project", 130), ("Client", 90), ("Status", 80), ("Years", 60),
    ("Quote", 75), ("Field", 45), ("Micro", 45), ("Report", 45),
    ("ID Due", 80), ("Rpt Due", 80),
]
STATUS_COLOURS = {
    "quoted": QColor(DUSTY_PURPLE), "accepted": QColor(MOSS_GREEN),
    "complete": QColor(TEXT_LIGHT), "declined": QColor(FADED_CRIMSON),
    "no_response": QColor(WARM_GRAY),
}
STATUS_DISPLAY = {
    "quoted": "Quoted", "accepted": "Accepted", "complete": "Complete",
    "declined": "Declined", "no_response": "No Response",
}


class ProjectsPanel(QWidget):
    """Project table — click a row to load into the form."""

    project_selected = Signal(dict)
    add_requested = Signal()

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._projects: list[dict] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("Projects")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            f"QTableWidget {{ background: {STONE_LIGHT}; "
            f"border: 1px solid {STONE_BORDER}; gridline-color: {STONE_BORDER}; "
            f'font-family: "{BODY_FAMILY}"; font-size: 12px; color: {TEXT_DARK}; '
            f"selection-background-color: #c8bfdb; selection-color: {TEXT_DARK}; }}"
            f"QTableWidget::item {{ padding: 3px 5px; }}"
            f"QTableWidget::item:alternate {{ background: #f4f3f1; }}"
            f"QHeaderView::section {{ background: {WARM_GRAY_LIGHT}; "
            f'font-family: "{BODY_FAMILY}"; font-size: 11px; font-weight: 600; '
            f"color: {TEXT_DARK}; border: none; "
            f"border-bottom: 1px solid {STONE_BORDER}; padding: 4px; }}")
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for i, (_, w) in enumerate(COLUMNS):
            if i > 0:
                self.table.setColumnWidth(i, w)
        self.table.setSortingEnabled(True)
        self.table.clicked.connect(self._on_clicked)
        layout.addWidget(self.table, 1)

    def load(self, projects: list[dict], year: int = 0):
        self._projects = {p["id"]: p for p in projects}
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(projects))
        for row, p in enumerate(projects):
            name_item = QTableWidgetItem(p["project_name"])
            name_item.setData(Qt.UserRole, p["id"])
            self.table.setItem(row, 0, name_item)
            self._set(row, 1, p.get("client", ""))
            status = p.get("status", "quoted")
            si = QTableWidgetItem(STATUS_DISPLAY.get(status, status))
            si.setTextAlignment(Qt.AlignCenter)
            si.setForeground(QBrush(STATUS_COLOURS.get(status, QColor(TEXT_MID))))
            si.setFont(QFont(BODY_FAMILY, 10, QFont.Bold))
            self.table.setItem(row, 2, si)
            sy, ey = p.get("start_year", 0), p.get("end_year", 0)
            yr_text = str(sy) if sy == ey else f"{sy}\u2013{ey}"
            self._ctr(row, 3, yr_text)
            qv = p.get("quote_value", 0)
            self._ctr(row, 4, f"\u00a3{qv:,.0f}" if qv else "\u2014")
            ft = db.get_project_field_total(self._conn, p["id"])
            mt = db.get_project_micro_total(self._conn, p["id"])
            rt = db.get_project_report_total(self._conn, p["id"])
            self._ctr(row, 5, f"{ft:g}" if ft else "\u2014")
            self._ctr(row, 6, f"{mt:g}" if mt else "\u2014")
            self._ctr(row, 7, f"{rt:g}" if rt else "\u2014")
            ad = db.get_project_annual_days(self._conn, p["id"], year) if year else {}
            self._date_cell(row, 8, ad.get("id_deadline", ""))
            self._date_cell(row, 9, ad.get("report_deadline", ""))
        self.table.setSortingEnabled(True)

    def _set(self, r, c, text):
        self.table.setItem(r, c, QTableWidgetItem(text))

    def _ctr(self, r, c, text):
        i = QTableWidgetItem(text)
        i.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(r, c, i)

    def _date_cell(self, r, c, date_str):
        """Date cell — display dd/mm/yyyy, sort by ISO in UserRole."""
        if date_str and len(date_str) == 10:
            parts = date_str.split("-")
            display = f"{parts[2]}/{parts[1]}/{parts[0]}"
        else:
            display = "\u2014"
        i = _SortItem(display)
        i.setTextAlignment(Qt.AlignCenter)
        i.setData(Qt.UserRole, date_str if date_str else "9999-99-99")
        self.table.setItem(r, c, i)

    def _on_clicked(self, index):
        row = index.row()
        item = self.table.item(row, 0)
        if item:
            pid = item.data(Qt.UserRole)
            if pid in self._projects:
                self.project_selected.emit(self._projects[pid])

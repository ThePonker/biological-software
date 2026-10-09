"""Embedded project form — multi-year projects with Apr-Mar allocations."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QDoubleSpinBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QDateEdit, QHeaderView, QSizePolicy
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QFont, QColor, QBrush
from Munia.theme import (
    STONE_BORDER, BODY_FAMILY, HEADING_FAMILY,
    TEXT_DARK, TEXT_MID, MOSS_GREEN, DUSTY_PURPLE, AMBER, WARM_GRAY_LIGHT
)
from Munia import munia_data as db
from Munia.munia_data import BIZ_MONTHS, BIZ_LABELS

STATUSES = ["quoted", "accepted", "complete", "declined", "no_response"]
STATUS_DISPLAY = {
    "quoted": "Quoted", "accepted": "Accepted", "complete": "Complete",
    "declined": "Declined", "no_response": "No Response",
}

class ProjectForm(QWidget):
    saved = Signal()
    deleted = Signal(int)
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._view_year = db.current_biz_year()
        self._alloc_year = self._view_year
        self._editing_id: int | None = None
        self._alloc_cache: dict[int, dict] = {}
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self._build_ui()
        self.clear()
    def set_year(self, year: int):
        self._view_year = year
        self._alloc_year = year
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        hdr = QHBoxLayout()
        self._title = QLabel("New Project")
        self._title.setStyleSheet(
            f'font-family: "{HEADING_FAMILY}"; font-size: 14px; '
            f"font-weight: bold; color: {TEXT_DARK};")
        hdr.addWidget(self._title)
        hdr.addStretch()
        self.new_btn = QPushButton("New")
        self.new_btn.setObjectName("secondary")
        self.new_btn.clicked.connect(self.clear)
        hdr.addWidget(self.new_btn)
        layout.addLayout(hdr)
        r1 = QHBoxLayout()
        r1.setSpacing(8)
        r1.addWidget(self._lbl("Project:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Project name")
        r1.addWidget(self.name_edit, 2)
        r1.addWidget(self._lbl("Client:"))
        self.client_edit = QLineEdit()
        self.client_edit.setPlaceholderText("Client")
        r1.addWidget(self.client_edit, 1)
        layout.addLayout(r1)
        r2 = QHBoxLayout()
        r2.setSpacing(8)
        r2.addWidget(self._lbl("Status:"))
        self.status_combo = QComboBox()
        self.status_combo.setFixedWidth(100)
        for s in STATUSES:
            self.status_combo.addItem(STATUS_DISPLAY[s], s)
        r2.addWidget(self.status_combo)
        r2.addWidget(self._lbl("Quote:"))
        self.quote_spin = QDoubleSpinBox()
        self.quote_spin.setRange(0, 999999)
        self.quote_spin.setDecimals(2)
        self.quote_spin.setPrefix("\u00a3 ")
        self.quote_spin.setFixedWidth(120)
        r2.addWidget(self.quote_spin)
        r2.addWidget(self._lbl("From:"))
        self.start_year_spin = QSpinBox()
        self.start_year_spin.setRange(2020, 2040)
        self.start_year_spin.setFixedWidth(85)
        r2.addWidget(self.start_year_spin)
        self.start_suffix = QLabel(f"/ {self._view_year + 1}")
        self.start_suffix.setStyleSheet(f"font-size: 12px; color: {TEXT_MID};")
        r2.addWidget(self.start_suffix)
        r2.addWidget(self._lbl("To:"))
        self.end_year_spin = QSpinBox()
        self.end_year_spin.setRange(2020, 2040)
        self.end_year_spin.setFixedWidth(85)
        r2.addWidget(self.end_year_spin)
        self.end_suffix = QLabel(f"/ {self._view_year + 1}")
        self.end_suffix.setStyleSheet(f"font-size: 12px; color: {TEXT_MID};")
        r2.addWidget(self.end_suffix)
        self.start_year_spin.valueChanged.connect(self._on_year_spins_changed)
        self.end_year_spin.valueChanged.connect(self._on_year_spins_changed)
        r2.addStretch()
        layout.addLayout(r2)
        alloc_hdr = QHBoxLayout()
        alloc_hdr.setSpacing(6)
        fl = QLabel("Allocations:")
        fl.setStyleSheet(f'font-family: "{BODY_FAMILY}"; font-size: 12px; '
                         f"font-weight: bold; color: {TEXT_DARK};")
        alloc_hdr.addWidget(fl)
        arrow_css = (
            f"QPushButton {{ background: transparent; color: {TEXT_DARK}; "
            f"border: 1px solid {STONE_BORDER}; border-radius: 3px; "
            f'font-family: "{BODY_FAMILY}"; font-size: 14px; font-weight: bold; '
            f"padding: 0px; }}"
            f"QPushButton:hover {{ background: {WARM_GRAY_LIGHT}; }}")
        self.alloc_prev = QPushButton("<")
        self.alloc_prev.setFixedSize(26, 24)
        self.alloc_prev.setStyleSheet(arrow_css)
        self.alloc_prev.clicked.connect(self._prev_alloc_year)
        alloc_hdr.addWidget(self.alloc_prev)
        self.alloc_year_lbl = QLabel("")
        self.alloc_year_lbl.setStyleSheet(
            f'font-family: "{BODY_FAMILY}"; font-size: 13px; '
            f"font-weight: bold; color: {TEXT_DARK};")
        alloc_hdr.addWidget(self.alloc_year_lbl)
        self.alloc_next = QPushButton(">")
        self.alloc_next.setFixedSize(26, 24)
        self.alloc_next.setStyleSheet(arrow_css)
        self.alloc_next.clicked.connect(self._next_alloc_year)
        alloc_hdr.addWidget(self.alloc_next)
        alloc_hdr.addStretch()
        layout.addLayout(alloc_hdr)
        yr_row = QHBoxLayout()
        yr_row.setSpacing(8)
        yr_row.addWidget(self._lbl("ID due:"))
        self.id_deadline = self._make_date()
        yr_row.addWidget(self.id_deadline)
        yr_row.addWidget(self._lbl("Report due:"))
        self.report_deadline = self._make_date()
        yr_row.addWidget(self.report_deadline)
        yr_row.addWidget(self._lbl("Notes:"))
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Year notes")
        yr_row.addWidget(self.notes_edit, 1)
        layout.addLayout(yr_row)
        field_lbl = QLabel("Field days:")
        field_lbl.setStyleSheet(f'font-family: "{BODY_FAMILY}"; font-size: 12px; '
                                f"font-weight: bold; color: {MOSS_GREEN};")
        layout.addWidget(field_lbl)
        self.field_grid = QTableWidget(1, 13)
        self.field_grid.setHorizontalHeaderLabels(BIZ_LABELS + ["Total"])
        self.field_grid.verticalHeader().setVisible(False)
        self.field_grid.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.field_grid.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        hg = self.field_grid.horizontalHeader()
        for i in range(13):
            hg.setSectionResizeMode(i, QHeaderView.Stretch)
        self.field_grid.setFixedHeight(58)
        self.field_grid.setStyleSheet(
            f"QTableWidget {{ background: white; border: 1px solid {STONE_BORDER}; "
            f'gridline-color: {STONE_BORDER}; font-family: "{BODY_FAMILY}"; '
            f"font-size: 12px; }}"
            f"QHeaderView::section {{ background: {WARM_GRAY_LIGHT}; "
            f'font-family: "{BODY_FAMILY}"; font-size: 10px; font-weight: 600; '
            f"border: none; border-bottom: 1px solid {STONE_BORDER}; padding: 2px; }}")
        for col in range(12):
            item = QTableWidgetItem("0")
            item.setTextAlignment(Qt.AlignCenter)
            self.field_grid.setItem(0, col, item)
        total = QTableWidgetItem("0")
        total.setTextAlignment(Qt.AlignCenter)
        total.setFlags(Qt.ItemIsEnabled)
        total.setFont(QFont(BODY_FAMILY, 10, QFont.Bold))
        total.setForeground(QBrush(QColor(MOSS_GREEN)))
        self.field_grid.setItem(0, 12, total)
        self.field_grid.cellChanged.connect(self._on_field_changed)
        layout.addWidget(self.field_grid)
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        ml = QLabel("Micro:")
        ml.setStyleSheet(f"font-weight: bold; color: {DUSTY_PURPLE}; font-size: 12px;")
        bottom.addWidget(ml)
        self.micro_spin = QDoubleSpinBox()
        self.micro_spin.setRange(0, 365)
        self.micro_spin.setDecimals(1)
        self.micro_spin.setSuffix(" d")
        self.micro_spin.setFixedWidth(80)
        bottom.addWidget(self.micro_spin)
        rl = QLabel("Report:")
        rl.setStyleSheet(f"font-weight: bold; color: {AMBER}; font-size: 12px;")
        bottom.addWidget(rl)
        self.report_spin = QDoubleSpinBox()
        self.report_spin.setRange(0, 365)
        self.report_spin.setDecimals(1)
        self.report_spin.setSuffix(" d")
        self.report_spin.setFixedWidth(80)
        bottom.addWidget(self.report_spin)
        bottom.addStretch()
        self.del_btn = QPushButton("Delete")
        self.del_btn.setObjectName("delete")
        self.del_btn.setFixedWidth(80)
        self.del_btn.clicked.connect(self._on_delete)
        self.del_btn.hide()
        bottom.addWidget(self.del_btn)
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("primary")
        self.save_btn.setFixedWidth(80)
        self.save_btn.clicked.connect(self._on_save)
        bottom.addWidget(self.save_btn)
        layout.addLayout(bottom)
    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"font-size: 12px; color: {TEXT_MID};")
        return l
    def _make_date(self):
        de = QDateEdit()
        de.setCalendarPopup(True)
        de.setDisplayFormat("dd/MM/yyyy")
        de.setSpecialValueText("Not set")
        de.setMinimumDate(QDate(self._view_year, 1, 1))
        de.setDate(de.minimumDate())
        de.setFixedWidth(120)
        return de
    def _deadline_str(self, widget):
        if widget.date() == widget.minimumDate():
            return ""
        return widget.date().toString("yyyy-MM-dd")
    def _set_deadline(self, widget, date_str):
        if date_str:
            d = QDate.fromString(date_str, "yyyy-MM-dd")
            if d.isValid():
                widget.setDate(d)
                return
        widget.setDate(widget.minimumDate())
    def _alloc_label(self):
        y = self._alloc_year
        return f"{y}/{y + 1}"
    def _save_current_alloc(self):
        self._alloc_cache[self._alloc_year] = {
            "field_months": self._get_field_months(),
            "micro": self.micro_spin.value(), "report": self.report_spin.value(),
            "id_deadline": self._deadline_str(self.id_deadline),
            "report_deadline": self._deadline_str(self.report_deadline),
            "notes": self.notes_edit.text().strip(),
        }
    def _load_alloc_year(self):
        self.alloc_year_lbl.setText(self._alloc_label())
        cached = self._alloc_cache.get(self._alloc_year)
        if cached:
            fm_map = {m["month"]: m for m in cached["field_months"]}
            micro, report = cached["micro"], cached["report"]
            id_dl, rpt_dl, notes = cached["id_deadline"], cached["report_deadline"], cached["notes"]
        elif self._editing_id:
            fm = db.get_project_field_months(self._conn, self._editing_id, self._alloc_year)
            fm_map = {m["month"]: m for m in fm}
            ad = db.get_project_annual_days(self._conn, self._editing_id, self._alloc_year)
            micro, report = ad.get("micro_days", 0), ad.get("report_days", 0)
            id_dl, rpt_dl, notes = ad.get("id_deadline", ""), ad.get("report_deadline", ""), ad.get("notes", "")
        else:
            fm_map, micro, report, id_dl, rpt_dl, notes = {}, 0, 0, "", "", ""
        self.field_grid.blockSignals(True)
        for col_idx, cal_month in enumerate(BIZ_MONTHS):
            v = fm_map.get(cal_month, {}).get("field_days", 0)
            self.field_grid.item(0, col_idx).setText(f"{v:g}" if v else "0")
        t = sum(float(self.field_grid.item(0, c).text() or "0") for c in range(12))
        self.field_grid.item(0, 12).setText(f"{t:g}")
        self.field_grid.blockSignals(False)
        self.micro_spin.setValue(micro)
        self.report_spin.setValue(report)
        self._set_deadline(self.id_deadline, id_dl)
        self._set_deadline(self.report_deadline, rpt_dl)
        self.notes_edit.setText(notes)
    def _prev_alloc_year(self):
        if self._alloc_year > self.start_year_spin.value():
            self._save_current_alloc()
            self._alloc_year -= 1
            self._load_alloc_year()
            self._update_alloc_buttons()
    def _next_alloc_year(self):
        if self._alloc_year < self.end_year_spin.value():
            self._save_current_alloc()
            self._alloc_year += 1
            self._load_alloc_year()
            self._update_alloc_buttons()
    def _update_alloc_buttons(self):
        self.alloc_prev.setEnabled(self._alloc_year > self.start_year_spin.value())
        self.alloc_next.setEnabled(self._alloc_year < self.end_year_spin.value())
    def _on_year_spins_changed(self):
        self.start_suffix.setText(f"/ {self.start_year_spin.value() + 1}")
        self.end_suffix.setText(f"/ {self.end_year_spin.value() + 1}")
        self._update_alloc_buttons()
    def clear(self):
        self._editing_id = None
        self._alloc_year = self._view_year
        self._alloc_cache.clear()
        self._title.setText("New Project")
        self.name_edit.clear()
        self.client_edit.clear()
        self.status_combo.setCurrentIndex(0)
        self.quote_spin.setValue(0)
        self.start_year_spin.setValue(self._view_year)
        self.end_year_spin.setValue(self._view_year)
        self.id_deadline.setDate(self.id_deadline.minimumDate())
        self.report_deadline.setDate(self.report_deadline.minimumDate())
        self.notes_edit.clear()
        self.field_grid.blockSignals(True)
        for col in range(12):
            self.field_grid.item(0, col).setText("0")
        self.field_grid.item(0, 12).setText("0")
        self.field_grid.blockSignals(False)
        self.micro_spin.setValue(0)
        self.report_spin.setValue(0)
        self.alloc_year_lbl.setText(self._alloc_label())
        self.del_btn.hide()
        self.save_btn.setText("Save")
        self._update_alloc_buttons()
    def load_project(self, project: dict):
        self._editing_id = project["id"]
        self._alloc_cache.clear()
        self._title.setText(f"Edit: {project['project_name']}")
        self.name_edit.setText(project.get("project_name", ""))
        self.client_edit.setText(project.get("client", ""))
        idx = self.status_combo.findData(project.get("status", "quoted"))
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        self.quote_spin.setValue(project.get("quote_value", 0))
        self.start_year_spin.setValue(project.get("start_year", self._view_year))
        self.end_year_spin.setValue(project.get("end_year", self._view_year))
        self._alloc_year = self._view_year
        self._load_alloc_year()
        self.del_btn.show()
        self.save_btn.setText("Update")
        self._update_alloc_buttons()
    def _on_field_changed(self, row, col):
        if col >= 12:
            return
        item = self.field_grid.item(0, col)
        try:
            val = max(float(item.text()), 0) if item.text() else 0
        except ValueError:
            val = 0
        self.field_grid.blockSignals(True)
        item.setText(f"{val:g}" if val else "0")
        t = sum(float(self.field_grid.item(0, c).text() or "0") for c in range(12))
        self.field_grid.item(0, 12).setText(f"{t:g}")
        self.field_grid.blockSignals(False)
    def _get_field_months(self):
        months = []
        for col_idx, cal_month in enumerate(BIZ_MONTHS):
            v = float(self.field_grid.item(0, col_idx).text() or "0")
            months.append({"month": cal_month, "field_days": v})
        return months
    def _on_save(self):
        if not self.name_edit.text().strip():
            return
        self._save_current_alloc()
        data = {
            "start_year": self.start_year_spin.value(),
            "end_year": self.end_year_spin.value(),
            "project_name": self.name_edit.text().strip(),
            "client": self.client_edit.text().strip(),
            "status": self.status_combo.currentData(),
            "quote_value": self.quote_spin.value(),
        }
        if self._editing_id:
            db.update_project(self._conn, self._editing_id, data)
            pid = self._editing_id
        else:
            pid = db.add_project(self._conn, data)
        for yr, alloc in self._alloc_cache.items():
            db.set_project_field_months(self._conn, pid, yr, alloc["field_months"])
            db.set_project_annual_days(self._conn, pid, yr, {
                "micro_days": alloc["micro"], "report_days": alloc["report"],
                "id_deadline": alloc["id_deadline"],
                "report_deadline": alloc["report_deadline"],
                "notes": alloc["notes"],
            })
        self.clear()
        self.saved.emit()
    def _on_delete(self):
        if self._editing_id:
            pid = self._editing_id
            self.clear()
            self.deleted.emit(pid)

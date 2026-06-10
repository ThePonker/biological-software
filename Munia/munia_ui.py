"""Munia main window — capacity planner with April-March business year."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QFrame, QMessageBox, QPushButton
)
from PySide6.QtCore import Qt
from Munia.theme import (
    window_stylesheet, HEADING_FAMILY, BODY_FAMILY,
    TEXT_DARK, TEXT_MID, STONE_BORDER, STONE_LIGHT,
    DUSTY_PURPLE, MOSS_GREEN, AMBER, FADED_CRIMSON, WARM_GRAY
)
from Munia import munia_data as db
from Munia.capacity_dashboard import CapacityDashboard
from Munia.project_form import ProjectForm
from Munia.projects_panel import ProjectsPanel
from Munia.budget_settings import BudgetSettingsDialog


class MuniaWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Munia \u2014 Capacity Planner")
        self.setStyleSheet(window_stylesheet())
        self.setWindowState(Qt.WindowMaximized)
        self._conn = db.get_connection()
        db.ensure_schema(self._conn)
        self._year = db.current_biz_year()
        self._build_ui()
        self._connect_signals()
        self._refresh()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 10, 16, 10)
        outer.setSpacing(10)
        header = QHBoxLayout()
        header.setSpacing(12)
        tc = QVBoxLayout()
        tc.setSpacing(0)
        t = QLabel("Munia")
        t.setObjectName("heading")
        s = QLabel("Capacity Planner")
        s.setObjectName("subheading")
        tc.addWidget(t)
        tc.addWidget(s)
        header.addLayout(tc)
        header.addStretch()
        yl = QLabel("Season:")
        yl.setStyleSheet(
            f'font-family: "{HEADING_FAMILY}"; font-size: 15px; '
            f"font-weight: bold; color: {TEXT_DARK};")
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2020, 2040)
        self.year_spin.setValue(self._year)
        self.year_spin.setFixedWidth(90)
        self.year_spin.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.year_label = QLabel(f"/ {self._year + 1}")
        self.year_label.setStyleSheet(
            f'font-family: "{HEADING_FAMILY}"; font-size: 15px; '
            f"font-weight: bold; color: {TEXT_MID};")
        header.addWidget(yl)
        header.addWidget(self.year_spin)
        header.addWidget(self.year_label)
        header.addSpacing(12)
        self.budget_btn = QPushButton("Budget Settings")
        self.budget_btn.setStyleSheet(
            "QPushButton { padding: 5px 14px; border: 1px solid " + STONE_BORDER + "; "
            "border-radius: 4px; font-size: 11px; color: " + TEXT_MID + "; } "
            "QPushButton:hover { background-color: " + STONE_LIGHT + "; }")
        self.budget_btn.clicked.connect(self._open_budget_settings)
        header.addWidget(self.budget_btn)
        outer.addLayout(header)
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {STONE_BORDER};")
        outer.addWidget(sep)
        body = QHBoxLayout()
        body.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(8)
        self.capacity = CapacityDashboard()
        left.addWidget(self.capacity)
        div1 = QFrame()
        div1.setFrameShape(QFrame.HLine)
        div1.setFixedHeight(3)
        div1.setStyleSheet(f"background: {STONE_BORDER};")
        left.addWidget(div1)
        self.form = ProjectForm(self._conn)
        left.addWidget(self.form)
        div2 = QFrame()
        div2.setFrameShape(QFrame.HLine)
        div2.setFixedHeight(3)
        div2.setStyleSheet(f"background: {STONE_BORDER};")
        left.addWidget(div2)
        stitle = QLabel("Pipeline Summary")
        stitle.setStyleSheet(
            f'font-family: "{HEADING_FAMILY}"; font-size: 14px; '
            f"font-weight: bold; color: {TEXT_DARK};")
        left.addWidget(stitle)
        self.summary_card = QFrame()
        self.summary_card.setStyleSheet(
            f"QFrame {{ background: {STONE_LIGHT}; "
            f"border: 1px solid {STONE_BORDER}; border-radius: 6px; }}")
        sc = QVBoxLayout(self.summary_card)
        sc.setContentsMargins(14, 8, 14, 8)
        sc.setSpacing(3)
        self.r_quoted = self._srow("0", "Quoted", DUSTY_PURPLE)
        self.r_declined = self._srow("0", "Declined", FADED_CRIMSON)
        self.r_no_resp = self._srow("0", "No Response", WARM_GRAY)
        self.r_total = self._srow("0", "Total", TEXT_DARK)
        for r in (self.r_quoted, self.r_declined, self.r_no_resp, self.r_total):
            sc.addLayout(r["layout"])
        sc.addSpacing(4)
        # Revenue hero row
        rev_row = QHBoxLayout()
        rev_row.setSpacing(16)
        self.won_lbl = self._hero("Revenue confirmed", "\u00a30", MOSS_GREEN, rev_row)
        self.lost_lbl = self._hero("Revenue lost", "\u00a30", FADED_CRIMSON, rev_row)
        rev_row.addStretch()
        sc.addLayout(rev_row)
        sc.addSpacing(4)
        # Confirmed days hero row
        days_title = QLabel("Confirmed Days")
        days_title.setStyleSheet(
            f'font-family: "{BODY_FAMILY}"; font-size: 11px; '
            f"font-weight: bold; color: {TEXT_MID};")
        sc.addWidget(days_title)
        days_row = QHBoxLayout()
        days_row.setSpacing(16)
        self.d_field = self._hero("Field", "0", MOSS_GREEN, days_row)
        self.d_micro = self._hero("Micro", "0", DUSTY_PURPLE, days_row)
        self.d_report = self._hero("Report", "0", AMBER, days_row)
        self.d_total = self._hero("Total", "0", TEXT_DARK, days_row)
        days_row.addStretch()
        sc.addLayout(days_row)
        left.addWidget(self.summary_card)
        left.addStretch()
        self.projects = ProjectsPanel(self._conn)
        body.addLayout(left, 2)
        body.addWidget(self.projects, 3)
        outer.addLayout(body, 1)

    def _srow(self, count_text, label_text, colour):
        row = QHBoxLayout()
        row.setSpacing(8)
        count = QLabel(count_text)
        count.setStyleSheet(
            f'font-family: "{BODY_FAMILY}"; font-size: 18px; '
            f"font-weight: bold; color: {colour};")
        count.setFixedWidth(30)
        label = QLabel(label_text)
        label.setStyleSheet(
            f'font-family: "{BODY_FAMILY}"; font-size: 12px; color: {TEXT_MID};')
        row.addWidget(count)
        row.addWidget(label)
        row.addStretch()
        return {"layout": row, "count": count, "label": label}

    def _hero(self, title, value, colour, parent_layout):
        col = QVBoxLayout()
        col.setSpacing(0)
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f'font-family: "{BODY_FAMILY}"; font-size: 11px; color: {TEXT_MID};')
        col.addWidget(lbl)
        val = QLabel(value)
        val.setStyleSheet(
            f'font-family: "{BODY_FAMILY}"; font-size: 20px; '
            f"font-weight: bold; color: {colour};")
        col.addWidget(val)
        parent_layout.addLayout(col)
        return val

    def _connect_signals(self):
        self.year_spin.valueChanged.connect(self._on_year_changed)
        self.projects.project_selected.connect(self._on_project_selected)
        self.form.saved.connect(self._refresh)
        self.form.deleted.connect(self._on_delete)

    def _open_budget_settings(self):
        dlg = BudgetSettingsDialog(self._conn, self._year, self)
        if dlg.exec() == BudgetSettingsDialog.Accepted:
            self._refresh()

    def _refresh(self):
        self.capacity.refresh(self._conn, self._year)
        self.form.set_year(self._year)
        projects = db.get_projects_for_year(self._conn, self._year)
        self.projects.load(projects, self._year)
        self._refresh_summary(projects)

    def _refresh_summary(self, projects):
        counts = {"quoted": 0, "accepted": 0, "declined": 0, "no_response": 0}
        values = {"quoted": 0.0, "accepted": 0.0, "declined": 0.0, "no_response": 0.0}
        for p in projects:
            st = p.get("status", "quoted")
            if st in counts:
                counts[st] += 1
                values[st] += p.get("quote_value", 0)
            else:
                counts["quoted"] += 1
        self.r_quoted["count"].setText(str(counts["quoted"]))
        self.r_quoted["label"].setText(
            f"Quoted (\u00a3{values['quoted']:,.0f})")
        self.r_declined["count"].setText(str(counts["declined"]))
        self.r_declined["label"].setText(
            f"Declined (\u00a3{values['declined']:,.0f})")
        self.r_no_resp["count"].setText(str(counts["no_response"]))
        self.r_no_resp["label"].setText(
            f"No Response (\u00a3{values['no_response']:,.0f})")
        self.r_total["count"].setText(str(len(projects)))
        self.won_lbl.setText(f"\u00a3{values['accepted']:,.0f}")
        lost = values["declined"] + values["no_response"]
        self.lost_lbl.setText(f"\u00a3{lost:,.0f}")
        a_field = db.get_accepted_field_total(self._conn, self._year)
        a_ann = db.get_annual_totals(self._conn, self._year, ("accepted",))
        micro = a_ann.get("micro", 0)
        report = a_ann.get("report", 0)
        total_d = a_field + micro + report
        self.d_field.setText(f"{a_field:g}")
        self.d_micro.setText(f"{micro:g}")
        self.d_report.setText(f"{report:g}")
        self.d_total.setText(f"{total_d:g}")

    def _on_year_changed(self, year):
        self._year = year
        self.year_label.setText(f"/ {year + 1}")
        self.form.clear()
        self._refresh()

    def _on_project_selected(self, project):
        self.form.load_project(project)

    def _on_delete(self, project_id):
        reply = QMessageBox.question(
            self, "Munia", "Delete this project?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            db.delete_project(self._conn, project_id)
            self._refresh()

    def closeEvent(self, event):
        if self._conn:
            self._conn.close()
        super().closeEvent(event)

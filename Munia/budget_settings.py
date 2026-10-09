"""
Munia — Budget Settings Dialog

Edit capacity budgets for a business year:
  - Field days per month (Apr-Jul by default)
  - Microscope days total
  - Report writing days total
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QPushButton, QFormLayout, QGroupBox,
)

from Munia.theme import (
    STONE_BORDER, HEADING_FAMILY,
    TEXT_DARK, TEXT_MID, MOSS_GREEN, DUSTY_PURPLE, AMBER,
)
from Munia import munia_data as db
from Munia.munia_data import BIZ_MONTHS, BIZ_LABELS, FIELD_MONTHS


class BudgetSettingsDialog(QDialog):
    """Edit capacity budgets for a given business year."""

    def __init__(self, conn, year: int, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._year = year
        self.setWindowTitle(f"Budget Settings — {year}/{year + 1}")
        self.setFixedWidth(400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel(f"Capacity Budget {self._year}/{self._year + 1}")
        title.setStyleSheet(
            f'font-family: "{HEADING_FAMILY}"; font-size: 14px; '
            f"font-weight: bold; color: {TEXT_DARK};"
        )
        layout.addWidget(title)

        info = QLabel(
            "Set the number of working days available for each activity. "
            "Changes apply to the selected business year only."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {TEXT_MID}; font-size: 11px;")
        layout.addWidget(info)

        # Field days
        field_group = QGroupBox("Field Days")
        field_group.setStyleSheet(self._group_style(MOSS_GREEN))
        fl = QFormLayout(field_group)
        fl.setSpacing(8)
        fl.setContentsMargins(12, 16, 12, 12)

        field_cap = db.get_field_capacity(self._conn, self._year)
        cap_map = {c["month"]: c["field_budget"] for c in field_cap}

        self._field_spins = {}
        for cal_month in BIZ_MONTHS:
            biz_idx = BIZ_MONTHS.index(cal_month)
            label = BIZ_LABELS[biz_idx]
            spin = QSpinBox()
            spin.setRange(0, 31)
            spin.setValue(int(cap_map.get(cal_month, 0)))
            spin.setSuffix(" days")
            is_field = cal_month in FIELD_MONTHS
            if not is_field:
                spin.setStyleSheet("color: #aaa;")
            self._field_spins[cal_month] = spin
            fl.addRow(f"{label}:", spin)

        layout.addWidget(field_group)

        # Microscope days
        micro_group = QGroupBox("Microscope Days")
        micro_group.setStyleSheet(self._group_style(DUSTY_PURPLE))
        ml = QFormLayout(micro_group)
        ml.setSpacing(8)
        ml.setContentsMargins(12, 16, 12, 12)

        ann = db.get_annual_capacity(self._conn, self._year)

        self.micro_spin = QSpinBox()
        self.micro_spin.setRange(0, 365)
        self.micro_spin.setValue(int(ann.get("micro_budget", 0)))
        self.micro_spin.setSuffix(" days")
        ml.addRow("Total budget:", self.micro_spin)

        layout.addWidget(micro_group)

        # Report days
        report_group = QGroupBox("Report Writing Days")
        report_group.setStyleSheet(self._group_style(AMBER))
        rl = QFormLayout(report_group)
        rl.setSpacing(8)
        rl.setContentsMargins(12, 16, 12, 12)

        self.report_spin = QSpinBox()
        self.report_spin.setRange(0, 365)
        self.report_spin.setValue(int(ann.get("report_budget", 0)))
        self.report_spin.setSuffix(" days")
        rl.addRow("Total budget:", self.report_spin)

        layout.addWidget(report_group)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            f"padding: 6px 16px; border: 1px solid {STONE_BORDER}; "
            f"border-radius: 4px; color: {TEXT_MID};"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(
            f"padding: 6px 16px; background-color: {MOSS_GREEN}; color: white; "
            f"border: none; border-radius: 4px; font-weight: bold;"
        )
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _save(self):
        # Update field budgets per month
        for cal_month, spin in self._field_spins.items():
            self._conn.execute(
                "INSERT OR REPLACE INTO capacity (year, month, field_budget) "
                "VALUES (?, ?, ?)",
                (self._year, cal_month, spin.value())
            )

        # Update micro/report budgets
        self._conn.execute(
            "INSERT OR REPLACE INTO annual_capacity "
            "(year, micro_budget, report_budget) VALUES (?, ?, ?)",
            (self._year, self.micro_spin.value(), self.report_spin.value())
        )

        self._conn.commit()
        self.accept()

    def _group_style(self, accent):
        return (
            f"QGroupBox {{ font-weight: 600; font-size: 12px; "
            f"color: {accent}; border: 1px solid {STONE_BORDER}; "
            f"border-radius: 4px; margin-top: 8px; padding-top: 16px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; "
            f"left: 12px; padding: 0 6px; }}"
        )

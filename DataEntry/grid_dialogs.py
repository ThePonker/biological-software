"""ExportOptionsDialog and EmbargoDialog (split from entry_grid.py, R13)."""
from __future__ import annotations


from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QDialog, QDialogButtonBox, QCheckBox, QDateEdit,
)

from DataEntry import theme


class ExportOptionsDialog(QDialog):
    """Ask whether to clear the job after exporting it to CSV."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export to CSV")
        self.setMinimumWidth(340)
        self.setStyleSheet(theme.input_qss())
        v = QVBoxLayout(self)
        intro = QLabel("Export this job's rows to a CSV file.")
        intro.setStyleSheet(f"color: {theme.INK}; font-size: 13px;")
        intro.setWordWrap(True)
        v.addWidget(intro)
        self.chk_clear = QCheckBox("Clear the job after export")
        self.chk_clear.setChecked(True)  # default: export-and-discard (unchanged behaviour)
        v.addWidget(self.chk_clear)
        hint = QLabel("Untick to keep the job open and its rows intact.")
        hint.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        hint.setWordWrap(True)
        v.addWidget(hint)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def clear_after(self) -> bool:
        return self.chk_clear.isChecked()


class EmbargoDialog(QDialog):
    """Choose whether to embargo a commercial job at commit -- 'no embargo' is a clear option."""
    def __init__(self, parent=None, current=None):
        super().__init__(parent)
        self.setWindowTitle("Embargo")
        # current: the job's embargo (carried from the project's records when a job is
        # reopened from Commercial Reports) -- offered as the default when still in force
        self.setMinimumWidth(360)
        self.setStyleSheet(theme.input_qss())
        from PySide6.QtCore import QDate
        from PySide6.QtWidgets import QRadioButton, QButtonGroup
        v = QVBoxLayout(self)

        intro = QLabel("Hold these records from iRecord until a date, or release with no embargo?")
        intro.setStyleSheet(f"color: {theme.INK}; font-size: 13px;")
        intro.setWordWrap(True)
        v.addWidget(intro)

        self.rb_none = QRadioButton("No embargo (available immediately)")
        self.rb_embargo = QRadioButton("Embargo until:")
        grp = QButtonGroup(self)
        grp.addButton(self.rb_none)
        grp.addButton(self.rb_embargo)

        v.addWidget(self.rb_none)
        row = QHBoxLayout()
        row.addWidget(self.rb_embargo)
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd/MM/yyyy")   # shown day first; stored ISO (value())
        self.date.setDate(QDate.currentDate().addYears(2))
        row.addWidget(self.date)
        row.addStretch(1)
        v.addLayout(row)

        self.rb_embargo.toggled.connect(self.date.setEnabled)
        self.rb_none.setChecked(True)   # default: no embargo, chosen deliberately
        self.date.setEnabled(False)
        cur = QDate.fromString(str(current or "")[:10], "yyyy-MM-dd")
        if cur.isValid() and cur > QDate.currentDate():
            self.date.setDate(cur)
            self.rb_embargo.setChecked(True)
            intro.setText(intro.text() + f"\n\nThis project's records are embargoed until "
                          f"{cur.toString('dd/MM/yyyy')}; the same date is offered.")

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def value(self):
        if self.rb_embargo.isChecked():
            return self.date.date().toString("yyyy-MM-dd")
        return None

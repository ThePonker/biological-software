"""
Examen -- picker for previewing an uncommitted Data Entry job (read-only).
"""
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QHeaderView,
                               QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout)

from shared.display_format import dmy


class EntryJobPicker(QDialog):
    """Lists examen_data.list_entry_jobs(); chosen_id() is the job picked, or None."""

    HEADS = ["Job", "Project", "Rows", "Species", "Dates", "Held back"]

    def __init__(self, jobs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preview a Data Entry job")
        self.resize(720, 360)
        self._jobs = list(jobs)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Active Data Entry jobs with records not yet committed. Rows counts the "
                             "rows a commit would write; Held back the rows it would leave in "
                             "staging (To check, undated or unreadable). The preview only reads "
                             "them; nothing is written."))
        self.table = QTableWidget(len(self._jobs), len(self.HEADS))
        self.table.setHorizontalHeaderLabels(self.HEADS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i, j in enumerate(self._jobs):
            dates = (f"{dmy(j['first_date'])} – {dmy(j['last_date'])}"
                     if j["first_date"] else "")
            for c, text in enumerate([j["name"], j["project"] or j["name"], str(j["rows"]),
                                      str(j["species"]), dates,
                                      str(j.get("held_back", 0))]):
                self.table.setItem(i, c, QTableWidgetItem(text))
        if self._jobs:
            self.table.selectRow(0)
        self.table.doubleClicked.connect(lambda _i: self.accept())
        lay.addWidget(self.table, 1)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def chosen_id(self):
        rows = self.table.selectionModel().selectedRows()
        return self._jobs[rows[0].row()]["id"] if rows else None

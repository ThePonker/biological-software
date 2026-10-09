"""JobsListPage -- the front door: list active jobs, create, open, delete.

Commercial jobs (8 Oct 2026): Project and Client are pickers of the names already in
use, so a typo cannot split one project into two in Examen and Commercial Reports.
"Show committed" lists finished jobs; Reopen (or Open on one) sets it back to active
so more records can be added under the same project.

Reads entry_jobs via staging_repo. Emits job_opened(job_id) when a job is opened. The
canonical Personal job is pinned at the top and can't be deleted.

Personal jobs exported for iRecord stay listed, "exported - awaiting iRecord", until
Check iRecord return finds every record back and Wil closes them (DE7, 9 Oct 2026).
Delete takes the staging CSV safety copy first (before_change, set by the widget; DE8).
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QDialog, QFormLayout,
    QLineEdit, QComboBox, QDialogButtonBox, QMessageBox, QCheckBox, QCompleter,
)

from DataEntry import theme
from DataEntry import staging_repo as repo


def _picker(names, placeholder):
    """Editable combo of existing names: pick one, or type a new one."""
    cmb = QComboBox()
    cmb.setEditable(True)
    cmb.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    cmb.addItem("")
    cmb.addItems(names)
    cmb.setCurrentIndex(0)
    cmb.lineEdit().setPlaceholderText(placeholder)
    comp = QCompleter(names, cmb)
    comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    comp.setFilterMode(Qt.MatchFlag.MatchContains)
    cmb.setCompleter(comp)
    return cmb


class NewJobDialog(QDialog):
    def __init__(self, parent=None, projects=None, job=None):
        super().__init__(parent)
        self._job = job          # editing an existing job's details (Edit details)
        # [{project, client}] already in use -- committed records and jobs
        self._projects = list(projects or [])
        self._project_names = list(dict.fromkeys(d["project"] for d in self._projects))
        self._client_names = sorted({d["client"] for d in self._projects if d["client"]},
                                    key=str.casefold)
        self.setWindowTitle("New job")
        self.setMinimumWidth(360)
        self.setStyleSheet(theme.input_qss())
        form = QFormLayout(self)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("e.g. Hook Farm Parcel 4")
        form.addRow("Name", self.txt_name)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["Personal", "Commercial"])
        self.cmb_mode.currentTextChanged.connect(self._on_mode)
        form.addRow("Mode", self.cmb_mode)

        self.txt_project = _picker(self._project_names, "pick an existing project, or type a new one")
        self.txt_client = _picker(self._client_names, "pick an existing client, or type a new one")
        self.txt_project.currentTextChanged.connect(self._on_project)
        self.lbl_client = QLabel("Client")
        self.lbl_project = QLabel("Project")
        form.addRow(self.lbl_project, self.txt_project)
        form.addRow(self.lbl_client, self.txt_client)
        self.lbl_existing = QLabel("")
        self.lbl_existing.setWordWrap(True)
        self.lbl_existing.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        form.addRow("", self.lbl_existing)
        self._set_commercial_visible(False)

        self.err = QLabel("")
        self.err.setStyleSheet(f"color: {theme.CLAY}; font-size: 12px;")
        form.addRow("", self.err)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.txt_name.setFocus()
        if job:
            self.setWindowTitle("Job details")
            self.txt_name.setText(job.get("name") or "")
            self.cmb_mode.setCurrentText(job.get("mode") or "Personal")
            self.txt_project.setCurrentText(job.get("project") or "")
            self.txt_client.setCurrentText(job.get("client") or "")
            note = QLabel("Changes apply to rows committed from now on. Records already "
                          "committed keep their project and client.")
            note.setWordWrap(True)
            note.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
            form.insertRow(form.rowCount() - 2, "", note)

    def _on_mode(self, mode: str):
        self._set_commercial_visible(mode == "Commercial")

    def _set_commercial_visible(self, vis: bool):
        for w in (self.lbl_client, self.txt_client, self.lbl_project, self.txt_project,
                  self.lbl_existing):
            w.setVisible(vis)

    def _on_project(self, text: str):
        """An existing project fills its client (when it has only one) and says so."""
        name = repo.canonical_name(text, self._project_names)
        clients = [d["client"] for d in self._projects if name and d["project"] == name]
        if not clients:
            self.lbl_existing.setText("")
            return
        if len(set(clients)) == 1 and not self.txt_client.currentText().strip():
            self.txt_client.setCurrentText(clients[0])
        self.lbl_existing.setText(
            "Existing project \u2014 records committed here join it in Examen and "
            "Commercial Reports. To add to its own job instead, tick \u201cShow committed\u201d "
            "and Reopen it.")

    def _accept(self):
        if not self.txt_name.text().strip():
            self.err.setText("Give the job a name.")
            return
        # A commercial job is grouped everywhere (Examen, Commercial Reports, the iRecord
        # export) by its project: without one its records become "(no project)" (8 Oct 2026).
        if self.cmb_mode.currentText() == "Commercial" and not self.txt_project.currentText().strip():
            self.err.setText("A commercial job needs a Project.")
            return
        self.accept()

    def values(self):
        mode = self.cmb_mode.currentText()
        commercial = mode == "Commercial"
        return {
            "name": self.txt_name.text().strip(),
            "mode": mode,
            # snapped to an existing spelling when only case or spacing differs
            "client": repo.canonical_name(self.txt_client.currentText(), self._client_names)
                      if commercial else None,
            "project": repo.canonical_name(self.txt_project.currentText(), self._project_names)
                       if commercial else None,
        }


class JobsListPage(QWidget):
    job_opened = Signal(int)

    def __init__(self, conn: sqlite3.Connection, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._conn = conn
        self.before_change = None   # safety copy before a delete: returns falsy on failure
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(12)

        top = QHBoxLayout()
        title = QLabel("Jobs")
        title.setStyleSheet(f"color: {theme.INK}; font-size: 16px; font-weight: 600;")
        top.addWidget(title)
        top.addStretch(1)
        self.chk_done = QCheckBox("Show committed")
        self.chk_done.setToolTip("List finished jobs too, so one can be reopened to add records")
        self.chk_done.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        self.chk_done.toggled.connect(lambda *_: self.refresh())
        top.addWidget(self.chk_done)
        top.addSpacing(10)
        self.btn_new = QPushButton("New job")
        self.btn_new.setStyleSheet(
            f"background: {theme.MOSS}; color: {theme.PAPER}; font-weight: 600;"
            f"padding: 6px 14px; border: none; border-radius: 5px;"
        )
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.clicked.connect(self._new_job)
        top.addWidget(self.btn_new)
        v.addLayout(top)

        hint = QLabel("Open a job to enter records. Your Personal job is always here; commercial "
                      "jobs you create as you go. Nothing commits to Observatum until you choose to.")
        hint.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        hint.setWordWrap(True)
        v.addWidget(hint)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "Mode", "Rows", "Last edited", "Status"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.table.cellDoubleClicked.connect(lambda *_: self._open_selected())
        self.table.itemSelectionChanged.connect(self._sync_buttons)
        self.table.setStyleSheet(
            f"QTableWidget {{ background: {theme.CARD}; border: 1px solid {theme.LINE};"
            f"  border-radius: 6px; font-size: 13px;"
            f"  selection-background-color: rgba(74,124,89,0.30); selection-color: {theme.INK}; }}"
            f"QTableWidget::item:selected {{ background: rgba(74,124,89,0.30); color: {theme.INK}; }}"
            f"QHeaderView::section {{ background: {theme.PAPER}; padding: 5px; border: none;"
            f"  border-bottom: 1px solid {theme.LINE}; font-weight: 600; }}"
        )
        v.addWidget(self.table, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_reopen = QPushButton("Reopen")
        self.btn_reopen.setToolTip("Set this committed job back to active to add more records. "
                                   "Its committed records stay in Observatum.")
        self.btn_reopen.setStyleSheet(
            f"background: transparent; color: {theme.SLATE}; border: 1px solid {theme.SLATE};"
            f"padding: 5px 12px; border-radius: 5px; font-size: 12px;"
        )
        self.btn_reopen.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reopen.clicked.connect(self._reopen_selected)
        row.addWidget(self.btn_reopen)
        self.btn_check = QPushButton("Check iRecord return")
        self.btn_check.setToolTip("After an iRecord sync: are all of this exported job's records "
                                  "back in Observatum? Close the job when they are.")
        self.btn_check.setStyleSheet(theme.button_secondary_qss())
        self.btn_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check.clicked.connect(self._check_return)
        row.addWidget(self.btn_check)
        self.btn_edit = QPushButton("Edit details")
        self.btn_edit.setToolTip("Change this job's name, project or client")
        self.btn_edit.setStyleSheet(
            f"background: transparent; color: {theme.SLATE}; border: 1px solid {theme.SLATE};"
            f"padding: 5px 12px; border-radius: 5px; font-size: 12px;"
        )
        self.btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit.clicked.connect(self._edit_selected)
        row.addWidget(self.btn_edit)
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setStyleSheet(
            f"background: transparent; color: {theme.CLAY}; border: 1px solid {theme.CLAY};"
            f"padding: 5px 12px; border-radius: 5px; font-size: 12px;"
        )
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.clicked.connect(self._delete_selected)
        row.addWidget(self.btn_delete)

        self.btn_open = QPushButton("Open  \u2192")
        self.btn_open.setStyleSheet(
            f"background: {theme.SLATE}; color: {theme.PAPER}; font-weight: 600;"
            f"padding: 6px 16px; border: none; border-radius: 5px;"
        )
        self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open.clicked.connect(self._open_selected)
        row.addWidget(self.btn_open)
        v.addLayout(row)

    # -- data ------------------------------------------------------------
    def refresh(self):
        jobs = repo.list_jobs(self._conn, include_done=self.chk_done.isChecked())
        self.table.setRowCount(0)
        for j in jobs:
            r = self.table.rowCount()
            self.table.insertRow(r)
            name_item = QTableWidgetItem(j["name"])
            name_item.setData(Qt.ItemDataRole.UserRole, j["id"])
            name_item.setData(Qt.ItemDataRole.UserRole + 1, repo.is_personal(j))
            name_item.setData(Qt.ItemDataRole.UserRole + 2, (j.get("status") or "active"))
            if repo.is_personal(j):
                f = name_item.font(); f.setBold(True); name_item.setFont(f)
            self.table.setItem(r, 0, name_item)
            mode_txt = j.get("mode") or ""
            if j.get("project") and (j.get("mode") or "").lower().startswith("comm"):
                mode_txt += f" \u00b7 {j['project']}" + (f" ({j['client']})" if j.get("client") else "")
            self.table.setItem(r, 1, QTableWidgetItem(mode_txt))
            self.table.setItem(r, 2, QTableWidgetItem(str(j.get("row_count", 0))))
            last = (j.get("updated_at") or "")[:16]
            self.table.setItem(r, 3, QTableWidgetItem(last))
            emb = j.get("embargo_until")
            status = j.get("status") or "active"
            status_txt = repo.STATUS_LABELS.get(status, status) if status != "active" \
                else ("embargo " + emb if emb else "")
            self.table.setItem(r, 4, QTableWidgetItem(status_txt))
        if self.table.rowCount():
            self.table.selectRow(0)
        self._sync_buttons()

    def _selected(self):
        r = self.table.currentRow()
        if r < 0:
            return None, None, False
        item = self.table.item(r, 0)
        return r, item.data(Qt.ItemDataRole.UserRole), bool(item.data(Qt.ItemDataRole.UserRole + 1))

    def _selected_status(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        return self.table.item(r, 0).data(Qt.ItemDataRole.UserRole + 2)

    def _sync_buttons(self):
        _, job_id, is_personal = self._selected()
        self.btn_open.setEnabled(job_id is not None)
        self.btn_edit.setEnabled(job_id is not None and not is_personal)
        awaiting = self._selected_status() == repo.AWAITING_IRECORD
        self.btn_reopen.setVisible(self.chk_done.isChecked() or awaiting)
        self.btn_reopen.setEnabled(job_id is not None and self._selected_status() != "active")
        self.btn_check.setVisible(awaiting)
        self.btn_check.setEnabled(awaiting)
        # can't delete the canonical Personal job
        self.btn_delete.setEnabled(job_id is not None and not is_personal)

    # -- actions ---------------------------------------------------------
    def _new_job(self):
        dlg = NewJobDialog(self, repo.known_projects(self._conn))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        vals = dlg.values()
        job_id = repo.create_job(self._conn, vals["name"], vals["mode"], vals["client"], vals["project"])
        self.refresh()
        self._select_job(job_id)

    def _edit_selected(self):
        _, job_id, is_personal = self._selected()
        if job_id is None or is_personal:
            return
        dlg = NewJobDialog(self, repo.known_projects(self._conn), job=repo.get_job(self._conn, job_id))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        repo.update_job(self._conn, job_id, name=v["name"], mode=v["mode"],
                        client=v["client"], project=v["project"])
        self.refresh()
        self._select_job(job_id)

    def _select_job(self, job_id):
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) == job_id:
                self.table.selectRow(r)
                return

    def _open_selected(self):
        _, job_id, _ = self._selected()
        if job_id is None:
            return
        if self._selected_status() != "active":
            if not self._confirm_reopen():
                return
            repo.reopen_job(self._conn, job_id)
        repo.touch_job(self._conn, job_id)
        self.job_opened.emit(job_id)

    def _confirm_reopen(self) -> bool:
        r, _, _ = self._selected()
        name = self.table.item(r, 0).text()
        if self._selected_status() == repo.AWAITING_IRECORD:
            return QMessageBox.question(
                self, "Reopen job",
                f"\u201c{name}\u201d was exported for iRecord and is waiting for its records "
                "to come back.\n\nReopen it to edit? It will need exporting again, and anything "
                "already imported into iRecord from the first file stays there.\n\nTo see "
                "whether the records are back, use \u201cCheck iRecord return\u201d instead."
            ) == QMessageBox.StandardButton.Yes
        return QMessageBox.question(
            self, "Reopen job",
            f"Reopen \u201c{name}\u201d to add more records?\n\n"
            "Its committed records stay in Observatum and are not loaded back into the grid; "
            "the grid starts empty. New records commit as a new batch under the same project "
            "and client.") == QMessageBox.StandardButton.Yes

    def _reopen_selected(self):
        _, job_id, _ = self._selected()
        if job_id is None or self._selected_status() == "active":
            return
        if not self._confirm_reopen():
            return
        repo.reopen_job(self._conn, job_id)
        self.refresh()
        self._select_job(job_id)

    def open_job_by_id(self, job_id: int):
        """Show and open a job chosen elsewhere (Commercial Reports' Add records)."""
        if not self.chk_done.isChecked():
            self.refresh()
        self._select_job(job_id)
        repo.touch_job(self._conn, job_id)
        self.job_opened.emit(job_id)

    def _delete_selected(self):
        r, job_id, is_personal = self._selected()
        if job_id is None or is_personal:
            return
        name = self.table.item(r, 0).text()
        n = repo.row_count(self._conn, job_id)
        msg = f"Delete job \u201c{name}\u201d"
        msg += f" and its {n} staged row{'s' if n != 1 else ''}?" if n else "?"
        msg += "\n\nThis removes only the staged working data \u2014 nothing already committed to Observatum."
        if QMessageBox.question(self, "Delete job", msg) != QMessageBox.StandardButton.Yes:
            return
        if not self._safety_copy():
            return
        repo.delete_job(self._conn, job_id)
        self.refresh()

    def _safety_copy(self) -> bool:
        """Staging CSV before a delete (DE8). False = stop (the copy failed, Wil said no)."""
        if self.before_change is None or self.before_change():
            return True
        return QMessageBox.question(
            self, "Safety copy failed",
            "The staging safety copy (staging_backup.csv) could not be written.\n\n"
            "Delete anyway?") == QMessageBox.StandardButton.Yes

    def _check_return(self):
        _, job_id, _ = self._selected()
        if job_id is None or self._selected_status() != repo.AWAITING_IRECORD:
            return
        from DataEntry.irecord_return_dialog import check_return
        if check_return(self, self._conn, job_id):
            self.refresh()

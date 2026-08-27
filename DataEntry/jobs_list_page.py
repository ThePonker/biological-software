"""JobsListPage -- the front door: list active jobs, create, open, delete.

Reads entry_jobs via staging_repo. Emits job_opened(job_id) when a job is opened. The
canonical Personal job is pinned at the top and can't be deleted.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QDialog, QFormLayout,
    QLineEdit, QComboBox, QDialogButtonBox, QMessageBox,
)

from DataEntry import theme
from DataEntry import staging_repo as repo


class NewJobDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
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

        self.txt_client = QLineEdit()
        self.txt_project = QLineEdit()
        self.lbl_client = QLabel("Client")
        self.lbl_project = QLabel("Project")
        form.addRow(self.lbl_client, self.txt_client)
        form.addRow(self.lbl_project, self.txt_project)
        self._set_commercial_visible(False)

        self.err = QLabel("")
        self.err.setStyleSheet(f"color: {theme.CLAY}; font-size: 12px;")
        form.addRow("", self.err)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.txt_name.setFocus()

    def _on_mode(self, mode: str):
        self._set_commercial_visible(mode == "Commercial")

    def _set_commercial_visible(self, vis: bool):
        for w in (self.lbl_client, self.txt_client, self.lbl_project, self.txt_project):
            w.setVisible(vis)

    def _accept(self):
        if not self.txt_name.text().strip():
            self.err.setText("Give the job a name.")
            return
        self.accept()

    def values(self):
        mode = self.cmb_mode.currentText()
        commercial = mode == "Commercial"
        return {
            "name": self.txt_name.text().strip(),
            "mode": mode,
            "client": self.txt_client.text().strip() if commercial else None,
            "project": self.txt_project.text().strip() if commercial else None,
        }


class JobsListPage(QWidget):
    job_opened = Signal(int)

    def __init__(self, conn: sqlite3.Connection, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._conn = conn
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
        jobs = repo.list_jobs(self._conn)
        self.table.setRowCount(0)
        for j in jobs:
            r = self.table.rowCount()
            self.table.insertRow(r)
            name_item = QTableWidgetItem(j["name"])
            name_item.setData(Qt.ItemDataRole.UserRole, j["id"])
            name_item.setData(Qt.ItemDataRole.UserRole + 1, repo.is_personal(j))
            if repo.is_personal(j):
                f = name_item.font(); f.setBold(True); name_item.setFont(f)
            self.table.setItem(r, 0, name_item)
            self.table.setItem(r, 1, QTableWidgetItem(j.get("mode") or ""))
            self.table.setItem(r, 2, QTableWidgetItem(str(j.get("row_count", 0))))
            last = (j.get("updated_at") or "")[:16]
            self.table.setItem(r, 3, QTableWidgetItem(last))
            emb = j.get("embargo_until")
            status = j.get("status") or "active"
            status_txt = status if status != "active" else ("embargo " + emb if emb else "")
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

    def _sync_buttons(self):
        _, job_id, is_personal = self._selected()
        self.btn_open.setEnabled(job_id is not None)
        # can't delete the canonical Personal job
        self.btn_delete.setEnabled(job_id is not None and not is_personal)

    # -- actions ---------------------------------------------------------
    def _new_job(self):
        dlg = NewJobDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        vals = dlg.values()
        job_id = repo.create_job(self._conn, vals["name"], vals["mode"], vals["client"], vals["project"])
        self.refresh()
        self._select_job(job_id)

    def _select_job(self, job_id):
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) == job_id:
                self.table.selectRow(r)
                return

    def _open_selected(self):
        _, job_id, _ = self._selected()
        if job_id is not None:
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
        repo.delete_job(self._conn, job_id)
        self.refresh()

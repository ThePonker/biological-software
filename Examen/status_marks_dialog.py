"""
Examen -- the "Status marks" dialog: every "likely to be downgraded" mark, global and per job,
with the status it was made against, the species' current status in Codex, and whether it still
applies (see status_marks.mark_state). Remove deletes the selected mark; nothing else is edited.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from Examen import status_marks as sm
from Examen.site_analysis_view import BTN_OUTLINE, BTN_PRIMARY, TABLE_STYLE
from Examen.style import TEXT_SECONDARY
from shared.text_sizes import font_css

HEADS = ["Species", "Applies to", "Status marked", "Current status", "State", "Reason", "Date"]
CANNOT_CHECK = "cannot check"
STATE_TEXT = {sm.APPLIED: "applied", sm.STALE: "status changed — not applied",
              sm.UNRECORDED: "status not recorded"}
NOT_BRACKETED = "not bracketed in this job"
ALL_JOBS = "All jobs"


def build_rows(current_keys=None):
    """One dict per global mark and per override: species, scope, job, status marked, current,
    state, reason, date, and what Remove acts on. current_keys: tvk -> current status_key (a
    function taking the tvks, default Codex; None or a failed lookup means unavailable)."""
    marks, overs = sm.list_marks(), sm.list_overrides()
    tvks = sorted({m["tvk"] for m in marks} | {o["tvk"] for o in overs})
    try:
        cur = (current_keys or sm.codex_status_keys)(tvks) if tvks else {}
    except Exception:  # noqa: BLE001 -- Codex unreadable: say so, do not guess
        cur = None
    rows = []
    for m in marks:
        rows.append(_row(m, "global", ALL_JOBS, cur, bracket=True))
    for o in overs:
        job = " / ".join(x for x in (o["project_name"], o["client"], o["survey_year"]) if x)
        rows.append(_row(o, "job", job or "(unnamed job)", cur, bracket=bool(o["bracket"])))
    return rows


def _row(rec, scope, job, cur, bracket):
    current = sm.NOT_GIVEN if cur is None else cur.get(rec["tvk"], "")
    state = sm.mark_state(rec["status_marked"], current) if bracket else None
    text = STATE_TEXT[state] if state else NOT_BRACKETED
    if state == sm.APPLIED and current is sm.NOT_GIVEN:     # Codex unreadable: do not claim it
        state, text = None, CANNOT_CHECK + " (Codex could not be read)"
    return {"species": rec["species_name"], "scope": scope, "job": job, "tvk": rec["tvk"],
            "marked": rec["status_marked"], "state": state,
            "state_text": text,
            "current": "(unavailable)" if current is sm.NOT_GIVEN else current,
            "reason": rec.get("reason", ""), "date": (rec["updated_at"] or "")[:10],
            "rec": rec}


class StatusMarksDialog(QDialog):
    def __init__(self, parent=None, current_keys=None):
        super().__init__(parent)
        self.setWindowTitle("Status marks")
        self.resize(900, 460)
        self._current_keys = current_keys
        lay = QVBoxLayout(self)
        note = QLabel("A mark applies only while the species' status is still the one marked. "
                      "If a status review changes it the mark is not applied: the published "
                      "status is shown without brackets.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {font_css('caption')};")
        lay.addWidget(note)
        self.table = QTableWidget(0, len(HEADS))
        self.table.setHorizontalHeaderLabels(HEADS)
        self.table.setStyleSheet(TABLE_STYLE)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)
        self.empty = QLabel("No status marks saved.")
        lay.addWidget(self.empty)
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setStyleSheet(BTN_OUTLINE)
        self.remove_btn.clicked.connect(self.remove_selected)
        btns.addWidget(self.remove_btn)
        close = QPushButton("Close")
        close.setStyleSheet(BTN_PRIMARY)
        close.clicked.connect(self.accept)
        btns.addWidget(close)
        lay.addLayout(btns)
        self.reload()

    def reload(self):
        self.rows = build_rows(self._current_keys)
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            job = r["job"] if r["scope"] == "job" else ALL_JOBS
            cells = [r["species"], job, r["marked"] or "—", r["current"] or "none",
                     r["state_text"], r["reason"], r["date"]]
            for j, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.table.setItem(i, j, item)
        self.empty.setVisible(not self.rows)
        self.remove_btn.setEnabled(bool(self.rows))

    def remove_selected(self):
        sel = self.table.currentRow()
        if sel < 0 or sel >= len(self.rows):
            QMessageBox.information(self, "Status marks", "Select a mark to remove.")
            return
        r = self.rows[sel]
        try:
            if r["scope"] == "global":
                sm.clear_mark(r["tvk"])
            else:
                o = r["rec"]
                sm.clear_override(o["project_name"], o["client"], o["survey_year"], r["tvk"])
        except sm.MissingTables as e:
            QMessageBox.information(self, "Status marks", str(e))
            return
        except Exception as e:  # noqa: BLE001 -- say so; one row per write, nothing half-done
            QMessageBox.warning(self, "Status marks", f"The mark could not be removed.\n\n{e}")
            return
        self.reload()

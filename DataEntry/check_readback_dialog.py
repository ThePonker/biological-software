"""Read back checking (17 Oct 2026): choose a checker's reply, see each answer beside its row,
tick the ones to accept, Apply. Nothing changes before Apply. The logic is check_readback.py;
the page's apply callback writes through the grid, so a new name is matched to its TVK the way
a typed name is."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from DataEntry import check_readback as cr
from DataEntry import theme
from DataEntry.check_export_dialog import remembered_folder

CHECKER_KEY = "DataEntry/checkReadbackChecker"
HEAD = ["Accept", "Ref", "Your ID", "Agree?", "Their ID", "Notes", "What happens"]


class CheckReadbackDialog(QDialog):
    def __init__(self, conn, job: Dict, apply_fn: Callable[[List[Dict], str], Dict], parent=None,
                 resolve: Optional[Callable[[str], Optional[Dict]]] = None):
        super().__init__(parent)
        self._conn, self._job, self._apply_fn, self._resolve = conn, job, apply_fn, resolve
        self.items: List[Dict] = []
        self.outcome: Dict = {}
        self.setWindowTitle("Read back checking")
        self.resize(980, 520)
        self.setStyleSheet(theme.input_qss())
        v = QVBoxLayout(self)
        intro = QLabel("Choose the checker's reply (the spreadsheet you sent, filled in, or a CSV "
                       "of it). Each answer is shown beside its row; nothing changes until you "
                       "press Apply.")
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {theme.INK}; font-size: 13px;")
        v.addWidget(intro)

        top = QHBoxLayout()
        self.file_lbl = QLabel("No reply chosen.")
        self.file_lbl.setStyleSheet(f"color: {theme.INK}; font-size: 12px;")
        top.addWidget(self.file_lbl, 1)
        pick = QPushButton("Choose reply…")
        pick.setStyleSheet(theme.button_secondary_qss(compact=True))
        pick.clicked.connect(self._choose)
        top.addWidget(pick)
        v.addLayout(top)

        who = QHBoxLayout()
        who.addWidget(QLabel("Checked by:"))
        self.checker = QLineEdit()
        self.checker.setPlaceholderText("e.g. Smith, J.  (goes into Determiner and Comment)")
        try:
            self.checker.setText(QSettings().value(CHECKER_KEY, "", type=str) or "")
        except Exception:
            pass
        self.checker.textChanged.connect(lambda _t: self._refresh_text())
        who.addWidget(self.checker, 1)
        v.addLayout(who)

        self.table = QTableWidget(0, len(HEAD))
        self.table.setHorizontalHeaderLabels(HEAD)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setStretchLastSection(True)
        self.table.itemChanged.connect(lambda _i: self._refresh_text())
        from shared.tick_style import style_item_view
        style_item_view(self.table)        # the suite's green tick (Wil, 17 Oct: none showed)
        v.addWidget(self.table, 1)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(f"color: {theme.INK}; font-size: 12px;")
        v.addWidget(self.summary)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.apply_btn = QPushButton("Apply ticked")
        self.apply_btn.setStyleSheet(theme.button_primary_qss())
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._apply)
        btns.addWidget(self.apply_btn)
        close = QPushButton("Close")
        close.setStyleSheet(theme.button_secondary_qss())
        close.clicked.connect(self.reject)
        btns.addWidget(close)
        v.addLayout(btns)

    # -- loading -------------------------------------------------------------
    def _choose(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "The checker's reply", str(remembered_folder()),
            "Reply (*.xlsx *.csv);;All files (*)")
        if path:
            self.load(path)

    def load(self, path) -> bool:
        try:
            reply = cr.read_reply(path)
        except Exception as e:
            QMessageBox.warning(self, "Read back checking", f"This reply cannot be read.\n\n{e}")
            return False
        self.items = cr.plan(self._conn, self._job["id"], reply, self._resolve)
        self.file_lbl.setText(f"Reply: {Path(path).name}  ({len(self.items)} line(s))")
        self._fill()
        return True

    def _fill(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.items))
        for r, it in enumerate(self.items):
            tick = QTableWidgetItem()
            if it["action"] in cr.APPLICABLE:
                tick.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                tick.setCheckState(Qt.CheckState.Checked if it["tick"] else Qt.CheckState.Unchecked)
            else:
                tick.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(r, 0, tick)
            for c, val in enumerate((it["ref"], it["your_id"], it["agree"], it["their_id"],
                                     it["notes"], self._what(it)), start=1):
                cell = QTableWidgetItem(val or "")
                cell.setToolTip(val or "")
                self.table.setItem(r, c, cell)
        self.table.blockSignals(False)
        self.table.resizeColumnsToContents()
        for c in range(self.table.columnCount()):
            self.table.setColumnWidth(c, min(self.table.columnWidth(c), 260))
        self._refresh_text()

    def _what(self, it) -> str:
        text = cr.ACTIONS[it["action"]]
        if it["action"] == "new_id" and it.get("resolved"):
            text += f": {it['resolved'].get('scientific_name')}"
        if it.get("suggested"):
            text += f" (\"{it['suggested']}\" not taken as a new ID: doubtful, unsure or not one species)"
        if it["changed"]:
            text += "  (the row's species has changed since the export: check before ticking)"
        return text

    # -- state -----------------------------------------------------------------
    def ticked(self) -> List[Dict]:
        out = []
        for r, it in enumerate(self.items):
            cell = self.table.item(r, 0)
            if cell is not None and it["action"] in cr.APPLICABLE \
                    and cell.checkState() == Qt.CheckState.Checked:
                out.append(it)
        return out

    def _refresh_text(self):
        n = len(self.ticked())
        counts = {}
        for it in self.items:
            counts[it["action"]] = counts.get(it["action"], 0) + 1
        parts = [f"{counts[k]} {cr.ACTIONS[k].split(':')[0].lower()}" for k in cr.ACTIONS
                 if counts.get(k)]
        self.summary.setText(("; ".join(parts) + ". " if parts else "")
                             + f"{n} ticked to apply.")
        self.apply_btn.setEnabled(n > 0)

    def _apply(self):
        chosen = self.ticked()
        who = self.checker.text().strip()
        if any(it["action"] == "new_id" for it in chosen) and not who:
            if QMessageBox.question(
                    self, "Read back checking",
                    "No checker's name: new identifications will keep the row's Determiner. "
                    "Apply anyway?") != QMessageBox.StandardButton.Yes:
                return
        try:
            QSettings().setValue(CHECKER_KEY, who)
        except Exception:
            pass
        try:
            self.outcome = self._apply_fn(chosen, who) or {}
        except Exception as e:
            QMessageBox.warning(self, "Read back checking", f"Stopped: {e}")
            return
        lines = [f"Applied {self.outcome.get('applied', 0)} answer(s)."]
        for note in self.outcome.get("notes", [])[:15]:
            lines.append("• " + note)
        QMessageBox.information(self, "Read back checking", "\n".join(lines))
        self.accept()


def resolver_from(species_delegate) -> Optional[Callable[[str], Optional[Dict]]]:
    """resolve(text) for check_readback.plan: the one species the grid's species cell would
    fill for this name without asking (a pasted name's rule), else None."""
    if species_delegate is None or not hasattr(species_delegate, "decide"):
        return None

    def resolve(text):
        action, found = species_delegate.decide(text, interactive=False)
        return found if action == "fill" and found and found.get("tvk") else None
    return resolve


def apply_through_grid(model, items: List[Dict], checker: str) -> Dict:
    """Write the accepted answers through the grid's model (so the row, the database and any
    photo names follow as for a typed edit). A new species is only ever the one plan() found
    for certain. Stops at the first error and says which answers were already applied.
    Returns {'applied': n, 'notes': [...]}."""
    from DataEntry.entry_grid import COLIDX
    where = {model.row_id(r): r for r in range(model.real_count())}
    done, notes = [], []
    for it in items:
        r = where.get(it["row_id"])
        if r is None:
            notes.append(f"{it['ref']}: the row is no longer in the job, skipped")
            continue
        ch = cr.changes_for(it, checker)
        if not ch:
            continue
        try:
            species = ch.pop("species", None)
            if species:
                model.setData(model.index(r, COLIDX["species_name"]), species,
                              Qt.ItemDataRole.EditRole)
            for key, val in ch.items():
                model.setData(model.index(r, COLIDX[key]), "" if val is None else val,
                              Qt.ItemDataRole.EditRole)
        except Exception as e:
            raise RuntimeError(
                f"{it['ref']} failed ({e}). Already applied: "
                + (", ".join(done) if done else "none") + ". The rest were not applied; "
                "a backup was taken before any change.") from e
        done.append(it["ref"])
    return {"applied": len(done), "notes": notes}

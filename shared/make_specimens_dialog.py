"""make_specimens_dialog -- the review screen for Make specimens (25 Nov 2026).

Used by Data Entry (ticked Keep rows) and by Observation Data (ticked records). One line per
row or record: the record's own details (read only) and what to make -- how many (0 up to its
No.), preparation, condition, storage location, drawer, notes. A row that already has specimens
starts at 0 and says so; one with no species match, or marked To check, is listed but cannot be
made. Make shows a preview, then shared.make_specimens.apply writes (away check, backup, one
transaction, read-back). Storage and drawer may stay blank: place them later with Drawer in hand.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout)

from DataEntry import theme
from shared import make_specimens as ms
from shared.fit_to_screen import fit_to_screen
from shared.specimen_vocab import CONDITIONS, PREPARATION_TYPES, STORAGE_LOCATIONS
from shared.text_sizes import font_css

HEADERS = ["Species", "Date", "Grid ref", "Site", "Sex", "Determiner", "No.", "Make",
           "Preparation", "Condition", "Storage", "Drawer", "Notes", "Note"]
C_MAKE, C_PREP, C_COND, C_STORE, C_DRAWER, C_NOTES, C_NOTE = 7, 8, 9, 10, 11, 12, 13


class MakeSpecimensDialog(QDialog):
    def __init__(self, cands: List[Dict], db_path, linked: bool = True, parent=None,
                 backup: Optional[Callable] = None):
        super().__init__(parent)
        self._cands, self._db_path, self._linked, self._backup = cands, db_path, linked, backup
        self.result_info: Optional[Dict] = None        # set once the specimens are written
        self.setWindowTitle("Make specimens")
        self.setModal(True)
        self.setMinimumSize(640, 420)
        kind = cands[0]["kind"] if cands else "row"
        v = QVBoxLayout(self)
        intro = ("One specimen per row is made by default, up to the row's No. Males and females are "
                 "separate rows. Storage and drawer may stay blank: place them later with Drawer in hand."
                 if kind == "row" else
                 "One specimen per record is made by default, up to the record's No. They are linked "
                 "to the record. Storage and drawer may stay blank: place them later with Drawer in hand.")
        v.addWidget(self._label(intro))
        if kind == "row" and not linked:
            v.addWidget(self._label(
                "This is a Personal job, whose rows go to iRecord: the specimens are made WITHOUT a "
                "field record link and will appear in Specimens to check.", warn=True))
        self._build_set_all(v)
        self.table = QTableWidget(len(cands), len(HEADERS))
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(f"QTableWidget {{ background: {theme.CARD}; color: {theme.INK}; "
                                 f"gridline-color: {theme.LINE}; font-size: {font_css('small')}; }}")
        for r, c in enumerate(cands):
            self._fill_row(r, c)
        self.table.resizeColumnsToContents()
        v.addWidget(self.table, 1)
        row = QHBoxLayout()
        self.summary = QLabel("")
        self.summary.setStyleSheet(f"color: {theme.MUTED}; font-size: {font_css('small')};")
        row.addWidget(self.summary, 1)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(theme.button_secondary_qss())
        cancel.clicked.connect(self.reject)
        self.make_btn = QPushButton("Make specimens")
        self.make_btn.setStyleSheet(theme.button_primary_qss())
        self.make_btn.clicked.connect(self._make)
        row.addWidget(cancel)
        row.addWidget(self.make_btn)
        v.addLayout(row)
        self._show_total()
        self.resize(1500, 600)              # every column on a desktop screen (fit_to_screen trims)
        fit_to_screen(self)

    # ------------------------------------------------------------------ build
    @staticmethod
    def _label(text, warn=False) -> QLabel:
        lb = QLabel(text)
        lb.setWordWrap(True)
        lb.setStyleSheet(f"color: {theme.CLAY if warn else theme.INK}; font-size: {font_css('small')};")
        return lb

    @staticmethod
    def _combo(items, current="", editable=False) -> QComboBox:
        cb = QComboBox()
        cb.setEditable(editable)
        cb.addItems(items)
        cb.setCurrentText(current)
        cb.setStyleSheet(theme.input_qss())
        return cb

    def _build_set_all(self, v) -> None:
        h = QHBoxLayout()
        h.addWidget(self._label("Set for all:"))
        self.all_prep = self._combo(PREPARATION_TYPES)
        self.all_cond = self._combo(CONDITIONS)
        self.all_store = self._combo(STORAGE_LOCATIONS, editable=True)
        self.all_drawer = QLineEdit()
        self.all_drawer.setPlaceholderText("Drawer")
        self.all_drawer.setMaximumWidth(90)
        # picking from a dropdown applies at once; the drawer applies on Enter or leaving the box
        # (Wil, 25 Nov 2026: one action, no separate Set button)
        for label, w, col in (("Preparation", self.all_prep, C_PREP), ("Condition", self.all_cond, C_COND),
                              ("Storage", self.all_store, C_STORE), ("Drawer", self.all_drawer, C_DRAWER)):
            lb = QLabel(label)
            lb.setStyleSheet(f"color: {theme.MUTED}; font-size: {font_css('small')}; margin-left: 8px;")
            h.addWidget(lb)
            h.addWidget(w)
            if isinstance(w, QComboBox):
                w.activated.connect(lambda _i, w=w, col=col: self._set_all(w, col))
            else:                       # only when typed in: tabbing past never blanks every drawer
                w.editingFinished.connect(lambda w=w, col=col: self._set_all_if_typed(w, col))
        h.addStretch(1)
        v.addLayout(h)

    def _set_all_if_typed(self, edit: QLineEdit, col) -> None:
        if edit.isModified():
            edit.setModified(False)
            self._set_all(edit, col)

    def _set_all(self, widget, col) -> None:
        text = widget.currentText() if isinstance(widget, QComboBox) else widget.text()
        for r, c in enumerate(self._cands):
            if not c["refused"]:
                cell = self.table.cellWidget(r, col)
                (cell.setCurrentText if isinstance(cell, QComboBox) else cell.setText)(text)

    def _fill_row(self, r: int, c: Dict) -> None:
        ch = ms.default_choice(c)
        for col, text in enumerate((c["species_name"], c["date"], c["grid_ref"], c["site_name"], c["sex"],
                                    c["determiner"], c["quantity"] if c["quantity"] not in (None, "") else "")):
            it = QTableWidgetItem("" if text is None else str(text))
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(r, col, it)
        spin = QSpinBox()
        spin.setRange(0, 0 if c["refused"] else c["max"])
        spin.setValue(ch["n"])
        spin.valueChanged.connect(lambda _=0: self._show_total())
        self.table.setCellWidget(r, C_MAKE, spin)
        self.table.setCellWidget(r, C_PREP, self._combo(PREPARATION_TYPES, ch["preparation_type"]))
        self.table.setCellWidget(r, C_COND, self._combo(CONDITIONS, ch["condition"]))
        self.table.setCellWidget(r, C_STORE, self._combo(STORAGE_LOCATIONS, editable=True))
        self.table.setCellWidget(r, C_DRAWER, QLineEdit())
        self.table.setCellWidget(r, C_NOTES, QLineEdit())
        notes = []
        if c["refused"]:
            notes.append(f"CANNOT MAKE: {c['refused']}")
            for col in (C_PREP, C_COND, C_STORE, C_DRAWER, C_NOTES):
                self.table.cellWidget(r, col).setEnabled(False)
        if c["existing"]:
            notes.append(f"ALREADY HAS {c['existing']} specimen(s): starts at 0")
        if c["date_note"]:
            notes.append(c["date_note"])
        it = QTableWidgetItem("; ".join(notes))
        it.setFlags(Qt.ItemFlag.ItemIsEnabled)
        if c["refused"] or c["existing"]:
            # the species cell too, so a flagged row shows even with the Note column off screen
            from PySide6.QtGui import QBrush, QColor
            fg, bg = (theme.CLAY, theme.CLAY_BG) if c["refused"] else (theme.GOLD, theme.GOLD_BG)
            for cell in (it, self.table.item(r, 0)):
                cell.setForeground(QBrush(QColor(fg)))
                cell.setBackground(QBrush(QColor(bg)))
                cell.setToolTip("; ".join(notes))
        self.table.setItem(r, C_NOTE, it)

    # ------------------------------------------------------------------ read
    def choices(self) -> Dict:
        out = {}
        for r, c in enumerate(self._cands):
            w = self.table.cellWidget
            out[(c["kind"], c["id"])] = {
                "n": w(r, C_MAKE).value(), "preparation_type": w(r, C_PREP).currentText(),
                "condition": w(r, C_COND).currentText(), "storage_location": w(r, C_STORE).currentText(),
                "drawer_number": w(r, C_DRAWER).text(), "notes": w(r, C_NOTES).text()}
        return out

    def _show_total(self) -> None:
        n = sum(self.table.cellWidget(r, C_MAKE).value() for r in range(len(self._cands)))
        self.summary.setText(f"{n} specimen(s) to make from {len(self._cands)} listed")

    # ------------------------------------------------------------------ make
    def _preview(self, text: str) -> bool:
        """Show the preview; True if Make was pressed (tests replace this). One line per row, no
        wrapping, as wide as the longest line (to the screen's width), scrolling when long; the
        closing explanation (the last line of `text`) wraps underneath (Wil, 25 Nov 2026)."""
        from PySide6.QtGui import QFontMetrics
        from PySide6.QtWidgets import QApplication, QPlainTextEdit
        body, _, footer = text.rpartition("\n")
        dlg = QDialog(self)
        dlg.setWindowTitle("Make specimens")
        v = QVBoxLayout(dlg)
        box = QPlainTextEdit(body)
        box.setReadOnly(True)
        box.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        box.setStyleSheet(f"QPlainTextEdit {{ background: {theme.CARD}; color: {theme.INK}; "
                          f"font-size: {font_css('small')}; }}")
        box.ensurePolished()                  # the stylesheet's font size, before measuring
        fm = QFontMetrics(box.font())
        longest = max((fm.horizontalAdvance(line) for line in body.splitlines()), default=400)
        screen = QApplication.primaryScreen().availableGeometry() if QApplication.primaryScreen() else None
        width = min(longest + 80, int(screen.width() * 0.9) if screen else longest + 80)
        height = min(fm.lineSpacing() * (body.count("\n") + 2) + 30,
                     int(screen.height() * 0.6) if screen else 600)
        box.setMinimumSize(max(width, 420), height)
        v.addWidget(box)
        v.addWidget(self._label(footer))
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(theme.button_secondary_qss())
        cancel.clicked.connect(dlg.reject)
        ok = QPushButton("Make specimens")
        ok.setStyleSheet(theme.button_primary_qss())
        ok.clicked.connect(dlg.accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        v.addLayout(row)
        return dlg.exec() == QDialog.DialogCode.Accepted

    def _warn(self, text: str) -> None:
        QMessageBox.warning(self, "Make specimens", text)

    def _info(self, text: str) -> None:
        QMessageBox.information(self, "Make specimens", text)

    def _make(self) -> Optional[Dict]:
        try:
            plan = ms.make_plan(self._cands, self.choices())
        except ValueError as e:
            self._warn(str(e))
            return None
        if not plan:
            self._info("Nothing to make: every number is 0.")
            return None
        if not self._preview(ms.describe(plan, self._linked)):
            return None
        try:
            res = ms.apply(self._db_path, plan, self._linked, self._backup)
        except ms.MakeRefused as e:
            self._warn(str(e))
            return None
        self.result_info = res
        kind = plan[0]["cand"]["kind"]
        tail = ("They are linked to their records." if kind == "record" else
                "At commit they are linked to the record." if self._linked else
                "They have no field record link: see Specimens to check.")
        self._info(f"Made {len(res['ids'])} specimen(s) from {len(plan)} {kind}(s) "
                   f"(specimen ids {', '.join(map(str, res['ids'][:12]))}"
                   f"{' ...' if len(res['ids']) > 12 else ''}). {tail}")
        self.accept()
        return res


__all__ = ["MakeSpecimensDialog"]

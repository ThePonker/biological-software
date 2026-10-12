"""
Drawer in hand -- the preview window and the Drawers list (split out of
drawer_assign_dialog.py, 12 Oct 2026, Round 9 C).

PreviewDialog: every change before anything is written, headed by what it does in words
("Add to Cabinet 2 · Drawer 1: 5", "Move from ... to ...: 2", "Remove from ...: 3").
DrawersDialog: storage › drawer › count for every drawer in use, with "Open this drawer"
and "Empty this drawer…" (the emptying itself is the main dialog's preview, backup, write).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from shared import drawer_assign as da
from shared.fit_to_screen import fit_to_screen

from ...themes import theme

ROLE_KEY = Qt.ItemDataRole.UserRole
FIELD_NAMES = {"storage_location": "Storage location", "drawer_number": "Drawer",
               "condition": "Condition", "preparation_type": "Preparation"}


class PreviewDialog(QDialog):
    """Every change, before anything is written."""

    def __init__(self, changes, specs_by_id, storage, drawer, parent=None, title=None):
        super().__init__(parent)
        t = theme()
        self.setWindowTitle(title or "Preview — drawer in hand")
        self.resize(820, 560)
        fit_to_screen(self)
        v = QVBoxLayout(self)
        n_spec = len({c[0] for c in changes})
        head = QLabel(f"<b>{n_spec} specimen{'s' if n_spec != 1 else ''}, "
                      f"{len(changes)} change{'s' if len(changes) != 1 else ''}</b> — "
                      f"{da.where(storage, drawer)}")
        head.setStyleSheet("font-size: 15px;")
        v.addWidget(head)
        self.lines = [f"{what}: {n} specimen{'s' if n != 1 else ''}"
                      for what, n in da.outline(changes, specs_by_id.values(), storage, drawer)]
        what = QLabel("<br>".join(
            (f"<span style='color:{t.get('danger')}'>{ln}</span>" if ln.startswith("Remove")
             else ln) for ln in self.lines))
        what.setTextFormat(Qt.TextFormat.RichText)
        what.setWordWrap(True)
        v.addWidget(what)
        tbl = QTableWidget(len(changes), 5)
        tbl.setHorizontalHeaderLabels(["Specimen", "Field", "Before", "", "After"])
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for i, (sid, field, before, after) in enumerate(changes):
            s = specs_by_id.get(sid, {})
            who = QTableWidgetItem(f"{s.get('species_name', '')}  {s.get('date_collected') or ''}")
            f = who.font(); f.setItalic(True); who.setFont(f)
            tbl.setItem(i, 0, who)
            tbl.setItem(i, 1, QTableWidgetItem(FIELD_NAMES.get(field, field)))
            b = QTableWidgetItem(before or "empty")
            b.setForeground(QBrush(QColor(t.get("text_muted"))))
            tbl.setItem(i, 2, b)
            tbl.setItem(i, 3, QTableWidgetItem("→"))
            a = QTableWidgetItem(after or "empty (removed)")
            fa = a.font(); fa.setBold(True); a.setFont(fa)
            if not after:
                a.setForeground(QBrush(QColor(t.get("danger"))))
            tbl.setItem(i, 4, a)
        tbl.resizeColumnsToContents()
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        v.addWidget(tbl, 1)
        note = QLabel("Observatum is backed up first. All changes are written together, or none. "
                      "Removing a specimen from a drawer clears only its storage and drawer.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {t.get('text_secondary')};")
        v.addWidget(note)
        bb = QDialogButtonBox()
        self.apply_btn = bb.addButton(f"Apply {len(changes)} changes", QDialogButtonBox.ButtonRole.AcceptRole)
        back = bb.addButton("Back", QDialogButtonBox.ButtonRole.RejectRole)
        self.apply_btn.setStyleSheet(t.button_primary_style())
        back.setStyleSheet(t.button_cancel_style())
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)


class DrawersDialog(QDialog):
    """Every drawer in use: storage › drawer › count. Pick one to open or empty.

    After exec(), self.action is None, ("open", storage, drawer) or ("empty", storage, drawer)."""

    def __init__(self, specs, parent=None):
        super().__init__(parent)
        t = theme()
        self.setWindowTitle("Drawers")
        self.resize(460, 520)
        fit_to_screen(self)
        self.action = None
        v = QVBoxLayout(self)
        rows = da.drawers(specs)
        total = sum(n for _, _, n in rows)
        v.addWidget(QLabel(f"<b>{len(rows)} drawer{'s' if len(rows) != 1 else ''} in use</b> — "
                           f"{total:,} specimens recorded in one"))
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Storage › drawer", "Specimens"])
        by_storage = {}
        for st, dr, n in rows:
            by_storage.setdefault(st, []).append((dr, n))
        for st, drs in by_storage.items():
            top = QTreeWidgetItem([st or "(no storage location)", f"{sum(n for _, n in drs):,}"])
            top.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tree.addTopLevelItem(top)
            for dr, n in drs:
                it = QTreeWidgetItem([dr or "(no drawer)", f"{n:,}"])
                it.setData(0, ROLE_KEY, (st, dr))
                top.addChild(it)
            top.setExpanded(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.resizeColumnToContents(1)
        self.tree.itemSelectionChanged.connect(self._sel)
        self.tree.itemDoubleClicked.connect(lambda *_: self._done("open"))
        v.addWidget(self.tree, 1)
        if not rows:
            v.addWidget(QLabel("No specimen is recorded in a drawer yet."))
        h = QHBoxLayout()
        self.btn_open = QPushButton("Open this drawer")
        self.btn_open.setStyleSheet(t.button_primary_style())
        self.btn_open.clicked.connect(lambda: self._done("open"))
        self.btn_empty = QPushButton("Empty this drawer…")
        self.btn_empty.setStyleSheet(t.button_delete_style())
        self.btn_empty.setToolTip("Take every specimen out of this drawer (storage and drawer cleared; "
                                  "a preview comes first)")
        self.btn_empty.clicked.connect(lambda: self._done("empty"))
        close = QPushButton("Close")
        close.setStyleSheet(t.button_cancel_style())
        close.clicked.connect(self.reject)
        h.addWidget(self.btn_open)
        h.addWidget(self.btn_empty)
        h.addStretch(1)
        h.addWidget(close)
        v.addLayout(h)
        self._sel()

    def selected(self):
        items = self.tree.selectedItems()
        key = items[0].data(0, ROLE_KEY) if items else None
        # Some PySide6 builds hand a stored tuple back as a list: always give a tuple
        return tuple(key) if key is not None else None

    def select(self, storage, drawer):
        """Select a drawer row (tests and callers)."""
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                key = top.child(j).data(0, ROLE_KEY)
                if key is not None and tuple(key) == (storage, drawer):
                    self.tree.setCurrentItem(top.child(j))
                    return True
        return False

    def _sel(self):
        ok = self.selected() is not None
        self.btn_open.setEnabled(ok)
        self.btn_empty.setEnabled(ok)

    def _done(self, what):
        key = self.selected()
        if key is None:
            return
        self.action = (what, key[0], key[1])
        self.accept()

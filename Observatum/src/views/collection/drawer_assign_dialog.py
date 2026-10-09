"""
Insect Collection -- "Drawer in hand" (backlog A1, 8 Oct 2026).

Take a drawer out, pick it at the top, tick each specimen as you find it -- the list is
in taxonomic order under genus headings, so it reads in the order the drawer is laid
out -- then Save drawer: a preview of every change, a backup, and one write.

Records where specimens ARE. Planning a layout is Curator's job; this does not plan.
Rules and the write live in shared/drawer_assign.py (pure, tested).
"""
from __future__ import annotations

import re
import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QFrame, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

import paths
from shared import drawer_assign as da

GOLD = "#8a6609"
GOLD_TEXT = "#7a5a08"
GOLD_BG = "#faf6eb"
GREY = "#9ca3af"
ROLE_ID = Qt.ItemDataRole.UserRole
ROLE_KEY = Qt.ItemDataRole.UserRole + 1


def _combo(values, current=""):
    c = QComboBox()
    c.setEditable(True)
    c.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    c.addItems([""] + [v for v in values if v])
    c.setCurrentText(current)
    return c


def next_drawer_name(name: str) -> str:
    """'Drawer 1' -> 'Drawer 2'; 'D9' -> 'D10'; no number -> unchanged."""
    m = re.search(r"(\d+)(\D*)$", name or "")
    if not m:
        return name
    return name[:m.start(1)] + str(int(m.group(1)) + 1) + m.group(2)


class PreviewDialog(QDialog):
    """Every change, before anything is written."""

    def __init__(self, changes, specs_by_id, storage, drawer, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preview — drawer in hand")
        self.resize(820, 560)
        v = QVBoxLayout(self)
        n_spec = len({c[0] for c in changes})
        head = QLabel(f"<b>{len(changes)} changes to {n_spec} specimens</b> — "
                      f"{storage}{' · ' if storage and drawer else ''}{drawer}")
        head.setStyleSheet("font-size: 15px;")
        v.addWidget(head)
        names = {"storage_location": "Storage location", "drawer_number": "Drawer",
                 "condition": "Condition", "preparation_type": "Preparation"}
        summ = da.summary(changes)
        v.addWidget(QLabel("   ".join(f"{names[f]}: {n}" for f, n in summ.items())))
        t = QTableWidget(len(changes), 5)
        t.setHorizontalHeaderLabels(["Specimen", "Field", "Before", "", "After"])
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for i, (sid, field, before, after) in enumerate(changes):
            s = specs_by_id.get(sid, {})
            who = QTableWidgetItem(f"{s.get('species_name', '')}  {s.get('date_collected') or ''}")
            f = who.font(); f.setItalic(True); who.setFont(f)
            t.setItem(i, 0, who)
            t.setItem(i, 1, QTableWidgetItem(names.get(field, field)))
            b = QTableWidgetItem(before or "empty"); b.setForeground(QBrush(QColor(GREY)))
            t.setItem(i, 2, b)
            t.setItem(i, 3, QTableWidgetItem("→"))
            a = QTableWidgetItem(after); fa = a.font(); fa.setBold(True); a.setFont(fa)
            t.setItem(i, 4, a)
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        t.resizeColumnsToContents()
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        v.addWidget(t, 1)
        note = QLabel("Observatum is backed up first. All changes are written together, or none.")
        note.setStyleSheet("color: #4b5563;")
        v.addWidget(note)
        bb = QDialogButtonBox()
        self.apply_btn = bb.addButton(f"Apply {len(changes)} changes", QDialogButtonBox.ButtonRole.AcceptRole)
        bb.addButton("Back", QDialogButtonBox.ButtonRole.RejectRole)
        self.apply_btn.setStyleSheet(f"background: {GOLD}; color: white; font-weight: 600; padding: 6px 14px;")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)


class DrawerAssignDialog(QDialog):
    """Pick the drawer in hand; tick what is in it; save."""
    saved = Signal(int)   # number of changes written

    def __init__(self, parent=None, db_path=None):
        super().__init__(parent)
        self.setWindowTitle("Drawer in hand — record what is in a drawer")
        self.resize(1240, 760)
        self._db = str(db_path or paths.OBSERVATUM_DB)
        self._ticked = set()
        self._filter = None            # ("order"|"family"|"genus", value) or None
        self._building = False
        self._load()
        self._build()
        self._fill_tree()
        self._fill_list()

    # ---------------------------------------------------------------- data
    def _load(self):
        conn = sqlite3.connect(f"file:{self._db}?mode=ro", uri=True)
        try:
            self._specs = da.load_specimens(conn)
        finally:
            conn.close()
        self._by_id = {s["id"]: s for s in self._specs}

    def _distinct(self, field):
        return sorted({(s.get(field) or "").strip() for s in self._specs} - {""}, key=str.casefold)

    # ---------------------------------------------------------------- ui
    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        bar = QFrame()
        bar.setStyleSheet(f"QFrame {{ background: {GOLD_BG}; border-bottom: 1px solid #e8dcc0; }}")
        b = QHBoxLayout(bar)
        b.setContentsMargins(16, 10, 16, 10)
        t = QLabel("Drawer in hand")
        t.setStyleSheet(f"color: {GOLD_TEXT}; font-weight: 600; font-size: 13px; border: none;")
        b.addWidget(t)
        b.addWidget(QLabel("Storage"))
        self.cmb_storage = _combo(self._distinct("storage_location"))
        self.cmb_storage.setMinimumWidth(170)
        b.addWidget(self.cmb_storage)
        b.addWidget(QLabel("Drawer"))
        self.cmb_drawer = _combo(self._distinct("drawer_number"))
        self.cmb_drawer.setMinimumWidth(150)
        b.addWidget(self.cmb_drawer)
        hint = QLabel("Tick each specimen as you find it. The list is in taxonomic order.")
        hint.setStyleSheet("color: #4b5563; border: none;")
        b.addWidget(hint, 1)
        self.lbl_count = QLabel("0 ticked")
        self.lbl_count.setStyleSheet("font-weight: 600; border: none;")
        b.addWidget(self.lbl_count)
        v.addWidget(bar)
        for c in (self.cmb_storage, self.cmb_drawer):
            c.currentTextChanged.connect(lambda *_: self._fill_list())

        split = QSplitter(Qt.Orientation.Horizontal)
        v.addWidget(split, 1)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(10, 10, 6, 10)
        lv.addWidget(QLabel("<b>Order › family › genus</b>"))
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(2)
        self.tree.itemSelectionChanged.connect(self._on_tree)
        lv.addWidget(self.tree, 1)
        self.chk_free = QCheckBox("Not yet in a drawer")
        self.chk_free.setChecked(True)
        self.chk_placed = QCheckBox("Already in a drawer")
        for c in (self.chk_free, self.chk_placed):
            c.toggled.connect(lambda *_: self._fill_list())
            lv.addWidget(c)
        split.addWidget(left)

        mid = QWidget()
        mv = QVBoxLayout(mid)
        mv.setContentsMargins(6, 10, 6, 10)
        top = QHBoxLayout()
        self.lbl_scope = QLabel("")
        self.lbl_scope.setStyleSheet("font-weight: 600;")
        top.addWidget(self.lbl_scope, 1)
        btn_all = QPushButton("Tick all shown")
        btn_all.clicked.connect(lambda: self._tick_shown(True))
        btn_none = QPushButton("Untick all shown")
        btn_none.clicked.connect(lambda: self._tick_shown(False))
        top.addWidget(btn_all)
        top.addWidget(btn_none)
        mv.addLayout(top)
        self.list = QTreeWidget()
        self.list.setColumnCount(5)
        self.list.setHeaderLabels(["Species", "Date", "Site", "Sex", "Drawer now"])
        self.list.setRootIsDecorated(False)
        self.list.setUniformRowHeights(True)
        self.list.itemChanged.connect(self._on_item_changed)
        mv.addWidget(self.list, 1)
        split.addWidget(mid)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(10, 10, 12, 10)
        self.lbl_drawer = QLabel("")
        self.lbl_drawer.setStyleSheet("font-size: 15px; font-weight: 600;")
        rv.addWidget(self.lbl_drawer)
        self.lbl_summary = QLabel("Nothing ticked yet.")
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setTextFormat(Qt.TextFormat.RichText)
        rv.addWidget(self.lbl_summary)
        rv.addSpacing(8)
        rv.addWidget(QLabel("<b>Also set on the ticked specimens</b>"))
        form = QFormLayout()
        self.cmb_condition = _combo(self._distinct("condition"))
        self.cmb_prep = _combo(sorted(set(self._distinct("preparation_type")) |
                                      {"Pinned", "Carded", "Pointed", "Alcohol", "Slide"}))
        form.addRow("Condition", self.cmb_condition)
        form.addRow("Preparation", self.cmb_prep)
        rv.addLayout(form)
        n = QLabel("Blank leaves a field as recorded. Only empty fields are filled.")
        n.setWordWrap(True)
        n.setStyleSheet("color: #6b7280;")
        rv.addWidget(n)
        rv.addStretch(1)
        self.btn_save = QPushButton("Save drawer — preview…")
        self.btn_save.setStyleSheet(f"background: {GOLD}; color: white; font-weight: 600; padding: 9px;")
        self.btn_save.clicked.connect(self._save)
        rv.addWidget(self.btn_save)
        self.btn_next = QPushButton("Next drawer")
        self.btn_next.clicked.connect(self._next_drawer)
        rv.addWidget(self.btn_next)
        split.addWidget(right)
        split.setSizes([250, 690, 300])

    # ---------------------------------------------------------------- tree
    def _fill_tree(self):
        self.tree.clear()
        root = QTreeWidgetItem(["All specimens", f"{len(self._specs):,}"])
        root.setData(0, ROLE_KEY, None)
        self.tree.addTopLevelItem(root)
        for order, fams in da.tree(self._specs):
            n_o = sum(n for _, gs in fams for _, n in gs)
            oi = QTreeWidgetItem([order, f"{n_o:,}"])
            oi.setData(0, ROLE_KEY, ("order", order))
            self.tree.addTopLevelItem(oi)
            for fam, gens in fams:
                fi = QTreeWidgetItem([fam, f"{sum(n for _, n in gens):,}"])
                fi.setData(0, ROLE_KEY, ("family", fam))
                oi.addChild(fi)
                for g, n in gens:
                    gi = QTreeWidgetItem([g, f"{n:,}"])
                    f = gi.font(0); f.setItalic(True); gi.setFont(0, f)
                    gi.setData(0, ROLE_KEY, ("genus", g))
                    fi.addChild(gi)
        self.tree.resizeColumnToContents(1)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

    def _on_tree(self):
        items = self.tree.selectedItems()
        self._filter = items[0].data(0, ROLE_KEY) if items else None
        self._fill_list()

    # ---------------------------------------------------------------- list
    def _in_scope(self, s):
        if self._filter:
            kind, val = self._filter
            key = {"order": "order_name", "family": "family", "genus": "genus"}[kind]
            if (s.get(key) or "") != val and not (val.startswith("(no ") and not s.get(key)):
                return False
        placed = bool((s.get("storage_location") or "").strip() or (s.get("drawer_number") or "").strip())
        here = placed and not da.elsewhere(s, self.cmb_storage.currentText(), self.cmb_drawer.currentText())
        if s["id"] in self._ticked or here:
            return True
        return self.chk_placed.isChecked() if placed else self.chk_free.isChecked()

    def _fill_list(self):
        if not hasattr(self, "list"):
            return
        self._building = True
        self.list.clear()
        storage, drawer = self.cmb_storage.currentText(), self.cmb_drawer.currentText()
        shown = [s for s in self._specs if self._in_scope(s)]
        genus = None
        head_font = QFont(); head_font.setBold(True); head_font.setItalic(True)
        for s in shown:
            if s["genus"] != genus:
                genus = s["genus"]
                h = QTreeWidgetItem([genus or "(no genus)"])
                h.setFont(0, head_font)
                h.setForeground(0, QBrush(QColor(GOLD_TEXT)))
                h.setFlags(Qt.ItemFlag.ItemIsEnabled)
                for c in range(5):
                    h.setBackground(c, QBrush(QColor("#f3efe4")))
                self.list.addTopLevelItem(h)
            away = da.elsewhere(s, storage, drawer)
            now = " · ".join(x for x in ((s.get("storage_location") or "").strip(),
                                         (s.get("drawer_number") or "").strip()) if x) or "—"
            it = QTreeWidgetItem([s["species_name"] or "", s.get("date_collected") or "",
                                  s.get("site_name") or "", s.get("sex") or "", now])
            f = it.font(0); f.setItalic(True); it.setFont(0, f)
            it.setData(0, ROLE_ID, s["id"])
            flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            if not away:
                flags |= Qt.ItemFlag.ItemIsUserCheckable
                it.setCheckState(0, Qt.CheckState.Checked if s["id"] in self._ticked
                                 else Qt.CheckState.Unchecked)
            else:
                for c in range(5):
                    it.setForeground(c, QBrush(QColor(GREY)))
                it.setToolTip(0, f"Recorded in {now}")
            it.setFlags(flags)
            self.list.addTopLevelItem(it)
        for c in range(1, 5):
            self.list.resizeColumnToContents(c)
        self.list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        scope = self._filter[1] if self._filter else "All specimens"
        free = sum(1 for s in shown if not (s.get("drawer_number") or s.get("storage_location")))
        self.lbl_scope.setText(f"{scope} — {len(shown):,} shown, {free:,} not yet in a drawer")
        self._building = False
        self._update_summary()

    def _on_item_changed(self, item, col):
        if self._building or col != 0:
            return
        sid = item.data(0, ROLE_ID)
        if sid is None:
            return
        if item.checkState(0) == Qt.CheckState.Checked:
            self._ticked.add(sid)
        else:
            self._ticked.discard(sid)
        self._update_summary()

    def _tick_shown(self, on):
        self._building = True
        for i in range(self.list.topLevelItemCount()):
            it = self.list.topLevelItem(i)
            sid = it.data(0, ROLE_ID)
            if sid is None or not (it.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                continue
            it.setCheckState(0, Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
            (self._ticked.add if on else self._ticked.discard)(sid)
        self._building = False
        self._update_summary()

    def _update_summary(self):
        storage, drawer = self.cmb_storage.currentText().strip(), self.cmb_drawer.currentText().strip()
        self.lbl_drawer.setText(" · ".join(x for x in (storage, drawer) if x) or "Pick a drawer above")
        n = len(self._ticked)
        self.lbl_count.setText(f"{n} ticked into this drawer")
        if not n:
            self.lbl_summary.setText("Nothing ticked yet.")
        else:
            by = {}
            for sid in self._ticked:
                g = self._by_id[sid]["genus"]
                by[g] = by.get(g, 0) + 1
            order = [s["genus"] for s in self._specs]
            parts = sorted(by.items(), key=lambda kv: order.index(kv[0]))
            self.lbl_summary.setText(" · ".join(f"<i>{g}</i> {c}" for g, c in parts)
                                     + f"<br><span style='color:#6b7280'>{n} specimens</span>")
        self.btn_save.setEnabled(bool(n) and bool(storage or drawer))
        self.btn_save.setText(f"Save drawer ({n}) — preview…")

    # ---------------------------------------------------------------- save
    def _save(self):
        storage, drawer = self.cmb_storage.currentText().strip(), self.cmb_drawer.currentText().strip()
        try:
            changes = da.plan(self._specs, sorted(self._ticked), storage, drawer,
                              self.cmb_condition.currentText(), self.cmb_prep.currentText())
        except ValueError as e:
            QMessageBox.warning(self, "Drawer in hand", str(e))
            return
        if not changes:
            QMessageBox.information(self, "Drawer in hand",
                                    "Nothing to change: the ticked specimens already carry these values.")
            return
        pv = PreviewDialog(changes, self._by_id, storage, drawer, self)
        if pv.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            from shared.backup_service import backup_main_only
            if not backup_main_only("pre-drawer-assign"):
                QMessageBox.warning(self, "Drawer in hand", "The backup failed, so nothing was written.")
                return
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Drawer in hand", f"Backup unavailable, so nothing was written.\n{e}")
            return
        try:
            conn = sqlite3.connect(self._db)
            n = da.apply(conn, changes)
            conn.close()
        except (sqlite3.Error, ValueError, RuntimeError) as e:
            QMessageBox.warning(self, "Drawer in hand", f"Nothing was written.\n\n{e}")
            return
        self._ticked.clear()
        self._load()
        self._fill_list()
        self.saved.emit(n)
        QMessageBox.information(self, "Drawer saved",
                                f"{n} changes written for {storage}{' · ' if storage and drawer else ''}{drawer}.")

    def _next_drawer(self):
        if self._ticked and QMessageBox.question(
                self, "Next drawer", f"{len(self._ticked)} ticked specimens are not saved yet. "
                "Move on and drop those ticks?") != QMessageBox.StandardButton.Yes:
            return
        self._ticked.clear()
        self.cmb_drawer.setCurrentText(next_drawer_name(self.cmb_drawer.currentText()))
        self._fill_list()

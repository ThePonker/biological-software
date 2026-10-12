"""
Insect Collection -- "Drawer in hand" (backlog A1, 8 Oct 2026).

Take a drawer out, pick it at the top, tick each specimen as you find it -- the list is
in taxonomic order under genus headings, so it reads in the order the drawer is laid
out -- then Save drawer: a preview of every change, a backup, and one write.

Round 9 C (12 Oct): specimens already recorded in the drawer being edited show ticked;
unticking one and saving takes it out of the drawer. A specimen recorded in another
drawer can be ticked after "Move here" (one at a time, or "Move all here").
"Drawers…" lists every drawer with its count, to open one or empty it.

Records where specimens ARE. Planning a layout is Curator's job; this does not plan.
Rules and the write live in shared/drawer_assign.py (pure, tested).
"""
from __future__ import annotations

import re
import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

import paths
from shared import drawer_assign as da
from shared.fit_to_screen import fit_to_screen

from ...themes import theme
from .drawer_assign_save import DrawerSaveMixin

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


class DrawerAssignDialog(DrawerSaveMixin, QDialog):
    """Pick the drawer in hand; tick what is in it; save."""
    saved = Signal(int)   # number of changes written

    def __init__(self, parent=None, db_path=None):
        super().__init__(parent)
        self.setWindowTitle("Drawer in hand — record what is in a drawer")
        self.resize(1240, 760)
        fit_to_screen(self)    # no taller than a laptop screen (R5)
        self._db = str(db_path or paths.OBSERVATUM_DB)
        self._ticked = set()           # ticked INTO this drawer (not yet recorded here)
        self._unticked = set()         # recorded here, unticked: to be removed on save
        self._move_ok = set()          # recorded in another drawer, "Move here" confirmed
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
        hint = QLabel("Tick each specimen as you find it; untick one to take it out. "
                      "The list is in taxonomic order.")
        hint.setStyleSheet("color: #4b5563; border: none;")
        hint.setWordWrap(True)          # wraps rather than widen the window (R5)
        b.addWidget(hint, 1)
        self.lbl_count = QLabel("0 ticked")
        self.lbl_count.setStyleSheet("font-weight: 600; border: none;")
        b.addWidget(self.lbl_count)
        self.btn_drawers = QPushButton("Drawers…")
        self.btn_drawers.setToolTip("Every drawer in use, with its count: open one, or empty it")
        self.btn_drawers.clicked.connect(self._open_drawers)
        b.addWidget(self.btn_drawers)
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
        self.lbl_scope.setWordWrap(True)
        mv.addWidget(self.lbl_scope)        # own row: the buttons below fit a laptop (R9 fix)
        top.addStretch(0)
        btn_all = QPushButton("Tick all")
        btn_all.setToolTip("Tick every specimen shown in the list")
        btn_all.clicked.connect(lambda: self._tick_shown(True))
        btn_none = QPushButton("Untick all")
        btn_none.setToolTip("Untick every specimen shown in the list")
        btn_none.clicked.connect(lambda: self._tick_shown(False))
        self.btn_move_all = QPushButton("Move all here…")
        self.btn_move_all.setToolTip("Tick the shown specimens recorded in other drawers, "
                                     "to move them into this one")
        self.btn_move_all.clicked.connect(self._move_all_shown)
        top.addWidget(btn_all)
        top.addWidget(btn_none)
        top.addWidget(self.btn_move_all)
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
        also = QLabel("<b>Also set on the ticked specimens</b>")
        also.setWordWrap(True)
        rv.addWidget(also)
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
    def _drawer(self):
        return self.cmb_storage.currentText().strip(), self.cmb_drawer.currentText().strip()

    def _is_ticked(self, s):
        st, dr = self._drawer()
        if da.here(s, st, dr):
            return s["id"] not in self._unticked
        return s["id"] in self._ticked

    def _prune(self):
        """After the drawer changes: keep only the ticks that still mean something."""
        st, dr = self._drawer()
        self._unticked = {i for i in self._unticked if da.here(self._by_id[i], st, dr)}
        self._ticked = {i for i in self._ticked if not da.here(self._by_id[i], st, dr)}

    def _in_scope(self, s):
        if self._filter:
            kind, val = self._filter
            key = {"order": "order_name", "family": "family", "genus": "genus"}[kind]
            if (s.get(key) or "") != val and not (val.startswith("(no ") and not s.get(key)):
                return False
        st, dr = self._drawer()
        if s["id"] in self._ticked or s["id"] in self._unticked or da.here(s, st, dr):
            return True
        return self.chk_placed.isChecked() if da.placed(s) else self.chk_free.isChecked()

    def _fill_list(self):
        if not hasattr(self, "list"):
            return
        self._prune()
        self._building = True
        self.list.clear()
        storage, drawer = self._drawer()
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
            it = QTreeWidgetItem([s["species_name"] or "", s.get("date_collected") or "",
                                  s.get("site_name") or "", s.get("sex") or "", ""])
            f = it.font(0); f.setItalic(True); it.setFont(0, f)
            it.setData(0, ROLE_ID, s["id"])
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                        | Qt.ItemFlag.ItemIsUserCheckable)
            self._style(it, s)
            self.list.addTopLevelItem(it)
        for c in range(1, 5):
            self.list.resizeColumnToContents(c)
        self.list.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        scope = self._filter[1] if self._filter else "All specimens"
        free = sum(1 for s in shown if not da.placed(s))
        self.lbl_scope.setText(f"{scope} — {len(shown):,} shown, {free:,} not yet in a drawer")
        self._building = False
        self._update_summary()

    def _style(self, it, s):
        """Tick box, 'Drawer now' text and greying for one row."""
        storage, drawer = self._drawer()
        away = da.elsewhere(s, storage, drawer)
        now = da.where(s.get("storage_location"), s.get("drawer_number")) or "—"
        ticked = self._is_ticked(s)
        if away and ticked:
            now = f"{now} → moving here"
        elif s["id"] in self._unticked:
            now = f"{now} → to be removed"
        it.setText(4, now)
        it.setCheckState(0, Qt.CheckState.Checked if ticked else Qt.CheckState.Unchecked)
        grey = away and not ticked
        for c in range(5):
            it.setForeground(c, QBrush(QColor(GREY)) if grey else QBrush())
        it.setToolTip(0, f"Recorded in {now}. Tick it to move it to this drawer." if grey else "")

    # ---------------------------------------------------------------- ticking
    def _ask(self, title, text, yes="Move here"):
        """Yes/No question (tests replace this)."""
        box = QMessageBox(QMessageBox.Icon.Question, title, text, parent=self)
        ok = box.addButton(yes, QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is ok

    def _set_tick(self, sid, on, confirm=True):
        """Record one tick; returns whether it took (a move can be declined)."""
        s = self._by_id[sid]
        st, dr = self._drawer()
        if da.here(s, st, dr):
            (self._unticked.discard if on else self._unticked.add)(sid)
            return True
        if not on:
            self._ticked.discard(sid)
            self._move_ok.discard(sid)
            return True
        if da.elsewhere(s, st, dr) and sid not in self._move_ok:
            if not (st or dr):
                QMessageBox.information(self, "Drawer in hand", "Pick the drawer at the top first.")
                return False
            if confirm and not self._ask(
                    "Move here?",
                    f"{s.get('species_name') or 'This specimen'} is recorded in "
                    f"{da.where(s.get('storage_location'), s.get('drawer_number'))}.\n\n"
                    f"Move it to {da.where(st, dr)}?"):
                return False
            self._move_ok.add(sid)
        self._ticked.add(sid)
        return True

    def _on_item_changed(self, item, col):
        if self._building or col != 0:
            return
        sid = item.data(0, ROLE_ID)
        if sid is None:
            return
        on = item.checkState(0) == Qt.CheckState.Checked
        self._set_tick(sid, on)
        self._building = True            # restyle in place (a declined move is unticked again)
        self._style(item, self._by_id[sid])
        self._building = False
        self.list.resizeColumnToContents(4)
        self._update_summary()

    def _shown_ids(self):
        out = []
        for i in range(self.list.topLevelItemCount()):
            sid = self.list.topLevelItem(i).data(0, ROLE_ID)
            if sid is not None:
                out.append(sid)
        return out

    def _tick_shown(self, on):
        """Tick (or untick) every shown specimen; ticking leaves those in other drawers alone
        (use Move all here). Unticking one recorded here takes it out on save."""
        st, dr = self._drawer()
        for sid in self._shown_ids():
            if on and da.elsewhere(self._by_id[sid], st, dr) and sid not in self._move_ok:
                continue
            self._set_tick(sid, on)
        self._fill_list()

    def _move_all_shown(self):
        st, dr = self._drawer()
        ids = [i for i in self._shown_ids()
               if da.elsewhere(self._by_id[i], st, dr) and i not in self._ticked]
        if not ids:
            QMessageBox.information(self, "Drawer in hand",
                                    "None of the shown specimens is recorded in another drawer.")
            return
        if not (st or dr):
            QMessageBox.information(self, "Drawer in hand", "Pick the drawer at the top first.")
            return
        froms = {}
        for i in ids:
            s = self._by_id[i]
            k = da.where(s.get("storage_location"), s.get("drawer_number"))
            froms[k] = froms.get(k, 0) + 1
        detail = "\n".join(f"  from {k}: {n}" for k, n in sorted(froms.items()))
        if not self._ask("Move all shown specimens here?",
                         f"Move {len(ids)} specimens to {da.where(st, dr)}?\n{detail}\n\n"
                         "Nothing is written until you save the drawer.", yes="Move all here"):
            return
        self._move_ok.update(ids)
        self._ticked.update(ids)
        self._fill_list()

    def _contents(self):
        """Ids that will be in this drawer after saving (ticked, in list order)."""
        return [s["id"] for s in self._specs if self._is_ticked(s)]

    def _update_summary(self):
        storage, drawer = self._drawer()
        self.lbl_drawer.setText(da.where(storage, drawer) or "Pick a drawer above")
        ids = self._contents()
        n = len(ids)
        moves = sum(1 for i in self._ticked if da.elsewhere(self._by_id[i], storage, drawer))
        adds = len(self._ticked) - moves
        rem = len(self._unticked)
        extra = ", ".join(x for x in (f"{adds} new" if adds else "", f"{moves} to move" if moves else "",
                                      f"{rem} to remove" if rem else "") if x)
        self.lbl_count.setText(f"{n} in this drawer" + (f" ({extra})" if extra else ""))
        if not n:
            self.lbl_summary.setText("Nothing ticked yet." if not rem else
                                     f"<span style='color:{theme().get('danger')}'>{rem} to remove</span>")
        else:
            by = {}
            for sid in ids:
                g = self._by_id[sid]["genus"]
                by[g] = by.get(g, 0) + 1
            self.lbl_summary.setText(" · ".join(f"<i>{g}</i> {c}" for g, c in by.items())
                                     + f"<br><span style='color:{theme().get('text_secondary')}'>{n} specimens"
                                     + (f"; {extra}" if extra else "") + "</span>")
        self.btn_save.setEnabled(bool(n or rem) and bool(storage or drawer))
        self.btn_save.setText(f"Save drawer ({n}) — preview…")

    def _next_drawer(self):
        if not self._drop_pending("Next drawer"):
            return
        self.cmb_drawer.setCurrentText(next_drawer_name(self.cmb_drawer.currentText()))
        self._fill_list()

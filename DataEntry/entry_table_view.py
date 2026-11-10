"""EntryTableView -- the grid's keyboard-driven table view (split from entry_grid.py, R13)."""
from __future__ import annotations


from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QTableView,
    QStyledItemDelegate, QAbstractItemView, QApplication,
)

from DataEntry.grid_columns import (
    COLUMNS, COLIDX)


def _count_keys():
    """(up, down) key sets for count mode, from QSettings DataEntry/countUpKeys / countDownKeys.

    Defaults: Space, + (main and keypad) and F13 count up; - counts down. A USB foot pedal
    programmed to send any of these works with no other set-up."""
    def parse(name, default):
        try:
            raw = QSettings().value(f"DataEntry/{name}", default, type=str) or default
        except Exception:
            raw = default
        keys = set()
        for part in raw.split(","):
            k = getattr(Qt.Key, "Key_" + part.strip(), None)
            if k is not None:
                keys.add(k)
        return keys or {getattr(Qt.Key, "Key_" + p) for p in default.split(",")}
    return parse("countUpKeys", "Space,Plus,Equal,F13"), parse("countDownKeys", "Minus,Underscore")


class EntryTableView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._clip_rows = None   # internal rich buffer (species dicts preserved)
        self._clip_text = None   # the text we put on the system clipboard at copy time
        self._clip_marker = None  # (r0, r1, c0, c1) of the copied block, for the dashed outline
        # B1 count mode: the page turns it on (button or F9); keys are configurable in QSettings
        # DataEntry/countUpKeys and DataEntry/countDownKeys (Qt key names, e.g. "Space,Plus,F13")
        self.count_mode = False
        self.on_count = None          # callback(row, new_qty)
        self.on_toggle_count = None   # callback() for F9
        self.on_count_done = None     # callback() when Enter ends a count (turns count mode off)
        self._up_keys, self._down_keys = _count_keys()
        # double-click the ROW NUMBER -> species account (a double-click on a cell still edits it)
        self.verticalHeader().sectionDoubleClicked.connect(self._open_species_account)

    def keyPressEvent(self, event):
        k = event.key()
        mods = event.modifiers()
        editing = self.state() == QAbstractItemView.State.EditingState

        if k == Qt.Key.Key_F9 and self.on_toggle_count:
            self.on_toggle_count(); return
        # B1: in count mode the clicker / pedal keys count, and nothing else happens
        if self.count_mode and not editing and not (mods & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            if k in self._up_keys or k in self._down_keys:
                cur = self.currentIndex()
                if cur.isValid():
                    n = self.model().bump_quantity(cur.row(), 1 if k in self._up_keys else -1)
                    if self.on_count:
                        self.on_count(cur.row(), n)
                return

        if mods & Qt.KeyboardModifier.ControlModifier:
            if k == Qt.Key.Key_R:
                self._repeat_row(); return
            if k == Qt.Key.Key_T and not editing:
                self._toggle_check_selected(); return
            if k == Qt.Key.Key_D:
                self._fill_down(); return
            if k == Qt.Key.Key_I and not editing:
                self._open_species_account(self.currentIndex().row()); return
            if k == Qt.Key.Key_C:
                self._copy(); return
            if k == Qt.Key.Key_V:
                self._paste(); return
            if k in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
                self._delete_selected_rows(); return
            if k in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self._insert_selected_rows(); return
            if k == Qt.Key.Key_Home:
                self._go(0, 0); return
            if k == Qt.Key.Key_End:
                self._go(self.model().rowCount() - 1, self.model().columnCount() - 1); return
            # Ctrl+Arrow: Excel-style jump to the next cell with data (only when not editing)
            if not editing and k in (Qt.Key.Key_Up, Qt.Key.Key_Down,
                                     Qt.Key.Key_Left, Qt.Key.Key_Right):
                dr, dc = {Qt.Key.Key_Up: (-1, 0), Qt.Key.Key_Down: (1, 0),
                          Qt.Key.Key_Left: (0, -1), Qt.Key.Key_Right: (0, 1)}[k]
                self._ctrl_move(dr, dc); return

        # Escape clears the copy outline (Excel behaviour) when not editing a cell.
        if k == Qt.Key.Key_Escape and not editing and self._clip_marker:
            self._clear_marker(); return

        # Enter / Shift+Enter -> commit the cell and wrap to the FIRST column (Species) of the
        # next / previous row, like starting a fresh record. Works while editing too.
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (mods & Qt.KeyboardModifier.ControlModifier):
            if self.count_mode and self.on_count_done:
                self.on_count_done()          # the count is already saved; Enter ends count mode
            cur = self.currentIndex()
            if cur.isValid():
                if editing:
                    ed = self.focusWidget()
                    if ed is not None and ed is not self:
                        try:
                            self.commitData(ed)
                            self.closeEditor(ed, QStyledItemDelegate.EndEditHint.NoHint)
                        except Exception:
                            pass
                step = -1 if (mods & Qt.KeyboardModifier.ShiftModifier) else 1
                self._go(cur.row() + step, 0)
            return

        if not editing and k == Qt.Key.Key_Space and not (mods & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            cur = self.currentIndex()
            if cur.isValid() and COLUMNS[cur.column()][2] == "check":
                self.model().toggle_check(cur.row())        # Space on the Check cell
                return

        if not editing:
            # Delete/Backspace clears the selected cell(s)
            if k in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                for ix in (self.selectedIndexes() or [self.currentIndex()]):   # visible rows only
                    if ix.isValid():
                        self.model().setData(ix, "", Qt.ItemDataRole.EditRole)
                return
            # printable key -> start editing and forward it (type to overwrite, Excel-style)
            text = event.text()
            if text and text.isprintable() and not (mods & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
                cur = self.currentIndex()
                if cur.isValid():
                    self.edit(cur)
                    fw = self.focusWidget()
                    if fw is not None and fw is not self:
                        from PySide6.QtGui import QKeyEvent
                        QApplication.sendEvent(fw, QKeyEvent(
                            event.type(), event.key(), event.modifiers(), event.text()))
                    return
        super().keyPressEvent(event)

    def _toggle_check_selected(self):
        """Ctrl+T, from any column: mark the selected rows to check -- or, if every one is
        marked already, take the mark off. Rows hidden by "To check only" are left out."""
        m = self.model()
        rows = [r for r in self._selected_rows() if r < m.real_count()]
        if not rows:
            cur = self.currentIndex()
            rows = [cur.row()] if cur.isValid() and cur.row() < m.real_count() else []
        if not rows or not m.has_check_columns():
            return
        mark = not all(m.is_flagged(r) for r in rows)
        for r in rows:
            if m.is_flagged(r) != mark:
                m.toggle_check(r)

    def mouseDoubleClickEvent(self, event):
        ix = self.indexAt(event.position().toPoint())
        if ix.isValid() and COLUMNS[ix.column()][2] == "check":
            self.model().toggle_check(ix.row())              # double-click on the Check cell
            return
        super().mouseDoubleClickEvent(event)

    def _repeat_row(self):
        """B2 (Ctrl+R): repeat this row's species below it and land on Sex -- for sex splits."""
        if self.state() == QAbstractItemView.State.EditingState:
            ed = self.focusWidget()
            if ed is not None and ed is not self:
                self.commitData(ed)
                self.closeEditor(ed, QStyledItemDelegate.EndEditHint.NoHint)
        cur = self.currentIndex()
        if not cur.isValid():
            return
        new = self.model().repeat_row(cur.row())
        if new is not None:
            self._go(new, COLIDX["sex"])

    def _go(self, row, col):
        m = self.model()
        row = max(0, min(row, m.rowCount() - 1))
        col = max(0, min(col, m.columnCount() - 1))
        self.setCurrentIndex(m.index(row, col))

    def _ctrl_move(self, dr, dc):
        """Excel-style Ctrl+Arrow: jump to the next cell with data in the given direction."""
        m = self.model()
        cur = self.currentIndex()
        if not cur.isValid():
            return
        maxr, maxc = m.rowCount() - 1, m.columnCount() - 1

        def inb(rr, cc):
            return 0 <= rr <= maxr and 0 <= cc <= maxc

        def filled(rr, cc):
            v = m.data(m.index(rr, cc), Qt.ItemDataRole.DisplayRole)
            return v not in (None, "")

        r, c = cur.row(), cur.column()
        if not inb(r + dr, c + dc):
            return
        rr, cc = r, c
        if filled(r, c) and filled(r + dr, c + dc):
            # inside a run -> go to the last filled cell before a gap (or the edge)
            while inb(rr + dr, cc + dc) and filled(rr + dr, cc + dc):
                rr += dr; cc += dc
        else:
            # step over the gap to the next filled cell (or the edge)
            rr += dr; cc += dc
            while inb(rr + dr, cc + dc) and not filled(rr, cc):
                rr += dr; cc += dc
        self._go(rr, cc)

    def _next_visible(self, row: int) -> int:
        """The first row at or after `row` that is not hidden ("To check only")."""
        n = self.model().rowCount()
        while row < n - 1 and self.isRowHidden(row):
            row += 1
        return row

    def move_down_from_editor(self):
        """After an editor commits via Enter, wrap to the first column (Species) of the next row."""
        cur = self.currentIndex()
        if cur.isValid():
            self._go(self._next_visible(cur.row() + 1), 0)

    # -- copy the value of one cell (species carries its whole payload) -------
    def _copy_cell(self, sr, sc, tr, tc):
        m = self.model()
        if COLUMNS[sc][2] == "species":
            m.setData(m.index(tr, tc), m.species_payload(sr), Qt.ItemDataRole.EditRole)
        else:
            v = m.cell_value(sr, sc)
            m.setData(m.index(tr, tc), "" if v is None else v, Qt.ItemDataRole.EditRole)

    # -- Ctrl+D: fill each selected column from its top selected cell ---------
    def _fill_down(self):
        idxs = self.selectedIndexes()          # rows hidden by "To check only" are left out
        if len(idxs) <= 1:
            cur = idxs[0] if idxs else self.currentIndex()
            if cur.isValid() and cur.row() > 0:
                self._copy_cell(cur.row() - 1, cur.column(), cur.row(), cur.column())
            return
        by_col = {}
        for ix in idxs:
            by_col.setdefault(ix.column(), []).append(ix.row())
        for col, rows in by_col.items():
            rows.sort()
            src = rows[0]
            for tgt in rows[1:]:
                self._copy_cell(src, col, tgt, col)

    # -- Ctrl+C: bounding box of the selection -> clipboard (+ rich buffer) ---
    def _selected_rows(self):
        return sorted({i.row() for i in self.selectedIndexes()})   # visible rows only

    def _delete_selected_rows(self):
        """Remove whole rows (Ctrl+-). Rows below shift up; confirms for more than one."""
        rows = self._selected_rows()
        m = self.model()
        real = [r for r in rows if r < len(getattr(m, "_rows", []))]
        if not real:
            return
        if len(real) > 1:
            from PySide6.QtWidgets import QMessageBox
            if QMessageBox.question(
                self, "Delete rows",
                f"Delete {len(real)} rows?\n\nRows below will move up. "
                f"This cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            ) != QMessageBox.StandardButton.Yes:
                return
        from DataEntry.photo_attach import ask_about_photos
        after = ask_about_photos(self, m._conn, [m._rows[r].get("id") for r in real], "Delete rows")
        if after is None:
            return
        n = m.delete_rows(real)
        after()
        failed = getattr(m, "delete_failures", None)
        if failed:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Rows not deleted",
                "These rows could not be deleted and are still in the grid:\n\n"
                + "\n".join(f"Row {n}: {why}" for n, why in sorted(failed)))
        print(f"[DataEntry] deleted {n} row(s)")

    def _insert_selected_rows(self):
        """Insert blank rows above the selection (Ctrl++), one per selected row."""
        rows = self._selected_rows()
        if not rows:
            return
        m = self.model()
        at = rows[0]
        n = m.insert_rows(at, len(rows), inherit=False)
        print(f"[DataEntry] inserted {n} row(s) above row {at + 1}")
        if n:
            self.setCurrentIndex(m.index(at, 0))

    def contextMenuEvent(self, event):
        from PySide6.QtWidgets import QMenu
        rows = self._selected_rows()
        m = self.model()
        real = [r for r in rows if r < len(getattr(m, "_rows", []))]
        if not real:
            return
        menu = QMenu(self)
        if len(real) == 1:
            p_ = m.species_payload(real[0])
            if p_.get("scientific_name") or p_.get("tvk"):
                menu.addAction("Species account\u2026   (Ctrl+I)").triggered.connect(
                    lambda *_a, r_=real[0]: self._open_species_account(r_))
                menu.addSeparator()
        ins = "Insert row above" if len(real) == 1 else f"Insert {len(real)} rows above"
        menu.addAction(ins).triggered.connect(self._insert_selected_rows)
        menu.addSeparator()
        label = "Delete row" if len(real) == 1 else f"Delete {len(real)} rows"
        act = menu.addAction(label)
        act.triggered.connect(self._delete_selected_rows)
        menu.exec(event.globalPos())

    def _open_species_account(self, r=None):
        """The same species account dialog the other tabs open: published accounts above,
        your own account below. Uses the row's TVK; a staged name without one opens read-only."""
        from PySide6.QtWidgets import QMessageBox
        m = self.model()
        if r is None or r < 0:
            r = self.currentIndex().row()
        if not (0 <= r < len(getattr(m, "_rows", []))):
            return
        p = m.species_payload(r)
        if not (p.get("scientific_name") or p.get("tvk")):
            QMessageBox.information(self, "Species account", "This row has no species yet.")
            return
        dlg_cls = None
        import importlib
        for modname in ("src.views.home.species_profile_dialog",
                        "Observatum.src.views.home.species_profile_dialog"):
            try:
                dlg_cls = importlib.import_module(modname).SpeciesProfileDialog
                break
            except Exception:
                continue
        if dlg_cls is None:
            QMessageBox.information(self, "Species account",
                                    "Species accounts open when Data Entry runs inside Observatum.")
            return
        try:
            from DataEntry import bootstrap
            bootstrap.get_database_safe()          # make sure Observatum's database is initialised
        except Exception:
            pass
        data = {
            "scientific_name": p.get("scientific_name"),
            "species_name": p.get("scientific_name"),
            "tvk": p.get("tvk"),
            "common_name": p.get("common_name"),
        }
        try:
            dlg_cls(data, self.window()).exec()
        except Exception as e:
            QMessageBox.warning(self, "Species account", f"Could not open the species account:\n\n{e}")

    def _copy(self):
        idxs = self.selectedIndexes()          # rows hidden by "To check only" are left out
        if not idxs:
            cur = self.currentIndex()
            if not cur.isValid():
                return
            idxs = [cur]
        rows = sorted({ix.row() for ix in idxs})
        cols = sorted({ix.column() for ix in idxs})
        m = self.model()
        text_lines, rich = [], []
        for r in rows:
            tcells, rcells = [], []
            for c in cols:
                if COLUMNS[c][2] == "species":
                    payload = m.species_payload(r)
                    rcells.append(payload)
                    tcells.append(payload.get("scientific_name") or "")
                else:
                    v = m.cell_value(r, c)
                    s = "" if v is None else str(v)
                    rcells.append(s)
                    tcells.append(s)
            text_lines.append("\t".join(tcells))
            rich.append(rcells)
        text = "\n".join(text_lines)
        QApplication.clipboard().setText(text)
        self._clip_rows = rich
        self._clip_text = text
        self._clip_cols = cols
        self._clip_marker = (rows[0], rows[-1], cols[0], cols[-1]) if rows and cols else None
        self.viewport().update()

    def _clipboard_grid(self):
        text = QApplication.clipboard().text()
        if self._clip_rows is not None and self._clip_text == text:
            return self._clip_rows  # rich (species dicts preserved for in-app paste)
        if not text:
            return []
        lines = [ln.rstrip("\r") for ln in text.split("\n")]
        while lines and lines[-1] == "":
            lines.pop()
        return [ln.split("\t") for ln in lines]

    # -- Ctrl+V: paste block anchored at the current cell --------------------
    def _clear_marker(self):
        if self._clip_marker is not None:
            self._clip_marker = None
            self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._clip_marker:
            return
        from PySide6.QtGui import QPainter, QPen, QColor
        r0, r1, c0, c1 = self._clip_marker
        m = self.model()
        if m is None or r1 >= m.rowCount() or c1 >= m.columnCount():
            return
        tl = self.visualRect(m.index(r0, c0))
        br = self.visualRect(m.index(r1, c1))
        rect = tl.united(br).adjusted(0, 0, -1, -1)
        p = QPainter(self.viewport())
        pen = QPen(QColor(74, 124, 89), 2, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawRect(rect)
        p.end()

    def _paste(self):
        grid = self._clipboard_grid()
        if not grid:
            return
        m = self.model()
        sel = [i for i in self.selectedIndexes() if i.isValid()]

        # single value + multi-cell selection -> fill the whole selection
        if len(grid) == 1 and len(grid[0]) == 1 and len(sel) > 1:
            val = grid[0][0]
            m.ensure_rows(max(i.row() for i in sel) + 1)
            unresolved, done = [], {}
            for idx in sel:
                v = val
                if idx.column() not in done:
                    done[idx.column()] = self._resolve_pasted(idx.column(), val, unresolved)
                v = done[idx.column()]
                m.setData(m.index(idx.row(), idx.column()), v, Qt.ItemDataRole.EditRole)
            self._report_unresolved(unresolved[:1])
            return

        if sel:
            r0 = min(i.row() for i in sel)
            c0 = min(i.column() for i in sel)
        else:
            cur = self.currentIndex()
            if not cur.isValid():
                return
            r0, c0 = cur.row(), cur.column()

        # the rows it lands on: visible ones only, so "To check only" never pastes into rows
        # it hides; the columns: a block that starts outside Check / Check note skips them, so
        # a block copied from a sheet laid out like the grid before 16 Oct lands where it did
        rows, r = [], r0
        while len(rows) < len(grid):
            m.ensure_rows(r + 1)
            if not self.isRowHidden(r):
                rows.append(r)
            r += 1
        check_keys = ("check_flag", "check_note")
        cols = [c for c in range(c0, m.columnCount())
                if c == c0 or COLUMNS[c0][0] in check_keys or COLUMNS[c][0] not in check_keys]
        unresolved = []
        for i, rowvals in enumerate(grid):
            for j, val in enumerate(rowvals):
                if j >= len(cols):
                    break
                c = cols[j]
                val = self._resolve_pasted(c, val, unresolved)
                m.setData(m.index(rows[i], c), val, Qt.ItemDataRole.EditRole)
        self._report_unresolved(unresolved)

    def _resolve_pasted(self, c, val, unresolved):
        """B4: a pasted species name goes through the same rules as a typed one -- matched to
        its TVK when that is certain, otherwise kept as text and listed (never guessed)."""
        if COLUMNS[c][2] != "species" or not isinstance(val, str) or not val.strip():
            return val
        delegate = self.itemDelegateForColumn(c)
        if not hasattr(delegate, "decide"):
            return val
        action, payload = delegate.decide(val.strip(), interactive=False)
        if action == "fill":
            return payload
        unresolved.append(val.strip())
        return {"scientific_name": val.strip()}

    def _report_unresolved(self, names):
        if not names:
            return
        from PySide6.QtWidgets import QMessageBox
        uniq = list(dict.fromkeys(names))
        QMessageBox.information(
            self, "Pasted names to check",
            f"{len(names)} pasted name(s) did not match one species for certain and are kept as "
            "text with no TVK:\n\n  " + "\n  ".join(uniq[:15])
            + ("\n  ..." if len(uniq) > 15 else "")
            + "\n\nType over each one to choose the species (the commit check lists any left).")

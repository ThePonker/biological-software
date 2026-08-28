"""entry_grid -- the editable grid over a job's entry_staging rows.

Species entry uses a cell-tailored popup (Qt.ToolTip list, keyboard-first) that mirrors the
proven Session-25 pattern rather than embedding the composite SpeciesSearch widget (which
fights Qt's cell-editor lifecycle). Falls back to a plain text cell when no search service.

Excel-isms: text is selected when a cell starts editing (type to overwrite), Delete/Backspace
clears the selected cell, Tab off the last cell adds a row. Columns are resizable.
Write-through: edits persist to entry_staging immediately.
"""
from __future__ import annotations

import sqlite3
from typing import List, Dict, Optional

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QTimer, QEvent, QPoint, Signal, QSettings
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableView,
    QStyledItemDelegate, QComboBox, QSpinBox, QAbstractItemView, QHeaderView,
    QLineEdit, QListWidget, QListWidgetItem, QDialog, QDialogButtonBox, QApplication,
    QFileDialog, QMessageBox, QCheckBox, QDateEdit,
)

from DataEntry import theme
from DataEntry import staging_repo as repo
from DataEntry.session_header import load_stages, load_sexes, load_methods

# (key, header, kind, width). Default order per Wil: Species, No., Sex, Stage, then context.
COLUMNS = [
    ("species_name", "Species", "species", 200),
    ("quantity", "No.", "number", 52),
    ("sex", "Sex", "sex", 78),
    ("stage", "Stage", "stage", 90),
    ("grid_ref", "Grid ref", "text", 95),
    ("method", "Method", "method", 120),
    ("date", "Date", "text", 100),
    ("sub_location", "Sub-location", "text", 120),
    ("trap_number", "Trap", "text", 70),
    ("visit_number", "Visit", "text", 60),
    ("comment", "Comment", "text", 100),
    ("vc_number", "VC No.", "number", 60),
    ("vice_county", "VC", "text", 60),
    ("recorder", "Recorder", "text", 110),
    ("determiner", "Determiner", "text", 110),
    ("common_name", "Common Name", "text", 120),
    ("order_name", "Order", "text", 110),
    ("family", "Family", "text", 130),
    ("site_name", "Site", "text", 100),
]

COLIDX = {key: i for i, (key, _, _, _) in enumerate(COLUMNS)}

DEFAULT_DISPLAY_ROWS = 1000  # blank rows shown when a job opens (spreadsheet-style canvas)


class StagingTableModel(QAbstractTableModel):
    def __init__(self, conn: sqlite3.Connection, job_id: int, vc_service=None, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._job_id = job_id
        self._vc_service = vc_service
        self._rows: List[Dict] = repo.fetch_rows(conn, job_id)
        self._min_display = DEFAULT_DISPLAY_ROWS
        self._copy_context = True  # tickbox: fill empty context cells from the nearest row above
        self._entry_recorder = ""   # from the Recorder box (applied on species match)
        self._entry_determiner = ""  # from the Determiner box

    def set_entry_defaults(self, recorder: str, determiner: str) -> None:
        self._entry_recorder = (recorder or "").strip()
        self._entry_determiner = (determiner or "").strip()

    # context fields copied down on a species match (never Certainty -- that's a fixed constant)
    _CONTEXT_COPY_KEYS = ("date", "grid_ref", "site_name",
                          "recorder", "determiner", "method",
                          "sub_location", "trap_number", "visit_number")

    def set_copy_context(self, on: bool) -> None:
        self._copy_context = bool(on)

    def _nearest_above(self, r: int, key: str):
        """Nearest non-empty value for `key` in a row above r (skips blank gap rows)."""
        for i in range(r - 1, -1, -1):
            v = self._rows[i].get(key)
            if v not in (None, ""):
                return v
        return None

    def rowCount(self, parent=QModelIndex()):
        # at least _min_display rows on screen; always one blank past the real data
        return 0 if parent.isValid() else max(len(self._rows) + 1, self._min_display)

    def real_count(self) -> int:
        return len(self._rows)

    def records_entered(self) -> int:
        return sum(1 for row in self._rows if (row.get("species_name") or "").strip())

    _MEANINGFUL = ("species_name", "quantity", "sex", "stage", "determiner", "sub_location",
                   "trap_number", "visit_number", "date", "site_name", "grid_ref",
                   "vice_county", "recorder", "method", "comment")

    def trim_empty_tail(self) -> int:
        """Delete trailing real rows that are completely empty (e.g. from over-scrolling)."""
        removed = 0
        def _empty(row):
            return not any((row.get(k) not in (None, "")) for k in self._MEANINGFUL)
        while self._rows and _empty(self._rows[-1]):
            old_total = self.rowCount()
            rid = self._rows[-1]["id"]
            new_total = max(len(self._rows), self._min_display)  # after pop, len-1+1
            if new_total < old_total:
                self.beginRemoveRows(QModelIndex(), old_total - 1, old_total - 1)
                repo.delete_row(self._conn, rid); self._rows.pop()
                self.endRemoveRows()
            else:
                repo.delete_row(self._conn, rid); self._rows.pop()
                r = len(self._rows)
                self.dataChanged.emit(self.index(r, 0), self.index(r, self.columnCount() - 1))
                self.headerDataChanged.emit(Qt.Orientation.Vertical, r, self.rowCount() - 1)
            removed += 1
        return removed

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return COLUMNS[section][1]
        if section == len(self._rows):
            return "*"  # the new-row marker, spreadsheet-style
        return str(section + 1)

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return (Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEditable)

    def insert_rows(self, at: int, count: int = 1, inherit: bool = True) -> int:
        """Insert count blank rows above view index t, renumbering row_order below.

        New rows inherit the context fields (date, site, grid ref, trap, etc.) of the row
        above, since insertion happens inside a block that shares them.
        """
        at = max(0, min(at, len(self._rows)))
        ctx = {}
        if inherit and at > 0:
            src = self._rows[at - 1]
            for k in self._CONTEXT_COPY_KEYS:
                v = src.get(k)
                if v not in (None, ""):
                    ctx[k] = v

        self.beginResetModel()
        made = []
        for _ in range(count):
            new_id = repo.insert_row(self._conn, self._job_id, dict(ctx))
            fresh = {c[0]: None for c in COLUMNS}
            fresh.update(ctx)
            fresh["id"] = new_id
            made.append(fresh)
        for i, row in enumerate(made):
            self._rows.insert(at + i, row)
        for i, row in enumerate(self._rows, start=1):
            if row.get("id") is not None:
                self._conn.execute(
                    "UPDATE entry_staging SET row_order=? WHERE id=?", (i, row["id"]))
        self._conn.commit()
        self.endResetModel()
        return len(made)

    def delete_rows(self, rows) -> int:
        """Delete real staging rows by view index. Virtual rows are ignored. Returns count."""
        targets = sorted({r for r in rows if 0 <= r < len(self._rows)}, reverse=True)
        if not targets:
            return 0
        self.beginResetModel()
        done = 0
        for r in targets:
            row = self._rows[r]
            rid = row.get("id")
            if rid is not None:
                try:
                    repo.delete_row(self._conn, rid)
                except Exception:
                    continue
            del self._rows[r]
            done += 1
        self.endResetModel()
        return done

    def sort_rows(self, column: int, descending: bool = False) -> None:
        """Sort the real staging rows in place. Blanks always go last; nothing is written."""
        key = COLUMNS[column][0]
        kind = COLUMNS[column][2]

        def sort_key(row):
            v = row.get(key)
            blank = v is None or str(v).strip() == ""
            if blank:
                return (1, "")            # blanks last, either direction
            if kind == "number":
                try:
                    return (0, float(v))
                except (TypeError, ValueError):
                    return (0, 0.0)
            return (0, str(v).strip().lower())

        real = [r for r in self._rows if r.get("species_name") or r.get("id")]
        blanks = [r for r in self._rows if r not in real]
        try:
            real.sort(key=sort_key, reverse=descending)
        except TypeError:
            real.sort(key=lambda r: (sort_key(r)[0], str(sort_key(r)[1])), reverse=descending)
        self.beginResetModel()
        self._rows = real + blanks
        self.endResetModel()

    def restore_entry_order(self) -> None:
        """Re-read the job's rows in their stored row_order."""
        self.beginResetModel()
        self._rows = repo.fetch_rows(self._conn, self._job_id)
        self.endResetModel()

    def _is_virtual(self, r: int) -> bool:
        return r >= len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return None
        if self._is_virtual(index.row()):
            return ""
        key = COLUMNS[index.column()][0]
        val = self._rows[index.row()].get(key)
        if key == "date":
            from DataEntry import date_utils
            return date_utils.to_display(val)  # show/edit as dd/mm/yyyy; stored as ISO
        return "" if val is None else str(val)

    def _materialize_to(self, r: int) -> None:
        """Ensure row index r is a real staging row, creating blank rows up to it if needed.

        Rows below the last real row stay virtual (unstored). In-region gaps become real empty
        rows -- correct spreadsheet behaviour; they're skipped on commit.
        """
        if r < len(self._rows):
            return
        old_total = self.rowCount()
        first_new = len(self._rows)
        for _ in range(first_new, r + 1):
            new_id = repo.insert_row(self._conn, self._job_id, {})
            fresh = {c[0]: None for c in COLUMNS}
            fresh["id"] = new_id
            self._rows.append(fresh)
        new_total = self.rowCount()
        if new_total > old_total:
            self.beginInsertRows(QModelIndex(), old_total, new_total - 1)
            self.endInsertRows()
        self.dataChanged.emit(self.index(first_new, 0), self.index(r, self.columnCount() - 1))
        self.headerDataChanged.emit(Qt.Orientation.Vertical, first_new, self.rowCount() - 1)

    def add_display_rows(self, n: int) -> None:
        """Grow the visible blank canvas by n rows (no DB writes -- they're virtual until typed)."""
        old = self.rowCount()
        base = max(self._min_display, len(self._rows) + 1)
        self._min_display = base + n
        new = self.rowCount()
        if new > old:
            self.beginInsertRows(QModelIndex(), old, new - 1)
            self.endInsertRows()

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        r = index.row()
        key, _, kind, _ = COLUMNS[index.column()]
        virtual = self._is_virtual(r)

        # species picked from the popup arrives as a dict -> expand all taxon fields at once
        if kind == "species" and isinstance(value, dict):
            name = value.get("scientific_name")
            if virtual and not name:
                return True  # nothing meaningful -> don't materialise
            if virtual:
                self._materialize_to(r)
            row = self._rows[r]
            updates = {
                "species_name": name,
                "species_tvk": value.get("tvk"),
                "common_name": value.get("common_name"),
                "order_name": value.get("order"),
                "family": value.get("family"),
                "taxon_rank": value.get("rank"),
            }
            row.update(updates)
            repo.update_row(self._conn, row["id"], updates)
            changed_cols = [index.column()]
            if name:
                ctx = {}
                # Recorder / Determiner: box wins over row-above; never overwrite a typed cell
                for k, boxval in (("recorder", self._entry_recorder),
                                  ("determiner", self._entry_determiner)):
                    if row.get(k) in (None, ""):
                        if boxval:
                            ctx[k] = boxval
                        elif self._copy_context:
                            v = self._nearest_above(r, k)
                            if v not in (None, ""):
                                ctx[k] = v
                # other context fields: nearest row above only (when copy-context on)
                if self._copy_context:
                    for k in self._CONTEXT_COPY_KEYS:
                        if k in ("recorder", "determiner"):
                            continue
                        if row.get(k) in (None, ""):
                            v = self._nearest_above(r, k)
                            if v not in (None, ""):
                                ctx[k] = v
                if ctx:
                    row.update(ctx)
                    repo.update_row(self._conn, row["id"], ctx)
                    changed_cols += [COLIDX[k] for k in ctx if k in COLIDX]
                    if "grid_ref" in ctx:
                        self._derive_vc(r)   # VC always from the ref, never copied down
                        changed_cols += [COLIDX[k] for k in ("vice_county", "vc_number")
                                         if k in COLIDX]
            lo, hi = min(changed_cols), max(changed_cols)
            self.dataChanged.emit(self.index(r, lo), self.index(r, hi),
                                  [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
            return True

        if kind == "species" and not str(value or "").strip() and not virtual:
            row = self._rows[r]
            clears = {"species_name": None, "species_tvk": None, "common_name": None,
                      "order_name": None, "family": None, "taxon_rank": None}
            row.update(clears)
            repo.update_row(self._conn, row["id"], clears)
            self.dataChanged.emit(self.index(r, 0),
                                  self.index(r, self.columnCount() - 1),
                                  [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
            return True

        if kind == "number":
            sval = str(value).strip()
            newv = None if sval == "" else self._as_qty(sval)
        elif key == "date":
            from DataEntry import date_utils
            newv = (date_utils.normalise(str(value).strip()) or None)
        else:
            newv = (str(value).strip() or None)

        if virtual:
            if newv in (None, ""):
                return True  # don't materialise on an empty edit (e.g. Delete)
            self._materialize_to(r)

        row = self._rows[r]
        if row.get(key) == newv:
            return True
        row[key] = newv
        repo.update_row(self._conn, row["id"], {key: newv})
        idx = self.index(r, index.column())
        self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
        if key == "grid_ref":
            self._derive_vc(r)
        return True

    def _derive_vc(self, r: int):
        """Auto-fill VC from the row's grid ref via the VC service (no clobber if lookup fails)."""
        if not self._vc_service or not (0 <= r < len(self._rows)):
            return
        row = self._rows[r]
        gr = (row.get("grid_ref") or "").strip()
        if not gr:
            return
        try:
            res = self._vc_service.get_vc_from_grid_ref(gr)
        except Exception:
            res = None
        if not res:
            return
        vc_num, vc_name = res
        updates = {"vice_county": vc_name, "vc_number": vc_num}
        row.update(updates)
        repo.update_row(self._conn, row["id"], updates)
        cols = [COLIDX[k] for k in ("vice_county", "vc_number") if k in COLIDX]
        if cols:
            self.dataChanged.emit(self.index(r, min(cols)), self.index(r, max(cols)),
                                  [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

    @staticmethod
    def _as_qty(sval: str) -> int:
        try:
            return max(1, int(sval))
        except (TypeError, ValueError):
            return 1

    def add_row(self, data: Optional[Dict] = None) -> int:
        new_id = repo.insert_row(self._conn, self._job_id, data or {})
        fresh = {c[0]: None for c in COLUMNS}
        fresh["id"] = new_id
        if data:
            fresh.update(data)
        r = len(self._rows)
        self.beginInsertRows(QModelIndex(), r, r)
        self._rows.append(fresh)
        self.endInsertRows()
        return new_id

    def remove_row(self, r: int) -> None:
        if not (0 <= r < len(self._rows)):
            return
        row_id = self._rows[r]["id"]
        self.beginRemoveRows(QModelIndex(), r, r)
        del self._rows[r]
        self.endRemoveRows()
        repo.delete_row(self._conn, row_id)

    def row_id(self, r: int):
        return self._rows[r]["id"] if 0 <= r < len(self._rows) else None

    # -- helpers for fill-down / copy / paste --------------------------------
    def species_payload(self, r: int) -> Dict:
        if 0 <= r < len(self._rows):
            row = self._rows[r]
            return {
                "scientific_name": row.get("species_name"),
                "tvk": row.get("species_tvk"),
                "common_name": row.get("common_name"),
                "family": row.get("family"),
                "order": row.get("order_name"),
                "rank": row.get("taxon_rank"),
            }
        return {"scientific_name": None, "tvk": None, "common_name": None,
                "family": None, "order": None, "rank": None}

    def cell_value(self, r: int, c: int):
        key = COLUMNS[c][0]
        if 0 <= r < len(self._rows):
            return self._rows[r].get(key)
        return None

    def ensure_rows(self, count: int) -> None:
        """Materialise real rows until there are at least `count` of them."""
        if count > 0:
            self._materialize_to(count - 1)

    def row_dict(self, r: int) -> Optional[Dict]:
        """A copy of a real row's fields (None for the trailing virtual row)."""
        if 0 <= r < len(self._rows):
            return dict(self._rows[r])
        return None


def _select_all(editor):
    if isinstance(editor, QLineEdit):
        editor.selectAll()
    elif isinstance(editor, QSpinBox):
        editor.selectAll()
    elif isinstance(editor, QComboBox) and editor.lineEdit() is not None:
        editor.lineEdit().selectAll()


class _EnterMovesDown:
    """Mixin: pressing Enter in an editor commits the cell and moves DOWN a row (Excel-style).

    If a combo's dropdown popup is open, Enter is left to the combo (to pick the item) instead.
    """
    def eventFilter(self, editor, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.KeyPress and event.key() in (
            Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if isinstance(editor, QComboBox) and editor.view().isVisible():
                return super().eventFilter(editor, event)  # let the popup take Enter
            self.commitData.emit(editor)
            self.closeEditor.emit(editor)
            view = self.parent()
            mover = getattr(view, "move_down_from_editor", None)
            if callable(mover):
                mover()
            return True
        return super().eventFilter(editor, event)


class _TextDelegate(_EnterMovesDown, QStyledItemDelegate):
    """Plain text cell, but selects existing text on edit so you can type over it."""
    def setEditorData(self, editor, index):
        super().setEditorData(editor, index)
        _select_all(editor)


class _OptionDelegate(_EnterMovesDown, QStyledItemDelegate):
    def __init__(self, options, parent=None, default=""):
        super().__init__(parent)
        self._options = list(options)
        self._default = default

    def createEditor(self, parent, option, index):
        cb = QComboBox(parent)
        cb.setEditable(True)
        cb.addItem("")
        cb.addItems([str(o) for o in self._options])
        return cb

    def setEditorData(self, editor, index):
        editor.setCurrentText(index.data(Qt.ItemDataRole.EditRole) or self._default)
        _select_all(editor)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class _NumberDelegate(_EnterMovesDown, QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        sp = QSpinBox(parent)
        sp.setRange(1, 100000)
        sp.setValue(1)
        return sp

    def setEditorData(self, editor, index):
        try:
            editor.setValue(int(index.data(Qt.ItemDataRole.EditRole)))
        except (TypeError, ValueError):
            editor.setValue(1)
        _select_all(editor)

    def setModelData(self, editor, model, index):
        editor.interpretText()
        model.setData(index, editor.value(), Qt.ItemDataRole.EditRole)


def rank_matches(text, results):
    """Sort matches so genus+epithet prefix hits float to the top (Wil's option b),
    while still showing everything Tabella's fuzzy match would."""
    tokens = [t for t in (text or "").lower().split() if t]

    def score(r):
        name = (r.get("scientific_name") or "").lower()
        words = name.split()
        if not tokens:
            return 3
        # tier 0: tokens are ordered prefixes of successive name words (rut mac -> Rutpela maculata)
        if len(tokens) <= len(words) and all(words[i].startswith(tokens[i]) for i in range(len(tokens))):
            return 0
        # tier 1: every token is a prefix of some word (any order)
        if all(any(w.startswith(t) for w in words) for t in tokens):
            return 1
        # tier 2: first token prefixes the genus
        if words and words[0].startswith(tokens[0]):
            return 2
        return 3

    return sorted(
        results,
        key=lambda r: (score(r), 0 if r.get("is_recorded") else 1, (r.get("scientific_name") or "")),
    )


def _to_species_dict(r):
    return {
        "scientific_name": r.get("scientific_name"),
        "tvk": r.get("tvk"),
        "common_name": r.get("common_name"),
        "family": r.get("family"),
        "order": r.get("order"),
        "rank": r.get("rank"),
    }


class _PickList(QListWidget):
    """List for the picker: digits 1-9 quick-pick, Enter activates current."""
    def keyPressEvent(self, event):
        k = event.key()
        if Qt.Key.Key_1 <= k <= Qt.Key.Key_9:
            idx = k - Qt.Key.Key_1
            if idx < self.count():
                self.setCurrentRow(idx)
                self.itemActivated.emit(self.item(idx))
                return
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            it = self.currentItem()
            if it:
                self.itemActivated.emit(it)
                return
        super().keyPressEvent(event)


class SpeciesPickerDialog(QDialog):
    """Tabella-style pick box: shown only when 2+ matches. Keyboard-first."""
    def __init__(self, term, results, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Species lookup")
        self.setMinimumWidth(460)
        self.chosen = None
        self.setStyleSheet(theme.input_qss())

        v = QVBoxLayout(self)
        lbl = QLabel(f"Multiple matches for \u201c{term}\u201d \u2014 choose one:")
        lbl.setStyleSheet(f"color: {theme.INK}; font-size: 13px;")
        lbl.setWordWrap(True)
        v.addWidget(lbl)

        self.listw = _PickList()
        self.listw.setStyleSheet(
            f"QListWidget {{ background: {theme.CARD}; border: 1px solid {theme.LINE};"
            f" font-size: 13px; outline: none; }}"
            f"QListWidget::item {{ padding: 4px 6px; }}"
            f"QListWidget::item:selected {{ background: {theme.SLATE}; color: {theme.PAPER}; }}"
        )
        for i, r in enumerate(results[:50], 1):
            label = f"{i}.  {r.get('scientific_name', '')}"
            cn = r.get("common_name")
            fam = r.get("family")
            if cn:
                label += f"   ({cn})"
            if fam:
                label += f"   [{fam}]"
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, r)
            self.listw.addItem(it)
        self.listw.setCurrentRow(0)
        self.listw.itemActivated.connect(self._accept_item)
        self.listw.itemDoubleClicked.connect(self._accept_item)
        v.addWidget(self.listw)

        hint = QLabel("Up/Down + Enter, type the number, or double-click. Esc to cancel.")
        hint.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        v.addWidget(hint)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept_current)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)
        self.listw.setFocus()

    def _accept_item(self, item):
        self.chosen = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _accept_current(self):
        it = self.listw.currentItem()
        if it:
            self._accept_item(it)


class SpeciesCascadeDelegate(_EnterMovesDown, QStyledItemDelegate):
    """Type a name; on commit run Tabella's cascade:
       exact -> fill silent; one fuzzy -> fill silent; 2+ -> modal picker; none -> unresolved.
    """
    def __init__(self, search_service, parent=None):
        super().__init__(parent)
        self._service = search_service

    def createEditor(self, parent, option, index):
        return QLineEdit(parent)

    def setEditorData(self, editor, index):
        editor.setText(index.data(Qt.ItemDataRole.EditRole) or "")
        editor.selectAll()
        editor._original = index.data(Qt.ItemDataRole.EditRole) or ""

    def _resolve(self, text):
        try:
            return list(self._service.search_species(text, limit=25) or [])
        except Exception:
            return []

    def decide(self, text):
        """Return one of: ('fill', dict) | ('pick', ranked_list) | ('unresolved', text)."""
        if not self._service:
            return ("unresolved", text)
        ranked = rank_matches(text, self._resolve(text))
        exact = next((r for r in ranked
                      if (r.get("scientific_name") or "").lower() == text.lower()), None)
        if exact:
            return ("fill", _to_species_dict(exact))
        if len(ranked) == 1:
            return ("fill", _to_species_dict(ranked[0]))
        if len(ranked) >= 2:
            return ("pick", ranked)
        return ("unresolved", text)

    def setModelData(self, editor, model, index):
        text = editor.text().strip()
        original = (getattr(editor, "_original", "") or "")
        if text == original:
            return
        if not text:
            model.setData(index, {"scientific_name": None}, Qt.ItemDataRole.EditRole)
            return
        action, payload = self.decide(text)
        if action == "fill":
            model.setData(index, payload, Qt.ItemDataRole.EditRole)
        elif action == "pick":
            parent = self.parent()
            dlg = SpeciesPickerDialog(text, payload, parent if isinstance(parent, QWidget) else None)
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.chosen:
                model.setData(index, _to_species_dict(dlg.chosen), Qt.ItemDataRole.EditRole)
            else:
                model.setData(index, {"scientific_name": text}, Qt.ItemDataRole.EditRole)  # unresolved
        else:  # unresolved
            model.setData(index, {"scientific_name": text}, Qt.ItemDataRole.EditRole)


class EntryTableView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._clip_rows = None   # internal rich buffer (species dicts preserved)
        self._clip_text = None   # the text we put on the system clipboard at copy time
        self._clip_marker = None  # (r0, r1, c0, c1) of the copied block, for the dashed outline

    def keyPressEvent(self, event):
        k = event.key()
        mods = event.modifiers()
        editing = self.state() == QAbstractItemView.State.EditingState

        if mods & Qt.KeyboardModifier.ControlModifier:
            if k == Qt.Key.Key_D:
                self._fill_down(); return
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

        if not editing:
            # Delete/Backspace clears the selected cell(s)
            if k in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                for ix in (self.selectionModel().selectedIndexes() or [self.currentIndex()]):
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

    def move_down_from_editor(self):
        """After an editor commits via Enter, wrap to the first column (Species) of the next row."""
        cur = self.currentIndex()
        if cur.isValid():
            self._go(cur.row() + 1, 0)

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
        m = self.model()
        idxs = self.selectionModel().selectedIndexes()
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
        return sorted({i.row() for i in self.selectionModel().selectedIndexes()})

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
        n = m.delete_rows(real)
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
        ins = "Insert row above" if len(real) == 1 else f"Insert {len(real)} rows above"
        menu.addAction(ins).triggered.connect(self._insert_selected_rows)
        menu.addSeparator()
        label = "Delete row" if len(real) == 1 else f"Delete {len(real)} rows"
        act = menu.addAction(label)
        act.triggered.connect(self._delete_selected_rows)
        menu.exec(event.globalPos())

    def _copy(self):
        idxs = self.selectionModel().selectedIndexes()
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
            for idx in sel:
                m.setData(m.index(idx.row(), idx.column()), val, Qt.ItemDataRole.EditRole)
            return

        if sel:
            r0 = min(i.row() for i in sel)
            c0 = min(i.column() for i in sel)
        else:
            cur = self.currentIndex()
            if not cur.isValid():
                return
            r0, c0 = cur.row(), cur.column()

        m.ensure_rows(r0 + len(grid))
        for i, rowvals in enumerate(grid):
            for j, val in enumerate(rowvals):
                c = c0 + j
                if c >= m.columnCount():
                    break
                m.setData(m.index(r0 + i, c), val, Qt.ItemDataRole.EditRole)


class ExportOptionsDialog(QDialog):
    """Ask whether to clear the job after exporting it to CSV."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export to CSV")
        self.setMinimumWidth(340)
        self.setStyleSheet(theme.input_qss())
        v = QVBoxLayout(self)
        intro = QLabel("Export this job's rows to a CSV file.")
        intro.setStyleSheet(f"color: {theme.INK}; font-size: 13px;")
        intro.setWordWrap(True)
        v.addWidget(intro)
        self.chk_clear = QCheckBox("Clear the job after export")
        self.chk_clear.setChecked(True)  # default: export-and-discard (unchanged behaviour)
        v.addWidget(self.chk_clear)
        hint = QLabel("Untick to keep the job open and its rows intact.")
        hint.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        hint.setWordWrap(True)
        v.addWidget(hint)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def clear_after(self) -> bool:
        return self.chk_clear.isChecked()


class EmbargoDialog(QDialog):
    """Choose whether to embargo a commercial job at commit -- 'no embargo' is a clear option."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Embargo")
        self.setMinimumWidth(360)
        self.setStyleSheet(theme.input_qss())
        from PySide6.QtCore import QDate
        from PySide6.QtWidgets import QRadioButton, QButtonGroup
        v = QVBoxLayout(self)

        intro = QLabel("Hold these records from iRecord until a date, or release with no embargo?")
        intro.setStyleSheet(f"color: {theme.INK}; font-size: 13px;")
        intro.setWordWrap(True)
        v.addWidget(intro)

        self.rb_none = QRadioButton("No embargo (available immediately)")
        self.rb_embargo = QRadioButton("Embargo until:")
        grp = QButtonGroup(self)
        grp.addButton(self.rb_none)
        grp.addButton(self.rb_embargo)

        v.addWidget(self.rb_none)
        row = QHBoxLayout()
        row.addWidget(self.rb_embargo)
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("yyyy-MM-dd")
        self.date.setDate(QDate.currentDate().addYears(2))
        row.addWidget(self.date)
        row.addStretch(1)
        v.addLayout(row)

        self.rb_embargo.toggled.connect(self.date.setEnabled)
        self.rb_none.setChecked(True)   # default: no embargo, chosen deliberately
        self.date.setEnabled(False)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def value(self):
        if self.rb_embargo.isChecked():
            return self.date.date().toString("yyyy-MM-dd")
        return None


class EntryGridPage(QWidget):
    finished = Signal()  # emitted after a successful commit / export / discard
    committed = Signal(int)  # emitted after a successful commit, with the number written

    def __init__(self, conn: sqlite3.Connection, job_id: int, search_service=None,
                 codex_path=None, commit_cb=None, vc_service=None, geojson_path=None,
                 tiles_dir=None, maps_dir=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._conn = conn
        self._job_id = job_id
        self._service = search_service
        self._codex_path = codex_path
        self._commit_cb = commit_cb
        self._vc_service = vc_service
        self._geojson_path = geojson_path
        self._tiles_dir = tiles_dir
        self._maps_dir = maps_dir
        self._job = repo.get_job(conn, job_id) or {"id": job_id, "mode": "Personal", "name": ""}
        self._stages, _ = load_stages()
        self._sexes, _ = load_sexes()
        self._methods, _ = load_methods()
        self._model = StagingTableModel(conn, job_id, vc_service, self)
        self._build_ui()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        # live info panel (display only) -- species / conservation / recording history
        from DataEntry.info_panel import InfoService, InfoPanel
        self._info_svc = InfoService(self._conn, self._codex_path)
        try:
            from DataEntry.species_dist_map import DistributionService
            self._dist_svc = DistributionService(self._conn, self._vc_service)
        except Exception:
            self._dist_svc = None
        self._info = InfoPanel(self._info_svc, self._vc_service, self._geojson_path,
                               self._tiles_dir, dist_service=self._dist_svc, maps_dir=self._maps_dir)
        v.addWidget(self._info)

        self._view = EntryTableView()
        self._view.setModel(self._model)
        self._view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self._view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._view.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed  # F2
        )
        # resizable, sensible default widths
        hh = self._view.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(True)
        for c, (_, _, _, w) in enumerate(COLUMNS):
            self._view.setColumnWidth(c, w)
        self._view.verticalHeader().setDefaultSectionSize(26)
        # drag-reorder + right-click show/hide, remembered via QSettings
        hh.setSectionsMovable(True)
        hh.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        hh.customContextMenuRequested.connect(self._header_menu)
        self._restore_header_state()
        hh.sectionMoved.connect(lambda *a: self._save_header_state())
        self._sort_col = None
        self._sort_desc = False
        hh.setSectionsClickable(True)
        hh.sectionClicked.connect(self._on_header_sort)
        hh.sectionResized.connect(lambda *a: self._save_header_state())
        self._view.setStyleSheet(
            f"QTableView {{ background: {theme.CARD}; border: 1px solid {theme.LINE};"
            f"  gridline-color: {theme.LINE}; font-size: 13px;"
            f"  selection-background-color: rgba(74,124,89,0.30); selection-color: {theme.INK}; }}"
            f"QTableView::item:selected {{ background: rgba(74,124,89,0.30); color: {theme.INK}; }}"
            f"QHeaderView::section {{ background: {theme.PAPER}; padding: 4px; border: none;"
            f"  border-right: 1px solid {theme.LINE}; border-bottom: 1px solid {theme.LINE};"
            f"  font-weight: 600; }}"
            + theme.input_qss()
        )

        for c, (key, _, kind, _) in enumerate(COLUMNS):
            if kind == "species":
                self._view.setItemDelegateForColumn(c, SpeciesCascadeDelegate(self._service, self._view))
            elif kind == "stage":
                self._view.setItemDelegateForColumn(c, _OptionDelegate(self._stages, self._view, "Adult"))
            elif kind == "sex":
                self._view.setItemDelegateForColumn(c, _OptionDelegate(self._sexes, self._view))
            elif kind == "method":
                self._view.setItemDelegateForColumn(c, _OptionDelegate(self._methods, self._view))
            elif kind == "number":
                self._view.setItemDelegateForColumn(c, _NumberDelegate(self._view))
            else:
                self._view.setItemDelegateForColumn(c, _TextDelegate(self._view))
        v.addWidget(self._view, 1)

        # ---- controls widget: sits in the banner (middle column), not at the bottom ----
        from PySide6.QtWidgets import QLineEdit
        from DataEntry.info_panel import _BANNER_H
        controls = QWidget()
        controls.setStyleSheet(theme.card_qss())
        controls.setFixedHeight(_BANNER_H)
        cv = QVBoxLayout(controls)
        cv.setContentsMargins(12, 10, 12, 10)
        cv.setSpacing(6)

        # Recorder / Determiner boxes (applied to a row on species match: box -> row above -> empty)
        def _box(lbl):
            h = QHBoxLayout(); h.setSpacing(6)
            L = QLabel(lbl); L.setFixedWidth(74)
            L.setStyleSheet(f"color: {theme.INK}; font-size: 12px;")
            e = QLineEdit(); e.setFixedWidth(180)
            e.setStyleSheet(theme.input_qss())
            h.addWidget(L); h.addWidget(e); h.addStretch(1)
            return h, e
        rrow, self._rec_box = _box("Recorder")
        drow, self._det_box = _box("Determiner")
        self._rec_box.setToolTip("Applied to each matched row's Recorder (unless already typed or filled from above).")
        self._det_box.setToolTip("Applied to each matched row's Determiner (unless already typed or filled from above).")
        self._rec_box.textChanged.connect(self._push_entry_defaults)
        self._det_box.textChanged.connect(self._push_entry_defaults)
        try:
            from PySide6.QtCore import QSettings
            s = QSettings()
            # seed from Observatum Settings defaults; fall back to the last-typed Data Entry value
            rec = s.value("general/default_recorder", "", type=str) \
                or s.value("DataEntry/entryRecorder", "", type=str)
            det = s.value("general/default_determiner", "", type=str) \
                or s.value("DataEntry/entryDeterminer", "", type=str)
            self._rec_box.setText(rec)
            self._det_box.setText(det)
        except Exception:
            pass
        cv.addLayout(rrow); cv.addLayout(drow)

        self._copy_ctx = QCheckBox("Copy context from row above")
        self._copy_ctx.setChecked(True)
        self._copy_ctx.setToolTip(
            "When a species matches, fill any empty Date / Grid ref / Site / VC / Recorder /\n"
            "Determiner / Method cells from the nearest filled row above. Never overwrites what\n"
            "you've already typed.")
        self._copy_ctx.setStyleSheet(f"color: {theme.INK}; font-size: 12px;")
        self._copy_ctx.toggled.connect(self._model.set_copy_context)
        cv.addWidget(self._copy_ctx)

        # add-rows row
        addr = QHBoxLayout(); addr.setSpacing(6)
        add_lbl = QLabel("Add rows:"); add_lbl.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        addr.addWidget(add_lbl)
        for n in (10, 100, 1000):
            b = QPushButton(f"+{n}")
            b.setStyleSheet(theme.button_primary_qss())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=n: self._model.add_display_rows(k))
            addr.addWidget(b)
        self._sort_btn = QPushButton("Entry order")
        self._sort_btn.setStyleSheet(theme.button_secondary_qss())
        self._sort_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sort_btn.setToolTip("Restore the rows to their entry order.")
        self._sort_btn.clicked.connect(self._restore_entry_order)
        self._sort_btn.setVisible(False)
        addr.addWidget(self._sort_btn)

        self._del_btn = QPushButton("Remove empty tail")
        self._del_btn.setStyleSheet(theme.button_delete_qss())
        self._del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._del_btn.clicked.connect(self._remove_row)
        addr.addWidget(self._del_btn); addr.addStretch(1)
        cv.addLayout(addr)

        # finish-job row: commit / export / discard (+ count)
        fin_row = QHBoxLayout(); fin_row.setSpacing(8)
        fin = QLabel("Finish job:"); fin.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        fin_row.addWidget(fin)
        self._commit_btn = QPushButton("Commit to Observatum")
        self._commit_btn.setStyleSheet(theme.button_primary_qss())
        self._commit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._commit_btn.clicked.connect(self._do_commit)
        if self._commit_cb is None:
            self._commit_btn.setEnabled(False)
            pass  # disabled look handled by button_primary_qss :disabled
            self._commit_btn.setToolTip("Commit is disabled here (preview / not launched against Observatum)")
        fin_row.addWidget(self._commit_btn)
        self._export_btn = QPushButton("Export\u2026")
        self._export_btn.setStyleSheet(theme.button_secondary_qss())
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.clicked.connect(self._do_export)
        fin_row.addWidget(self._export_btn)
        self._discard_btn = QPushButton("Discard job")
        self._discard_btn.setStyleSheet(theme.button_delete_qss())
        self._discard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._discard_btn.clicked.connect(self._do_discard)
        fin_row.addWidget(self._discard_btn)
        fin_row.addStretch(1)
        cv.addLayout(fin_row)

        # count + optional 'species popup unavailable' note
        meta = QHBoxLayout()
        if not self._service:
            note = QLabel("species popup unavailable \u2014 typing names as text")
            note.setStyleSheet(f"color: {theme.GOLD}; font-size: 11px;")
            meta.addWidget(note)
        self._count = QLabel("")
        self._count.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        meta.addStretch(1)
        self._count.hide()  # duplicated by the This-workbook card; keep object, don't show
        cv.addLayout(meta)
        cv.addStretch(1)

        self._info.set_pending_provider(self._job.get("mode", "Personal"), self._pending_count)
        self._info.set_workbook_provider(self._workbook_summary)
        self._info.set_locations_provider(self._locations_summary)
        self._info.set_controls_widget(controls)
        self._push_entry_defaults()

        self._model.rowsInserted.connect(self._update_count)
        self._model.rowsRemoved.connect(self._update_count)
        self._model.dataChanged.connect(self._update_count)
        self._model.dataChanged.connect(lambda *a: self._info.refresh_counts())
        self._model.rowsInserted.connect(lambda *a: self._info.refresh_counts())
        self._model.rowsRemoved.connect(lambda *a: self._info.refresh_counts())
        self._model.dataChanged.connect(lambda *a: self._info.refresh_workbook())
        self._model.dataChanged.connect(lambda *a: self._info.refresh_locations())
        self._model.rowsInserted.connect(lambda *a: self._info.refresh_workbook())
        self._model.rowsRemoved.connect(lambda *a: self._info.refresh_workbook())
        self._update_count()

        # refresh the info panel as the current row changes or its species is edited
        self._view.selectionModel().currentChanged.connect(lambda cur, prev: self._refresh_info(cur))
        self._model.dataChanged.connect(self._on_data_changed)
        self._refresh_info(self._view.currentIndex())

    def _on_data_changed(self, top_left, bottom_right, roles=None):
        cur = self._view.currentIndex()
        if cur.isValid() and top_left.row() <= cur.row() <= bottom_right.row():
            self._refresh_info(cur)

    def _refresh_info(self, index):
        if index is not None and index.isValid():
            self._info.update_for_row(self._model.row_dict(index.row()))
        else:
            self._info.clear()

    def _remove_row(self):
        # trim trailing blank rows (housekeeping after over-scrolling / gaps at the end)
        self._model.trim_empty_tail()
        self._update_count()

    def _on_header_sort(self, column: int):
        """Click a header to sort; click again to reverse. View only -- nothing is saved."""
        if self._sort_col == column:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col, self._sort_desc = column, False
        self._model.sort_rows(column, self._sort_desc)
        arrow = "\u25be" if self._sort_desc else "\u25b4"
        self._sort_btn.setText(f"Entry order  (sorted by {COLUMNS[column][1]} {arrow})")
        self._sort_btn.setVisible(True)
        if self._copy_ctx.isChecked():
            self._ctx_was_on = True
            self._copy_ctx.setChecked(False)   # 'row above' is meaningless while sorted

    def _restore_entry_order(self):
        self._sort_col, self._sort_desc = None, False
        self._model.restore_entry_order()
        self._sort_btn.setVisible(False)
        if getattr(self, "_ctx_was_on", False):
            self._copy_ctx.setChecked(True)
            self._ctx_was_on = False

    def _locations_summary(self):
        """[(sub_location, trap_number, grid_ref, count)] for this job, most-used first."""
        try:
            rows = self._conn.execute(
                "SELECT sub_location, trap_number, grid_ref, COUNT(*) n "
                "FROM entry_staging WHERE job_id=? AND grid_ref IS NOT NULL "
                "AND trap_number IS NOT NULL AND TRIM(trap_number)<>'' "
                "AND TRIM(grid_ref)<>'' GROUP BY 1,2,3 ORDER BY sub_location, trap_number, grid_ref",
                (self._job_id,)).fetchall()
        except Exception:
            return []
        return [(r["sub_location"], r["trap_number"], r["grid_ref"], r["n"]) for r in rows]

    def _workbook_summary(self):
        """(records, distinct species, [(order, count), ...], individuals) for this job."""
        try:
            rows = self._conn.execute(
                "SELECT species_tvk, species_name, order_name, quantity FROM entry_staging WHERE job_id=?",
                (self._job_id,)).fetchall()
        except Exception:
            return (0, 0, [], 0)
        recs = [r for r in rows if (r["species_name"] or r["species_tvk"])]
        species = len({(r["species_tvk"] or r["species_name"]) for r in recs})
        from collections import Counter
        by_order = Counter((r["order_name"] or "Unassigned") for r in recs)
        individuals = 0
        for r in recs:
            try:
                q = int(r["quantity"])
            except (TypeError, ValueError):
                q = 1
            individuals += q if q > 0 else 1
        return (len(recs), species, by_order.most_common(), individuals)

    def _pending_count(self, tvk):
        if not tvk:
            return 0
        try:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM entry_staging WHERE job_id=? AND species_tvk=?",
                (self._job_id, tvk)).fetchone()
            return int(row[0]) if row else 0
        except Exception:
            return 0

    def _push_entry_defaults(self, *args):
        rec = self._rec_box.text().strip()
        det = self._det_box.text().strip()
        self._model.set_entry_defaults(rec, det)
        try:
            from PySide6.QtCore import QSettings
            s = QSettings()
            s.setValue("DataEntry/entryRecorder", rec)
            s.setValue("DataEntry/entryDeterminer", det)
        except Exception:
            pass

    def _update_count(self, *args):
        n = self._model.records_entered()
        self._count.setText(f"{n} record{'s' if n != 1 else ''} entered")

    # -- the three exits -----------------------------------------------------
    def _is_commercial(self) -> bool:
        return (self._job.get("mode") or "").lower().startswith("comm")

    def _do_commit(self):
        from DataEntry import commit_service as cs  # noqa: F401 (kept for symmetry/tests)
        if self._commit_cb is None:
            QMessageBox.information(self, "Commit",
                                   "Commit needs Observatum \u2014 launch via run_entry.bat.")
            return
        if self._model.real_count() == 0:
            QMessageBox.information(self, "Commit", "Nothing to commit yet.")
            return
        embargo = None
        if self._is_commercial():
            dlg = EmbargoDialog(self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            embargo = dlg.value()
        if QMessageBox.question(
            self, "Commit to Observatum",
            "Write this job's records into Observatum? Committed rows are removed from staging.",
        ) != QMessageBox.StandardButton.Yes:
            return
        summary = None
        try:
            summary = self._commit_cb(self._job_id, embargo)
        except Exception as e:
            QMessageBox.warning(self, "Commit failed", f"Nothing was committed.\n\n{e}")
            return
        if summary is None:
            QMessageBox.warning(self, "Commit failed",
                                "Could not write to Observatum. Nothing was committed.")
            return
        bits = [f"Committed {summary['committed']} record(s)."]
        detail = []
        if summary.get("skipped_species"):
            detail.append(f"{summary['skipped_species']} skipped (no species)")
        if summary.get("skipped_date"):
            detail.append(f"{summary['skipped_date']} skipped (no date)")
        if summary.get("unresolved"):
            detail.append(f"{summary['unresolved']} committed without a TVK")
        if summary.get("future"):
            detail.append(f"{summary['future']} have a future date \u2014 worth checking")
        if detail:
            bits.append("; ".join(detail))
        if summary.get("remaining"):
            bits.append(f"\n{summary['remaining']} row(s) left in staging to fix \u2014 the job stays open.")
        QMessageBox.information(self, "Committed", "\n".join(bits))
        if summary.get("committed"):
            self.committed.emit(int(summary["committed"]))
        self.finished.emit()

    def _do_export(self):
        from DataEntry import commit_service as cs
        # ask whether to clear the job afterwards (default: clear, preserving old behaviour)
        dlg = ExportOptionsDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        clear_after = dlg.clear_after()
        default = f"{(self._job.get('name') or 'job').replace(' ', '_')}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export job to CSV", default, "CSV files (*.csv)")
        if not path:
            return
        try:
            if clear_after:
                n = cs.export_and_discard(self._conn, self._job, path, COLUMNS)
            else:
                n = cs.export_job(self._conn, self._job, path, COLUMNS)
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        if clear_after:
            QMessageBox.information(self, "Exported",
                                   f"Wrote {n} row(s) to:\n{path}\n\nThe job's staged rows have been cleared.")
            self.finished.emit()
        else:
            QMessageBox.information(self, "Exported",
                                   f"Wrote {n} row(s) to:\n{path}\n\nThe job is unchanged \u2014 still open.")
            # stay on the grid; nothing else to do

    def _do_discard(self):
        from DataEntry import commit_service as cs
        n = self._model.real_count()
        msg = "Discard this job" + (f" and its {n} staged row{'s' if n != 1 else ''}?" if n else "?")
        msg += "\n\nThis removes only staged working data \u2014 nothing already in Observatum."
        if QMessageBox.question(self, "Discard job", msg) != QMessageBox.StandardButton.Yes:
            return
        cs.discard_job(self._conn, self._job)
        self.finished.emit()

    # -- saved column layout (drag-reorder + show/hide via QSettings) ---------
    _HEADER_KEY = "DataEntry/gridHeaderState"

    def _settings(self) -> QSettings:
        return QSettings("Flauna", "Observatum")

    def _save_header_state(self):
        s = self._settings()
        s.setValue(self._HEADER_KEY, self._view.horizontalHeader().saveState())
        s.setValue(self._HEADER_KEY + "Cols", len(COLUMNS))

    def _restore_header_state(self):
        s = self._settings()
        st = s.value(self._HEADER_KEY)
        try:
            saved_cols = int(s.value(self._HEADER_KEY + "Cols", 0))
        except (TypeError, ValueError):
            saved_cols = 0
        if saved_cols != len(COLUMNS):
            st = None   # column set changed -- fall back to the default order
        if st is not None:
            try:
                self._view.horizontalHeader().restoreState(st)
            except Exception:
                pass
        # species must never end up hidden by a stale/broken layout
        sp = next((i for i, c in enumerate(COLUMNS) if c[0] == "species_name"), 0)
        self._view.setColumnHidden(sp, False)

    def _header_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        hh = self._view.horizontalHeader()
        menu = QMenu(self)
        ins = "Insert row above" if len(real) == 1 else f"Insert {len(real)} rows above"
        menu.addAction(ins).triggered.connect(self._insert_selected_rows)
        menu.addSeparator()
        for c, (key, header, _, _) in enumerate(COLUMNS):
            act = menu.addAction(header)
            act.setCheckable(True)
            act.setChecked(not self._view.isColumnHidden(c))
            if key == "species_name":
                act.setEnabled(False)  # always visible
            act.toggled.connect(lambda checked, col=c: self._toggle_column(col, checked))
        menu.addSeparator()
        menu.addAction("Show all columns").triggered.connect(self._show_all_columns)
        menu.exec(hh.mapToGlobal(pos))

    def _toggle_column(self, c, visible):
        if not visible and COLUMNS[c][0] == "species_name":
            return
        self._view.setColumnHidden(c, not visible)
        self._save_header_state()

    def _show_all_columns(self):
        for c in range(len(COLUMNS)):
            self._view.setColumnHidden(c, False)
        self._save_header_state()

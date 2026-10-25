"""StagingTableModel -- the grid's table model over a job's entry_staging rows (split from entry_grid.py, R13)."""
from __future__ import annotations

import sqlite3
from typing import List, Dict, Optional

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSettings
from PySide6.QtWidgets import (
    QMessageBox,
)

from DataEntry import theme
from DataEntry import staging_repo as repo
from DataEntry.grid_columns import (
    COLUMNS, COLIDX, CHECK_HINT, CHECK_YES, LAST_ROW_KEY, DEFAULT_DISPLAY_ROWS)


class StagingTableModel(QAbstractTableModel):
    def __init__(self, conn: sqlite3.Connection, job_id: int, vc_service=None, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._job_id = job_id
        self._vc_service = vc_service
        self._rows: List[Dict] = repo.fetch_rows(conn, job_id)
        self._photo_counts: Dict[int, int] = {}
        self.refresh_photo_counts()
        self._min_display = DEFAULT_DISPLAY_ROWS
        self._has_check = repo.has_check_columns(conn)   # False until the script has been run
        self._last_row_id = None
        self._copy_context = True  # tickbox: fill empty context cells from the nearest row above
        self._sorted = False       # view sorted by a column: 'row above' is not the entry order
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

    def copies_context(self) -> bool:
        """Copy from the row above now? Only with the tick on and the rows in entry order."""
        return self._copy_context and not self._sorted

    # fields a repeat (B2) carries over besides the context keys: the species and its stage
    _REPEAT_KEYS = ("species_name", "species_tvk", "common_name", "order_name", "family",
                    "taxon_rank", "stage", "vice_county", "vc_number")

    def repeat_row(self, r: int) -> Optional[int]:
        """B2: a copy of row r (species, stage and context) inserted just below it, with Sex
        and No. left blank for the next split. Returns the new row's index."""
        if not (0 <= r < len(self._rows)) or not self._rows[r].get("species_name"):
            return None
        src = dict(self._rows[r])
        self.insert_rows(r + 1, 1, inherit=True)        # context keys from row r
        new = self._rows[r + 1]
        upd = {k: src.get(k) for k in self._REPEAT_KEYS if src.get(k) not in (None, "")}
        if upd:
            new.update(upd)
            repo.update_row(self._conn, new["id"], upd)
            self.dataChanged.emit(self.index(r + 1, 0), self.index(r + 1, self.columnCount() - 1),
                                  [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
        return r + 1

    def bump_quantity(self, r: int, delta: int) -> int:
        """B1 count mode: add delta to row r's No. (never below 1; a blank No. counts as 0)."""
        self._materialize_to(r)
        try:
            cur = int(self._rows[r].get("quantity") or 0)
        except (TypeError, ValueError):
            cur = 0
        new = max(1, cur + delta)
        self.setData(self.index(r, COLIDX["quantity"]), str(new), Qt.ItemDataRole.EditRole)
        return new

    def _nearest_above(self, r: int, key: str):
        """Value for `key` from the row IMMEDIATELY above r.

        Stops at a blank row: Wil uses empty rows to separate date / trap / parcel
        blocks, so reaching across one would copy context from the wrong block and
        silently produce a record with the wrong grid ref, trap or sub-location.
        """
        i = r - 1
        if i < 0 or i >= len(self._rows):
            return None
        above = self._rows[i]
        if not (above.get("species_name") or "").strip():
            return None            # blank separator row -- copy nothing
        v = above.get(key)
        return v if v not in (None, "") else None

    def rowCount(self, parent=QModelIndex()):
        # at least _min_display rows on screen; always one blank past the real data
        return 0 if parent.isValid() else max(len(self._rows) + 1, self._min_display)

    def real_count(self) -> int:
        return len(self._rows)

    def records_entered(self) -> int:
        return sum(1 for row in self._rows if (row.get("species_name") or "").strip())

    _MEANINGFUL = ("species_name", "quantity", "sex", "stage", "determiner", "sub_location",
                   "trap_number", "visit_number", "date", "site_name", "grid_ref",
                   "vice_county", "recorder", "method", "comment", "check_flag", "check_note")

    def trim_empty_tail(self) -> int:
        """Delete trailing real rows that are completely empty (e.g. from over-scrolling)."""
        removed = 0
        def _empty(row):
            return not any((row.get(k) not in (None, "")) for k in self._MEANINGFUL)
        def _has_photos(rid):
            try:
                from shared import bench_photos
                return bench_photos.count_for_rows(self._conn, [rid]) > 0
            except Exception:
                return True                    # unsure: keep the row
        while self._rows and _empty(self._rows[-1]) and not _has_photos(self._rows[-1]["id"]):
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
        n = self._photo_counts.get((self._rows[section] or {}).get("id")) if section < len(self._rows) else None
        return f"{section + 1}  \U0001F4F7{n}" if n else str(section + 1)

    def refresh_photo_counts(self) -> None:
        """Re-read how many bench photos each row has (shown in the row header)."""
        try:
            from shared import photo_links
            self._photo_counts = photo_links.staging_counts(
                self._conn, [r.get("id") for r in self._rows])
        except Exception as e:
            print(f"photo counts: {e}")
            self._photo_counts = {}
        if self._rows:
            self.headerDataChanged.emit(Qt.Orientation.Vertical, 0, len(self._rows) - 1)

    # -- "To check" mark (not determined yet) ---------------------------------
    def has_check_columns(self) -> bool:
        return self._has_check

    def is_flagged(self, r: int) -> bool:
        from DataEntry.commit_service import is_flagged
        return 0 <= r < len(self._rows) and is_flagged(self._rows[r])

    def flagged_count(self) -> int:
        from DataEntry.commit_service import is_flagged
        return sum(1 for row in self._rows if is_flagged(row))

    def toggle_check(self, r: int) -> None:
        """Flip the To check mark of view row r (nothing without the database columns)."""
        if self._has_check:
            self.setData(self.index(r, COLIDX["check_flag"]),
                         "" if self.is_flagged(r) else "1", Qt.ItemDataRole.EditRole)

    # -- the last row entered or edited, remembered per job ---------------------
    def _remember_last(self, row_id) -> None:
        if row_id is None or row_id == self._last_row_id:
            return
        self._last_row_id = row_id
        try:
            QSettings().setValue(LAST_ROW_KEY.format(self._job_id), int(row_id))
        except Exception:
            pass

    def last_row_index(self) -> Optional[int]:
        """View row of the staging row last inserted or edited in this job (also from an
        earlier session); if it is gone, the last row with any data; None if there is none."""
        rid = self._last_row_id
        if rid is None:
            try:
                rid = int(QSettings().value(LAST_ROW_KEY.format(self._job_id), 0) or 0) or None
            except (TypeError, ValueError):
                rid = None
        for i, row in enumerate(self._rows):
            if rid is not None and row.get("id") == rid:
                return i
        for i in range(len(self._rows) - 1, -1, -1):
            if any(self._rows[i].get(k) not in (None, "") for k in self._MEANINGFUL):
                return i
        return None

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
        at = max(0, at)
        if at > len(self._rows):
            # inserting into the virtual canvas below the "*" marker: make the rows
            # above real first, exactly as typing into a blank row would.
            self._materialize_to(at - 1)
        at = min(at, len(self._rows))
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
        self._renumber_entry_order([r["id"] for r in made], at)
        self._conn.commit()
        self.endResetModel()
        if made:
            self._remember_last(made[-1]["id"])
        return len(made)

    def _renumber_entry_order(self, new_ids, at: int) -> None:
        """Give rows just inserted at view index `at` their place in ENTRY order.

        Entry order is the stored row_order, not the view: renumbering by the view
        made a sort permanent as soon as a row was inserted or repeated (review DE3).
        The new rows go straight after the row above them (whose context they copy);
        at the top, before the row below. Unsorted, that is exactly the view position.
        """
        stored = dict(self._conn.execute(
            "SELECT id, row_order FROM entry_staging WHERE job_id=?", (self._job_id,)).fetchall())
        new = set(new_ids)
        old = [r["id"] for r in self._rows if r.get("id") is not None and r["id"] not in new]
        entry = sorted(old, key=lambda i: (stored.get(i) if stored.get(i) is not None else i, i))
        n = len(new_ids)
        above = self._rows[at - 1].get("id") if at > 0 else None
        below = self._rows[at + n].get("id") if at + n < len(self._rows) else None
        if above in entry:
            pos = entry.index(above) + 1
        elif below in entry:
            pos = entry.index(below)
        else:
            pos = len(entry) if at > 0 else 0
        entry[pos:pos] = list(new_ids)
        order = {rid: i for i, rid in enumerate(entry, start=1)}
        for rid, i in order.items():
            if stored.get(rid) != i:
                self._conn.execute("UPDATE entry_staging SET row_order=? WHERE id=?", (i, rid))
        for row in self._rows:
            if row.get("id") in order:
                row["row_order"] = order[row["id"]]

    def delete_rows(self, rows) -> int:
        """Delete real staging rows by view index. Virtual rows are ignored. Returns count.

        A row that could not be deleted stays; its view row number (1-based) and error are
        left in self.delete_failures for the caller to report."""
        self.delete_failures = []
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
                except Exception as e:
                    self.delete_failures.append((r + 1, str(e)))
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
        self._sorted = True
        self.endResetModel()

    def restore_entry_order(self) -> None:
        """Re-read the job's rows in their stored row_order."""
        self.beginResetModel()
        self._rows = repo.fetch_rows(self._conn, self._job_id)
        self._sorted = False
        self.refresh_photo_counts()
        self.endResetModel()

    def _is_virtual(self, r: int) -> bool:
        return r >= len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if (index.isValid() and role in (Qt.ItemDataRole.BackgroundRole, Qt.ItemDataRole.ToolTipRole)
                and COLUMNS[index.column()][2] == "species" and not self._is_virtual(index.row())):
            row = self._rows[index.row()]
            if row.get("species_name") and not row.get("species_tvk"):      # B4/B6: not matched
                if role == Qt.ItemDataRole.BackgroundRole:
                    from PySide6.QtGui import QColor
                    return QColor(250, 222, 214)
                return ("Not matched to a species -- no TVK. Type over it to choose; "
                        "the commit check lists any left.")
            return None
        if (index.isValid() and role in (Qt.ItemDataRole.BackgroundRole, Qt.ItemDataRole.ToolTipRole)
                and COLUMNS[index.column()][0] == "date" and not self._is_virtual(index.row())):
            return self._date_flag(self._rows[index.row()].get("date"), role)
        if (index.isValid() and role in (Qt.ItemDataRole.BackgroundRole, Qt.ItemDataRole.ToolTipRole)
                and COLUMNS[index.column()][0] == "vc_number" and not self._is_virtual(index.row())):
            from DataEntry.commit_service import read_vc
            if read_vc(self._rows[index.row()].get("vc_number"))[0]:
                return None
            if role == Qt.ItemDataRole.BackgroundRole:
                from PySide6.QtGui import QColor
                return QColor(theme.CLAY_BG)
            return ("Can't read this VC number -- type a vice-county number from 1 to 113, "
                    "or leave it blank. The row stays in staging until it can be read.")
        if (index.isValid() and role in (Qt.ItemDataRole.BackgroundRole, Qt.ItemDataRole.ToolTipRole)
                and COLUMNS[index.column()][0] == "quantity" and not self._is_virtual(index.row())):
            from DataEntry.commit_service import read_qty
            if read_qty(self._rows[index.row()].get("quantity")) is not None:
                return None
            if role == Qt.ItemDataRole.BackgroundRole:
                from PySide6.QtGui import QColor
                return QColor(theme.CLAY_BG)
            from DataEntry.commit_service import is_zero_qty
            if is_zero_qty(self._rows[index.row()].get("quantity")):     # decision 8
                return ("Count of 0 \u2014 fix the count. Absence isn't recorded: type 1 or more. "
                        "The row stays in staging and is not committed until it is fixed.")
            return ("Can't read this number -- type a whole number of 1 or more. "
                    "The row stays in staging until it can be read.")
        if index.isValid() and COLUMNS[index.column()][2] == "check":
            return self._check_data(index.row(), role)
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

    def _check_data(self, r: int, role):
        """The Check cell: a coloured 'To check' tag when marked, the note in its tooltip."""
        if not self._has_check:
            return CHECK_HINT if role == Qt.ItemDataRole.ToolTipRole else None
        if not self.is_flagged(r):
            return ("Not marked. Type \"to check\" (or x), press Space, or Ctrl+T from any "
                    "column." if role == Qt.ItemDataRole.ToolTipRole else None)
        if role == Qt.ItemDataRole.DisplayRole:
            return "to check"
        from PySide6.QtGui import QColor
        if role == Qt.ItemDataRole.BackgroundRole:
            return QColor(theme.GOLD_BG)
        if role == Qt.ItemDataRole.ForegroundRole:
            return QColor(theme.GOLD)
        if role == Qt.ItemDataRole.ToolTipRole:
            note = (self._rows[r].get("check_note") or "").strip()
            return note or "Marked to check. Ctrl+T, Space or double-click to clear."
        return None

    @staticmethod
    def _date_flag(value, role):
        """DE1: an unreadable date ('31/02/2026', 'summer') or a future one shows in its cell."""
        from DataEntry import date_utils
        if value in (None, ""):
            return None
        if not date_utils.is_readable(value):
            msg = ("Can't read this date -- type dd/mm/yyyy, mm/yyyy (or Jun 2026) or a year. "
                   "It stays in staging until it can be read.")
            bg = theme.CLAY_BG
        elif date_utils.is_future(value):
            msg, bg = "This date is in the future.", theme.GOLD_BG
        else:
            kind = date_utils.date_type(value)
            if role == Qt.ItemDataRole.ToolTipRole and kind in ("O", "Y"):
                return "Month and year only" if kind == "O" else "Year only"
            return None
        if role == Qt.ItemDataRole.BackgroundRole:
            from PySide6.QtGui import QColor
            return QColor(bg)
        return msg

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
        r = index.row() if index.isValid() else -1
        old = self._rows[r] if 0 <= r < len(self._rows) else None
        old_id, old_key = (old.get("id"), self._photo_key(old)) if old else (None, None)
        ok = self._set_data(index, value, role)
        if ok and 0 <= r < len(self._rows):
            self._remember_last(self._rows[r].get("id"))
        if ok and old_id is not None and 0 <= r < len(self._rows):
            new_key = self._photo_key(self._rows[r])
            if new_key != old_key:
                self._photos_follow_row(old_id, old_key, new_key)
        return ok

    @staticmethod
    def _photo_key(row) -> tuple:
        """(species, sex, ISO date or '') -- what a bench photo's name is made from
        (photo_attach.name_for: the date only when it is a full day)."""
        from DataEntry import date_utils
        date = row.get("date")
        iso = (date_utils.start_iso(date) or "") if date and date_utils.date_type(date) == "D" else ""
        return ((row.get("species_name") or "").strip(), (row.get("sex") or "").strip(), iso)

    def _photos_follow_row(self, row_id, old_key, new_key) -> None:
        """A row's species, sex or date changed: its bench photos are renamed inside _Bench
        (no species folder is made until commit). A paste or fill over many rows gives one
        note at the end, not one per row."""
        try:
            from shared import bench_photos, photo_files, photo_links
            if not photo_links.photos_for_staging(self._conn, row_id):
                return
            named = getattr(self, "_photo_names_from", None)
            if named is None:
                named = self._photo_names_from = {}
            if not new_key[0]:
                if old_key[0]:
                    named.setdefault(row_id, old_key)   # cleared: the photos keep this name
                return
            if not old_key[0]:
                old_key = named.pop(row_id, None)
            if old_key is None:
                # cleared in an earlier session: the old name is not known, nothing guessed
                res = photo_files.RedetResult(left=[
                    (p, "the species was cleared earlier, so its old name is not known: rename it by hand")
                    for p in photo_links.photos_for_staging(self._conn, row_id)])
            else:
                res = bench_photos.rename_for_row(self._conn, row_id, old_key, new_key)
            if res.left:
                if not getattr(self, "_photo_notes", None):
                    self._photo_notes = []
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, self._show_photo_notes)
                import os
                self._photo_notes.append(f"Photos not renamed for {new_key[0]}: " + "; ".join(
                    f"{os.path.basename(p)} ({why})" for p, why in res.left))
        except Exception as e:
            print(f"photos follow row: {e}")

    def _show_photo_notes(self) -> None:
        notes, self._photo_notes = getattr(self, "_photo_notes", []) or [], []
        if notes:
            QMessageBox.information(None, "Photos", "\n".join(notes[:20]))

    def _set_data(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        r = index.row()
        key, _, kind, _ = COLUMNS[index.column()]
        virtual = self._is_virtual(r)

        if key in ("check_flag", "check_note") and not self._has_check:
            return True            # the database has no such columns yet: nothing to write
        if kind == "check":
            # only an explicit value switches it on (a pasted number or word does not)
            on = value is True or (isinstance(value, int) and value == 1) or \
                str(value if value is not None else "").strip().lower() in CHECK_YES
            if virtual:
                if not on:
                    return True
                self._materialize_to(r)
            row = self._rows[r]
            newv = 1 if on else None
            if row.get(key) != newv:
                row[key] = newv
                repo.update_row(self._conn, row["id"], {key: newv})
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole,
                                                     Qt.ItemDataRole.EditRole])
            return True

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
                copy_above = self.copies_context()
                # Recorder / Determiner: box wins over row-above; never overwrite a typed cell
                for k, boxval in (("recorder", self._entry_recorder),
                                  ("determiner", self._entry_determiner)):
                    if row.get(k) in (None, ""):
                        if boxval:
                            ctx[k] = boxval
                        elif copy_above:
                            v = self._nearest_above(r, k)
                            if v not in (None, ""):
                                ctx[k] = v
                # other context fields: nearest row above only (when copy-context on)
                if copy_above:
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
            if sval == "":
                newv = None
            elif key == "vc_number":                            # unreadable: kept as typed
                from DataEntry.commit_service import read_vc
                ok, n = read_vc(sval)
                newv = n if ok else sval
            else:
                newv = self._as_qty(sval)                       # unreadable: kept as typed
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
        """VC from the row's grid ref via the VC service. A cleared or unreadable grid ref
        clears the VC (DE2: 'XX123' kept the previous VC41). Without a VC service only a
        cleared grid ref clears it -- nothing can be checked."""
        if not (0 <= r < len(self._rows)):
            return
        row = self._rows[r]
        gr = (row.get("grid_ref") or "").strip()
        if not gr:
            res = (None, None)
        elif not self._vc_service:
            return
        else:
            try:
                res = self._vc_service.get_vc_from_grid_ref(gr)
            except Exception:
                res = None
            res = res or (None, None)
        vc_num, vc_name = res
        if row.get("vc_number") == vc_num and row.get("vice_county") == vc_name:
            return
        updates = {"vice_county": vc_name, "vc_number": vc_num}
        row.update(updates)
        repo.update_row(self._conn, row["id"], updates)
        cols = [COLIDX[k] for k in ("vice_county", "vc_number") if k in COLIDX]
        if cols:
            self.dataChanged.emit(self.index(r, min(cols)), self.index(r, max(cols)),
                                  [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

    @staticmethod
    def _as_qty(sval: str):
        """A whole number of 1 or more, else the text as typed -- shown flagged in its cell
        and kept in staging (DE9: 'c.20' or '0' silently became 1)."""
        from DataEntry.commit_service import read_qty
        n = read_qty(sval)
        return sval if n is None else n

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
        self._remember_last(new_id)
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

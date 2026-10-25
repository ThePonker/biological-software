"""The entry grid page's saved column layout (split from entry_grid.py, R13)."""
from __future__ import annotations

import json

from PySide6.QtCore import QSettings

from DataEntry.grid_columns import (
    COLUMNS, COLIDX)

class GridLayoutMixin:
    """Methods of EntryGridPage: drag-reorder and show/hide of columns, kept in QSettings."""
    # -- saved column layout (drag-reorder + show/hide via QSettings) ---------
    _HEADER_KEY = "DataEntry/gridHeaderState"

    def _settings(self) -> QSettings:
        from shared.settings_store import app_settings
        return app_settings()

    # Before 16 Oct 2026 the grid had these columns (no Check / Check note): a layout saved
    # then is read through them, so adding columns keeps Wil's order, widths and hidden set
    _LEGACY_KEYS = tuple(k for k, _, _, _ in COLUMNS if k not in ("check_flag", "check_note"))

    def _save_header_state(self):
        s = self._settings()
        hh = self._view.horizontalHeader()
        s.setValue(self._HEADER_KEY, hh.saveState())
        s.setValue(self._HEADER_KEY + "Cols", len(COLUMNS))
        # the same layout by column key, so a later change to COLUMNS keeps it (16 Oct 2026)
        layout = [{"key": k, "pos": hh.visualIndex(c), "width": hh.sectionSize(c),
                   "hidden": bool(self._view.isColumnHidden(c))} for c, (k, _, _, _) in enumerate(COLUMNS)]
        s.setValue(self._HEADER_KEY + "Keys", json.dumps(layout))

    @staticmethod
    def _legacy_layout(state, keys):
        """[{key, pos, width, hidden}] read from a header state saved with columns `keys`."""
        from PySide6.QtGui import QStandardItemModel
        from PySide6.QtWidgets import QTableView
        model = QStandardItemModel(0, len(keys))
        view = QTableView()
        view.setModel(model)
        hh = view.horizontalHeader()
        if not hh.restoreState(state):
            return []
        return [{"key": k, "pos": hh.visualIndex(i), "width": hh.sectionSize(i),
                 "hidden": hh.isSectionHidden(i)} for i, k in enumerate(keys)]

    def _apply_layout(self, layout) -> bool:
        """Order, widths and hidden columns by key; columns the layout does not know keep
        their default place after the column they follow in COLUMNS."""
        hh = self._view.horizontalHeader()
        known = {d["key"]: d for d in layout if d.get("key") in COLIDX}
        if not known:
            return False
        order = sorted(known, key=lambda k: known[k]["pos"])
        for k, _, _, _ in COLUMNS:                       # new columns after their neighbour
            if k not in known:
                i = COLIDX[k]
                prev = next((COLUMNS[j][0] for j in range(i - 1, -1, -1) if COLUMNS[j][0] in order), None)
                order.insert(order.index(prev) + 1 if prev else 0, k)
        for want, k in enumerate(order):
            c = COLIDX[k]
            hh.moveSection(hh.visualIndex(c), want)
            if k in known:
                d = known[k]
                if d.get("width"):
                    hh.resizeSection(c, int(d["width"]))
                self._view.setColumnHidden(c, bool(d.get("hidden")))
        return True

    def _restore_header_state(self):
        s = self._settings()
        st = s.value(self._HEADER_KEY)
        try:
            saved_cols = int(s.value(self._HEADER_KEY + "Cols", 0))
        except (TypeError, ValueError):
            saved_cols = 0
        done = False
        try:
            keys = s.value(self._HEADER_KEY + "Keys")
            if keys:
                done = self._apply_layout(json.loads(keys))
            elif st is not None and saved_cols == len(self._LEGACY_KEYS) != len(COLUMNS):
                done = self._apply_layout(self._legacy_layout(st, self._LEGACY_KEYS))
        except Exception as e:                           # a broken layout: defaults
            print(f"[DataEntry] column layout not restored: {e}")
        if not done and st is not None and saved_cols == len(COLUMNS):
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

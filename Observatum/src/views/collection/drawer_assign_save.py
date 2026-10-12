"""
Drawer in hand -- saving (split out of drawer_assign_dialog.py, 12 Oct 2026, Round 9 C).

Save drawer, Empty this drawer and the Drawers list. Every write is: preview of every
change, a kept backup ("pre-drawer-assign"), then one guarded transaction
(shared/drawer_assign.apply). Mixed into DrawerAssignDialog; uses its _specs, _by_id,
_db, _ticked / _unticked / _move_ok, the drawer combos and _load / _fill_list.
"""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QDialog, QMessageBox

from shared import drawer_assign as da

from .drawer_preview import DrawersDialog, PreviewDialog


class DrawerSaveMixin:
    # ---------------------------------------------------------------- save
    def plan_changes(self):
        """The changes Save drawer would make (raises ValueError as plan() does)."""
        storage, drawer = self._drawer()
        ticked = self._contents()
        away = {i for i in ticked if da.elsewhere(self._by_id[i], storage, drawer)}
        if not away <= self._move_ok:          # never move without a "Move here"
            raise ValueError(f"{len(away - self._move_ok)} ticked specimens are in another drawer "
                             "and were not confirmed to move")
        return da.plan(self._specs, ticked, storage, drawer,
                       self.cmb_condition.currentText(), self.cmb_prep.currentText(),
                       move=bool(away), remove=sorted(self._unticked))

    def _save(self):
        storage, drawer = self._drawer()
        try:
            changes = self.plan_changes()
        except ValueError as e:
            QMessageBox.warning(self, "Drawer in hand", str(e))
            return
        if not changes:
            QMessageBox.information(self, "Drawer in hand",
                                    "Nothing to change: the ticked specimens already carry these values.")
            return
        self._commit(changes, storage, drawer)

    def _preview(self, changes, storage, drawer, title=None):
        """Show the preview; True if Apply was pressed (tests replace this)."""
        pv = PreviewDialog(changes, self._by_id, storage, drawer, self, title=title)
        return pv.exec() == QDialog.DialogCode.Accepted

    def _backup(self):
        from shared.backup_service import backup_main_only
        return backup_main_only("pre-drawer-assign")

    def _commit(self, changes, storage, drawer, title=None):
        """Preview, backup, one guarded write. Returns the number of changes written."""
        if not self._preview(changes, storage, drawer, title):
            return 0
        try:
            if not self._backup():
                QMessageBox.warning(self, "Drawer in hand", "The backup failed, so nothing was written.")
                return 0
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Drawer in hand", f"Backup unavailable, so nothing was written.\n{e}")
            return 0
        try:
            conn = sqlite3.connect(self._db)
            try:
                n = da.apply(conn, changes)
            finally:
                conn.close()
        except (sqlite3.Error, ValueError, RuntimeError) as e:
            QMessageBox.warning(self, "Drawer in hand", f"Nothing was written.\n\n{e}")
            return 0
        self._ticked.clear()
        self._unticked.clear()
        self._move_ok.clear()
        self._load()
        self._fill_list()
        self.saved.emit(n)
        self._info("Drawer saved", f"{n} changes written for {da.where(storage, drawer)}.")
        return n

    def _info(self, title, text):
        QMessageBox.information(self, title, text)

    def _pending(self):
        return len(self._ticked) + len(self._unticked)

    def _drop_pending(self, what):
        n = self._pending()
        if n and QMessageBox.question(
                self, what, f"{n} ticks or unticks are not saved yet. "
                "Move on and drop them?") != QMessageBox.StandardButton.Yes:
            return False
        self._ticked.clear()
        self._unticked.clear()
        self._move_ok.clear()
        return True

    # ---------------------------------------------------------------- drawers list
    def _drawers_dialog(self):
        return DrawersDialog(self._specs, self)

    def _open_drawers(self):
        dlg = self._drawers_dialog()
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.action:
            return
        what, st, dr = dlg.action
        if not self._drop_pending("Drawers"):
            return
        self.go_to(st, dr)
        if what == "empty":
            self.empty_drawer(st, dr)

    def go_to(self, storage, drawer):
        """Show this drawer (as if picked at the top)."""
        self.cmb_storage.setCurrentText(storage)
        self.cmb_drawer.setCurrentText(drawer)
        self._fill_list()

    def empty_drawer(self, storage, drawer):
        """Take every specimen out of this drawer: preview, backup, one write."""
        ids = da.in_drawer(self._specs, storage, drawer)
        if not ids:
            self._info("Empty this drawer", f"No specimen is recorded in {da.where(storage, drawer)}.")
            return 0
        changes = da.plan(self._specs, [], storage, drawer, remove=ids)
        return self._commit(changes, storage, drawer, title=f"Empty {da.where(storage, drawer)}")

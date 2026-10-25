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
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog  # noqa: F401  (tests reach entry_grid.QDialog)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QAbstractItemView, QHeaderView,
    QMessageBox, QCheckBox,
)

from DataEntry import theme
from DataEntry import staging_repo as repo
from DataEntry.session_header import load_stages, load_sexes, load_methods
from DataEntry.grid_columns import (  # noqa: F401  (re-exported: callers import these from here)
    COLUMNS, COLIDX, CHECK_HINT, CHECK_YES, LAST_ROW_KEY, _CSV_COLUMNS, DEFAULT_DISPLAY_ROWS)
from DataEntry.staging_model import StagingTableModel
from DataEntry.grid_delegates import (  # noqa: F401  (re-exported: callers import these from here)
    _select_all, _EnterMovesDown, _TextDelegate, _OptionDelegate, _CheckDelegate, _NumberDelegate,
    _to_species_dict, _PickList, SpeciesPickerDialog, SpeciesCascadeDelegate, resolve_name)
from DataEntry.entry_table_view import EntryTableView, _count_keys  # noqa: F401
from DataEntry.grid_dialogs import ExportOptionsDialog, EmbargoDialog  # noqa: F401
from DataEntry.grid_exits_mixin import GridExitsMixin
from DataEntry.grid_layout_mixin import GridLayoutMixin


class EntryGridPage(GridExitsMixin, GridLayoutMixin, QWidget):
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
        self.before_change = None   # staging CSV before Discard / Export-and-clear (DE8)
        self._build_ui()

    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        # live info panel (display only) -- species / conservation / recording history
        from DataEntry.info_panel import InfoService, InfoPanel
        self._info_svc = InfoService(self._conn, self._codex_path)
        try:
            from shared.maps.species_dist_map import DistributionService
            self._dist_svc = DistributionService(self._conn, self._vc_service)
        except Exception:
            self._dist_svc = None
        self._info = InfoPanel(self._info_svc, self._vc_service, self._geojson_path,
                               self._tiles_dir, dist_service=self._dist_svc, maps_dir=self._maps_dir)
        # in a horizontal scroll area: on a window too narrow for even the cards that must
        # stay, a scroll bar appears under the banner instead of the window being forced wider
        from DataEntry.banner_layout import BannerScroll
        self._banner_scroll = BannerScroll(self._info)
        v.addWidget(self._banner_scroll)

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
            elif kind == "check":
                self._view.setItemDelegateForColumn(c, _CheckDelegate(self._view))
            else:
                self._view.setItemDelegateForColumn(c, _TextDelegate(self._view))
        v.addWidget(self._view, 1)

        # ---- controls widget: sits in the banner (middle column), not at the bottom ----
        from PySide6.QtWidgets import QLineEdit
        controls = QWidget()
        # card look on the panel only: unscoped, the border cascaded onto every label and
        # check box inside it (boxed "Recorder", 2 px taller rows)
        controls.setObjectName("deControls")
        controls.setStyleSheet("QWidget#deControls { %s }" % theme.card_qss())
        # No fixed height here (R9-8): the banner is made as tall as these rows need at the
        # machine's font (Segoe UI is taller), so no button is squeezed and its text clipped.
        cv = QVBoxLayout(controls)
        cv.setContentsMargins(12, 6, 12, 6)
        cv.setSpacing(3)

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
            from shared.settings_store import app_settings
            s = app_settings()
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
            "you've already typed.\n"
            "While the grid is sorted nothing is copied (the row above isn't the one\n"
            "entered before); the tick is kept and works again in entry order.")
        self._copy_ctx.setStyleSheet(f"color: {theme.INK}; font-size: 12px;")
        self._copy_ctx.toggled.connect(self._model.set_copy_context)
        cv.addWidget(self._copy_ctx)

        # add-rows row
        addr = QHBoxLayout(); addr.setSpacing(6)
        add_lbl = QLabel("Add rows:"); add_lbl.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        addr.addWidget(add_lbl)
        for n in (10, 100, 1000):
            b = QPushButton(f"+{n}")
            b.setStyleSheet(theme.button_primary_qss(compact=True))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=n: self._model.add_display_rows(k))
            addr.addWidget(b)

        self._del_btn = QPushButton("Remove empty tail")
        self._del_btn.setStyleSheet(theme.button_delete_qss(compact=True))
        self._del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._del_btn.clicked.connect(self._remove_row)
        addr.addWidget(self._del_btn); addr.addStretch(1)
        cv.addLayout(addr)

        # B1 count mode: big glanceable counter; clicker / pedal keys count the current row
        cnt_row = QHBoxLayout(); cnt_row.setSpacing(8)
        self._count_btn = QPushButton("Count mode (F9)")
        self._count_btn.setCheckable(True)
        self._count_btn.setStyleSheet(theme.button_secondary_qss(compact=True))
        self._count_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._count_btn.setToolTip(
            "Count the current row's No. with a key or a foot pedal: Space or + adds one,\n"
            "- takes one off, Enter goes to the next record. F9 turns it on and off.")
        self._count_btn.toggled.connect(self._set_count_mode)
        self._count_btn.toggled.connect(
            lambda on: (None if on else self._count_btn.setText("Count mode (F9)")))
        cnt_row.addWidget(self._count_btn)
        self._photo_btn = QPushButton("Photo\u2026")
        self._photo_btn.setStyleSheet(theme.button_secondary_qss(compact=True))
        self._photo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._photo_btn.setToolTip("Attach photos from the capture folder to the current row.")
        self._photo_btn.clicked.connect(self._attach_photos)
        if not self._on_live_db():
            # bench photos are real files in the one photo library, linked in this database:
            # on a dev copy the links would be invisible to the live app (14 Oct 2026)
            self._photo_btn.setEnabled(False)
            self._photo_btn.setToolTip("Photos can only be attached in the live database "
                                       "(observatum.db), not a dev or test copy.")
        cnt_row.addWidget(self._photo_btn)
        self._check_export_btn = QPushButton("Export for checking\u2026")
        self._check_export_btn.setStyleSheet(theme.button_secondary_qss(compact=True))
        self._check_export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_export_btn.setToolTip("A spreadsheet and a folder of photo copies for the rows "
                                          "marked to check (or the selected rows), to send to be checked.")
        self._check_export_btn.clicked.connect(self._export_for_checking)
        cnt_row.addWidget(self._check_export_btn)
        self._readback_btn = QPushButton("Read back checking\u2026")
        self._readback_btn.setStyleSheet(theme.button_secondary_qss(compact=True))
        self._readback_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._readback_btn.setToolTip("Read a checker's reply to Export for checking: see each "
                                      "answer beside its row and accept the ones you want.")
        self._readback_btn.clicked.connect(self._read_back_checking)
        cnt_row.addWidget(self._readback_btn)
        self._counter = QLabel("")
        self._counter.setStyleSheet(f"color: {theme.INK}; font-size: 26px; font-weight: 700;")
        self._counter.setVisible(False)
        cnt_row.addWidget(self._counter)
        cnt_row.addStretch(1)
        # room for the big counter now, so turning count mode on never moves the grid
        self._counter.setText("0")
        cnt_row.addStrut(max(self._counter.sizeHint().height(),
                             self._count_btn.sizeHint().height()))
        self._counter.setText("")
        cv.addLayout(cnt_row)
        # To check only (view filter) and Last entered row
        nav_row = QHBoxLayout(); nav_row.setSpacing(8)
        self._check_only_btn = QPushButton("To check only (0)")
        self._check_only_btn.setCheckable(True)
        self._check_only_btn.setStyleSheet(
            theme.button_secondary_qss(compact=True)
            + f"QPushButton:checked {{ background-color: {theme.GOLD_BG}; font-weight: 600; }}")
        self._check_only_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_only_btn.toggled.connect(lambda on: self._apply_check_filter())
        nav_row.addWidget(self._check_only_btn)
        self._last_btn = QPushButton("Last entered row")
        self._last_btn.setStyleSheet(theme.button_secondary_qss(compact=True))
        self._last_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._last_btn.setToolTip("Go to the row you last entered or edited in this job.")
        self._last_btn.clicked.connect(self._go_to_last_row)
        nav_row.addWidget(self._last_btn)
        nav_row.addStretch(1)
        cv.addLayout(nav_row)
        for sig in (self._model.dataChanged, self._model.rowsInserted, self._model.rowsRemoved,
                    self._model.modelReset):
            sig.connect(lambda *a: self._check_changed())
        self._check_changed()
        self._view.on_toggle_count = self._count_btn.toggle
        self._view.on_count_done = lambda: self._count_btn.setChecked(False)
        self._view.on_count = lambda r, n: self._show_counter(r)

        # finish-job row: commit / export / discard (+ count)
        fin_row = QHBoxLayout(); fin_row.setSpacing(8)
        fin = QLabel("Finish job:"); fin.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        fin_row.addWidget(fin)
        self._commit_btn = QPushButton("Commit to Observatum")
        self._commit_btn.setStyleSheet(theme.button_primary_qss(compact=True))
        self._commit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if repo.is_test_copy(self._job):
            # a copy made by scripts/copy_job_for_test.py: committing it would record every
            # row twice (17 Oct 2026, Wil's test: the guard in commit_job came after the question)
            self._commit_btn.setEnabled(False)
            self._commit_btn.setToolTip("This is a test copy of a job: it cannot be committed. "
                                        "Discard it when you have finished with it.")
        elif not self._is_commercial() and str(self._job.get("notes") or "").startswith("Exported for iRecord"):
            # exported the old way (no keys): its records come back by Check iRecord
            # return; committing them here as well would hold them twice
            self._commit_btn.setEnabled(False)
            self._commit_btn.setToolTip("This job was exported for iRecord before keys were "
                                        "used. Use Check iRecord return on the Jobs page.")
        elif self._commit_cb is None:
            self._commit_btn.setEnabled(False)
            self._commit_btn.setToolTip("Commit is disabled here (preview / not launched against Observatum)")
        # Personal jobs commit like commercial ones (14 Oct 2026, take 2): records go to iRecord
        # later, in bulk, from Observatum's export (it sends each record's key as External key)
        self._commit_btn.clicked.connect(self._do_commit)
        fin_row.addWidget(self._commit_btn)
        self._export_btn = QPushButton("Export\u2026")
        self._export_btn.setStyleSheet(theme.button_secondary_qss(compact=True))
        self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._export_btn.clicked.connect(self._do_export)
        fin_row.addWidget(self._export_btn)
        self._discard_btn = QPushButton("Discard job")
        self._discard_btn.setStyleSheet(theme.button_delete_qss(compact=True))
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
        # Which order the grid is showing, always in view (L21, 10 Oct): "Entry order"
        # on a button that appeared only once sorted left it unclear which order was on
        self._order_lbl = QLabel()
        self._order_lbl.setToolTip("Click a column heading to sort the view; click it again "
                                   "to reverse.\nSorting never changes the entry order.")
        meta.addWidget(self._order_lbl)
        # Only while sorted: one click back to the order the rows were entered (L21). On
        # the "Showing" line, beside the order it undoes (R9-8: it used to take +1000's place)
        self._sort_btn = QPushButton("Back to entry order")
        self._sort_btn.setStyleSheet(theme.button_secondary_qss(compact=True))
        self._sort_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sort_btn.setToolTip("Show the rows in the order they were entered.\n"
                                  "Sorting only changes the view: the entry order is kept.")
        self._sort_btn.clicked.connect(self._restore_entry_order)
        self._sort_btn.setVisible(False)
        meta.addWidget(self._sort_btn)
        # the line keeps the button's height while it is hidden: no jump when it appears
        meta.addStrut(self._sort_btn.sizeHint().height())
        self._show_order(None, False)
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
        self._view.selectionModel().currentChanged.connect(lambda cur, prev: self._show_counter(cur.row()))
        self._model.dataChanged.connect(self._on_data_changed)
        self._refresh_info(self._view.currentIndex())

    # -- To check: filter, button text, export; Last entered row ----------------
    def _check_changed(self):
        """Keep the 'To check only (n)' text and, while it is on, the hidden rows current."""
        n = self._model.flagged_count()
        self._check_only_btn.setText(f"To check only ({n})")
        has = self._model.has_check_columns()
        self._check_only_btn.setEnabled(has)
        self._check_only_btn.setToolTip(
            "Show only the rows marked to check (view only; the other rows stay)." if has
            else CHECK_HINT)
        if self._check_only_btn.isChecked():
            self._apply_check_filter()

    def _apply_check_filter(self):
        on = self._check_only_btn.isChecked()
        for r in range(self._model.rowCount()):
            self._view.setRowHidden(r, on and not self._model.is_flagged(r))

    def _export_for_checking(self):
        from DataEntry.check_export_dialog import CheckExportDialog
        m = self._model
        selected = [m.row_id(r) for r in self._view._selected_rows()]
        selected = [i for i in selected if i is not None]
        flagged = [m.row_id(r) for r in range(m.real_count()) if m.is_flagged(r)]
        job = repo.get_job(self._conn, self._job_id) or self._job
        CheckExportDialog(self._conn, job, selected, flagged, self).exec()

    def _read_back_checking(self):
        from DataEntry.check_readback_dialog import (
            CheckReadbackDialog, apply_through_grid, resolver_from)
        job = repo.get_job(self._conn, self._job_id) or self._job

        def apply(items, checker):
            if self._on_live_db():
                from shared import backup_service
                if not backup_service.backup_main_only("pre-checking-readback"):
                    raise ValueError("the backup failed, so nothing was changed")
            try:
                return apply_through_grid(self._model, items, checker)
            finally:
                self._check_changed()
        resolve = resolver_from(self._view.itemDelegateForColumn(COLIDX["species_name"]))
        CheckReadbackDialog(self._conn, job, apply, self, resolve=resolve).exec()

    def _go_to_last_row(self):
        r = self._model.last_row_index()
        if r is None:
            QMessageBox.information(self, "Last entered row", "No rows have been entered yet.")
            return
        if self._view.isRowHidden(r):
            self._check_only_btn.setChecked(False)       # the filter would hide it
        ix = self._model.index(r, COLIDX["species_name"])
        self._view.clearSelection()
        self._view.setCurrentIndex(ix)
        self._view.scrollTo(ix, QAbstractItemView.ScrollHint.PositionAtCenter)
        self._view.setFocus()

    def _set_count_mode(self, on: bool):
        self._view.count_mode = bool(on)
        self._counter.setVisible(bool(on))
        self._view.setFocus()
        self._show_counter(self._view.currentIndex().row())

    def _on_live_db(self) -> bool:
        """Is this staging connection the live observatum.db (not a dev or test copy)?"""
        try:
            import os
            from DataEntry.data_entry_widget import LIVE_DB_BASENAME
            for _seq, name, path in self._conn.execute("PRAGMA database_list"):
                if name == "main":
                    return os.path.basename(path or "").lower() == LIVE_DB_BASENAME
        except Exception:
            pass
        return False

    def _attach_photos(self):
        row = self._model.row_dict(self._view.currentIndex().row())
        if not row or not row.get("id") or not (row.get("species_name") or "").strip():
            QMessageBox.information(self, "Photo", "Enter the species first.")
            return
        from DataEntry.photo_attach import PhotoAttachDialog
        PhotoAttachDialog(self._conn, row, self).exec()
        self._model.refresh_photo_counts()

    def _show_counter(self, r):
        if not self._view.count_mode:
            return
        row = self._model.row_dict(r) if r is not None and r >= 0 else None
        n = (row or {}).get("quantity") or 0
        name = (row or {}).get("species_name") or "no species yet"
        self._counter.setText(f"{n}")
        self._counter.setToolTip(name)
        self._count_btn.setText(f"Counting: {name[:28]}")

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
        self._show_order(column, self._sort_desc)
        # The "Copy context" tick is the user's and is left alone (R9-8: sorting used to
        # untick it). While sorted the model copies nothing, as 'row above' means nothing.

    def _restore_entry_order(self):
        self._sort_col, self._sort_desc = None, False
        self._model.restore_entry_order()
        self._show_order(None, False)

    def _show_order(self, column, descending: bool):
        """Say which order the grid shows: the label, and the 'Back to entry order'
        button (shown only while sorted). View only (L21). No heading arrow: the style
        draws ascending as a down arrow on some platforms, against the label's."""
        # the copy-context tick says when sorting has switched it off (14 Oct 2026)
        ctx = getattr(self, "_copy_ctx", None)
        if ctx is not None:
            ctx.setText("Copy context from row above" if column is None else
                        "Copy context from row above \u2014 off while sorted (Back to entry order)")
        if column is None:
            self._order_lbl.setText("Showing: entry order")
            self._order_lbl.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
            self._sort_btn.setVisible(False)
            return
        arrow = "\u25be" if descending else "\u25b4"
        self._order_lbl.setText(f"Showing: sorted by {COLUMNS[column][1]} {arrow}  (view only)")
        self._order_lbl.setStyleSheet(f"color: {theme.INK}; font-size: 12px; font-weight: 600;")
        self._sort_btn.setVisible(True)

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
        from collections import Counter, defaultdict
        by_order = Counter((r["order_name"] or "Unassigned") for r in recs)
        spp_by_order = defaultdict(set)
        for r in recs:
            spp_by_order[r["order_name"] or "Unassigned"].add(
                r["species_tvk"] or r["species_name"])
        individuals = 0
        for r in recs:
            try:
                q = int(r["quantity"])
            except (TypeError, ValueError):
                q = 1
            individuals += q if q > 0 else 1
        ordered = [(o, len(spp_by_order[o]), n) for o, n in by_order.most_common()]
        return (len(recs), species, ordered, individuals)

    def _pending_count(self, tvk):
        """Staged rows for this species across ALL jobs, split by job mode."""
        if not tvk:
            return {"personal": 0, "commercial": 0}
        try:
            row = self._conn.execute(
                "SELECT j.mode, COUNT(*) FROM entry_staging s "
                "JOIN entry_jobs j ON j.id = s.job_id "
                f"WHERE s.species_tvk=? AND j.status IN ({','.join('?' * len(repo.PENDING_STATUSES))}) "
                "GROUP BY j.mode", (tvk, *repo.PENDING_STATUSES)).fetchall()
            out = {"personal": 0, "commercial": 0}
            for mode, n in row:
                if str(mode or "").lower().startswith("comm"):
                    out["commercial"] += n
                else:
                    out["personal"] += n
            return out
        except Exception:
            return {"personal": 0, "commercial": 0}

    def _push_entry_defaults(self, *args):
        rec = self._rec_box.text().strip()
        det = self._det_box.text().strip()
        self._model.set_entry_defaults(rec, det)
        try:
            from shared.settings_store import app_settings
            s = app_settings()
            s.setValue("DataEntry/entryRecorder", rec)
            s.setValue("DataEntry/entryDeterminer", det)
        except Exception:
            pass

    def _update_count(self, *args):
        n = self._model.records_entered()
        self._count.setText(f"{n} record{'s' if n != 1 else ''} entered")

"""photo_intake_dialog -- "Records from photos": phone photos in the capture folder become
Data Entry rows (one per date and place), are attached to a record already made, or are filed
in the species folder (14 Oct 2026). The logic is in shared/photo_intake.py."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListView, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout,
)

from DataEntry import date_utils, theme
from DataEntry import staging_repo as repo
from DataEntry.photo_attach import KEY_FOLDER, PhotoAttachDialog, _settings, capture_folder
from shared import photo_intake

THUMB = 160



PHONE_EXTS = (".jpg", ".jpeg")      # phone photos: JPEGs only (Wil, 14 Oct 2026)

class PhotoIntakeDialog(QDialog):
    def __init__(self, conn, parent=None, search_service=None):
        super().__init__(parent)
        self._conn = conn
        self._service = search_service
        if self._service is None:
            try:
                from DataEntry import bootstrap
                self._service = bootstrap.get_search_service_safe()
            except Exception:
                self._service = None
        self._species = None            # picked from the list (has a TVK)
        self._info: dict = {}           # path -> read_photo dict
        self._files: dict = {}          # path -> mtime
        self.setWindowTitle("Records from photos")
        self.resize(1100, 820)
        v = QVBoxLayout(self)

        top = QHBoxLayout()
        self._folder_lbl = QLabel()
        self._folder_lbl.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        self._folder_lbl.setWordWrap(True)
        top.addWidget(self._folder_lbl, 1)
        self._change_btn = QPushButton("Change folder…")
        self._change_btn.setStyleSheet(theme.button_secondary_qss(compact=True))
        self._change_btn.clicked.connect(self._change_folder)
        top.addWidget(self._change_btn)
        v.addLayout(top)

        self._msg = QLabel()
        self._msg.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        self._msg.setWordWrap(True)
        v.addWidget(self._msg)

        self.list = QListWidget()
        self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        self.list.setMovement(QListView.Movement.Static)
        self.list.setIconSize(QSize(THUMB, THUMB))
        self.list.setGridSize(QSize(THUMB + 24, THUMB + 40))
        self.list.setWordWrap(True)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.itemSelectionChanged.connect(self._update_state)
        v.addWidget(self.list, 1)

        srow = QHBoxLayout()
        srow.addWidget(QLabel("Species:"))
        self.species_edit = QLineEdit()
        self.species_edit.setPlaceholderText("type a name, press Enter, pick from the list")
        self.species_edit.setStyleSheet(theme.input_qss())
        self.species_edit.returnPressed.connect(self._find_species)
        self.species_edit.textEdited.connect(self._species_typed)
        srow.addWidget(self.species_edit, 1)
        self.find_btn = QPushButton("Find")
        self.find_btn.setStyleSheet(theme.button_secondary_qss(compact=True))
        self.find_btn.clicked.connect(self._find_species)
        srow.addWidget(self.find_btn)
        v.addLayout(srow)
        self._species_lbl = QLabel()
        self._species_lbl.setStyleSheet(f"color: {theme.INK}; font-size: 12px;")
        v.addWidget(self._species_lbl)

        jrow = QHBoxLayout()
        jrow.addWidget(QLabel("Job:"))
        self.job_box = QComboBox()
        jrow.addWidget(self.job_box, 1)
        jrow.addWidget(QLabel("Site (optional):"))
        self.site_edit = QLineEdit()
        self.site_edit.setStyleSheet(theme.input_qss())
        jrow.addWidget(self.site_edit, 1)
        v.addLayout(jrow)
        self._fill_jobs()

        self._result = QLabel()
        self._result.setStyleSheet(f"color: {theme.INK}; font-size: 12px;")
        self._result.setWordWrap(True)
        v.addWidget(self._result)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.make_btn = QPushButton("Make records")
        self.make_btn.setStyleSheet(theme.button_primary_qss(compact=True))
        self.make_btn.clicked.connect(self._make_records)
        btns.addWidget(self.make_btn)
        self.folder_btn = QPushButton("Species folder only")
        self.folder_btn.setStyleSheet(theme.button_secondary_qss(compact=True))
        self.folder_btn.clicked.connect(self._species_folder_only)
        btns.addWidget(self.folder_btn)
        close = QPushButton("Close")
        close.setStyleSheet(theme.button_secondary_qss(compact=True))
        close.clicked.connect(self.accept)
        btns.addWidget(close)
        v.addLayout(btns)

        self._live = self._on_live_db()
        self._backed_up = False          # observatum.db backed up once, before the first write
        self._load()

    # -- setup ------------------------------------------------------------------------------
    def _on_live_db(self) -> bool:
        try:
            from DataEntry.data_entry_widget import LIVE_DB_BASENAME
            for _seq, name, path in self._conn.execute("PRAGMA database_list"):
                if name == "main":
                    return os.path.basename(path or "").lower() == LIVE_DB_BASENAME
        except Exception:
            pass
        return False

    def _fill_jobs(self) -> None:
        self.job_box.clear()
        try:
            personal = repo.ensure_personal_job(self._conn)
            jobs = repo.list_jobs(self._conn)
        except Exception:
            personal, jobs = None, []
        for j in jobs:
            if j.get("status") != "active":     # a job awaiting iRecord can't be committed
                continue
            self.job_box.addItem(j.get("name") or f"Job {j['id']}", j["id"])
        i = self.job_box.findData(personal)
        if i >= 0:
            self.job_box.setCurrentIndex(i)

    @staticmethod
    def _defaults() -> dict:
        try:
            from PySide6.QtCore import QSettings
            s = QSettings()
            rec = s.value("general/default_recorder", "", type=str) or s.value("DataEntry/entryRecorder", "", type=str)
            det = s.value("general/default_determiner", "", type=str) or s.value("DataEntry/entryDeterminer", "", type=str)
            return {"recorder": rec, "determiner": det}
        except Exception:
            return {"recorder": "", "determiner": ""}

    # -- species ----------------------------------------------------------------------------
    def _species_typed(self, _t=None) -> None:
        self._species = None
        self._species_lbl.setText("")
        self._update_state()

    def _find_species(self) -> None:
        """The Data Entry grid's own rules: resolve_name over the search service; a picker when
        there is more than one match."""
        from DataEntry.entry_grid import SpeciesPickerDialog, _to_species_dict
        from shared.species_rank import resolve_name
        text = self.species_edit.text().strip()
        if not text or not self._service:
            if text:
                self._species_lbl.setText("The species search is not available.")
            return
        try:
            results = list(self._service.search_species(text, limit=25) or [])
        except Exception:
            results = []
        action, payload = resolve_name(text, results, interactive=True)
        picked = None
        if action == "fill":
            picked = _to_species_dict(payload)
        elif action == "pick":
            dlg = SpeciesPickerDialog(text, payload, self)
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.chosen:
                picked = _to_species_dict(dlg.chosen)
        self.set_species(picked)
        if not picked:
            self._species_lbl.setText("No species chosen -- pick one from the list.")

    def set_species(self, d) -> None:
        """d: the grid's species dict (scientific_name, tvk, common_name, order, family, rank)."""
        if d and d.get("scientific_name") and d.get("tvk"):
            self._species = {"species_name": d["scientific_name"], "species_tvk": d["tvk"],
                             "common_name": d.get("common_name") or "", "order_name": d.get("order") or "",
                             "family": d.get("family") or "", "taxon_rank": d.get("rank") or ""}
            self.species_edit.setText(d["scientific_name"])
            self._species_lbl.setText(" · ".join(b for b in (d["scientific_name"], d.get("common_name") or "",
                                                              d.get("family") or "") if b))
        else:
            self._species = None
        self._update_state()

    # -- the capture folder -----------------------------------------------------------------
    def _change_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Capture folder", str(capture_folder()))
        if d:
            _settings().setValue(KEY_FOLDER, d)
            self._load()

    def _load(self, note: str = "") -> None:
        folder = capture_folder()
        self._folder_lbl.setText(f"Capture folder: {folder}")
        self.list.clear()
        self._files, self._info = {}, {}
        problem = ""
        if not folder.is_dir():
            problem = f"The capture folder {folder} does not exist."
        else:
            found = []
            for f in folder.iterdir():
                if f.is_file() and f.suffix.lower() in PHONE_EXTS:
                    try:
                        found.append((f.stat().st_mtime, f))
                    except OSError:
                        pass
            found.sort(key=lambda t: t[0], reverse=True)
            for mtime, f in found:
                info = photo_intake.read_photo(f)
                ref = photo_intake.grid_ref(info["lat"], info["lon"]) if info["lat"] is not None else None
                when = date_utils.to_display(info["taken"]) if info["taken"] else "no date"
                it = QListWidgetItem(QIcon(PhotoAttachDialog._thumb(f)), f.name)
                it.setToolTip(f"{f.name}\nTaken: {when} {info['time']}\n{ref or 'no GPS'}")
                it.setData(Qt.ItemDataRole.UserRole, str(f))
                self.list.addItem(it)
                self._files[str(f)] = mtime
                self._info[str(f)] = info
            if not found:
                problem = f"No photos in {folder}."
        if not self._live:
            problem = "Records from photos works only on the live database (observatum.db)."
        self._msg.setText(note or problem)
        self._problem = bool(problem)
        self._update_state()

    def _selected(self) -> list:
        paths = [it.data(Qt.ItemDataRole.UserRole) for it in self.list.selectedItems()]
        return sorted(paths, key=lambda p: (self._files.get(p, 0), p))

    def _update_state(self) -> None:
        ok = bool(self._species) and bool(self._selected()) and self._live and not getattr(self, "_problem", False)
        self.make_btn.setEnabled(ok)
        self.folder_btn.setEnabled(ok)

    # -- actions ----------------------------------------------------------------------------
    def _groups(self) -> list:
        return photo_intake.group([self._info[p] for p in self._selected() if p in self._info])

    def _backup(self) -> bool:
        """observatum.db backed up once per window, before its first write (rows, links to an
        existing record); False (nothing done) if the backup fails (review 14 Oct 2026)."""
        if self._backed_up:
            return True
        from shared import backup_service
        if not backup_service.backup_main_only("pre-photo-intake"):
            QMessageBox.warning(self, "Records from photos",
                                "The database could not be backed up, so nothing was changed.")
            return False
        self._backed_up = True
        return True

    def _make_records(self) -> None:
        if not self._species:
            return
        job_id = self.job_box.currentData()
        if job_id is None or not self._backup():
            return
        sp, defaults = self._species, self._defaults()
        site = self.site_edit.text().strip()
        if site:
            defaults["site_name"] = site
        made, attached, failed, skipped = [], 0, [], 0
        for g in self._groups():
            first = next((p for p in g if p["lat"] is not None), None)
            iso = g[0]["taken"]
            try:
                found = photo_intake.existing_records(
                    self._conn, sp["species_name"], sp["species_tvk"], iso,
                    first["lat"] if first else None, first["lon"] if first else None)
            except Exception:
                found = []
            if found:
                oid, osite, oref = found[0]
                where = osite or oref or "an unnamed place"
                ans = QMessageBox.question(
                    self, "Record exists",
                    f"A record of {sp['species_name']} on {date_utils.to_display(iso)} at {where} already "
                    "exists -- attach the photos to it instead?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
                if ans == QMessageBox.StandardButton.Cancel:
                    skipped += len(g)
                    continue
                if ans == QMessageBox.StandardButton.Yes:
                    for p in g:
                        try:
                            photo_intake.attach_to_record(self._conn, p["path"], oid, sp, iso)
                            attached += 1
                        except Exception as e:
                            failed.append(f"{Path(p['path']).name}: {e}")
                    continue
            fails: list = []
            try:
                ids = photo_intake.make_rows(self._conn, job_id, [g], sp, defaults, failures=fails)
                made += ids
            except Exception as e:
                failed += [f"{Path(p['path']).name}: {e}" for p in g]
                continue
            failed += [f"{Path(p).name}: {why}" for p, why in fails]
        parts = []
        if made:
            parts.append(f"{len(made)} row(s) made in {self.job_box.currentText()}")
        if attached:
            parts.append(f"{attached} photo(s) attached to existing records")
        if skipped:
            parts.append(f"{skipped} photo(s) skipped")
        self._finish(parts, failed)

    def _species_folder_only(self) -> None:
        if not self._species or not self._backup():
            return
        filed, failed = 0, []
        for p in self._selected():
            info = self._info.get(p)
            try:
                photo_intake.to_species_folder(self._conn, p, self._species, info["taken"] if info else "")
                filed += 1
            except Exception as e:
                failed.append(f"{Path(p).name}: {e}")
        self._finish([f"{filed} photo(s) filed in the species folder"] if filed else [], failed)

    def _finish(self, parts: list, failed: list) -> None:
        text = "; ".join(parts) or "Nothing done"
        if failed:
            text += "\nCould not be moved (left where they were):\n" + "\n".join(failed)
        self._load()
        self._result.setText(text)
        self._fill_jobs_keep()

    def _fill_jobs_keep(self) -> None:
        cur = self.job_box.currentData()
        self._fill_jobs()
        i = self.job_box.findData(cur)
        if i >= 0:
            self.job_box.setCurrentIndex(i)

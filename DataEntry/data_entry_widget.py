"""DataEntryWidget -- self-contained entry widget. Step 1: jobs list.

Opens to the JOBS LIST (the front door). Each job is a durable named container in the staging
tables. Opening a job goes to a per-job placeholder for now; the editable grid arrives in step 2.
Self-contained: takes a database PATH, opens its own sqlite connection, self-heals the staging
schema, and ensures a Personal job exists. No Observatum-core dependency yet (commit/species
search arrive in later steps).
"""
from __future__ import annotations

import os
import sqlite3
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget, QPushButton,
)

from DataEntry import theme
from DataEntry import staging_repo as repo
from DataEntry.jobs_list_page import JobsListPage

LIVE_DB_BASENAME = "observatum.db"


class DataEntryWidget(QWidget):
    committed = Signal(int)  # fires after a successful commit, with the number of records written

    def __init__(self, db_path: str, parent: Optional[QWidget] = None, embedded: bool = False,
                 allow_commit: Optional[bool] = None):
        super().__init__(parent)
        self._db_path = db_path
        self._embedded = embedded
        self._allow_commit = allow_commit
        self._conn: Optional[sqlite3.Connection] = None
        self._schema_error: Optional[str] = None
        self._search_service = None
        self._codex_path = None
        self._vc_service = None
        self._geojson_path = None
        self._tiles_dir = None
        self._maps_dir = None
        self._open_connection()
        self._resolve_search_service()
        self._resolve_codex_path()
        self._resolve_vc_service()
        self.setWindowTitle("Data Entry")
        self._build_ui()

    # -- csv safety net ---------------------------------------------------
    def _start_backup_timer(self):
        """Rolling CSV backup of staging every 15 minutes while the tab is open."""
        try:
            from PySide6.QtCore import QTimer
            self._backup_timer = QTimer(self)
            self._backup_timer.setInterval(15 * 60 * 1000)
            self._backup_timer.timeout.connect(self.backup_now)
            self._backup_timer.start()
        except Exception as e:
            print(f"[DataEntry] backup timer not started: {e}")

    def backup_now(self):
        """Write the staging CSV. Safe to call at any time; never raises."""
        if self._conn is None:
            return
        try:
            from DataEntry import csv_backup
            csv_backup.backup_staging(self._conn)
        except Exception as e:
            print(f"[DataEntry] staging backup failed: {e}")

    def backup_observations_now(self, *_):
        """Write the observations CSV. Wired to the grid's committed signal."""
        try:
            from DataEntry import csv_backup
            csv_backup.backup_staging(self._conn)
            csv_backup.backup_observations(self._db_path)
        except Exception as e:
            print(f"[DataEntry] post-commit backup failed: {e}")

    # -- db --------------------------------------------------------------
    def is_live_db(self) -> bool:
        return os.path.basename(self._db_path).lower() == LIVE_DB_BASENAME

    def _open_connection(self):
        try:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
            repo.ensure_schema(self._conn)          # self-heal if migration wasn't run
            repo.ensure_personal_job(self._conn)    # guarantee the Personal job
        except sqlite3.Error as e:
            self._schema_error = str(e)

    def _resolve_search_service(self):
        """Best-effort: Observatum's species search service (None if unavailable)."""
        try:
            from DataEntry import bootstrap
            self._search_service = bootstrap.get_search_service_safe()
        except Exception:
            self._search_service = None

    def _resolve_vc_service(self):
        """Best-effort: Observatum's VC lookup service for grid-ref -> VC (None if unavailable)."""
        try:
            from DataEntry import bootstrap
            self._vc_service = bootstrap.get_vc_service_safe()
        except Exception:
            self._vc_service = None
        # VC boundary GeoJSON for the vector fallback map (None if not found)
        self._geojson_path = None
        self._tiles_dir = None
        try:
            import paths
            p = str(paths.VC_GEOJSON)
            if os.path.exists(p):
                self._geojson_path = p
            from DataEntry.raster_map import find_tiles_dir
            self._tiles_dir = find_tiles_dir(str(paths.MAPS_DIR))
            self._maps_dir = str(paths.MAPS_DIR)
        except Exception:
            pass

    def _resolve_codex_path(self):
        """Locate codex.db for the info panel's conservation lookups (None if absent)."""
        try:
            import paths
            p = str(paths.CODEX_DB)
            if os.path.exists(p):
                self._codex_path = p
                return
        except Exception:
            pass
        cand = os.path.join(os.path.dirname(self._db_path), "codex.db")
        self._codex_path = cand if os.path.exists(cand) else None

    def closeEvent(self, event):
        self.backup_now()          # last write before the connection goes
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        super().closeEvent(event)

    # -- ui --------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # No dark title bar -- the tab already reads "Data Entry". Light status notice only.
        root.addWidget(self._safety_banner())

        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        if self._conn is not None and self._schema_error is None:
            self._jobs = JobsListPage(self._conn)
            self._jobs.job_opened.connect(self._open_job)
            self._stack.addWidget(self._jobs)

            self._job_host = QWidget()
            self._job_host.setStyleSheet(f"background: {theme.PAPER};")
            self._job_layout = QVBoxLayout(self._job_host)
            self._job_layout.setContentsMargins(16, 8, 16, 12)
            self._job_layout.setSpacing(6)
            self._stack.addWidget(self._job_host)
            self._stack.setCurrentIndex(0)
        else:
            err = QLabel(f"Could not open the staging schema: {self._schema_error or 'no connection'}")
            err.setStyleSheet(f"color: {theme.CLAY}; padding: 18px; font-size: 13px;")
            err.setWordWrap(True)
            self._stack.addWidget(err)

        self._status = QLabel(self._summary())
        self._status.setStyleSheet(
            f"color: {theme.MUTED}; font-size: 11px; padding: 6px 10px;"
            f"border-top: 1px solid {theme.LINE}; background: {theme.PAPER};"
        )
        root.addWidget(self._status)

    def _safety_banner(self) -> QWidget:
        w = QLabel()
        go_live = getattr(self, "_embedded", False) and self._allow_commit is True
        def _st(bg, fg, accent, bold=600):
            return (f"color: {fg}; background: {bg}; font-weight: {bold}; font-size: 12px;"
                    f"padding: 7px 16px; border-left: 4px solid {accent};")
        if go_live:
            w.setText("LIVE \u2014 commits go into Observatum (observatum.db). Make sure you have a backup.")
            w.setStyleSheet(_st(theme.CLAY_BG, theme._g("danger_text", "#991b1b"), theme.CLAY, 700))
        elif getattr(self, "_embedded", False):
            w.setText("Preview inside Observatum \u2014 dev copy, commit disabled. "
                      "Use \u2018Export\u2019 to take data out; go-live wiring enables commit.")
            w.setStyleSheet(_st(theme.SLATE_BG, theme._g("accent_stats_dark", "#454f5c"), theme.SLATE))
        elif self.is_live_db():
            w.setText("WARNING: LIVE database. (Staging is separate, but work on a dev copy.)")
            w.setStyleSheet(_st(theme.CLAY_BG, theme._g("danger_text", "#991b1b"), theme.CLAY, 700))
        else:
            w.setText("Development copy \u2014 safe to test. Staged jobs live here, uncommitted.")
            w.setStyleSheet(_st(theme.MOSS_BG, theme._g("success_text", "#3d6b4a"), theme.MOSS))
        return w

    def _summary(self) -> str:
        if self._conn is None:
            return "No database connection."
        try:
            n = self._conn.execute("SELECT COUNT(*) FROM entry_jobs WHERE status='active'").fetchone()[0]
            return f"{n} active job{'s' if n != 1 else ''} in {os.path.basename(self._db_path)}."
        except sqlite3.Error as e:
            return f"Staging unavailable: {e}"

    # -- job open: the editable grid -------------------------------------
    def _open_job(self, job_id: int):
        job = repo.get_job(self._conn, job_id)
        if not job:
            return
        while self._job_layout.count():
            item = self._job_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        top = QHBoxLayout()
        back = QPushButton("\u2190 Jobs")
        back.setStyleSheet(theme.button_secondary_qss())
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.clicked.connect(self._back_to_jobs)
        top.addWidget(back)
        bits = [f"<b>{job['name']}</b>", job.get("mode") or ""]
        if job.get("client"): bits.append("client: " + job["client"])
        if job.get("project"): bits.append("project: " + job["project"])
        lab = QLabel("  \u00b7  ".join(b for b in bits if b))
        lab.setTextFormat(Qt.TextFormat.RichText)
        lab.setStyleSheet(f"color: {theme.INK}; font-size: 13px; padding-left: 10px;")
        top.addWidget(lab)
        top.addStretch(1)
        tw = QWidget(); tw.setLayout(top)
        self._job_layout.addWidget(tw)

        from DataEntry.entry_grid import EntryGridPage
        commit_cb = self._do_commit if self._commit_available() else None
        grid = EntryGridPage(self._conn, job_id, self._search_service, self._codex_path,
                             commit_cb, self._vc_service, self._geojson_path, self._tiles_dir, self._maps_dir)
        grid.finished.connect(self._on_job_finished)
        grid.committed.connect(self.committed)  # forward to the host app (reload Observation Data)
        self._job_layout.addWidget(grid, 1)

        self._stack.setCurrentIndex(1)
        self._status.setText(f"Open: {job['name']} ({job.get('mode')}). Staged \u2014 nothing committed."
                             + ("  Previously committed records stay in Observatum; this grid holds "
                                "only new rows." if self._has_committed(job) else ""))

    def _has_committed(self, job) -> bool:
        """True when records for this job's project and client are already in Observatum."""
        if not (job.get("project") and (job.get("mode") or "").lower().startswith("comm")):
            return False
        try:
            return self._conn.execute(
                "SELECT 1 FROM observations WHERE record_type='Commercial' AND project_name=? "
                "AND COALESCE(client,'')=? LIMIT 1",
                (job["project"], job.get("client") or "")).fetchone() is not None
        except sqlite3.Error:
            return False

    def open_project_job(self, project: str, client: str = "", embargo_until=None) -> str:
        """Open (reopening or creating as needed) the Commercial job for this project and
        client, for Commercial Reports' "Add records". Returns 'open', 'reopened' or
        'created', or '' when staging is unavailable."""
        if self._conn is None or not hasattr(self, "_jobs"):
            return ""
        self.backup_now()
        job_id, how = repo.open_project_job(self._conn, project, client, embargo_until)
        self._jobs.open_job_by_id(job_id)     # emits job_opened -> _open_job
        return how

    def _back_to_jobs(self):
        self.backup_now()          # leaving a job: commit / export / discard / Jobs
        self._jobs.refresh()
        self._stack.setCurrentIndex(0)
        self._status.setText(self._summary())

    def _on_job_finished(self):
        # a commit / export / discard completed -> back to the jobs list
        try:
            repo.ensure_personal_job(self._conn)  # keep the standing personal job present
        except Exception:
            pass
        self._back_to_jobs()

    def _commit_available(self) -> bool:
        # explicit override wins (go-live sets True, preview sets False)
        if self._allow_commit is False:
            return False
        if self._allow_commit is True:
            try:
                from DataEntry import bootstrap
                return bootstrap.get_database_safe() is not None
            except Exception:
                return False
        # default (allow_commit is None): standalone only, never in an embedded preview
        if getattr(self, "_embedded", False):
            return False
        try:
            from DataEntry import bootstrap
            return bootstrap.get_database_safe() is not None
        except Exception:
            return False

    def _do_commit(self, job_id, embargo):
        """Commit callback for the grid: write staging rows into observations. Returns summary/None."""
        from DataEntry import bootstrap
        from DataEntry import commit_service as cs
        db = bootstrap.get_database_safe()
        if db is None:
            return None
        model = bootstrap.make_observation_model(db)
        if model is None:
            return None
        job = repo.get_job(self._conn, job_id)
        if not job:
            return None
        # Snapshot observatum.db before the one irreversible action. A failed backup
        # refuses the commit -- None is already handled upstream as 'nothing written'.
        try:
            from shared.backup_service import backup_main_only
            if not backup_main_only('pre-commit'):
                print('[backup] pre-commit backup failed -- commit refused')
                return None
        except Exception as _e:
            print(f'[backup] pre-commit unavailable -- commit refused: {_e}')
            return None

        return cs.commit_job(db, model, self._conn, job, embargo)

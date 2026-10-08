"""
Commercial Reports Dashboard Component.

Provides embargo status tracking, project overview, and release management.

Managing a job (8 Oct 2026): click a project to see its records by survey year and
site. "Add records" opens Data Entry on that project's job -- reopened, or created if
none exists -- carrying the exact project, client and current embargo, so new records
always join the same project. "View / edit" opens Observation Data filtered to the
project; records are edited or deleted there, the one place that deletes.
"""

import sqlite3
from datetime import date

from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox, QDialog, QFormLayout, QComboBox,
    QDialogButtonBox, QCompleter
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont

from ...themes import theme
from ...core.config import TabColors, ButtonColors
from ...models.database import get_database
from .stat_widgets import StatCard


class EditProjectDialog(QDialog):
    """New project name and client for one project, with existing names to pick from."""

    def __init__(self, project, client, projects, clients, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit project / client")
        self.setMinimumWidth(420)
        form = QFormLayout(self)
        intro = QLabel(f"Change the project or client on every record of "
                       f"\u201c{project or '(no project)'}\u201d"
                       + (f" ({client})" if client else "") + ".")
        intro.setWordWrap(True)
        form.addRow(intro)
        self.cmb_project = self._picker(projects, project)
        self.cmb_client = self._picker(clients, client)
        form.addRow("Project", self.cmb_project)
        form.addRow("Client", self.cmb_client)
        self.err = QLabel("")
        self.err.setStyleSheet("color: #a63d40;")
        form.addRow("", self.err)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    @staticmethod
    def _picker(names, current):
        cmb = QComboBox()
        cmb.setEditable(True)
        cmb.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        cmb.addItems([""] + list(names))
        cmb.setCurrentText(current or "")
        comp = QCompleter(list(names), cmb)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        cmb.setCompleter(comp)
        return cmb

    def _accept(self):
        if not self.cmb_project.currentText().strip():
            self.err.setText("A commercial project needs a name.")
            return
        self.accept()

    def values(self):
        return (" ".join(self.cmb_project.currentText().split()),
                " ".join(self.cmb_client.currentText().split()))


class CommercialReportsDashboard(QScrollArea):
    """Dashboard for commercial data management and embargo tracking."""

    report_requested = Signal(str)
    add_records_requested = Signal(str, str, str)   # project, client, embargo_until ('' = none)
    view_project_requested = Signal(str, str)       # project, client

    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = None
        self._initialized = False
        self._setup_ui()

    def _setup_ui(self):
        t = theme()
        self.setWidgetResizable(True)
        self.setStyleSheet(
            f"QScrollArea {{ border: none; background-color: {t.get('background')}; }}"
        )

        container = QWidget()
        self.setWidget(container)
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(32, 24, 32, 32)
        self._layout.setSpacing(16)

        # Alert banner (hidden by default)
        self._alert_frame = QFrame()
        self._alert_frame.setVisible(False)
        self._alert_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #fff3e0;
                border: 1px solid #ffb74d;
                border-radius: 6px;
                padding: 12px;
            }}
        """)
        alert_layout = QHBoxLayout(self._alert_frame)
        alert_layout.setContentsMargins(16, 12, 16, 12)

        self._alert_label = QLabel()
        self._alert_label.setWordWrap(True)
        self._alert_label.setStyleSheet(
            "color: #e65100; font-size: 13px; font-weight: bold; border: none;"
        )
        alert_layout.addWidget(self._alert_label, 1)

        self._layout.addWidget(self._alert_frame)

        # Header
        header = QLabel("Commercial Data Management")
        header.setStyleSheet(
            f"color: {t.get('text_heading')}; font-size: 18px; font-weight: bold;"
        )
        self._layout.addWidget(header)

        # Summary cards row
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        self._active_card = StatCard("Active Embargoes", "0", "projects under embargo",
                                     TabColors.COMMERCIAL)
        cards_layout.addWidget(self._active_card)

        self._expired_card = StatCard("Expired Embargoes", "0", "ready to release",
                                      "#e65100")
        cards_layout.addWidget(self._expired_card)

        self._released_card = StatCard("Released", "0", "uploaded to iRecord",
                                       t.get('success'))
        cards_layout.addWidget(self._released_card)

        self._total_card = StatCard("Total Commercial", "0", "records",
                                    TabColors.COMMERCIAL)
        cards_layout.addWidget(self._total_card)

        self._layout.addLayout(cards_layout)

        # Project breakdown table — collapsible
        self._table_toggle = QPushButton("▼  Project Embargo Status")
        self._table_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._table_toggle.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {t.get('text_heading')};
                font-size: 14px;
                font-weight: bold;
                text-align: left;
                padding: 4px 0;
            }}
            QPushButton:hover {{
                color: {TabColors.COMMERCIAL};
            }}
        """)
        self._table_toggle.clicked.connect(self._toggle_table)
        self._table_expanded = True
        self._layout.addWidget(self._table_toggle)

        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "Project", "Client", "Records", "Species",
            "Embargo Status", "Expires", "Action"
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._table.setColumnWidth(0, 180)
        self._table.setColumnWidth(1, 140)
        self._table.setColumnWidth(2, 70)
        self._table.setColumnWidth(3, 70)
        self._table.setColumnWidth(4, 120)
        self._table.setColumnWidth(5, 100)
        self._table.setColumnWidth(6, 120)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {t.get('border')};
                border-radius: 6px;
                background-color: {t.get('surface')};
                gridline-color: {t.get('border')};
            }}
            QTableWidget::item {{
                padding: 6px 8px;
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                padding: 8px;
                border: none;
                border-bottom: 1px solid {t.get('border')};
                font-weight: 600;
            }}
        """)
        self._table.setMinimumHeight(250)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.itemSelectionChanged.connect(self._on_project_selected)
        self._layout.addWidget(self._table)

        # ---- the selected project: its records, and what to do with them ----
        self._detail = QFrame()
        self._detail.setVisible(False)
        self._detail.setStyleSheet(
            f"QFrame#detail {{ background-color: {t.get('surface')}; "
            f"border: 1px solid {t.get('border')}; border-radius: 6px; }}")
        self._detail.setObjectName("detail")
        dl = QVBoxLayout(self._detail)
        dl.setContentsMargins(16, 12, 16, 12)
        dl.setSpacing(8)
        head = QHBoxLayout()
        self._detail_title = QLabel("")
        self._detail_title.setStyleSheet(
            f"color: {t.get('text_heading')}; font-size: 14px; font-weight: bold; border: none;")
        head.addWidget(self._detail_title, 1)
        self._btn_rename = QPushButton("Edit project / client\u2026")
        self._btn_view = QPushButton("View / edit in Observation Data")
        self._btn_add = QPushButton("Add records\u2026")
        for b, primary in ((self._btn_rename, False), (self._btn_view, False), (self._btn_add, True)):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton {{ background-color: {ButtonColors.PRIMARY if primary else 'transparent'};"
                f" color: {'white' if primary else TabColors.COMMERCIAL};"
                f" border: 1px solid {ButtonColors.PRIMARY if primary else TabColors.COMMERCIAL};"
                f" border-radius: 4px; padding: 5px 12px; font-size: 12px; }}")
            head.addWidget(b)
        self._btn_view.setToolTip("Open Observation Data showing only this project's records. "
                                  "Edit or delete records there.")
        self._btn_add.setToolTip("Open Data Entry on this project's job (reopened, or created), "
                                 "with the same project, client and embargo.")
        self._btn_rename.setToolTip("Rename the project or change its client on every record -- "
                                    "yours, contributed records and Data Entry jobs. Backed up first.")
        self._btn_rename.clicked.connect(self._on_rename_project)
        self._btn_view.clicked.connect(self._on_view_project)
        self._btn_add.clicked.connect(self._on_add_records)
        dl.addLayout(head)
        self._detail_summary = QLabel("")
        self._detail_summary.setWordWrap(True)
        self._detail_summary.setStyleSheet(f"color: {t.get('text_muted')}; font-size: 12px; border: none;")
        dl.addWidget(self._detail_summary)
        self._detail_table = QTableWidget(0, 7)
        self._detail_table.setHorizontalHeaderLabels(
            ["Year", "Site", "Records", "Species", "First", "Last", "Embargo"])
        self._detail_table.verticalHeader().setVisible(False)
        self._detail_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._detail_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._detail_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._detail_table.setMinimumHeight(160)
        dl.addWidget(self._detail_table)
        self._layout.addWidget(self._detail)
        self._selected_project = None    # (project, client, embargo_until)

        # Future reports placeholder
        future_label = QLabel("Reports: Site Species List, Project Summary, "
                              "Site Comparison, Survey Effort — coming soon")
        future_label.setStyleSheet(
            f"color: {t.get('text_muted')}; font-size: 12px; font-style: italic;"
        )
        future_label.setAlignment(Qt.AlignCenter)
        self._layout.addWidget(future_label)

        self._layout.addStretch()

    def refresh(self, observation_model=None):
        """Refresh the dashboard with current data."""
        db = get_database()
        if not db:
            return

        try:
            main_path = (db.get_main_path() if hasattr(db, 'get_main_path')
                         else str(db._main_db_path))
            conn = sqlite3.connect(main_path)
            today = date.today().isoformat()

            # Get project breakdown
            cursor = conn.execute("""
                SELECT project_name, client, embargo_status, embargo_until,
                       COUNT(*) as record_count,
                       COUNT(DISTINCT species_name) as species_count
                FROM observations
                WHERE record_type = 'Commercial'
                GROUP BY project_name, client, embargo_status, embargo_until
                ORDER BY embargo_status DESC, project_name
            """)
            projects = cursor.fetchall()

            # Calculate summaries
            active_projects = 0
            active_records = 0
            expired_projects = 0
            expired_records = 0
            released_projects = 0
            released_records = 0
            total_records = 0
            no_embargo_records = 0

            table_rows = []
            for proj, client, status, until, records, species in projects:
                total_records += records
                proj_name = proj or "(no project)"
                client_name = client or ""

                if status == "Active" and until and until > today:
                    display_status = "Under Embargo"
                    active_projects += 1
                    active_records += records
                elif status == "Active" and until and until <= today:
                    display_status = "EXPIRED"
                    expired_projects += 1
                    expired_records += records
                elif status == "Released":
                    display_status = "Released"
                    released_projects += 1
                    released_records += records
                else:
                    display_status = "No Embargo"
                    no_embargo_records += records

                table_rows.append((
                    proj_name, client_name, records, species,
                    display_status, until or "", status or ""
                ))

            conn.close()

            # Update cards
            self._active_card.set_value(
                str(active_projects),
                f"{active_records:,} records under embargo"
            )
            self._expired_card.set_value(
                str(expired_projects),
                f"{expired_records:,} records ready to release"
            )
            self._released_card.set_value(
                str(released_projects),
                f"{released_records:,} records released"
            )
            self._total_card.set_value(
                f"{total_records:,}",
                "commercial records"
            )

            # Alert banner
            if expired_projects > 0:
                self._alert_label.setText(
                    f"⚠ {expired_projects} project(s) with {expired_records:,} records "
                    f"have expired embargo periods — ready for iRecord upload. "
                    f"Export to iRecord, then click 'Release' below."
                )
                self._alert_frame.setVisible(True)
            else:
                self._alert_frame.setVisible(False)

            # Populate table
            self._table.setRowCount(len(table_rows))
            keep = self._selected_project
            self._table.blockSignals(True)
            for row_idx, (proj, client, records, species, status, until, raw_status) in enumerate(table_rows):
                name_item = QTableWidgetItem(proj)
                # the raw names: "(no project)" is display only
                name_item.setData(Qt.ItemDataRole.UserRole,
                                  (proj if proj != "(no project)" else "", client))
                self._table.setItem(row_idx, 0, name_item)
                self._table.setItem(row_idx, 1, QTableWidgetItem(client))

                records_item = QTableWidgetItem(str(records))
                records_item.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(row_idx, 2, records_item)

                species_item = QTableWidgetItem(str(species))
                species_item.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(row_idx, 3, species_item)

                status_item = QTableWidgetItem(status)
                status_item.setTextAlignment(Qt.AlignCenter)
                if status == "EXPIRED":
                    status_item.setForeground(QColor("#e65100"))
                    status_item.setFont(QFont("", -1, QFont.Weight.Bold))
                elif status == "Under Embargo":
                    status_item.setForeground(QColor(TabColors.COMMERCIAL))
                elif status == "Released":
                    status_item.setForeground(QColor("#2e7d32"))
                self._table.setItem(row_idx, 4, status_item)

                self._table.setItem(row_idx, 5, QTableWidgetItem(until))

                # Action button
                if status == "EXPIRED" or status == "Under Embargo":
                    btn = QPushButton("Release")
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {ButtonColors.PRIMARY};
                            color: white;
                            border: none;
                            border-radius: 4px;
                            padding: 4px 12px;
                            font-size: 11px;
                        }}
                        QPushButton:hover {{
                            background-color: #3d6b4a;
                        }}
                    """)
                    btn.clicked.connect(
                        lambda checked, p=proj, c=client, s=raw_status:
                        self._release_project(p if p != "(no project)" else "", c)
                    )
                    self._table.setCellWidget(row_idx, 6, btn)
                elif status == "Released":
                    released_label = QLabel("✓ Released")
                    released_label.setAlignment(Qt.AlignCenter)
                    released_label.setStyleSheet(
                        "color: #2e7d32; font-size: 11px; border: none;"
                    )
                    self._table.setCellWidget(row_idx, 6, released_label)
            self._table.blockSignals(False)
            if keep:                       # keep the open project open across a refresh
                self._show_project(keep[0], keep[1])

        except Exception as e:
            print(f"[CommercialReports] Error refreshing: {e}")
            import traceback
            traceback.print_exc()

    # ---- project detail -------------------------------------------------
    def _main_path(self):
        db = get_database()
        if not db:
            return None
        return db.get_main_path() if hasattr(db, 'get_main_path') else str(db._main_db_path)

    def _on_project_selected(self):
        r = self._table.currentRow()
        item = self._table.item(r, 0) if r >= 0 else None
        if item is None:
            return
        project, client = item.data(Qt.ItemDataRole.UserRole) or ("", "")
        self._show_project(project, client)

    def _show_project(self, project: str, client: str):
        """Fill the detail panel for one project + client: records by survey year and site."""
        path = self._main_path()
        if not path:
            return
        where = ("record_type = 'Commercial' AND COALESCE(project_name,'') = ? "
                 "AND COALESCE(client,'') = ?")
        params = (project or "", client or "")
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            rows = conn.execute(f"""
                SELECT substr(date,1,4), COALESCE(NULLIF(TRIM(site_name),''), '(no site)'),
                       COUNT(*), COUNT(DISTINCT species_name), MIN(date), MAX(date),
                       MAX(CASE WHEN embargo_status='Active' THEN embargo_until END),
                       SUM(embargo_status='Released')
                FROM observations WHERE {where}
                GROUP BY 1, 2 ORDER BY 1 DESC, 2""", params).fetchall()
            n, nsp = conn.execute(
                f"SELECT COUNT(*), COUNT(DISTINCT species_name) FROM observations WHERE {where}",
                params).fetchone()
            emb = conn.execute(
                f"SELECT MAX(embargo_until) FROM observations WHERE {where} "
                "AND embargo_status='Active' AND embargo_until > date('now')", params).fetchone()[0]
            conn.close()
        except sqlite3.Error as e:
            print(f"[CommercialReports] project detail failed: {e}")
            return

        def dmy(s):
            s = str(s or "")
            return f"{s[8:10]}/{s[5:7]}/{s[:4]}" if len(s) >= 10 and s[4] == "-" else s

        self._selected_project = (project, client, emb or "")
        self._detail_title.setText((project or "(no project)") + (f"  \u2014  {client}" if client else ""))
        years = sorted({r[0] for r in rows if r[0]}, reverse=True)
        self._detail_summary.setText(
            f"{n:,} record{'s' if n != 1 else ''}, {nsp:,} species, {len(rows)} site-year"
            f"{'s' if len(rows) != 1 else ''}"
            + (f" across {', '.join(years)}" if years else "")
            + (f".  Embargoed until {dmy(emb)}." if emb else ".  No embargo in force."))
        self._detail_table.setRowCount(len(rows))
        for i, (yr, site, cnt, sp, first, last, until, released) in enumerate(rows):
            emb_txt = (f"until {dmy(until)}" if until else
                       "Released" if released else "none")
            for c, v in enumerate([yr or "", site, f"{cnt:,}", f"{sp:,}", dmy(first), dmy(last), emb_txt]):
                it = QTableWidgetItem(v)
                if c in (0, 2, 3, 4, 5):
                    it.setTextAlignment(Qt.AlignCenter)
                self._detail_table.setItem(i, c, it)
        self._detail_table.resizeColumnsToContents()
        self._detail_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._btn_add.setEnabled(bool(project))   # a job needs a project name
        self._detail.setVisible(True)

    def _on_add_records(self):
        if self._selected_project and self._selected_project[0]:
            self.add_records_requested.emit(*self._selected_project)

    def _on_rename_project(self):
        """Change project and/or client across observations, contributed records and jobs."""
        if not self._selected_project:
            return
        from shared import project_rename as pr
        old_p, old_c = self._selected_project[0], self._selected_project[1]
        path = self._main_path()
        if not path:
            return
        try:
            ro = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            names = ro.execute(
                "SELECT DISTINCT TRIM(project_name), TRIM(COALESCE(client,'')) FROM observations "
                "WHERE record_type='Commercial' AND COALESCE(TRIM(project_name),'')!=''").fetchall()
            before = pr.plan(ro, old_p, old_c)
            ro.close()
        except sqlite3.Error as e:
            QMessageBox.warning(self, "Edit project", f"Could not read the records:\n{e}")
            return
        projects = sorted({p for p, _ in names}, key=str.casefold)
        clients = sorted({c for _, c in names if c}, key=str.casefold)
        dlg = EditProjectDialog(old_p, old_c, projects, clients, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_p, new_c = dlg.values()
        if (new_p, new_c) == ((old_p or "").strip(), (old_c or "").strip()):
            return
        ro = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        clash = pr.plan(ro, new_p, new_c)
        ro.close()
        label = {"observations": "own records", "contributed_observations": "contributed records",
                 "entry_jobs": "Data Entry job(s)"}
        lines = [f"  {before[t]:,} {label[t]}" for t in before if before[t]]
        msg = (f"Change\n  {old_p or '(no project)'}" + (f"  \u2014  {old_c}" if old_c else "")
               + f"\nto\n  {new_p}" + (f"  \u2014  {new_c}" if new_c else "  (no client)")
               + "\n\non:\n" + "\n".join(lines))
        if clash.get("observations") or clash.get("contributed_observations"):
            msg += (f"\n\n\u26a0 {clash.get('observations', 0) + clash.get('contributed_observations', 0):,} "
                    "records already carry that project and client. The two will MERGE into one "
                    "project in Examen and here.")
        msg += "\n\nObservatum is backed up first. Saved Examen snapshots keep the old name."
        if QMessageBox.question(self, "Edit project / client", msg,
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            from shared.backup_service import backup_main_only
            if not backup_main_only("pre-project-rename"):
                QMessageBox.warning(self, "Edit project", "The backup failed, so nothing was changed.")
                return
        except Exception as e:
            QMessageBox.warning(self, "Edit project", f"Backup unavailable, so nothing was changed.\n{e}")
            return
        try:
            conn = sqlite3.connect(path)
            done = pr.rename(conn, (old_p, old_c), (new_p, new_c))
            conn.close()
        except (sqlite3.Error, ValueError) as e:
            QMessageBox.warning(self, "Edit project", f"Nothing was changed:\n{e}")
            return
        self._selected_project = (new_p, new_c, self._selected_project[2])
        self.refresh()
        QMessageBox.information(
            self, "Edit project / client",
            "Updated " + ", ".join(f"{n:,} {label[t]}" for t, n in done.items() if n) + ".")

    def _on_view_project(self):
        if self._selected_project:
            self.view_project_requested.emit(self._selected_project[0], self._selected_project[1])

    def _toggle_table(self):
        """Toggle the project table visibility."""
        self._table_expanded = not self._table_expanded
        self._table.setVisible(self._table_expanded)
        arrow = "▼" if self._table_expanded else "▶"
        self._table_toggle.setText(f"{arrow}  Project Embargo Status")

    def _release_project(self, project_name: str, client: str):
        """Mark all records for a project as Released."""
        reply = QMessageBox.question(
            self,
            "Release Embargo",
            f"Mark all records for '{project_name or '(no project)'}' "
            f"as Released?\n\nThis confirms the data has been uploaded "
            f"to iRecord and removes the embargo.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            db = get_database()
            main_path = (db.get_main_path() if hasattr(db, 'get_main_path')
                         else str(db._main_db_path))
            conn = sqlite3.connect(main_path)

            if project_name:
                conn.execute("""
                    UPDATE observations
                    SET embargo_status = 'Released'
                    WHERE record_type = 'Commercial'
                    AND project_name = ?
                    AND (client = ? OR (client IS NULL AND ? = ''))
                """, (project_name, client, client))
            else:
                conn.execute("""
                    UPDATE observations
                    SET embargo_status = 'Released'
                    WHERE record_type = 'Commercial'
                    AND (project_name IS NULL OR project_name = '')
                    AND (client = ? OR (client IS NULL AND ? = ''))
                """, (client, client))

            conn.commit()
            updated = conn.total_changes
            conn.close()

            QMessageBox.information(
                self, "Embargo Released",
                f"Updated records for '{project_name or '(no project)'}' "
                f"to Released status."
            )

            self.refresh()

        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to release embargo: {e}"
            )

    def apply_theme(self):
        t = theme()
        self.setStyleSheet(
            f"QScrollArea {{ border: none; background-color: {t.get('background')}; }}"
        )

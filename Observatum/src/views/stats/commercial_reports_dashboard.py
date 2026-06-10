"""
Commercial Reports Dashboard Component.

Provides embargo status tracking, project overview, and release management.
Future: Site Species List, Project Summary, Site Comparison, Survey Effort reports.
"""

import sqlite3
from datetime import date

from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont

from ...themes import theme
from ...core.config import TabColors, ButtonColors
from ...models.database import get_database
from .stat_widgets import StatCard


class CommercialReportsDashboard(QScrollArea):
    """Dashboard for commercial data management and embargo tracking."""

    report_requested = Signal(str)

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
        self._layout.addWidget(self._table)

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
            for row_idx, (proj, client, records, species, status, until, raw_status) in enumerate(table_rows):
                self._table.setItem(row_idx, 0, QTableWidgetItem(proj))
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

        except Exception as e:
            print(f"[CommercialReports] Error refreshing: {e}")
            import traceback
            traceback.print_exc()

    def _toggle_table(self):
        """Toggle the project table visibility."""
        self._table_expanded = not self._table_expanded
        self._table.setVisible(self._table_expanded)
        arrow = "▼" if self._table_expanded else "▶"
        self._table_toggle.setText(f"{arrow}  Project Embargo Status")

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

"""
Database Settings Panel Component.

Settings for database paths, statistics, backup, and maintenance.
"""

from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QGridLayout, QFrame, QFileDialog, QMessageBox
)
from PySide6.QtCore import Signal, QSettings, Qt

from ...themes import theme


class DatabaseSettingsPanel(QScrollArea):
    """Database settings panel."""
    
    database_changed = Signal()
    
    def __init__(self, db_manager=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        t = theme()
        
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 20, 20)
        layout.setSpacing(24)
        
        # Database Locations section
        self._setup_paths_section(layout)
        
        # Database Statistics section
        self._setup_stats_section(layout)
        
        # Maintenance section
        self._setup_maintenance_section(layout)
        
        layout.addStretch()
        self.setWidget(content)
    
    def _get_frame_style(self) -> str:
        """Get standard frame style."""
        t = theme()
        return f"background-color: {t.get('surface_alt')}; border: 1px solid {t.get('border')}; border-radius: 6px; padding: 12px;"
    
    def _get_link_button_style(self) -> str:
        """Get link-style button."""
        t = theme()
        return f"color: {t.get('success')}; border: none; padding: 4px;"
    
    def _setup_paths_section(self, layout):
        """Set up database paths section."""
        t = theme()
        
        paths_group = QGroupBox("Database Locations")
        paths_layout = QVBoxLayout(paths_group)
        paths_layout.setSpacing(12)
        
        # Main database
        main_db_frame = QFrame()
        main_db_frame.setStyleSheet(self._get_frame_style())
        main_db_layout = QHBoxLayout(main_db_frame)
        
        main_db_info = QVBoxLayout()
        main_db_info.addWidget(QLabel("<b>Main Database</b>"))
        self.main_db_path = QLabel()
        self.main_db_path.setStyleSheet(f"font-family: monospace; font-size: 11px; color: {t.get('text_secondary')};")
        self.main_db_path.setWordWrap(True)
        main_db_info.addWidget(self.main_db_path)
        main_db_layout.addLayout(main_db_info, 1)
        
        change_main_btn = QPushButton("Change")
        change_main_btn.setStyleSheet(self._get_link_button_style())
        change_main_btn.clicked.connect(self._change_main_db)
        main_db_layout.addWidget(change_main_btn)
        
        paths_layout.addWidget(main_db_frame)
        
        # UKSI database
        uksi_db_frame = QFrame()
        uksi_db_frame.setStyleSheet(self._get_frame_style())
        uksi_db_layout = QHBoxLayout(uksi_db_frame)
        
        uksi_db_info = QVBoxLayout()
        uksi_db_info.addWidget(QLabel("<b>UKSI Reference Database</b>"))
        self.uksi_db_path = QLabel()
        self.uksi_db_path.setStyleSheet(f"font-family: monospace; font-size: 11px; color: {t.get('text_secondary')};")
        self.uksi_db_path.setWordWrap(True)
        uksi_db_info.addWidget(self.uksi_db_path)
        uksi_db_layout.addLayout(uksi_db_info, 1)
        
        update_uksi_btn = QPushButton("Update")
        update_uksi_btn.setStyleSheet(self._get_link_button_style())
        update_uksi_btn.clicked.connect(self._update_uksi_db)
        uksi_db_layout.addWidget(update_uksi_btn)
        
        paths_layout.addWidget(uksi_db_frame)
        
        layout.addWidget(paths_group)
    
    def _setup_stats_section(self, layout):
        """Set up database statistics section."""
        t = theme()
        
        stats_group = QGroupBox("Database Statistics")
        stats_layout = QGridLayout(stats_group)
        stats_layout.setSpacing(12)
        
        self._stat_labels = {}
        stats = [
            ('observations', 'Observation Records'),
            ('commercial', 'Commercial Records'),
            ('scheme', 'Recording Scheme Records'),
            ('specimens', 'Specimen Records'),
        ]
        
        for i, (key, label) in enumerate(stats):
            row, col = i // 2, i % 2
            stat_frame = QFrame()
            stat_frame.setStyleSheet(self._get_frame_style())
            stat_layout = QVBoxLayout(stat_frame)
            stat_layout.setContentsMargins(12, 8, 12, 8)
            
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
            stat_layout.addWidget(lbl)
            
            value_lbl = QLabel("--")
            value_lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {t.get('text_primary')};")
            stat_layout.addWidget(value_lbl)
            self._stat_labels[key] = value_lbl
            
            stats_layout.addWidget(stat_frame, row, col)
        
        layout.addWidget(stats_group)
    
    def _setup_maintenance_section(self, layout):
        """Set up maintenance section."""
        t = theme()

        maint_group = QGroupBox("Maintenance")
        maint_layout = QVBoxLayout(maint_group)
        maint_layout.setSpacing(12)

        # Database size
        self.db_size_label = QLabel("Current size: --")
        self.db_size_label.setStyleSheet(f"color: {t.get('text_muted')}; font-size: 11px;")
        maint_layout.addWidget(self.db_size_label)

        # Backup/Restore buttons
        btn_layout = QHBoxLayout()
        backup_btn = QPushButton("Backup Database")
        backup_btn.clicked.connect(self._backup_database)
        btn_layout.addWidget(backup_btn)

        restore_btn = QPushButton("Restore from Backup")
        restore_btn.clicked.connect(self._restore_database)
        btn_layout.addWidget(restore_btn)
        btn_layout.addStretch()
        maint_layout.addLayout(btn_layout)

        # Species Alias Manager
        alias_btn = QPushButton("Manage Species Aliases")
        alias_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        alias_btn.clicked.connect(self._open_alias_manager)
        maint_layout.addWidget(alias_btn)

        layout.addWidget(maint_group)

    def _open_alias_manager(self):
        """Open the species alias manager dialog."""
        from ..dialogs.alias_manager_dialog import AliasManagerDialog
        dialog = AliasManagerDialog(db_manager=self.db_manager, parent=self)
        dialog.exec()

    def load_settings(self):
        """Public method to load settings. Called by settings_tab.py."""
        self._load_settings()
    
    def _load_settings(self):
        """Load settings from QSettings."""
        settings = QSettings()
        self.main_db_path.setText(settings.value("databases/main_path", "Not configured"))
        self.uksi_db_path.setText(settings.value("databases/uksi_path", "Not configured"))
    
    def refresh(self):
        """Refresh the panel after database connection."""
        if self.db_manager:
            if self.db_manager.main_db_path:
                self.main_db_path.setText(str(self.db_manager.main_db_path))
            if self.db_manager.uksi_db_path:
                self.uksi_db_path.setText(str(self.db_manager.uksi_db_path))
        
        self._refresh_stats()
    
    def _refresh_stats(self):
        """Refresh database statistics from actual database."""
        if not self.db_manager or not self.db_manager.main_db_path:
            return
            
        try:
            # Count observations
            try:
                result = self.db_manager.execute_main(
                    "SELECT COUNT(*) as count FROM observations"
                )
                self._stat_labels['observations'].setText(f"{result[0]['count']:,}")
            except Exception:
                self._stat_labels['observations'].setText("--")
            
            # Count commercial records
            try:
                result = self.db_manager.execute_main(
                    "SELECT COUNT(*) as count FROM observations WHERE record_type = 'Commercial'"
                )
                self._stat_labels['commercial'].setText(f"{result[0]['count']:,}")
            except Exception:
                self._stat_labels['commercial'].setText("--")
            
            # Count scheme records
            try:
                result = self.db_manager.execute_main(
                    "SELECT COUNT(*) as count FROM recording_scheme"
                )
                self._stat_labels['scheme'].setText(f"{result[0]['count']:,}")
            except Exception:
                self._stat_labels['scheme'].setText("--")
            
            # Count specimens
            try:
                result = self.db_manager.execute_main(
                    "SELECT COUNT(*) as count FROM specimens"
                )
                self._stat_labels['specimens'].setText(f"{result[0]['count']:,}")
            except Exception:
                self._stat_labels['specimens'].setText("--")
                
            # Update database size
            try:
                import os
                size_bytes = os.path.getsize(self.db_manager.main_db_path)
                if size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                self.db_size_label.setText(f"Current size: {size_str}")
            except Exception:
                pass
                
        except Exception as e:
            print(f"Error refreshing stats: {e}")
    
    def _change_main_db(self):
        """Change main database path."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Main Database", "", "SQLite Database (*.db)"
        )
        if path:
            try:
                import sqlite3
                conn = sqlite3.connect(path)
                conn.execute("SELECT 1")
                conn.close()
            except Exception as e:
                QMessageBox.warning(self, "Invalid Database", 
                    f"The selected file is not a valid SQLite database:\n{e}")
                return
            
            settings = QSettings()
            settings.setValue("databases/main_path", path)
            settings.sync()
            self.main_db_path.setText(path)
            
            if self.db_manager:
                try:
                    self.db_manager.set_main_path(path)
                    self._refresh_stats()
                    self.database_changed.emit()
                    QMessageBox.information(self, "Database Connected",
                        f"Main database connected successfully.\n\nPath: {path}")
                except Exception as e:
                    QMessageBox.warning(self, "Connection Error", f"Could not connect: {e}")
    
    def _update_uksi_db(self):
        """Update UKSI database path."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select UKSI Database", "", "SQLite Database (*.db)"
        )
        if path:
            try:
                import sqlite3
                conn = sqlite3.connect(path)
                conn.execute("SELECT 1")
                conn.close()
            except Exception as e:
                QMessageBox.warning(self, "Invalid Database", 
                    f"The selected file is not a valid SQLite database:\n{e}")
                return
            
            settings = QSettings()
            settings.setValue("databases/uksi_path", path)
            settings.sync()
            self.uksi_db_path.setText(path)
            
            if self.db_manager:
                try:
                    self.db_manager.set_uksi_path(path)
                    self.database_changed.emit()
                    QMessageBox.information(self, "Database Connected",
                        f"UKSI database connected successfully.\n\nPath: {path}")
                except Exception as e:
                    QMessageBox.warning(self, "Connection Error", f"Could not connect: {e}")
    
    def _backup_database(self):
        """Backup database by copying the file."""
        if not self.db_manager or not self.db_manager.main_db_path:
            QMessageBox.warning(self, "Backup", "No database configured.")
            return

        import os
        default_name = os.path.splitext(os.path.basename(self.db_manager.main_db_path))[0]
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Backup", f"{default_name}_backup.db", "SQLite Database (*.db)"
        )
        if path:
            try:
                # SQLite online backup API -- consistent even with the database
                # open in WAL mode, which shutil.copy2 is not.
                self.db_manager.backup_main(path)
                QMessageBox.information(self, "Backup", f"Database backed up to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Backup Failed", f"Could not backup database:\n{e}")

    def _restore_database(self):
        """Restoring is done with the app closed -- point the user at the script.

        Replacing a database file while Observatum holds it open leaves stale
        -wal / -shm side-files that do not match the restored main file. The
        standalone script checks the chosen backup before touching anything,
        takes a safety copy via the SQLite backup API, clears the side-files,
        and verifies the result.
        """
        QMessageBox.information(
            self, "Restore Database",
            "Restoring is done with Observatum closed, so that nothing is "
            "holding the database while it is replaced.\n\n"
            "1. Close Observatum.\n"
            "2. Open a terminal in the project folder.\n"
            "3. Run:   python scripts\\restore_database.py\n\n"
            "It lists the available backups with their record counts and dates, "
            "checks the one you choose before touching anything, and takes a "
            "safety copy of your current database first."
        )


    def apply_theme(self):
        """Apply the current theme to all components."""
        t = theme()
        
        # Re-apply styles to frames - would require storing references
        # For now, the panel would need to be rebuilt for full theme refresh
        pass

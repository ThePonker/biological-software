"""
Sync Settings Panel Component.

iRecord synchronisation settings and progress dialog.
"""

from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QCheckBox, QGroupBox, QFrame,
    QDialog, QProgressBar
)
from PySide6.QtCore import Qt, QSettings

from ...themes import theme
from ...core.config import Settings


class SyncProgressDialog(QDialog):
    """Dialog showing iRecord sync progress and results."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("iRecord Sync")
        self.setFixedSize(450, 400)
        self.setModal(True)
        self._setup_ui()
    
    def _setup_ui(self):
        t = theme()
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Progress area (shown during sync)
        self.progress_frame = QFrame()
        progress_layout = QVBoxLayout(self.progress_frame)
        progress_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setMinimumWidth(300)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("Syncing with iRecord...")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setStyleSheet(f"font-weight: bold; color: {t.get('text_primary')};")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_detail = QLabel("Downloading and processing records")
        self.progress_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_detail.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
        progress_layout.addWidget(self.progress_detail)
        
        layout.addWidget(self.progress_frame)
        
        # Results area (shown after sync)
        self.results_frame = QFrame()
        self.results_frame.hide()
        results_layout = QVBoxLayout(self.results_frame)
        
        # Summary grid
        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(8)
        
        self._summary_labels = {}
        self._summary_frames = []
        
        # Define summary items with theme token mappings
        summaries = [
            ('new', 'New', 'success'),
            ('updated', 'Updated', 'info'),
            ('unchanged', 'Unchanged', 'text_secondary'),
            ('errors', 'Errors', 'error'),
        ]
        
        for key, label, color_key in summaries:
            frame = QFrame()
            # Use appropriate background based on color key
            if color_key == 'success':
                bg = t.get('success_bg_light')
            elif color_key == 'info':
                bg = t.get('info_bg_light')
            elif color_key == 'error':
                bg = t.get('error_bg_light')
            else:
                bg = t.get('surface_alt')
            
            frame.setStyleSheet(f"background-color: {bg}; border-radius: 6px; padding: 8px;")
            frame_layout = QVBoxLayout(frame)
            frame_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            color = t.get(color_key) if color_key in ['success', 'info', 'error'] else t.get('text_secondary')
            
            value_lbl = QLabel("0")
            value_lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")
            value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame_layout.addWidget(value_lbl)
            
            name_lbl = QLabel(label)
            name_lbl.setStyleSheet(f"font-size: 11px; color: {color};")
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame_layout.addWidget(name_lbl)
            
            summary_layout.addWidget(frame)
            self._summary_labels[key] = value_lbl
            self._summary_frames.append(frame)
        
        results_layout.addLayout(summary_layout)
        
        # Details area
        self.details_label = QLabel()
        self.details_label.setWordWrap(True)
        self.details_label.setStyleSheet(f"color: {t.get('text_primary')}; font-size: 12px;")
        results_layout.addWidget(self.details_label)
        
        layout.addWidget(self.results_frame)
        
        # Close button
        self.close_btn = QPushButton("Done")
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('success')};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {t.get('success_hover')}; }}
        """)
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.hide()
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)
    
    def show_results(self, new=0, updated=0, unchanged=0, errors=0):
        """Show sync results."""
        self.progress_frame.hide()
        self.results_frame.show()
        self.close_btn.show()
        
        self._summary_labels['new'].setText(str(new))
        self._summary_labels['updated'].setText(str(updated))
        self._summary_labels['unchanged'].setText(str(unchanged))
        self._summary_labels['errors'].setText(str(errors))


class SyncSettingsPanel(QScrollArea):
    """iRecord sync settings panel."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
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
        
        # Info banner
        self._setup_info_banner(layout)
        
        # Sync settings group
        # Protected fields group
        self._setup_protected_fields(layout)
        
        # Conflict resolution group
        
        layout.addStretch()
        self.setWidget(content)
    
    def _setup_info_banner(self, layout):
        """Set up info banner with sync status."""
        t = theme()

        info_frame = QFrame()
        info_frame.setStyleSheet(f"background-color: {t.get('info_bg_light')}; border: 1px solid {t.get('info_border')}; border-radius: 6px; padding: 12px;")
        info_layout = QVBoxLayout(info_frame)

        info_title = QLabel("ℹ️ One-way sync: iRecord → Observatum")
        info_title.setStyleSheet(f"font-weight: bold; color: {t.get('info')};")
        info_layout.addWidget(info_title)

        info_text = QLabel("iRecord is the authoritative source. Changes made on iRecord will update local records during sync. Local changes do not overwrite iRecord data.")
        info_text.setStyleSheet(f"color: {t.get('info')}; font-size: 12px;")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)

        # Sync status row
        sync_status_layout = QHBoxLayout()
        sync_status_layout.setContentsMargins(0, 8, 0, 0)
        
        sync_method_label = QLabel("Sync Method: Manual (CSV download)")
        sync_method_label.setStyleSheet(f"color: {t.get('info')}; font-size: 12px;")
        sync_status_layout.addWidget(sync_method_label)
        
        sync_status_layout.addStretch()
        
        self.last_sync_label = QLabel("Last Sync: Never")
        self.last_sync_label.setStyleSheet(f"color: {t.get('info')}; font-size: 12px;")
        sync_status_layout.addWidget(self.last_sync_label)
        
        info_layout.addLayout(sync_status_layout)

        layout.addWidget(info_frame)

    def _setup_sync_settings(self, layout):
        """Set up sync settings group."""
        t = theme()
        
        sync_group = QGroupBox("iRecord Synchronisation")
        sync_layout = QVBoxLayout(sync_group)
        sync_layout.setSpacing(16)
        
        # Sync method
        method_layout = QHBoxLayout()
        method_layout.addWidget(QLabel("Sync Method:"))
        self.sync_method = QComboBox()
        self.sync_method.addItems(["Manual (CSV download)", "Weekly reminder", "Monthly reminder"])
        self.sync_method.setMinimumHeight(28)
        method_layout.addWidget(self.sync_method, 1)
        sync_layout.addLayout(method_layout)
        
        # Last sync and sync button
        last_sync_frame = QFrame()
        last_sync_frame.setStyleSheet(f"background-color: {t.get('surface_alt')}; border: 1px solid {t.get('border')}; border-radius: 6px; padding: 12px;")
        last_sync_layout = QHBoxLayout(last_sync_frame)
        
        last_sync_info = QVBoxLayout()
        last_sync_info.addWidget(QLabel("<b>Last Sync</b>"))
        self.last_sync_label = QLabel("Never")
        self.last_sync_label.setStyleSheet(f"color: {t.get('text_secondary')};")
        last_sync_info.addWidget(self.last_sync_label)
        last_sync_layout.addLayout(last_sync_info, 1)
        
        sync_now_btn = QPushButton("Sync Now")
        sync_now_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('success')};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {t.get('success_hover')}; }}
        """)
        sync_now_btn.clicked.connect(self._sync_now)
        last_sync_layout.addWidget(sync_now_btn)
        
        sync_layout.addWidget(last_sync_frame)
        
        layout.addWidget(sync_group)
    
    def _setup_protected_fields(self, layout):
        """Set up protected fields group."""
        t = theme()
        
        protected_group = QGroupBox("Protected Local Fields")
        protected_layout = QVBoxLayout(protected_group)
        
        protected_desc = QLabel("These fields are never overwritten during iRecord sync:")
        protected_desc.setStyleSheet(f"color: {t.get('text_secondary')}; margin-bottom: 8px;")
        protected_layout.addWidget(protected_desc)
        
        for field in ["Site name (local)", "Internal notes", "Specimen links", "Embargo status"]:
            field_lbl = QLabel(f"✔ {field}")
            field_lbl.setStyleSheet(f"color: {t.get('success')};")
            protected_layout.addWidget(field_lbl)
        
        layout.addWidget(protected_group)
    
    def _setup_conflict_resolution(self, layout):
        """Set up conflict resolution group."""
        conflict_group = QGroupBox("Conflict Resolution")
        conflict_layout = QVBoxLayout(conflict_group)
        
        self.auto_accept = QCheckBox("Automatically accept iRecord changes (recommended)")
        self.auto_accept.setChecked(True)
        conflict_layout.addWidget(self.auto_accept)
        
        self.prompt_overwrite = QCheckBox("Prompt before overwriting local data")
        conflict_layout.addWidget(self.prompt_overwrite)
        
        layout.addWidget(conflict_group)
    
    def load_settings(self):
        """Public method to load settings. Called by settings_tab.py."""
        self._load_settings()
    
    def _load_settings(self):
        """Load settings from QSettings."""
        settings = QSettings()
        last_sync = settings.value(Settings.SYNC_LAST_SYNC, "Never")
        self.last_sync_label.setText(f"Last Sync: {last_sync}")

    def _sync_now(self):
        """Show instructions for iRecord sync via Import Wizard."""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "iRecord Sync",
            "To sync with iRecord:\n\n"
            "1. Download your records from iRecord as CSV\n"
            "2. Go to Observation Data tab\n"
            "3. Click Import > iRecord Download\n\n"
            "This will match and update your local records."
        )

        settings = QSettings()
        settings.setValue(Settings.SYNC_METHOD, self.sync_method.currentText())
    
    def apply_theme(self):
        """Apply the current theme to all components."""
        # Would need to store frame references for full theme update
        pass
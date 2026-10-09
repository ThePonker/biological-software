"""
General Settings Panel Component.

Settings for defaults, date format, and theme.

UPDATED: Removed font size and grid ref format settings
UPDATED: All settings now auto-save on change
UPDATED: Fixed signal blocking during load to prevent settings corruption
"""

from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QCheckBox, QGroupBox, QGridLayout, QFrame,
    QPushButton, QCompleter
)
from PySide6.QtCore import Signal, QSettings, Qt

from ...themes import theme
from ...utils.constants import (
    DATE_FORMAT_OPTIONS
)

# Import centralised config
from ...core.config import Settings, Defaults
from shared.db_open import connect_ro  # D9: reference data, read-only


class GeneralSettingsPanel(QScrollArea):
    """General settings panel."""

    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._loading = False  # Flag to prevent saves during load
        self._setup_ui()
        self._connect_auto_save()
        self._load_settings()

    def _setup_ui(self):
        t = theme()

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"background-color: {t.get('background')};")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 20, 20)
        layout.setSpacing(24)

        # Theme section
        self._setup_theme_section(layout)

        # Default Values section
        self._setup_defaults_section(layout)

        # Common Name Display section
        self._setup_common_names_section(layout)

        # Display Preferences section (date format only)
        self._setup_display_section(layout)

        # Automatic Calculations section
        self._setup_auto_section(layout)

        # Filter Bar Defaults section
        self._setup_scheme_section(layout)
        self._setup_filter_defaults_section(layout)

        # CSV Backup on Close section

        self._setup_csv_backup_section(layout)

        # Active Record Books (Tabella) section
        self._setup_record_books_section(layout)

        layout.addStretch()
        self.setWidget(content)

    def _connect_auto_save(self):
        """Connect all settings fields to auto-save on change."""
        # Text fields - save when editing finished (user leaves field)
        self.default_recorder.editingFinished.connect(self.save_settings)
        self.default_determiner.editingFinished.connect(self.save_settings)
        self.user_initials.editingFinished.connect(self.save_settings)
        
        # Dropdowns - save immediately on selection change
        self.date_format.currentIndexChanged.connect(self.save_settings)
        
        # Checkboxes - save immediately on change
        self.auto_vc.stateChanged.connect(self.save_settings)
        self.exclude_incomplete.stateChanged.connect(self.save_settings)
        
        # Note: Common name checkboxes connected in _setup_common_names_section
        # Note: Theme combo connected in _setup_theme_section
        self.scheme_families_input.editingFinished.connect(self.save_settings)

    def _setup_theme_section(self, layout):
        """Set up theme selection section."""
        t = theme()

        theme_group = QGroupBox("Appearance")
        theme_layout = QHBoxLayout(theme_group)
        theme_layout.setSpacing(16)

        theme_label = QLabel("Theme:")
        theme_layout.addWidget(theme_label)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(t.available_themes)
        self.theme_combo.setMinimumHeight(28)
        self.theme_combo.setMinimumWidth(150)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        theme_layout.addWidget(self.theme_combo)

        theme_note = QLabel("Changes take effect immediately")
        theme_note.setStyleSheet(f"color: {t.get('text_muted')}; font-size: {t.font_size('sm')};")
        theme_layout.addWidget(theme_note)

        theme_layout.addStretch()
        layout.addWidget(theme_group)

    def _on_theme_changed(self, theme_name: str):
        """Handle theme selection change."""
        if self._loading:
            return
        t = theme()
        if t.set_theme(theme_name):
            # Theme changed, emit settings_changed to trigger UI refresh
            self.settings_changed.emit()


    def _setup_defaults_section(self, layout):
        """Set up default values section."""
        defaults_group = QGroupBox("Default Values")
        defaults_layout = QGridLayout(defaults_group)
        defaults_layout.setColumnStretch(1, 1)
        defaults_layout.setHorizontalSpacing(16)
        defaults_layout.setVerticalSpacing(12)

        defaults_layout.addWidget(QLabel("Default Recorder:"), 0, 0)
        self.default_recorder = QLineEdit()
        self.default_recorder.setMinimumHeight(28)
        defaults_layout.addWidget(self.default_recorder, 0, 1)

        defaults_layout.addWidget(QLabel("Default Determiner:"), 1, 0)
        self.default_determiner = QLineEdit()
        self.default_determiner.setMinimumHeight(28)
        defaults_layout.addWidget(self.default_determiner, 1, 1)

        defaults_layout.addWidget(QLabel("User Initials:"), 2, 0)
        self.user_initials = QLineEdit()
        self.user_initials.setPlaceholderText("e.g., WJH")
        self.user_initials.setMaxLength(5)
        self.user_initials.setMinimumHeight(28)
        self.user_initials.setMaximumWidth(80)
        defaults_layout.addWidget(self.user_initials, 2, 1)

        layout.addWidget(defaults_group)

    def _setup_common_names_section(self, layout):
        """Set up common names display section."""
        t = theme()

        common_names_group = QGroupBox("Common Name Display")
        cn_layout = QVBoxLayout(common_names_group)
        cn_layout.setSpacing(8)

        cn_desc = QLabel("Choose which tabs display common names alongside scientific names.")
        cn_desc.setStyleSheet(f"color: {t.get('text_secondary')}; margin-bottom: 4px;")
        cn_desc.setWordWrap(True)
        cn_layout.addWidget(cn_desc)

        self.cn_home = QCheckBox("Home (Recent Activity & Species Info)")
        self.cn_home.setChecked(True)
        cn_layout.addWidget(self.cn_home)

        self.cn_observations = QCheckBox("Observation Data")
        self.cn_observations.setChecked(True)
        cn_layout.addWidget(self.cn_observations)

        self.cn_recording_scheme = QCheckBox("Recording Scheme")
        self.cn_recording_scheme.setChecked(True)
        cn_layout.addWidget(self.cn_recording_scheme)

        self.cn_insect_collection = QCheckBox("Insect Collection")
        self.cn_insect_collection.setChecked(True)
        cn_layout.addWidget(self.cn_insect_collection)

        # Connect changes to save immediately and emit settings_changed
        self.cn_home.stateChanged.connect(self._on_common_name_changed)
        self.cn_observations.stateChanged.connect(self._on_common_name_changed)
        self.cn_recording_scheme.stateChanged.connect(self._on_common_name_changed)
        self.cn_insect_collection.stateChanged.connect(self._on_common_name_changed)

        layout.addWidget(common_names_group)

    def _on_common_name_changed(self):
        """Handle common name checkbox changes - save immediately."""
        if self._loading:
            return  # Don't save during initial load
        
        settings = QSettings()
        settings.setValue(Settings.COMMON_NAMES_HOME, self.cn_home.isChecked())
        settings.setValue(Settings.COMMON_NAMES_OBSERVATIONS, self.cn_observations.isChecked())
        settings.setValue(Settings.COMMON_NAMES_RECORDING_SCHEME, self.cn_recording_scheme.isChecked())
        settings.setValue(Settings.COMMON_NAMES_INSECT_COLLECTION, self.cn_insect_collection.isChecked())
        settings.sync()  # Force immediate write
        self.settings_changed.emit()

    def _setup_display_section(self, layout):
        """Set up display preferences section."""
        t = theme()
        
        display_group = QGroupBox("Display Preferences")
        display_layout = QGridLayout(display_group)
        display_layout.setColumnStretch(1, 1)
        display_layout.setHorizontalSpacing(16)
        display_layout.setVerticalSpacing(12)

        display_layout.addWidget(QLabel("Date Format:"), 0, 0)
        self.date_format = QComboBox()
        self.date_format.addItems(list(DATE_FORMAT_OPTIONS.keys()))
        self.date_format.setMinimumHeight(28)
        display_layout.addWidget(self.date_format, 0, 1)
        
        # Add note about where date format applies
        date_note = QLabel("Used for date entry fields and display")
        date_note.setStyleSheet(f"color: {t.get('text_muted')}; font-size: {t.font_size('sm')};")
        display_layout.addWidget(date_note, 1, 1)

        layout.addWidget(display_group)

    def _setup_auto_section(self, layout):
        """Set up automatic calculations section."""
        t = theme()
        
        auto_group = QGroupBox("Automatic Calculations")
        auto_layout = QVBoxLayout(auto_group)

        self.auto_vc = QCheckBox("Automatically calculate Vice County from Grid Reference")
        auto_layout.addWidget(self.auto_vc)
        
        # Species filtering section
        auto_layout.addSpacing(12)
        filter_label = QLabel("Species Statistics Filtering")
        filter_label.setStyleSheet(f"font-weight: bold; margin-top: 8px;")
        auto_layout.addWidget(filter_label)
        
        filter_desc = QLabel("Exclude incomplete identifications from species counts and lists.")
        filter_desc.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px;")
        filter_desc.setWordWrap(True)
        auto_layout.addWidget(filter_desc)
        
        self.exclude_incomplete = QCheckBox("Exclude genus-only and aggregate species (e.g. 'Bombus', 'Andrena agg.')")
        self.exclude_incomplete.setChecked(True)
        auto_layout.addWidget(self.exclude_incomplete)

        layout.addWidget(auto_group)

    def _setup_scheme_section(self, layout):
        """Recording Scheme family scope setting."""
        t = theme()
        group = QGroupBox("Recording Scheme")
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                color: {t.get('text_heading')};
                border: 1px solid {t.get('border')};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 20px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }}
        """)
        grid = QGridLayout(group)
        grid.setSpacing(8)

        label = QLabel("Target Families:")
        label.setToolTip("Comma-separated family names that this recording scheme covers.\n"
                         "Leave blank for no restriction.\n"
                         "Example: Cerambycidae")
        label.setStyleSheet(f"color: {t.get('text_primary')};")
        grid.addWidget(label, 0, 0)

        self.scheme_families_input = QLineEdit()
        self.scheme_families_input.setPlaceholderText("e.g. Cerambycidae (leave blank for all)")

        # Load family names from UKSI for autocomplete
        try:
            import sqlite3
            from ...core.config import Paths
            uksi_path = Paths.default_uksi_db()
            conn = connect_ro(str(uksi_path))
            all_families = [r[0] for r in conn.execute(
                "SELECT DISTINCT family FROM taxa WHERE family IS NOT NULL AND family != '' ORDER BY family"
            ).fetchall()]
            conn.close()
            completer = QCompleter(all_families, self)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setMaxVisibleItems(12)
            self.scheme_families_input.setCompleter(completer)
        except Exception as e:
            print(f"[Settings] Could not load UKSI families for autocomplete: {e}")

        # Load family names from UKSI for autocomplete
        try:
            import sqlite3
            from ...core.config import Paths
            uksi_path = Paths.default_uksi_db()
            conn = connect_ro(str(uksi_path))
            all_families = [r[0] for r in conn.execute(
                "SELECT DISTINCT family FROM taxa WHERE family IS NOT NULL AND family != '' ORDER BY family"
            ).fetchall()]
            conn.close()
            completer = QCompleter(all_families, self)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setMaxVisibleItems(12)
            self.scheme_families_input.setCompleter(completer)
        except Exception as e:
            print(f"[Settings] Could not load UKSI families for autocomplete: {e}")
        self.scheme_families_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 6px 8px;
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
            }}
        """)
        grid.addWidget(self.scheme_families_input, 0, 1)

        hint = QLabel("Controls which families are shown in the Recording Scheme tab and filter wizard.")
        hint.setStyleSheet(f"color: {t.get('text_muted')}; font-size: 11px; font-style: italic;")
        grid.addWidget(hint, 1, 0, 1, 2)

        layout.addWidget(group)

    def _setup_filter_defaults_section(self, layout):
        """Set up filter bar defaults section."""
        t = theme()
        
        filter_group = QGroupBox("Filter Bar Defaults")
        filter_layout = QVBoxLayout(filter_group)
        filter_layout.setSpacing(8)

        filter_desc = QLabel("Choose whether filter bars are shown by default when opening each tab.")
        filter_desc.setStyleSheet(f"color: {t.get('text_secondary')}; margin-bottom: 4px;")
        filter_desc.setWordWrap(True)
        filter_layout.addWidget(filter_desc)

        self.filters_observations = QCheckBox("Observation Data - Show filters on open")
        self.filters_observations.setChecked(True)
        filter_layout.addWidget(self.filters_observations)

        self.filters_recording_scheme = QCheckBox("Recording Scheme - Show filters on open")
        self.filters_recording_scheme.setChecked(True)
        filter_layout.addWidget(self.filters_recording_scheme)

        self.filters_collection = QCheckBox("Insect Collection - Show filters on open")
        self.filters_collection.setChecked(True)
        filter_layout.addWidget(self.filters_collection)

        # Connect to auto-save
        self.filters_observations.stateChanged.connect(self.save_settings)
        self.filters_recording_scheme.stateChanged.connect(self.save_settings)
        self.filters_collection.stateChanged.connect(self.save_settings)

        layout.addWidget(filter_group)

    def _setup_csv_backup_section(self, layout):
        """Set up CSV backup on close section."""
        t = theme()

        backup_group = QGroupBox("CSV Safety Backup")
        backup_layout = QVBoxLayout(backup_group)
        backup_layout.setSpacing(8)

        backup_desc = QLabel("Automatically export all data tables to CSV files when closing the application, if changes were made during the session.")
        backup_desc.setStyleSheet(f"color: {t.get('text_secondary')}; margin-bottom: 4px;")
        backup_desc.setWordWrap(True)
        backup_layout.addWidget(backup_desc)

        self.csv_backup_enabled = QCheckBox("Export CSV backups on close (when data has changed)")
        backup_layout.addWidget(self.csv_backup_enabled)

        # Path selector
        path_layout = QHBoxLayout()
        path_label = QLabel("Backup folder:")
        path_label.setMinimumWidth(90)
        path_layout.addWidget(path_label)

        self.csv_backup_path = QLineEdit()
        self.csv_backup_path.setReadOnly(True)
        self.csv_backup_path.setPlaceholderText("Select a folder...")
        path_layout.addWidget(self.csv_backup_path, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_csv_backup_path)
        path_layout.addWidget(browse_btn)

        backup_layout.addLayout(path_layout)

        # Connect to auto-save
        self.csv_backup_enabled.stateChanged.connect(self.save_settings)

        layout.addWidget(backup_group)

    def _browse_csv_backup_path(self):
        """Open folder picker for CSV backup location."""
        from PySide6.QtWidgets import QFileDialog
        current = self.csv_backup_path.text()
        folder = QFileDialog.getExistingDirectory(self, "Select CSV Backup Folder", current)
        if folder:
            self.csv_backup_path.setText(folder)
            self.save_settings()

    def _setup_record_books_section(self, layout):
        """Set up Active Record Books folder section (Tabella integration)."""
        t = theme()

        rb_group = QGroupBox("Active Record Books (Tabella)")
        rb_layout = QVBoxLayout(rb_group)
        rb_layout.setSpacing(8)

        rb_desc = QLabel("Folder of in-use Tabella .xlsm workbooks. The pending-records refresh scans this folder for entries not yet imported into Observatum.")
        rb_desc.setStyleSheet(f"color: {t.get('text_secondary')}; margin-bottom: 4px;")
        rb_desc.setWordWrap(True)
        rb_layout.addWidget(rb_desc)

        path_layout = QHBoxLayout()
        path_label = QLabel("Folder:")
        path_label.setMinimumWidth(90)
        path_layout.addWidget(path_label)

        self.record_books_path = QLineEdit()
        self.record_books_path.setReadOnly(True)
        self.record_books_path.setPlaceholderText("Select a folder...")
        path_layout.addWidget(self.record_books_path, 1)

        rb_browse_btn = QPushButton("Browse...")
        rb_browse_btn.clicked.connect(self._browse_record_books_path)
        path_layout.addWidget(rb_browse_btn)

        rb_layout.addLayout(path_layout)
        layout.addWidget(rb_group)

    def _browse_record_books_path(self):
        """Open folder picker for the Active Record Books location."""
        from PySide6.QtWidgets import QFileDialog
        current = self.record_books_path.text()
        folder = QFileDialog.getExistingDirectory(self, "Select Active Record Books Folder", current)
        if folder:
            self.record_books_path.setText(folder)
            self.save_settings()

    def _load_settings(self):
        """Load settings from QSettings (internal)."""
        self._loading = True  # Block saves during load
        
        try:
            settings = QSettings()

            # Theme
            saved_theme = settings.value(Settings.THEME, Defaults.THEME)
            idx = self.theme_combo.findText(saved_theme)
            if idx >= 0:
                self.theme_combo.setCurrentIndex(idx)

            # Default values
            self.default_recorder.setText(settings.value(Settings.DEFAULT_RECORDER, Defaults.RECORDER))
            self.default_determiner.setText(settings.value(Settings.DEFAULT_DETERMINER, Defaults.DETERMINER))
            self.user_initials.setText(settings.value(Settings.USER_INITIALS, Defaults.USER_INITIALS))

            # Common names display settings
            self.cn_home.setChecked(settings.value(Settings.COMMON_NAMES_HOME, Defaults.SHOW_COMMON_NAMES, type=bool))
            self.cn_observations.setChecked(settings.value(Settings.COMMON_NAMES_OBSERVATIONS, Defaults.SHOW_COMMON_NAMES, type=bool))
            self.cn_recording_scheme.setChecked(settings.value(Settings.COMMON_NAMES_RECORDING_SCHEME, Defaults.SHOW_COMMON_NAMES, type=bool))
            self.cn_insect_collection.setChecked(settings.value(Settings.COMMON_NAMES_INSECT_COLLECTION, Defaults.SHOW_COMMON_NAMES, type=bool))

            # Date format
            date_fmt = settings.value(Settings.DATE_FORMAT, Defaults.DATE_FORMAT)
            idx = self.date_format.findText(date_fmt)
            if idx >= 0:
                self.date_format.setCurrentIndex(idx)

            # Auto VC calculation
            self.auto_vc.setChecked(settings.value(Settings.AUTO_CALCULATE_VC, Defaults.AUTO_CALCULATE_VC, type=bool))
            
            # Exclude incomplete species
            self.exclude_incomplete.setChecked(settings.value(Settings.EXCLUDE_INCOMPLETE_SPECIES, Defaults.EXCLUDE_INCOMPLETE_SPECIES, type=bool))
            
            # Filter bar defaults
            self.filters_observations.setChecked(settings.value(Settings.FILTERS_VISIBLE_OBSERVATIONS, Defaults.FILTERS_VISIBLE_OBSERVATIONS, type=bool))
            self.filters_recording_scheme.setChecked(settings.value(Settings.FILTERS_VISIBLE_RECORDING_SCHEME, Defaults.FILTERS_VISIBLE_RECORDING_SCHEME, type=bool))
            self.filters_collection.setChecked(settings.value(Settings.FILTERS_VISIBLE_COLLECTION, Defaults.FILTERS_VISIBLE_COLLECTION, type=bool))

            # CSV backup settings
            self.csv_backup_enabled.setChecked(settings.value(Settings.CSV_BACKUP_ON_CLOSE, False, type=bool))
            import os
            default_path = os.path.join(os.path.dirname(os.path.abspath(".")), "data", "csv_backups")
            self.csv_backup_path.setText(settings.value(Settings.CSV_BACKUP_PATH, default_path))

            # Active Record Books folder (Tabella)
            import os as _os
            default_rb = _os.path.join(_os.path.expanduser("~"), "OneDrive", "Active Record Books")
            self.record_books_path.setText(settings.value(Settings.ACTIVE_RECORD_BOOKS_PATH, default_rb))
            
        finally:
            # Recording Scheme families
            self.scheme_families_input.setText(
                settings.value(Settings.SCHEME_FAMILIES, "", str)
            )

            self._loading = False  # Re-enable saves

    def load_settings(self):
        """Load settings from QSettings (public API)."""
        self._load_settings()

    def save_settings(self):
        """Save settings to QSettings."""
        if self._loading:
            return  # Don't save during load
            
        settings = QSettings()

        # Save all settings
        settings.setValue(Settings.DEFAULT_RECORDER, self.default_recorder.text())
        settings.setValue(Settings.DEFAULT_DETERMINER, self.default_determiner.text())
        settings.setValue(Settings.USER_INITIALS, self.user_initials.text().upper())
        settings.setValue(Settings.DATE_FORMAT, self.date_format.currentText())
        settings.setValue(Settings.AUTO_CALCULATE_VC, self.auto_vc.isChecked())
        settings.setValue(Settings.EXCLUDE_INCOMPLETE_SPECIES, self.exclude_incomplete.isChecked())

        # Common names display settings
        settings.setValue(Settings.COMMON_NAMES_HOME, self.cn_home.isChecked())
        settings.setValue(Settings.COMMON_NAMES_OBSERVATIONS, self.cn_observations.isChecked())
        settings.setValue(Settings.COMMON_NAMES_RECORDING_SCHEME, self.cn_recording_scheme.isChecked())
        settings.setValue(Settings.COMMON_NAMES_INSECT_COLLECTION, self.cn_insect_collection.isChecked())

        # Filter bar defaults
        settings.setValue(Settings.FILTERS_VISIBLE_OBSERVATIONS, self.filters_observations.isChecked())
        settings.setValue(Settings.FILTERS_VISIBLE_RECORDING_SCHEME, self.filters_recording_scheme.isChecked())
        settings.setValue(Settings.FILTERS_VISIBLE_COLLECTION, self.filters_collection.isChecked())

        # CSV backup settings
        settings.setValue(Settings.CSV_BACKUP_ON_CLOSE, self.csv_backup_enabled.isChecked())
        settings.setValue(Settings.CSV_BACKUP_PATH, self.csv_backup_path.text())
        settings.setValue(Settings.ACTIVE_RECORD_BOOKS_PATH, self.record_books_path.text())

        # Recording Scheme families
        settings.setValue(Settings.SCHEME_FAMILIES,
                          self.scheme_families_input.text().strip())

        settings.sync()  # Force immediate write
        self.settings_changed.emit()

    def apply_theme(self):
        """Apply the current theme to all components."""
        t = theme()
        self.setStyleSheet(f"background-color: {t.get('background')};")

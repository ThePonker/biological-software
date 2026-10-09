"""
Observation Import Wizard for Observatum V2.

A multi-step wizard for importing observation data from:
- iRecord CSV downloads (sync existing records)
- Personal CSV templates (new records)

Features:
- Mode selection (iRecord Sync vs Personal Upload)
- Auto-detection of iRecord format
- Column mapping with auto-match
- Live validation with progress counters
- Inline editing for Personal uploads
- Duplicate detection and handling
- "Never upload to iRecord" batch flag
- Confirmation dialog with import preview
- Auto-refresh of Observation tab after import

MODULAR STRUCTURE:
- validation_worker.py: ObservationValidationWorker, ObservationImportRow, RowStatus, ImportMode
- wizard_pages_mixin.py: Page creation methods
- wizard_file_mixin.py: File handling, iRecord detection
- wizard_validation_mixin.py: Validation callbacks, live counters
- wizard_import_mixin.py: Import execution, duplicate handling

Usage:
    from src.views.dialogs.observation_import_wizard import ObservationImportWizard
    
    wizard = ObservationImportWizard(parent, uksi_model, vc_service, db, observation_model)
    wizard.import_completed.connect(on_import_done)
    if wizard.exec() == QDialog.Accepted:
        print(f"Imported {wizard.imported_count} records")
"""

from typing import Optional, Dict, List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal

from .validation_worker import (
    ObservationImportRow, ObservationValidationWorker, RowStatus, ImportMode,
    _find_vc_database
)
from .wizard_pages_mixin import WizardPagesMixin
from .wizard_file_mixin import WizardFileMixin
from .wizard_validation_mixin import WizardValidationMixin
from .wizard_import_mixin import WizardImportMixin
from .wizard_species_mixin import WizardSpeciesResolutionMixin

from src.themes import theme
from src.core.config import TabColors
from shared.species_lookup import is_unresolved_error


class ObservationImportWizard(
    QDialog,
    WizardPagesMixin,
    WizardFileMixin,
    WizardValidationMixin,
    WizardSpeciesResolutionMixin,
    WizardImportMixin
):
    """
    Multi-step wizard for importing observation data.
    
    Steps:
    1. Mode Selection - Choose iRecord Sync or Personal Upload
    2. File Selection - Choose CSV file
    3. Column Mapping - Map file columns to database fields
    4. Validation - Preview and validate data
    5. Confirmation - Review import summary and options
    6. Import - Execute import with progress
    7. Summary - Show results
    """
    
    import_completed = Signal(int)  # Emits count of imported/updated records
    
    def __init__(
        self,
        parent=None,
        uksi_model=None,
        vc_service=None,
        db=None,
        observation_model=None
    ):
        super().__init__(parent)
        self.uksi_model = uksi_model
        self.db = db
        self.observation_model = observation_model
        self.vc_db_path = None
        
        # Tab colors for Observation (Sage Green)
        self._accent = TabColors.OBSERVATION
        self._accent_light = TabColors.OBSERVATION_LIGHT
        self._accent_dark = TabColors.OBSERVATION_DARK
        
        # Initialize VC service
        self._init_vc_service(vc_service)
        
        self.setWindowTitle("Import Observations")
        self.setMinimumSize(1100, 800)
        self.resize(1200, 850)
        self.setModal(True)
        
        # Data state
        self.file_path: Optional[str] = None
        self.raw_rows: List[Dict[str, str]] = []
        self.columns: List[str] = []
        self.column_mapping: Dict[str, str] = {}
        self.validated_rows: List[ObservationImportRow] = []
        self.is_irecord_format: bool = False
        
        # Import counts
        self.imported_count: int = 0
        self.updated_count: int = 0
        self.skipped_count: int = 0
        self.error_count: int = 0
        
        # Track edited rows for revalidation
        self._edited_row_indices: set = set()
        
        # Validation worker reference
        self.validation_worker: Optional[ObservationValidationWorker] = None
        
        self._setup_ui()
    
    def _init_vc_service(self, vc_service):
        """Initialize the VC lookup service."""
        if vc_service is None:
            self.vc_db_path = _find_vc_database()
            
            if self.vc_db_path:
                try:
                    from src.services.vc_lookup_service import VCLookupService
                    self.vc_service = VCLookupService(self.vc_db_path)
                except ImportError:
                    try:
                        from services.vc_lookup_service import VCLookupService
                        self.vc_service = VCLookupService(self.vc_db_path)
                    except ImportError:
                        self.vc_service = None
            else:
                self.vc_service = None
        else:
            self.vc_service = vc_service
            if hasattr(vc_service, '_db_path') and vc_service._db_path:
                self.vc_db_path = vc_service._db_path
    
    def _setup_ui(self):
        """Set up the wizard UI."""
        t = theme()

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header bar (Sage Green - matches Observation Data tab)
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {self._accent};
                border: none;
            }}
        """)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(24, 20, 24, 20)

        self.header_label = QLabel("Import Observations")
        self.header_label.setStyleSheet("""
            color: white;
            font-size: 18px;
            font-weight: 600;
        """)
        header_layout.addWidget(self.header_label)

        self.step_label = QLabel("Step 1 of 7: Select Import Mode")
        self.step_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.8);
            font-size: 13px;
        """)
        header_layout.addWidget(self.step_label)

        layout.addWidget(header)

        # Stacked widget for steps
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {t.get('surface')};")
        layout.addWidget(self.stack, 1)

        # Create all step pages
        self._create_mode_selection_page()   # Step 1
        self._create_file_selection_page()   # Step 2
        self._create_column_mapping_page()   # Step 3
        self._create_validation_page()       # Step 4
        self._create_confirmation_page()     # Step 5
        self._create_import_page()           # Step 6
        self._create_summary_page()          # Step 7

        # Footer with navigation buttons
        footer = QFrame()
        footer.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border-top: 1px solid {t.get('border')};
            }}
        """)
        nav_layout = QHBoxLayout(footer)
        nav_layout.setContentsMargins(24, 16, 24, 16)
        nav_layout.setSpacing(12)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_secondary')};
                border: 1px solid {t.get('border')};
                padding: 10px 24px;
                border-radius: {t.get('radius_md')};
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
                border-color: {t.get('border_strong')};
            }}
        """)
        self.cancel_btn.clicked.connect(self.reject)
        nav_layout.addWidget(self.cancel_btn)

        nav_layout.addStretch()

        self.back_btn = QPushButton("← Back")
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_primary')};
                border: 1px solid {t.get('border')};
                padding: 10px 24px;
                border-radius: {t.get('radius_md')};
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
            }}
        """)
        self.back_btn.clicked.connect(self._go_back)
        self.back_btn.setVisible(False)
        nav_layout.addWidget(self.back_btn)

        # Resolve Species button (hidden until errors found)
        self.resolve_species_btn = QPushButton("Resolve Species...")
        self.resolve_species_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.resolve_species_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {self._accent};
                border: 1px solid {self._accent};
                border-radius: {t.get('radius_md')};
                padding: 8px 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {self._accent};
                color: white;
            }}
        """)
        self.resolve_species_btn.clicked.connect(self._open_resolve_species_dialog)
        self.resolve_species_btn.setVisible(False)
        nav_layout.addWidget(self.resolve_species_btn)

        self.next_btn = QPushButton("Next →")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._accent};
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: {t.get('radius_md')};
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {self._accent_dark};
            }}
            QPushButton:disabled {{
                background-color: {t.get('text_muted')};
            }}
        """)
        self.next_btn.clicked.connect(self._go_next)
        nav_layout.addWidget(self.next_btn)

        layout.addWidget(footer)

    def _open_resolve_species_dialog(self):
        """Reopen the bulk species resolution dialog."""
        unmatched = []
        for row in self.validated_rows:
            if row.status == RowStatus.ERROR and is_unresolved_error(row.error_message):
                if row.species_name not in unmatched:
                    unmatched.append(row.species_name)
        if unmatched:
            self._prompt_resolve_unmatched()
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "No Errors", "No unmatched species to resolve.")

    def _browse_existing_values(self, column: str, target_field):
        """Show popup with existing values for a database column."""
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
            QListWidgetItem, QPushButton, QLabel, QMessageBox
        )
        from PySide6.QtCore import Qt
        from ....themes import theme
        from ....models.database import get_database

        t = theme()
        db = get_database()
        if not db:
            return

        results = db.execute_main(
            f"SELECT DISTINCT {column} FROM observations "
            f"WHERE {column} IS NOT NULL AND {column} != '' "
            f"ORDER BY {column}"
        )
        values = [r[column] for r in results if r[column]] if results else []

        if not values:
            QMessageBox.information(self, "No Data", f"No existing {column.replace('_', ' ')} values found.")
            return

        dlg = QDialog(self)
        label = column.replace("_", " ").title()
        dlg.setWindowTitle(f"Select {label}")
        dlg.setMinimumSize(350, 400)
        dlg.setStyleSheet(f"QDialog {{ background-color: {t.get('surface')}; }}")

        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel(f"{len(values)} existing {label.lower()}(s)")
        header.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
        layout.addWidget(header)

        list_widget = QListWidget()
        list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                font-size: 13px;
            }}
            QListWidget::item {{
                padding: 10px 12px;
                color: {t.get('text_primary')};
            }}
            QListWidget::item:selected {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_primary')};
                border-left: 3px solid {t.get('primary')};
            }}
            QListWidget::item:hover {{
                background-color: {t.get('surface_alt')};
            }}
        """)
        for val in values:
            list_widget.addItem(QListWidgetItem(str(val)))
        layout.addWidget(list_widget)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setMinimumWidth(90)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{ background-color: {t.get('hover')}; }}
        """)
        cancel_btn.clicked.connect(dlg.reject)
        btn_layout.addWidget(cancel_btn)

        select_btn = QPushButton("Select")
        select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_btn.setMinimumWidth(90)
        select_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_primary')};
                border-left: 3px solid {t.get('primary')};
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {t.get('primary_dark')}; }}
        """)

        def on_select():
            item = list_widget.currentItem()
            if item:
                target_field.setText(item.text())
                dlg.accept()

        select_btn.clicked.connect(on_select)
        list_widget.itemDoubleClicked.connect(lambda item: (target_field.setText(item.text()), dlg.accept()))
        btn_layout.addWidget(select_btn)

        layout.addLayout(btn_layout)
        dlg.exec()

    def _get_selected_mode(self) -> ImportMode:
        """Get the selected import mode from cards."""
        mode_id = self._get_selected_mode_from_cards()
        if mode_id == "irecord_sync":
            return ImportMode.IRECORD_SYNC
        elif mode_id == "commercial_upload":
            return ImportMode.COMMERCIAL_UPLOAD
        else:
            return ImportMode.PERSONAL_UPLOAD
    
    def _go_back(self):
        """Go to previous step."""
        current = self.stack.currentIndex()
        if current > 0:
            self.stack.setCurrentIndex(current - 1)
            self._update_step_ui()
    
    def _go_next(self):
        """Go to next step."""
        current = self.stack.currentIndex()
        
        if current == 0:  # Mode selection -> File selection
            # Warn if Commercial mode with missing project/client
            if self._get_selected_mode() == ImportMode.COMMERCIAL_UPLOAD:
                missing = []
                if hasattr(self, 'commercial_project') and not self.commercial_project.text().strip():
                    missing.append('Project Name')
                if hasattr(self, 'commercial_client') and not self.commercial_client.text().strip():
                    missing.append('Client')
                if missing:
                    result = QMessageBox.warning(
                        self,
                        'Missing Information',
                        f'The following fields are empty: {", ".join(missing)}.\n\nContinue anyway?',
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if result != QMessageBox.StandardButton.Yes:
                        return
            self.stack.setCurrentIndex(1)
        
        elif current == 1:  # File selection -> Column mapping
            if not self.file_path:
                QMessageBox.warning(self, "No File", "Please select a file to import.")
                return
            self._setup_column_mapping()
            self.stack.setCurrentIndex(2)
        
        elif current == 2:  # Column mapping -> Validation
            if self._start_validation():
                self.stack.setCurrentIndex(3)
            else:
                return
        
        elif current == 3:  # Validation -> Confirmation
            if not self.validated_rows:
                QMessageBox.warning(self, "No Data", "No rows have been validated.")
                return
            self._update_confirmation_counts()
            self.stack.setCurrentIndex(4)
        
        elif current == 4:  # Confirmation -> Import
            # Capture checkbox state before page change (widget becomes invisible)
            self._include_errors_at_import = self.include_errors_checkbox.isChecked() if hasattr(self, "include_errors_checkbox") else False
            self.stack.setCurrentIndex(5)
            # Auto-start import
            self._do_import()
        
        elif current == 5:  # Import -> Summary
            self._update_summary()
            self.stack.setCurrentIndex(6)
        
        elif current == 6:  # Summary -> Close
            self.accept()
            return
        
        self._update_step_ui()
    
    def _update_step_ui(self):
        """Update UI based on current step."""
        t = theme()
        current = self.stack.currentIndex()
        
        steps = [
            "Step 1 of 7: Select Import Mode",
            "Step 2 of 7: Select File",
            "Step 3 of 7: Map Columns",
            "Step 4 of 7: Validate Data",
            "Step 5 of 7: Confirm Import",
            "Step 6 of 7: Importing...",
            "Step 7 of 7: Summary",
        ]
        
        self.step_label.setText(steps[current])
        
        # Back button
        self.back_btn.setVisible(current > 0 and current < 5)
        
        # Get current import mode for mode-specific UI
        import_mode = self._get_selected_mode()
        
        # Configure confirmation page options based on mode
        if current == 4:  # Confirmation page
            # Hide "Never upload to iRecord" for iRecord Sync (data already in iRecord)
            self.never_upload_checkbox.setVisible(import_mode in (ImportMode.PERSONAL_UPLOAD, ImportMode.COMMERCIAL_UPLOAD))
            # Skip duplicates: both upload modes (IMP-8 -- Commercial always re-inserted them)
            self.skip_duplicates_checkbox.setVisible(import_mode in (ImportMode.PERSONAL_UPLOAD,
                                                                     ImportMode.COMMERCIAL_UPLOAD))
            # include_errors visibility handled by _update_confirmation_counts
            # Hide options frame entirely if no options visible
            has_visible_options = import_mode in (ImportMode.PERSONAL_UPLOAD, ImportMode.COMMERCIAL_UPLOAD)
            self.options_frame.setVisible(has_visible_options)
        
        # Next button text and state
        if current == 4:
            valid_count = sum(1 for r in self.validated_rows if r.status != RowStatus.ERROR
                              and not self._skips_duplicate(r, import_mode))
            skip_count = len(self.validated_rows) - valid_count
            if skip_count > 0:
                self.next_btn.setText(f"Import {valid_count} Records ({skip_count} skipped)")
            else:
                self.next_btn.setText(f"Import {valid_count} Records")
        elif current == 5:
            self.next_btn.setText("View Summary")
            self.next_btn.setEnabled(False)  # Disabled during import
            # Change Cancel to Close once import starts
            self.cancel_btn.setText("Close")
            self.cancel_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.get('surface')};
                    color: {t.get('text_primary')};
                    border: 1px solid {t.get('border_strong')};
                    padding: 10px 16px;
                    border-radius: {t.get('radius_md')};
                    font-weight: 500;
                }}
                QPushButton:hover {{ background-color: {t.get('hover')}; }}
            """)
        elif current == 6:
            self.next_btn.setText("Close")
            self.cancel_btn.hide()
            self.back_btn.hide()
        else:
            self.next_btn.setText("Next →")
        
        # Enable next button based on current page state
        if current == 0:
            self.next_btn.setEnabled(True)
        elif current == 1:
            self.next_btn.setEnabled(self.file_path is not None)
        elif current == 2:
            self.next_btn.setEnabled(True)
        elif current == 3:
            # Enabled when validation completes
            pass
        elif current == 4:
            self.next_btn.setEnabled(True)
        elif current == 6:
            self.next_btn.setEnabled(True)
    
    def closeEvent(self, event):
        """Handle window close - cancel validation if running."""
        if self.validation_worker and self.validation_worker.isRunning():
            self.validation_worker.cancel()
            self.validation_worker.wait()
        event.accept()

"""
Recording Scheme Import Wizard for Observatum V2.

A multi-step wizard for importing recording scheme data from:
- iRecord CSV downloads
- NBN Atlas CSV downloads
- Generic CSV files

Features:
- Mode selection (iRecord / NBN Atlas / Generic CSV)
- Auto-detection of file format
- Column mapping with auto-match
- Live validation with progress counters
- Inline editing for generic mode
- Duplicate detection and handling
- Auto-refresh of Recording Scheme tab after import

MODULAR STRUCTURE:
- validation_worker.py: SchemeValidationWorker, SchemeImportRow, RowStatus, SchemeImportMode
- wizard_pages_mixin.py: Page creation methods
- wizard_file_mixin.py: File handling, format detection
- wizard_validation_mixin.py: Validation callbacks, live counters
- wizard_import_mixin.py: Import execution, duplicate handling

Usage:
    from src.views.dialogs.scheme_import_wizard import SchemeImportWizard

    wizard = SchemeImportWizard(parent, uksi_model, vc_service, db)
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
    SchemeImportRow, SchemeValidationWorker, RowStatus, SchemeImportMode,
    _find_vc_database
)
from .wizard_pages_mixin import WizardPagesMixin
from .wizard_file_mixin import WizardFileMixin
from .wizard_validation_mixin import WizardValidationMixin
from .wizard_import_mixin import WizardImportMixin

from src.themes import theme
from src.core.config import TabColors, ButtonColors


class SchemeImportWizard(
    QDialog,
    WizardPagesMixin,
    WizardFileMixin,
    WizardValidationMixin,
    WizardImportMixin
):
    """
    Multi-step wizard for importing recording scheme data.

    Steps:
    1. Mode Selection - Choose iRecord / NBN Atlas / Generic CSV
    2. File Selection - Choose CSV file
    3. Column Mapping - Map file columns to database fields
    4. Validation - Preview and validate data
    5. Confirmation - Review import summary and options
    6. Import - Execute import with progress
    7. Summary - Show results
    """

    import_completed = Signal(int)  # Emits count of imported records

    def __init__(
        self,
        parent=None,
        uksi_model=None,
        vc_service=None,
        db=None,
    ):
        super().__init__(parent)
        self.uksi_model = uksi_model
        self.db = db
        self.vc_db_path = None

        # Tab colors for Recording Scheme (Dusty Purple)
        self._accent = TabColors.RECORDING_SCHEME
        self._accent_light = TabColors.RECORDING_SCHEME_LIGHT
        self._accent_dark = TabColors.RECORDING_SCHEME_DARK

        # Initialize VC service
        self._init_vc_service(vc_service)

        self.setWindowTitle("Import Recording Scheme Data")
        self.setMinimumSize(1100, 800)
        self.resize(1200, 850)
        self.setModal(True)

        # Data state
        self.file_path: Optional[str] = None
        self._file_encoding: str = 'utf-8'
        self.raw_rows: List[Dict[str, str]] = []
        self.columns: List[str] = []
        self.column_mapping: Dict[str, str] = {}
        self.validated_rows: List[SchemeImportRow] = []

        # Import counts
        self.imported_count: int = 0
        self.updated_count: int = 0
        self.skipped_count: int = 0
        self.error_count: int = 0

        # Track edited rows for revalidation
        self._edited_row_indices: set = set()

        # Validation worker reference
        self.validation_worker: Optional[SchemeValidationWorker] = None

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

        # Header
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {self._accent};
                border: none;
            }}
        """)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(24, 20, 24, 20)

        self.title_label = QLabel("Import Recording Scheme Data")
        self.title_label.setStyleSheet("""
            color: white;
            font-size: 18px;
            font-weight: 600;
        """)
        header_layout.addWidget(self.title_label)

        self.step_label = QLabel("Step 1 of 7: Select Import Mode")
        self.step_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.8);
            font-size: 13px;
        """)
        header_layout.addWidget(self.step_label)

        layout.addWidget(header)

        # Content area with stacked widget
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {t.get('surface')};")
        layout.addWidget(self.stack, 1)

        # Create pages
        self._create_mode_selection_page()    # 0
        self._create_file_selection_page()    # 1
        self._create_column_mapping_page()    # 2
        self._create_validation_page()        # 3
        self._create_confirmation_page()      # 4
        self._create_import_page()            # 5
        self._create_summary_page()           # 6

        # Footer with navigation buttons
        footer = QFrame()
        footer.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border-top: 1px solid {t.get('border')};
            }}
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 16, 24, 16)
        footer_layout.setSpacing(12)

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
        footer_layout.addWidget(self.cancel_btn)

        footer_layout.addStretch()

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
        footer_layout.addWidget(self.back_btn)

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
        footer_layout.addWidget(self.next_btn)

        layout.addWidget(footer)

        # Set initial state
        self.stack.setCurrentIndex(0)
        self._update_navigation()

    def _get_selected_mode(self) -> SchemeImportMode:
        """Get the selected import mode from cards."""
        mode_id = self._get_selected_mode_from_cards()
        mode_map = {
            'irecord': SchemeImportMode.IRECORD,
            'nbn_atlas': SchemeImportMode.NBN_ATLAS,
            'generic_csv': SchemeImportMode.GENERIC_CSV,
        }
        return mode_map.get(mode_id, SchemeImportMode.IRECORD)

    def _update_navigation(self):
        """Update navigation buttons based on current step."""
        current = self.stack.currentIndex()
        total = self.stack.count()

        # Step labels
        step_names = [
            "Select Import Mode",
            "Select File",
            "Map Columns",
            "Validate Data",
            "Confirm Import",
            "Importing...",
            "Complete"
        ]

        self.step_label.setText(f"Step {current + 1} of {total}: {step_names[current]}")

        # Back button
        self.back_btn.setVisible(current > 0 and current < 5)

        # Next button
        if current == total - 1:
            self.next_btn.setText("Close")
        elif current == 4:
            self.next_btn.setText("Import")
        else:
            self.next_btn.setText("Next →")

        # Cancel button
        self.cancel_btn.setVisible(current < 5)

    def _go_next(self):
        """Go to next step."""
        current = self.stack.currentIndex()

        # Validate current step
        if not self._validate_step(current):
            return

        # Handle step transitions
        if current == 0:
            # Mode selection -> File selection
            self.stack.setCurrentIndex(1)

        elif current == 1:
            # File selection -> Column mapping
            if not self.file_path:
                QMessageBox.warning(self, "No File", "Please select a CSV file.")
                return
            self._populate_mapping_page()
            self.stack.setCurrentIndex(2)

        elif current == 2:
            # Column mapping -> Validation
            self.column_mapping = self._get_column_mapping()
            self.stack.setCurrentIndex(3)
            self._update_navigation()
            # Use QTimer to defer validation start, allowing UI to update first
            from PySide6.QtCore import QTimer
            QTimer.singleShot(50, self._start_validation)
            return  # Don't call _update_navigation again at the end

        elif current == 3:
            # Validation -> Confirmation
            self._update_confirmation_counts()
            self.stack.setCurrentIndex(4)

        elif current == 4:
            # Confirmation -> Import
            self.stack.setCurrentIndex(5)
            self.next_btn.setEnabled(False)
            self._do_import()

        elif current == 5:
            # Import -> Summary
            self._update_summary()
            self.stack.setCurrentIndex(6)

        elif current == 6:
            # Summary -> Close
            self.accept()

        self._update_navigation()

    def _go_back(self):
        """Go to previous step."""
        current = self.stack.currentIndex()
        if current > 0:
            self.stack.setCurrentIndex(current - 1)
            self._update_navigation()

    def _validate_step(self, step: int) -> bool:
        """Validate the current step before proceeding."""
        if step == 1:
            # File selection
            if not self.file_path:
                QMessageBox.warning(self, "No File", "Please select a CSV file.")
                return False
            if not self.raw_rows:
                QMessageBox.warning(self, "No Data", "The selected file contains no data.")
                return False

        elif step == 2:
            # Column mapping - check required fields
            mapping = self._get_column_mapping()
            missing = []

            if not mapping.get('species_name'):
                missing.append("Species Name")
            if not mapping.get('date'):
                missing.append("Date")
            if not mapping.get('grid_ref'):
                missing.append("Grid Reference")

            if missing:
                QMessageBox.warning(
                    self, "Missing Mappings",
                    f"Please map the following required fields:\n• " + "\n• ".join(missing)
                )
                return False

        elif step == 3:
            # Validation - check if any valid rows
            valid_count = sum(1 for r in self.validated_rows if r.status != RowStatus.ERROR)
            if valid_count == 0:
                QMessageBox.warning(
                    self, "No Valid Data",
                    "All rows have validation errors. Please fix the issues or select a different file."
                )
                return False

        return True

    def closeEvent(self, event):
        """Handle dialog close."""
        if self.validation_worker and self.validation_worker.isRunning():
            self.validation_worker.cancel()
            self.validation_worker.wait()
        super().closeEvent(event)

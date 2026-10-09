"""
Specimen Import Wizard for Observatum V2.

A multi-step wizard for importing insect collection specimen data from
TSV/CSV files. Features:

- File selection with format auto-detection
- Column mapping to database fields
- Species validation against UKSI (auto-populates taxonomy)
- Grid reference validation and VC lookup
- Preview with error highlighting
- Inline editing for problem records
- Species search dialog for fixing species errors
- Revalidate functionality after edits
- Problem export for unmatched records
- Duplicate handling options

REFACTORED: Split into modules for maintainability:
- validation_worker.py: ValidationWorker, ImportRow, RowStatus
- species_search_dialog.py: SpeciesSearchDialog
- bulk_resolution_dialog.py: BulkSpeciesResolutionDialog
- wizard_pages_mixin.py: Page creation methods
- wizard_validation_mixin.py: Validation callbacks
- wizard_species_mixin.py: Species resolution handlers
- wizard_file_mixin.py: File handling methods

Usage:
    from src.views.dialogs.specimen_import_wizard import SpecimenImportWizard
    
    wizard = SpecimenImportWizard(parent, uksi_model, vc_service)
    if wizard.exec() == QDialog.Accepted:
        imported_count = wizard.imported_count
"""

from typing import Optional, Dict, List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QStackedWidget, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal

from .validation_worker import ImportRow, RowStatus, _find_vc_database
from .wizard_pages_mixin import WizardPagesMixin
from .wizard_validation_mixin import WizardValidationMixin
from .wizard_species_mixin import WizardSpeciesResolutionMixin
from .wizard_file_mixin import WizardFileMixin

from ....themes import theme
from ....core.config import TabColors


class SpecimenImportWizard(
    QDialog,
    WizardPagesMixin,
    WizardValidationMixin,
    WizardSpeciesResolutionMixin,
    WizardFileMixin
):
    """
    Multi-step wizard for importing specimen collection data.
    
    Steps:
    1. File Selection - Choose TSV/CSV file
    2. Column Mapping - Map file columns to database fields
    3. Validation - Preview and validate data
    4. Import - Execute import with progress
    5. Summary - Show results
    """
    
    import_completed = Signal(int)
    specimen_imported = Signal(object)  # Emits the Specimen object after each successful import
    
    def __init__(self, parent=None, uksi_model=None, vc_service=None, db=None, specimen_model=None):
        super().__init__(parent)
        self.uksi_model = uksi_model
        self.db = db
        self.specimen_model = specimen_model
        self.vc_db_path = None
        self.alias_service = None
        self.species_aliases: Dict[str, dict] = {}
        
        # Tab colors for Collection
        self._accent = TabColors.COLLECTION
        self._accent_light = TabColors.COLLECTION_LIGHT
        self._accent_dark = TabColors.COLLECTION_DARK
        
        # Initialize services
        self._init_alias_service()
        self._init_vc_service(vc_service)
        
        self.setWindowTitle("Import Specimen Collection")
        self.setMinimumSize(1100, 800)
        self.resize(1200, 850)
        self.setModal(True)
        
        # Data state
        self.file_path: Optional[str] = None
        self.raw_rows: List[Dict[str, str]] = []
        self.columns: List[str] = []
        self.column_mapping: Dict[str, str] = {}
        self.validated_rows: List[ImportRow] = []
        self.imported_count: int = 0
        self.skipped_count: int = 0
        self.error_count: int = 0
        
        self._edited_row_indices: set = set()
        
        self._setup_ui()
    
    def _init_alias_service(self):
        """Initialize the species alias service."""
        try:
            from src.services.species_alias_service import SpeciesAliasService
            self.alias_service = SpeciesAliasService(db_manager=self.db)
            self._load_aliases()
        except ImportError:
            try:
                from services.species_alias_service import SpeciesAliasService
                self.alias_service = SpeciesAliasService(db_manager=self.db)
                self._load_aliases()
            except ImportError:
                print("[SpecimenImportWizard] Could not import SpeciesAliasService")
    
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
    
    def _load_aliases(self):
        """Load species aliases from database."""
        if not self.alias_service:
            return
        
        try:
            aliases = self.alias_service.get_all_aliases()
            for alias in aliases:
                key = alias['input_name'].lower().strip()
                self.species_aliases[key] = {
                    'uksi_name': alias['uksi_name'],
                    'uksi_tvk': alias.get('uksi_tvk', ''),
                    'uksi_common_name': alias.get('uksi_common_name', ''),
                    'uksi_order': alias.get('uksi_order', ''),
                    'uksi_family': alias.get('uksi_family', ''),
                    'uksi_subfamily': alias.get('uksi_subfamily', '')
                }
            print(f"[SpecimenImportWizard] Loaded {len(self.species_aliases)} species aliases")
        except Exception as e:
            print(f"[SpecimenImportWizard] Error loading aliases: {e}")
    
    def _setup_ui(self):
        """Set up the wizard UI."""
        t = theme()

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with accent color
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {self._accent};
                border: none;
            }}
        """)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(24, 20, 24, 20)

        self.header_label = QLabel("Import Specimen Collection")
        self.header_label.setStyleSheet("""
            color: white;
            font-size: 18px;
            font-weight: 600;
        """)
        header_layout.addWidget(self.header_label)

        self.step_label = QLabel("Step 1 of 5: Select File")
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

        # Create step pages (from WizardPagesMixin)
        self._create_file_selection_page()
        self._create_column_mapping_page()
        self._create_validation_page()
        self._create_import_page()
        self._create_summary_page()

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

        # Cancel on left
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setMinimumWidth(100)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_secondary')};
                border: 1px solid {t.get('border')};
                padding: 8px 16px;
                border-radius: {t.get('radius_md')};
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
                border-color: {t.get('border_strong')};
            }}
        """)
        self.cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self.cancel_btn)

        footer_layout.addStretch()

        # Back button
        self.back_btn = QPushButton("← Back")
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.setMinimumWidth(100)
        self.back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_primary')};
                border: 1px solid {t.get('border')};
                padding: 8px 16px;
                border-radius: {t.get('radius_md')};
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
            }}
        """)
        self.back_btn.clicked.connect(self._go_back)
        self.back_btn.setEnabled(False)
        footer_layout.addWidget(self.back_btn)

        # Resolve Species button (hidden by default)
        self.resolve_species_btn = QPushButton("Resolve Species...")
        self.resolve_species_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.resolve_species_btn.setMinimumWidth(130)
        self.resolve_species_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {self._accent};
                border: 1px solid {self._accent};
                padding: 8px 16px;
                border-radius: {t.get('radius_md')};
            }}
            QPushButton:hover {{
                background-color: {self._accent_light};
            }}
        """)
        self.resolve_species_btn.clicked.connect(self._open_resolve_species_dialog)
        self.resolve_species_btn.setVisible(False)
        footer_layout.addWidget(self.resolve_species_btn)

        # Next button
        self.next_btn = QPushButton("Next →")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setMinimumWidth(100)
        self.next_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._accent};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: {t.get('radius_md')};
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {self._accent_dark};
            }}
            QPushButton:disabled {{
                background-color: {t.get('text_muted')};
            }}
        """)
        self.next_btn.clicked.connect(self._go_next)
        self.next_btn.setEnabled(False)
        footer_layout.addWidget(self.next_btn)

        layout.addWidget(footer)

    def _do_import(self):
        """Execute the actual import using batch processing."""
        t = theme()

        if not self.db:
            QMessageBox.critical(self, "Error", "Database connection not available.")
            return

        # Filter rows to import
        rows_to_import = []
        import_errors = self.import_errors_checkbox.isChecked()
        import_warnings = self.import_warnings_radio.isChecked()

        for row in self.validated_rows:
            if row.status == RowStatus.ERROR and not import_errors:
                continue
            if row.status == RowStatus.WARNING and not import_warnings:
                continue
            rows_to_import.append(row)

        if not rows_to_import:
            QMessageBox.warning(self, "No Data", "No valid rows to import.")
            return

        # Taxonomy from each row's FINAL species (9 Oct 2026). A species picked by hand --
        # bulk resolution, the search dialogs, revalidate -- set the TVK but kept no sort key
        # (invisible in the collection sidebar) or the previous species' key (filed under
        # the wrong species). Now recomputed for every row, just before writing.
        try:
            from shared.import_core import taxonomy_for_tvks
            tax = taxonomy_for_tvks(r.species_tvk for r in rows_to_import)
        except Exception as e:
            tax = {}
            print(f"[SpecimenImportWizard] Taxonomy lookup failed: {e}")
        for r in rows_to_import:
            t_ = tax.get(r.species_tvk)
            if t_:
                r.taxonomic_sort_key = t_["sort_key"]
                r.superfamily = t_["superfamily"] or r.superfamily
                r.subfamily = t_["subfamily"] or r.subfamily
                r.order_name = t_["order_name"] or r.order_name
                r.family = t_["family"] or r.family
        def _has_key(k):
            try:
                return float(k) == float(k) and float(k) > 0      # not None, '', NaN or 0
            except (TypeError, ValueError):
                return False
        unsorted = [r for r in rows_to_import if not _has_key(r.taxonomic_sort_key)]
        if unsorted:
            names = ", ".join(sorted({r.species_name or "?" for r in unsorted})[:12])
            if QMessageBox.warning(
                    self, "Specimens without a place in the collection",
                    f"{len(unsorted)} specimen(s) have no taxonomic sort key, so they will not "
                    f"appear in the collection sidebar:\n\n{names}\n\nImport them anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return

        # Snapshot observatum.db first, so any import can be undone (9 Oct 2026)
        try:
            from shared.backup_service import backup_main_only
            backed_up = backup_main_only("pre-specimen-import")
        except Exception as e:
            print(f"[SpecimenImportWizard] Backup error: {e}")
            backed_up = False
        if not backed_up:
            if QMessageBox.warning(
                    self, "Backup failed",
                    "Observatum could not back up the database before importing.\n\nImport anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
        self._import_errors = []

        self.import_progress.setMaximum(len(rows_to_import))
        self.imported_count = 0
        self.skipped_count = 0
        self.error_count = 0

        try:
            from datetime import datetime
            now = datetime.now().isoformat()

            batch_size = 500
            ui_update_freq = 100
            insert_batch = []

            for i, row in enumerate(rows_to_import):
                # Combine import notes and error/warning messages
                notes_parts = []
                if row.import_notes:
                    notes_parts.append(row.import_notes)
                if row.error_message:
                    notes_parts.append(f"[Import: {row.error_message}]")
                combined_notes = " | ".join(notes_parts) if notes_parts else None

                # Convert empty specimen_code to None (allows multiple NULLs with UNIQUE constraint)
                specimen_code = row.specimen_code if row.specimen_code else None

                record = {
                    'specimen_code': specimen_code,
                    'species_name': row.species_name,
                    'species_tvk': row.species_tvk,
                    'common_name': row.common_name,
                    'order_name': row.order_name,
                    'family': row.family,
                    'subfamily': row.subfamily,
            'taxonomic_sort_key': row.taxonomic_sort_key,
            'taxon_group': row.taxon_group or None,
            'superfamily': row.superfamily or None,
                    'date_collected': row.date_collected,
                    'grid_ref': row.grid_ref,
                    'vice_county': row.vc_name,
                    'vc_number': row.vc_number,
                    'site_name': row.site_name,
                    'collector': row.collector,
                    'determiner': row.determiner,
                    'preparation_type': row.preparation_type,
                    'storage_location': row.storage_location,
                    'drawer_unit': row.drawer_unit,
                    'condition': row.condition,
                    'label_data': row.label_data,
                    'notes': row.notes,
                    'import_notes': combined_notes,
                    'created_at': now,
                    'updated_at': now,
                }
                insert_batch.append(record)

                # Execute batch when full or at end
                if len(insert_batch) >= batch_size or i == len(rows_to_import) - 1:
                    success_count = self._batch_insert_specimens(insert_batch)
                    self.imported_count += success_count
                    self.error_count += len(insert_batch) - success_count
                    insert_batch = []

                # Update UI every N rows
                if (i + 1) % ui_update_freq == 0 or i == len(rows_to_import) - 1:
                    self.import_progress.setValue(i + 1)
                    self.import_status_label.setText(f"Importing row {i + 1} of {len(rows_to_import)}...")
                    from PySide6.QtWidgets import QApplication
                    QApplication.processEvents()

            self.import_status_label.setText("Import complete!")
            self.import_status_label.setStyleSheet(f"color: {t.get('success')}; font-weight: 600;")

            if self._import_errors:
                shown = "\n".join(f"{who}: {why}" for who, why in self._import_errors[:8])
                more = len(self._import_errors) - 8
                QMessageBox.warning(
                    self, "Some specimens were not imported",
                    f"{len(self._import_errors)} specimen(s) could not be written.\n\n{shown}"
                    + (f"\n... and {more} more" if more > 0 else "")
                    + "\n\nA backup was taken before the import (pre-specimen-import).")

            if self.imported_count > 0:
                self.import_completed.emit(self.imported_count)

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Import Error", f"Error during import:\n{str(e)}")
            self.import_status_label.setText(f"Error: {str(e)}")
            self.import_status_label.setStyleSheet(f"color: {t.get('error')};")

    def _batch_insert_specimens(self, records: list) -> int:
        """Insert a batch; if it fails, row by row, collecting why (9 Oct 2026).

        One bad row (e.g. a specimen code already held) used to lose all 500, with the
        reason only on the console."""
        from shared.import_core import insert_rows
        ok, fails = insert_rows(
            self.db, "specimens", records,
            lambda r: f"{r.get('species_name') or '?'} {r.get('date_collected') or ''} "
                      f"{r.get('specimen_code') or ''}".strip())
        if not hasattr(self, "_import_errors"):
            self._import_errors = []
        self._import_errors += fails
        return ok

    def _update_summary(self):
        """Update the summary page."""
        t = theme()
        
        self.summary_stats.setText(
            f"Imported: {self.imported_count} specimens\n"
            f"Skipped: {self.skipped_count} rows\n"
            f"Errors: {self.error_count} rows"
        )
        
        if self.error_count > 0:
            self.summary_icon.setText("⚠")
            self.summary_icon.setStyleSheet(f"font-size: 48px; color: {t.get('warning')};")
            self.summary_title.setText("Import Complete with Warnings")
        else:
            self.summary_icon.setText("✓")
            self.summary_icon.setStyleSheet(f"font-size: 48px; color: {t.get('success')};")
            self.summary_title.setText("Import Complete!")
    
    def _go_back(self):
        """Go to previous step."""
        current = self.stack.currentIndex()
        if current > 0:
            self.stack.setCurrentIndex(current - 1)
            self._update_step_ui()
    
    def _go_next(self):
        """Go to next step."""
        current = self.stack.currentIndex()
        
        if current == 0:
            self._setup_column_mapping()
            self.stack.setCurrentIndex(1)
        elif current == 1:
            if self._start_validation():
                self.stack.setCurrentIndex(2)
            else:
                return
        elif current == 2:
            self.stack.setCurrentIndex(3)
        elif current == 3:
            self._do_import()
            self._update_summary()
            self.stack.setCurrentIndex(4)
        elif current == 4:
            self.accept()
            return
        
        self._update_step_ui()
    
    def _update_step_ui(self):
        """Update UI based on current step."""
        current = self.stack.currentIndex()
        
        steps = [
            "Step 1 of 5: Select File",
            "Step 2 of 5: Map Columns",
            "Step 3 of 5: Validate Data",
            "Step 4 of 5: Import Options",
            "Step 5 of 5: Summary",
        ]
        
        self.step_label.setText(steps[current])
        self.back_btn.setEnabled(current > 0 and current < 4)
        
        if current == 3:
            self.next_btn.setText("Import")
        elif current == 4:
            self.next_btn.setText("Close")
            self.cancel_btn.hide()
        else:
            self.next_btn.setText("Next →")
        
        if current == 0:
            self.next_btn.setEnabled(self.file_path is not None)
        elif current == 1:
            self.next_btn.setEnabled(True)
        elif current == 3:
            self.next_btn.setEnabled(True)
        elif current == 4:
            self.next_btn.setEnabled(True)

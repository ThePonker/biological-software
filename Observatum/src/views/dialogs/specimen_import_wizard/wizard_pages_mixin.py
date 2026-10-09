"""
Wizard Page Creation Mixin for Specimen Import Wizard.

Contains all _create_*_page() methods for the 5 wizard steps.
"""

from PySide6.QtWidgets import (
    QTableView,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QWidget, QProgressBar, QAbstractItemView, QGroupBox, QRadioButton, QButtonGroup,
    QScrollArea, QCheckBox
)
from PySide6.QtCore import Qt

from ....themes import theme
from ....core.config import ButtonColors


class WizardPagesMixin:
    """Mixin providing page creation methods for SpecimenImportWizard."""
    
    def _create_file_selection_page(self):
        """Create the file selection page (Step 1)."""
        t = theme()
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        
        # Instructions
        instructions = QLabel(
            "Select a TSV or CSV file containing your specimen collection data.\n"
            "The file should have column headers in the first row."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(f"color: {t.get('text_secondary')};")
        layout.addWidget(instructions)
        
        # File selection row
        file_layout = QHBoxLayout()
        
        self.file_path_label = QLabel("No file selected")
        self.file_path_label.setStyleSheet(f"""
            padding: 12px;
            background-color: {t.get('surface_alt')};
            border: 1px solid {t.get('border')};
            border-radius: {t.get('radius_md')};
            color: {t.get('text_secondary')};
        """)
        file_layout.addWidget(self.file_path_label, 1)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.setMinimumWidth(100)
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)
        
        layout.addLayout(file_layout)
        
        # File info
        self.file_info_label = QLabel("")
        self.file_info_label.setStyleSheet(f"color: {t.get('success')};")
        layout.addWidget(self.file_info_label)
        
        # Preview section
        preview_label = QLabel("Preview (first 5 rows):")
        preview_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')};")
        layout.addWidget(preview_label)
        
        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(200)
        self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview_table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_md')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                padding: 8px;
                border: none;
                border-bottom: 1px solid {t.get('border')};
                font-weight: 600;
            }}
        """)
        layout.addWidget(self.preview_table)
        
        layout.addStretch()
        self.stack.addWidget(page)
    
    def _create_column_mapping_page(self):
        """Create the column mapping page (Step 2)."""
        t = theme()
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        
        # Instructions
        instructions = QLabel(
            "Map your file columns to the specimen database fields.\n"
            "Required fields are marked with *. Taxonomy fields will be auto-populated from UKSI."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(f"color: {t.get('text_secondary')};")
        layout.addWidget(instructions)
        
        # Scrollable mapping area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        mapping_widget = QWidget()
        self.mapping_layout = QVBoxLayout(mapping_widget)
        self.mapping_layout.setSpacing(8)
        
        # Combos populated when file is loaded
        self.mapping_combos = {}
        
        scroll.setWidget(mapping_widget)
        layout.addWidget(scroll, 1)
        
        self.stack.addWidget(page)
    
    def _create_validation_page(self):
        """Create the validation preview page with inline editing (Step 3)."""
        t = theme()
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        
        # Progress bar
        self.validation_progress = QProgressBar()
        self.validation_progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {ButtonColors.PRIMARY};
            }}
        """)
        layout.addWidget(self.validation_progress)
        
        # Summary stats row
        stats_layout = QHBoxLayout()
        
        self.valid_count_label = QLabel("Valid: 0")
        self.valid_count_label.setStyleSheet(f"color: {t.get('success')}; font-weight: 600;")
        stats_layout.addWidget(self.valid_count_label)
        
        self.warning_count_label = QLabel("Warnings: 0")
        self.warning_count_label.setStyleSheet(f"color: {t.get('warning')}; font-weight: 600;")
        stats_layout.addWidget(self.warning_count_label)
        
        self.error_count_label = QLabel("Errors: 0")
        self.error_count_label.setStyleSheet(f"color: {t.get('error')}; font-weight: 600;")
        stats_layout.addWidget(self.error_count_label)

        stats_layout.addStretch()

        # Species Match Report button
        self.match_report_btn = QPushButton("Species Match Report")
        self.match_report_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.match_report_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {ButtonColors.PRIMARY};
                border: 1px solid {ButtonColors.PRIMARY};
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {ButtonColors.PRIMARY};
                color: white;
            }}
        """)
        self.match_report_btn.clicked.connect(self._show_match_report)
        self.match_report_btn.setEnabled(False)  # Enable after validation completes
        stats_layout.addWidget(self.match_report_btn)
        
        stats_layout.addStretch()
        
        # Export problems button
        self.export_problems_btn = QPushButton("Export Problems to CSV")
        self.export_problems_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_problems_btn.clicked.connect(self._export_problems)
        self.export_problems_btn.setEnabled(False)
        stats_layout.addWidget(self.export_problems_btn)
        
        layout.addLayout(stats_layout)
        
        # Edit instructions
        edit_instructions = QLabel(
            "💡 Double-click Species to search UKSI. Edit Date, Grid Ref, or Location directly, "
            "then click Revalidate."
        )
        edit_instructions.setStyleSheet(f"""
            color: {t.get('text_secondary')};
            font-size: 12px;
            padding: 6px 10px;
            background-color: {t.get('info_bg')};
            border-radius: {t.get('radius_sm')};
            border: 1px solid {t.get('info')};
        """)
        edit_instructions.setWordWrap(True)
        layout.addWidget(edit_instructions)
        
        # Validation table
        self.validation_table = QTableView()
        self.validation_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.validation_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.validation_table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_md')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                padding: 6px;
                border: none;
                border-bottom: 1px solid {t.get('border')};
                font-weight: 600;
            }}
            QTableWidget::item:selected {{
                background-color: {self._accent_light};
            }}
        """)
        # Double-click handled in validation mixin via _on_table_double_clicked
        # Cell changes handled via model.setData - no direct signal needed
        layout.addWidget(self.validation_table, 1)
        
        # Filter and action row
        filter_layout = QHBoxLayout()
        
        radio_style = self._get_radio_style()
        
        self.filter_button_group = QButtonGroup(self)
        
        self.show_all_radio = QRadioButton("Show All")
        self.show_all_radio.setStyleSheet(radio_style)
        self.show_all_radio.setChecked(True)
        self.filter_button_group.addButton(self.show_all_radio, 0)
        filter_layout.addWidget(self.show_all_radio)
        
        self.show_errors_radio = QRadioButton("Show Errors Only")
        self.show_errors_radio.setStyleSheet(radio_style)
        self.filter_button_group.addButton(self.show_errors_radio, 1)
        filter_layout.addWidget(self.show_errors_radio)
        
        self.show_warnings_radio = QRadioButton("Show Warnings Only")
        self.show_warnings_radio.setStyleSheet(radio_style)
        self.filter_button_group.addButton(self.show_warnings_radio, 2)
        filter_layout.addWidget(self.show_warnings_radio)
        
        self.filter_button_group.buttonClicked.connect(self._filter_validation_table)
        
        filter_layout.addStretch()
        
        # Revalidate button
        self.revalidate_btn = QPushButton("🔄 Revalidate Edited Rows")
        self.revalidate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.revalidate_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._accent};
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: {t.get('radius_sm')};
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {self._accent_dark}; }}
            QPushButton:disabled {{ background-color: {t.get('text_muted')}; }}
        """)
        self.revalidate_btn.clicked.connect(self._revalidate_edited_rows)
        self.revalidate_btn.setEnabled(False)
        filter_layout.addWidget(self.revalidate_btn)
        
        layout.addLayout(filter_layout)
        
        # Track edited rows
        self._edited_row_indices = set()
        
        self.stack.addWidget(page)
    
    def _create_import_page(self):
        """Create the import options and progress page (Step 4)."""
        t = theme()
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        
        radio_style = self._get_radio_style()
        checkbox_style = self._get_checkbox_style()
        
        # Import options group
        options_group = QGroupBox("Import Options")
        options_layout = QVBoxLayout(options_group)
        
        # Row handling section
        error_label = QLabel("Row handling:")
        error_label.setStyleSheet("font-weight: 600;")
        options_layout.addWidget(error_label)
        
        error_indent = QWidget()
        error_indent_layout = QVBoxLayout(error_indent)
        error_indent_layout.setContentsMargins(20, 0, 0, 0)
        error_indent_layout.setSpacing(8)
        
        self.import_errors_checkbox = QCheckBox("Import rows with errors (missing TVK, etc.)")
        self.import_errors_checkbox.setStyleSheet(checkbox_style)
        self.import_errors_checkbox.setChecked(False)
        error_indent_layout.addWidget(self.import_errors_checkbox)
        
        self.import_warnings_checkbox = QCheckBox("Import rows with warnings")
        self.import_warnings_checkbox.setStyleSheet(checkbox_style)
        self.import_warnings_checkbox.setChecked(True)
        error_indent_layout.addWidget(self.import_warnings_checkbox)
        
        # Compatibility alias
        self.import_warnings_radio = self.import_warnings_checkbox
        
        options_layout.addWidget(error_indent)
        layout.addWidget(options_group)
        
        # Progress section
        progress_label = QLabel("Import Progress:")
        progress_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(progress_label)
        
        self.import_progress = QProgressBar()
        self.import_progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {ButtonColors.PRIMARY};
            }}
        """)
        layout.addWidget(self.import_progress)
        
        self.import_status_label = QLabel("Ready to import")
        self.import_status_label.setStyleSheet(f"color: {t.get('text_secondary')};")
        layout.addWidget(self.import_status_label)
        
        layout.addStretch()
        self.stack.addWidget(page)
    
    def _create_summary_page(self):
        """Create the summary page (Step 5)."""
        t = theme()
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        
        # Success icon
        self.summary_icon = QLabel("✓")
        self.summary_icon.setStyleSheet(f"font-size: 48px; color: {t.get('success')};")
        self.summary_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.summary_icon)
        
        # Title
        self.summary_title = QLabel("Import Complete!")
        self.summary_title.setStyleSheet(f"""
            font-size: 24px;
            font-weight: 600;
            color: {t.get('text_primary')};
        """)
        self.summary_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.summary_title)
        
        # Stats box
        self.summary_stats = QLabel("")
        self.summary_stats.setStyleSheet(f"""
            font-size: 14px;
            color: {t.get('text_secondary')};
            padding: 16px;
            background-color: {t.get('surface_alt')};
            border-radius: {t.get('radius_lg')};
        """)
        self.summary_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.summary_stats)
        
        layout.addStretch()
        self.stack.addWidget(page)
    
    def _get_radio_style(self) -> str:
        """Get consistent radio button styling."""
        t = theme()
        return f"""
            QRadioButton {{
                spacing: 6px;
            }}
            QRadioButton::indicator {{
                width: 14px;
                height: 14px;
                border-radius: 6px;
                border: 2px solid {t.get('text_primary')};
            }}
            QRadioButton::indicator:checked {{
                background-color: {t.get('text_primary')};
                border: 2px solid {t.get('text_primary')};
            }}
            QRadioButton::indicator:unchecked {{
                background-color: {t.get('surface')};
                border: 2px solid {t.get('text_primary')};
            }}
        """
    
    def _get_checkbox_style(self) -> str:
        """Get consistent checkbox styling."""
        t = theme()
        return f"""
            QCheckBox {{
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 2px solid {t.get('text_primary')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {t.get('accent_collection', '#b8860b')};
                border: 2px solid {t.get('accent_collection', '#b8860b')};
                border-radius: 4px;
            }}
            QCheckBox::indicator:unchecked {{
                background-color: {t.get('surface')};
                border: 2px solid {t.get('border')};
                border-radius: 4px;
            }}
        """


    def _show_match_report(self):
        """Show the species matching report dialog."""
        from .species_match_report import SpeciesMatchReportDialog
        if hasattr(self, "validated_rows") and self.validated_rows:
            uksi = self.uksi_model if hasattr(self, 'uksi_model') else None
            dialog = SpeciesMatchReportDialog(
                self.validated_rows, self, uksi_model=uksi,
                name_columns=[self.column_mapping.get("species_name", "")])
            dialog.exec()

            # Refresh the validation table to show any re-matched species
            if hasattr(self, 'validation_model') and self.validation_model:
                self.validation_model.layoutChanged.emit()
            if dialog.changed_rows() and hasattr(self, '_update_validation_counts'):
                self._update_validation_counts()
            # Update confirmation counts
            if hasattr(self, '_update_confirmation_counts'):
                self._update_confirmation_counts()

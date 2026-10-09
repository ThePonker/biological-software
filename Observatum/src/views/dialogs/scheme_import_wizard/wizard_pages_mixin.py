"""
Wizard Pages Mixin for Recording Scheme Import Wizard.

Contains page creation methods for each wizard step:
1. Mode Selection (iRecord / NBN Atlas / Generic CSV)
2. File Selection + Preview
3. Column Mapping
4. Validation Preview
5. Confirmation
6. Summary
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableView, QProgressBar, QCheckBox, QScrollArea, QRadioButton, QGroupBox
)
from PySide6.QtCore import Qt

from src.themes import theme


from ..import_common.mode_option_card import ModeOptionCard  # noqa: F401  (C4: one copy)
from ..import_common.progress_pages import ImportProgressPagesMixin


class WizardPagesMixin(ImportProgressPagesMixin):
    """Mixin providing page creation methods for SchemeImportWizard."""

    def _get_radio_style(self) -> str:
        """Get radio button stylesheet."""
        t = theme()
        return f"""
            QRadioButton {{
                color: {t.get('text_primary')};
                spacing: 8px;
            }}
            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
            }}
            QRadioButton::indicator:checked {{
                background-color: {self._accent};
                border: 2px solid {self._accent};
                border-radius: 6px;
            }}
            QRadioButton::indicator:unchecked {{
                background-color: {t.get('surface')};
                border: 2px solid {t.get('border')};
                border-radius: 6px;
            }}
        """

    def _get_checkbox_style(self) -> str:
        """Get checkbox stylesheet."""
        t = theme()
        return f"""
            QCheckBox {{
                color: {t.get('text_primary')};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
            }}
            QCheckBox::indicator:checked {{
                background-color: {self._accent};
                border: 2px solid {self._accent};
                border-radius: 4px;
            }}
            QCheckBox::indicator:unchecked {{
                background-color: {t.get('surface')};
                border: 2px solid {t.get('border')};
                border-radius: 4px;
            }}
        """

    def _create_mode_selection_page(self):
        """Step 1: Choose import mode."""
        t = theme()

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Instructions
        instructions = QLabel(
            "Select the source of your Recording Scheme data:"
        )
        instructions.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 13px;")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Mode cards container
        self.mode_cards = []

        # iRecord option
        self.irecord_card = ModeOptionCard(
            "iRecord Download",
            "Import records from an iRecord CSV download.\n"
            "Columns are auto-mapped from iRecord format.\n"
            "Supports duplicate detection by iRecord ID.",
            "irecord",
            self._accent
        )
        self.irecord_card.setClickCallback(lambda: self._select_mode_card(self.irecord_card))
        self.irecord_card.setSelected(True)
        self.mode_cards.append(self.irecord_card)
        layout.addWidget(self.irecord_card)

        # NBN Atlas option
        self.nbn_card = ModeOptionCard(
            "NBN Atlas Download",
            "Import records from an NBN Atlas CSV download.\n"
            "Columns are auto-mapped from NBN format.\n"
            "Includes full Darwin Core taxonomy fields.",
            "nbn_atlas",
            self._accent
        )
        self.nbn_card.setClickCallback(lambda: self._select_mode_card(self.nbn_card))
        self.nbn_card.setSelected(False)
        self.mode_cards.append(self.nbn_card)
        layout.addWidget(self.nbn_card)

        # Generic CSV option
        self.generic_card = ModeOptionCard(
            "Generic CSV",
            "Import records from any CSV file.\n"
            "You map columns to database fields manually.\n"
            "Species taxonomy is auto-populated from UKSI.",
            "generic_csv",
            self._accent
        )
        self.generic_card.setClickCallback(lambda: self._select_mode_card(self.generic_card))
        self.generic_card.setSelected(False)
        self.mode_cards.append(self.generic_card)
        layout.addWidget(self.generic_card)

        layout.addStretch()

        self.stack.addWidget(page)

    def _select_mode_card(self, selected_card: ModeOptionCard):
        """Handle mode card selection."""
        for card in self.mode_cards:
            card.setSelected(card == selected_card)

    def _get_selected_mode_from_cards(self) -> str:
        """Get the mode_id of the selected card."""
        for card in self.mode_cards:
            if card.isSelected():
                return card.mode_id
        return "irecord"

    def _create_file_selection_page(self):
        """Step 2: Select and preview file."""
        t = theme()

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Instructions
        instructions = QLabel(
            "Select a CSV file containing your recording scheme data.\n"
            "The file should have column headers in the first row."
        )
        instructions.setStyleSheet(f"color: {t.get('text_secondary')};")
        layout.addWidget(instructions)

        # File browser
        file_layout = QHBoxLayout()

        self.file_path_label = QLabel("No file selected")
        self.file_path_label.setStyleSheet(f"""
            padding: 12px;
            background-color: {t.get('surface_alt')};
            border: 1px solid {t.get('border')};
            border-radius: {t.get('radius_md')};
            color: {t.get('text_muted')};
        """)
        file_layout.addWidget(self.file_path_label, 1)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.setMinimumWidth(100)
        self.browse_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._accent};
                color: white;
                border: none;
                padding: 10px 16px;
                border-radius: {t.get('radius_md')};
                font-weight: 500;
            }}
            QPushButton:hover {{ background-color: {self._accent_dark}; }}
        """)
        self.browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(self.browse_btn)

        layout.addLayout(file_layout)

        # File info
        self.file_info_label = QLabel("")
        self.file_info_label.setStyleSheet(f"color: {t.get('text_secondary')};")
        layout.addWidget(self.file_info_label)

        # Format detection label
        self.format_detected_label = QLabel("")
        self.format_detected_label.setStyleSheet(f"""
            background-color: {t.get('info_bg_light')};
            border: 1px solid {t.get('info_border')};
            border-radius: {t.get('radius_md')};
            padding: 8px 12px;
            color: {t.get('info_text')};
            font-size: 12px;
        """)
        self.format_detected_label.setVisible(False)
        layout.addWidget(self.format_detected_label)

        # Preview label
        preview_label = QLabel("Preview (first 5 rows):")
        preview_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(preview_label)

        # Preview table
        self.preview_table = QTableWidget()
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setStyleSheet(f"""
            QTableWidget {{
                gridline-color: {t.get('border')};
                background-color: {t.get('surface')};
                alternate-background-color: {t.get('surface_alt')};
            }}
            QTableWidget::item:selected {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {t.get('table_header_bg')};
                padding: 6px;
                border: none;
                border-bottom: 1px solid {t.get('border')};
                font-weight: 600;
            }}
        """)
        layout.addWidget(self.preview_table, 1)

        self.stack.addWidget(page)

    def _create_column_mapping_page(self):
        """Step 3: Map columns to database fields."""
        t = theme()

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Instructions
        self.mapping_instructions = QLabel(
            "Map your file columns to the recording scheme database fields.\n"
            "Required fields are marked with *. Taxonomy fields will be auto-populated from UKSI."
        )
        self.mapping_instructions.setStyleSheet(f"color: {t.get('text_secondary')};")
        layout.addWidget(self.mapping_instructions)

        # Scroll area for mappings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_md')};
                background-color: {t.get('surface')};
            }}
        """)

        scroll_widget = QWidget()
        self.mapping_layout = QVBoxLayout(scroll_widget)
        self.mapping_layout.setSpacing(12)
        self.mapping_layout.setContentsMargins(16, 16, 16, 16)

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, 1)

        # Store combo references
        self.mapping_combos: dict = {}

        self.stack.addWidget(page)

    def _create_validation_page(self):
        """Step 4: Validate and preview data."""
        t = theme()

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Progress bar
        self.validation_progress = QProgressBar()
        self.validation_progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_md')};
                background-color: {t.get('surface_alt')};
                text-align: center;
                height: 24px;
            }}
            QProgressBar::chunk {{
                background-color: {self._accent};
                border-radius: {t.get('radius_sm')};
            }}
        """)
        layout.addWidget(self.validation_progress)

        # Live counters
        counters_layout = QHBoxLayout()
        counters_layout.setSpacing(24)

        self.valid_label = QLabel("Valid: 0")
        self.valid_label.setStyleSheet(f"color: {t.get('success')}; font-weight: 600; font-size: 13px;")
        counters_layout.addWidget(self.valid_label)

        self.warning_label = QLabel("Warnings: 0")
        self.warning_label.setStyleSheet(f"color: {t.get('warning')}; font-weight: 600; font-size: 13px;")
        counters_layout.addWidget(self.warning_label)

        self.error_label = QLabel("Errors: 0")
        self.error_label.setStyleSheet(f"color: {t.get('error')}; font-weight: 600; font-size: 13px;")
        counters_layout.addWidget(self.error_label)

        counters_layout.addStretch()

        # Export problems button
        self.export_problems_btn = QPushButton("Export Problems to CSV")
        self.export_problems_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_problems_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('surface')};
                color: {t.get('text_secondary')};
                border: 1px solid {t.get('border')};
                padding: 6px 12px;
                border-radius: {t.get('radius_md')};
            }}
            QPushButton:hover {{ background-color: {t.get('hover')}; }}
        """)
        self.export_problems_btn.clicked.connect(self._export_problems)
        counters_layout.addWidget(self.export_problems_btn)

        self.match_report_btn = QPushButton("Species Match Report")
        self.match_report_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.match_report_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: #4a7c59;
                border: 1px solid #4a7c59;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: #4a7c59;
                color: white;
            }}
            QPushButton:disabled {{
                color: #aaa;
                border-color: #ccc;
            }}
        """)
        self.match_report_btn.setEnabled(False)
        self.match_report_btn.clicked.connect(self._show_match_report)
        counters_layout.addWidget(self.match_report_btn)

        # Names not matched exactly are errors until confirmed here (9 Oct 2026, one rule
        # set for the three wizards) -- the same dialog as the other two wizards
        self.resolve_species_btn = QPushButton("Resolve Species...")
        self.resolve_species_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.resolve_species_btn.setStyleSheet(self.match_report_btn.styleSheet())
        self.resolve_species_btn.clicked.connect(self._open_resolve_species_dialog)
        self.resolve_species_btn.setVisible(False)
        counters_layout.addWidget(self.resolve_species_btn)

        layout.addLayout(counters_layout)

        # Edit hint (for generic mode)
        self.edit_hint = QLabel(
            "💡 Double-click Species to search UKSI. Edit Date, Grid Ref, or Location directly, then click Revalidate."
        )
        self.edit_hint.setStyleSheet(f"""
            background-color: {t.get('info_bg_light')};
            border: 1px solid {t.get('info_border')};
            border-radius: {t.get('radius_md')};
            padding: 8px 12px;
            color: {t.get('info_text')};
            font-size: 12px;
        """)
        layout.addWidget(self.edit_hint)

        # Validation table
        self.validation_table = QTableView()
        self.validation_table.setAlternatingRowColors(True)
        self.validation_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.validation_table.setStyleSheet(f"""
            QTableView {{
                gridline-color: {t.get('border')};
                background-color: {t.get('surface')};
                alternate-background-color: {t.get('surface_alt')};
            }}
            QTableWidget::item:selected {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {t.get('table_header_bg')};
                padding: 6px;
                border: none;
                border-bottom: 1px solid {t.get('border')};
                font-weight: 600;
            }}
        """)
        self.validation_table.doubleClicked.connect(self._on_table_double_clicked)
        # cellChanged not used with QTableView/model
        layout.addWidget(self.validation_table, 1)

        # Filter and revalidate row
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(16)

        filter_style = f"""
            QRadioButton {{
                color: {t.get('text_primary')};
                font-size: 13px;
                font-weight: 500;
                spacing: 8px;
            }}
            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
            }}
            QRadioButton::indicator:unchecked {{
                border: 2px solid {t.get('border_strong')};
                border-radius: 8px;
                background-color: {t.get('surface')};
            }}
            QRadioButton::indicator:checked {{
                border: 2px solid {self._accent};
                border-radius: 8px;
                background-color: {self._accent};
            }}
        """

        self.filter_all_radio = QRadioButton("Show All")
        self.filter_all_radio.setChecked(True)
        self.filter_all_radio.setStyleSheet(filter_style)
        self.filter_all_radio.toggled.connect(self._apply_filter)
        filter_layout.addWidget(self.filter_all_radio)

        self.filter_errors_radio = QRadioButton("Show Errors Only")
        self.filter_errors_radio.setStyleSheet(filter_style)
        self.filter_errors_radio.toggled.connect(self._apply_filter)
        filter_layout.addWidget(self.filter_errors_radio)

        self.filter_warnings_radio = QRadioButton("Show Warnings Only")
        self.filter_warnings_radio.setStyleSheet(filter_style)
        self.filter_warnings_radio.toggled.connect(self._apply_filter)
        filter_layout.addWidget(self.filter_warnings_radio)

        filter_layout.addStretch()

        # Revalidate button
        self.revalidate_btn = QPushButton("🔄 Revalidate Edited Rows")
        self.revalidate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.revalidate_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._accent};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: {t.get('radius_md')};
                font-weight: 500;
            }}
            QPushButton:hover {{ background-color: {self._accent_dark}; }}
        """)
        self.revalidate_btn.clicked.connect(self._revalidate_edited_rows)
        filter_layout.addWidget(self.revalidate_btn)

        layout.addLayout(filter_layout)

        self.stack.addWidget(page)

    def _create_confirmation_page(self):
        """Step 5: Import Options - matches Specimen wizard layout."""
        t = theme()

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        radio_style = self._get_radio_style()
        checkbox_style = self._get_checkbox_style()

        # Import options group (matches Specimen wizard)
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

        options_layout.addWidget(error_indent)

        # Duplicate handling section
        dup_label = QLabel("Duplicate handling:")
        dup_label.setStyleSheet("font-weight: 600; margin-top: 12px;")
        options_layout.addWidget(dup_label)

        dup_indent = QWidget()
        dup_indent_layout = QVBoxLayout(dup_indent)
        dup_indent_layout.setContentsMargins(20, 0, 0, 0)
        dup_indent_layout.setSpacing(8)

        self.update_duplicates_checkbox = QCheckBox("Update existing records")
        self.update_duplicates_checkbox.setToolTip("Overwrite existing records if a duplicate is found")
        self.update_duplicates_checkbox.setStyleSheet(checkbox_style)
        self.update_duplicates_checkbox.setChecked(False)
        dup_indent_layout.addWidget(self.update_duplicates_checkbox)

        options_layout.addWidget(dup_indent)
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
                background-color: {self._accent};
            }}
        """)
        layout.addWidget(self.import_progress)

        self.import_status_label = QLabel("Ready to import")
        self.import_status_label.setStyleSheet(f"color: {t.get('text_secondary')};")
        layout.addWidget(self.import_status_label)

        layout.addStretch()
        self.stack.addWidget(page)

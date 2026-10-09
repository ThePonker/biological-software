"""
Wizard Pages Mixin for Observation Import Wizard.

Contains page creation methods for each wizard step:
1. Mode Selection (iRecord Sync / Personal Upload)
2. File Selection + Preview
3. Column Mapping
4. Validation Preview
5. Confirmation
6. Summary
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QRadioButton, QGroupBox, QTableWidget,
    QProgressBar, QCheckBox,
    QScrollArea, QLineEdit, QDateEdit
)
from PySide6.QtCore import Qt, QDate

from src.themes import theme


class ModeOptionCard(QFrame):
    """
    A clickable card for mode selection with proper hover behavior.
    The entire card highlights together when hovered or selected.
    """
    
    def __init__(self, title: str, description: str, mode_id: str, accent_color: str, parent=None):
        super().__init__(parent)
        self.accent_color = accent_color
        self.mode_id = mode_id
        self._selected = False
        self._on_clicked = None
        
        t = theme()
        
        self.setObjectName("modeCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style(False)
        
        layout = QHBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Custom radio indicator (circle)
        self.indicator = QLabel()
        self.indicator.setFixedSize(20, 20)
        self._update_indicator(False)
        layout.addWidget(self.indicator)
        
        # Text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"""
            font-weight: 600; 
            font-size: 14px; 
            color: {t.get('text_primary')};
            background: transparent;
            border: none;
        """)
        text_layout.addWidget(self.title_label)
        
        self.desc_label = QLabel(description)
        self.desc_label.setStyleSheet(f"""
            color: {t.get('text_secondary')}; 
            font-size: 12px;
            background: transparent;
            border: none;
        """)
        self.desc_label.setWordWrap(True)
        text_layout.addWidget(self.desc_label)
        
        layout.addLayout(text_layout, 1)
    
    def _update_style(self, selected: bool):
        """Update card border and background based on selection state."""
        t = theme()
        border_color = self.accent_color if selected else t.get('border')
        bg_color = t.get('surface')
        
        self.setStyleSheet(f"""
            ModeOptionCard {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: {t.get('radius_lg')};
            }}
            ModeOptionCard:hover {{
                border-color: {self.accent_color};
            }}
        """)
    
    def _update_indicator(self, selected: bool):
        """Update the radio indicator circle."""
        t = theme()
        
        if selected:
            # Filled circle with accent color
            self.indicator.setStyleSheet(f"""
                background-color: {self.accent_color};
                border: 2px solid {self.accent_color};
                border-radius: 6px;
            """)
        else:
            # Empty circle with visible border
            self.indicator.setStyleSheet(f"""
                background-color: {t.get('surface')};
                border: 2px solid {t.get('border_strong')};
                border-radius: 6px;
            """)
    
    def setSelected(self, selected: bool):
        """Set the selection state of this card."""
        self._selected = selected
        self._update_style(selected)
        self._update_indicator(selected)
    
    def isSelected(self) -> bool:
        return self._selected
    
    def mousePressEvent(self, event):
        """Handle click to select this card."""
        if self._on_clicked:
            self._on_clicked()
        super().mousePressEvent(event)
    
    def setClickCallback(self, callback):
        """Set callback for when card is clicked."""
        self._on_clicked = callback


class WizardPagesMixin:
    """Mixin providing page creation methods for ObservationImportWizard."""
    
    def _create_mode_selection_page(self):
        """Step 1: Choose import mode."""
        t = theme()
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Instructions
        instructions = QLabel(
            "Select the type of data you want to import:"
        )
        instructions.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 13px;")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Mode cards container
        self.mode_cards = []
        
        # iRecord Sync option
        self.irecord_card = ModeOptionCard(
            "iRecord Sync",
            "Import records from an iRecord CSV download.\n"
            "Updates existing records and adds new ones.\n"
            "All columns are auto-mapped from iRecord format.",
            "irecord_sync",
            self._accent
        )
        self.irecord_card.setClickCallback(lambda: self._select_mode_card(self.irecord_card))
        self.irecord_card.setSelected(True)
        self.mode_cards.append(self.irecord_card)
        layout.addWidget(self.irecord_card)

        # iRecord commercial checkbox (mark new records as Commercial)
        self.irecord_commercial_checkbox = QCheckBox('Mark new records as Commercial')
        self.irecord_commercial_checkbox.setStyleSheet(f"color: {t.get('text_secondary')}; margin-left: 20px; border: none; background: transparent;")
        self.irecord_commercial_checkbox.setVisible(False)
        self.irecord_commercial_checkbox.toggled.connect(self._toggle_irecord_commercial)
        layout.addWidget(self.irecord_commercial_checkbox)
        
        # Personal Upload option
        self.personal_card = ModeOptionCard(
            "Personal Upload",
            "Import records from your own CSV template.\n"
            "New records only - you map columns to database fields.\n"
            "Species taxonomy is auto-populated from UKSI.",
            "personal_upload",
            self._accent
        )
        self.personal_card.setClickCallback(lambda: self._select_mode_card(self.personal_card))
        self.personal_card.setSelected(False)
        self.mode_cards.append(self.personal_card)
        layout.addWidget(self.personal_card)

        # Commercial Upload option
        self.commercial_card = ModeOptionCard(
            "Commercial Data",
            "Import commercial survey/consultancy records.\n"
            "Set project, client, and embargo details.\n"
            "Records are protected from upload until embargo lifts.",
            "commercial_upload",
            self._accent
        )
        self.commercial_card.setClickCallback(lambda: self._select_mode_card(self.commercial_card))
        self.commercial_card.setSelected(False)
        self.mode_cards.append(self.commercial_card)
        layout.addWidget(self.commercial_card)

        # Commercial settings frame (shown when Commercial mode selected)
        self.commercial_settings_frame = QFrame()
        self.commercial_settings_frame.setStyleSheet(f"background-color: {t.get('surface_alt')}; border: 1px solid {t.get('border')}; border-radius: 8px;")
        self.commercial_settings_frame.setVisible(False)
        comm_layout = QVBoxLayout(self.commercial_settings_frame)
        comm_layout.setSpacing(12)

        comm_title = QLabel("Commercial Record Settings")
        comm_title.setStyleSheet(f"font-weight: 600; font-size: 14px; color: {t.get('text_primary')}; border: none; background: transparent;")
        comm_layout.addWidget(comm_title)

        # Project name
        proj_layout = QHBoxLayout()
        proj_label = QLabel("Project Name:")
        proj_label.setStyleSheet(f"color: {t.get('text_secondary')}; border: none; background: transparent;")
        proj_label.setFixedWidth(130)
        proj_layout.addWidget(proj_label)
        self.commercial_project = QLineEdit()
        self.commercial_project.setPlaceholderText("e.g. Thames Valley Ecology Survey")
        self.commercial_project.setStyleSheet(f"background-color: {t.get('surface')}; color: {t.get('text_primary')}; border: 1px solid {t.get('border')}; border-radius: 4px; padding: 6px;")
        proj_layout.addWidget(self.commercial_project)
        self.browse_projects_btn = QPushButton("Browse...")
        self.browse_projects_btn.setFixedWidth(80)
        self.browse_projects_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_projects_btn.setStyleSheet(f"background-color: {t.get('surface')}; color: {t.get('text_primary')}; border: 1px solid {t.get('border')}; border-radius: 4px; padding: 6px;")
        self.browse_projects_btn.clicked.connect(lambda: self._browse_existing_values("project_name", self.commercial_project))
        proj_layout.addWidget(self.browse_projects_btn)
        comm_layout.addLayout(proj_layout)

        # Client
        client_layout = QHBoxLayout()
        client_label = QLabel("Client:")
        client_label.setStyleSheet(f"color: {t.get('text_secondary')}; border: none; background: transparent;")
        client_label.setFixedWidth(130)
        client_layout.addWidget(client_label)
        self.commercial_client = QLineEdit()
        self.commercial_client.setPlaceholderText("e.g. Environment Agency")
        self.commercial_client.setStyleSheet(f"background-color: {t.get('surface')}; color: {t.get('text_primary')}; border: 1px solid {t.get('border')}; border-radius: 4px; padding: 6px;")
        client_layout.addWidget(self.commercial_client)
        self.browse_clients_btn = QPushButton("Browse...")
        self.browse_clients_btn.setFixedWidth(80)
        self.browse_clients_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_clients_btn.setStyleSheet(f"background-color: {t.get('surface')}; color: {t.get('text_primary')}; border: 1px solid {t.get('border')}; border-radius: 4px; padding: 6px;")
        self.browse_clients_btn.clicked.connect(lambda: self._browse_existing_values("client", self.commercial_client))
        client_layout.addWidget(self.browse_clients_btn)
        comm_layout.addLayout(client_layout)

        # Embargo toggle
        self.embargo_checkbox = QCheckBox("Apply embargo period")
        self.embargo_checkbox.setStyleSheet(f"color: {t.get('text_primary')}; border: none; background: transparent;")
        self.embargo_checkbox.setChecked(True)
        self.embargo_checkbox.toggled.connect(self._toggle_embargo_date)
        comm_layout.addWidget(self.embargo_checkbox)

        # Embargo date container (shown when checkbox checked)
        self.embargo_date_frame = QFrame()
        self.embargo_date_frame.setStyleSheet("border: none; background: transparent;")
        embargo_layout = QHBoxLayout(self.embargo_date_frame)
        embargo_layout.setContentsMargins(20, 0, 0, 0)
        embargo_label = QLabel("Until:")
        embargo_label.setStyleSheet(f"color: {t.get('text_secondary')}; border: none; background: transparent;")
        embargo_label.setFixedWidth(50)
        embargo_layout.addWidget(embargo_label)
        self.commercial_embargo_date = QDateEdit()
        self.commercial_embargo_date.setCalendarPopup(True)
        self.commercial_embargo_date.calendarWidget().setMinimumWidth(280)
        self.commercial_embargo_date.setMinimumWidth(120)
        self.commercial_embargo_date.setDate(QDate.currentDate().addYears(1))
        self.commercial_embargo_date.setStyleSheet(f"background-color: {t.get('surface')}; color: {t.get('text_primary')}; border: 1px solid {t.get('border')}; border-radius: 4px; padding: 6px;")
        embargo_layout.addWidget(self.commercial_embargo_date)
        embargo_layout.addStretch()
        comm_layout.addWidget(self.embargo_date_frame)

        # Info text
        self.embargo_info = QLabel("Records will be protected from iRecord upload until this date.")
        self.embargo_info.setStyleSheet(f"color: {t.get('text_muted')}; font-size: 11px; border: none; background: transparent; margin-left: 20px;")
        comm_layout.addWidget(self.embargo_info)

        layout.addWidget(self.commercial_settings_frame)
        
        layout.addStretch()
        
        self.stack.addWidget(page)
    
    def _select_mode_card(self, selected_card: ModeOptionCard):
        """Handle mode card selection - deselect others."""
        for card in self.mode_cards:
            card.setSelected(card == selected_card)
        # Show/hide commercial settings
        if hasattr(self, 'commercial_settings_frame'):
            # Show commercial settings for Commercial mode OR iRecord with checkbox checked
            show_commercial = selected_card.mode_id == 'commercial_upload' or (
                selected_card.mode_id == 'irecord_sync' and 
                hasattr(self, 'irecord_commercial_checkbox') and 
                self.irecord_commercial_checkbox.isChecked()
            )
            self.commercial_settings_frame.setVisible(show_commercial)
        # Show/hide iRecord commercial checkbox
        if hasattr(self, 'irecord_commercial_checkbox'):
            self.irecord_commercial_checkbox.setVisible(selected_card.mode_id == 'irecord_sync')
            if selected_card.mode_id != 'irecord_sync':
                self.irecord_commercial_checkbox.setChecked(False)
    

    def _toggle_irecord_commercial(self, checked: bool):
        """Show/hide commercial settings when iRecord commercial checkbox toggled."""
        if hasattr(self, 'commercial_settings_frame'):
            self.commercial_settings_frame.setVisible(checked)

    def _toggle_embargo_date(self, checked: bool):
        """Show/hide embargo date picker based on checkbox."""
        if hasattr(self, 'embargo_date_frame'):
            self.embargo_date_frame.setVisible(checked)
        if hasattr(self, 'embargo_info'):
            self.embargo_info.setVisible(checked)

    def _get_selected_mode_from_cards(self) -> str:
        """Get the mode_id of the selected card."""
        for card in self.mode_cards:
            if card.isSelected():
                return card.mode_id
        return "irecord_sync"
    
    def _create_file_selection_page(self):
        """Step 2: Select and preview file."""
        t = theme()
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Instructions
        instructions = QLabel(
            "Select a CSV file containing your observation data.\n"
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
            "Map your file columns to the observation database fields.\n"
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
        
        # Export problems button (only for personal mode)
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
        
        layout.addLayout(counters_layout)
        
        # Hint for editing (personal mode only)
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
        self.validation_table = QTableWidget()
        self.validation_table.setAlternatingRowColors(True)
        self.validation_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.validation_table.setStyleSheet(f"""
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
        self.validation_table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.validation_table.cellChanged.connect(self._on_cell_changed)
        layout.addWidget(self.validation_table, 1)
        
        # Filter and revalidate row
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(16)
        
        # Styled filter radio buttons with better readability
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
        
        # Revalidate button (personal mode only)
        self.resolve_species_btn = QPushButton("Resolve Species...")
        self.resolve_species_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.resolve_species_btn.setMinimumWidth(130)
        self.resolve_species_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('surface')};
                color: {t.get('warning')};
                border: 1px solid {t.get('warning')};
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {t.get('surface_alt')}; }}
        """)
        self.resolve_species_btn.clicked.connect(self._open_resolve_species_dialog)
        self.resolve_species_btn.setVisible(False)
        filter_layout.addWidget(self.resolve_species_btn)

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
        """Step 5: Confirmation before import."""
        t = theme()
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Summary frame
        summary_frame = QFrame()
        summary_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
                padding: 20px;
            }}
        """)
        summary_layout = QVBoxLayout(summary_frame)
        summary_layout.setSpacing(16)
        
        # Title
        summary_title = QLabel("Import Summary")
        summary_title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {t.get('text_primary')};")
        summary_layout.addWidget(summary_title)
        
        # Stats grid
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(32)
        
        # New records
        self.new_count_frame = self._create_stat_card("New Records", "0", t.get('success'))
        stats_layout.addWidget(self.new_count_frame)
        
        # Update records
        self.update_count_frame = self._create_stat_card("To Update", "0", t.get('info'))
        stats_layout.addWidget(self.update_count_frame)
        
        # Skipped
        self.skip_count_frame = self._create_stat_card("Skipped", "0", t.get('text_muted'))
        stats_layout.addWidget(self.skip_count_frame)
        
        stats_layout.addStretch()
        summary_layout.addLayout(stats_layout)
        
        # Row handling section
        error_group = QGroupBox("Row handling:")
        error_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 600;
                color: {t.get('text_primary')};
                border: 1px solid {t.get('border')};
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }}
        """)
        error_layout = QVBoxLayout(error_group)
        error_layout.setSpacing(6)

        # Styled radio buttons for row handling
        t = theme()
        radio_style = f"""
            QRadioButton {{
                spacing: 8px; font-size: 12px; color: {t.get('text_primary')};
            }}
            QRadioButton::indicator {{
                width: 16px; height: 16px; border-radius: 8px;
                border: 2px solid {t.get('border_strong')};
            }}
            QRadioButton::indicator:checked {{
                background-color: {t.get('accent_observations', '#5f8575')};
                border-color: {t.get('accent_observations', '#5f8575')};
            }}
            QRadioButton::indicator:unchecked {{
                background-color: {t.get('surface')};
            }}
        """
        self.import_all_checkbox = QRadioButton("Import all valid and warning rows (skip errors)")
        self.import_all_checkbox.setChecked(True)
        self.import_all_checkbox.setStyleSheet(radio_style)
        error_layout.addWidget(self.import_all_checkbox)

        self.import_valid_only_checkbox = QRadioButton("Import valid rows only (skip warnings and errors)")
        self.import_valid_only_checkbox.setStyleSheet(radio_style)
        error_layout.addWidget(self.import_valid_only_checkbox)

        self.import_warnings_checkbox = QRadioButton("Import all rows including errors (not recommended)")
        self.import_warnings_checkbox.setStyleSheet(radio_style)
        error_layout.addWidget(self.import_warnings_checkbox)

        # Alias for compatibility with import mixin
        self.import_warnings_radio = self.import_warnings_checkbox

        summary_layout.addWidget(error_group)

        # View updates button
        self.view_updates_btn = QPushButton("View Records to Update")
        self.view_updates_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_updates_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('surface')};
                color: {t.get('info')};
                border: 1px solid {t.get('info')};
                padding: 8px 16px;
                border-radius: {t.get('radius_md')};
            }}
            QPushButton:hover {{ background-color: {t.get('info_bg_light')}; }}
        """)
        self.view_updates_btn.clicked.connect(self._show_update_preview)
        summary_layout.addWidget(self.view_updates_btn)
        
        layout.addWidget(summary_frame)
        
        # Options frame
        self.options_frame = QFrame()
        self.options_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
                padding: 20px;
            }}
        """)
        options_layout = QVBoxLayout(self.options_frame)
        options_layout.setSpacing(12)
        
        self.options_title = QLabel("Import Options")
        self.options_title.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {t.get('text_primary')};")
        options_layout.addWidget(self.options_title)
        
        # Never upload checkbox (ONLY for Personal Upload mode - hidden for iRecord Sync)
        self.never_upload_checkbox = QCheckBox("Mark all imported records as 'Never upload to iRecord'")
        self.never_upload_checkbox.setStyleSheet(f"color: {t.get('text_primary')};")
        options_layout.addWidget(self.never_upload_checkbox)
        
        # Duplicate handling (personal mode)
        self.skip_duplicates_checkbox = QCheckBox("Skip duplicate records (matching species + date + grid ref)")
        self.skip_duplicates_checkbox.setChecked(True)
        self.skip_duplicates_checkbox.setStyleSheet(f"color: {t.get('text_primary')};")
        options_layout.addWidget(self.skip_duplicates_checkbox)

        # Include errors checkbox
        # Hidden ? row handling radio buttons handle this
        self.include_errors_checkbox = QCheckBox("")
        self.include_errors_checkbox.setVisible(False)
        
        layout.addWidget(self.options_frame)
        
        layout.addStretch()
        
        self.stack.addWidget(page)
    
    def _create_stat_card(self, label: str, value: str, color: str) -> QFrame:
        """Create a stat card for confirmation page."""
        t = theme()
        
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface_alt')};
                border-radius: {t.get('radius_md')};
                padding: 12px 20px;
            }}
        """)
        
        layout = QVBoxLayout(frame)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)
        
        value_label = QLabel(value)
        value_label.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {color};")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setObjectName("value_label")
        layout.addWidget(value_label)
        
        name_label = QLabel(label)
        name_label.setStyleSheet(f"font-size: 12px; color: {t.get('text_secondary')};")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)
        
        return frame
    
    def _create_import_page(self):
        """Step 6: Import progress."""
        t = theme()
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)
        
        layout.addStretch()
        
        # Status label
        self.import_status_label = QLabel("Preparing import...")
        self.import_status_label.setStyleSheet(f"font-size: 16px; color: {t.get('text_primary')};")
        self.import_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.import_status_label)
        
        # Progress bar
        self.import_progress = QProgressBar()
        self.import_progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_md')};
                background-color: {t.get('surface_alt')};
                text-align: center;
                height: 28px;
                font-weight: 600;
            }}
            QProgressBar::chunk {{
                background-color: {self._accent};
                border-radius: {t.get('radius_sm')};
            }}
        """)
        self.import_progress.setMinimum(0)
        self.import_progress.setMaximum(100)
        layout.addWidget(self.import_progress)
        
        # Counts during import
        self.import_counts_label = QLabel("")
        self.import_counts_label.setStyleSheet(f"color: {t.get('text_secondary')};")
        self.import_counts_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.import_counts_label)
        
        layout.addStretch()
        
        self.stack.addWidget(page)
    
    def _create_summary_page(self):
        """Step 7: Import summary."""
        t = theme()
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)
        
        layout.addStretch()
        
        # Icon
        self.summary_icon = QLabel("✓")
        self.summary_icon.setStyleSheet(f"font-size: 64px; color: {t.get('success')};")
        self.summary_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.summary_icon)
        
        # Title
        self.summary_title = QLabel("Import Complete!")
        self.summary_title.setStyleSheet(f"font-size: 20px; font-weight: 600; color: {t.get('text_primary')};")
        self.summary_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.summary_title)
        
        # Stats
        self.summary_stats = QLabel("")
        self.summary_stats.setStyleSheet(f"font-size: 14px; color: {t.get('text_secondary')};")
        self.summary_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.summary_stats)
        
        layout.addStretch()
        
        self.stack.addWidget(page)
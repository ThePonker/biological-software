"""
Scheme Dialog Components.

Dialogs for Recording Scheme tab:
- SchemeRecordDetailDialog: Record detail modal
- SaveFilterDialog: Save filter dialog
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QWidget, QLineEdit
)
from PySide6.QtCore import Signal

from ...themes import theme


class SchemeRecordDetailDialog(QDialog):
    """Modal dialog showing full details of a recording scheme record."""
    
    profile_requested = Signal(dict)
    
    def __init__(self, record: dict, parent=None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle("Record Detail")
        self.setMinimumSize(480, 600)
        self.setModal(True)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Species header
        self._setup_species_header(layout)
        
        # Taxonomy section
        self._setup_taxonomy_section(layout)
        
        # Record details
        self._setup_details_section(layout)
        
        # Verification status
        self._setup_verification_section(layout)
        
        # Source key
        if self.record.get('sourceKey'):
            self._setup_source_key_section(layout)
        
        # Species Profile section
        self._setup_profile_section(layout)
        
        layout.addStretch()
        
        # Action buttons
        self._setup_action_buttons(layout)
    
    def _setup_species_header(self, layout):
        """Set up species header."""
        t = theme()
        
        species_frame = QFrame()
        species_layout = QVBoxLayout(species_frame)
        species_layout.setContentsMargins(0, 0, 0, 0)
        
        species_name = QLabel(f"<i>{self.record.get('species', '')}</i>")
        species_name.setStyleSheet(f"font-size: {t.font_size('2xl')}; color: {t.get('text_primary')};")
        species_layout.addWidget(species_name)
        
        if self.record.get('common'):
            common_name = QLabel(self.record['common'])
            common_name.setStyleSheet(f"color: {t.get('text_secondary')};")
            species_layout.addWidget(common_name)
        
        layout.addWidget(species_frame)
    
    def _setup_taxonomy_section(self, layout):
        """Set up taxonomy section."""
        t = theme()
        
        tax_frame = QFrame()
        tax_frame.setStyleSheet(f"background-color: {t.get('surface_alt')}; border-radius: {t.get('radius_md')}; padding: 12px;")
        tax_layout = QVBoxLayout(tax_frame)
        
        tax_header = QLabel("TAXONOMY (UKSI)")
        tax_header.setStyleSheet(f"font-size: {t.font_size('xs')}; font-weight: bold; color: {t.get('text_secondary')}; letter-spacing: 1px;")
        tax_layout.addWidget(tax_header)
        
        tax_grid = QGridLayout()
        tax_grid.setHorizontalSpacing(24)
        tax_grid.setVerticalSpacing(4)
        
        self._add_tax_field(tax_grid, 0, "Family", self.record.get('family', ''))
        self._add_tax_field(tax_grid, 1, "Subfamily", self.record.get('subfamily', ''))
        
        tax_layout.addLayout(tax_grid)
        layout.addWidget(tax_frame)
    
    def _setup_details_section(self, layout):
        """Set up record details section."""
        details_grid = QGridLayout()
        details_grid.setHorizontalSpacing(24)
        details_grid.setVerticalSpacing(8)
        
        row = 0
        self._add_detail_field(details_grid, row, 0, "Date", self.record.get('date', ''))
        self._add_detail_field(details_grid, row, 1, "Grid Ref", self.record.get('gridRef', ''), mono=True)
        
        row += 1
        self._add_detail_field(details_grid, row, 0, "Location", self.record.get('location', ''), colspan=2)
        
        row += 1
        vc_text = f"{self.record.get('vc', '')} - {self.record.get('vcName', '')}"
        self._add_detail_field(details_grid, row, 0, "Vice County", vc_text)
        
        # Source badge
        t = theme()
        source = self.record.get('source', '')
        source_widget = QLabel(source)
        source_widget.setStyleSheet(self._get_source_style(source))
        source_container = QWidget()
        sc_layout = QVBoxLayout(source_container)
        sc_layout.setContentsMargins(0, 0, 0, 0)
        sc_label = QLabel("Source")
        sc_label.setStyleSheet(f"font-size: {t.font_size('sm')}; color: {t.get('text_secondary')};")
        sc_layout.addWidget(sc_label)
        sc_layout.addWidget(source_widget)
        details_grid.addWidget(source_container, row, 1)
        
        row += 1
        self._add_detail_field(details_grid, row, 0, "Recorder", self.record.get('recorder', ''))
        self._add_detail_field(details_grid, row, 1, "Determiner", self.record.get('determiner', ''))
        
        layout.addLayout(details_grid)
    
    def _setup_verification_section(self, layout):
        """Set up verification status section."""
        t = theme()
        
        status_frame = QFrame()
        status_frame.setStyleSheet(f"border-top: 1px solid {t.get('border')}; padding-top: 12px;")
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 12, 0, 0)
        
        status_label = QLabel("Verification Status")
        status_label.setStyleSheet(f"font-size: {t.font_size('sm')}; color: {t.get('text_secondary')};")
        status_layout.addWidget(status_label)
        
        status = self.record.get('verification', '')
        status_badge = QLabel(status)
        status_badge.setStyleSheet(self._get_verification_style(status))
        status_layout.addWidget(status_badge)
        
        layout.addWidget(status_frame)
    
    def _setup_source_key_section(self, layout):
        """Set up source key section."""
        t = theme()
        
        key_frame = QFrame()
        key_frame.setStyleSheet(f"border-top: 1px solid {t.get('border')}; padding-top: 12px;")
        key_layout = QVBoxLayout(key_frame)
        key_layout.setContentsMargins(0, 12, 0, 0)
        
        key_label = QLabel("Source Key")
        key_label.setStyleSheet(f"font-size: {t.font_size('sm')}; color: {t.get('text_secondary')};")
        key_layout.addWidget(key_label)
        
        key_value = QLabel(self.record.get('sourceKey', ''))
        key_value.setStyleSheet(f"font-family: monospace; color: {t.get('text_secondary')};")
        key_layout.addWidget(key_value)
        
        layout.addWidget(key_frame)
    
    def _setup_profile_section(self, layout):
        """Set up species profile section."""
        t = theme()
        
        profile_frame = QFrame()
        profile_frame.setStyleSheet(f"border-top: 1px solid {t.get('border')}; padding-top: 12px;")
        profile_layout = QVBoxLayout(profile_frame)
        profile_layout.setContentsMargins(0, 12, 0, 0)
        
        profile_header = QHBoxLayout()
        profile_title = QLabel("SPECIES PROFILE")
        profile_title.setStyleSheet(f"font-size: {t.font_size('xs')}; font-weight: bold; color: {t.get('text_secondary')}; letter-spacing: 1px;")
        profile_header.addWidget(profile_title)
        profile_header.addStretch()
        
        profile_btn = QPushButton("+ Add" if not self.record.get('hasProfile') else "Edit")
        profile_btn.setStyleSheet(f"color: {t.get('primary')}; border: none; font-size: {t.font_size('sm')};")
        profile_btn.clicked.connect(lambda: self.profile_requested.emit(self.record))
        profile_header.addWidget(profile_btn)
        
        profile_layout.addLayout(profile_header)
        
        if self.record.get('hasProfile'):
            profile_text = QLabel(self.record.get('profileText', 'Profile notes would appear here...'))
            profile_text.setStyleSheet(f"background-color: {t.get('surface_alt')}; border-radius: {t.get('radius_sm')}; padding: 8px; color: {t.get('text_heading')};")
            profile_text.setWordWrap(True)
            profile_layout.addWidget(profile_text)
        else:
            no_profile = QLabel("No profile saved for this species.")
            no_profile.setStyleSheet(f"color: {t.get('text_muted')}; font-style: italic;")
            profile_layout.addWidget(no_profile)
        
        layout.addWidget(profile_frame)
    
    def _setup_action_buttons(self, layout):
        """Set up action buttons."""
        t = theme()
        
        btn_frame = QFrame()
        btn_frame.setStyleSheet(f"border-top: 1px solid {t.get('border')}; padding-top: 12px;")
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 12, 0, 0)
        
        edit_btn = QPushButton("Edit")
        edit_btn.setMinimumHeight(36)
        btn_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet(f"color: {t.get('error')}; border-color: {t.get('error')};")
        delete_btn.setMinimumHeight(36)
        btn_layout.addWidget(delete_btn)
        
        layout.addWidget(btn_frame)
    
    def _add_tax_field(self, grid, col: int, label: str, value: str):
        """Add taxonomy field to grid."""
        t = theme()
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-size: {t.font_size('sm')}; color: {t.get('text_muted')};")
        layout.addWidget(lbl)
        
        val = QLabel(value)
        val.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')};")
        layout.addWidget(val)
        
        grid.addWidget(container, 0, col)
    
    def _add_detail_field(self, grid, row: int, col: int, label: str, value: str, 
                          mono: bool = False, colspan: int = 1):
        """Add detail field to grid."""
        t = theme()
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-size: {t.font_size('sm')}; color: {t.get('text_secondary')};")
        layout.addWidget(lbl)
        
        val = QLabel(value)
        style = "font-weight: 600;"
        if mono:
            style += " font-family: monospace;"
        val.setStyleSheet(style)
        layout.addWidget(val)
        
        grid.addWidget(container, row, col, 1, colspan)
    
    def _get_source_style(self, source: str) -> str:
        t = theme()
        colors = {
            'iRecord': f'background-color: {t.get("info_bg")}; color: {t.get("info_text")};',
            'NBN': f'background-color: {t.get("info_bg")}; color: {t.get("info")};',
            'Email': f'background-color: {t.get("background")}; color: {t.get("text_secondary")};',
        }
        base = colors.get(source, colors['Email'])
        return f"{base} padding: 4px 8px; border-radius: {t.get('radius_sm')}; font-size: {t.font_size('sm')}; font-weight: 600;"
    
    def _get_verification_style(self, status: str) -> str:
        t = theme()
        colors = {
            'Accepted': f'background-color: {t.get("success_bg")}; color: {t.get("success_text")};',
            'Unconfirmed': f'background-color: {t.get("background")}; color: {t.get("text_secondary")};',
            'Pending': f'background-color: {t.get("warning_bg")}; color: {t.get("warning_text")};',
            'Rejected': f'background-color: {t.get("error_bg")}; color: {t.get("error")};',
        }
        base = colors.get(status, colors['Unconfirmed'])
        return f"{base} padding: 6px 12px; border-radius: {t.get('radius_sm')}; font-weight: 600;"


class SaveFilterDialog(QDialog):
    """Dialog for saving current filter configuration."""
    
    def __init__(self, current_filters: dict, parent=None):
        super().__init__(parent)
        self.current_filters = current_filters
        self.setWindowTitle("Save Filter")
        self.setFixedWidth(350)
        self.setModal(True)
        self._setup_ui()
    
    def _setup_ui(self):
        t = theme()
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Name input
        layout.addWidget(QLabel("Filter Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Oxfordshire records, Pending 2024...")
        self.name_input.setMinimumHeight(32)
        layout.addWidget(self.name_input)
        
        # Current filters display
        filters_frame = QFrame()
        filters_frame.setStyleSheet(f"background-color: {t.get('surface_alt')}; border-radius: {t.get('radius_md')}; padding: 12px;")
        filters_layout = QVBoxLayout(filters_frame)
        
        filters_header = QLabel("CURRENT FILTER SETTINGS")
        filters_header.setStyleSheet(f"font-size: {t.font_size('xs')}; font-weight: bold; color: {t.get('text_secondary')}; letter-spacing: 1px;")
        filters_layout.addWidget(filters_header)
        
        # Show active filters
        active_filters = []
        if self.current_filters.get('source') != 'all':
            active_filters.append(f"Source: {self.current_filters['source']}")
        if self.current_filters.get('species'):
            active_filters.append(f"Species: {self.current_filters['species']}")
        if self.current_filters.get('location'):
            active_filters.append(f"Location: {self.current_filters['location']}")
        if self.current_filters.get('date_from'):
            active_filters.append(f"Date From: {self.current_filters['date_from']}")
        if self.current_filters.get('date_to'):
            active_filters.append(f"Date To: {self.current_filters['date_to']}")
        if self.current_filters.get('subfamily'):
            active_filters.append(f"Subfamily: {self.current_filters['subfamily']}")
        if self.current_filters.get('vice_county'):
            active_filters.append(f"Vice County: {self.current_filters['vice_county']}")
        if self.current_filters.get('status'):
            active_filters.append(f"Status: {self.current_filters['status']}")
        
        if active_filters:
            for f in active_filters:
                lbl = QLabel(f)
                lbl.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('base')};")
                filters_layout.addWidget(lbl)
        else:
            no_filters = QLabel("No filters applied")
            no_filters.setStyleSheet(f"color: {t.get('text_muted')}; font-style: italic;")
            filters_layout.addWidget(no_filters)
        
        layout.addWidget(filters_frame)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save Filter")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('primary')};
                color: {t.get('primary_text')};
                border: none;
                border-radius: {t.get('radius_md')};
                padding: 10px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {t.get('primary_hover')}; }}
        """)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn, 1)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def get_filter_name(self) -> str:
        """Get entered filter name."""
        return self.name_input.text().strip()

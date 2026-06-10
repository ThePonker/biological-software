"""
Conservation Override Dialog.

Modal for adding/editing conservation status overrides.
Used in Settings tab.

Features:
- Species search
- GB Status dropdown
- Red List dropdown
- Legislative dropdown
- Source field
- Save/Cancel buttons
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QLineEdit, 
    QPushButton, QHBoxLayout
)
from PySide6.QtCore import Signal

from ...themes import theme


class ConservationOverrideDialog(QDialog):
    """
    Modal dialog for adding/editing conservation overrides.
    
    Signals:
        override_saved: Emitted when override is saved (override_data dict)
    """
    
    override_saved = Signal(dict)
    
    # Status options
    GB_STATUS_OPTIONS = [
        "", "Nationally Rare", "Nationally Scarce", "Notable", "Local", "Common"
    ]
    
    RED_LIST_OPTIONS = [
        "", "Extinct", "Critically Endangered", "Endangered", "Vulnerable",
        "Near Threatened", "Least Concern", "Data Deficient", "Not Evaluated"
    ]
    
    LEGISLATIVE_OPTIONS = [
        "", "Wildlife & Countryside Act", "Habitats Directive Annex II",
        "Habitats Directive Annex IV", "NERC Act S.41", "Bern Convention"
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._override_id = None
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        t = theme()
        
        self.setWindowTitle("Conservation Status Override")
        self.setMinimumWidth(450)
        
        layout = QVBoxLayout(self)
        
        # Form layout
        form = QFormLayout()
        
        # Species search
        self.species_input = QLineEdit()
        self.species_input.setPlaceholderText("Search species...")
        form.addRow("Species:", self.species_input)
        
        # GB Status
        self.gb_status = QComboBox()
        self.gb_status.addItems(self.GB_STATUS_OPTIONS)
        form.addRow("GB Status:", self.gb_status)
        
        # Red List
        self.red_list = QComboBox()
        self.red_list.addItems(self.RED_LIST_OPTIONS)
        form.addRow("Red List:", self.red_list)
        
        # Legislative
        self.legislative = QComboBox()
        self.legislative.addItems(self.LEGISLATIVE_OPTIONS)
        form.addRow("Legislative:", self.legislative)
        
        # Source
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("e.g., Red Data Book 2023")
        form.addRow("Source:", self.source_input)
        
        layout.addLayout(form)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('success')};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {t.get('success_hover')}; }}
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _on_save(self):
        """Handle save button click."""
        override_data = {
            'id': self._override_id,
            'species_name': self.species_input.text(),
            'gb_status': self.gb_status.currentText() or None,
            'red_list_status': self.red_list.currentText() or None,
            'legislative_status': self.legislative.currentText() or None,
            'source': self.source_input.text() or None,
        }
        self.override_saved.emit(override_data)
        self.accept()
    
    def set_override(self, override: dict):
        """Set existing override for editing."""
        self._override_id = override.get('id')
        self.species_input.setText(override.get('species_name', ''))
        
        # Set combo boxes
        gb = override.get('gb_status', '')
        if gb in self.GB_STATUS_OPTIONS:
            self.gb_status.setCurrentText(gb)
        
        rl = override.get('red_list_status', '')
        if rl in self.RED_LIST_OPTIONS:
            self.red_list.setCurrentText(rl)
        
        leg = override.get('legislative_status', '')
        if leg in self.LEGISLATIVE_OPTIONS:
            self.legislative.setCurrentText(leg)
        
        self.source_input.setText(override.get('source', ''))

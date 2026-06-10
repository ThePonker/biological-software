"""
Record Detail UI Mixin.

Extracted UI section builders for RecordDetailDialog.
"""

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QDateEdit, QComboBox, QSpinBox,
    QPushButton, QFrame, QCheckBox, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ...themes import theme


# Controlled value lists
SEX_OPTIONS = ["", "Female", "Male", "Mixed", "Not recorded"]
STAGE_OPTIONS = ["", "Adult", "Larva", "Pupa", "Egg", "Nymph", "Teneral", "Not recorded"]
from ...utils.constants import SAMPLE_METHOD_OPTIONS
VERIFICATION_OPTIONS = ["", "Pending", "Accepted", "Unconfirmed", "Rejected"]


class RecordDetailUIMixin:
    """Mixin providing UI section builders for RecordDetailDialog."""
    
    def _build_species_header(self, layout):
        """Build the species header section."""
        t = theme()
        
        species_frame = QFrame()
        species_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface_alt')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
        """)
        species_layout = QVBoxLayout(species_frame)
        species_layout.setSpacing(6)
        species_layout.setContentsMargins(12, 12, 12, 12)
        
        # Species name row
        species_row = QHBoxLayout()
        
        self.species_label = QLabel()
        font = QFont()
        font.setPointSize(14)
        font.setItalic(True)
        font.setBold(True)
        self.species_label.setFont(font)
        self.species_label.setStyleSheet(f"color: {t.get('text_primary')};")
        species_row.addWidget(self.species_label)
        
        species_row.addStretch()
        
        self.species_profile_btn = QPushButton("Species Profile →")
        self.species_profile_btn.setFlat(True)
        self.species_profile_btn.setStyleSheet(f"color: {t.get('success')}; font-size: {t.font_size('sm')};")
        species_row.addWidget(self.species_profile_btn)
        
        species_layout.addLayout(species_row)
        
        # Common name
        self.common_name_label = QLabel()
        self.common_name_label.setStyleSheet(f"color: {t.get('text_secondary')};")
        species_layout.addWidget(self.common_name_label)
        
        layout.addWidget(species_frame)
    
    def _build_species_edit_section(self, layout):
        """Build the species edit section (hidden by default)."""
        t = theme()
        
        self.species_edit_frame = QFrame()
        self.species_edit_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('error_bg')};
                border: 1px solid {t.get('error')};
                border-radius: {t.get('radius_md')};
            }}
        """)
        self.species_edit_frame.setVisible(False)
        
        edit_layout = QVBoxLayout(self.species_edit_frame)
        edit_layout.setContentsMargins(12, 10, 12, 10)
        edit_layout.setSpacing(8)
        
        self.allow_species_change = QCheckBox("Allow species change (for misidentification corrections)")
        self.allow_species_change.setStyleSheet(f"""
            QCheckBox {{
                color: {t.get('error')};
                font-size: {t.font_size('sm')};
                font-weight: bold;
            }}
        """)
        edit_layout.addWidget(self.allow_species_change)
        
        # Species edit field (hidden until checkbox checked)
        self.species_edit_container = QWidget()
        self.species_edit_container.setVisible(False)
        edit_field_layout = QHBoxLayout(self.species_edit_container)
        edit_field_layout.setContentsMargins(0, 0, 0, 0)
        
        new_species_label = QLabel("New species:")
        new_species_label.setStyleSheet(f"color: {t.get('error')}; font-weight: bold;")
        edit_field_layout.addWidget(new_species_label)
        
        self.species_edit = QLineEdit()
        self.species_edit.setPlaceholderText("Enter correct species name...")
        self.species_edit.setStyleSheet("font-style: italic;")
        edit_field_layout.addWidget(self.species_edit, stretch=1)
        
        edit_layout.addWidget(self.species_edit_container)
        
        layout.addWidget(self.species_edit_frame)
    
    def _build_taxonomy_row(self, layout):
        """Build the taxonomy display row."""
        t = theme()
        
        taxonomy_layout = QHBoxLayout()
        taxonomy_layout.setSpacing(24)
        
        for label_text, attr_name in [("Class", "class_value"), ("Order", "order_value"), ("Family", "family_value")]:
            box = QVBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color: {t.get('text_muted')}; font-size: {t.font_size('xs')};")
            box.addWidget(lbl)
            value_lbl = QLabel("-")
            value_lbl.setStyleSheet(f"color: {t.get('text_heading')}; font-weight: bold;")
            setattr(self, attr_name, value_lbl)
            box.addWidget(value_lbl)
            taxonomy_layout.addLayout(box)
        
        taxonomy_layout.addStretch()
        layout.addLayout(taxonomy_layout)
    
    def _build_collection_status(self, layout):
        """Build the collection status section."""
        t = theme()
        
        self.collection_frame = QFrame()
        self.collection_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('warning_bg')};
                border: 1px solid {t.get('warning')};
                border-radius: {t.get('radius_md')};
                padding: 8px;
            }}
        """)
        collection_layout = QHBoxLayout(self.collection_frame)
        collection_layout.setContentsMargins(8, 6, 8, 6)
        
        self.collection_icon = QLabel("!")
        self.collection_icon.setStyleSheet(f"color: {t.get('warning')}; font-weight: bold; font-size: {t.font_size('xl')};")
        self.collection_icon.setFixedWidth(24)
        collection_layout.addWidget(self.collection_icon)
        
        self.collection_text = QLabel("Not in Collection")
        self.collection_text.setStyleSheet(f"color: {t.get('warning_text')}; font-weight: bold;")
        collection_layout.addWidget(self.collection_text, stretch=1)
        
        layout.addWidget(self.collection_frame)
    
    def _build_details_grid(self, layout):
        """Build the details input grid."""
        t = theme()
        
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)
        
        row = 0
        
        # Date | Grid Ref
        grid.addWidget(self._label("Date"), row, 0)
        grid.addWidget(self._label("Grid Ref"), row, 1)
        row += 1
        
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.calendarWidget().setMinimumWidth(280)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setMinimumHeight(28)
        grid.addWidget(self.date_edit, row, 0)
        
        self.grid_ref_edit = QLineEdit()
        self.grid_ref_edit.setPlaceholderText("e.g. SP580207")
        self.grid_ref_edit.setMinimumHeight(28)
        grid.addWidget(self.grid_ref_edit, row, 1)
        row += 1
        
        # Location
        grid.addWidget(self._label("Location"), row, 0, 1, 2)
        row += 1
        self.location_edit = QLineEdit()
        self.location_edit.setMinimumHeight(28)
        grid.addWidget(self.location_edit, row, 0, 1, 2)
        row += 1
        
        # VC | Qty
        grid.addWidget(self._label("Vice County"), row, 0)
        grid.addWidget(self._label("Quantity"), row, 1)
        row += 1
        
        self.vc_label = QLabel("-")
        self.vc_label.setStyleSheet("font-weight: bold;")
        self.vc_label.setMinimumHeight(28)
        grid.addWidget(self.vc_label, row, 0)
        
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 9999)
        self.quantity_spin.setMinimumHeight(28)
        grid.addWidget(self.quantity_spin, row, 1)
        row += 1
        
        # Sex | Stage
        grid.addWidget(self._label("Sex"), row, 0)
        grid.addWidget(self._label("Stage"), row, 1)
        row += 1
        
        self.sex_combo = QComboBox()
        self.sex_combo.addItems(SEX_OPTIONS)
        self.sex_combo.setMinimumHeight(28)
        grid.addWidget(self.sex_combo, row, 0)
        
        self.stage_combo = QComboBox()
        self.stage_combo.addItems(STAGE_OPTIONS)
        self.stage_combo.setMinimumHeight(28)
        grid.addWidget(self.stage_combo, row, 1)
        row += 1
        
        # Recorder | Determiner
        grid.addWidget(self._label("Recorder"), row, 0)
        grid.addWidget(self._label("Determiner"), row, 1)
        row += 1
        
        self.recorder_edit = QLineEdit()
        self.recorder_edit.setMinimumHeight(28)
        grid.addWidget(self.recorder_edit, row, 0)
        
        self.determiner_edit = QLineEdit()
        self.determiner_edit.setMinimumHeight(28)
        grid.addWidget(self.determiner_edit, row, 1)
        row += 1
        
        # Method | Type
        grid.addWidget(self._label("Method"), row, 0)
        grid.addWidget(self._label("Type"), row, 1)
        row += 1
        
        self.method_combo = QComboBox()
        self.method_combo.addItems(SAMPLE_METHOD_OPTIONS)
        self.method_combo.setMinimumHeight(28)
        grid.addWidget(self.method_combo, row, 0)
        
        
        layout.addLayout(grid)
    
    def _build_verification_section(self, layout):
        """Build the verification status section."""
        t = theme()
        
        verif_layout = QHBoxLayout()
        verif_layout.addWidget(self._label("Verification Status"))
        verif_layout.addStretch()
        
        self.verification_badge = QLabel()
        self.verification_badge.setMinimumHeight(28)
        verif_layout.addWidget(self.verification_badge)
        
        self.verification_combo = QComboBox()
        self.verification_combo.addItems(VERIFICATION_OPTIONS)
        self.verification_combo.setMinimumHeight(28)
        self.verification_combo.setMinimumWidth(120)
        self.verification_combo.setVisible(False)
        verif_layout.addWidget(self.verification_combo)
        
        layout.addLayout(verif_layout)
    
    def _build_irecord_section(self, layout):
        """Build the iRecord key section."""
        t = theme()
        
        self.irecord_widget = QWidget()
        irecord_layout = QHBoxLayout(self.irecord_widget)
        irecord_layout.setContentsMargins(0, 0, 0, 0)
        irecord_layout.addWidget(QLabel("iRecord Key:"))
        self.irecord_value = QLabel("-")
        self.irecord_value.setStyleSheet(f"font-family: monospace; color: {t.get('text_secondary')};")
        irecord_layout.addWidget(self.irecord_value)
        irecord_layout.addStretch()
        self.irecord_widget.setVisible(False)
        layout.addWidget(self.irecord_widget)
    
    def _build_action_buttons(self, layout):
        """Build the action buttons section."""
        t = theme()
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {t.get('border')};")
        layout.addWidget(sep)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet(f"color: {t.get('error')};")
        btn_layout.addWidget(self.delete_btn)
        
        btn_layout.addStretch()
        
        self.edit_btn = QPushButton("Edit")
        btn_layout.addWidget(self.edit_btn)
        
        self.cancel_btn = QPushButton("Close")
        btn_layout.addWidget(self.cancel_btn)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.setStyleSheet(f"background-color: {t.get('success')}; color: {t.get('primary_text')}; padding: 6px 16px;")
        self.save_btn.setVisible(False)
        btn_layout.addWidget(self.save_btn)
        
        layout.addLayout(btn_layout)
    
    def _label(self, text: str) -> QLabel:
        """Create a styled label."""
        t = theme()
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: {t.font_size('sm')}; color: {t.get('text_secondary')};")
        return lbl
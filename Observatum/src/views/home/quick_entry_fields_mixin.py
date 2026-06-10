"""
Quick Entry Fields Mixin.

Extracted field creation methods for QuickEntryForm.
"""

from PySide6.QtWidgets import (
    QWidget, QLineEdit, QDateEdit, QComboBox, QCheckBox,
    QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton
)
from PySide6.QtCore import QDate, QSettings

from ..components.species_search import SpeciesSearch
from ..components.filter_styles import get_clear_button_style
from .quantity_spinner import QuantitySpinner
from ...themes import theme


# Controlled value lists
SEX_OPTIONS = ["", "Female", "Male", "Mixed", "Not recorded"]
# STAGE_OPTIONS imported from constants below
CERTAINTY_OPTIONS = ["", "Certain", "Likely", "Uncertain"]
from ...utils.constants import SAMPLE_METHOD_OPTIONS, STAGE_OPTIONS


class QuickEntryFieldsMixin:
    """Mixin providing field creation methods for QuickEntryForm."""
    
    def _create_species_field(self) -> QWidget:
        """Create species search field."""
        self.species_search = SpeciesSearch()
        self.species_search.species_selected.connect(self._on_species_selected)
        return self.species_search
    
    def _create_date_field(self) -> QWidget:
        """Create date field."""
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.calendarWidget().setMinimumWidth(280)
        
        settings = QSettings()
        date_fmt = settings.value("general/date_format", "dd/MM/yyyy")
        qt_format = date_fmt.replace("mm", "MM")
        self.date_edit.setDisplayFormat(qt_format)
        self.date_edit.setMinimumHeight(32)
        
        return self.date_edit
    
    def _create_grid_ref_field(self) -> QWidget:
        """Create grid reference field."""
        self.grid_ref_edit = QLineEdit()
        self.grid_ref_edit.setPlaceholderText("e.g. SP580207")
        self.grid_ref_edit.setMinimumHeight(32)
        return self.grid_ref_edit
    
    def _create_location_field(self) -> QWidget:
        """Create location field."""
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("Site name")
        self.location_edit.setMinimumHeight(32)
        return self.location_edit
    
    def _create_recorder_field(self) -> QWidget:
        """Create recorder field."""
        self.recorder_edit = QLineEdit()
        self.recorder_edit.setPlaceholderText("Recorder name")
        self.recorder_edit.setMinimumHeight(32)
        return self.recorder_edit
    
    def _create_determiner_field(self) -> QWidget:
        """Create determiner field."""
        self.determiner_edit = QLineEdit()
        self.determiner_edit.setPlaceholderText("Determiner name")
        self.determiner_edit.setMinimumHeight(32)
        return self.determiner_edit
    
    def _create_sex_field(self) -> QWidget:
        """Create sex dropdown."""
        self.sex_combo = QComboBox()
        self.sex_combo.addItems(SEX_OPTIONS)
        self.sex_combo.setMinimumHeight(32)
        return self.sex_combo
    
    def _create_stage_field(self) -> QWidget:
        """Create stage dropdown."""
        self.stage_combo = QComboBox()
        self.stage_combo.addItems(STAGE_OPTIONS)
        self.stage_combo.setMinimumHeight(32)
        return self.stage_combo
    
    def _create_quantity_field(self) -> QWidget:
        """Create quantity spinner with themed +/- buttons."""
        self.quantity_spin = QuantitySpinner()
        self.quantity_spin.setMinimum(1)
        self.quantity_spin.setMaximum(9999)
        self.quantity_spin.setValue(1)
        return self.quantity_spin
    
    def _create_certainty_field(self) -> QWidget:
        """Create certainty dropdown."""
        self.certainty_combo = QComboBox()
        self.certainty_combo.addItems(CERTAINTY_OPTIONS)
        self.certainty_combo.setMinimumHeight(32)
        return self.certainty_combo
    
    def _create_method_field(self) -> QWidget:
        """Create method dropdown."""
        self.method_combo = QComboBox()
        self.method_combo.addItems(SAMPLE_METHOD_OPTIONS)
        self.method_combo.setMinimumHeight(32)
        return self.method_combo
    
    def _create_comment_field(self) -> QWidget:
        """Create comment field."""
        self.comment_edit = QLineEdit()
        self.comment_edit.setPlaceholderText("Optional notes...")
        self.comment_edit.setMinimumHeight(32)
        return self.comment_edit

    def _create_record_type_field(self) -> QWidget:
        """Create record type (Personal/Commercial) dropdown."""
        self.record_type_combo = QComboBox()
        self.record_type_combo.addItems(['Personal', 'Commercial'])
        self.record_type_combo.setMinimumHeight(32)
        return self.record_type_combo

    def _create_never_upload_field(self) -> QWidget:
        """Create 'Never upload to iRecord' checkbox."""
        t = theme()
        self.never_upload_check = QCheckBox("Never upload to iRecord")
        self.never_upload_check.setStyleSheet(f"""
            QCheckBox {{
                color: {t.get('text_secondary')};
                font-size: {t.font_size('sm')};
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
        """)
        return self.never_upload_check

    def _setup_buttons(self):
        """Set up action buttons."""
        t = theme()
        
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {t.get('border')};")
        self.add_widget(sep)
        
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 8, 0, 0)
        button_layout.setSpacing(8)
        button_layout.addStretch()
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setMinimumHeight(32)
        self.clear_btn.setStyleSheet(get_clear_button_style())
        self.clear_btn.clicked.connect(self.clear_form)
        button_layout.addWidget(self.clear_btn)
        
        self.save_btn = QPushButton("Save Record")
        self.save_btn.setMinimumHeight(32)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('success')};
                color: white;
                padding: 6px 20px;
                border: none;
                border-radius: {t.get('radius_md')};
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {t.get('success_light')}; }}
        """)
        self.save_btn.clicked.connect(self._on_save_clicked)
        button_layout.addWidget(self.save_btn)
        
        self.add_layout(button_layout)
    
    def _setup_reference_boxes(self):
        """Add static reference boxes showing dropdown options."""
        t = theme()
        
        ref_container = QFrame()
        ref_container.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface_alt')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_md')};
            }}
        """)
        
        ref_layout = QVBoxLayout(ref_container)
        ref_layout.setContentsMargins(12, 10, 12, 10)
        ref_layout.setSpacing(6)
        
        title = QLabel("Dropdown Options Reference")
        title.setStyleSheet(f"font-size: {t.font_size('sm')}; font-weight: 600; color: {t.get('text_primary')}; background: transparent; border: none;")
        ref_layout.addWidget(title)
        
        label_style = f"font-size: {t.font_size('xs')}; color: {t.get('text_secondary')}; background: transparent; border: none;"
        label_style = f"font-size: {t.font_size('xs')}; color: {t.get('text_secondary')}; background: transparent; border: none;"
        
        method_text = ", ".join([m for m in SAMPLE_METHOD_OPTIONS if m])
        method_label = QLabel(f"<b>Method:</b> {method_text}")
        method_label.setWordWrap(True)
        method_label.setStyleSheet(label_style)
        ref_layout.addWidget(method_label)
        
        
        stage_text = ", ".join([s for s in STAGE_OPTIONS if s])
        stage_label = QLabel(f"<b>Stage:</b> {stage_text}")
        stage_label.setWordWrap(True)
        stage_label.setStyleSheet(label_style)
        ref_layout.addWidget(stage_label)
        
        self.add_widget(ref_container)

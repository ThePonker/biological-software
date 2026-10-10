"""
Edit Observation Dialog.

Modal dialog for editing an observation record that hasn't been
uploaded to iRecord yet. Based on the AddSpecimenDialog pattern.
"""

from typing import Dict, Any
from src.utils.date_utils import format_date_display, parse_display_date, get_user_date_format
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QLineEdit, QTextEdit, QPushButton, QScrollArea, QWidget, QMessageBox
)
from PySide6.QtCore import Qt
from ..components.species_search import SpeciesSearch

from ...themes import theme
from ...core.config import TabColors, ButtonColors


class EditObservationDialog(QDialog):
    """Modal dialog for editing a local observation."""

    def __init__(self, parent=None, uksi_model=None, vc_service=None,
                 observation: Dict[str, Any] = None, db=None,
                 require_date_and_grid: bool = True):
        super().__init__(parent)
        # False for scheme records, many of which have no date or grid ref (OBS-04)
        self._require_date_and_grid = require_date_and_grid
        self._uksi_model = uksi_model
        self._vc_service = vc_service
        self._observation = observation or {}
        self._db = db
        self._selected_species = None

        self._accent = TabColors.PERSONAL
        self._accent_light = TabColors.PERSONAL_LIGHT

        self.setWindowTitle("Edit Observation")
        self.setMinimumSize(520, 620)
        self.setModal(True)
        self._setup_ui()

        if observation:
            self._populate(observation)

    def _setup_ui(self):
        t = theme()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 8)

        # Species search
        species_group = QVBoxLayout()
        species_label = QLabel("Species *")
        species_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
        species_group.addWidget(species_label)

        self.species_search = SpeciesSearch()
        self.species_search.species_selected.connect(self._on_species_selected)
        species_group.addWidget(self.species_search)

        self.species_info_label = QLabel()
        self.species_info_label.setStyleSheet(f"font-size: 12px; color: {self._accent}; font-style: italic;")
        self.species_info_label.hide()
        species_group.addWidget(self.species_info_label)
        layout.addLayout(species_group)

        # Date
        date_hint = get_user_date_format().replace('%d', 'DD').replace('%m', 'MM').replace('%Y', 'YYYY').replace('%y', 'YY')
        self._add_field(layout, "Date *", "date_edit", date_hint)

        # Site Name
        self._add_field(layout, "Site Name *", "site_edit", "e.g. Bernwood Forest")

        # Grid Reference
        self._add_field(layout, "Grid Reference *", "gridref_edit", "e.g. SP580207")

        # VC feedback
        self.vc_label = QLabel()
        self.vc_label.setStyleSheet(f"font-size: 11px; color: {t.get('text_muted')}; padding-left: 4px;")
        layout.addWidget(self.vc_label)

        # Recorder
        self._add_field(layout, "Recorder", "recorder_edit", "")

        # Determiner
        self._add_field(layout, "Determiner", "determiner_edit", "")

        # Comment
        notes_group = QVBoxLayout()
        notes_label = QLabel("Comment")
        notes_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
        notes_group.addWidget(notes_label)

        self.comment_edit = QTextEdit()
        self.comment_edit.setPlaceholderText("Notes about this observation...")
        self.comment_edit.setMaximumHeight(80)
        self.comment_edit.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
                padding: 8px;
                font-size: 13px;
            }}
            QTextEdit:focus {{
                border-color: {self._accent};
            }}
        """)
        notes_group.addWidget(self.comment_edit)
        layout.addLayout(notes_group)

        layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

        # Buttons
        btn_frame = QFrame()
        btn_frame.setStyleSheet(f"background-color: {t.get('surface')}; border-top: 1px solid {t.get('border')};")
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(16, 12, 16, 12)

        save_btn = QPushButton("Save Changes")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ButtonColors.PRIMARY};
                color: white;
                border: none;
                border-radius: {t.get('radius_md')};
                padding: 12px 24px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {ButtonColors.PRIMARY_HOVER}; }}
        """)
        save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(save_btn, 1)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid {ButtonColors.SECONDARY};
                color: {ButtonColors.SECONDARY};
                border-radius: {t.get('radius_md')};
                padding: 12px 24px;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {t.get('hover')}; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        main_layout.addWidget(btn_frame)

        # Connect grid ref validation
        self.gridref_edit.editingFinished.connect(self._validate_grid_ref)

    def _add_field(self, layout, label_text, attr_name, placeholder):
        t = theme()
        group = QVBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
        group.addWidget(label)

        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setMinimumHeight(36)
        edit.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
                padding: 8px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {self._accent};
            }}
        """)
        group.addWidget(edit)
        setattr(self, attr_name, edit)
        layout.addLayout(group)

    def _on_species_selected(self, species_data: dict):
        self._selected_species = species_data
        info_parts = []
        if species_data.get('order'):
            info_parts.append(species_data['order'])
        if species_data.get('family'):
            info_parts.append(species_data['family'])
        info = " - ".join(info_parts)
        if species_data.get('common_name'):
            info += f" - {species_data['common_name']}"
        if info:
            self.species_info_label.setText(info)
            self.species_info_label.show()

    def _validate_grid_ref(self):
        grid_ref = self.gridref_edit.text().strip().upper()
        if not grid_ref or not self._vc_service:
            self.vc_label.setText("")
            return
        try:
            vc_info = self._vc_service.get_vice_county(grid_ref)
            if vc_info:
                self.vc_label.setText(f"VC{vc_info.get('number', '?')}: {vc_info.get('name', 'Unknown')}")
            else:
                self.vc_label.setText("")
        except:
            self.vc_label.setText("")

    def _populate(self, obs):
        species_data = {
            'scientific_name': obs.get('species_name', ''),
            'tvk': obs.get('species_tvk', ''),
            'common_name': obs.get('common_name', ''),
            'family': obs.get('family', ''),
            'order': obs.get('order_name', obs.get('order', ''))
        }
        self.species_search.set_species(species_data)
        self._selected_species = species_data

        raw_date = obs.get('date', '')
        if raw_date:
            self.date_edit.setText(format_date_display(raw_date, 'user'))
        else:
            self.date_edit.setText('')

        self.site_edit.setText(obs.get('site_name', obs.get('location', '')))
        self.gridref_edit.setText(obs.get('grid_ref', ''))
        self.recorder_edit.setText(obs.get('recorder', ''))
        self.determiner_edit.setText(obs.get('determiner', ''))
        self.comment_edit.setText(obs.get('comment', obs.get('notes', '')))

        # Show species info
        info_parts = []
        if obs.get('order_name') or obs.get('order'):
            info_parts.append(obs.get('order_name') or obs.get('order'))
        if obs.get('family'):
            info_parts.append(obs['family'])
        info = " - ".join(info_parts)
        if obs.get('common_name'):
            info += f" - {obs['common_name']}"
        if info:
            self.species_info_label.setText(info)
            self.species_info_label.show()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._on_save()
                return
            if hasattr(self, 'species_search') and hasattr(self.species_search, '_popup'):
                if self.species_search._popup.isVisible():
                    return
            return
        super().keyPressEvent(event)

    def _on_save(self):
        if not self._selected_species:
            QMessageBox.warning(self, "Missing Species",
                "Please select a species from the search results.")
            self.species_search.search_input.setFocus()
            return
        if self._require_date_and_grid and not self.date_edit.text().strip():
            QMessageBox.warning(self, "Missing Date", "Please enter a date.")
            self.date_edit.setFocus()
            return
        if self._require_date_and_grid and not self.gridref_edit.text().strip():
            QMessageBox.warning(self, "Missing Grid Ref", "Please enter a grid reference.")
            self.gridref_edit.setFocus()
            return
        self.accept()

    def get_observation_data(self) -> Dict[str, Any]:
        """Get the edited observation data."""
        date_text = self.date_edit.text().strip()
        iso_date = parse_display_date(date_text)

        data = {
            'species_name': self._selected_species.get('scientific_name', '') if self._selected_species else '',
            'date': iso_date if iso_date else date_text,
            'site_name': self.site_edit.text().strip(),
            'grid_ref': self.gridref_edit.text().strip().upper(),
            'recorder': self.recorder_edit.text().strip(),
            'determiner': self.determiner_edit.text().strip(),
            'comment': self.comment_edit.toPlainText().strip(),
        }

        if self._selected_species:
            data['species_tvk'] = self._selected_species.get('tvk')
            data['common_name'] = self._selected_species.get('common_name')
            data['family'] = self._selected_species.get('family')
            data['order_name'] = self._selected_species.get('order')

        if self._vc_service and data['grid_ref']:
            try:
                vc_info = self._vc_service.get_vice_county(data['grid_ref'])
                if vc_info:
                    data['vice_county'] = vc_info.get('name')
                    data['vc_number'] = vc_info.get('number')
            except Exception:
                pass

        return data

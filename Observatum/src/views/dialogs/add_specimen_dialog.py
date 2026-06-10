"""
Add Specimen Dialog.

Modal dialog for adding or editing a specimen in the collection.
Includes species autocomplete from UKSI and grid ref validation.
"""

from typing import Optional, Dict, Any
from src.utils.date_utils import format_date_display, parse_display_date, get_user_date_format
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QLineEdit, QTextEdit, QPushButton, QCompleter, QComboBox,
    QScrollArea, QWidget, QMessageBox
)
from PySide6.QtCore import Qt, QStringListModel, Signal
from ..components.species_search import SpeciesSearch

from ...themes import theme
from ...core.config import TabColors, ButtonColors


class AddSpecimenDialog(QDialog):
    """Modal dialog for adding or editing a specimen."""
    
    # Signal emitted when user wants to edit species profile
    profile_edit_requested = Signal(str, str)  # species_name, species_tvk
    
    def __init__(
        self,
        parent=None,
        uksi_model=None,
        vc_service=None,
        existing_specimen: Optional[Dict[str, Any]] = None,
        db=None
    ):
        """
        Initialize the dialog.
        
        Args:
            parent: Parent widget
            uksi_model: UKSIModel for species lookup (optional)
            vc_service: VCLookupService for grid ref validation (optional)
            existing_specimen: Existing specimen data for edit mode (optional)
            db: Database manager for profile lookup (optional)
        """
        super().__init__(parent)
        
        self._uksi_model = uksi_model
        self._vc_service = vc_service
        self._existing_specimen = existing_specimen
        self._db = db
        self._selected_species = None  # Store selected UKSI species info
        self._profile_text = None  # Store loaded profile text
        
        # Tab colors
        self._accent = TabColors.COLLECTION
        self._accent_light = TabColors.COLLECTION_LIGHT
        self._accent_dark = TabColors.COLLECTION_DARK
        
        # Set title based on mode
        if existing_specimen:
            self.setWindowTitle("Edit Specimen")
        else:
            self.setWindowTitle("Add Specimen")
        
        self.setMinimumSize(520, 780)
        self.setModal(True)
        self._setup_ui()
        self._setup_autocomplete()
        self._connect_signals()
        
        # Populate fields if editing
        if existing_specimen:
            self._populate_from_existing(existing_specimen)
    
    def _setup_ui(self):
        """Set up the user interface."""
        t = theme()
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Scrollable content area
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
        self.species_search.species_selected.connect(self._on_species_selected_from_search)
        species_group.addWidget(self.species_search)

        # Species info (auto-populated)
        self.species_info_label = QLabel()
        self.species_info_label.setStyleSheet(f"font-size: 12px; color: {self._accent}; font-style: italic;")
        self.species_info_label.hide()
        species_group.addWidget(self.species_info_label)
        
        layout.addLayout(species_group)
        
        # Auto-populated note
        auto_note1 = QFrame()
        auto_note1.setStyleSheet(f"background-color: {t.get('surface_alt')}; border-radius: {t.get('radius_md')};")
        auto_layout1 = QVBoxLayout(auto_note1)
        auto_layout1.setContentsMargins(10, 8, 10, 8)
        auto_header1 = QLabel("<b>Auto-populated from UKSI:</b>")
        auto_header1.setStyleSheet(f"font-size: 11px; color: {t.get('text_secondary')};")
        auto_layout1.addWidget(auto_header1)
        auto_fields1 = QLabel("Order, Family, Common Name")
        auto_fields1.setStyleSheet(f"font-size: 11px; color: {t.get('text_muted')};")
        auto_layout1.addWidget(auto_fields1)
        layout.addWidget(auto_note1)
        
        # Date Collected - use dynamic placeholder from settings
        date_hint = get_user_date_format().replace('%d', 'DD').replace('%m', 'MM').replace('%Y', 'YYYY').replace('%y', 'YY')
        self._add_form_field(layout, "Date Collected *", "date_edit", date_hint)
        
        # Location / Site Name
        self._add_form_field(layout, "Location / Site Name *", "location_edit", "e.g. Bernwood Forest")
        
        # Local Site Name (protected during sync)
        self._add_form_field(layout, "Local Site Name", "site_local_edit", "Your local name for this site (optional)")
        
        # Grid Reference
        grid_group = QVBoxLayout()
        grid_label = QLabel("Grid Reference *")
        grid_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
        grid_group.addWidget(grid_label)
        
        self.gridref_edit = QLineEdit()
        self.gridref_edit.setPlaceholderText("e.g. SP580207")
        self.gridref_edit.setMinimumHeight(36)
        self.gridref_edit.setStyleSheet(f"""
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
        grid_group.addWidget(self.gridref_edit)
        
        # Grid ref validation feedback
        self.gridref_feedback = QLabel()
        self.gridref_feedback.setStyleSheet("font-size: 11px;")
        self.gridref_feedback.hide()
        grid_group.addWidget(self.gridref_feedback)
        
        layout.addLayout(grid_group)
        
        # Auto-calculated note
        auto_note2 = QFrame()
        auto_note2.setStyleSheet(f"background-color: {t.get('surface_alt')}; border-radius: {t.get('radius_md')};")
        auto_layout2 = QVBoxLayout(auto_note2)
        auto_layout2.setContentsMargins(10, 8, 10, 8)
        auto_header2 = QLabel("<b>Auto-calculated from Grid Ref:</b>")
        auto_header2.setStyleSheet(f"font-size: 11px; color: {t.get('text_secondary')};")
        auto_layout2.addWidget(auto_header2)
        self.vc_info_label = QLabel("Vice County")
        self.vc_info_label.setStyleSheet(f"font-size: 11px; color: {t.get('text_muted')};")
        auto_layout2.addWidget(self.vc_info_label)
        layout.addWidget(auto_note2)
        
        # Sex
        sex_group = QVBoxLayout()
        sex_label = QLabel("Sex")
        sex_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
        sex_group.addWidget(sex_label)
        
        self.sex_combo = QComboBox()
        self.sex_combo.addItems(["", "Male", "Female", "Unknown"])
        self.sex_combo.setMinimumHeight(36)
        self.sex_combo.setStyleSheet(f"""
            QComboBox {{
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
                padding: 8px;
                font-size: 13px;
            }}
        """)
        sex_group.addWidget(self.sex_combo)
        layout.addLayout(sex_group)
        
        # Collector
        self._add_form_field(layout, "Collector", "collector_edit", "", "")
        
        # Determiner
        self._add_form_field(layout, "Determiner", "determiner_edit", "", "")
        
        # Specimen Notes (specific to this specimen)
        notes_group = QVBoxLayout()
        notes_label = QLabel("Specimen Notes")
        notes_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
        notes_group.addWidget(notes_label)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Notes specific to this specimen (condition, label info, etc.)...")
        self.notes_edit.setMaximumHeight(70)
        self.notes_edit.setStyleSheet(f"""
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
        notes_group.addWidget(self.notes_edit)
        layout.addLayout(notes_group)
        
        # Species Profile Section
        self._add_profile_section(layout)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)
        
        # Buttons (fixed at bottom)
        btn_frame = QFrame()
        btn_frame.setStyleSheet(f"background-color: {t.get('surface')}; border-top: 1px solid {t.get('border')};")
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(16, 12, 16, 12)
        
        # Save button (Moss Green - primary action)
        save_btn = QPushButton("Save Specimen")
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
        
        # Cancel button (Warm Gray outlined)
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
    
    def _add_form_field(self, layout, label_text: str, attr_name: str,
                        placeholder: str = "", default: str = ""):
        """Add a form field to the layout."""
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
        if default:
            edit.setText(default)
        group.addWidget(edit)
        
        setattr(self, attr_name, edit)
        layout.addLayout(group)
    
    def _add_profile_section(self, layout):
        """Add species profile section."""
        t = theme()
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {t.get('separator')};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        layout.addSpacing(8)
        
        # Header with link
        header_row = QHBoxLayout()
        
        profile_header = QLabel("Species Profile")
        profile_header.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
        header_row.addWidget(profile_header)
        
        header_row.addStretch()
        
        # Profile link uses tab accent color
        self.profile_link = QPushButton("Create Profile")
        self.profile_link.setStyleSheet(f"""
            QPushButton {{
                border: none;
                background: transparent;
                color: {self._accent};
                font-size: 11px;
                padding: 0;
            }}
            QPushButton:hover {{
                color: {self._accent_dark};
            }}
        """)
        self.profile_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.profile_link.clicked.connect(self._on_profile_link_clicked)
        header_row.addWidget(self.profile_link)
        
        layout.addLayout(header_row)
        
        # Profile content (read-only display)
        self.profile_display = QLabel("No profile for this species yet.")
        self.profile_display.setWordWrap(True)
        self.profile_display.setStyleSheet(f"""
            color: {t.get('text_muted')};
            font-size: 12px;
            font-style: italic;
            padding: 8px 0;
        """)
        layout.addWidget(self.profile_display)
    
    def _setup_autocomplete(self):
        """Set up species autocomplete if UKSI model available."""
        if not self._uksi_model:
            return
        
        # We'll do live search on text change instead of using static completer
        # Species search component handles text change internally
    
    def _on_species_selected_from_search(self, species_data: dict):
        """Handle species selection from SpeciesSearch component."""
        self._selected_species = species_data
        
        # Show taxonomic info
        info_parts = []
        if species_data.get('order'):
            info_parts.append(species_data['order'])
        if species_data.get('family'):
            info_parts.append(species_data['family'])
        info_display = " - ".join(info_parts)
        if species_data.get('common_name'):
            info_display += f" - {species_data['common_name']}"
        if info_display:
            self.species_info_label.setText(info_display)
            self.species_info_label.show()
        
        # Load profile
        self._load_species_profile(
            species_data.get('scientific_name', ''),
            species_data.get('tvk')
        )

    def _connect_signals(self):
        """Connect widget signals."""
        # Validate grid ref on change
        self.gridref_edit.editingFinished.connect(self._validate_grid_ref)
    
    def _on_species_text_changed(self, text: str):
        """Handle species search as user types."""
        if not self._uksi_model or len(text) < 2:
            self.species_info_label.hide()
            return
        
        # Search UKSI
        try:
            results = self._uksi_model.search_species(text, limit=1)
            if results:
                result = results[0]
                self._selected_species = result
                info_parts = []
                if result.order_name:
                    info_parts.append(result.order_name)
                if result.family:
                    info_parts.append(result.family)
                display = " · ".join(info_parts)
                if result.common_name:
                    display += f" – {result.common_name}"
                if display:
                    self.species_info_label.setText(display)
                    self.species_info_label.show()
                
                # Update profile section for new species
                self._load_species_profile(result.name if hasattr(result, 'name') else text, 
                                          result.tvk if hasattr(result, 'tvk') else None)
            else:
                self._selected_species = None
                self.species_info_label.hide()
                self._update_profile_display(None)
        except Exception as e:
            print(f"[AddSpecimenDialog] Species search error: {e}")

    def _on_species_selected(self, text: str):
        """Handle selection from autocomplete dropdown."""
        if text in self._species_results:
            result = self._species_results[text]
            self._selected_species = result
            
            # Update the edit field with just scientific name
            scientific_name = result.scientific_name or result.name
            # SpeciesSearch handles display
            pass  # handled by component
            # end of species display handling
            
            # Show taxonomic info
            info_parts = []
            if result.order_name:
                info_parts.append(result.order_name)
            if result.family:
                info_parts.append(result.family)
            info_display = " - ".join(info_parts)
            if result.common_name:
                info_display += f" - {result.common_name}"
            if info_display:
                self.species_info_label.setText(info_display)
                self.species_info_label.show()
            
            # Load profile for selected species
            self._load_species_profile(scientific_name, result.tvk if hasattr(result, 'tvk') else None)
    
    def _load_species_profile(self, species_name: str, species_tvk: str = None):
        """Load species profile from database."""
        if not self._db:
            # Try to get database from parent or import
            try:
                from ...models.database import get_database
                self._db = get_database()
            except:
                pass
        
        if not self._db:
            self._update_profile_display(None)
            return
        
        try:
            # Try by TVK first, then by name
            profile_text = None
            
            if species_tvk:
                result = self._db.execute_main(
                    "SELECT profile_text FROM species_profiles WHERE species_tvk = ?",
                    (species_tvk,)
                )
                if result and result[0][0]:
                    profile_text = result[0][0]
            
            if not profile_text and species_name:
                result = self._db.execute_main(
                    "SELECT profile_text FROM species_profiles WHERE species_name = ?",
                    (species_name,)
                )
                if result and result[0][0]:
                    profile_text = result[0][0]
            
            self._update_profile_display(profile_text)
            
        except Exception as e:
            print(f"[AddSpecimenDialog] Error loading profile: {e}")
            self._update_profile_display(None)
    
    def _update_profile_display(self, profile_text: str):
        """Update the profile display section."""
        t = theme()
        self._profile_text = profile_text
        
        if profile_text:
            # Truncate if very long
            display_text = profile_text[:300] + "..." if len(profile_text) > 300 else profile_text
            self.profile_display.setText(display_text)
            self.profile_display.setStyleSheet(f"""
                color: {t.get('text_primary')};
                font-size: 12px;
                font-style: normal;
                padding: 8px 0;
            """)
            self.profile_link.setText("Edit Profile")
        else:
            self.profile_display.setText("No profile for this species yet.")
            self.profile_display.setStyleSheet(f"""
                color: {t.get('text_muted')};
                font-size: 12px;
                font-style: italic;
                padding: 8px 0;
            """)
            self.profile_link.setText("Create Profile")
    
    def _on_profile_link_clicked(self):
        """Handle click on profile create/edit link."""
        species_name = self._selected_species.get('scientific_name', '') if self._selected_species else ''
        species_tvk = self._selected_species.get('tvk') if self._selected_species else None
        
        if not species_tvk and self._existing_specimen:
            species_tvk = self._existing_specimen.get('species_tvk')
        
        if species_name:
            self.profile_edit_requested.emit(species_name, species_tvk or '')
    
    def _validate_grid_ref(self):
        """Validate the grid reference and look up vice county."""
        t = theme()
        grid_ref = self.gridref_edit.text().strip().upper()
        if not grid_ref:
            self.gridref_feedback.hide()
            self.vc_info_label.setText("Vice County")
            return
        
        if not self._vc_service:
            return
        
        try:
            is_valid, message = self._vc_service.validate_grid_ref(grid_ref)
            if is_valid:
                self.gridref_feedback.setText("✓ Valid grid reference")
                self.gridref_feedback.setStyleSheet(f"font-size: 11px; color: {t.get('success_text')};")
                
                # Look up vice county
                vc_info = self._vc_service.get_vice_county(grid_ref)
                if vc_info:
                    self.vc_info_label.setText(f"VC{vc_info.get('number', '?')}: {vc_info.get('name', 'Unknown')}")
                else:
                    self.vc_info_label.setText("Vice County: Unknown")
            else:
                self.gridref_feedback.setText(f"✗ {message}")
                self.gridref_feedback.setStyleSheet(f"font-size: 11px; color: {t.get('error_text')};")
            
            self.gridref_feedback.show()
        except Exception as e:
            print(f"[AddSpecimenDialog] Grid ref validation error: {e}")
    
    def _populate_from_existing(self, specimen: Dict[str, Any]):
        """Populate form fields from existing specimen data."""
        species_data = {
            'scientific_name': specimen.get('species_name', specimen.get('species', '')),
            'tvk': specimen.get('species_tvk', specimen.get('tvk', '')),
            'common_name': specimen.get('common_name', ''),
            'family': specimen.get('family', ''),
            'order': specimen.get('order_name', specimen.get('order', ''))
        }
        self.species_search.set_species(species_data)
        self._selected_species = species_data  # Set for validation
        
        raw_date = specimen.get('date_collected', specimen.get('date', ''))
        if raw_date:
            self.date_edit.setText(format_date_display(raw_date, 'user'))
        else:
            self.date_edit.setText('')
        
        self.location_edit.setText(specimen.get('site_name', specimen.get('location', '')))
        self.site_local_edit.setText(specimen.get('site_name_local', ''))
        self.gridref_edit.setText(specimen.get('grid_ref', specimen.get('gridRef', '')))
        self.collector_edit.setText(specimen.get('collector', ''))
        self.determiner_edit.setText(specimen.get('determiner', ''))
        self.notes_edit.setText(specimen.get('notes', ''))
        
        # Set sex combo
        sex = specimen.get('sex', '')
        index = self.sex_combo.findText(sex)
        if index >= 0:
            self.sex_combo.setCurrentIndex(index)
        
        # Show existing species info (order, family, common name)
        info_parts = []
        order = specimen.get('order_name') or specimen.get('order', '')
        family = specimen.get('family', '')
        common_name = specimen.get('common_name', '')
        
        if order:
            info_parts.append(order)
        if family:
            info_parts.append(family)
        
        display = " · ".join(info_parts)
        if common_name:
            display += f" – {common_name}"
        
        if display:
            self.species_info_label.setText(display)
            self.species_info_label.show()
        
        # Load species profile for this specimen's species
        species_name = specimen.get('species_name', specimen.get('species', ''))
        species_tvk = specimen.get('species_tvk')
        if species_name:
            self._load_species_profile(species_name, species_tvk)
    
    def keyPressEvent(self, event):
        """Ctrl+Enter saves. Plain Enter blocked from closing dialog."""
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._on_save()
                return
            # Check if species popup is showing
            if hasattr(self, "species_search") and hasattr(self.species_search, "_popup"):
                if self.species_search._popup.isVisible():
                    return
            # Block plain Enter from closing dialog
            return
        super().keyPressEvent(event)

    def _get_date_for_db(self):
        """Convert display date to ISO for database storage."""
        text = self.date_edit.text().strip()
        if not text:
            return ''
        iso = parse_display_date(text)
        return iso if iso else text

    def _on_save(self):
        """Handle save button click with validation."""
        if not self._selected_species:
            QMessageBox.warning(self, "Missing Species",
                "Please select a species from the search results.\n\n"
                "Type a name and click on the matching entry in the dropdown.")
            self.species_search.search_input.setFocus()
            return
        
        if not self.date_edit.text().strip():
            QMessageBox.warning(self, "Missing Date", "Please enter a date collected.")
            self.date_edit.setFocus()
            return
        
        if not self.gridref_edit.text().strip():
            QMessageBox.warning(self, "Missing Grid Ref", "Please enter a grid reference.")
            self.gridref_edit.setFocus()
            return
        
        self.accept()
    
    def get_specimen_data(self) -> Dict[str, Any]:
        """
        Get the entered specimen data.
        
        Returns:
            Dict with specimen fields matching SpecimenModel.insert_specimen() expectations
        """
        data = {
            'species_name': self._selected_species.get('scientific_name', '') if self._selected_species else '',
            'date_collected': self._get_date_for_db(),
            'site_name': self.location_edit.text().strip(),
            'site_name_local': self.site_local_edit.text().strip(),
            'grid_ref': self.gridref_edit.text().strip().upper(),
            'collector': self.collector_edit.text().strip(),
            'determiner': self.determiner_edit.text().strip(),
            'notes': self.notes_edit.toPlainText().strip(),
            'sex': self.sex_combo.currentText() if self.sex_combo.currentText() else None,
        }
        
        # Add UKSI data if species was found
        if self._selected_species:
            data['species_tvk'] = self._selected_species.get('tvk')
            data['common_name'] = self._selected_species.get('common_name')
            data['family'] = self._selected_species.get('family')
            data['order_name'] = self._selected_species.get('order')
        
        # Add vice county if available
        if self._vc_service and data['grid_ref']:
            try:
                vc_info = self._vc_service.get_vice_county(data['grid_ref'])
                if vc_info:
                    data['vice_county'] = vc_info.get('name')
                    data['vc_number'] = vc_info.get('number')
            except:
                pass
        
        return data

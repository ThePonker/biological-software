"""
Species Info Panel Component.

Displays contextual information about the selected species.
"""

from typing import Optional, Dict

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QWidget, QTextEdit
)
from PySide6.QtCore import Qt, Signal, QSettings

from .card import Card
from ...themes import theme
from ...core.config import Settings, Defaults, TabColors, ButtonColors


class SpeciesInfoPanel(Card):
    """Panel showing contextual information about the selected species."""

    view_specimens_clicked = Signal(str)  # Emits species TVK
    view_records_clicked = Signal(str)  # Emits species name for filtering observations
    profile_clicked = Signal(dict)  # Emits species data for profile editing

    def __init__(self, parent=None):
        super().__init__("Species Info", parent)
        self._current_species: Optional[Dict] = None
        self._current_profile: str = ""
        self._show_common_names = True
        self._load_common_name_setting()

        self._add_clear_button()
        self._setup_ui()

    def _load_common_name_setting(self):
        """Load the common name display setting."""
        settings = QSettings()
        self._show_common_names = settings.value(
            Settings.COMMON_NAMES_HOME, 
            Defaults.SHOW_COMMON_NAMES, 
            type=bool
        )

    def _add_clear_button(self):
        """Add clear button to header."""
        t = theme()
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_secondary')};
                border: none;
                font-size: {t.font_size('sm')};
                padding: 2px 8px;
            }}
            QPushButton:hover {{
                color: {t.get('text_primary')};
            }}
        """)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear)
        self.clear_btn.setVisible(False)  # Hidden until species is selected
        self.add_header_widget(self.clear_btn)

    def clear(self):
        """Clear the species info panel."""
        self.set_species(None)

    def _setup_ui(self):
        """Set up the panel UI."""
        t = theme()

        # Content container (will be shown/hidden)
        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        # Species name
        self.name_label = QLabel()
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet(f"font-size: {t.font_size('xl')}; font-weight: 600; font-style: italic; color: {t.get('text_primary')}; border: none; background: transparent;")
        content_layout.addWidget(self.name_label)

        self.common_name_label = QLabel()
        self.common_name_label.setStyleSheet(f"color: {t.get('text_primary')}; font-size: {t.font_size('base')}; border: none; background: transparent;")
        content_layout.addWidget(self.common_name_label)

        # Taxonomy - horizontal rows (Label: Value)
        order_layout = QHBoxLayout()
        self.order_label = QLabel("Order")
        self.order_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('base')}; border: none; background: transparent;")
        self.order_label.setFixedWidth(50)
        order_layout.addWidget(self.order_label)

        self.order_value = QLabel("-")
        self.order_value.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')}; font-size: {t.font_size('base')}; border: none; background: transparent;")
        order_layout.addWidget(self.order_value)
        order_layout.addStretch()
        content_layout.addLayout(order_layout)

        family_layout = QHBoxLayout()
        self.family_label = QLabel("Family")
        self.family_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('base')}; border: none; background: transparent;")
        self.family_label.setFixedWidth(50)
        family_layout.addWidget(self.family_label)

        self.family_value = QLabel("-")
        self.family_value.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')}; font-size: {t.font_size('base')}; border: none; background: transparent;")
        family_layout.addWidget(self.family_value)
        family_layout.addStretch()
        content_layout.addLayout(family_layout)

        # Records count - plain text row
        records_layout = QHBoxLayout()
        self.records_label = QLabel("Your Records")
        self.records_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('base')}; border: none; background: transparent;")
        records_layout.addWidget(self.records_label)

        self.view_records_btn = QPushButton("View records ->")
        self.view_records_btn.setFlat(True)
        self.view_records_btn.setStyleSheet(f"color: {TabColors.OBSERVATION}; font-size: {t.font_size('sm')}; text-align: left; padding: 0; border: none; background: transparent;")
        self.view_records_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_records_btn.setVisible(False)
        self.view_records_btn.clicked.connect(self._on_view_records)
        records_layout.addWidget(self.view_records_btn)

        records_layout.addStretch()

        self.records_value = QLabel("0")
        self.records_value.setStyleSheet(f"font-weight: 700; font-size: {t.font_size('lg')}; color: {TabColors.OBSERVATION}; border: none; background: transparent;")
        records_layout.addWidget(self.records_value)

        content_layout.addLayout(records_layout)

        # Collection status - layout matching Your Records row
        collection_layout = QHBoxLayout()
        self.collection_status = QLabel("Not in Collection")
        self.collection_status.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('base')}; border: none; background: transparent;")
        collection_layout.addWidget(self.collection_status)

        self.view_specimens_btn = QPushButton("View specimens →")
        self.view_specimens_btn.setFlat(True)
        self.view_specimens_btn.setStyleSheet(f"color: {TabColors.COLLECTION}; font-size: {t.font_size('sm')}; text-align: left; padding: 0; border: none; background: transparent;")
        self.view_specimens_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_specimens_btn.setVisible(False)
        self.view_specimens_btn.clicked.connect(self._on_view_specimens)
        collection_layout.addWidget(self.view_specimens_btn)

        collection_layout.addStretch()

        self.collection_count = QLabel("")
        self.collection_count.setStyleSheet(f"font-weight: 700; font-size: {t.font_size('lg')}; color: {TabColors.COLLECTION}; border: none; background: transparent;")
        self.collection_count.setVisible(False)
        collection_layout.addWidget(self.collection_count)

        content_layout.addLayout(collection_layout)

        # Species Profile section
        self._setup_profile_section(content_layout)

        self.content.setVisible(False)
        self.add_widget(self.content)

        # Placeholder
        self.placeholder = QLabel("Select a species to view details")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet(f"color: {t.get('text_muted')}; font-style: italic; padding: 40px;")
        self.add_widget(self.placeholder)
        self.add_stretch()

    def _setup_profile_section(self, content_layout):
        """Set up species profile section."""
        t = theme()

        profile_section = QVBoxLayout()
        profile_section.setSpacing(8)

        profile_header = QHBoxLayout()
        self.profile_label = QLabel("Species Profile")
        self.profile_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: {t.font_size('base')}; border: none; background: transparent;")
        profile_header.addWidget(self.profile_label)
        profile_header.addStretch()

        self.profile_btn = QPushButton("Create")
        self.profile_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ButtonColors.PRIMARY};
                color: white;
                border: none;
                border-radius: {t.get('radius_sm')};
                padding: 4px 12px;
                font-size: {t.font_size('sm')};
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {t.get('success_hover')}; }}
        """)
        self.profile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.profile_btn.clicked.connect(self._on_profile_clicked)
        profile_header.addWidget(self.profile_btn)

        profile_section.addLayout(profile_header)

        # Profile preview - expands to fill space
        self.profile_preview = QTextEdit()
        self.profile_preview.setReadOnly(True)
        self.profile_preview.setPlaceholderText("No profile notes yet")
        self.profile_preview.setStyleSheet(f"""
            QTextEdit {{
                color: {t.get('text_primary')};
                font-size: {t.font_size('sm')};
                background-color: {t.get('input_bg')};
                padding: 8px;
                border: 1px solid {t.get('border_strong', t.get('border'))};
                border-radius: {t.get('radius_md')};
            }}
        """)
        self.profile_preview.setMinimumHeight(60)
        # No maximum height - will expand to fill available space
        profile_section.addWidget(self.profile_preview, 1)  # stretch=1

        content_layout.addLayout(profile_section, 1)  # stretch=1 to fill remaining space

    def set_species(self, species_data: Optional[Dict]):
        """Update the displayed species."""
        t = theme()
        self._current_species = species_data

        if not species_data:
            self.content.setVisible(False)
            self.placeholder.setVisible(True)
            self.clear_btn.setVisible(False)
            return

        self.content.setVisible(True)
        self.placeholder.setVisible(False)
        self.clear_btn.setVisible(True)

        # Update display
        self.name_label.setText(species_data.get('scientific_name', 'Unknown'))

        # Common name - only show if setting enabled
        common = species_data.get('common_name', '')
        if self._show_common_names:
            if common:
                self.common_name_label.setText(common)
            else:
                self.common_name_label.setText("No common name")
            self.common_name_label.setVisible(True)
        else:
            self.common_name_label.setVisible(False)

        # Taxonomy
        order_val = species_data.get('order') or species_data.get('order_name') or '-'
        family_val = species_data.get('family') or '-'
        self.order_value.setText(order_val)
        self.family_value.setText(family_val)

        # Records count
        record_count = species_data.get('record_count', 0)
        self.records_value.setText(f"{record_count:,}")
        self.view_records_btn.setVisible(record_count > 0)

        # Collection status - layout matching Your Records row
        in_collection = species_data.get('in_collection', False)
        specimen_count = species_data.get('specimen_count', 0)

        if in_collection:
            self.collection_status.setText("In Collection")
            self.collection_status.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('base')}; border: none; background: transparent;")
            self.view_specimens_btn.setVisible(True)
            self.collection_count.setText(str(specimen_count))
            self.collection_count.setVisible(True)
        else:
            self.collection_status.setText("Not in Collection")
            self.collection_status.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('base')}; border: none; background: transparent;")
            self.view_specimens_btn.setVisible(False)
            self.collection_count.setVisible(False)

        # Load profile
        self._load_profile(species_data.get('tvk'))

    def _load_profile(self, tvk: str):
        """Load species profile from database."""
        t = theme()
        self._current_profile = ""
        self.profile_preview.clear()
        self.profile_btn.setText("Create")

        if not tvk:
            return

        try:
            from ...models.database import get_database
            db = get_database()
            query = "SELECT profile_text FROM species_profiles WHERE species_tvk = ?"
            results = db.execute_main(query, (tvk,))

            if results and results[0][0]:
                self._current_profile = results[0][0]
                # Show truncated preview
                preview = self._current_profile[:300]
                if len(self._current_profile) > 300:
                    preview += "..."
                self.profile_preview.setText(preview)
                self.profile_btn.setText("View")
        except Exception as e:
            print(f"Error loading profile: {e}")

    def set_profile(self, profile_text: str):
        """Update the profile display after edit."""
        self._current_profile = profile_text
        if profile_text:
            preview = profile_text[:300]
            if len(profile_text) > 300:
                preview += "..."
            self.profile_preview.setText(preview)
            self.profile_btn.setText("View")
        else:
            self.profile_preview.clear()
            self.profile_btn.setText("Create")

    def refresh_common_name_setting(self):
        """Refresh the common name display setting and update display."""
        old_setting = self._show_common_names
        self._load_common_name_setting()
        
        # Only refresh if setting changed and we have a species displayed
        if old_setting != self._show_common_names and self._current_species:
            self.set_species(self._current_species)

    def _on_view_records(self):
        """Handle view records button click."""
        if self._current_species:
            species_name = self._current_species.get('species_name') or self._current_species.get('scientific_name', '')
            if species_name:
                self.view_records_clicked.emit(species_name)

    def _on_view_specimens(self):
        """Handle view specimens button click."""
        if self._current_species:
            tvk = self._current_species.get('tvk') or self._current_species.get('species_tvk')
            if tvk:
                self.view_specimens_clicked.emit(tvk)

    def _on_profile_clicked(self):
        """Handle profile button click."""
        if self._current_species:
            self.profile_clicked.emit(self._current_species)

    def apply_theme(self):
        """Apply the current theme."""
        t = theme()

        # Update name labels
        self.name_label.setStyleSheet(f"font-size: {t.font_size('xl')}; font-weight: 600; font-style: italic; color: {t.get('text_primary')}; border: none; background: transparent;")
        self.common_name_label.setStyleSheet(f"color: {t.get('text_primary')}; font-size: {t.font_size('base')}; border: none; background: transparent;")

        # Update taxonomy labels
        self.order_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('base')}; border: none; background: transparent;")
        self.order_value.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')}; font-size: {t.font_size('base')}; border: none; background: transparent;")
        self.family_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('base')}; border: none; background: transparent;")
        self.family_value.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')}; font-size: {t.font_size('base')}; border: none; background: transparent;")

        # Update records
        self.records_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('base')}; border: none; background: transparent;")
        self.records_value.setStyleSheet(f"font-weight: 700; font-size: {t.font_size('lg')}; color: {TabColors.OBSERVATION}; border: none; background: transparent;")

        # Update collection status
        self.collection_status.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('base')}; border: none; background: transparent;")
        self.view_specimens_btn.setStyleSheet(f"color: {TabColors.COLLECTION}; font-size: {t.font_size('sm')}; text-align: left; padding: 0; border: none; background: transparent;")
        self.collection_count.setStyleSheet(f"font-weight: 700; font-size: {t.font_size('lg')}; color: {TabColors.COLLECTION}; border: none; background: transparent;")

        # Update placeholder
        self.placeholder.setStyleSheet(f"color: {t.get('text_muted')}; font-style: italic; padding: 40px; border: none; background: transparent;")

        # Update profile section
        self.profile_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: {t.font_size('base')}; border: none; background: transparent;")
        self.profile_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ButtonColors.PRIMARY};
                color: white;
                border: none;
                border-radius: {t.get('radius_sm')};
                padding: 4px 12px;
                font-size: {t.font_size('sm')};
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {t.get('success_hover')}; }}
        """)
        self.profile_preview.setStyleSheet(f"""
            QTextEdit {{
                color: {t.get('text_primary')};
                font-size: {t.font_size('sm')};
                background-color: {t.get('input_bg')};
                padding: 8px;
                border: 1px solid {t.get('border_strong', t.get('border'))};
                border-radius: {t.get('radius_md')};
            }}
        """)

        # Re-apply species data to update styles
        if self._current_species:
            self.set_species(self._current_species)

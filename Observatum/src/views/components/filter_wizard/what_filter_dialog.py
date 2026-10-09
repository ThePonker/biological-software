"""
What Filter Dialog.

Filter by species, order, and family with search bars and chips.
- Species: Fuzzy search with common names (e.g., "rut mac" or "blackbird")
- Order/Family: Fuzzy multi-word search
- Search, arrow keys to select, Enter to add
- Chips stack vertically
"""

from typing import Dict, Any, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QScrollArea, QWidget
)
from PySide6.QtCore import Qt, QTimer

from ....themes import theme
from ....core.config import ButtonColors


from .chip_display import FilterChip  # I9: one copy
from .fuzzy import picking_from_popup, FuzzyCompleter


class WhatFilterDialog(QDialog):
    """Dialog for filtering by taxonomy with fuzzy search including common names."""
    
    def __init__(
        self,
        accent_color: str = None,
        current_values: Dict[str, Any] = None,
        species_list: List[str] = None,
        taxon_groups: List[str] = None,
        family_list: List[str] = None,
        taxon_family_map: Dict[str, List[str]] = None,
        search_service=None,
        parent=None
    ):
        super().__init__(parent)
        self._accent_color = accent_color or "#5f8575"
        self._current = current_values or {}
        
        # Species with common names: display -> scientific_name
        self._species_display_list: List[str] = []
        self._species_map: Dict[str, str] = {}  # display_text -> scientific_name
        
        self._order_list = taxon_groups or []
        self._family_list = family_list or []
        self._species_param = species_list

        self._chips: Dict[str, List[FilterChip]] = {}

        # Only query observations if no tab-specific data was provided
        if not self._order_list and not self._family_list and not species_list:
            self._load_user_taxa()
        elif species_list:
            # Build display list from provided species
            self._species_display_list = []
            self._species_map = {}
            for sp in species_list:
                self._species_display_list.append(sp)
                self._species_map[sp] = sp

        
        self.setWindowTitle("Filter by What")
        self.setMinimumWidth(500)
        self.setMinimumHeight(520)
        self.setModal(True)
        
        self._setup_ui()
        self._load_current_values()
    
    def _load_user_taxa(self):
        """Load taxa from user's observation data with common names."""
        try:
            from ....core.config import Paths
            import sqlite3
            
            db_path = Paths.default_main_db()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Orders
            cursor.execute("""
                SELECT DISTINCT order_name 
                FROM observations 
                WHERE order_name IS NOT NULL AND order_name != ''
                ORDER BY order_name
            """)
            self._order_list = [row[0] for row in cursor.fetchall()]
            
            # Families
            cursor.execute("""
                SELECT DISTINCT family 
                FROM observations 
                WHERE family IS NOT NULL AND family != ''
                ORDER BY family
            """)
            self._family_list = [row[0] for row in cursor.fetchall()]
            
            # Species with common names - get both from observations
            cursor.execute("""
                SELECT DISTINCT species_name, common_name 
                FROM observations 
                WHERE species_name IS NOT NULL AND species_name != ''
                ORDER BY species_name
            """)
            
            self._species_display_list = []
            self._species_map = {}
            
            for row in cursor.fetchall():
                scientific = row[0]
                common = row[1] if row[1] else ""
                
                if common:
                    # Display: "Common Name (Scientific name)"
                    display = f"{common} ({scientific})"
                else:
                    display = scientific
                
                self._species_display_list.append(display)
                self._species_map[display] = scientific
            
            conn.close()
            print(f"[WhatFilterDialog] Loaded {len(self._order_list)} orders, {len(self._family_list)} families, {len(self._species_display_list)} species")
        except Exception as e:
            print(f"[WhatFilterDialog] Error loading user taxa: {e}")
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        t = theme()
        
        self.setStyleSheet(f"background-color: {t.get('background')};")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        header = QLabel("🦋 What to Include")
        header.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: 600;
                color: {self._accent_color};
                background: transparent;
            }}
        """)
        layout.addWidget(header)
        
        desc = QLabel("Type to search (e.g., 'blackbird' or 'rut mac'). Press Enter to add.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px; background: transparent;")
        layout.addWidget(desc)
        
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {t.get('border')};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        
        # SPECIES - uses special handler for mapping display->scientific
        species_section = self._create_species_section()
        layout.addWidget(species_section)
        
        # ORDER
        order_section = self._create_text_section("Order", "Search orders (e.g., 'dip' or 'col')...", self._order_list, "taxon_group", "Order")
        self._order_input = order_section['input']
        layout.addWidget(order_section['widget'])
        
        # FAMILY
        family_section = self._create_text_section("Family", "Search families (e.g., 'ceram')...", self._family_list, "family", "Family")
        self._family_input = family_section['input']
        layout.addWidget(family_section['widget'])
        
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"background-color: {t.get('border')};")
        sep2.setFixedHeight(1)
        layout.addWidget(sep2)
        
        # CHIPS
        chip_header = QHBoxLayout()
        self._chip_title = QLabel("No filters applied")
        self._chip_title.setStyleSheet(f"font-weight: 500; font-size: 12px; color: {t.get('text_secondary')};")
        chip_header.addWidget(self._chip_title)
        chip_header.addStretch()
        
        self._clear_all_btn = QPushButton("Clear All")
        self._clear_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_all_btn.clicked.connect(self._clear_all_chips)
        self._clear_all_btn.setVisible(False)
        self._clear_all_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {self._accent_color};
                font-size: 11px;
            }}
            QPushButton:hover {{
                text-decoration: underline;
            }}
        """)
        chip_header.addWidget(self._clear_all_btn)
        layout.addLayout(chip_header)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setMaximumHeight(150)
        scroll.setMinimumHeight(60)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 6px;
            }}
        """)
        
        self._chip_container = QWidget()
        self._chip_container.setStyleSheet(f"background-color: {t.get('surface')};")
        self._chip_layout = QVBoxLayout(self._chip_container)
        self._chip_layout.setContentsMargins(8, 8, 8, 8)
        self._chip_layout.setSpacing(6)
        self._chip_layout.addStretch()
        
        scroll.setWidget(self._chip_container)
        layout.addWidget(scroll)
        
        layout.addStretch()
        
        # BUTTONS
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        clear_btn = QPushButton("Clear")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_all_filters)
        clear_btn.setAutoDefault(False)
        clear_btn.setDefault(False)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: #a63d40;
                border: 1px solid #a63d40;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: rgba(166, 61, 64, 0.1);
            }}
        """)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setAutoDefault(False)
        cancel_btn.setDefault(False)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_secondary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 10px 24px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
            }}
        """)
        button_layout.addWidget(cancel_btn)
        
        apply_btn = QPushButton("Apply Filters")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(self.accept)
        apply_btn.setAutoDefault(False)
        apply_btn.setDefault(False)
        apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ButtonColors.PRIMARY};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {self._darken_color(ButtonColors.PRIMARY)};
            }}
        """)
        button_layout.addWidget(apply_btn)
        
        layout.addLayout(button_layout)
    
    def _create_species_section(self) -> QFrame:
        """Create species search with common name support."""
        t = theme()
        
        section = QFrame()
        section.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        lbl = QLabel("Species")
        lbl.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')}; font-size: 13px; background: transparent;")
        layout.addWidget(lbl)
        
        self._species_input = QLineEdit()
        self._species_input.setPlaceholderText("Search by common or scientific name...")
        self._species_input.setClearButtonEnabled(True)
        self._species_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 10px 14px;
                font-size: 13px;
                color: {t.get('text_primary')};
            }}
            QLineEdit:focus {{
                border-color: {self._accent_color};
            }}
        """)
        
        if self._species_display_list:
            completer = FuzzyCompleter(self._species_display_list, self._species_input)
            self._species_input.setCompleter(completer)
            completer.activated.connect(self._on_species_completer_activated)
        
        self._species_input.returnPressed.connect(self._on_species_enter)
        
        layout.addWidget(self._species_input)
        
        return section
    
    def _on_species_completer_activated(self, display_text: str):
        """Handle species autocomplete - map display to scientific name."""
        if display_text:
            scientific_name = self._species_map.get(display_text, display_text)
            self._add_chip("species", scientific_name, f"Species: {display_text}")
            QTimer.singleShot(50, self._species_input.clear)
    
    def _on_species_enter(self):
        """Handle Enter in species field."""
        if picking_from_popup(self._species_input):   # the completer's activated handler adds the chip
            return
        text = self._species_input.text().strip()
        if text:
            # Check if it matches a display text
            scientific_name = self._species_map.get(text, text)
            # Find display text for chip
            display = text
            for disp, sci in self._species_map.items():
                if sci == scientific_name or disp == text:
                    display = disp
                    scientific_name = sci
                    break
            self._add_chip("species", scientific_name, f"Species: {display}")
            self._species_input.clear()
    
    def _create_text_section(self, label: str, placeholder: str, data_list: List[str], category: str, prefix: str) -> dict:
        """Create a text search section with fuzzy completer."""
        t = theme()
        
        section = QFrame()
        section.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')}; font-size: 13px; background: transparent;")
        layout.addWidget(lbl)
        
        input_widget = QLineEdit()
        input_widget.setPlaceholderText(placeholder)
        input_widget.setClearButtonEnabled(True)
        input_widget.setStyleSheet(f"""
            QLineEdit {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 10px 14px;
                font-size: 13px;
                color: {t.get('text_primary')};
            }}
            QLineEdit:focus {{
                border-color: {self._accent_color};
            }}
        """)
        
        if data_list:
            completer = FuzzyCompleter(data_list, input_widget)
            input_widget.setCompleter(completer)
            completer.activated.connect(lambda text: self._on_completer_activated(input_widget, category, prefix, text))
        
        input_widget.returnPressed.connect(lambda: self._on_enter_pressed(input_widget, category, prefix))
        
        layout.addWidget(input_widget)
        
        return {'widget': section, 'input': input_widget}
    
    def _on_completer_activated(self, input_widget: QLineEdit, category: str, prefix: str, text: str):
        """Handle autocomplete selection."""
        if text:
            self._add_chip(category, text, f"{prefix}: {text}")
            QTimer.singleShot(50, input_widget.clear)
    
    def _on_enter_pressed(self, input_widget: QLineEdit, category: str, prefix: str):
        """Handle Enter key."""
        if picking_from_popup(input_widget):   # the completer's activated handler adds the chip
            return
        text = input_widget.text().strip()
        if text:
            self._add_chip(category, text, f"{prefix}: {text}")
            input_widget.clear()
    
    def _add_chip(self, category: str, value: str, display_text: str):
        """Add a chip."""
        if category in self._chips:
            for chip in self._chips[category]:
                if chip.get_value() == value:
                    return
        
        chip = FilterChip(category, value, display_text, self._accent_color)
        chip.removed.connect(self._remove_chip)
        
        if category not in self._chips:
            self._chips[category] = []
        self._chips[category].append(chip)
        
        self._chip_layout.insertWidget(self._chip_layout.count() - 1, chip)
        self._update_chip_header()
    
    def _remove_chip(self, category: str, value: str):
        """Remove a chip."""
        if category not in self._chips:
            return
        
        for chip in self._chips[category]:
            if chip.get_value() == value:
                self._chips[category].remove(chip)
                self._chip_layout.removeWidget(chip)
                chip.deleteLater()
                break
        
        if not self._chips[category]:
            del self._chips[category]
        
        self._update_chip_header()
    
    def _clear_all_chips(self):
        """Clear all chips."""
        for category, chips in list(self._chips.items()):
            for chip in chips:
                self._chip_layout.removeWidget(chip)
                chip.deleteLater()
        self._chips.clear()
        self._update_chip_header()
    
    def _clear_all_filters(self):
        """Clear everything."""
        self._clear_all_chips()
        self._species_input.clear()
        self._order_input.clear()
        self._family_input.clear()
    
    def _update_chip_header(self):
        """Update chip count header."""
        count = sum(len(chips) for chips in self._chips.values())
        if count == 0:
            self._chip_title.setText("No filters applied")
            self._clear_all_btn.setVisible(False)
        else:
            self._chip_title.setText(f"Applied Filters ({count}):")
            self._clear_all_btn.setVisible(True)
    
    def _load_current_values(self):
        """Load existing filter values as chips."""
        if not self._current:
            return
        
        for sp in self._current.get('species', []):
            # Find display text for scientific name
            display = sp
            for disp, sci in self._species_map.items():
                if sci == sp:
                    display = disp
                    break
            self._add_chip("species", sp, f"Species: {display}")
        
        for order in self._current.get('taxon_group', []):
            self._add_chip("taxon_group", order, f"Order: {order}")
        
        for fam in self._current.get('family', []):
            self._add_chip("family", fam, f"Family: {fam}")
    
    def get_values(self) -> Dict[str, Any]:
        """Get the filter values."""
        result = {}
        for category, chips in self._chips.items():
            result[category] = [chip.get_value() for chip in chips]
        return result
    
    def _darken_color(self, hex_color: str, factor: float = 0.85) -> str:
        hex_color = hex_color.lstrip('#')
        r = int(int(hex_color[0:2], 16) * factor)
        g = int(int(hex_color[2:4], 16) * factor)
        b = int(int(hex_color[4:6], 16) * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

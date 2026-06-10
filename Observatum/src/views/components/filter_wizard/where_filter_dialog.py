"""
Where Filter Dialog.

Filter by vice county, grid reference, and site name.
- Vice County: Fuzzy search bar
- Grid Reference: Search by 2-letter prefix or any figure (2-10)
- Site Name: Fuzzy search bar with partial match toggle
- All fields: Press Enter to add
"""

from typing import Dict, Any, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QCompleter, QScrollArea, QWidget, QSizePolicy,
    QCheckBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem

from ....themes import theme
from ....core.config import ButtonColors


class FuzzyFilterProxyModel(QSortFilterProxyModel):
    """Proxy model that filters by matching ALL space-separated words.
    
    Includes common geographic abbreviation expansion:
    - south/sth, north/nth, east/e, west/w
    - fen/fn, wood/wd, field/fld, farm/fm, etc.
    """
    
    # Abbreviation mappings (both directions)
    ABBREVIATIONS = {
        'south': ['sth', 's'],
        'sth': ['south', 's'],
        'north': ['nth', 'n'],
        'nth': ['north', 'n'],
        'east': ['e', 'est'],
        'west': ['w', 'wst'],
        'fen': ['fn'],
        'fn': ['fen'],
        'wood': ['wd', 'wds'],
        'wd': ['wood'],
        'woods': ['wds', 'wd'],
        'wds': ['woods', 'wood'],
        'field': ['fld', 'flds'],
        'fld': ['field'],
        'fields': ['flds', 'fld'],
        'farm': ['fm'],
        'fm': ['farm'],
        'lane': ['ln'],
        'ln': ['lane'],
        'road': ['rd'],
        'rd': ['road'],
        'meadow': ['mdw', 'mead'],
        'mdw': ['meadow'],
        'reserve': ['res', 'rsv'],
        'res': ['reserve'],
        'nature': ['nat'],
        'nat': ['nature'],
        'green': ['grn'],
        'grn': ['green'],
        'great': ['gt', 'grt'],
        'gt': ['great'],
        'little': ['lt', 'ltl'],
        'lt': ['little'],
        'saint': ['st'],
        'st': ['saint', 'street'],
        'street': ['st'],
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_words = []
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    
    def setFilterText(self, text: str):
        self._filter_words = text.lower().split()
        self.invalidateFilter()
    
    def _word_matches(self, word: str, text_lower: str) -> bool:
        """Check if word matches text, including abbreviation variants."""
        # Direct match
        if word in text_lower:
            return True
        
        # Try abbreviation variants
        variants = self.ABBREVIATIONS.get(word, [])
        for variant in variants:
            if variant in text_lower:
                return True
        
        return False
    
    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        if not self._filter_words:
            return True
        
        index = self.sourceModel().index(source_row, 0, source_parent)
        text = self.sourceModel().data(index, Qt.ItemDataRole.DisplayRole)
        if not text:
            return False
        
        text_lower = text.lower()
        return all(self._word_matches(word, text_lower) for word in self._filter_words)


class GridRefProxyModel(QSortFilterProxyModel):
    """Proxy model for grid reference prefix matching."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_text = ""
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    
    def setFilterText(self, text: str):
        self._filter_text = text.upper().strip()
        self.invalidateFilter()
    
    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        if not self._filter_text:
            return True
        
        index = self.sourceModel().index(source_row, 0, source_parent)
        grid_ref = self.sourceModel().data(index, Qt.ItemDataRole.DisplayRole)
        if not grid_ref:
            return False
        
        return grid_ref.upper().startswith(self._filter_text)


class FuzzyCompleter(QCompleter):
    """Completer with fuzzy multi-word matching."""
    
    def __init__(self, items: List[str], parent=None):
        self._source_model = QStandardItemModel(parent)
        for item in items:
            self._source_model.appendRow(QStandardItem(item))
        
        self._proxy_model = FuzzyFilterProxyModel(parent)
        self._proxy_model.setSourceModel(self._source_model)
        
        super().__init__(self._proxy_model, parent)
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setMaxVisibleItems(10)
    
    def splitPath(self, path: str) -> List[str]:
        self._proxy_model.setFilterText(path)
        return [path]
    
    def pathFromIndex(self, index) -> str:
        source_index = self._proxy_model.mapToSource(index)
        return self._source_model.data(source_index, Qt.ItemDataRole.DisplayRole)


class GridRefCompleter(QCompleter):
    """Completer for grid references with prefix matching."""
    
    def __init__(self, items: List[str], parent=None):
        self._source_model = QStandardItemModel(parent)
        for item in items:
            self._source_model.appendRow(QStandardItem(item))
        
        self._proxy_model = GridRefProxyModel(parent)
        self._proxy_model.setSourceModel(self._source_model)
        
        super().__init__(self._proxy_model, parent)
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setMaxVisibleItems(15)
    
    def splitPath(self, path: str) -> List[str]:
        self._proxy_model.setFilterText(path)
        return [path]
    
    def pathFromIndex(self, index) -> str:
        source_index = self._proxy_model.mapToSource(index)
        return self._source_model.data(source_index, Qt.ItemDataRole.DisplayRole)


class FilterChip(QFrame):
    """A single removable chip."""
    
    removed = Signal(str, str)
    
    def __init__(self, category: str, value: str, display_text: str, accent_color: str, parent=None):
        super().__init__(parent)
        self._category = category
        self._value = value
        self._accent_color = accent_color
        
        t = theme()
        
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 8, 4)
        layout.setSpacing(8)
        
        label = QLabel(display_text)
        label.setStyleSheet(f"color: {t.get('text_primary')}; font-size: 12px; background: transparent;")
        layout.addWidget(label)
        
        layout.addStretch()
        
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(lambda: self.removed.emit(self._category, self._value))
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_secondary')};
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
                color: {t.get('text_primary')};
            }}
        """)
        layout.addWidget(remove_btn)
        
        hex_color = accent_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = int(r + (255 - r) * 0.9)
        g = int(g + (255 - g) * 0.9)
        b = int(b + (255 - b) * 0.9)
        light_color = f"#{r:02x}{g:02x}{b:02x}"
        
        self.setStyleSheet(f"""
            FilterChip {{
                background-color: {light_color};
                border: 1px solid {accent_color};
                border-radius: 4px;
            }}
        """)
    
    def get_category(self): return self._category
    def get_value(self): return self._value


class WhereFilterDialog(QDialog):
    """Dialog for filtering by location."""
    
    def __init__(
        self,
        accent_color: str = None,
        current_values: Dict[str, Any] = None,
        parent=None
    ):
        super().__init__(parent)
        self._accent_color = accent_color or "#5f8575"
        self._current = current_values or {}
        
        self._vc_list: List[str] = []
        self._grid_ref_list: List[str] = []
        self._site_list: List[str] = []
        
        self._chips: Dict[str, List[FilterChip]] = {}
        
        # Flag to prevent double handling of Enter
        self._handling_selection = False
        
        self._load_user_locations()
        
        self.setWindowTitle("Filter by Where")
        self.setMinimumWidth(500)
        self.setMinimumHeight(520)
        self.setModal(True)
        
        self._setup_ui()
        self._load_current_values()
    
    def _load_user_locations(self):
        """Load location data from user's observations."""
        try:
            from ....core.config import Paths
            import sqlite3
            
            db_path = Paths.default_main_db()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Vice Counties
            cursor.execute("""
                SELECT DISTINCT vice_county 
                FROM observations 
                WHERE vice_county IS NOT NULL AND vice_county != ''
                ORDER BY vice_county
            """)
            self._vc_list = [row[0] for row in cursor.fetchall()]
            
            # Grid References
            cursor.execute("""
                SELECT DISTINCT grid_ref 
                FROM observations 
                WHERE grid_ref IS NOT NULL AND grid_ref != ''
                ORDER BY grid_ref
            """)
            self._grid_ref_list = [row[0] for row in cursor.fetchall()]
            
            # Site Names
            cursor.execute("""
                SELECT DISTINCT site_name 
                FROM observations 
                WHERE site_name IS NOT NULL AND site_name != ''
                ORDER BY site_name
            """)
            self._site_list = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            print(f"[WhereFilterDialog] Loaded {len(self._vc_list)} VCs, {len(self._grid_ref_list)} grid refs, {len(self._site_list)} sites")
        except Exception as e:
            print(f"[WhereFilterDialog] Error loading locations: {e}")
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        t = theme()
        
        self.setStyleSheet(f"background-color: {t.get('background')};")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        header = QLabel("📍 Where to Include")
        header.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: 600;
                color: {self._accent_color};
                background: transparent;
            }}
        """)
        layout.addWidget(header)
        
        desc = QLabel("Search and press Enter to add. Grid refs match by prefix (e.g., 'TL' or 'TL25').")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px; background: transparent;")
        layout.addWidget(desc)
        
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {t.get('border')};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        
        # VICE COUNTY
        vc_section = self._create_search_section("Vice County", "Search vice counties...", self._vc_list, "vice_county", "VC")
        self._vc_input = vc_section['input']
        layout.addWidget(vc_section['widget'])
        
        # GRID REFERENCE
        grid_section = self._create_search_section("Grid Reference", "Search by prefix (TL, TL25, etc.)...", self._grid_ref_list, "grid_ref", "Grid", is_grid_ref=True)
        self._grid_input = grid_section['input']
        layout.addWidget(grid_section['widget'])
        
        # SITE NAME with partial match toggle
        site_section = self._create_site_section()
        layout.addWidget(site_section)
        
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
    
    def _create_site_section(self) -> QFrame:
        """Create site name section with partial match toggle."""
        t = theme()
        
        section = QFrame()
        section.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Label row with checkbox
        label_row = QHBoxLayout()
        lbl = QLabel("Site Name")
        lbl.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')}; font-size: 13px; background: transparent;")
        label_row.addWidget(lbl)
        
        label_row.addStretch()
        
        self._partial_match_cb = QCheckBox("Partial match")
        self._partial_match_cb.setChecked(True)  # Default to partial match
        self._partial_match_cb.setStyleSheet(f"""
            QCheckBox {{
                color: {t.get('text_primary')};
                font-size: 12px;
                spacing: 6px;
                padding: 4px 8px;
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid {self._accent_color};
                border-radius: 3px;
                background-color: white;
            }}
            QCheckBox::indicator:checked {{
                background-color: {self._accent_color};
                image: none;
            }}
        """)
        label_row.addWidget(self._partial_match_cb)
        
        layout.addLayout(label_row)
        
        self._site_input = QLineEdit()
        self._site_input.setPlaceholderText("Search site names (abbreviations: sth=south, nth=north)...")
        self._site_input.setClearButtonEnabled(True)
        self._site_input.setStyleSheet(f"""
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
        
        if self._site_list:
            completer = FuzzyCompleter(self._site_list, self._site_input)
            self._site_input.setCompleter(completer)
            completer.activated.connect(self._on_site_selection)
        
        self._site_input.returnPressed.connect(self._on_site_enter)
        
        layout.addWidget(self._site_input)
        
        return section
    
    def _on_site_selection(self, text: str):
        """Handle site autocomplete selection - respects partial match toggle."""
        if not text:
            return
        
        self._handling_selection = True
        
        if self._partial_match_cb.isChecked():
            # Partial match - use the user's typed text, not dropdown selection
            typed_text = self._site_input.text().strip()
            if typed_text:
                value = f"~{typed_text}"
                display = f"Site: *{typed_text}*"
            else:
                # Fallback to selected text
                value = f"~{text}"
                display = f"Site: *{text}*"
        else:
            # Exact match - use selected text from dropdown
            value = text
            display = f"Site: {text}"
        
        self._add_chip("site_name", value, display)
        
        QTimer.singleShot(50, lambda: self._finish_selection(self._site_input))
    
    def _on_site_enter(self):
        """Handle Enter in site field - check partial match toggle."""
        if self._handling_selection:
            return
        
        text = self._site_input.text().strip()
        if not text:
            return
        
        if self._partial_match_cb.isChecked():
            # Partial match - prefix with ~
            value = f"~{text}"
            display = f"Site: *{text}*"
        else:
            # Exact match
            value = text
            display = f"Site: {text}"
        
        self._add_chip("site_name", value, display)
        self._site_input.clear()
    
    def _create_search_section(self, label: str, placeholder: str, data_list: List[str], category: str, prefix: str, is_grid_ref: bool = False) -> dict:
        """Create a search section with completer."""
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
            if is_grid_ref:
                completer = GridRefCompleter(data_list, input_widget)
            else:
                completer = FuzzyCompleter(data_list, input_widget)
            input_widget.setCompleter(completer)
            
            # When user selects from dropdown
            completer.activated.connect(lambda text: self._on_selection(input_widget, category, prefix, text, is_grid_ref))
        
        # When user presses Enter
        input_widget.returnPressed.connect(lambda: self._on_enter(input_widget, category, prefix, is_grid_ref))
        
        layout.addWidget(input_widget)
        
        return {'widget': section, 'input': input_widget}
    
    def _on_selection(self, input_widget: QLineEdit, category: str, prefix: str, text: str, is_grid_ref: bool):
        """Handle autocomplete selection."""
        if not text:
            return
        
        self._handling_selection = True
        
        display = f"{prefix}: {text}"
        self._add_chip(category, text, display)
        
        QTimer.singleShot(50, lambda: self._finish_selection(input_widget))
    
    def _finish_selection(self, input_widget: QLineEdit):
        """Finish selection and reset flag."""
        input_widget.clear()
        self._handling_selection = False
    
    def _on_enter(self, input_widget: QLineEdit, category: str, prefix: str, is_grid_ref: bool):
        """Handle Enter key press."""
        if self._handling_selection:
            return
        
        text = input_widget.text().strip()
        if not text:
            return
        
        # For grid refs, validate and uppercase
        if is_grid_ref:
            text = text.upper()
            if not (len(text) >= 1 and text[0].isalpha()):
                return
            display = f"{prefix}: {text}*"
        else:
            display = f"{prefix}: {text}"
        
        self._add_chip(category, text, display)
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
        self._vc_input.clear()
        self._grid_input.clear()
        self._site_input.clear()
    
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
        
        for vc in self._current.get('vice_county', []):
            self._add_chip("vice_county", vc, f"VC: {vc}")
        
        for grid in self._current.get('grid_ref', []):
            display = f"Grid: {grid}*" if len(grid) <= 4 else f"Grid: {grid}"
            self._add_chip("grid_ref", grid, display)
        
        for site in self._current.get('site_name', []):
            if site.startswith('~'):
                display = f"Site: *{site[1:]}*"
            else:
                display = f"Site: {site}"
            self._add_chip("site_name", site, display)
    
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

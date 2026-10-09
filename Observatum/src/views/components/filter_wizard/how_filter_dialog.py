"""
How Filter Dialog.

Filter by method/sample details.
- Tick boxes for quick method selection (loaded from user's data)
- Search bar with partial match for notes/comments
"""

from typing import Dict, Any, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QScrollArea, QWidget, QCheckBox, QGridLayout
)
from PySide6.QtCore import Qt

from ....themes import theme
from ....core.config import ButtonColors


from .chip_display import FilterChip  # I9: one copy


class HowFilterDialog(QDialog):
    """Dialog for filtering by method/sample details."""
    
    def __init__(
        self,
        accent_color: str = None,
        current_values: Dict[str, Any] = None,
        method_list: List[str] = None,  # Kept for compatibility but loads from DB
        parent=None
    ):
        super().__init__(parent)
        self._accent_color = accent_color or "#5f8575"
        self._current = current_values or {}
        
        self._method_list: List[str] = []
        self._method_checkboxes: Dict[str, QCheckBox] = {}
        
        self._chips: Dict[str, List[FilterChip]] = {}
        
        self._load_user_methods()
        
        self.setWindowTitle("Filter by How")
        self.setMinimumWidth(550)
        self.setMinimumHeight(550)
        self.setModal(True)
        
        self._setup_ui()
        self._load_current_values()
    
    def _load_user_methods(self):
        """Load method data from user's observations."""
        try:
            from ....core.config import Paths
            import sqlite3
            
            db_path = Paths.default_main_db()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get distinct methods
            cursor.execute("""
                SELECT DISTINCT method 
                FROM observations 
                WHERE method IS NOT NULL AND method != ''
                ORDER BY method
            """)
            self._method_list = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            print(f"[HowFilterDialog] Loaded {len(self._method_list)} methods")
        except Exception as e:
            print(f"[HowFilterDialog] Error loading methods: {e}")
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        t = theme()
        
        self.setStyleSheet(f"background-color: {t.get('background')};")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        header = QLabel("🔧 How to Include")
        header.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: 600;
                color: {self._accent_color};
                background: transparent;
            }}
        """)
        layout.addWidget(header)
        
        desc = QLabel("Select methods using checkboxes, or search notes/comments for specific terms.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px; background: transparent;")
        layout.addWidget(desc)
        
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {t.get('border')};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        
        # METHOD CHECKBOXES
        method_label = QLabel("Sample Methods")
        method_label.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')}; font-size: 13px; background: transparent;")
        layout.addWidget(method_label)
        
        method_scroll = QScrollArea()
        method_scroll.setWidgetResizable(True)
        method_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        method_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        method_scroll.setMaximumHeight(150)
        method_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 6px;
            }}
        """)
        
        method_container = QWidget()
        method_container.setStyleSheet(f"background-color: {t.get('surface')};")
        method_grid = QGridLayout(method_container)
        method_grid.setContentsMargins(12, 12, 12, 12)
        method_grid.setSpacing(8)
        
        # Create checkboxes for each method (2 columns)
        for i, method in enumerate(self._method_list):
            cb = QCheckBox(method)
            cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {t.get('text_primary')};
                    font-size: 12px;
                    spacing: 6px;
                }}
                QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border: 2px solid {t.get('border')};
                    border-radius: 3px;
                    background-color: white;
                }}
                QCheckBox::indicator:checked {{
                    background-color: {self._accent_color};
                    border-color: {self._accent_color};
                }}
            """)
            row = i // 2
            col = i % 2
            method_grid.addWidget(cb, row, col)
            self._method_checkboxes[method] = cb
        
        method_scroll.setWidget(method_container)
        layout.addWidget(method_scroll)
        
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"background-color: {t.get('border')};")
        sep2.setFixedHeight(1)
        layout.addWidget(sep2)
        
        # NOTES SEARCH with partial match
        notes_section = self._create_notes_section()
        layout.addWidget(notes_section)
        
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet(f"background-color: {t.get('border')};")
        sep3.setFixedHeight(1)
        layout.addWidget(sep3)
        
        # CHIPS for notes search
        chip_header = QHBoxLayout()
        self._chip_title = QLabel("Notes search terms:")
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
        scroll.setMaximumHeight(100)
        scroll.setMinimumHeight(50)
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
    
    def _create_notes_section(self) -> QFrame:
        """Create notes search section."""
        t = theme()
        
        section = QFrame()
        section.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        lbl = QLabel("Search Notes/Comments")
        lbl.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')}; font-size: 13px; background: transparent;")
        layout.addWidget(lbl)
        
        hint = QLabel("Search across: comment, internal_notes, sample_comment (e.g., 'nettle', 'oak')")
        hint.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px; background: transparent;")
        layout.addWidget(hint)
        
        self._notes_input = QLineEdit()
        self._notes_input.setPlaceholderText("Type search term and press Enter to add...")
        self._notes_input.setClearButtonEnabled(True)
        self._notes_input.setStyleSheet(f"""
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
        
        self._notes_input.returnPressed.connect(self._on_notes_enter)
        
        layout.addWidget(self._notes_input)
        
        return section
    
    def _on_notes_enter(self):
        """Handle Enter in notes search field."""
        text = self._notes_input.text().strip()
        if not text:
            return
        
        # Notes search is always partial match (uses ~ prefix)
        value = f"~{text}"
        display = f"Notes: *{text}*"
        
        self._add_chip("notes_search", value, display)
        self._notes_input.clear()
    
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
        self._notes_input.clear()
        for cb in self._method_checkboxes.values():
            cb.setChecked(False)
    
    def _update_chip_header(self):
        """Update chip count header."""
        count = sum(len(chips) for chips in self._chips.values())
        if count == 0:
            self._chip_title.setText("Notes search terms:")
            self._clear_all_btn.setVisible(False)
        else:
            self._chip_title.setText(f"Notes search ({count}):")
            self._clear_all_btn.setVisible(True)
    
    def _load_current_values(self):
        """Load existing filter values."""
        if not self._current:
            return
        
        # Load method checkboxes
        for method in self._current.get('method', []):
            if not method.startswith('~') and method in self._method_checkboxes:
                self._method_checkboxes[method].setChecked(True)
        
        # Load notes search chips
        for note in self._current.get('notes_search', []):
            if note.startswith('~'):
                display = f"Notes: *{note[1:]}*"
            else:
                display = f"Notes: {note}"
            self._add_chip("notes_search", note, display)
    
    def get_values(self) -> Dict[str, Any]:
        """Get the filter values."""
        result = {}
        
        # Get selected methods from checkboxes
        selected_methods = [method for method, cb in self._method_checkboxes.items() if cb.isChecked()]
        if selected_methods:
            result['method'] = selected_methods
        
        # Get notes search terms from chips
        if 'notes_search' in self._chips:
            result['notes_search'] = [chip.get_value() for chip in self._chips['notes_search']]
        
        return result
    
    def _darken_color(self, hex_color: str, factor: float = 0.85) -> str:
        hex_color = hex_color.lstrip('#')
        r = int(int(hex_color[0:2], 16) * factor)
        g = int(int(hex_color[2:4], 16) * factor)
        b = int(int(hex_color[4:6], 16) * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

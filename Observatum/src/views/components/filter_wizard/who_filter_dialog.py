"""
Who Filter Dialog.

Filter by recorder or determiner with fuzzy search.
- Loads data directly from user's observations
- Enter to add, no Add buttons
- Fuzzy multi-word search
"""

from typing import Dict, Any, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QCompleter, QScrollArea, QWidget, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem

from ....themes import theme
from ....core.config import ButtonColors


class FuzzyFilterProxyModel(QSortFilterProxyModel):
    """Proxy model that filters by matching ALL space-separated words."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_words = []
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    
    def setFilterText(self, text: str):
        self._filter_words = text.lower().split()
        self.invalidateFilter()
    
    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        if not self._filter_words:
            return True
        
        index = self.sourceModel().index(source_row, 0, source_parent)
        text = self.sourceModel().data(index, Qt.ItemDataRole.DisplayRole)
        if not text:
            return False
        
        text_lower = text.lower()
        return all(word in text_lower for word in self._filter_words)


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


class WhoFilterDialog(QDialog):
    """Dialog for filtering by recorder/determiner."""
    
    def __init__(
        self,
        accent_color: str = None,
        current_values: Dict[str, Any] = None,
        recorder_list: List[str] = None,  # Kept for compatibility but not used
        determiner_list: List[str] = None,  # Kept for compatibility but not used
        parent=None
    ):
        super().__init__(parent)
        self._accent_color = accent_color or "#5f8575"
        self._current = current_values or {}
        
        self._recorder_list: List[str] = []
        self._determiner_list: List[str] = []
        
        self._chips: Dict[str, List[FilterChip]] = {}
        
        # Flag to prevent double handling of Enter
        self._handling_selection = False
        
        self._load_user_people()
        
        self.setWindowTitle("Filter by Who")
        self.setMinimumWidth(500)
        self.setMinimumHeight(450)
        self.setModal(True)
        
        self._setup_ui()
        self._load_current_values()
    
    def _load_user_people(self):
        """Load recorder/determiner data from user's observations."""
        try:
            from ....core.config import Paths
            import sqlite3
            
            db_path = Paths.default_main_db()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Recorders
            cursor.execute("""
                SELECT DISTINCT recorder 
                FROM observations 
                WHERE recorder IS NOT NULL AND recorder != ''
                ORDER BY recorder
            """)
            self._recorder_list = [row[0] for row in cursor.fetchall()]
            
            # Determiners
            cursor.execute("""
                SELECT DISTINCT determiner 
                FROM observations 
                WHERE determiner IS NOT NULL AND determiner != ''
                ORDER BY determiner
            """)
            self._determiner_list = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            print(f"[WhoFilterDialog] Loaded {len(self._recorder_list)} recorders, {len(self._determiner_list)} determiners")
        except Exception as e:
            print(f"[WhoFilterDialog] Error loading people: {e}")
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        t = theme()
        
        self.setStyleSheet(f"background-color: {t.get('background')};")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        header = QLabel("👤 Who to Include")
        header.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: 600;
                color: {self._accent_color};
                background: transparent;
            }}
        """)
        layout.addWidget(header)
        
        desc = QLabel("Search and press Enter to add. Multiple selections use OR logic.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px; background: transparent;")
        layout.addWidget(desc)
        
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {t.get('border')};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        
        # RECORDER with partial match toggle
        recorder_section = self._create_search_section_with_toggle("Recorder", "Search recorders...", self._recorder_list, "recorder", "Recorder")
        self._recorder_input = recorder_section['input']
        self._recorder_partial_cb = recorder_section['checkbox']
        layout.addWidget(recorder_section['widget'])
        
        # DETERMINER with partial match toggle
        determiner_section = self._create_search_section_with_toggle("Determiner", "Search determiners...", self._determiner_list, "determiner", "Determiner")
        self._determiner_input = determiner_section['input']
        self._determiner_partial_cb = determiner_section['checkbox']
        layout.addWidget(determiner_section['widget'])
        
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
    
    def _create_search_section_with_toggle(self, label: str, placeholder: str, data_list: List[str], category: str, prefix: str) -> dict:
        """Create a search section with completer and partial match toggle."""
        t = theme()
        
        section = QFrame()
        section.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Label row with checkbox
        from PySide6.QtWidgets import QCheckBox
        label_row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')}; font-size: 13px; background: transparent;")
        label_row.addWidget(lbl)
        
        label_row.addStretch()
        
        partial_cb = QCheckBox("Partial match")
        partial_cb.setChecked(True)  # Default to partial match
        partial_cb.setStyleSheet(f"""
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
            }}
        """)
        label_row.addWidget(partial_cb)
        
        layout.addLayout(label_row)
        
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
            completer.activated.connect(lambda text: self._on_selection_with_toggle(input_widget, category, prefix, text, partial_cb))
        
        input_widget.returnPressed.connect(lambda: self._on_enter_with_toggle(input_widget, category, prefix, partial_cb))
        
        layout.addWidget(input_widget)
        
        return {'widget': section, 'input': input_widget, 'checkbox': partial_cb}
    
    def _on_selection_with_toggle(self, input_widget: QLineEdit, category: str, prefix: str, text: str, partial_cb):
        """Handle autocomplete selection - respects partial match toggle."""
        if not text:
            return
        
        self._handling_selection = True
        
        if partial_cb.isChecked():
            # Partial match - use the user's typed text
            typed_text = input_widget.text().strip()
            if typed_text:
                value = f"~{typed_text}"
                display = f"{prefix}: *{typed_text}*"
            else:
                value = f"~{text}"
                display = f"{prefix}: *{text}*"
        else:
            # Exact match
            value = text
            display = f"{prefix}: {text}"
        
        self._add_chip(category, value, display)
        
        QTimer.singleShot(50, lambda: self._finish_selection(input_widget))
    
    def _on_enter_with_toggle(self, input_widget: QLineEdit, category: str, prefix: str, partial_cb):
        """Handle Enter key press - respects partial match toggle."""
        if self._handling_selection:
            return
        
        text = input_widget.text().strip()
        if not text:
            return
        
        if partial_cb.isChecked():
            value = f"~{text}"
            display = f"{prefix}: *{text}*"
        else:
            value = text
            display = f"{prefix}: {text}"
        
        self._add_chip(category, value, display)
        input_widget.clear()
    
    def _create_search_section(self, label: str, placeholder: str, data_list: List[str], category: str, prefix: str) -> dict:
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
            completer = FuzzyCompleter(data_list, input_widget)
            input_widget.setCompleter(completer)
            completer.activated.connect(lambda text: self._on_selection(input_widget, category, prefix, text))
        
        input_widget.returnPressed.connect(lambda: self._on_enter(input_widget, category, prefix))
        
        layout.addWidget(input_widget)
        
        return {'widget': section, 'input': input_widget}
    
    def _on_selection(self, input_widget: QLineEdit, category: str, prefix: str, text: str):
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
    
    def _on_enter(self, input_widget: QLineEdit, category: str, prefix: str):
        """Handle Enter key press."""
        if self._handling_selection:
            return
        
        text = input_widget.text().strip()
        if not text:
            return
        
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
        self._recorder_input.clear()
        self._determiner_input.clear()
    
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
        
        for recorder in self._current.get('recorder', []):
            if recorder.startswith('~'):
                display = f"Recorder: *{recorder[1:]}*"
            else:
                display = f"Recorder: {recorder}"
            self._add_chip("recorder", recorder, display)
        
        for determiner in self._current.get('determiner', []):
            if determiner.startswith('~'):
                display = f"Determiner: *{determiner[1:]}*"
            else:
                display = f"Determiner: {determiner}"
            self._add_chip("determiner", determiner, display)
    
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

"""
Species Search Dialog for Specimen Import Wizard.

Dialog for searching and selecting a species from UKSI.
Used for fixing species errors in the import wizard.

Split from specimen_import_wizard.py for maintainability.
"""

from typing import Optional, Dict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Signal, QTimer

from ....themes import theme


class SpeciesSearchDialog(QDialog):
    """
    Dialog for searching and selecting a species from UKSI.
    
    Used for fixing species errors in the import wizard.
    """
    
    species_selected = Signal(dict)  # Emits species data dict
    
    def __init__(self, parent=None, uksi_model=None, initial_text: str = ""):
        super().__init__(parent)
        self.uksi_model = uksi_model
        self._selected_species = None
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_search)
        
        self.setWindowTitle("Search Species")
        self.setMinimumSize(500, 400)
        self.setModal(True)
        
        self._setup_ui()
        
        if initial_text:
            self.search_input.setText(initial_text)
            self._do_search()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        t = theme()
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Instructions
        instructions = QLabel("Search for the correct species name:")
        instructions.setStyleSheet("font-weight: 600;")
        layout.addWidget(instructions)
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type species name (min 2 characters)...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px 12px;
                border: 1px solid {t.get('border')};
                border-radius: 6px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 2px solid {t.get('success')};
            }}
        """)
        self.search_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.search_input)
        
        # Results list
        self.results_list = QListWidget()
        self.results_list.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {t.get('border')};
                border-radius: 6px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {t.get('surface_alt')};
            }}
            QListWidget::item:selected {{
                background-color: {t.get('success_bg_light')};
                color: {t.get('success')};
            }}
            QListWidget::item:hover {{
                background-color: {t.get('hover')};
            }}
        """)
        self.results_list.itemClicked.connect(self._on_item_clicked)
        self.results_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.results_list, 1)
        
        # Selected species info
        self.selected_label = QLabel("No species selected")
        self.selected_label.setStyleSheet(f"""
            padding: 8px;
            background-color: {t.get('surface_alt')};
            border-radius: 4px;
            color: {t.get('text_secondary')};
        """)
        layout.addWidget(self.selected_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setMinimumWidth(80)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.select_btn = QPushButton("Select Species")
        self.select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_btn.setMinimumWidth(120)
        self.select_btn.setEnabled(False)
        self.select_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('success')};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {t.get('success_hover')}; }}
            QPushButton:disabled {{ background-color: {t.get('text_muted')}; }}
        """)
        self.select_btn.clicked.connect(self._on_select)
        button_layout.addWidget(self.select_btn)
        
        layout.addLayout(button_layout)
    
    def _on_text_changed(self, text: str):
        """Handle text input changes with debounce."""
        if len(text) >= 2:
            self._search_timer.start(300)  # 300ms debounce
        else:
            self.results_list.clear()
    
    def _do_search(self):
        """Execute the species search."""
        text = self.search_input.text().strip()
        
        if len(text) < 2 or not self.uksi_model:
            return
        
        self.results_list.clear()
        
        # Search UKSI; when that finds nothing, the shared suggestions (synonyms, close
        # spellings: 'Rutpela maculta' -> Rutpela maculata)
        from shared.species_lookup import parse_qualifier, search_candidates
        text = parse_qualifier(text)[1]
        results = self.uksi_model.search_species(text, limit=20)
        if not results:
            try:
                results = search_candidates(self.uksi_model, text, 20)
            except Exception as e:
                print(f"[SpeciesSearchDialog] suggestions failed: {e}")
        
        for result in results:
            # Format: "Scientific name - Common name (Family)"
            display_parts = [result.scientific_name]
            if result.common_name:
                display_parts.append(f"- {result.common_name}")
            if result.family:
                display_parts.append(f"({result.family})")
            
            display_text = " ".join(display_parts)
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, {
                'tvk': result.tvk,
                'scientific_name': result.scientific_name,
                'common_name': result.common_name or '',
                'order_name': result.order_name or '',
                'family': result.family or '',
                'kingdom': getattr(result, 'kingdom', '') or '',
                'rank': getattr(result, 'rank', '') or '',
            })
            
            # Make scientific name italic
            font = item.font()
            font.setItalic(True)
            item.setFont(font)
            
            self.results_list.addItem(item)
    
    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle single click on result item."""
        t = theme()
        
        self._selected_species = item.data(Qt.ItemDataRole.UserRole)
        if self._selected_species:
            self.selected_label.setText(
                f"Selected: {self._selected_species['scientific_name']}"
            )
            self.selected_label.setStyleSheet(f"""
                padding: 8px;
                background-color: {t.get('success_bg_light')};
                border-radius: 4px;
                color: {t.get('success')};
                font-weight: 600;
            """)
            self.select_btn.setEnabled(True)
    
    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle double-click to immediately select."""
        self._on_item_clicked(item)
        self._on_select()
    
    def _on_select(self):
        """Confirm selection and close dialog."""
        if self._selected_species:
            self.species_selected.emit(self._selected_species)
            self.accept()
    
    def get_selected_species(self) -> Optional[Dict]:
        """Get the selected species data."""
        return self._selected_species

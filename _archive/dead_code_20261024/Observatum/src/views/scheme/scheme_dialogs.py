"""
Scheme Dialog Components.

Dialogs for Recording Scheme tab:
- SchemeRecordDetailDialog: Record detail modal
- SaveFilterDialog: Save filter dialog
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QLineEdit
)

from ...themes import theme


class SaveFilterDialog(QDialog):
    """Dialog for saving current filter configuration."""
    
    def __init__(self, current_filters: dict, parent=None):
        super().__init__(parent)
        self.current_filters = current_filters
        self.setWindowTitle("Save Filter")
        self.setFixedWidth(350)
        self.setModal(True)
        self._setup_ui()
    
    def _setup_ui(self):
        t = theme()
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Name input
        layout.addWidget(QLabel("Filter Name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Oxfordshire records, Pending 2024...")
        self.name_input.setMinimumHeight(32)
        layout.addWidget(self.name_input)
        
        # Current filters display
        filters_frame = QFrame()
        filters_frame.setStyleSheet(f"background-color: {t.get('surface_alt')}; border-radius: {t.get('radius_md')}; padding: 12px;")
        filters_layout = QVBoxLayout(filters_frame)
        
        filters_header = QLabel("CURRENT FILTER SETTINGS")
        filters_header.setStyleSheet(f"font-size: {t.font_size('xs')}; font-weight: bold; color: {t.get('text_secondary')}; letter-spacing: 1px;")
        filters_layout.addWidget(filters_header)
        
        # Show active filters
        active_filters = []
        if self.current_filters.get('source') != 'all':
            active_filters.append(f"Source: {self.current_filters['source']}")
        if self.current_filters.get('species'):
            active_filters.append(f"Species: {self.current_filters['species']}")
        if self.current_filters.get('location'):
            active_filters.append(f"Location: {self.current_filters['location']}")
        if self.current_filters.get('date_from'):
            active_filters.append(f"Date From: {self.current_filters['date_from']}")
        if self.current_filters.get('date_to'):
            active_filters.append(f"Date To: {self.current_filters['date_to']}")
        if self.current_filters.get('subfamily'):
            active_filters.append(f"Subfamily: {self.current_filters['subfamily']}")
        if self.current_filters.get('vice_county'):
            active_filters.append(f"Vice County: {self.current_filters['vice_county']}")
        if self.current_filters.get('status'):
            active_filters.append(f"Status: {self.current_filters['status']}")
        
        if active_filters:
            for f in active_filters:
                lbl = QLabel(f)
                lbl.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('base')};")
                filters_layout.addWidget(lbl)
        else:
            no_filters = QLabel("No filters applied")
            no_filters.setStyleSheet(f"color: {t.get('text_muted')}; font-style: italic;")
            filters_layout.addWidget(no_filters)
        
        layout.addWidget(filters_frame)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save Filter")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('primary')};
                color: {t.get('primary_text')};
                border: none;
                border-radius: {t.get('radius_md')};
                padding: 10px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {t.get('primary_hover')}; }}
        """)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn, 1)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def get_filter_name(self) -> str:
        """Get entered filter name."""
        return self.name_input.text().strip()

"""
Map Filter Panel component for Observatum V2.

Provides species search, date range filters, vice county selection,
display style options, and grid squares list.
"""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QScrollArea, QWidget
)
from PySide6.QtCore import Qt, Signal

from ...models.database import get_database
from ...themes import theme
from ...core.config import TabColors


class MapFilterPanel(QFrame):
    """Side panel with map filters."""
    
    species_selected = Signal(dict)
    species_cleared = Signal()
    generate_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_species = None
        self._accent = TabColors.MAPPING
        self._accent_light = TabColors.MAPPING_LIGHT
        self._accent_dark = TabColors.MAPPING_DARK
        self._setup_ui()
    
    def _setup_ui(self):
        t = theme()
        self.setFixedWidth(280)
        self.setStyleSheet(f"background-color: {t.get('surface')}; border-right: 1px solid {t.get('border')};")
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Title
        title = QLabel("MAP FILTERS")
        title.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: 11px; letter-spacing: 1px;")
        layout.addWidget(title)
        
        # Species search
        self._setup_species_search(layout)
        
        # Selected species card
        self._setup_selected_card(layout)
        
        # Date range
        self._setup_date_range(layout)
        
        # Quick date presets
        self._setup_date_presets(layout)
        
        # Vice County
        self._setup_vice_county(layout)
        
        # Display style
        self._setup_display_style(layout)
        
        # Generate button
        self._setup_generate_button(layout)
        
        # Grid squares list
        self._setup_grid_list(layout)
        
        layout.addStretch()
        
        scroll.setWidget(container)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
    
    def _setup_species_search(self, layout: QVBoxLayout):
        """Set up species search section."""
        t = theme()
        species_group = QVBoxLayout()
        species_group.setSpacing(4)
        
        species_label = QLabel("Species")
        species_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
        species_group.addWidget(species_label)
        
        self.species_search = QLineEdit()
        self.species_search.setPlaceholderText("Search your species...")
        self.species_search.setMinimumHeight(32)
        self.species_search.textChanged.connect(self._on_search_changed)
        species_group.addWidget(self.species_search)
        
        # Search results dropdown
        self.results_frame = QFrame()
        self.results_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
            }}
        """)
        self.results_frame.hide()
        self.results_layout = QVBoxLayout(self.results_frame)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(0)
        species_group.addWidget(self.results_frame)
        
        layout.addLayout(species_group)
    
    def _setup_selected_card(self, layout: QVBoxLayout):
        """Set up selected species card."""
        t = theme()
        self.selected_card = QFrame()
        self.selected_card.setStyleSheet(f"""
            QFrame {{
                background-color: {self._accent_light};
                border: 1px solid {self._accent};
                border-radius: {t.get('radius_md')};
            }}
        """)
        self.selected_card.hide()
        
        selected_layout = QVBoxLayout(self.selected_card)
        selected_layout.setContentsMargins(12, 8, 12, 8)
        
        selected_header = QHBoxLayout()
        self.selected_name = QLabel()
        self.selected_name.setStyleSheet("font-weight: 600; font-style: italic;")
        selected_header.addWidget(self.selected_name)
        selected_header.addStretch()
        
        clear_btn = QPushButton("✕")
        clear_btn.setFixedSize(20, 20)
        clear_btn.setStyleSheet(f"border: none; color: {t.get('text_secondary')};")
        clear_btn.clicked.connect(self._clear_species)
        selected_header.addWidget(clear_btn)
        
        selected_layout.addLayout(selected_header)
        
        self.selected_common = QLabel()
        self.selected_common.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px;")
        selected_layout.addWidget(self.selected_common)
        
        self.selected_records = QLabel()
        self.selected_records.setStyleSheet(f"color: {self._accent_dark}; font-size: 12px; margin-top: 4px;")
        selected_layout.addWidget(self.selected_records)
        
        layout.addWidget(self.selected_card)
    
    def _setup_date_range(self, layout: QVBoxLayout):
        """Set up date range section."""
        t = theme()
        date_group = QVBoxLayout()
        date_group.setSpacing(4)
        
        date_label = QLabel("Date Range")
        date_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
        date_group.addWidget(date_label)
        
        date_row = QHBoxLayout()
        self.date_from = QLineEdit()
        self.date_from.setPlaceholderText("From")
        self.date_from.setMinimumHeight(28)
        date_row.addWidget(self.date_from)
        
        self.date_to = QLineEdit()
        self.date_to.setPlaceholderText("To")
        self.date_to.setMinimumHeight(28)
        date_row.addWidget(self.date_to)
        
        date_group.addLayout(date_row)
        layout.addLayout(date_group)
    
    def _setup_date_presets(self, layout: QVBoxLayout):
        """Set up quick date preset buttons."""
        t = theme()
        presets_group = QVBoxLayout()
        presets_group.setSpacing(4)
        
        presets_label = QLabel("Quick Select")
        presets_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
        presets_group.addWidget(presets_label)
        
        presets_row = QHBoxLayout()
        presets_row.setSpacing(4)
        for preset in ['2025', '2024', '2023', '2020-25', 'All']:
            btn = QPushButton(preset)
            btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 4px 8px;
                    border: 1px solid {t.get('border')};
                    border-radius: {t.get('radius_sm')};
                    font-size: 11px;
                }}
                QPushButton:hover {{ background-color: {t.get('hover')}; }}
            """)
            btn.clicked.connect(lambda checked, p=preset: self._on_date_preset(p))
            presets_row.addWidget(btn)
        presets_group.addLayout(presets_row)
        layout.addLayout(presets_group)
    
    def _setup_vice_county(self, layout: QVBoxLayout):
        """Set up vice county selector."""
        t = theme()
        vc_group = QVBoxLayout()
        vc_group.setSpacing(4)
        
        vc_label = QLabel("Vice County")
        vc_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
        vc_group.addWidget(vc_label)
        
        self.vc_combo = QComboBox()
        self.vc_combo.setMinimumHeight(28)
        self._populate_vc_combo()
        vc_group.addWidget(self.vc_combo)
        layout.addLayout(vc_group)
    
    def _populate_vc_combo(self):
        """Populate VC dropdown from user's recorded vice counties."""
        try:
            import sqlite3
            import paths
            conn = sqlite3.connect(str(paths.OBSERVATUM_DB))
            # Get VCs from observations + specimens + recording_scheme
            rows = conn.execute("""
                SELECT DISTINCT vc_number, vice_county FROM (
                    SELECT vc_number, vice_county FROM observations
                    WHERE vc_number IS NOT NULL AND vc_number != ''
                    UNION
                    SELECT vc_number, vice_county FROM specimens
                    WHERE vc_number IS NOT NULL AND vc_number != ''
                )
                ORDER BY CAST(vc_number AS INTEGER)
            """).fetchall()
            conn.close()

            items = []
            for r in rows:
                vc_num = r[0]
                vc_name = r[1] or ''
                if vc_name:
                    items.append(f"VC{vc_num} - {vc_name}")
                else:
                    items.append(f"VC{vc_num}")

            if items:
                self.vc_combo.addItems(items)
            else:
                self.vc_combo.addItem("No VCs found")
        except Exception as e:
            self.vc_combo.addItems(['VC23 - Oxfordshire'])
            print(f"[FilterPanel] Error loading VCs: {e}")

    def _setup_display_style(self, layout: QVBoxLayout):
        """Set up display style selector."""
        t = theme()
        style_group = QVBoxLayout()
        style_group.setSpacing(4)
        
        style_label = QLabel("Display Style")
        style_label.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
        style_group.addWidget(style_label)
        
        self.style_combo = QComboBox()
        self.style_combo.setMinimumHeight(28)
        self.style_combo.addItems([
            'Presence (filled squares)',
            'Density (colour gradient)',
            'Date classes (by decade)'
        ])
        style_group.addWidget(self.style_combo)
        layout.addLayout(style_group)
    
    def _on_date_preset(self, preset: str):
        """Handle date preset button click."""
        if preset == 'All':
            self.date_from.setText('')
            self.date_to.setText('')
        elif '-' in preset:
            parts = preset.split('-')
            self.date_from.setText(f"20{parts[0]}" if len(parts[0]) == 2 else parts[0])
            self.date_to.setText(f"20{parts[1]}" if len(parts[1]) == 2 else parts[1])
        else:
            self.date_from.setText(preset)
            self.date_to.setText(preset)
        self.generate_requested.emit()

    def _setup_generate_button(self, layout: QVBoxLayout):
        """Set up generate map button."""
        t = theme()
        self.generate_btn = QPushButton("Generate Map")
        self.generate_btn.setMinimumHeight(36)
        self.generate_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._accent};
                color: white;
                border: none;
                border-radius: {t.get('radius_md')};
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: {self._accent_dark}; }}
        """)
        self.generate_btn.clicked.connect(self.generate_requested.emit)
        layout.addWidget(self.generate_btn)
    
    def _setup_grid_list(self, layout: QVBoxLayout):
        """Set up grid squares list section."""
        t = theme()
        grid_group = QVBoxLayout()
        grid_group.setSpacing(8)
        
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {t.get('separator')};")
        grid_group.addWidget(sep)
        
        self.grid_title = QLabel("GRID SQUARES (0)")
        self.grid_title.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: 11px; letter-spacing: 1px;")
        grid_group.addWidget(self.grid_title)
        
        self.grid_list = QVBoxLayout()
        self.grid_list.setSpacing(4)
        grid_group.addLayout(self.grid_list)
        
        layout.addLayout(grid_group)
    
    def _on_search_changed(self, text: str):
        """Handle species search - queries your recorded species."""
        # Clear existing results
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if len(text) < 2:
            self.results_frame.hide()
            return
        
        # Search your observations for matching species
        matches = self._search_recorded_species(text)
        
        if not matches:
            self.results_frame.hide()
            return
        
        self.results_frame.show()
        
        for species in matches[:8]:
            item = self._create_result_item(species)
            self.results_layout.addWidget(item)
    
    def _create_result_item(self, species: dict) -> QFrame:
        """Create a search result item widget."""
        t = theme()
        item = QFrame()
        item.setStyleSheet(f"""
            QFrame {{
                border-bottom: 1px solid {t.get('separator')};
            }}
            QFrame:hover {{ background-color: {self._accent_light}; }}
        """)
        item.setCursor(Qt.CursorShape.PointingHandCursor)
        
        item_layout = QHBoxLayout(item)
        item_layout.setContentsMargins(8, 6, 8, 6)
        
        info = QVBoxLayout()
        name = QLabel(f"<i>{species['scientific_name']}</i>")
        name.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')};")
        info.addWidget(name)
        
        if species.get('common_name'):
            common = QLabel(species['common_name'])
            common.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px;")
            info.addWidget(common)
        
        item_layout.addLayout(info)
        item_layout.addStretch()
        
        count = QLabel(str(species['records']))
        count.setStyleSheet(f"background-color: {t.get('surface_alt')}; padding: 2px 6px; border-radius: {t.get('radius_sm')}; font-size: 11px;")
        item_layout.addWidget(count)
        
        # Make clickable
        item.mousePressEvent = lambda e, s=species: self._select_species(s)
        
        return item
    
    def _search_recorded_species(self, text: str) -> list:
        """Search for species in your observations."""
        try:
            db = get_database()
            query = """
                SELECT species_name, species_tvk, common_name, COUNT(*) as record_count
                FROM observations
                WHERE species_name LIKE ? OR common_name LIKE ?
                GROUP BY species_tvk
                ORDER BY record_count DESC
                LIMIT 10
            """
            search_term = f"%{text}%"
            results = db.execute_main(query, (search_term, search_term))
            
            species_list = []
            for row in results:
                species_list.append({
                    'scientific_name': row[0],
                    'tvk': row[1],
                    'common_name': row[2],
                    'records': row[3]
                })
            return species_list
        except Exception as e:
            print(f"Error searching species: {e}")
            return []
    
    def _select_species(self, species: dict):
        """Select a species."""
        self._selected_species = species
        self.species_search.setText(species['scientific_name'])
        self.results_frame.hide()
        
        # Show selected card
        self.selected_name.setText(species['scientific_name'])
        common = species.get('common_name', '')
        self.selected_common.setText(common if common else '')
        self.selected_common.setVisible(bool(common))
        self.selected_records.setText(f"{species['records']} records")
        self.selected_card.show()
        
        self.species_selected.emit(species)
    
    def _clear_species(self):
        """Clear selected species."""
        self._selected_species = None
        self.species_search.clear()
        self.selected_card.hide()
        self.species_cleared.emit()
    
    def set_grid_squares(self, squares: list):
        """Update the grid squares list."""
        t = theme()
        # Clear existing
        while self.grid_list.count():
            item = self.grid_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.grid_title.setText(f"GRID SQUARES ({len(squares)})")
        
        for sq in squares:
            row = QHBoxLayout()
            
            grid_label = QLabel(sq['grid'])
            grid_label.setStyleSheet(f"font-family: monospace; color: {t.get('text_heading')};")
            row.addWidget(grid_label)
            
            row.addStretch()
            
            count_label = QLabel(f"{sq['count']} records")
            count_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px;")
            row.addWidget(count_label)
            
            container = QWidget()
            container.setLayout(row)
            self.grid_list.addWidget(container)
    
    def get_selected_species(self):
        """Get the currently selected species."""
        return self._selected_species

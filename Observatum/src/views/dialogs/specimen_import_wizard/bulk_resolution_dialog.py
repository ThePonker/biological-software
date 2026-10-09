"""
Bulk Species Resolution Dialog for Specimen Import Wizard.

Dialog for resolving multiple unmatched species at once.
Shows all unique unmatched species names with search functionality
and suggested matches. Nothing is matched until the user applies a match.
(Saving aliases was removed 9 Oct 2026: UKSI's synonyms cover them.)

Split from specimen_import_wizard.py for maintainability.
"""

from typing import Dict, List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from ....themes import theme
from ....core.config import TabColors, ButtonColors


class BulkSpeciesResolutionDialog(QDialog):
    """
    Dialog for resolving multiple unmatched species at once.
    
    Shows all unique unmatched species names with search functionality
    and suggested matches.
    """
    
    def __init__(self, parent=None, uksi_model=None, unmatched_species: List[str] = None,
                 accent=None, accent_light=None, accent_dark=None):
        super().__init__(parent)
        self.uksi_model = uksi_model
        self.unmatched_species = unmatched_species or []
        
        # Tab colors for Collection
        self._accent = accent or TabColors.COLLECTION
        self._accent_light = accent_light or TabColors.COLLECTION_LIGHT
        self._accent_dark = accent_dark or TabColors.COLLECTION_DARK
        
        # Store resolutions: {original_name: {uksi_data}}
        self.resolutions: Dict[str, dict] = {}
        
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_search)
        
        self.setWindowTitle("Resolve Unmatched Species")
        self.setMinimumSize(800, 600)
        self.setModal(True)
        
        self._setup_ui()
        self._populate_species_list()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        t = theme()
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Header
        header = QLabel(f"<b>{len(self.unmatched_species)}</b> species could not be matched to UKSI")
        header.setStyleSheet(f"font-size: 14px; color: {t.get('error')};")
        layout.addWidget(header)
        
        instructions = QLabel(
            "For each name below, choose the correct UKSI taxon from the suggestions, or search "
            "for it. A name stays unmatched (and is not imported) until you apply a match."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(f"color: {t.get('text_secondary')};")
        layout.addWidget(instructions)
        
        # Main content - split view
        content = QHBoxLayout()
        content.setSpacing(16)
        
        # Left panel - Species list
        left_panel = QVBoxLayout()
        left_label = QLabel("Unmatched Species:")
        left_label.setStyleSheet("font-weight: 600;")
        left_panel.addWidget(left_label)
        
        self.species_list = QListWidget()
        self.species_list.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_md')};
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {t.get('surface_alt')};
            }}
            QListWidget::item:selected {{
                background-color: {self._accent_light};
                color: {self._accent_dark};
            }}
        """)
        self.species_list.currentItemChanged.connect(self._on_species_selected)
        left_panel.addWidget(self.species_list)
        
        # Stats
        self.stats_label = QLabel("0 / 0 resolved")
        self.stats_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
        left_panel.addWidget(self.stats_label)
        
        content.addLayout(left_panel, 1)
        
        # Right panel - Search and match
        right_panel = QVBoxLayout()
        
        # Current species being resolved
        self.current_species_label = QLabel("Select a species to resolve")
        self.current_species_label.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 600;
            padding: 8px;
            background-color: {self._accent_light};
            border-radius: {t.get('radius_sm')};
            color: {self._accent_dark};
        """)
        right_panel.addWidget(self.current_species_label)
        
        # Search input
        search_label = QLabel("Search UKSI:")
        search_label.setStyleSheet("font-weight: 600; margin-top: 8px;")
        right_panel.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to search UKSI...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px 12px;
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_md')};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 2px solid {self._accent};
            }}
        """)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        right_panel.addWidget(self.search_input)
        
        # Search results
        results_label = QLabel("Search Results:")
        results_label.setStyleSheet("font-weight: 600; margin-top: 8px;")
        right_panel.addWidget(results_label)
        
        self.results_list = QListWidget()
        self.results_list.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_md')};
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {t.get('surface_alt')};
            }}
            QListWidget::item:selected {{
                background-color: {t.get('success_bg')};
                color: {t.get('success')};
            }}
            QListWidget::item:hover {{
                background-color: {t.get('hover')};
            }}
        """)
        self.results_list.itemDoubleClicked.connect(self._on_result_double_clicked)
        right_panel.addWidget(self.results_list, 1)
        
        # Apply button for current species (Moss Green - primary action)
        self.apply_btn = QPushButton("Apply Match →")
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.setEnabled(False)
        self.apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ButtonColors.PRIMARY};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: {t.get('radius_md')};
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {ButtonColors.PRIMARY_HOVER}; }}
            QPushButton:disabled {{ background-color: {t.get('text_muted')}; }}
        """)
        self.apply_btn.clicked.connect(self._apply_match)
        right_panel.addWidget(self.apply_btn)
        
        # Skip button (Secondary - Warm Gray outlined)
        self.skip_btn = QPushButton("Skip (leave unmatched)")
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_btn.setStyleSheet(f"""
            QPushButton {{
                color: {t.get('text_secondary')};
                border: 1px solid {t.get('border')};
                padding: 6px 12px;
                border-radius: {t.get('radius_md')};
            }}
            QPushButton:hover {{
                background-color: {t.get('surface_alt')};
            }}
        """)
        self.skip_btn.clicked.connect(self._skip_current)
        right_panel.addWidget(self.skip_btn)
        
        content.addLayout(right_panel, 2)
        layout.addLayout(content, 1)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel Resolve")
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        # Continue button (Tab accent - navigation action)
        self.done_btn = QPushButton("Continue with Resolved Species")
        self.done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.done_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._accent};
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: {t.get('radius_md')};
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {self._accent_dark}; }}
        """)
        self.done_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.done_btn)
        
        layout.addLayout(button_layout)
    
    def _populate_species_list(self):
        """Populate the list of unmatched species."""
        t = theme()
        self.species_list.clear()
        
        for species in self.unmatched_species:
            item = QListWidgetItem(species)
            item.setData(Qt.ItemDataRole.UserRole, species)
            
            # Mark as unresolved initially (error color)
            item.setForeground(QColor(t.get('error')))
            
            self.species_list.addItem(item)
        
        self._update_stats()
    
    def _on_species_selected(self, current, previous):
        """Handle species selection in the list."""
        t = theme()
        if not current:
            return
        
        species = current.data(Qt.ItemDataRole.UserRole)
        self.current_species_label.setText(f"Resolving: {species}")
        
        # Pre-populate search with the name, without cf. / agg. (they defeat the search)
        from shared.species_lookup import parse_qualifier
        self.search_input.setText(parse_qualifier(species)[1])
        self._do_search()
        
        # Check if already resolved
        if species in self.resolutions:
            resolution = self.resolutions[species]
            self.current_species_label.setText(
                f"✓ {species} → {resolution.get('scientific_name', 'Unknown')}"
            )
            self.current_species_label.setStyleSheet(f"""
                font-size: 14px;
                font-weight: 600;
                padding: 8px;
                background-color: {t.get('success_bg')};
                border-radius: {t.get('radius_sm')};
                color: {t.get('success')};
            """)
    
    def _on_search_text_changed(self, text: str):
        """Handle search text changes with debounce."""
        if len(text) >= 2:
            self._search_timer.start(300)
        else:
            self.results_list.clear()
    
    def _do_search(self):
        """Execute the UKSI search."""
        text = self.search_input.text().strip()
        
        if len(text) < 2 or not self.uksi_model:
            return
        
        self.results_list.clear()
        
        # Search UKSI; when that finds nothing, the shared suggestions (synonyms, close
        # spellings: 'Rutpela maculta' -> Rutpela maculata)
        results = self.uksi_model.search_species(text, limit=15)
        if not results:
            from shared.species_lookup import search_candidates
            try:
                results = search_candidates(self.uksi_model, text, 15)
            except Exception as e:
                print(f"[BulkSpeciesResolution] suggestions failed: {e}")
        
        # Also search for aggregate/sensu lato entries
        if hasattr(self, '_uksi_db') or (hasattr(self.uksi_model, 'db') and self.uksi_model.db):
            try:
                db = self.uksi_model.db
                agg_results = db.execute_uksi(
                    "SELECT t.tvk, t.scientific_name, t.rank, t.kingdom, "
                    "t.\"order\" as order_name, t.family, cn.common_name "
                    "FROM taxa t LEFT JOIN common_names cn ON t.tvk = cn.tvk "
                    "WHERE t.scientific_name LIKE ? "
                    "AND (t.rank = 'Species sensu lato' OR t.rank = 'Species aggregate') "
                    "LIMIT 5",
                    (text + "%",)
                )
                if agg_results:
                    for ar in agg_results:
                        # Check not already in results
                        existing_tvks = {r.tvk for r in results}
                        if ar["tvk"] not in existing_tvks:
                            class AggResult:
                                pass
                            obj = AggResult()
                            obj.scientific_name = ar["scientific_name"]
                            obj.tvk = ar["tvk"]
                            obj.rank = ar["rank"]
                            obj.common_name = ar["common_name"] if ar["common_name"] else ""
                            obj.order_name = ar["order_name"] if ar["order_name"] else ""
                            obj.family = ar["family"] if ar["family"] else ""
                            results.append(obj)
            except Exception:
                pass

        # Check for duplicate scientific names needing disambiguation
        name_counts = {}
        for result in results:
            name_counts[result.scientific_name] = name_counts.get(result.scientific_name, 0) + 1

        for result in results:
            # Format display
            display_parts = [result.scientific_name]
            if hasattr(result, 'rank') and result.rank:
                if result.rank != 'Species':
                    display_parts.append(f"[{result.rank}]")
                elif name_counts.get(result.scientific_name, 0) > 1:
                    display_parts.append("[s.s.]")
            if result.common_name:
                display_parts.append(f"- {result.common_name}")
            if result.family:
                display_parts.append(f"({result.family})")
            
            item = QListWidgetItem(" ".join(display_parts))
            item.setData(Qt.ItemDataRole.UserRole, {
                'scientific_name': result.scientific_name,
                'tvk': result.tvk,
                'common_name': result.common_name or '',
                'order_name': result.order_name or '',
                'family': result.family or '',
                'subfamily': getattr(result, 'subfamily', '') or '',
                'kingdom': getattr(result, 'kingdom', '') or '',
                'rank': getattr(result, 'rank', '') or '',
            })
            
            # Make scientific name italic
            font = item.font()
            font.setItalic(True)
            item.setFont(font)
            
            self.results_list.addItem(item)
        
        self.apply_btn.setEnabled(False)
        self.results_list.itemClicked.connect(self._on_result_clicked)
    
    def _on_result_clicked(self, item):
        """Handle click on a search result."""
        self.apply_btn.setEnabled(True)
    
    def _on_result_double_clicked(self, item):
        """Handle double-click to immediately apply match."""
        self._apply_match()
    
    def _apply_match(self):
        """Apply the selected match to the current species."""
        t = theme()
        current_item = self.species_list.currentItem()
        result_item = self.results_list.currentItem()
        
        if not current_item or not result_item:
            return
        
        original_species = current_item.data(Qt.ItemDataRole.UserRole)
        uksi_data = result_item.data(Qt.ItemDataRole.UserRole)
        
        # Store resolution
        self.resolutions[original_species] = uksi_data
        
        # Update UI - mark as resolved (success color)
        current_item.setForeground(QColor(t.get('success')))
        current_item.setText(f"✓ {original_species} → {uksi_data['scientific_name']}")
        
        self.current_species_label.setText(
            f"✓ Matched: {original_species} → {uksi_data['scientific_name']}"
        )
        self.current_species_label.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 600;
            padding: 8px;
            background-color: {t.get('success_bg')};
            border-radius: {t.get('radius_sm')};
            color: {t.get('success')};
        """)
        
        self._update_stats()
        
        # Move to next unresolved species
        self._select_next_unresolved()
    
    def _skip_current(self):
        """Skip the current species (import without TVK)."""
        t = theme()
        current_item = self.species_list.currentItem()
        if not current_item:
            return
        
        original_species = current_item.data(Qt.ItemDataRole.UserRole)
        
        # Mark as skipped (empty resolution)
        self.resolutions[original_species] = {'skipped': True}
        
        # Update UI (warning color)
        current_item.setForeground(QColor(t.get('warning')))
        current_item.setText(f"⚠ {original_species} (skipped)")
        
        self._update_stats()
        self._select_next_unresolved()
    
    def _select_next_unresolved(self):
        """Select the next unresolved species in the list."""
        current_row = self.species_list.currentRow()
        
        # Look for next unresolved
        for i in range(current_row + 1, self.species_list.count()):
            item = self.species_list.item(i)
            species = item.data(Qt.ItemDataRole.UserRole)
            if species and species not in self.resolutions:
                self.species_list.setCurrentRow(i)
                return
        
        # Wrap around to beginning
        for i in range(0, current_row):
            item = self.species_list.item(i)
            species = item.data(Qt.ItemDataRole.UserRole)
            if species and species not in self.resolutions:
                self.species_list.setCurrentRow(i)
                return
    
    def _update_stats(self):
        """Update the resolution statistics."""
        total = len(self.unmatched_species)
        resolved = len([r for r in self.resolutions.values() if not r.get('skipped')])
        skipped = len([r for r in self.resolutions.values() if r.get('skipped')])
        
        self.stats_label.setText(
            f"{resolved} resolved, {skipped} skipped / {total} total"
        )
    
    def get_resolutions(self) -> Dict[str, dict]:
        """Get all resolutions (excluding skipped)."""
        return {k: v for k, v in self.resolutions.items() if not v.get('skipped')}
    
    def get_aliases_to_save(self) -> Dict[str, dict]:
        """Saved aliases are no longer written (9 Oct 2026); kept so old callers get {}."""
        return {}

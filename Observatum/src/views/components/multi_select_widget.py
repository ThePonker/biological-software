"""
Multi-Select Widget Component.

Reusable checkbox list with search, select all, and count display.
Used throughout the Filter Wizard v2 for multi-selection filtering.
"""

from typing import List, Dict, Any, Optional, Set
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QCheckBox
)
from PySide6.QtCore import Signal, Qt

from ...themes import theme
from ...core.config import ButtonColors


class MultiSelectWidget(QWidget):
    """
    Multi-select widget with checkboxes.
    
    Features:
    - Search/filter items
    - Select All / Clear All buttons
    - Live count of selected items
    - Include/Exclude mode toggle
    - Scrollable list for many items
    
    Signals:
        selection_changed: Emitted when selection changes (selected_items: Set[str])
        mode_changed: Emitted when include/exclude mode changes (is_include: bool)
    """
    
    selection_changed = Signal(set)
    mode_changed = Signal(bool)
    
    def __init__(
        self,
        title: str = "Select Items",
        items: List[str] = None,
        show_search: bool = True,
        show_mode_toggle: bool = True,
        accent_color: str = None,
        max_visible_items: int = 8,
        parent=None
    ):
        super().__init__(parent)
        self._title = title
        self._items: List[str] = items or []
        self._show_search = show_search
        self._show_mode_toggle = show_mode_toggle
        self._accent_color = accent_color or ButtonColors.PRIMARY
        self._max_visible = max_visible_items
        
        # State
        self._selected: Set[str] = set()
        self._is_include_mode = True  # True = Include, False = Exclude
        self._checkboxes: Dict[str, QCheckBox] = {}
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the widget UI."""
        t = theme()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Header row: Title + Count
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        title_label = QLabel(self._title)
        title_label.setStyleSheet(f"""
            QLabel {{
                font-weight: 600;
                font-size: 13px;
                color: {t.get('text_primary')};
            }}
        """)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        self._count_label = QLabel("0 selected")
        self._count_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: {t.get('text_muted')};
            }}
        """)
        header_layout.addWidget(self._count_label)
        
        layout.addLayout(header_layout)
        
        # Include/Exclude toggle
        if self._show_mode_toggle:
            mode_layout = QHBoxLayout()
            mode_layout.setSpacing(4)
            
            self._include_btn = QPushButton("Include")
            self._exclude_btn = QPushButton("Exclude")
            
            for btn in [self._include_btn, self._exclude_btn]:
                btn.setCheckable(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedHeight(26)
            
            self._include_btn.setChecked(True)
            self._update_mode_button_styles()
            
            self._include_btn.clicked.connect(lambda: self._set_mode(True))
            self._exclude_btn.clicked.connect(lambda: self._set_mode(False))
            
            mode_layout.addWidget(self._include_btn)
            mode_layout.addWidget(self._exclude_btn)
            mode_layout.addStretch()
            
            layout.addLayout(mode_layout)
        
        # Search box
        if self._show_search:
            self._search_input = QLineEdit()
            self._search_input.setPlaceholderText("Search...")
            self._search_input.setClearButtonEnabled(True)
            self._search_input.textChanged.connect(self._filter_items)
            self._style_input(self._search_input)
            layout.addWidget(self._search_input)
        
        # Action buttons: Select All / Clear All
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        
        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._select_all_btn.clicked.connect(self._select_all)
        self._style_link_button(self._select_all_btn)
        actions_layout.addWidget(self._select_all_btn)
        
        self._clear_all_btn = QPushButton("Clear All")
        self._clear_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_all_btn.clicked.connect(self._clear_all)
        self._style_link_button(self._clear_all_btn)
        actions_layout.addWidget(self._clear_all_btn)
        
        actions_layout.addStretch()
        layout.addLayout(actions_layout)
        
        # Scrollable checkbox list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        # Calculate height based on max visible items
        item_height = 28
        scroll.setMinimumHeight(min(len(self._items), self._max_visible) * item_height + 10)
        scroll.setMaximumHeight(self._max_visible * item_height + 10)
        
        # Container for checkboxes
        self._checkbox_container = QWidget()
        self._checkbox_layout = QVBoxLayout(self._checkbox_container)
        self._checkbox_layout.setContentsMargins(4, 4, 4, 4)
        self._checkbox_layout.setSpacing(2)
        
        # Populate checkboxes
        self._populate_checkboxes()
        
        self._checkbox_layout.addStretch()
        scroll.setWidget(self._checkbox_container)
        
        # Style scroll area
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
            }}
            QWidget {{
                background-color: {t.get('surface')};
            }}
        """)
        
        layout.addWidget(scroll)
    
    def _populate_checkboxes(self):
        """Create checkboxes for all items."""
        t = theme()
        
        # Clear existing
        for cb in self._checkboxes.values():
            cb.deleteLater()
        self._checkboxes.clear()
        
        # Create checkboxes
        for item in sorted(self._items):
            cb = QCheckBox(item)
            cb.setChecked(item in self._selected)
            cb.stateChanged.connect(lambda state, i=item: self._on_checkbox_changed(i, state))
            cb.setStyleSheet(f"""
                QCheckBox {{
                    color: {t.get('text_primary')};
                    font-size: 12px;
                    padding: 4px 8px;
                    spacing: 8px;
                }}
                QCheckBox:hover {{
                    background-color: {t.get('hover')};
                    border-radius: 3px;
                }}
                QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border-radius: 3px;
                    border: 1px solid {t.get('border')};
                    background-color: {t.get('surface')};
                }}
                QCheckBox::indicator:checked {{
                    background-color: {self._accent_color};
                    border-color: {self._accent_color};
                }}
            """)
            
            self._checkboxes[item] = cb
            self._checkbox_layout.addWidget(cb)
    
    def _on_checkbox_changed(self, item: str, state: int):
        """Handle checkbox state change."""
        if state == Qt.CheckState.Checked.value:
            self._selected.add(item)
        else:
            self._selected.discard(item)
        
        self._update_count()
        self.selection_changed.emit(self._selected.copy())
    
    def _filter_items(self, text: str):
        """Filter visible checkboxes based on search text."""
        search_lower = text.lower().strip()
        
        for item, cb in self._checkboxes.items():
            visible = search_lower in item.lower() if search_lower else True
            cb.setVisible(visible)
    
    def _select_all(self):
        """Select all visible items."""
        for item, cb in self._checkboxes.items():
            if cb.isVisible():
                cb.setChecked(True)
    
    def _clear_all(self):
        """Clear all selections."""
        for cb in self._checkboxes.values():
            cb.setChecked(False)
    
    def _set_mode(self, is_include: bool):
        """Set include/exclude mode."""
        self._is_include_mode = is_include
        self._include_btn.setChecked(is_include)
        self._exclude_btn.setChecked(not is_include)
        self._update_mode_button_styles()
        self.mode_changed.emit(is_include)
    
    def _update_mode_button_styles(self):
        """Update include/exclude button styles based on state."""
        t = theme()
        
        active_style = f"""
            QPushButton {{
                background-color: {self._accent_color};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 500;
            }}
        """
        
        inactive_style = f"""
            QPushButton {{
                background-color: {t.get('surface')};
                color: {t.get('text_secondary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
            }}
        """
        
        self._include_btn.setStyleSheet(active_style if self._is_include_mode else inactive_style)
        self._exclude_btn.setStyleSheet(inactive_style if self._is_include_mode else active_style)
    
    def _update_count(self):
        """Update the selected count label."""
        count = len(self._selected)
        mode_text = "included" if self._is_include_mode else "excluded"
        
        if count == 0:
            self._count_label.setText("None selected")
        elif count == 1:
            self._count_label.setText(f"1 {mode_text}")
        else:
            self._count_label.setText(f"{count} {mode_text}")
    
    def _style_input(self, widget: QLineEdit):
        """Apply consistent input styling."""
        t = theme()
        widget.setStyleSheet(f"""
            QLineEdit {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 12px;
                color: {t.get('text_primary')};
            }}
            QLineEdit:focus {{
                border-color: {self._accent_color};
            }}
        """)
    
    def _style_link_button(self, btn: QPushButton):
        """Style as a text link button."""
        t = theme()
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {self._accent_color};
                font-size: 11px;
                padding: 2px 4px;
            }}
            QPushButton:hover {{
                text-decoration: underline;
            }}
        """)
    
    # ─────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────
    
    def set_items(self, items: List[str]):
        """Set the list of available items."""
        self._items = items
        self._selected.clear()
        self._populate_checkboxes()
        self._update_count()
    
    def add_items(self, items: List[str]):
        """Add items to the list (avoids duplicates)."""
        existing = set(self._items)
        for item in items:
            if item not in existing:
                self._items.append(item)
        self._populate_checkboxes()
    
    def get_selected(self) -> Set[str]:
        """Get the set of selected items."""
        return self._selected.copy()
    
    def set_selected(self, items: Set[str]):
        """Set the selected items."""
        self._selected = set(items)
        for item, cb in self._checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(item in self._selected)
            cb.blockSignals(False)
        self._update_count()
    
    def is_include_mode(self) -> bool:
        """Return True if in Include mode, False if Exclude mode."""
        return self._is_include_mode
    
    def set_include_mode(self, is_include: bool):
        """Set the include/exclude mode."""
        self._set_mode(is_include)
    
    def get_filter_config(self) -> Dict[str, Any]:
        """
        Get the full filter configuration.
        
        Returns:
            {
                'selected': ['item1', 'item2', ...],
                'mode': 'include' | 'exclude'
            }
        """
        return {
            'selected': list(self._selected),
            'mode': 'include' if self._is_include_mode else 'exclude'
        }
    
    def set_filter_config(self, config: Dict[str, Any]):
        """
        Set the full filter configuration.
        
        Args:
            config: {'selected': [...], 'mode': 'include'|'exclude'}
        """
        if 'selected' in config:
            self.set_selected(set(config['selected']))
        if 'mode' in config:
            self.set_include_mode(config['mode'] == 'include')
    
    def clear(self):
        """Clear all selections and reset mode."""
        self._clear_all()
        self._set_mode(True)
    
    def has_selection(self) -> bool:
        """Return True if any items are selected."""
        return len(self._selected) > 0
    
    def generate_sql_clause(self, column_name: str) -> Optional[str]:
        """
        Generate SQL WHERE clause for this filter.
        
        Args:
            column_name: The database column to filter on
            
        Returns:
            SQL clause string or None if no selection
            
        Example:
            # Include mode: "order_name IN ('Coleoptera', 'Diptera')"
            # Exclude mode: "order_name NOT IN ('Coleoptera', 'Diptera')"
        """
        if not self._selected:
            return None
        
        # Escape single quotes in values
        escaped = [v.replace("'", "''") for v in self._selected]
        values = ", ".join(f"'{v}'" for v in escaped)
        
        if self._is_include_mode:
            return f"{column_name} IN ({values})"
        else:
            return f"{column_name} NOT IN ({values})"
    
    def generate_sql_params(self, column_name: str) -> tuple:
        """
        Generate parameterized SQL clause and params.
        
        Returns:
            (clause_with_placeholders, params_tuple)
            
        Example:
            ('order_name IN (?, ?)', ('Coleoptera', 'Diptera'))
        """
        if not self._selected:
            return (None, ())
        
        placeholders = ", ".join("?" for _ in self._selected)
        params = tuple(self._selected)
        
        if self._is_include_mode:
            clause = f"{column_name} IN ({placeholders})"
        else:
            clause = f"{column_name} NOT IN ({placeholders})"
        
        return (clause, params)


class MultiSelectWithHierarchy(MultiSelectWidget):
    """
    Multi-select widget with parent-child hierarchy.
    
    Used for Order → Family relationships where selecting
    an Order shows only its Families.
    
    Additional Features:
    - Parent selection filters child items
    - Can show all children or filtered by parent
    """
    
    def __init__(
        self,
        title: str = "Select Items",
        hierarchy: Dict[str, List[str]] = None,
        show_search: bool = True,
        show_mode_toggle: bool = True,
        accent_color: str = None,
        max_visible_items: int = 8,
        parent=None
    ):
        # hierarchy: {'Coleoptera': ['Cerambycidae', 'Carabidae'], ...}
        self._hierarchy = hierarchy or {}
        self._current_parent_filter: Optional[str] = None
        
        # Flatten to get all items
        all_items = []
        for children in self._hierarchy.values():
            all_items.extend(children)
        
        super().__init__(
            title=title,
            items=sorted(set(all_items)),
            show_search=show_search,
            show_mode_toggle=show_mode_toggle,
            accent_color=accent_color,
            max_visible_items=max_visible_items,
            parent=parent
        )
    
    def filter_by_parent(self, parent: Optional[str]):
        """
        Filter visible items to those belonging to parent.
        
        Args:
            parent: Parent key (e.g., 'Coleoptera') or None to show all
        """
        self._current_parent_filter = parent
        
        if parent is None or parent not in self._hierarchy:
            # Show all
            for cb in self._checkboxes.values():
                cb.setVisible(True)
        else:
            # Show only children of this parent
            allowed = set(self._hierarchy.get(parent, []))
            for item, cb in self._checkboxes.items():
                cb.setVisible(item in allowed)
    
    def set_hierarchy(self, hierarchy: Dict[str, List[str]]):
        """Update the hierarchy mapping."""
        self._hierarchy = hierarchy
        
        # Update items list
        all_items = []
        for children in self._hierarchy.values():
            all_items.extend(children)
        
        self.set_items(sorted(set(all_items)))

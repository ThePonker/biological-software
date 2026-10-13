"""
What Filter Dialog.

ONE search box (Round 11, 13 Oct 2026, backlog 17): species, whole groups (genus, family,
superfamily, order -- by a common word like "ladybird" too), orders, families and taxon
groups, in one drop-down list drawn like Quick Entry's (what_search.py). Each pick becomes a
chip saying what it is ("Species: Turdus merula (Blackbird)", "Family: All Coccinellidae
(ladybirds)", "Taxon group: Butterflies (Lepidoptera)", "Order: Coleoptera").

The four boxes it replaces (Species, Taxon group, Order, Family) gave the keys species /
group / taxon_group / family; the chips keep them, so saved filters and every reader of the
filters (services/filter_builder.py, the tab's chip summary, the Mapping tab) are unchanged.
The chips are alternatives: a record matching ANY of them is kept, as before.
- Arrow keys to choose, Enter to add; Enter without a choice adds what the text names
  exactly, else the list's top row.
"""

from typing import Any, Dict, List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout,
    QWidget,
)

from ....core.config import ButtonColors
from ....themes import theme
from .chip_display import FilterChip  # I9: one copy
from .fuzzy import picking_from_popup
from .what_search import WhatChoices, WhatCompleter

# the order chips are listed in when a dialog opens on stored values
KEY_ORDER = ("species", "group", "taxon_group", "family")


class WhatFilterDialog(QDialog):
    """Dialog for filtering by taxonomy: one box that finds everything."""

    def __init__(
        self,
        accent_color: str = None,
        current_values: Dict[str, Any] = None,
        species_list: List[str] = None,
        taxon_groups: List[str] = None,
        family_list: List[str] = None,
        taxon_family_map: Dict[str, List[str]] = None,
        search_service=None,
        group_list: List[str] = None,
        species_info: Dict[str, dict] = None,
        parent=None
    ):
        """taxon_groups: the tab's ORDERS (stored under the key 'taxon_group', as always);
        group_list: its taxon groups (display labels, key 'group'); species_info: {name:
        {common, family, rank}} from the tab's records (filter_builder.tab_values)."""
        super().__init__(parent)
        self._accent_color = accent_color or ButtonColors.PRIMARY
        self._current = current_values or {}
        species, orders, families = species_list, taxon_groups, family_list
        groups = group_list
        if not orders and not families and not species:
            species, orders, families, groups, species_info = self._load_user_taxa()
        self._choices = WhatChoices(species or [], orders or [], families or [],
                                    groups or [], species_info)
        self._chips: Dict[str, List[FilterChip]] = {}

        self.setWindowTitle("Filter by What")
        self.setMinimumWidth(560)
        self.setMinimumHeight(440)
        self.setModal(True)

        self._setup_ui()
        self._load_current_values()

    @staticmethod
    def _load_user_taxa():
        """Fallback only (the wizard passes the tab's own lists): Observation Data's values,
        read-only (SRCH20)."""
        try:
            from ....core.config import Paths
            from ....services.filter_builder import tab_values
            v = tab_values(Paths.default_main_db(), "observations",
                           only=("species", "orders", "families", "groups", "species_info"))
            return v["species"], v["orders"], v["families"], v["groups"], v["species_info"]
        except Exception as e:
            print(f"[WhatFilterDialog] Error loading user taxa: {e}")
            return [], [], [], [], {}

    # ------------------------------------------------------------ layout

    def _setup_ui(self):
        t = theme()
        self.setStyleSheet(f"background-color: {t.get('background')};")

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 24)

        header = QLabel("🦋 What to Include")
        header.setStyleSheet(f"font-size: 18px; font-weight: 600; color: {self._accent_color}; "
                             "background: transparent;")
        layout.addWidget(header)

        desc = QLabel("Type a species, a group, a family, an order or a taxon group "
                      "(e.g. 'blackbird', 'ladybird', 'Cerambycidae', 'rut mac'). "
                      "Choose from the list or press Enter to add it. "
                      "Records matching any of your choices are kept.")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px; "
                           "background: transparent;")
        layout.addWidget(desc)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search species, groups, families, orders…")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 10px 14px;
                font-size: 13px;
                color: {t.get('text_primary')};
            }}
            QLineEdit:focus {{ border-color: {self._accent_color}; }}
        """)
        self._completer = WhatCompleter(self._choices, self._search_input,
                                        secondary=t.get('text_secondary'))
        self._search_input.setCompleter(self._completer)
        self._completer.activated.connect(self._on_completer_activated)
        self._search_input.returnPressed.connect(self._on_enter)
        layout.addWidget(self._search_input)

        sep = QFrame()            # a plain 1 px rule in the theme's border colour
        sep.setStyleSheet(f"background-color: {t.get('border')};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        layout.addLayout(self._chip_header(t))
        layout.addWidget(self._chip_area(t), 1)
        layout.addLayout(self._buttons(t))

    def _chip_header(self, t) -> QHBoxLayout:
        row = QHBoxLayout()
        self._chip_title = QLabel("Nothing chosen yet")
        self._chip_title.setStyleSheet(f"font-weight: 500; font-size: 12px; "
                                       f"color: {t.get('text_secondary')};")
        row.addWidget(self._chip_title)
        row.addStretch()
        self._clear_all_btn = QPushButton("Clear All")
        self._clear_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_all_btn.clicked.connect(self._clear_all_chips)
        # never the dialog's default button: Enter in a box must not press it (F77)
        self._clear_all_btn.setAutoDefault(False)
        self._clear_all_btn.setVisible(False)
        self._clear_all_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none;
                           color: {self._accent_color}; font-size: 11px; }}
            QPushButton:hover {{ text-decoration: underline; }}
        """)
        row.addWidget(self._clear_all_btn)
        return row

    def _chip_area(self, t) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setMinimumHeight(120)
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
        return scroll

    def _buttons(self, t) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        def button(text, style, slot):
            b = QPushButton(text)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            b.setAutoDefault(False)     # Enter in the box adds a chip, never closes
            b.setDefault(False)
            b.setStyleSheet(style)
            return b

        self._clear_btn = button("Clear", f"""
            QPushButton {{ background-color: transparent; color: {ButtonColors.DANGER};
                           border: 1px solid {ButtonColors.DANGER}; border-radius: 4px;
                           padding: 10px 20px; font-size: 13px; }}
            QPushButton:hover {{ background-color: {t.get('hover')}; }}
        """, self._clear_all_filters)
        row.addWidget(self._clear_btn)
        row.addStretch()
        self._cancel_btn = button("Cancel", f"""
            QPushButton {{ background-color: transparent; color: {ButtonColors.SECONDARY_TEXT};
                           border: 1px solid {ButtonColors.SECONDARY}; border-radius: 4px;
                           padding: 10px 24px; font-size: 13px; }}
            QPushButton:hover {{ background-color: {t.get('hover')}; }}
        """, self.reject)
        row.addWidget(self._cancel_btn)
        self._apply_btn = button("Apply Filters", f"""
            QPushButton {{ background-color: {ButtonColors.PRIMARY};
                           color: {ButtonColors.PRIMARY_TEXT}; border: none; border-radius: 4px;
                           padding: 10px 24px; font-size: 13px; font-weight: 500; }}
            QPushButton:hover {{ background-color: {ButtonColors.PRIMARY_HOVER}; }}
        """, self.accept)
        row.addWidget(self._apply_btn)
        return row

    # ------------------------------------------------------------ picking

    def _on_completer_activated(self, display_text: str):
        """A row chosen from the list (click, or arrow keys and Enter)."""
        choice = self._completer.choice(display_text)
        if choice is None:
            choice = self._choices.typed(display_text)
        if choice is not None:
            self._add_chip(choice.key, choice.value, choice.chip)
        QTimer.singleShot(50, self._search_input.clear)

    def _on_enter(self):
        """Enter in the box without a highlighted row: what the text names exactly, else
        the list's top row (WhatChoices.typed)."""
        if picking_from_popup(self._search_input):   # the activated handler adds the chip
            return
        choice = self._choices.typed(self._search_input.text())
        if choice is not None:
            self._add_chip(choice.key, choice.value, choice.chip)
            self._search_input.clear()
            popup = self._completer.popup()
            if popup is not None:
                popup.hide()

    # ------------------------------------------------------------ chips

    def _add_chip(self, category: str, value: str, display_text: str):
        if any(chip.get_value() == value for chip in self._chips.get(category, [])):
            return
        chip = FilterChip(category, value, display_text, self._accent_color)
        chip.removed.connect(self._remove_chip)
        self._chips.setdefault(category, []).append(chip)
        self._chip_layout.insertWidget(self._chip_layout.count() - 1, chip)
        self._update_chip_header()

    def _remove_chip(self, category: str, value: str):
        chips = self._chips.get(category)
        if not chips:
            return
        for chip in chips:
            if chip.get_value() == value:
                chips.remove(chip)
                self._chip_layout.removeWidget(chip)
                chip.deleteLater()
                break
        if not chips:
            del self._chips[category]
        self._update_chip_header()

    def _clear_all_chips(self):
        for chips in self._chips.values():
            for chip in chips:
                self._chip_layout.removeWidget(chip)
                chip.deleteLater()
        self._chips.clear()
        self._update_chip_header()

    def _clear_all_filters(self):
        self._clear_all_chips()
        self._search_input.clear()

    def _update_chip_header(self):
        count = sum(len(chips) for chips in self._chips.values())
        if count == 0:
            self._chip_title.setText("Nothing chosen yet")
            self._clear_all_btn.setVisible(False)
        else:
            self._chip_title.setText(f"Chosen ({count}) — records matching any of these:")
            self._clear_all_btn.setVisible(True)

    def chip_texts(self) -> List[str]:
        """The chips' texts, top to bottom (tests and the manual check)."""
        out = []
        for i in range(self._chip_layout.count()):
            w = self._chip_layout.itemAt(i).widget()
            if isinstance(w, FilterChip):
                out.append(w._display)
        return out

    def _load_current_values(self):
        """Stored values (a reopened dialog, a saved filter made with the four boxes) as
        chips in the one list, each saying what it is."""
        from ....services.filter_builder import as_list
        for key in KEY_ORDER:
            for value in as_list(self._current.get(key)):
                c = self._choices.for_value(key, value)
                self._add_chip(c.key, c.value, c.chip)

    def get_values(self) -> Dict[str, Any]:
        """{key: [values]} -- the keys the four boxes gave (species, group, taxon_group,
        family), so every reader of the filters is unchanged."""
        return {category: [chip.get_value() for chip in chips]
                for category, chips in self._chips.items()}

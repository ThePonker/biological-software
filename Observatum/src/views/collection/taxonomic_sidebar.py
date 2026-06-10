"""
Taxonomic Sidebar - Tree view of collection in systematic order.

Shows Order > Family > Species hierarchy with specimen counts.
Clicking filters the main table. Detail panel shows family info.
"""

import sqlite3
from typing import Optional, Dict, List, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTreeWidget, QTreeWidgetItem,
    QSplitter, QLabel, QFrame, QPushButton
)
from PySide6.QtCore import Qt, Signal

from .family_detail_panel import FamilyDetailPanel
from ...themes import theme
from ...core.config import TabColors
from ...utils.constants import INSECT_ORDER_POSITION


class TaxonomicSidebar(QWidget):
    """Collapsible sidebar showing taxonomic hierarchy of the collection."""

    # Emitted when user clicks a node: (filter_type, filter_value)
    # filter_type: 'all', 'order', 'family', 'species'
    filter_requested = Signal(str, str)

    def __init__(self, family_notes_repo, uksi_db_path: str, parent=None):
        super().__init__(parent)
        self._repo = family_notes_repo
        self._uksi_db_path = uksi_db_path
        self._tree_data = {}  # order -> {family -> {species -> count}}
        self._family_stats = {}  # family -> (specimen_count, species_count, genera)
        self._setup_ui()

    def _setup_ui(self):
        t = theme()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Internal splitter: tree on top, detail panel on bottom
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Top section: search + tree
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(4, 4, 4, 0)
        top_layout.setSpacing(4)

        # Search row: search box + reset button
        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(4)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter tree...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {t.get('border')};
                border-radius: 4px; padding: 4px 8px;
                font-size: 10px; background: {t.get('surface')};
            }}
            QLineEdit:focus {{ border-color: {TabColors.COLLECTION}; }}
        """)
        self.search_box.textChanged.connect(self._filter_tree)
        search_row.addWidget(self.search_box, 1)

        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setFixedHeight(26)
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {TabColors.COLLECTION};
                border-radius: 4px; padding: 2px 10px;
                font-size: 10px; color: {TabColors.COLLECTION};
            }}
            QPushButton:hover {{
                background: {TabColors.COLLECTION_LIGHT};
            }}
        """)
        self._reset_btn.setVisible(False)
        self._reset_btn.clicked.connect(self._on_reset)
        search_row.addWidget(self._reset_btn)

        top_layout.addLayout(search_row)

        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.setAnimated(True)
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                border: none;
                background: {t.get('surface')};
                font-size: 11px;
            }}
            QTreeWidget::item {{
                padding: 2px 4px;
            }}
            QTreeWidget::item:selected {{
                background-color: {TabColors.COLLECTION_LIGHT};
                color: {t.get('text_primary')};
            }}
            QTreeWidget::item:hover {{
                background-color: {t.get('hover', TabColors.COLLECTION_LIGHT)};
            }}
        """)
        self.tree.itemClicked.connect(self._on_item_clicked)
        top_layout.addWidget(self.tree, 1)

        splitter.addWidget(top_widget)

        # Bottom section: detail panel
        self.detail_panel = FamilyDetailPanel(
            self._repo, self._uksi_db_path)
        splitter.addWidget(self.detail_panel)

        # Splitter proportions: tree gets ~70%, detail ~30%
        splitter.setSizes([400, 150])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

    def build_tree(self, specimens: list):
        """
        Build the tree from specimen data.

        Args:
            specimens: List of dicts with keys:
                order_name, family, subfamily, species_name,
                species_tvk, taxonomic_sort_key, specimen_count
        """
        self.tree.clear()
        self._tree_data = {}
        self._family_stats = {}

        if not specimens:
            return

        # Group data by order > superfamily > family > species
        # Structure: {order: {superfamily: {family: {species: (count, sort_key)}}}}
        orders = {}
        for sp in specimens:
            order = sp.get('order_name', '') or 'Unknown'
            superfamily = sp.get('superfamily', '') or ''
            family = sp.get('family', '') or 'Unknown'
            species = sp.get('species_name', '')
            count = int(sp.get('specimen_count', 0) or 0)
            sort_key = int(sp.get('taxonomic_sort_key', 0) or 0)

            if order not in orders:
                orders[order] = {}
            if superfamily not in orders[order]:
                orders[order][superfamily] = {}
            if family not in orders[order][superfamily]:
                orders[order][superfamily][family] = {}
            orders[order][superfamily][family][species] = (count, sort_key)

        # Compute family stats
        for order, superfamilies in orders.items():
            for sf, families in superfamilies.items():
                for family, species_dict in families.items():
                    total_specimens = sum(int(c) for c, _ in species_dict.values())
                    total_species = len(species_dict)
                    genera = sorted(set(
                        s.split()[0] for s in species_dict.keys() if s and ' ' in s
                    ))
                    self._family_stats[family] = (total_specimens, total_species, genera)

        # Sort orders by INSECT_ORDER_POSITION
        sorted_orders = sorted(
            orders.keys(),
            key=lambda o: INSECT_ORDER_POSITION.get(o, 99)
        )

        # Add "All Specimens" node
        total_all = 0
        for superfamilies in orders.values():
            for families in superfamilies.values():
                for species_dict in families.values():
                    for c, _ in species_dict.values():
                        total_all += int(c)
        all_item = QTreeWidgetItem(self.tree, [f"All Specimens ({total_all:,})"])
        all_item.setData(0, Qt.ItemDataRole.UserRole, ('all', ''))
        font = all_item.font(0)
        font.setBold(True)
        all_item.setFont(0, font)

        # Build tree
        for order in sorted_orders:
            families = orders[order]
            superfamilies = orders[order]
            order_count = sum(
                int(c) for fams in superfamilies.values()
                for species_dict in fams.values()
                for c, _ in species_dict.values()
            )

            # Order node
            order_item = QTreeWidgetItem(self.tree, [f"{order} ({order_count:,})"])
            order_item.setData(0, Qt.ItemDataRole.UserRole, ('order', order))
            font = order_item.font(0)
            font.setBold(True)
            order_item.setFont(0, font)

            # Sort superfamilies by min sort_key
            sorted_sfs = sorted(
                superfamilies.items(),
                key=lambda sf: min(
                    int(sk) for fam in sf[1].values() for _, sk in fam.values()
                ) if any(sf[1].values()) else 0
            )

            for sf_name, families in sorted_sfs:
                # If superfamily exists, add as a node; otherwise families go directly under order
                if sf_name:
                    sf_count = sum(
                        int(c) for fam in families.values() for c, _ in fam.values()
                    )
                    sf_item = QTreeWidgetItem(order_item, [f"{sf_name} ({sf_count})"])
                    sf_item.setData(0, Qt.ItemDataRole.UserRole, ('superfamily', sf_name))
                    parent_for_families = sf_item
                else:
                    parent_for_families = order_item

                # Sort families by min sort_key
                sorted_families = sorted(
                    families.items(),
                    key=lambda f: min(int(sk) for _, sk in f[1].values()) if f[1] else 0
                )

                for family, species_dict in sorted_families:
                    family_count = sum(int(c) for c, _ in species_dict.values())

                    family_text = f"{family} ({family_count})"
                    family_item = QTreeWidgetItem(parent_for_families, [family_text])
                    family_item.setData(0, Qt.ItemDataRole.UserRole, ('family', family))

                    # Sort species by sort_key
                    sorted_species = sorted(
                        species_dict.items(),
                        key=lambda s: int(s[1][1] or 0)
                    )

                    for species, (count, sort_key) in sorted_species:
                        species_text = f"{species} ({count})" if int(count) > 1 else species
                        species_item = QTreeWidgetItem(family_item, [species_text])
                        species_item.setData(0, Qt.ItemDataRole.UserRole, ('species', species))

        # Expand first level by default
        self.tree.expandItem(all_item)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle tree item click — emit filter signal and update detail panel."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        filter_type, filter_value = data
        self.filter_requested.emit(filter_type, filter_value)
        self._reset_btn.setVisible(filter_type != 'all')

        if filter_type == 'all':
            self.detail_panel.clear()
        elif filter_type == 'order':
            self._show_order_detail(filter_value, item)
        elif filter_type == 'superfamily':
            self._show_superfamily_detail(filter_value, item)
        elif filter_type == 'family':
            self._show_family_detail(filter_value, item)
        elif filter_type == 'species':
            self._show_species_detail(filter_value, item)

    def _get_parent_order(self, item: QTreeWidgetItem) -> str:
        """Walk up the tree to find the order name."""
        current = item.parent()
        while current:
            data = current.data(0, Qt.ItemDataRole.UserRole)
            if data and data[0] == 'order':
                return data[1]
            current = current.parent()
        return ""

    def _show_order_detail(self, order_name: str, item: QTreeWidgetItem):
        """Show detail panel for an order."""
        # Count specimens and species under this order
        total_specimens = 0
        total_species = set()
        families = []
        for i in range(item.childCount()):
            child = item.child(i)
            child_data = child.data(0, Qt.ItemDataRole.UserRole)
            if child_data:
                if child_data[0] == 'superfamily':
                    for j in range(child.childCount()):
                        fam = child.child(j)
                        fam_data = fam.data(0, Qt.ItemDataRole.UserRole)
                        if fam_data and fam_data[0] == 'family':
                            families.append(fam_data[1])
                            stats = self._family_stats.get(fam_data[1], (0, 0, []))
                            total_specimens += stats[0]
                            for k in range(fam.childCount()):
                                sp = fam.child(k)
                                sp_data = sp.data(0, Qt.ItemDataRole.UserRole)
                                if sp_data and sp_data[0] == 'species':
                                    total_species.add(sp_data[1])
                elif child_data[0] == 'family':
                    families.append(child_data[1])
                    stats = self._family_stats.get(child_data[1], (0, 0, []))
                    total_specimens += stats[0]
                    for j in range(child.childCount()):
                        sp = child.child(j)
                        sp_data = sp.data(0, Qt.ItemDataRole.UserRole)
                        if sp_data and sp_data[0] == 'species':
                            total_species.add(sp_data[1])

        self.detail_panel.show_order(order_name, total_specimens, 
                                      len(total_species), families)

    def _show_superfamily_detail(self, sf_name: str, item: QTreeWidgetItem):
        """Show detail panel for a superfamily."""
        order_name = self._get_parent_order(item)
        total_specimens = 0
        total_species = set()
        families = []
        for i in range(item.childCount()):
            fam = item.child(i)
            fam_data = fam.data(0, Qt.ItemDataRole.UserRole)
            if fam_data and fam_data[0] == 'family':
                families.append(fam_data[1])
                stats = self._family_stats.get(fam_data[1], (0, 0, []))
                total_specimens += stats[0]
                for j in range(fam.childCount()):
                    sp = fam.child(j)
                    sp_data = sp.data(0, Qt.ItemDataRole.UserRole)
                    if sp_data and sp_data[0] == 'species':
                        total_species.add(sp_data[1])

        self.detail_panel.show_superfamily(order_name, sf_name, total_specimens,
                                            len(total_species), families)

    def _show_family_detail(self, family: str, item: QTreeWidgetItem):
        """Show detail panel for a family."""
        order_name = self._get_parent_order(item)
        stats = self._family_stats.get(family, (0, 0, []))
        specimen_count, species_count, genera = stats
        self.detail_panel.show_family(
            order_name, family, specimen_count, species_count, genera)

    def _show_species_detail(self, species_name: str, item: QTreeWidgetItem):
        """Show detail panel for a species."""
        order_name = self._get_parent_order(item)
        # Get family from parent
        family = ""
        parent = item.parent()
        if parent:
            parent_data = parent.data(0, Qt.ItemDataRole.UserRole)
            if parent_data and parent_data[0] == 'family':
                family = parent_data[1]

        # Look up species info from UKSI
        tvk = ""
        common_name = ""
        conservation = ""
        try:
            import sqlite3
            conn = sqlite3.connect(self._uksi_db_path)
            cursor = conn.execute(
                'SELECT tvk, red_list_status, rarity_status, legal_protection '
                'FROM taxa WHERE scientific_name = ? AND rank = \'Species\' LIMIT 1',
                (species_name,))
            row = cursor.fetchone()
            if row:
                tvk = row[0] or ""
                statuses = [s for s in [row[1], row[2], row[3]] if s]
                conservation = "; ".join(statuses)

            if tvk:
                cn_cursor = conn.execute(
                    "SELECT common_name FROM common_names WHERE tvk = ? AND preferred = 1 LIMIT 1",
                    (tvk,))
                cn_row = cn_cursor.fetchone()
                common_name = cn_row[0] if cn_row else ""
            conn.close()
        except Exception:
            pass

        # Count specimens
        specimen_count = 0
        stats = self._family_stats.get(family, (0, 0, []))
        # Get from tree item text
        text = item.text(0)
        if '(' in text and text.endswith(')'):
            try:
                specimen_count = int(text.split('(')[-1].rstrip(')'))
            except ValueError:
                specimen_count = 1
        else:
            specimen_count = 1

        self.detail_panel.show_species(
            species_name, tvk, common_name, family, order_name,
            specimen_count, conservation)

    def _on_reset(self):
        """Reset sidebar: clear filter, collapse tree, show all specimens."""
        self.search_box.clear()
        self.tree.collapseAll()
        self.detail_panel.clear()
        self._reset_btn.setVisible(False)
        self.filter_requested.emit('all', '')

    def select_by_family(self, family: str):
        """Highlight the family node in the tree without triggering a filter."""
        if not family:
            return
        
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            order_item = self.tree.topLevelItem(i)
            for j in range(order_item.childCount()):
                child = order_item.child(j)
                child_data = child.data(0, Qt.ItemDataRole.UserRole)
                if not child_data:
                    continue
                
                if child_data[0] == 'family' and child_data[1] == family:
                    self.tree.setCurrentItem(child)
                    self.tree.scrollToItem(child)
                    order_item.setExpanded(True)
                    self._show_family_detail(family, child)
                    self.tree.blockSignals(False)
                    return
                
                # Check under superfamily nodes
                if child_data[0] == 'superfamily':
                    for k in range(child.childCount()):
                        fam_item = child.child(k)
                        fam_data = fam_item.data(0, Qt.ItemDataRole.UserRole)
                        if fam_data and fam_data[0] == 'family' and fam_data[1] == family:
                            self.tree.setCurrentItem(fam_item)
                            self.tree.scrollToItem(fam_item)
                            order_item.setExpanded(True)
                            child.setExpanded(True)
                            self._show_family_detail(family, fam_item)
                            self.tree.blockSignals(False)
                            return
        
        self.tree.blockSignals(False)

    def _filter_tree(self, text: str):
        """Filter tree nodes by search text."""
        text_lower = text.lower().strip()

        for i in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(i)
            top_data = top_item.data(0, Qt.ItemDataRole.UserRole)

            if top_data and top_data[0] == 'all':
                top_item.setHidden(bool(text_lower))
                continue

            # Order level
            order_visible = False
            for j in range(top_item.childCount()):
                family_item = top_item.child(j)
                family_visible = False

                # Check family name
                if text_lower in family_item.text(0).lower():
                    family_visible = True

                # Check species under this family
                for k in range(family_item.childCount()):
                    species_item = family_item.child(k)
                    species_match = text_lower in species_item.text(0).lower()
                    species_item.setHidden(not species_match and not family_visible)
                    if species_match:
                        family_visible = True

                family_item.setHidden(not family_visible)
                if family_visible:
                    order_visible = True
                    if text_lower:
                        family_item.setExpanded(True)

            top_item.setHidden(not order_visible)
            if order_visible and text_lower:
                top_item.setExpanded(True)

    def refresh(self, specimens: list):
        """Rebuild the tree with new data."""
        self.build_tree(specimens)

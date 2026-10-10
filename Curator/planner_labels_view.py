"""
Curator — Taxonomic Labels View

Tree view of the taxonomic hierarchy with label preview and
PDF export for printing collection labels at various levels.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QRadioButton, QFrame,
    QSplitter, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QSpinBox, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from .planner_tree_data import load_taxonomic_tree, TaxonNode
from .planner_data import load_orders, config_problems
from .planner_label_preview import LabelPreviewWidget
from .planner_settings import load_settings, SettingsDialog
from .planner_fonts import load_qt_fonts, get_available_fonts


class LabelsView(QWidget):
    """Main labels view with controls, tree, preview, and export."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tree_root = None
        load_qt_fonts()
        self._settings = load_settings()
        self._setup_ui()
        self._apply_settings()
        self._populate_orders()
        self.show_problems()

    def show_problems(self):
        problems = config_problems()
        self.problem_label.setText("\n".join("\u26a0 " + p for p in problems))
        self.problem_label.setVisible(bool(problems))

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # =============================================================
        # LEFT PANEL — controls only (compact)
        # =============================================================
        left = QWidget()
        left.setMaximumWidth(220)
        left.setMinimumWidth(180)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(12, 12, 12, 12)
        ll.setSpacing(8)

        # Missing or unreadable config files, said on screen (CUR-3)
        self.problem_label = QLabel("")
        self.problem_label.setWordWrap(True)
        self.problem_label.setStyleSheet("color: #a63d40; font-size: 11px;")
        ll.addWidget(self.problem_label)

        ll.addWidget(QLabel("Order"))
        self.order_combo = QComboBox()
        self.order_combo.currentIndexChanged.connect(self._on_order_changed)
        ll.addWidget(self.order_combo)

        self.my_only_cb = QCheckBox("My specimens only")
        self.my_only_cb.setChecked(False)
        self.my_only_cb.toggled.connect(self._populate_orders)
        ll.addWidget(self.my_only_cb)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #ddd;")
        ll.addWidget(sep1)

        ll.addWidget(QLabel("Label Levels"))
        self.cb_order = QCheckBox("Order")
        self.cb_order.setChecked(True)
        self.cb_order.toggled.connect(self._update_preview)
        ll.addWidget(self.cb_order)

        self.cb_suborder = QCheckBox("Suborder")
        self.cb_suborder.setChecked(True)
        self.cb_suborder.toggled.connect(self._update_preview)
        ll.addWidget(self.cb_suborder)

        self.cb_superfamily = QCheckBox("Superfamily")
        self.cb_superfamily.setChecked(True)
        self.cb_superfamily.toggled.connect(self._update_preview)
        ll.addWidget(self.cb_superfamily)

        self.cb_family = QCheckBox("Family")
        self.cb_family.setChecked(True)
        self.cb_family.toggled.connect(self._update_preview)
        ll.addWidget(self.cb_family)

        self.cb_subfamily = QCheckBox("Subfamily")
        self.cb_subfamily.toggled.connect(self._update_preview)
        ll.addWidget(self.cb_subfamily)

        self.cb_genus = QCheckBox("Genus")
        self.cb_genus.toggled.connect(self._update_preview)
        ll.addWidget(self.cb_genus)

        self.cb_species = QCheckBox("Species")
        self.cb_species.toggled.connect(self._update_preview)
        ll.addWidget(self.cb_species)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #ddd;")
        ll.addWidget(sep2)

        ll.addWidget(QLabel("Format"))
        self.rb_full = QRadioButton("Full-width strips")
        self.rb_pinned = QRadioButton("Small pinned labels")
        self.rb_full.setChecked(True)
        self.rb_full.toggled.connect(self._update_preview)
        ll.addWidget(self.rb_full)
        ll.addWidget(self.rb_pinned)

        self.cb_common = QCheckBox("Common names")
        self.cb_common.setChecked(True)
        self.cb_common.toggled.connect(self._update_preview)
        ll.addWidget(self.cb_common)

        counts_label = QLabel("Counts")
        counts_label.setStyleSheet("font-size: 11px; margin-top: 4px;")
        ll.addWidget(counts_label)

        self.cb_my_specimens = QCheckBox("My specimens")
        self.cb_my_specimens.setChecked(False)
        self.cb_my_specimens.toggled.connect(self._update_preview)
        ll.addWidget(self.cb_my_specimens)

        self.cb_my_species = QCheckBox("My species")
        self.cb_my_species.setChecked(False)
        self.cb_my_species.toggled.connect(self._update_preview)
        ll.addWidget(self.cb_my_species)

        self.cb_fauna = QCheckBox("GB fauna species")
        self.cb_fauna.setChecked(False)
        self.cb_fauna.toggled.connect(self._update_preview)
        ll.addWidget(self.cb_fauna)

        sep_font = QFrame()
        sep_font.setFrameShape(QFrame.Shape.HLine)
        sep_font.setStyleSheet("color: #ddd;")
        ll.addWidget(sep_font)

        ll.addWidget(QLabel("Font"))
        self.font_combo = QComboBox()
        self.font_combo.addItems(get_available_fonts())
        self.font_combo.currentIndexChanged.connect(self._update_preview)
        ll.addWidget(self.font_combo)

        size_layout = QHBoxLayout()
        size_layout.setSpacing(6)
        size_layout.addWidget(QLabel("Size"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 24)
        self.size_spin.setValue(11)
        self.size_spin.setSuffix(" pt")
        self.size_spin.valueChanged.connect(self._update_preview)
        size_layout.addWidget(self.size_spin)
        ll.addLayout(size_layout)

        ll.addStretch()

        # Export button at bottom of controls
        export_btn = QPushButton("Export PDF")
        export_btn.setStyleSheet(
            "QPushButton { background-color: #4a7c59; color: white; "
            "border: none; padding: 8px 16px; border-radius: 4px; } "
            "QPushButton:hover { background-color: #3d6348; }"
        )
        export_btn.clicked.connect(self._export_pdf)
        ll.addWidget(export_btn)

        settings_btn = QPushButton("Settings")
        settings_btn.setStyleSheet(
            "QPushButton { padding: 6px 16px; border: 1px solid #8b8178; "
            "border-radius: 4px; color: #8b8178; } "
            "QPushButton:hover { background-color: #f0eeea; }"
        )
        settings_btn.clicked.connect(self._open_settings)
        ll.addWidget(settings_btn)

        splitter.addWidget(left)

        # =============================================================
        # MIDDLE PANEL — taxonomic tree
        # =============================================================
        middle = QWidget()
        middle.setMinimumWidth(220)
        ml = QVBoxLayout(middle)
        ml.setContentsMargins(8, 12, 8, 12)
        ml.setSpacing(8)

        tree_header = QHBoxLayout()
        tree_lbl = QLabel("Taxonomic Tree")
        tree_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        tree_header.addWidget(tree_lbl)
        tree_header.addStretch()
        check_all_btn = QPushButton("All")
        check_all_btn.setFixedWidth(40)
        check_all_btn.setStyleSheet("font-size: 10px; padding: 2px;")
        check_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        tree_header.addWidget(check_all_btn)
        uncheck_all_btn = QPushButton("None")
        uncheck_all_btn.setFixedWidth(40)
        uncheck_all_btn.setStyleSheet("font-size: 10px; padding: 2px;")
        uncheck_all_btn.clicked.connect(lambda: self._set_all_checked(False))
        tree_header.addWidget(uncheck_all_btn)
        ml.addLayout(tree_header)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.itemChanged.connect(self._on_item_checked)
        ml.addWidget(self.tree, 1)

        splitter.addWidget(middle)

        # =============================================================
        # RIGHT PANEL — label preview
        # =============================================================
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(12, 12, 12, 12)
        rl.setSpacing(10)

        header = QLabel("Label Preview")
        header.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        rl.addWidget(header)

        self.preview = LabelPreviewWidget()
        rl.addWidget(self.preview, 1)

        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)  # controls - fixed
        splitter.setStretchFactor(1, 1)  # tree - flexible
        splitter.setStretchFactor(2, 2)  # preview - most space
        splitter.setSizes([200, 280, 500])

        main_layout.addWidget(splitter)

    def _apply_settings(self):
        """Apply saved settings to controls."""
        s = self._settings
        # Font
        idx = self.font_combo.findText(s.get("font_family", "Libre Baskerville"))
        if idx >= 0:
            self.font_combo.setCurrentIndex(idx)
        # Size
        self.size_spin.setValue(s.get("font_size", 11))
        # My specimens toggle
        self.my_only_cb.setChecked(s.get("my_specimens_only", False))
        # Count toggles
        self.cb_my_specimens.setChecked(s.get("show_my_specimens", False))
        self.cb_my_species.setChecked(s.get("show_my_species", False))
        self.cb_fauna.setChecked(s.get("show_fauna", False))

    def _open_settings(self):
        """Open settings dialog and apply changes."""
        dlg = SettingsDialog(self)
        if dlg.exec() == SettingsDialog.Accepted:
            self._settings = dlg.get_settings()
            self._apply_settings()
            self._populate_orders()

    def _populate_orders(self):
        my_only = self.my_only_cb.isChecked()
        if my_only:
            orders = load_orders()
        else:
            from .planner_data import load_orders_from_uksi
            orders = load_orders_from_uksi()

        self.order_combo.blockSignals(True)
        current = self.order_combo.currentData()
        self.order_combo.clear()
        for name, count in orders:
            if my_only:
                self.order_combo.addItem(f"{name} ({count} specimens)", name)
            else:
                self.order_combo.addItem(f"{name} ({count} families)", name)
        # Restore selection if still available
        if current:
            idx = self.order_combo.findData(current)
            if idx >= 0:
                self.order_combo.setCurrentIndex(idx)
        self.order_combo.blockSignals(False)
        if orders:
            self._on_order_changed()

    def _on_order_changed(self):
        self._rebuild()

    def _rebuild(self):
        order = self.order_combo.currentData()
        if not order:
            return
        my_only = self.my_only_cb.isChecked()
        self._tree_root = load_taxonomic_tree(order, my_specimens_only=my_only)
        self._populate_tree()
        self._update_preview()

    def _populate_tree(self):
        self.tree.blockSignals(True)
        self.tree.clear()
        if not self._tree_root:
            self.tree.blockSignals(False)
            return
        self._add_tree_children(None, self._tree_root)
        self.tree.expandToDepth(0)
        # Check all items by default
        self._set_all_checked_silent(True)
        self.tree.blockSignals(False)

    def _set_all_checked_silent(self, checked):
        """Set all items checked/unchecked without triggering signals."""
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            item.setCheckState(0, state)
            self._set_children_checked(item, state)

    def _add_tree_children(self, parent_item, node: TaxonNode):
        if parent_item is None:
            item = QTreeWidgetItem(self.tree)
        else:
            item = QTreeWidgetItem(parent_item)

        label = node.name
        if node.specimen_count > 0:
            label += f" ({node.specimen_count})"
        elif node.species_count > 0:
            label += f" [{node.species_count} spp]"
        item.setText(0, label)
        item.setData(0, Qt.ItemDataRole.UserRole, node)

        # Checkable
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Checked)

        # Style by rank
        if node.rank == "Order":
            item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
        elif node.rank == "Superfamily":
            f = QFont("Segoe UI", 9)
            f.setItalic(True)
            item.setFont(0, f)
            item.setForeground(0, QColor("#9a7555"))
        elif node.rank == "Suborder":
            f = QFont("Segoe UI", 10)
            f.setItalic(True)
            item.setFont(0, f)
            item.setForeground(0, QColor("#5a4d78"))
        elif node.rank == "Family":
            item.setFont(0, QFont("Segoe UI", 9, QFont.Weight.Bold))
        elif node.rank == "Subfamily":
            f = QFont("Segoe UI", 9)
            f.setItalic(True)
            item.setFont(0, f)
            item.setForeground(0, QColor("#6e8898"))
        elif node.rank == "Genus":
            f = QFont("Segoe UI", 9)
            f.setItalic(True)
            item.setFont(0, f)

        if not node.in_collection:
            item.setForeground(0, QColor("#cccccc"))

        for child in node.children:
            self._add_tree_children(item, child)

    def _on_item_checked(self, item, column):
        """Cascade check state to children."""
        self.tree.blockSignals(True)
        state = item.checkState(0)
        self._set_children_checked(item, state)
        self.tree.blockSignals(False)
        self._update_preview()

    def _set_children_checked(self, item, state):
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, state)
            self._set_children_checked(child, state)

    def _set_all_checked(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.tree.blockSignals(True)
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            item.setCheckState(0, state)
            self._set_children_checked(item, state)
        self.tree.blockSignals(False)
        self._update_preview()

    def _update_preview(self):
        if not self._tree_root:
            return

        checked = self._get_checked_names()
        labels = []
        seen = set()
        self._collect_labels(self._tree_root, labels, checked, seen)

        self.preview.set_labels(
            labels,
            full_width=self.rb_full.isChecked(),
            show_common=self.cb_common.isChecked(),
            show_my_specimens=self.cb_my_specimens.isChecked(),
            show_my_species=self.cb_my_species.isChecked(),
            show_fauna=self.cb_fauna.isChecked(),
            font_family=self.font_combo.currentText(),
            font_size=self.size_spin.value(),
        )

    def _collect_labels(self, node: TaxonNode, labels: list,
                        checked_names: set = None, seen: set = None):
        """Walk tree and collect labels for enabled levels, deduplicating."""
        if seen is None:
            seen = set()

        include = {
            "Order": self.cb_order.isChecked(),
            "Suborder": self.cb_suborder.isChecked(),
            "Superfamily": self.cb_superfamily.isChecked(),
            "Family": self.cb_family.isChecked(),
            "Subfamily": self.cb_subfamily.isChecked(),
            "Genus": self.cb_genus.isChecked(),
            "Species": self.cb_species.isChecked(),
        }

        if include.get(node.rank, False):
            # Deduplicate by name+rank
            key = (node.name, node.rank)
            if key not in seen:
                if checked_names is None or node.name in checked_names:
                    seen.add(key)
                    labels.append((
                        node.name, node.rank, node.common_name,
                        node.specimen_count,
                        node.my_species_count,
                        node.uksi_species_count,
                    ))

        for child in node.children:
            self._collect_labels(child, labels, checked_names, seen)

    def _get_checked_names(self) -> set:
        """Get names of all checked items in the tree."""
        checked = set()
        self._walk_tree_checked(self.tree.invisibleRootItem(), checked)
        return checked

    def _walk_tree_checked(self, item, checked):
        for i in range(item.childCount()):
            child = item.child(i)
            if child.checkState(0) == Qt.CheckState.Checked:
                node = child.data(0, Qt.ItemDataRole.UserRole)
                if node:
                    checked.add(node.name)
            self._walk_tree_checked(child, checked)

    def _export_pdf(self):
        if not self._tree_root:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Labels PDF", "collection_labels.pdf",
            "PDF Files (*.pdf)"
        )
        if not path:
            return

        checked = self._get_checked_names()
        labels = []
        self._collect_labels(self._tree_root, labels, checked)

        if not labels:
            QMessageBox.information(self, "Export PDF", "No labels are ticked.")
            return
        from .planner_label_export import export_taxonomic_labels_pdf
        font = self.font_combo.currentText()
        try:
            used = export_taxonomic_labels_pdf(
                path, labels,
                full_width=self.rb_full.isChecked(),
                show_common=self.cb_common.isChecked(),
                show_my_specimens=self.cb_my_specimens.isChecked(),
                show_my_species=self.cb_my_species.isChecked(),
                show_fauna=self.cb_fauna.isChecked(),
                font_family=font,
                font_size=self.size_spin.value(),
            )
        except Exception as e:  # noqa: BLE001 -- shown, not printed to a console (CUR-3)
            QMessageBox.warning(self, "Export failed", f"The labels PDF could not be written.\n\n{e}")
            return
        note = ""
        if used and used.replace(" ", "") != font.replace(" ", ""):
            note = (f"\n\nThe font {font} is not installed in Curator\\fonts, "
                    f"so {used} was used.")
        QMessageBox.information(self, "Labels exported",
                                f"{len(labels)} labels written to:\n{path}{note}")

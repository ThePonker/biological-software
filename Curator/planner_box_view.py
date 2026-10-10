"""
Collection Planner — Box Layout View (Experimental)

The original box allocation view with visual box preview,
family list with draggable dividers, and allocation summary.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QSplitter, QScrollArea, QSpinBox, QFileDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from .planner_data import (
    load_orders, load_families, allocate_to_boxes,
    ProfileManager, BoxAllocation, calculate_family_rows, config_problems,
)
from .planner_preview import BoxPreviewPanel
from .planner_family_list import FamilyListPanel


class AllocationSummaryItem(QWidget):
    clicked = Signal(int)

    def __init__(self, box_alloc, index, parent=None):
        super().__init__(parent)
        self._index = index
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        label = QLabel(box_alloc.label)
        label.setFont(QFont("Segoe UI", 9))
        layout.addWidget(label, 1)
        pct_label = QLabel(f"{box_alloc.capacity_pct}%")
        colour = "#7a9e7e" if box_alloc.capacity_pct < 80 else "#c2956e"
        if box_alloc.capacity_pct > 95:
            colour = "#a63d40"
        pct_label.setStyleSheet(f"color: {colour}; font-weight: bold;")
        layout.addWidget(pct_label)

    def mousePressEvent(self, event):
        self.clicked.emit(self._index)


class BoxLayoutView(QWidget):
    """Box allocation view with visual preview and draggable dividers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile_mgr = ProfileManager()
        self._families = []
        self._boxes = []
        self._break_indices = []
        self._setup_ui()
        self._populate_orders()
        self.show_problems()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # LEFT PANEL
        left = QWidget()
        left.setMaximumWidth(360)
        left.setMinimumWidth(280)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(12, 12, 12, 12)
        ll.setSpacing(10)

        # Missing or unreadable config files, said on screen (CUR-3)
        self.problem_label = QLabel("")
        self.problem_label.setWordWrap(True)
        self.problem_label.setStyleSheet("color: #a63d40; font-size: 11px;")
        ll.addWidget(self.problem_label)

        ll.addWidget(QLabel("Order"))
        self.order_combo = QComboBox()
        self.order_combo.currentIndexChanged.connect(self._on_order_changed)
        ll.addWidget(self.order_combo)

        ll.addWidget(QLabel("Box Size"))
        self.box_combo = QComboBox()
        for key, box in self._profile_mgr.get_all_boxes().items():
            self.box_combo.addItem(box.label, key)
        self.box_combo.currentIndexChanged.connect(self._recalculate)
        ll.addWidget(self.box_combo)

        growth_group = QHBoxLayout()
        growth_group.setSpacing(8)
        growth_group.addWidget(QLabel("Growth %"))
        self.growth_spin = QSpinBox()
        self.growth_spin.setRange(0, 100)
        self.growth_spin.setValue(20)
        self.growth_spin.setSuffix("%")
        self.growth_spin.valueChanged.connect(self._recalculate)
        growth_group.addWidget(self.growth_spin)
        ll.addLayout(growth_group)

        recalc_btn = QPushButton("Recalculate")
        recalc_btn.setStyleSheet(
            "QPushButton { background-color: #4a7c59; color: white; "
            "border: none; padding: 8px; border-radius: 4px; font-weight: bold; } "
            "QPushButton:hover { background-color: #3d6348; }")
        recalc_btn.clicked.connect(self._recalculate)
        ll.addWidget(recalc_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        ll.addWidget(sep)

        ll.addWidget(QLabel("Families (drag dividers to rebalance)"))
        self.family_list = FamilyListPanel()
        self.family_list.profile_changed.connect(self._on_profile_changed)
        self.family_list.breaks_changed.connect(self._on_breaks_changed)
        ll.addWidget(self.family_list, 1)

        splitter.addWidget(left)

        # RIGHT PANEL
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(12, 12, 12, 12)
        rl.setSpacing(12)
        self.preview = BoxPreviewPanel()
        rl.addWidget(self.preview, 2)

        self.summary_label = QLabel("Allocation Summary")
        self.summary_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        rl.addWidget(self.summary_label)

        self.summary_scroll = QScrollArea()
        self.summary_scroll.setWidgetResizable(True)
        self.summary_scroll.setMaximumHeight(200)
        self.summary_container = QWidget()
        self.summary_layout = QVBoxLayout(self.summary_container)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.summary_layout.setSpacing(2)
        self.summary_layout.addStretch()
        self.summary_scroll.setWidget(self.summary_container)
        rl.addWidget(self.summary_scroll, 1)

        export_layout = QHBoxLayout()
        btn = QPushButton("Export PDF")
        btn.setStyleSheet(
            "QPushButton { background-color: #4a7c59; color: white; "
            "border: none; padding: 8px 16px; border-radius: 4px; } "
            "QPushButton:hover { background-color: #3d6348; }")
        btn.clicked.connect(self._export_pdf)
        export_layout.addWidget(btn)
        export_layout.addStretch()
        rl.addLayout(export_layout)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)

    def show_problems(self):
        problems = config_problems()
        self.problem_label.setText("\n".join("\u26a0 " + p for p in problems))
        self.problem_label.setVisible(bool(problems))

    def _populate_orders(self):
        orders = load_orders()
        self.order_combo.blockSignals(True)
        self.order_combo.clear()
        for name, count in orders:
            self.order_combo.addItem(f"{name} ({count})", name)
        self.order_combo.blockSignals(False)
        if orders:
            self._on_order_changed()

    def _on_order_changed(self):
        order = self.order_combo.currentData()
        if not order:
            return
        self._families = load_families(order)
        for fam in self._families:
            fam.profile_key = self._profile_mgr.get_family_profile(fam.family)
        self._recalculate()

    def _recalculate(self):
        box_key = self.box_combo.currentData()
        growth = self.growth_spin.value()
        if not box_key or not self._families:
            return
        self._boxes = allocate_to_boxes(
            self._families, self._profile_mgr, box_key, growth)
        self._break_indices = self._compute_break_indices()
        self._update_all()

    def _compute_break_indices(self):
        # A family split across boxes (CUR-1) is one family in the list: its
        # later parts do not advance the index, and a box holding only a later
        # part adds no divider.
        breaks = [0]
        idx = 0
        for box in self._boxes:
            idx += sum(1 for f in box.families if getattr(f, "part", 0) <= 1)
            if idx < len(self._families) and idx not in breaks:
                breaks.append(idx)
        return breaks

    def _rebuild_boxes_from_breaks(self):
        box_key = self.box_combo.currentData()
        growth = self.growth_spin.value()
        box_size = self._profile_mgr.get_box(box_key)
        if not box_size:
            return
        breaks = sorted(self._break_indices)
        self._boxes = []
        for b in range(len(breaks)):
            start = breaks[b]
            end = breaks[b + 1] if b + 1 < len(breaks) else len(self._families)
            fams = self._families[start:end]
            height_used = 0
            for i, fam in enumerate(fams):
                info = calculate_family_rows(fam, self._profile_mgr, box_size, growth)
                height_used += info["height_mm"]
                if i > 0:
                    height_used += 8
            self._boxes.append(BoxAllocation(
                box_number=b + 1, families=fams, rows_used=height_used,
                total_rows=box_size.height_mm,
                capacity_pct=round((height_used / box_size.height_mm) * 100)))

    def _update_all(self):
        self.family_list.set_data(
            self._families, self._break_indices, self._profile_mgr)
        box_key = self.box_combo.currentData()
        growth = self.growth_spin.value()
        self.preview.set_data(self._boxes, self._profile_mgr, box_key, growth)
        self._rebuild_summary()

    def _rebuild_summary(self):
        while self.summary_layout.count() > 1:
            item = self.summary_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.summary_label.setText(f"Allocation Summary \u2014 {len(self._boxes)} boxes")
        for i, box in enumerate(self._boxes):
            w = AllocationSummaryItem(box, i)
            w.clicked.connect(self.preview.show_box)
            self.summary_layout.insertWidget(self.summary_layout.count() - 1, w)

    def _on_profile_changed(self, family_name, profile_key):
        self._profile_mgr.save()
        self._recalculate()

    def _on_breaks_changed(self, new_breaks):
        self._break_indices = new_breaks
        self._rebuild_boxes_from_breaks()
        box_key = self.box_combo.currentData()
        growth = self.growth_spin.value()
        self.preview.set_data(self._boxes, self._profile_mgr, box_key, growth)
        self._rebuild_summary()

    def _export_pdf(self):
        if not self._boxes:
            problem = getattr(self._profile_mgr, "problem", "")
            QMessageBox.information(self, "Export PDF",
                                    "There is no layout to export"
                                    + (": " + problem if problem else "."))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", "collection_layout.pdf", "PDF Files (*.pdf)")
        if not path:
            return
        from .planner_export import export_layout_pdf
        box_key = self.box_combo.currentData()
        growth = self.growth_spin.value()
        try:
            export_layout_pdf(path, self._boxes, self._profile_mgr, box_key, growth)
        except Exception as e:  # noqa: BLE001 -- shown, not printed to a console (CUR-3)
            QMessageBox.warning(self, "Export failed", f"The PDF could not be written.\n\n{e}")
            return
        QMessageBox.information(self, "PDF exported", f"Written to:\n{path}")

"""
Collection Planner — Family List with Draggable Box Dividers

Shows families in systematic order with visual dividers between boxes.
Dividers can be dragged up/down to move the split point between boxes.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QScrollArea,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QCursor


class FamilyListItem(QWidget):
    """Single family row in the list."""

    profile_changed = Signal(str, str)  # family_name, new_profile_key

    def __init__(self, family_data, profile_mgr, box_number, parent=None):
        super().__init__(parent)
        self.family_data = family_data
        self._profile_mgr = profile_mgr
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Box number badge
        badge = QLabel(f"B{box_number}")
        badge.setFixedSize(28, 28)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            "background-color: #e8e0d8; color: #9a7555; "
            "border-radius: 4px; font-size: 10px; font-weight: bold;"
        )
        layout.addWidget(badge)

        # Family info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(0)

        name_label = QLabel(family_data.family)
        name_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        info_layout.addWidget(name_label)

        parts = [f"{family_data.specimen_count} specimens"]
        if family_data.superfamily:
            parts.append(family_data.superfamily)
        detail_label = QLabel(" \u2014 ".join(parts))
        detail_label.setStyleSheet("color: #888; font-size: 11px;")
        info_layout.addWidget(detail_label)

        layout.addLayout(info_layout, 1)

        # Mounting profile dropdown
        self.profile_combo = QComboBox()
        self.profile_combo.setFixedWidth(75)
        short_labels = {"micro": "Micro", "side": "Side", "standard": "Std", "spread": "Spread", "large": "Large"}
        for key in profile_mgr.profile_keys():
            self.profile_combo.addItem(short_labels.get(key, key), key)

        current = profile_mgr.get_family_profile(family_data.family)
        idx = self.profile_combo.findData(current)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)

        self.profile_combo.currentIndexChanged.connect(self._on_changed)
        layout.addWidget(self.profile_combo)

    def _on_changed(self):
        key = self.profile_combo.currentData()
        self.family_data.profile_key = key
        self._profile_mgr.set_family_profile(self.family_data.family, key)
        self.profile_changed.emit(self.family_data.family, key)


class BoxDivider(QWidget):
    """
    Draggable divider between box groups.
    Drag up = move break point earlier (family above goes to next box).
    Drag down = move break point later (family below goes to previous box).
    """

    break_moved = Signal(int, int)  # divider_index, direction (-1=up, +1=down)

    def __init__(self, divider_index, box_above, box_below, parent=None):
        super().__init__(parent)
        self.divider_index = divider_index
        self._box_above = box_above
        self._box_below = box_below
        self._dragging = False
        self._drag_start_y = 0
        self._drag_threshold = 20  # Pixels to trigger a move
        self.setFixedHeight(24)
        self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))

    def paintEvent(self, event):
        painter = QPainter(self)
        w = self.width()
        h = self.height()
        mid_y = h // 2

        # Background
        painter.fillRect(0, 0, w, h, QColor("#f5f0eb"))

        # Dashed divider line
        pen = QPen(QColor("#c2956e"), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(8, mid_y, w - 8, mid_y)

        # Box labels
        painter.setPen(QColor("#9a7555"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        label = f"Box {self._box_above}  \u2502  Box {self._box_below}"
        painter.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, label)

        # Drag grip dots
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#c2956e"))
        for dy in [-3, 0, 3]:
            painter.drawEllipse(w - 18, mid_y + dy - 1, 3, 3)
            painter.drawEllipse(w - 12, mid_y + dy - 1, 3, 3)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_y = event.globalPosition().y()

    def mouseMoveEvent(self, event):
        if not self._dragging:
            return
        delta = event.globalPosition().y() - self._drag_start_y
        if abs(delta) >= self._drag_threshold:
            direction = -1 if delta < 0 else 1
            self.break_moved.emit(self.divider_index, direction)
            self._drag_start_y = event.globalPosition().y()

    def mouseReleaseEvent(self, event):
        self._dragging = False


class FamilyListPanel(QWidget):
    """
    Scrollable family list with draggable box dividers.

    Emits:
        profile_changed(family_name, profile_key)
        breaks_changed(break_indices)  — when dividers are dragged
    """

    profile_changed = Signal(str, str)
    breaks_changed = Signal(list)  # list of family indices where boxes split

    def __init__(self, parent=None):
        super().__init__(parent)
        self._families = []
        self._break_indices = []  # indices in families list where new box starts
        self._profile_mgr = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._list_layout = QVBoxLayout(self._container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)

    def set_data(self, families: list, break_indices: list, profile_mgr):
        """
        Set the family list and box break points.

        Args:
            families: list of FamilyData in systematic order
            break_indices: indices where new boxes start
                           e.g., [0, 5, 12] means Box1=fam[0:5], Box2=fam[5:12], Box3=fam[12:]
            profile_mgr: ProfileManager instance
        """
        self._families = families
        self._break_indices = list(break_indices)
        self._profile_mgr = profile_mgr
        self._rebuild()

    def get_break_indices(self) -> list:
        return list(self._break_indices)

    def _rebuild(self):
        """Rebuild the list with families and dividers."""
        # Clear existing widgets
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._families or not self._profile_mgr:
            return

        # Determine which box each family belongs to
        box_for_family = []
        box_num = 1
        break_set = set(self._break_indices[1:]) if len(self._break_indices) > 1 else set()

        for i in range(len(self._families)):
            if i in break_set:
                box_num += 1
            box_for_family.append(box_num)

        total_boxes = box_num
        divider_idx = 0

        for i, family in enumerate(self._families):
            # Insert divider before this family if it starts a new box (not the first)
            if i in break_set:
                box_above = box_for_family[i - 1] if i > 0 else 1
                box_below = box_for_family[i]
                divider = BoxDivider(divider_idx, box_above, box_below)
                divider.break_moved.connect(self._on_break_moved)
                self._list_layout.insertWidget(
                    self._list_layout.count() - 1, divider
                )
                divider_idx += 1

            # Family item
            item = FamilyListItem(
                family, self._profile_mgr, box_for_family[i]
            )
            item.profile_changed.connect(self.profile_changed.emit)
            self._list_layout.insertWidget(
                self._list_layout.count() - 1, item
            )

    def _on_break_moved(self, divider_index: int, direction: int):
        """
        Handle divider drag.
        direction: -1 = move break earlier (up), +1 = move break later (down)
        """
        if len(self._break_indices) < 2:
            return

        # Find which break index this divider corresponds to
        # Dividers correspond to break_indices[1], break_indices[2], etc.
        actual_idx = divider_index + 1
        if actual_idx >= len(self._break_indices):
            return

        current_pos = self._break_indices[actual_idx]
        new_pos = current_pos + direction

        # Bounds check
        prev_break = self._break_indices[actual_idx - 1]
        next_break = (self._break_indices[actual_idx + 1]
                      if actual_idx + 1 < len(self._break_indices)
                      else len(self._families))

        # Don't let breaks cross each other or go out of range
        if new_pos <= prev_break or new_pos >= next_break:
            return

        self._break_indices[actual_idx] = new_pos
        self._rebuild()
        self.breaks_changed.emit(list(self._break_indices))

"""
Collection Planner — Box Preview Widget

Custom-painted QWidget showing a scaled representation of one box
with family sections drawn proportionally.
"""

import math

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush


# Colour palette for family sections (cycle through these)
FAMILY_COLOURS = [
    "#c2956e",  # Terracotta
    "#7a9e7e",  # Sage green
    "#6e8898",  # Dusty blue
    "#8b8178",  # Warm grey
    "#b8860b",  # Gold
    "#a63d40",  # Muted red
    "#5f8575",  # Dark sage
    "#9a7555",  # Dark terracotta
    "#4a7c59",  # Moss green
    "#6b5b73",  # Muted purple
]


class BoxCanvas(QWidget):
    """Custom-painted canvas showing one box layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._box_width_mm = 395
        self._box_height_mm = 255
        self._sections = []  # list of (family_name, height_mm, colour, specimen_count, profile_label)
        self._capacity_pct = 0
        self._box_label = ""
        self.setMinimumSize(300, 200)

    def set_box_size(self, width_mm: int, height_mm: int):
        self._box_width_mm = width_mm
        self._box_height_mm = height_mm
        self.update()

    def set_sections(self, sections: list, capacity_pct: float, label: str):
        """
        sections: list of dicts with keys:
            family, height_mm, colour, specimen_count, profile_label,
            specimens_per_row, base_rows, growth_rows
        """
        self._sections = sections
        self._capacity_pct = capacity_pct
        self._box_label = label
        self.update()

    def clear(self):
        self._sections = []
        self._capacity_pct = 0
        self._box_label = ""
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Margins for labels and padding
        margin_top = 35
        margin_bottom = 25
        margin_left = 15
        margin_right = 130  # Space for family labels on the right

        # Available drawing area
        draw_w = w - margin_left - margin_right
        draw_h = h - margin_top - margin_bottom

        if draw_w <= 0 or draw_h <= 0:
            painter.end()
            return

        # Scale factor: fit box proportions into drawing area
        scale_x = draw_w / self._box_width_mm
        scale_y = draw_h / self._box_height_mm
        scale = min(scale_x, scale_y)

        box_w = self._box_width_mm * scale
        box_h = self._box_height_mm * scale

        # Centre the box horizontally in the draw area
        box_x = margin_left + (draw_w - box_w) / 2
        box_y = margin_top

        # Box title
        painter.setPen(QColor("#333333"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(
            QRectF(0, 4, w, 28), Qt.AlignmentFlag.AlignCenter,
            self._box_label
        )

        # Box outline
        painter.setPen(QPen(QColor("#999999"), 2))
        painter.setBrush(QBrush(QColor("#fafafa")))
        painter.drawRect(QRectF(box_x, box_y, box_w, box_h))

        # Draw family sections
        y_pos = box_y
        separator_px = 3 * scale  # Visual separator between families
        sf_separator_px = 5 * scale  # Larger gap at superfamily boundary
        sf_header_h = 9 * scale  # Height for superfamily label

        for i, section in enumerate(self._sections):
            # Superfamily header at boundary
            if section.get("is_sf_boundary") and section.get("superfamily"):
                y_pos += sf_separator_px
                sf_count = sum(1 for s in self._sections if s.get("superfamily") == section["superfamily"])
                if sf_count >= 2 and y_pos + sf_header_h < box_y + box_h:
                    painter.setPen(QColor("#9a7555"))
                    painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                    painter.drawText(
                        QRectF(box_x + 3, y_pos, box_w - 6, sf_header_h),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        f"\u2014 {section['superfamily']} \u2014"
                    )
                    # Thin line under the header
                    painter.setPen(QPen(QColor("#c2956e"), 0.5, Qt.PenStyle.DashLine))
                    painter.drawLine(
                        int(box_x + 2), int(y_pos + sf_header_h - 1),
                        int(box_x + box_w - 2), int(y_pos + sf_header_h - 1)
                    )
                    y_pos += sf_header_h
            elif i > 0:
                y_pos += separator_px
            # First family in box — show superfamily if it has one
            elif i == 0 and section.get("superfamily"):
                sf_count = sum(1 for s in self._sections if s.get("superfamily") == section["superfamily"])
                if sf_count >= 2:
                    painter.setPen(QColor("#9a7555"))
                    painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                    painter.drawText(
                        QRectF(box_x + 3, y_pos, box_w - 6, sf_header_h),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        f"\u2014 {section['superfamily']} \u2014"
                    )
                    y_pos += sf_header_h

            section_h = section["height_mm"] * scale

            if y_pos + section_h > box_y + box_h:
                section_h = (box_y + box_h) - y_pos
                if section_h <= 0:
                    break

            colour = QColor(section["colour"])

            # Filled section
            painter.setPen(QPen(colour.darker(120), 1))
            colour.setAlpha(140)
            painter.setBrush(QBrush(colour))
            painter.drawRect(QRectF(box_x + 1, y_pos, box_w - 2, section_h))

            # Growth area (lighter)
            if section.get("growth_rows", 0) > 0 and section.get("base_rows", 0) > 0:
                base_h = (section["base_rows"] / (section["base_rows"] + section["growth_rows"])) * section_h
                growth_h = section_h - base_h
                if growth_h > 2:
                    growth_colour = QColor(section["colour"])
                    growth_colour.setAlpha(50)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(growth_colour))
                    painter.drawRect(QRectF(
                        box_x + 1, y_pos + base_h,
                        box_w - 2, growth_h
                    ))

            # Family label to the right of the box
            label_x = box_x + box_w + 8
            label_y = y_pos + section_h / 2

            painter.setPen(QColor("#333333"))
            painter.setFont(QFont("Segoe UI", 8))

            family_text = section["family"]
            count_text = f"  ({section['specimen_count']})"

            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(
                QRectF(label_x, label_y - 12, margin_right - 12, 14),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                family_text
            )
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QColor("#888888"))
            painter.drawText(
                QRectF(label_x, label_y + 1, margin_right - 12, 12),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"{section['specimen_count']} specimens, {section['profile_label']}"
            )

            # Connecting line from section to label
            painter.setPen(QPen(QColor("#cccccc"), 1, Qt.PenStyle.DotLine))
            painter.drawLine(
                int(box_x + box_w), int(label_y),
                int(label_x - 3), int(label_y)
            )

            y_pos += section_h + separator_px

        # Capacity bar at the bottom
        bar_y = box_y + box_h + 8
        bar_w = box_w
        bar_h = 10

        painter.setPen(QPen(QColor("#cccccc"), 1))
        painter.setBrush(QBrush(QColor("#eeeeee")))
        painter.drawRect(QRectF(box_x, bar_y, bar_w, bar_h))

        fill_w = bar_w * min(self._capacity_pct, 100) / 100
        fill_colour = QColor("#7a9e7e") if self._capacity_pct < 80 else QColor("#c2956e")
        if self._capacity_pct > 95:
            fill_colour = QColor("#a63d40")
        painter.setBrush(QBrush(fill_colour))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(box_x, bar_y, fill_w, bar_h))

        painter.setPen(QColor("#555555"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(
            QRectF(box_x, bar_y, bar_w, bar_h),
            Qt.AlignmentFlag.AlignCenter,
            f"{self._capacity_pct}% capacity"
        )

        painter.end()


class BoxPreviewPanel(QWidget):
    """Panel with box canvas and navigation buttons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._boxes = []
        self._current_index = 0
        self._profile_mgr = None
        self._box_key = ""
        self._growth_pct = 20
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.canvas = BoxCanvas()
        layout.addWidget(self.canvas, 1)

        # Navigation
        nav = QHBoxLayout()
        nav.setSpacing(8)

        self.prev_btn = QPushButton("\u25C0 Prev Box")
        self.prev_btn.clicked.connect(self._prev)
        nav.addWidget(self.prev_btn)

        self.nav_label = QLabel("Box 0 of 0")
        self.nav_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.nav_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        nav.addWidget(self.nav_label, 1)

        self.next_btn = QPushButton("Next Box \u25B6")
        self.next_btn.clicked.connect(self._next)
        nav.addWidget(self.next_btn)

        layout.addLayout(nav)

    def set_data(self, boxes: list, profile_mgr, box_key: str, growth_pct: float):
        self._boxes = boxes
        self._profile_mgr = profile_mgr
        self._box_key = box_key
        self._growth_pct = growth_pct
        self._current_index = 0
        self._refresh()

    def show_box(self, index: int):
        if 0 <= index < len(self._boxes):
            self._current_index = index
            self._refresh()

    def _prev(self):
        if self._current_index > 0:
            self._current_index -= 1
            self._refresh()

    def _next(self):
        if self._current_index < len(self._boxes) - 1:
            self._current_index += 1
            self._refresh()

    def _refresh(self):
        if not self._boxes or not self._profile_mgr:
            self.canvas.clear()
            self.nav_label.setText("No boxes")
            return

        box_alloc = self._boxes[self._current_index]
        box_size = self._profile_mgr.get_box(self._box_key)

        if not box_size:
            return

        self.canvas.set_box_size(box_size.width_mm, box_size.height_mm)

        # Build sections with superfamily grouping
        sections = []
        from .planner_data import calculate_family_rows
        prev_sf = ""
        for i, family in enumerate(box_alloc.families):
            info = calculate_family_rows(
                family, self._profile_mgr, box_size, self._growth_pct
            )
            colour = FAMILY_COLOURS[i % len(FAMILY_COLOURS)]
            is_sf_boundary = (family.superfamily != prev_sf
                              and family.superfamily != ""
                              and prev_sf != "" and i > 0)
            sections.append({
                "family": family.family,
                "superfamily": family.superfamily,
                "is_sf_boundary": is_sf_boundary,
                "height_mm": info["height_mm"],
                "colour": colour,
                "specimen_count": family.specimen_count,
                "profile_label": info["profile"].label,
                "specimens_per_row": info["specimens_per_row"],
                "base_rows": info["base_rows"],
                "growth_rows": info["growth_rows"],
            })
            prev_sf = family.superfamily

        self.canvas.set_sections(sections, box_alloc.capacity_pct, box_alloc.label)

        total = len(self._boxes)
        current = self._current_index + 1
        self.nav_label.setText(f"Box {current} of {total}")
        self.prev_btn.setEnabled(self._current_index > 0)
        self.next_btn.setEnabled(self._current_index < total - 1)

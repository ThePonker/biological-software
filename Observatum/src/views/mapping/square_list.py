"""The list of mapped squares in the Mapping tab's filter panel (H4): most records first,
click a row to see its records. Split out of filter_panel.py (10 Oct 2026, round 2).
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ...core.config import TabColors
from ...themes import theme


class MapSquareList(QWidget):
    """GRID SQUARES (n) and a row per square. square_clicked carries the square's label."""

    square_clicked = Signal(str)

    GRID_LIST_MAX = 200            # rows shown; the rest are summarised in one line

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accent_light = TabColors.MAPPING_LIGHT
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._setup_grid_list(layout)

    def _setup_grid_list(self, layout: QVBoxLayout):
        t = theme()
        group = QVBoxLayout()
        group.setSpacing(8)
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {t.get('separator')};")
        group.addWidget(sep)
        self.grid_title = QLabel("GRID SQUARES (0)")
        self.grid_title.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: 11px; letter-spacing: 1px;")
        group.addWidget(self.grid_title)
        self.grid_list = QVBoxLayout()
        self.grid_list.setSpacing(4)
        group.addLayout(self.grid_list)
        layout.addLayout(group)

    def set_squares(self, squares: list):
        """Update the grid squares list (most records first). Click a row to see its records."""
        t = theme()
        while self.grid_list.count():
            item = self.grid_list.takeAt(0)
            if item.widget():
                item.widget().hide()          # gone now, not at the next event loop
                item.widget().deleteLater()
        self.grid_title.setText(f"GRID SQUARES ({len(squares):,})")
        ordered = sorted(squares, key=lambda sq: (-sq['count'], sq['grid']))
        for sq in ordered[:self.GRID_LIST_MAX]:
            row = QHBoxLayout()
            row.setContentsMargins(4, 2, 4, 2)
            grid_label = QLabel(sq['grid'])
            grid_label.setStyleSheet(f"font-family: monospace; color: {t.get('text_heading')};")
            row.addWidget(grid_label)
            row.addStretch()
            n, k = sq['count'], sq.get('species', 0)
            count_label = QLabel(f"{n:,} record{'s' if n != 1 else ''} · {k} sp.")
            count_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px;")
            row.addWidget(count_label)
            container = QFrame()
            container.setLayout(row)
            container.setCursor(Qt.CursorShape.PointingHandCursor)
            container.setToolTip((f"{sq['taxa']}: " if sq.get('taxa') else "")
                                + "Show the records in this square")
            container.setStyleSheet(f"QFrame:hover {{ background-color: {self._accent_light}; }}")
            container.mousePressEvent = lambda e, g=sq['grid']: self.square_clicked.emit(g)
            self.grid_list.addWidget(container)
        if len(ordered) > self.GRID_LIST_MAX:
            more = QLabel(f"… and {len(ordered) - self.GRID_LIST_MAX:,} more "
                          f"(click them on the map)")
            more.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px;")
            self.grid_list.addWidget(more)

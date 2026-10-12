"""The frame every Lector screen shares: back button, title, actions, scrolling body."""
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QLayout, QStyledItemDelegate, QVBoxLayout, QWidget

from src.views.components.hscroll_strip import HScrollStrip

from Lector.ui import style as S
from shared.fit_to_screen import scroll_body


class Screen(QWidget):
    """header (back button / title / subtitle on the left, action buttons on the right) and a
    body that scrolls when the window is too small for it."""

    def __init__(self, win, title="", subtitle=""):
        super().__init__()
        self.setObjectName("lectorPage")
        self.win, self.svc = win, win.svc
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 18, 28, 12)
        outer.setSpacing(12)
        head = QHBoxLayout()
        head.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(2)
        # "← Back": to the screen you came from (Saved searches when unknown)
        self.back_btn = S.button("\u2190 Back", "outline", "Back to where you came from",
                                 lambda: win.back())
        self.back_btn.hide()
        crumb_row = QHBoxLayout()
        crumb_row.addWidget(self.back_btn)
        crumb_row.addStretch(1)
        left.addLayout(crumb_row)
        self.title = S.label(title, "h1", wrap=True)
        self.subtitle = S.label(subtitle, "muted", wrap=True)
        left.addWidget(self.title)
        left.addWidget(self.subtitle)
        head.addLayout(left, 1)
        bar = QWidget()
        self.actions = QHBoxLayout(bar)
        self.actions.setContentsMargins(0, 0, 0, 0)
        self.actions.setSpacing(8)
        # Observatum's strip: the buttons scroll sideways rather than hold the window wide
        head.addWidget(HScrollStrip(bar), 0, Qt.AlignmentFlag.AlignBottom)
        outer.addLayout(head)
        self.body_widget = QWidget()
        self.body_widget.setObjectName("lectorPage")
        self.body = QVBoxLayout(self.body_widget)
        self.body.setContentsMargins(0, 0, 4, 0)
        self.body.setSpacing(12)
        # the body fills the page when it fits; on a small screen (or with large text) it
        # scrolls rather than hold the window wider or taller than the screen
        outer.addWidget(scroll_body(self.body_widget), 1)

    def show_back(self):
        self.back_btn.show()


def clear_layout(layout):
    """Remove and delete every item of a layout (rows rebuilt on refresh)."""
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


class FlowLayout(QLayout):
    """Lays widgets left to right and wraps them onto new lines (word chips)."""

    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self._items = []
        self._space = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._place(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._place(rect, apply=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _place(self, rect, apply):
        x, y, line = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > rect.right() + 1 and line > 0:
                x, y, line = rect.x(), y + line + self._space, 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._space
            line = max(line, hint.height())
        return y + line - rect.y()


def fit_widget_column(table, col, minimum=60):
    """Widen a table column to its widest cell widget (buttons in cells are not measured
    by ResizeToContents)."""
    widths = []
    for r in range(table.rowCount()):
        w = table.cellWidget(r, col)
        if w is not None:
            polish(w)
            widths.append(w.sizeHint().width())
    # + the theme's 8 px item padding each side (table_style), which the cell widget loses
    table.setColumnWidth(col, max([minimum] + widths) + 24)


def polish(widget):
    """Apply style sheets now, so a size hint taken before the widget is shown is right."""
    for child in [widget] + widget.findChildren(QWidget):
        child.ensurePolished()
    if widget.layout() is not None:
        widget.layout().invalidate()


def fit_rows(table, minimum=40):
    """Rows as tall as their wrapped cell widgets need at the present column widths."""
    for r in range(table.rowCount()):
        h = minimum
        for col in range(table.columnCount()):
            w = table.cellWidget(r, col)
            if w is None:
                continue
            polish(w)
            width = table.columnWidth(col) - 16          # the theme's item padding
            hfw = w.heightForWidth(width) if w.hasHeightForWidth() else -1
            h = max(h, hfw if hfw > 0 else w.sizeHint().height())
        table.setRowHeight(r, h + 18)


def left_headers(table):
    table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft
                                                 | Qt.AlignmentFlag.AlignVCenter)


class WrapDelegate(QStyledItemDelegate):
    """List rows tall enough for their wrapped text (Qt's own measure cut some last
    lines, or elided them)."""

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        text = index.data() or ""
        width = max(80, self.parent().viewport().width() - 44)   # icon, padding, border
        r = option.fontMetrics.boundingRect(QRect(0, 0, width, 100000),
                                            int(Qt.TextFlag.TextWordWrap), text)
        return QSize(size.width(), max(size.height(), r.height() + 16))

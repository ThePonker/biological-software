"""Tick column for the record tables (Observations, Recording Scheme, Insect Collection).

One look and one behaviour everywhere (9 Oct 2026). The three tables each drew their tick
differently -- a native box, a green check mark, a faded box with an outline -- and Qt only
toggled it when the click hit the small box itself. TickDelegate draws the column itself:

  * an empty rounded box when unticked, the box filled in the tab's colour with a white
    tick when ticked;
  * a click anywhere in the cell toggles it; Shift+click ticks (or unticks) every row
    between the last one clicked and this one, in the order the table is showing.

The models still hold the state (CheckStateRole); the delegate only draws and toggles it.

    tick_column.install(self.table_view, "accent_observations")
"""
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from ...themes import theme

COLUMN = 0          # the tick column is always first in all three tables
BOX = 14            # px


def is_checked(value) -> bool:
    """Qt hands over the enum or its plain int, depending on the caller."""
    if value == Qt.CheckState.Checked:
        return True
    try:
        return int(getattr(value, "value", value)) == Qt.CheckState.Checked.value
    except (TypeError, ValueError):
        return False


class TickDelegate(QStyledItemDelegate):
    def __init__(self, view, accent_key: str):
        super().__init__(view)
        self._view = view
        self._accent_key = accent_key
        self._last_row = None

    # ------------------------------------------------------------------ drawing
    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        opt.features &= ~QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
        opt.state &= ~QStyle.StateFlag.State_HasFocus
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)  # row background

        t = theme()
        ticked = is_checked(index.data(Qt.ItemDataRole.CheckStateRole))
        r = option.rect
        box = QRectF(r.center().x() - BOX / 2 + 0.5, r.center().y() - BOX / 2 + 0.5, BOX, BOX)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if ticked:
            accent = QColor(t.get(self._accent_key))
            painter.setPen(QPen(accent, 1))
            painter.setBrush(accent)
        else:
            painter.setPen(QPen(QColor(t.get("border_strong")), 1))
            painter.setBrush(QColor(t.get("surface")))
        painter.drawRoundedRect(box, 3, 3)
        if ticked:
            mark = QPainterPath(QPointF(box.left() + 3.2, box.center().y() + 0.2))
            mark.lineTo(box.left() + 6, box.bottom() - 3.6)
            mark.lineTo(box.right() - 3, box.top() + 3.8)
            pen = QPen(QColor(t.get("button_primary_text")), 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(mark)
        painter.restore()

    # ------------------------------------------------------------------ clicking
    def editorEvent(self, event, model, option, index):
        kind = event.type()
        if kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
            return True                          # swallowed: no row-open on the tick cell
        if kind != QEvent.Type.MouseButtonRelease or event.button() != Qt.MouseButton.LeftButton:
            return False
        if not option.rect.contains(event.position().toPoint()):
            return False
        tick = not is_checked(index.data(Qt.ItemDataRole.CheckStateRole))
        rows = [index.row()]
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier and self._last_row is not None:
            lo, hi = sorted((self._last_row, index.row()))
            rows = range(lo, hi + 1)
        value = Qt.CheckState.Checked if tick else Qt.CheckState.Unchecked
        for row in rows:
            model.setData(model.index(row, index.column()), value, Qt.ItemDataRole.CheckStateRole)
        self._last_row = index.row()
        return True


def install(view, accent_key: str, column: int = COLUMN) -> TickDelegate:
    delegate = TickDelegate(view, accent_key)
    view.setItemDelegateForColumn(column, delegate)
    return delegate

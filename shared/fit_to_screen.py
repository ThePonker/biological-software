"""Keep windows on a laptop screen (R5, 11 Oct 2026).

The suite was laid out on a 1920x1080 monitor. On a laptop (1366x768, or 1920x1080 at 150 %
scaling = 1280x720, less the taskbar) several dialogs opened taller than the screen, with
their OK / Next / Cancel buttons below the bottom edge.

    from shared.fit_to_screen import fit_to_screen, scroll_body

    fit_to_screen(dialog)          # in __init__, after resize(): applied when first shown
    layout.addWidget(scroll_body(page_or_stack), 1)   # the body scrolls, buttons stay put

fit_to_screen() makes the window no bigger than the free desktop (never below its minimum),
centres it on its parent window (or the screen) and keeps it inside the free desktop. On a
big monitor nothing changes: a window that already fits keeps its size.
"""

from PySide6.QtCore import QEvent, QObject, QRect, QSize, Qt
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QFrame, QScrollArea, QWidget

#: room for the Windows title bar and frame (logical px)
TITLE_BAR = 32
FRAME = 8


def available_geometry(widget: QWidget = None) -> QRect:
    """The free desktop (screen less the taskbar) the widget is on, or will open on."""
    screen = None
    if widget is not None:
        anchor = widget.parentWidget().window() if widget.parentWidget() else widget
        screen = anchor.screen() if anchor.isVisible() else None
    if screen is None:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
    return screen.availableGeometry()


def fitted_size(widget: QWidget, avail: QRect):
    """(width, height) for the window's contents: its present size, no larger than the free
    desktop allows, never below its minimum."""
    mw = max(widget.minimumWidth(), widget.minimumSizeHint().width())
    mh = max(widget.minimumHeight(), widget.minimumSizeHint().height())
    w = max(mw, min(widget.width(), avail.width() - FRAME))
    h = max(mh, min(widget.height(), avail.height() - TITLE_BAR))
    return w, h


def place(widget: QWidget, avail: QRect = None):
    """Size and position a top-level window now (see module docstring)."""
    avail = avail or available_geometry(widget)
    w, h = fitted_size(widget, avail)
    if (w, h) != (widget.width(), widget.height()):
        widget.resize(w, h)
    parent = widget.parentWidget()
    if parent is not None and parent.window().isVisible():
        centre = parent.window().frameGeometry().center()
    else:
        centre = avail.center()
    fw, fh = w + FRAME, h + TITLE_BAR          # the frame around the contents
    x = centre.x() - fw // 2
    y = centre.y() - fh // 2
    x = max(avail.left(), min(x, avail.left() + avail.width() - fw))
    y = max(avail.top(), min(y, avail.top() + avail.height() - fh))
    widget.move(x, y)


class _FitOnShow(QObject):
    def __init__(self, widget: QWidget, natural: bool):
        super().__init__(widget)
        self._natural = natural

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show and obj.isWindow():
            obj.removeEventFilter(self)
            if self._natural:
                # Qt opens a window that was never resized at no more than 2/3 of the
                # screen's height; open it at the size it asks for (then fitted below)
                obj.resize(obj.sizeHint().expandedTo(obj.minimumSizeHint()))
            place(obj)
        return False


def fit_to_screen(widget: QWidget, now: bool = False):
    """Fit a top-level window to the free desktop when it is first shown (or now).
    Call it after any resize() the window makes for itself."""
    if now or widget.isVisible():
        place(widget)
        return
    natural = not widget.testAttribute(Qt.WidgetAttribute.WA_Resized)
    widget.installEventFilter(_FitOnShow(widget, natural))


class BodyScroll(QScrollArea):
    """A frameless scroll area that asks for its body's whole size (a plain QScrollArea
    asks for at most ~24 lines), so the window opens exactly as it did without it."""

    def sizeHint(self) -> QSize:
        body = self.widget()
        if body is None:
            return super().sizeHint()
        hint = body.sizeHint().expandedTo(body.minimumSizeHint())
        return hint + QSize(2 * self.frameWidth(), 2 * self.frameWidth())

    def minimumSizeHint(self) -> QSize:
        """Short as you like; as narrow as the body allows when it never scrolls sideways."""
        hint = super().minimumSizeHint()
        body = self.widget()
        if body is None or self.horizontalScrollBarPolicy() != Qt.ScrollBarPolicy.ScrollBarAlwaysOff:
            return hint
        w = (max(body.minimumSizeHint().width(), body.minimumWidth())
             + self.verticalScrollBar().sizeHint().width() + 2 * self.frameWidth())
        return QSize(max(w, hint.width()), hint.height())


def scroll_body(body: QWidget, horizontal: bool = True) -> QScrollArea:
    """Wrap a dialog's body so it scrolls when the window is shorter than the body; the
    buttons laid out outside it stay on screen. Looks the same when there is room."""
    area = BodyScroll()
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setWidgetResizable(True)
    area.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAsNeeded if horizontal else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    # see-through, so the dialog's own background shows as before
    area.setAutoFillBackground(False)
    area.viewport().setAutoFillBackground(False)
    area.setStyleSheet("QScrollArea { background: transparent; }")
    fill = body.autoFillBackground()       # setWidget() turns it on
    area.setWidget(body)
    body.setAutoFillBackground(fill)
    return area

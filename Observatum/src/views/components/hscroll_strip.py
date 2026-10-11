"""Containers that never force the main window wider.

HScrollStrip: a one-line strip (toolbar, filter bar, row of section buttons).
PageScroll:   a whole tab page (Home; the tabs built on first opening).

When there is room the strip looks exactly like the widget it holds; when the window is
narrower than the widget's row of buttons, a thin horizontal scroll bar appears under it
instead of the whole main window refusing to shrink (review R4, 11 Oct 2026: the filter
bars and toolbars held Observatum at 1,730 px or more).

    layout.addWidget(HScrollStrip(self.filter_bar))

The held widget keeps its own show/hide: `filter_bar.setVisible(False)` hides the strip.
"""

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtWidgets import QFrame, QScrollArea, QSizePolicy, QWidget


class HScrollStrip(QScrollArea):
    """Holds one widget; scrolls it sideways only when it cannot fit."""

    #: the narrowest the strip asks for (the window decides the rest)
    MIN_WIDTH = 160

    def __init__(self, child: QWidget, parent: QWidget = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.viewport().setAutoFillBackground(False)
        self.setAutoFillBackground(False)
        # hidden on purpose (setVisible(False) before it was added)? A widget never yet
        # shown also reports isHidden(), so ask whether the hide was explicit
        hidden = (child.testAttribute(Qt.WidgetAttribute.WA_WState_ExplicitShowHide)
                  and child.testAttribute(Qt.WidgetAttribute.WA_WState_Hidden))
        # setWidget() shows it...
        fill = child.autoFillBackground()   # ...and makes it paint a background
        self.setWidget(child)
        child.setAutoFillBackground(fill)
        child.installEventFilter(self)
        if hidden:
            child.hide()
            self.hide()
        self._refit()

    # -- size --------------------------------------------------------------

    def _child_height(self) -> int:
        c = self.widget()
        if c is None:
            return 0
        return max(c.sizeHint().height(), c.minimumSizeHint().height(), c.minimumHeight())

    def _needs_bar(self) -> bool:
        c = self.widget()
        if c is None:
            return False
        need = max(c.minimumSizeHint().width(), c.minimumWidth())
        return need > self.width()

    def _refit(self):
        h = self._child_height()
        if self._needs_bar():
            h += self.horizontalScrollBar().sizeHint().height()
        if self.height() != h or self.minimumHeight() != h:
            self.setFixedHeight(h)

    def sizeHint(self) -> QSize:
        c = self.widget()
        w = c.sizeHint().width() if c is not None else self.MIN_WIDTH
        return QSize(w, self.height() or self._child_height())

    def minimumSizeHint(self) -> QSize:
        c = self.widget()
        w = min(self.MIN_WIDTH, c.minimumSizeHint().width()) if c is not None else 0
        return QSize(w, self._child_height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refit()

    # -- follow the held widget ---------------------------------------------

    def eventFilter(self, obj, event):
        if obj is self.widget():
            et = event.type()
            if et == QEvent.Type.ShowToParent:
                self.setVisible(True)
                self._refit()
            elif et == QEvent.Type.HideToParent:
                self.setVisible(False)
            elif et == QEvent.Type.LayoutRequest:
                self._refit()
                self.updateGeometry()
            elif et == QEvent.Type.Resize:
                # The strip changes its own height inside its resizeEvent (scroll bar shown
                # or not). On a page first shown narrow, the held widget then got one resize
                # event with the old, taller size and its layout kept it: the buttons sat
                # 7 px low and were cut off (Examen, R5). Re-check once things settle.
                QTimer.singleShot(0, self, self._sync_child_layout)
        return super().eventFilter(obj, event)

    def _sync_child_layout(self):
        c = self.widget()
        lay = c.layout() if c is not None else None
        if lay is not None and lay.geometry() != c.rect():
            lay.setGeometry(c.rect())


class PageScroll(QScrollArea):
    """A whole tab page that scrolls rather than hold the window wide (or tall).

    At any size the page fits, it looks and behaves exactly as before; below the page's
    own minimum a scroll bar appears. Used for Home (four panels side by side) and for
    the tabs built on first opening (Stats/Reports, Mapping, Settings), R4 11 Oct 2026.
    """

    def __init__(self, page: QWidget, parent: QWidget = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.viewport().setAutoFillBackground(False)
        self.setAutoFillBackground(False)
        fill = page.autoFillBackground()
        self.setWidget(page)
        page.setAutoFillBackground(fill)

    def minimumSizeHint(self) -> QSize:
        return QSize(200, 120)

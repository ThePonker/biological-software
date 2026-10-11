"""Sizing helpers for the Data Entry banner (the row of cards above the grid). R9-8, 11 Oct 2026.

The cards used to have fixed widths and one fixed height (194 px). On Wil's PC (Segoe UI is
taller and wider than the Linux fonts) that clipped the button text in the controls card and,
on a narrower window, pushed the Records legend off the right edge. Now:

* each card has a preferred width (its old fixed width) and a smaller minimum, so the row
  narrows to fit the window instead of running off it (`BannerCard`);
* the banner height is the old 194 px or whatever the cards' rows need at this font, if more
  (`banner_height`), so no button is ever squeezed below its text;
* the legend's check boxes shorten their label with "..." when narrow, the full label on
  hover (`ElidedCheckBox`).

Round 3 fix (11 Oct, Wil's PC): with wider text than on Linux the cards' contents needed more
than their fixed minimum / maximum widths, and the window could not be made narrower than
~1563 px. A card's widths now come from what its contents measure at run time
(`BannerCard.refit`), and the banner sits in a horizontal scroll area (`BannerScroll`), so in
the worst case a scroll bar appears under the banner; the window is never forced wider.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtWidgets import (QCheckBox, QFrame, QScrollArea, QSizePolicy, QStyle,
                               QStyleOptionButton, QWidget)


class BannerCard(QWidget):
    """A banner card: `pref_w` wide when there is room, down to `min_w` when there isn't --
    but never narrower than its own contents measure at this font (`least_width`)."""

    def __init__(self, pref_w: int, min_w: int, parent=None):
        super().__init__(parent)
        self._pref_w = int(pref_w)
        self._min_w = int(min_w)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)  # card QSS background
        self.setMinimumWidth(self._min_w)
        self.setMaximumWidth(self._pref_w)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def least_width(self) -> int:
        """The narrowest this card can be: `min_w`, or its layout's minimum if wider."""
        lay = self.layout()
        need = lay.minimumSize().width() if lay is not None else 0
        return max(self._min_w, need)

    def refit(self):
        """Measure the contents (after polish) and set the minimum and maximum widths."""
        self.ensurePolished()
        least = self.least_width()
        if self.minimumWidth() != least:
            self.setMinimumWidth(least)
        if self.maximumWidth() != max(self._pref_w, least):
            self.setMaximumWidth(max(self._pref_w, least))

    def sizeHint(self):
        return QSize(max(self._pref_w, self.least_width()), super().sizeHint().height())


class BannerScroll(QScrollArea):
    """Holds the banner: no frame, no vertical scroll bar, a horizontal one only when the
    banner can't be narrowed to the window (very wide text). It never asks for more width
    than the window has, and is exactly as tall as the banner (+ the bar when shown)."""

    def __init__(self, inner: QWidget, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self.viewport().setAutoFillBackground(False)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.setWidget(inner)
        inner.installEventFilter(self)
        self.horizontalScrollBar().rangeChanged.connect(lambda *_: self._fit_height())
        self._fit_height()

    def _fit_height(self):
        inner = self.widget()
        if inner is None:
            return
        h = max(inner.minimumHeight(), inner.sizeHint().height())
        bar = self.horizontalScrollBar()
        if bar.maximum() > 0:
            h += bar.sizeHint().height()
        if self.height() != h or self.minimumHeight() != h:
            self.setFixedHeight(h)

    def eventFilter(self, obj, e):
        if obj is self.widget() and e.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest):
            self._fit_height()
        return super().eventFilter(obj, e)

    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())


def banner_height(base: int, widgets) -> int:
    """`base`, or the tallest height the widgets' own layouts need at this font if more."""
    h = int(base)
    for w in widgets:
        if w is None:
            continue
        w.ensurePolished()
        lay = w.layout()
        need = lay.minimumSize().height() if lay is not None else w.minimumSizeHint().height()
        h = max(h, need)
    return h


class ElidedCheckBox(QCheckBox):
    """A check box whose label is shortened with an ellipsis to the width it gets.

    Its minimum width is small, so a narrow card can shrink it; the full label is its
    tooltip whenever the label is shortened.
    """

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def full_text(self) -> str:
        return self._full

    def _box_width(self) -> int:
        """Indicator + gap: everything but the label."""
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        ind = self.style().pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth, opt, self)
        gap = self.style().pixelMetric(QStyle.PixelMetric.PM_CheckBoxLabelSpacing, opt, self)
        return ind + gap + 4

    def sizeHint(self):
        s = super().sizeHint()
        fm = self.fontMetrics()
        extra = fm.horizontalAdvance(self._full) - fm.horizontalAdvance(self.text())
        # at least the width _elide needs to show the whole label (never elided at its hint)
        w = max(s.width() + max(0, extra), self._box_width() + fm.horizontalAdvance(self._full))
        return QSize(w, s.height())

    def minimumSizeHint(self):
        return QSize(self._box_width() + self.fontMetrics().horizontalAdvance("Wwww…"),
                     super().minimumSizeHint().height())

    def _elide(self):
        avail = self.width() - self._box_width()
        fm = self.fontMetrics()
        if fm.horizontalAdvance(self._full) <= avail:
            text = self._full
        else:
            text = fm.elidedText(self._full, Qt.TextElideMode.ElideRight, max(0, avail))
        if text != self.text():
            self.setText(text)
        self.setToolTip("" if text == self._full else self._full)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._elide()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._elide()

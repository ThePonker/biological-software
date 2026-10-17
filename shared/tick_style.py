"""Every check box ticked in the suite's green, with the suite's tick (16 Oct 2026).

shared/tick_mark.py draws the tick; this module gives it to every QCheckBox the application
shows that has no look of its own, once, so a new box needs no styling code.

    from shared.tick_style import install, theme_colours
    install(app, lambda: theme_colours(theme()))      # Observatum's Naturalist theme

colours: a function returning the keys COLOURS (fill = the accent/primary, mark = the tick,
border and background of the empty box). A box that already styles its own indicator, or sits
in a panel whose style sheet does (Lector's window-wide one), is left exactly as it is.
"""
from typing import Callable, Dict, Optional

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QCheckBox, QWidget

from shared.tick_mark import checkbox_qss

COLOURS = ("fill", "mark", "border", "background")
_MARK = "_biosoft_tick_qss"          # the rule this module added (so it can be renewed)


def theme_colours(t) -> Dict[str, str]:
    """The colours from an Observatum-style theme object (anything with .get(key))."""
    return {"fill": t.get("primary"), "mark": t.get("button_primary_text"),
            "border": t.get("border_strong"), "background": t.get("surface")}


def has_own_indicator(box: QCheckBox) -> bool:
    """True if the box, or a widget above it, already has a style sheet for the indicator
    that this module did not add."""
    w: Optional[QWidget] = box
    while w is not None:
        sheet = w.styleSheet() or ""
        added = w.property(_MARK) if w is box else ""
        if added:
            sheet = sheet.replace(added, "")
        if "::indicator" in sheet:
            return True
        w = w.parentWidget()
    return False


def apply(box: QCheckBox, c: Dict[str, str]) -> None:
    """Give one check box the suite's tick (any rules it already has are kept)."""
    added = box.property(_MARK) or ""
    own = (box.styleSheet() or "").replace(added, "") if added else (box.styleSheet() or "")
    rule = checkbox_qss(fill=c["fill"], mark=c["mark"], border=c["border"],
                        background=c["background"])
    box.setStyleSheet(own + rule)
    box.setProperty(_MARK, rule)


def is_styled(box: QCheckBox) -> bool:
    return bool(box.property(_MARK))


_installed = None


class _TickFilter(QObject):
    def __init__(self, colours: Callable[[], Dict[str, str]], parent=None):
        super().__init__(parent)
        self._colours = colours

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.Type.Show and isinstance(obj, QCheckBox)
                and not is_styled(obj) and not has_own_indicator(obj)):
            try:
                apply(obj, self._colours())
            except Exception as e:                      # never stop a box showing
                print(f"[tick_style] {e}")
        return False


def install(app: Optional[QApplication] = None,
            colours: Optional[Callable[[], Dict[str, str]]] = None) -> QObject:
    """Style every check box the application shows (once per application; a second call
    replaces the colours). Returns the event filter."""
    global _installed
    app = app or QApplication.instance()
    if _installed is not None and _installed.parent() is app:
        _installed._colours = colours or _installed._colours
        return _installed
    _installed = _TickFilter(colours, app)
    app.installEventFilter(_installed)
    return _installed


__all__ = ["COLOURS", "apply", "has_own_indicator", "install", "is_styled", "theme_colours"]

"""Every check box ticked in the suite's green, with the suite's tick (16 Oct 2026); every
radio button filled the same green with a dot (17 Oct 2026).

shared/tick_mark.py draws the tick and the dot; this module gives them to every QCheckBox and
QRadioButton the application shows that has no look of its own, once, so a new box needs no
styling code. Ticks inside a list or tree (checkable items) are styled per view with
style_item_view(view).

    from shared.tick_style import install, theme_colours
    install(app, lambda: theme_colours(theme()))      # Observatum's Naturalist theme

colours: a function returning the keys COLOURS (fill = the accent/primary, mark = the tick,
border and background of the empty box). A box that already styles its own indicator, or sits
in a panel whose style sheet does (Lector's window-wide one), is left exactly as it is.
"""
from typing import Callable, Dict, Optional

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QAbstractButton, QApplication, QCheckBox, QRadioButton, QWidget

from shared.tick_mark import checkbox_qss, radio_qss

COLOURS = ("fill", "mark", "border", "background")
_MARK = "_biosoft_tick_qss"          # the rule this module added (so it can be renewed)


def theme_colours(t) -> Dict[str, str]:
    """The colours from an Observatum-style theme object (anything with .get(key))."""
    return {"fill": t.get("primary"), "mark": t.get("button_primary_text"),
            "border": t.get("border_strong"), "background": t.get("surface")}


def has_own_indicator(box: QWidget) -> bool:
    """True if the box, or a widget above it, already has a style sheet for the indicator
    that this module did not add."""
    # a radio button is only held back by a radio rule: a panel styling its check boxes
    # (QCheckBox::indicator) says nothing about its radio buttons, and the reverse
    other = "QCheckBox::indicator" if isinstance(box, QRadioButton) else "QRadioButton::indicator"
    w: Optional[QWidget] = box
    while w is not None:
        sheet = w.styleSheet() or ""
        added = w.property(_MARK) if w is box else ""
        if added:
            sheet = sheet.replace(added, "")
        if "::indicator" in sheet.replace(other, ""):
            return True
        w = w.parentWidget()
    return False


def apply(box: QAbstractButton, c: Dict[str, str]) -> None:
    """Give one check box the suite's tick, or one radio button the suite's dot (any rules it
    already has are kept)."""
    added = box.property(_MARK) or ""
    own = (box.styleSheet() or "").replace(added, "") if added else (box.styleSheet() or "")
    qss = radio_qss if isinstance(box, QRadioButton) else checkbox_qss
    rule = qss(fill=c["fill"], mark=c["mark"], border=c["border"], background=c["background"])
    box.setStyleSheet(own + rule)
    box.setProperty(_MARK, rule)


def is_styled(box: QWidget) -> bool:
    return bool(box.property(_MARK))


_installed = None


class _TickFilter(QObject):
    def __init__(self, colours: Callable[[], Dict[str, str]], parent=None):
        super().__init__(parent)
        self._colours = colours

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.Type.Show and isinstance(obj, (QCheckBox, QRadioButton))
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


def style_item_view(view: QWidget, colours: Optional[Dict[str, str]] = None) -> None:
    """The suite's tick for the checkable items of a list or tree (QListWidget, QTreeWidget):
    their tick boxes are drawn by the view, so the box filter above never sees them. Uses the
    installed colours unless given; does nothing if none are known or the view styles its own
    indicator."""
    c = colours or (_installed._colours() if _installed is not None and _installed._colours
                    else None)
    if not c or has_own_indicator(view):
        return
    sel = type(view).__name__
    view.setStyleSheet((view.styleSheet() or "") + checkbox_qss(
        fill=c["fill"], mark=c["mark"], border=c["border"], background=c["background"],
        selector=sel) + f"""
        {sel}::indicator:indeterminate {{ border: 2px solid {c["fill"]};
            background-color: {c["background"]}; }}
    """)                                   # part of a group ticked: a green outline


__all__ = ["COLOURS", "apply", "has_own_indicator", "install", "is_styled", "style_item_view",
           "theme_colours"]

"""Drop-down lists always have a solid background (F50, 12 Oct 2026).

Many panels clear their own background with a style sheet that has no selector, e.g.
`box.setStyleSheet("background: transparent; border: none;")`. Such a rule applies to every
widget inside the panel -- including the pop-up list of a QComboBox (or a QCompleter) that
sits in it, so the list was drawn see-through over the form behind it, with the window's
drop shadow showing as a "text shadow" (Quick Entry's Project list).

install(app) fixes it once for the whole application: when a combo box's pop-up (or a
completer's list) is about to show and its background has come out transparent, the list
is given a style sheet of its own with a solid background (a widget's own style sheet wins
over any it inherits, whatever their selectors). Pop-ups that already have a solid
background are left exactly as they are.

    from shared.opaque_popups import install
    install(app, lambda: (theme().get('surface'), theme().get('text_primary')))

colours: a function returning (background, text) colour strings from the app's theme --
called each time, so a theme change is followed. Without it, the application palette's
Base and Text colours are used.
"""
from typing import Callable, Optional, Tuple

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QAbstractItemView, QApplication, QComboBox, QWidget

_MARK = "_opaque_popup_qss"     # the style sheet this module gave a widget (so it can be renewed)


def is_see_through(view: QAbstractItemView) -> bool:
    """True when the list's background would not be painted (no brush, or a clear colour)."""
    brush = view.viewport().palette().brush(view.viewport().backgroundRole())
    base = view.palette().brush(QPalette.ColorRole.Base)
    return any(b.style() == Qt.BrushStyle.NoBrush or b.color().alpha() < 255 for b in (brush, base))


def _own_sheet(widget: QWidget) -> str:
    """The widget's own style sheet without anything this module added."""
    sheet = widget.styleSheet() or ""
    added = widget.property(_MARK) or ""
    return sheet.replace(added, "") if added else sheet


def make_opaque(view: QAbstractItemView, background: str, text: str) -> bool:
    """Give a pop-up list (and the frame round a combo box's list) a solid background if it
    has come out see-through. Returns True if it changed anything."""
    if not view.property(_MARK) and not is_see_through(view):
        return False                  # (one made solid here is renewed: a theme may change)
    rule_view = f"QAbstractItemView {{ background-color: {background}; color: {text}; }}"
    targets = [(view, rule_view)]
    frame = view.parentWidget()
    if frame is not None and frame.isWindow() and frame is not view:
        targets.append((frame, f"{frame.metaObject().className()} "
                               f"{{ background-color: {background}; }}"))
    for w, rule in targets:
        w.setStyleSheet(_own_sheet(w) + rule)
        w.setProperty(_MARK, rule)
    return True


def _popup_view(obj) -> Optional[QAbstractItemView]:
    """The list of a pop-up window about to show: a combo box's list frame, or a completer's
    list (a top-level item view)."""
    if not isinstance(obj, QWidget) or not obj.isWindow():
        return None
    if isinstance(obj, QAbstractItemView):
        return obj
    if obj.metaObject().className() == "QComboBoxPrivateContainer":
        combo = obj.parentWidget()
        if isinstance(combo, QComboBox):
            return combo.view()
        return obj.findChild(QAbstractItemView)
    return None


_installed = None


class _PopupFilter(QObject):
    def __init__(self, colours: Optional[Callable[[], Tuple[str, str]]], parent=None):
        super().__init__(parent)
        self._colours = colours

    def colours(self) -> Tuple[str, str]:
        if self._colours is not None:
            try:
                return self._colours()
            except Exception as e:                    # never stop a list opening
                print(f"[opaque_popups] theme colours unavailable: {e}")
        pal = QApplication.palette()
        return (pal.color(QPalette.ColorRole.Base).name(),
                pal.color(QPalette.ColorRole.Text).name())

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show:
            view = _popup_view(obj)
            if view is not None:
                try:
                    make_opaque(view, *self.colours())
                except Exception as e:
                    print(f"[opaque_popups] {e}")
        return False


def install(app: Optional[QApplication] = None,
            colours: Optional[Callable[[], Tuple[str, str]]] = None) -> QObject:
    """Watch every pop-up list the application opens (once per application; a second call
    replaces the colours). Returns the event filter."""
    global _installed
    app = app or QApplication.instance()
    if _installed is not None and _installed.parent() is app:
        _installed._colours = colours or _installed._colours
        return _installed
    _installed = _PopupFilter(colours, app)
    app.installEventFilter(_installed)
    return _installed


__all__ = ["install", "make_opaque", "is_see_through"]

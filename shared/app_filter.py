"""One application-wide event filter for the suite's install()-style helpers (Round 16, C2).

Four modules (tick_style, calendar_style, opaque_popups, dialog_geometry) each used to put a
Python event filter on the QApplication, so every event of every widget went through four
Python calls (measured 3.6 us per event against 0.3 us with none). Now they register a handler
here for the few event types they need, and this module installs ONE filter whose eventFilter
returns at once for any other event type.

    from shared import app_filter
    app_filter.register(app, "my_name", handler, (QEvent.Type.Show,))

handler(obj, event) is called for those event types only; its return value is ignored (none of
the handlers ever consumed an event). Registering the same name again replaces the handler.
"""
from __future__ import annotations

import traceback
from typing import Callable, Dict, Iterable, List, Tuple

from PySide6.QtCore import QEvent, QObject

Handler = Callable[[object, QEvent], object]


class AppFilter(QObject):
    def __init__(self, app):
        super().__init__(app)
        self._entries: Dict[str, Tuple[Handler, Tuple[QEvent.Type, ...]]] = {}
        self._by_type: Dict[QEvent.Type, List[Handler]] = {}

    def register(self, name: str, handler: Handler, types: Iterable[QEvent.Type]) -> None:
        self._entries[name] = (handler, tuple(types))
        self._rebuild()

    def unregister(self, name: str) -> None:
        if self._entries.pop(name, None) is not None:
            self._rebuild()

    def _rebuild(self) -> None:
        by_type: Dict[QEvent.Type, List[Handler]] = {}
        for handler, types in self._entries.values():
            for t in types:
                by_type.setdefault(t, []).append(handler)
        self._by_type = by_type

    def eventFilter(self, obj, event):
        handlers = self._by_type.get(event.type())
        if handlers:                                 # every other event type: straight through
            for h in tuple(handlers):
                try:
                    h(obj, event)
                except Exception:                # one failing handler must not skip the rest
                    traceback.print_exc()
        return False


_filter = None


def get(app) -> AppFilter:
    """The application's one filter (made and installed on first use)."""
    global _filter
    if _filter is None or _filter.parent() is not app:
        _filter = AppFilter(app)
        app.installEventFilter(_filter)
    return _filter


def register(app, name: str, handler: Handler, types: Iterable[QEvent.Type]) -> AppFilter:
    f = get(app)
    f.register(name, handler, types)
    return f


def unregister(app, name: str) -> None:
    if _filter is not None and _filter.parent() is app:
        _filter.unregister(name)


__all__ = ["AppFilter", "get", "register", "unregister"]

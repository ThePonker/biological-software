"""A tab page that builds its real contents on request: all at once (ensure_built), or a
piece at a time (build_steps).

The main window puts one of these in the tab bar for Stats/Reports, Mapping and Settings.
Round 4 (startup speed, 11 Oct 2026) built them on first opening; Round 5 built them under
the splash screen. Round 6 (Wil: "window early, rest behind") builds them in the background
after the window has opened, in short slices (background_loader.py drives build_steps), so
the window keeps responding; until then the page says "Finishing loading…". Building on
first opening (ensure_built) remains the fallback when the background build failed.

    page = LazyTabPage(build_mapping_parts, "Mapping")   # a generator function, see below
    tabs.addTab(page, "Mapping")
    ...
    page.ensure_built()   # -> the real tab widget, built once

`parts()` is a generator function: it builds the tab, yields between pieces (each a short
stretch of work on the GUI thread) and returns the tab widget. A plain function returning
the widget is accepted too.
"""

import inspect
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

PENDING_TEXT = "Finishing loading…"


class LazyTabPage(QWidget):
    """Placeholder page; the real tab is built by `parts()` when first needed."""

    def __init__(self, parts: Callable, name: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._parts = parts
        self._name = name
        self._building = False
        self._gen = None              # the build in progress (shared by both ways of building)
        # True while the background loader is going to build this page: showing it then
        # does not build it at once (the loader is told to do it next instead)
        self.deferred = False
        self.page: Optional[QWidget] = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QLabel(PENDING_TEXT)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._style_placeholder()
        layout.addWidget(self._placeholder)

    @property
    def is_built(self) -> bool:
        return self.page is not None

    def _style_placeholder(self):
        try:
            from ..themes import theme
            self._placeholder.setStyleSheet(
                f"color: {theme().get('text_secondary')}; font-size: 13px;")
        except Exception:
            pass

    def _generator(self):
        """The build in progress, or a new one."""
        if self._gen is None:
            made = self._parts()
            if not inspect.isgenerator(made):         # a plain factory: built already
                def done(tab=made):
                    return tab
                    yield                             # never reached: makes this a generator
                made = done()
            self._gen = made
        return self._gen

    def _advance(self) -> bool:
        """One piece of the build; True when the tab is built (and installed)."""
        try:
            next(self._generator())
            return False
        except StopIteration as stop:
            self._gen = None
            self._install(stop.value)
            return True
        except BaseException:
            self._gen = None                          # a failed build starts again next time
            raise

    def build_steps(self):
        """Build the tab a piece at a time: a generator yielding between pieces; returns the
        tab. Safe to mix with ensure_built() (they continue the same build)."""
        while self.page is None:
            if self._advance():
                break
            yield
        return self.page

    def ensure_built(self) -> Optional[QWidget]:
        """Build the real tab now if it is not built yet (finishing a background build
        already under way); return it."""
        if self.page is None and not self._building:
            self._building = True
            try:
                while not self._advance():
                    pass
            finally:
                self._building = False
        return self.page

    def _install(self, page: QWidget):
        self.page = page
        self.deferred = False
        layout = self.layout()
        layout.removeWidget(self._placeholder)
        self._placeholder.hide()
        self._placeholder.deleteLater()
        # in a scroll area: a page wider than the window scrolls rather than hold
        # the main window wide (R4: Mapping and Stats/Reports with wide text)
        from .components.hscroll_strip import PageScroll
        self._scroll = PageScroll(page)
        layout.addWidget(self._scroll)

    def showEvent(self, event):
        # Safety net: however the page comes on screen, it is never left empty -- unless the
        # background loader is about to build it (it shows "Finishing loading…" meanwhile)
        super().showEvent(event)
        if self.page is None and not self.deferred:
            self.ensure_built()

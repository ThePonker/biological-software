"""A tab page that builds its real contents the first time it is opened.

The main window puts one of these in the tab bar for a tab that nothing needs at
startup (Stats/Reports, Mapping, Settings). Building the Mapping tab alone loaded and
projected every vice-county outline (several seconds) before the window could open
(startup speed, 11 Oct 2026).

    page = LazyTabPage(build_mapping_tab, "Mapping")
    tabs.addTab(page, "Mapping")
    ...
    page.ensure_built()   # -> the real tab widget, built once
"""

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LazyTabPage(QWidget):
    """Placeholder page; the real tab is built by `factory()` on first need."""

    def __init__(self, factory: Callable[[], QWidget], name: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._factory = factory
        self._name = name
        self._building = False
        self.page: Optional[QWidget] = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QLabel(f"Opening {name}…")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._placeholder)

    @property
    def is_built(self) -> bool:
        return self.page is not None

    def ensure_built(self) -> Optional[QWidget]:
        """Build the real tab if it is not built yet; return it."""
        if self.page is None and not self._building:
            self._building = True
            try:
                page = self._factory()
            finally:
                self._building = False
            self.page = page
            layout = self.layout()
            layout.removeWidget(self._placeholder)
            self._placeholder.hide()
            self._placeholder.deleteLater()
            # in a scroll area: a page wider than the window scrolls rather than hold
            # the main window wide (R4: Mapping and Stats/Reports with wide text)
            from .components.hscroll_strip import PageScroll
            self._scroll = PageScroll(page)
            layout.addWidget(self._scroll)
        return self.page

    def showEvent(self, event):
        # Safety net: however the page comes on screen, it is never left empty
        super().showEvent(event)
        if self.page is None:
            self.ensure_built()

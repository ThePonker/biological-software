"""Contributed records window (Round 20, 11 Nov 2026).

The Contributed tab became a button, "Contributed records...", on the Observation Data filter
bar. This wraps the unchanged ContributedTab in a non-modal dialog; the main window keeps one
(MainWindow.open_contributed_records). The tab is read-only, so closing the window has no
pending work to lose; its records are read when the window is first opened.
"""
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget

from shared.fit_to_screen import available_geometry, fit_to_screen
from .contributed_tab import ContributedTab

GEOMETRY_SETTING = "contributed/dialog_geometry"
SHARE_OF_WINDOW = 0.85          # of the main window, before fit_to_screen trims it


class ContributedDialog(QDialog):
    """Non-modal window holding the Contributed records browser."""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Contributed records")
        self.setModal(False)
        self.setSizeGripEnabled(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.contributed_tab = ContributedTab(self)
        layout.addWidget(self.contributed_tab)
        self._size_from(parent)
        fit_to_screen(self)

    def _size_from(self, parent: QWidget):
        """The remembered size, else about 85 % of the main window (or the free desktop)."""
        try:
            geom = QSettings().value(GEOMETRY_SETTING)
            if geom and self.restoreGeometry(geom):
                return
        except Exception:
            pass
        base = parent.window().size() if parent is not None else available_geometry().size()
        self.resize(int(base.width() * SHARE_OF_WINDOW), int(base.height() * SHARE_OF_WINDOW))

    def show_records(self, text: str = ""):
        """Open (or raise) the window; `text` goes into its filter box when given."""
        self.contributed_tab.initialize()               # reads on first opening only
        if text:
            self.contributed_tab.search_edit.setText(text)
            self.contributed_tab._load_records()
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def done(self, result):
        try:
            QSettings().setValue(GEOMETRY_SETTING, self.saveGeometry())
        except Exception as e:
            print(f"[Contributed] window size not saved: {e}")
        super().done(result)

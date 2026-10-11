"""A plain cover over a tab whose records are still loading: "Finishing loading…".

Round 6 (11 Oct 2026): the Recording Scheme tab is a real tab from the start (other code
reaches into it), but its records load in the background after the window opens. Until they
are shown it is covered by this label, in the theme's colours, which follows the tab's size;
it is hidden the moment the records are in. Not a dialog: nothing pops up.
"""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QLabel, QWidget


class PendingCover(QLabel):
    def __init__(self, over: QWidget, text: str):
        super().__init__(text, over)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setObjectName("pendingCover")
        try:
            from ..themes import theme
            t = theme()
            self.setStyleSheet(f"QLabel#pendingCover {{ background-color: {t.get('background')};"
                               f" color: {t.get('text_secondary')}; font-size: 13px; }}")
        except Exception:
            pass
        self.setGeometry(over.rect())
        over.installEventFilter(self)
        self.raise_()
        self.show()

    def eventFilter(self, obj, event):
        if obj is self.parent() and event.type() == QEvent.Type.Resize:
            self.setGeometry(obj.rect())
            self.raise_()
        return False

"""The "Open in iRecord" button (R9-3, 11 Oct 2026).

One button for every record window: it opens the record's own page on iRecord in the
browser. The link pattern is shared/irecord_links.py. A record with no iRecord ID gets no
button (irecord_button_for returns None); in a list the button greys out instead
(set_irecord_id(None)) and says why.
"""
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QPushButton

from shared.irecord_links import irecord_id_of, irecord_url

from ...themes import theme

NO_ID_TIP = "This record has no iRecord ID: it has not been into iRecord."


class IRecordButton(QPushButton):
    """Outlined (secondary) button opening one record's iRecord page."""

    def __init__(self, irecord_id=None, parent=None):
        super().__init__("Open in iRecord", parent)
        self.setObjectName("irecord_button")
        self.setStyleSheet(theme().button_secondary_style())
        self.open_url = QDesktopServices.openUrl          # replaceable in tests
        self._url: Optional[str] = None
        self.clicked.connect(self._open)
        self.set_irecord_id(irecord_id)

    def set_irecord_id(self, irecord_id) -> None:
        """Point the button at a record (None / blank: greyed out, with the reason)."""
        self._url = irecord_url(irecord_id)
        self.setEnabled(self._url is not None)
        if self._url:
            self.setToolTip(f"iRecord record {irecord_id_of(irecord_id)}: open its page "
                            f"in your browser\n{self._url}")
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setToolTip(NO_ID_TIP)
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def url(self) -> Optional[str]:
        return self._url

    def _open(self) -> None:
        if self._url:
            self.open_url(QUrl(self._url))


def irecord_button_for(record: Optional[dict], parent=None) -> Optional[IRecordButton]:
    """The button for a record dict holding an iRecord ID, or None (no button shown)."""
    rid = (record or {}).get("irecord_id")
    return IRecordButton(rid, parent) if irecord_url(rid) else None

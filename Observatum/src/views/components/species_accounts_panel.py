"""
Species accounts panel -- the right-hand column of the Record Detail windows.

  * Your account at the top, in the opening tab's colours (accent, accent_light,
    accent_dark from TabColors) -- the text reports use.
  * Published review accounts below, in full, newest first, each cited;
    superseded ones last; non-open licences marked "internal reference".

Reads both layers through shared/species_accounts.py, so review text is never
mistaken for yours. Emits edit_requested; the host window opens the editor and
calls refresh() afterwards.
"""
import html

from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QWidget)
from PySide6.QtCore import Qt, Signal

from ...themes import theme

try:
    from shared.species_accounts import get_species_accounts
except Exception:
    get_species_accounts = None


def _ddmmyyyy(s):
    s = (s or "")[:10]
    return f"{s[8:10]}/{s[5:7]}/{s[:4]}" if len(s) == 10 and s[4] == "-" else s


class SpeciesAccountsPanel(QFrame):
    edit_requested = Signal()

    def __init__(self, tvk, species_name, accent, accent_light, accent_dark, parent=None):
        super().__init__(parent)
        self._tvk = (tvk or "").strip() or None
        self._name = (species_name or "").strip() or None
        self._accent, self._light, self._dark = accent, accent_light, accent_dark
        t = theme()
        self._t = t
        self.setStyleSheet("QFrame { background: transparent; border: none; }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel("Species accounts")
        title.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {t.get('text_primary')};")
        head.addWidget(title)
        head.addStretch()
        self._btn = QPushButton("Edit my account")
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setStyleSheet(f"""
            QPushButton {{ background-color: {accent}; color: white; border: none;
                          border-radius: {t.get('radius_sm')}; padding: 4px 12px;
                          font-size: 11px; font-weight: 600; }}
            QPushButton:hover {{ background-color: {accent_dark}; }}
        """)
        self._btn.clicked.connect(self.edit_requested.emit)
        head.addWidget(self._btn)
        outer.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 4, 0)
        self._body_layout.setSpacing(8)
        scroll.setWidget(self._body)
        outer.addWidget(scroll, 1)

        self.refresh()

    # ------------------------------------------------------------------
    def _label(self, rich, style):
        lab = QLabel(rich)
        lab.setTextFormat(Qt.TextFormat.RichText)
        lab.setWordWrap(True)
        lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lab.setStyleSheet(style)
        return lab

    @staticmethod
    def _paras(text):
        return "".join(f"<p style='margin:4px 0'>{html.escape(p).replace(chr(10), '<br>')}</p>"
                       for p in (text or "").split("\n\n") if p.strip())

    def refresh(self, *_):
        """Reload both layers from the databases and redraw."""
        while self._body_layout.count():
            item = self._body_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        t = self._t
        acc = None
        if get_species_accounts is not None and (self._tvk or self._name):
            try:
                acc = get_species_accounts(self._tvk, self._name)
            except Exception as e:
                print(f"Species accounts: {e}")
        own = acc.own if acc else None
        reviews = acc.reviews if acc else []

        # Your account -- tab colours
        meta = "used in reports"
        if own and acc and acc.own_updated:
            meta += f" · updated {_ddmmyyyy(acc.own_updated)}"
        body = self._paras(own) if own else \
            "<p style='margin:4px 0'><i>No account of your own yet.</i></p>"
        self._body_layout.addWidget(self._label(
            f"<div style='color:{self._dark}; font-size:11px'><b>Your account</b> &nbsp;·&nbsp; {meta}</div>{body}",
            f"QLabel {{ background-color: {self._light}; border: 1px solid {self._accent}; "
            f"border-radius: {t.get('radius_md')}; padding: 9px 11px; color: {t.get('text_primary')}; "
            f"font-size: 12px; }}"))
        self._btn.setText("Edit my account" if own else "Write my account")
        if not self._tvk:
            self._btn.setEnabled(False)
            self._btn.setToolTip("This record has no TVK, so an account cannot be saved for it.")

        # Published accounts
        sub = t.get('text_secondary', t.get('text_primary'))
        n = len(reviews)
        self._body_layout.addWidget(self._label(
            f"<b>Published accounts ({n})</b> — reference" if n else
            "<b>Published accounts</b> — none for this species",
            f"QLabel {{ color: {sub}; font-size: 11px; padding-top: 4px; }}"))
        for r in reviews:
            year = (r.date_published or "")[:4]
            cite = r.author or r.cite
            if year and year not in cite:
                cite = f"{cite} {year}"
            head = f"<b>{html.escape(cite)}</b>"
            if r.review_name:
                head += f" — {html.escape(r.review_name)}"
            notes = []
            if r.superseded:
                notes.append("superseded")
            lic = (r.licence or "").lower()
            if not lic or "internal" in lic or "not openly" in lic:
                notes.append("internal reference — not for reports")
            if notes:
                head += f"<br><i>{'; '.join(notes)}</i>"
            colour = sub if r.superseded else t.get('text_primary')
            self._body_layout.addWidget(self._label(
                f"<div style='font-size:11px'>{head}</div>{self._paras(r.text)}",
                f"QLabel {{ background-color: {t.get('surface')}; border: 1px solid {t.get('border')}; "
                f"border-radius: {t.get('radius_md')}; padding: 9px 11px; color: {colour}; font-size: 12px; }}"))
        self._body_layout.addStretch()

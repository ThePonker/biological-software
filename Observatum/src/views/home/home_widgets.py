"""Small shared pieces of the redesigned Home cards (Round 19): links, toggles, headings."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton

from shared.text_sizes import font_css
from ...themes import theme


def link_button(text: str, color: str = "") -> QPushButton:
    """A flat, underline-on-hover text link."""
    t = theme()
    b = QPushButton(text)
    b.setFlat(True)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton {{ color: {color or t.get('success_text')}; font-size: {font_css('small')};"
        " padding: 0; border: none; background: transparent; text-align: right; }"
        "QPushButton:hover { text-decoration: underline; }")
    return b


def pill_button(text: str) -> QPushButton:
    """A small checkable pill (Newest / Highest status / Personal only)."""
    t = theme()
    b = QPushButton(text)
    b.setCheckable(True)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton {{ font-size: {font_css('caption')}; padding: 3px 8px; border-radius: 11px;"
        f" border: 1px solid {t.get('border_strong', t.get('border'))}; background: {t.get('surface')};"
        f" color: {t.get('text_primary')}; }}"
        f"QPushButton:checked {{ border: 1px solid {t.get('success')}; background: {t.get('success_bg')};"
        f" color: {t.get('success_text')}; }}")
    return b


def note_label(text: str = "", wrap: bool = True) -> QLabel:
    """A caption-size muted line."""
    t = theme()
    lab = QLabel(text)
    lab.setWordWrap(wrap)
    lab.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {font_css('caption')};"
                      " border: none; background: transparent;")
    return lab

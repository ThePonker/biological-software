"""The 1940s theme's main-window header: the tab bar area in cloth green with a mustard rule under
it, cream tab text, and a small beetle mark in its left corner (R21).

The colours are theme tokens (header_bg, header_rule, header_text, header_mark). Naturalist
leaves them '' so header_style() returns '' and add_header_mark() does nothing: its window style
sheet is exactly what it was.
"""
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel, QTabWidget

from shared.text_sizes import font_css

# A simple beetle seen from above: body, wing-case line, head, six legs, two antennae.
BEETLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<g fill="{c}" stroke="{c}" stroke-linecap="round">
<ellipse cx="32" cy="38" rx="14" ry="18" stroke="none"/>
<ellipse cx="32" cy="17" rx="7" ry="6" stroke="none"/>
<g fill="none" stroke-width="3">
<path d="M18 30 L8 24"/><path d="M18 40 L7 42"/><path d="M19 49 L10 58"/>
<path d="M46 30 L56 24"/><path d="M46 40 L57 42"/><path d="M45 49 L54 58"/>
<path d="M28 12 L23 4"/><path d="M36 12 L41 4"/></g></g>
<path d="M32 22 L32 56" stroke="{bg}" stroke-width="2" fill="none"/></svg>"""


def header_style(t) -> str:
    """Style sheet text for the main window's tab bar, or '' when the theme has no header.

    MainWindow puts it BEFORE its per-tab `nth-of-type` rules: Qt does not know that pseudo-state,
    and the rules after the first one that uses it are not applied."""
    bg, rule, text = t.get('header_bg', ''), t.get('header_rule', ''), t.get('header_text', '')
    if not (bg and rule and text):
        return ""
    return f"""
        /* 1940s header: cloth-green tab bar, mustard rule, cream text */
        QTabWidget {{ background-color: {bg}; }}
        QTabWidget::pane {{ border: none; border-top: 3px solid {rule};
            background-color: {t.get('background')}; }}
        QTabBar {{ background-color: {bg}; }}
        QTabBar::tab {{ background-color: {bg}; color: {text}; font-size: {font_css('body')};
            border-bottom: 3px solid transparent; }}
        QTabBar::tab:hover {{ background-color: {t.get('primary_hover')}; }}
        QTabBar::tab:selected {{ background-color: {bg}; color: {text}; font-weight: 700;
            border-bottom-color: {rule}; }}
        QTabBar::tab:first:selected {{ border-bottom-color: {rule}; }}
        QTabBar QToolButton {{ background-color: {bg}; border: none; }}
    """


def beetle_pixmap(colour: str, background: str, size: int = 28) -> QPixmap:
    """The beetle mark drawn from the inline SVG, `size` px square, on a transparent ground."""
    svg = BEETLE_SVG.format(c=colour, bg=background).encode()
    renderer = QSvgRenderer(QByteArray(svg))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    renderer.render(p, QRectF(0, 0, size, size))
    p.end()
    return pm


def beetle_icon(colour: str, background: str, size: int = 28) -> QIcon:
    return QIcon(beetle_pixmap(colour, background, size))


def add_header_mark(tabs: QTabWidget, t) -> QLabel:
    """Put the beetle in the tab bar's left corner (None when the theme has no header)."""
    mark, bg = t.get('header_mark', ''), t.get('header_bg', '')
    if not (mark and bg):
        return None
    tabs.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)   # the green runs the full width
    label = QLabel()
    label.setPixmap(beetle_pixmap(mark, bg))
    label.setContentsMargins(12, 2, 6, 2)
    label.setStyleSheet(f"background-color: {bg};")
    tabs.setCornerWidget(label, Qt.Corner.TopLeftCorner)
    return label

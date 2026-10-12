"""Lector's look: Observatum's Naturalist theme (src.themes.theme), nothing hardcoded.

Lector's own accent is the theme's Steel Blue (accent_stats: Stats & Reports, the
closest to a library); it marks the navigation, view buttons and links, as each
Observatum tab uses its own accent. Buttons follow the suite's colour system:
primary Moss Green (Save / Run / Create), navigate/view in the accent, cancel warm
grey outlined, delete crimson outlined.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout
from src.themes import theme

T = theme()
ACCENT, ACCENT_LIGHT, ACCENT_DARK = (T.get("accent_stats"), T.get("accent_stats_light"),
                                     T.get("accent_stats_dark"))

# review status / tag -> (badge variant, label)
STATUS_LABELS = {"unreviewed": "Unreviewed", "relevant": "Relevant",
                 "not_relevant": "Not relevant", "record_extracted": "Record extracted"}
STATUS_BADGE = {"unreviewed": "default", "relevant": "success", "not_relevant": "error",
                "record_extracted": "info"}
TAG_LABELS = {"record": "Record", "biology": "Biology", "mention": "Mention",
              "index": "Index or list"}


def c(key):
    """A theme colour."""
    return T.get(key)


def border_of(variant):
    """'warning' -> warning_border (or the variant's own colour where the theme has none)."""
    return T.get(variant + "_border", None) or T.get(variant)


def app_qss():
    """The window-wide stylesheet: background, inputs, tables, scroll bars, check boxes."""
    return f"""
        QMainWindow, QWidget#lectorPage, QStackedWidget {{ background: {c('background')}; }}
        QLabel {{ color: {c('text_primary')}; }}
        {T.input_style()}
        QPlainTextEdit, QTextBrowser {{ background: {c('input_bg')}; color: {c('text_primary')};
            border: 1px solid {c('border')}; border-radius: {c('radius_sm')}; }}
        QPlainTextEdit:focus {{ border: 2px solid {c('focus_border')}; }}
        {T.table_style()}
        QListWidget {{ background: {c('surface')}; border: 1px solid {c('border')};
            border-radius: {c('radius_md')}; color: {c('text_primary')}; outline: none; }}
        QListWidget::item {{ padding: 6px 8px; border-bottom: 1px solid {c('separator')}; }}
        QListWidget::item:selected {{ background: {ACCENT_LIGHT}; color: {c('text_primary')};
            border-left: 3px solid {ACCENT}; }}
        {T.scrollbar_style()}
        {T.checkbox_style()}
        QRadioButton {{ color: {c('text_primary')}; spacing: 8px; }}
        {T.tooltip_style()}
        {T.status_bar_style()}
        QProgressBar {{ background: {c('surface_alt')}; border: 1px solid {c('border')};
            border-radius: {c('radius_sm')}; text-align: center; color: {c('text_primary')};
            min-height: 14px; max-height: 14px; }}
        QProgressBar::chunk {{ background: {ACCENT}; border-radius: {c('radius_sm')}; }}
        QTabBar::tab {{ padding: 6px 14px; border: none; border-bottom: 3px solid transparent;
            background: transparent; color: {c('text_secondary')}; }}
        QTabBar::tab:selected {{ color: {ACCENT_DARK}; border-bottom-color: {ACCENT};
            font-weight: 600; }}
        QTabWidget::pane {{ border: none; }}
        QSplitter::handle {{ background: {c('background')}; }}
    """


def nav_qss():
    """Left navigation: surface panel, the current page in the accent (as a tab header)."""
    return f"""
        QFrame#lectorNav {{ background: {c('surface')}; border: none;
            border-right: 1px solid {c('border')}; }}
        QFrame#lectorNav QLabel {{ background: transparent; border: none; }}
        QFrame#lectorNav QPushButton {{ text-align: left; padding: 9px 12px; border: none;
            border-left: 4px solid transparent; border-radius: 0;
            background: transparent; color: {c('text_secondary')};
            font-size: {T.font_size('base')}; }}
        QFrame#lectorNav QPushButton:hover {{ background: {c('hover')}; }}
        QFrame#lectorNav QPushButton:checked {{ background: {ACCENT_LIGHT}; color: {ACCENT_DARK};
            border-left: 4px solid {ACCENT}; font-weight: 600; }}
    """


def button_qss(kind="primary"):
    """primary (Moss Green), view (accent, filled), outline (accent, outlined),
    cancel (warm grey outlined), delete (crimson outlined), link (accent text)."""
    if kind == "primary":
        return T.button_primary_style()
    if kind == "cancel":
        return T.button_cancel_style()
    if kind == "delete":
        return T.button_delete_style()
    if kind == "link":
        return (f"QPushButton {{ color: {ACCENT}; background: transparent; border: none;"
                f" padding: 2px 4px; text-decoration: underline; }}"
                f"QPushButton:hover {{ color: {ACCENT_DARK}; }}"
                f"QPushButton:disabled {{ color: {c('text_muted')}; text-decoration: none; }}")
    filled = kind == "view"
    return f"""
        QPushButton {{ background: {ACCENT if filled else 'transparent'};
            color: {c('primary_text') if filled else ACCENT};
            border: 1px solid {ACCENT}; border-radius: {c('radius_md')}; padding: 6px 12px;
            font-size: {T.font_size('base')}; {'font-weight: 600;' if filled else ''} }}
        QPushButton:hover {{ background: {ACCENT_DARK if filled else ACCENT_LIGHT}; }}
        QPushButton:checked {{ background: {ACCENT_LIGHT}; color: {ACCENT_DARK};
            border: 2px solid {ACCENT}; font-weight: 600; }}
        QPushButton:disabled {{ background: {c('disabled_bg')}; color: {c('disabled_text')};
            border-color: {c('disabled_border')}; }}
    """


def button(text, kind="primary", tip=None, slot=None):
    b = QPushButton(text)
    b.setStyleSheet(button_qss(kind))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if tip:
        b.setToolTip(tip)
    if slot:
        b.clicked.connect(slot)
    b.ensurePolished()
    b.setMinimumHeight(b.sizeHint().height())      # never squashed in a short window
    return b


def label(text="", kind="body", wrap=False):
    """kind: h1 (page title), h2 (card title), caps (small capitals header),
    body, muted, small, warn."""
    lab = QLabel(text)
    styles = {
        "h1": f"font-size: {T.font_size('3xl')}; font-weight: 700; color: {c('text_primary')};",
        "h2": f"font-size: {T.font_size('xl')}; font-weight: 700; color: {c('text_primary')};",
        "caps": (f"font-size: {T.font_size('sm')}; font-weight: 600; letter-spacing: 1px;"
                 f" color: {c('text_heading')};"),
        "body": f"color: {c('text_primary')};",
        "muted": f"color: {c('text_secondary')};",
        "small": f"color: {c('text_secondary')}; font-size: {T.font_size('sm')};",
        "warn": f"color: {c('warning_text')};",
    }
    lab.setStyleSheet(styles.get(kind, styles["body"]) + " background: transparent; border: none;")
    lab.setWordWrap(wrap)
    if kind == "caps":
        lab.setText(text.upper())
    return lab


def badge(text, variant="default"):
    lab = QLabel(text)
    lab.setStyleSheet(T.badge_style(variant))
    return lab


def note_box(text, variant="warning"):
    """A coloured note (warning / info / success) that wraps."""
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setTextFormat(Qt.TextFormat.RichText)
    lab.setStyleSheet(f"background: {c(variant + '_bg')}; color: {c(variant + '_text')};"
                      f" border: 1px solid {border_of(variant)};"
                      f" border-radius: {c('radius_md')}; padding: 8px 10px;")
    return lab


class Card(QFrame):
    """A white panel as Observatum's Home cards: optional title, a vertical layout."""

    def __init__(self, title=None, parent=None, variant=None):
        super().__init__(parent)
        self.setObjectName("lectorCard")
        bg, border = c("surface"), c("border")
        if variant:
            bg, border = c(variant + "_bg"), border_of(variant)
        self.setStyleSheet(f"QFrame#lectorCard {{ background: {bg}; border: 1px solid {border};"
                           f" border-radius: {c('radius_lg')}; }}")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 14, 16, 14)
        self.body.setSpacing(8)
        if title:
            self.title = label(title, "h2")
            self.body.addWidget(self.title)


def dot_icon(colour_key, size=10):
    """A small round icon in a theme colour (status marks in lists)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(c(colour_key)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.end()
    return QIcon(pm)


STATUS_DOT = {"unreviewed": "text_muted", "relevant": "success", "not_relevant": "danger",
              "record_extracted": "info"}


def fmt_when(iso):
    """'2026-10-12T10:41:48' -> '12 Oct 2026, 10:41'."""
    if not iso:
        return ""
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    try:
        y, m, d = iso[:10].split("-")
        out = f"{int(d)} {months[int(m) - 1]} {y}"
        return out + (f", {iso[11:16]}" if len(iso) >= 16 else "")
    except (ValueError, IndexError):
        return iso


def fmt_seconds(s):
    s = int(s or 0)
    if s < 90:
        return f"about {s} seconds"
    m = round(s / 60)
    return f"about {m} minutes" if m < 90 else f"about {m / 60:.1f} hours"

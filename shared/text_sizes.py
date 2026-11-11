"""The suite's named interface text sizes, in pixels (R18, 10 Nov 2026) - the one source.

Wil's screen is 1920x1080 at 100% scaling. Every stylesheet and font in the apps takes its size
from here, by name, so a size is changed in one place:

    from shared.text_sizes import font_css, font_px
    label.setStyleSheet(f"color: {c}; font-size: {font_css('body')};")     # -> "font-size: 14px;"
    font_px("body")                                                        # -> 14
    qfont("body", "Segoe UI", QFont.Weight.Bold)                           # a QFont of that pixel size

No Qt and no theme import at module level: the theme (Observatum/src/themes/naturalist.py) reads
TEXT_PX to publish the same numbers as `font_px_<name>` tokens, and the apps read them through
these helpers. The theme's older point tokens (font_size_xs .. font_size_stat) are unchanged.
The display_* names keep the sizes the code used before R18 (nothing of 16 px or more was changed).
"""

TEXT_PX = {
    "caption": 12,
    "small": 13,
    "body": 14,
    "body_large": 15,
    "heading": 16,
    "title": 18,
    "display_20": 20,
    "display_22": 22,
    "display_24": 24,
    "display_26": 26,
    "display_28": 28,
    "display_32": 32,
    "display_48": 48,
    "display_64": 64,
}


def font_px(name):
    """The pixel size for a named text size (KeyError for a name that does not exist)."""
    return TEXT_PX[name]


def font_css(name):
    """The size as a stylesheet value, e.g. font_css('body') -> '14px'."""
    return f"{TEXT_PX[name]}px"


def qfont(name, family="", weight=None, italic=False):
    """A QFont of the named pixel size (family '' = the application's)."""
    from PySide6.QtGui import QFont
    f = QFont(family) if family else QFont()
    f.setPixelSize(TEXT_PX[name])
    if weight is not None:
        f.setWeight(weight)
    if italic:
        f.setItalic(True)
    return f

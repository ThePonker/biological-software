"""theme_fonts -- the fonts a theme names (R21, 16 Nov 2026).

The 1940s theme names 'EB Garamond' (text) and 'Cormorant SC' (card and section titles); both are
bundled in shared/fonts/ (SIL Open Font License, texts alongside). A theme's 'font_family' /
'font_heading' that is not one of the bundled families (Naturalist's, or '') means "leave it as
it is": nothing is registered or applied, so Naturalist is unchanged.

    app = QApplication(...)
    from shared import theme_fonts
    theme_fonts.install(app)        # registers the files, sets the application font and titles

Call it after the QApplication exists. Titles: QGroupBox titles and every widget given the object
name TITLE_OBJECT_NAME (the Home cards' title, views/home/card.py) draw in the heading family.
"""
from __future__ import annotations

from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent / "fonts"
TITLE_OBJECT_NAME = "cardTitle"

BUNDLED = {
    # Static files cut from the variable EB Garamond at weight 500 (regular, italic) and 700 (bold):
    # the 400 weight looked faint on Windows (Wil, 16 Nov). The variable files stay for reference.
    "EB Garamond": ("EBGaramond-Text-Regular.ttf", "EBGaramond-Text-Italic.ttf",
                    "EBGaramond-Text-Bold.ttf", "EBGaramond-Text-BoldItalic.ttf"),
    "Cormorant SC": ("CormorantSC-Medium.ttf", "CormorantSC-SemiBold.ttf", "CormorantSC-Bold.ttf"),
}
_registered: set = set()


def _theme_fonts() -> tuple:
    """(font_family, font_heading) of the theme this program draws in."""
    from shared.theme_lookup import value
    return value("font_family", ""), value("font_heading", "")


def bundled_families(font_family: str, font_heading: str) -> list:
    """The bundled families the theme names (order kept, no repeats)."""
    out = []
    for name in (font_family, font_heading):
        if name in BUNDLED and name not in out:
            out.append(name)
    return out


def register_theme_fonts(font_family: str = None, font_heading: str = None) -> list:
    """Load the bundled font files the theme names into Qt (needs a QApplication).
    Returns the families registered ([] for Naturalist). Defaults: the active theme's."""
    if font_family is None or font_heading is None:
        font_family, font_heading = _theme_fonts()
    from PySide6.QtGui import QFontDatabase
    done = []
    for family in bundled_families(font_family, font_heading):
        for fname in BUNDLED[family]:
            if fname in _registered:
                continue
            if QFontDatabase.addApplicationFont(str(FONT_DIR / fname)) < 0:
                print(f"[theme_fonts] could not load {fname}")
                continue
            _registered.add(fname)
        done.append(family)
    return done


def apply_app_font(app, font_family: str = None) -> bool:
    """Set the application font's family from the theme (size and weight unchanged).
    False, and nothing changed, unless the theme names a bundled family."""
    if font_family is None:
        font_family = _theme_fonts()[0]
    if font_family not in BUNDLED:
        return False
    font = app.font()
    font.setFamily(font_family)
    app.setFont(font)
    return True


def heading_style(font_heading: str) -> str:
    """The application style sheet rule giving titles the heading family ('' for none)."""
    if font_heading not in BUNDLED:
        return ""
    rule = f'font-family: "{font_heading}"; font-weight: 700;'
    return (f"QGroupBox::title {{ {rule} }}\n"
            f"QLabel#{TITLE_OBJECT_NAME} {{ {rule} }}\n")


def apply_heading_font(app, font_heading: str = None) -> bool:
    """Add the title rule to the application style sheet (nothing for Naturalist)."""
    if font_heading is None:
        font_heading = _theme_fonts()[1]
    rule = heading_style(font_heading)
    if not rule:
        return False
    app.setStyleSheet(app.styleSheet() + "\n" + rule)
    return True


def install(app) -> list:
    """Register the fonts, set the application font and the title rule, for the active theme."""
    families = register_theme_fonts()
    apply_app_font(app)
    apply_heading_font(app)
    return families

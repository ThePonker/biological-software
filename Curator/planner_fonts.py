"""
Curator — Font Loader

Registers custom TTF fonts from Curator/fonts/ for:
  - Qt preview (QFontDatabase)
  - fpdf2 PDF export (FPDF.add_font)

Call load_qt_fonts() at startup for preview.
Call register_pdf_fonts(pdf) before PDF export.
"""

from pathlib import Path

FONTS_DIR = Path(__file__).parent / "fonts"

# Custom font families and their TTF files (relative to FONTS_DIR)
CUSTOM_FONTS = {
    "EB Garamond": {
        "regular": "EB_Garamond/static/EBGaramond-Regular.ttf",
        "bold": "EB_Garamond/static/EBGaramond-Bold.ttf",
        "italic": "EB_Garamond/static/EBGaramond-Italic.ttf",
        "bolditalic": "EB_Garamond/static/EBGaramond-BoldItalic.ttf",
    },
    "Libre Baskerville": {
        "regular": "Libre_Baskerville/static/LibreBaskerville-Regular.ttf",
        "bold": "Libre_Baskerville/static/LibreBaskerville-Bold.ttf",
        "italic": "Libre_Baskerville/static/LibreBaskerville-Italic.ttf",
    },
    "Cormorant Garamond": {
        "regular": "Cormorant_Garamond/static/CormorantGaramond-Regular.ttf",
        "bold": "Cormorant_Garamond/static/CormorantGaramond-Bold.ttf",
        "italic": "Cormorant_Garamond/static/CormorantGaramond-Italic.ttf",
        "bolditalic": "Cormorant_Garamond/static/CormorantGaramond-BoldItalic.ttf",
    },
    "Libre Caslon Text": {
        "regular": "Libre_Caslon_Text/LibreCaslonText-Regular.ttf",
        "bold": "Libre_Caslon_Text/LibreCaslonText-Bold.ttf",
        "italic": "Libre_Caslon_Text/LibreCaslonText-Italic.ttf",
    },
}

# Built-in PDF fonts (don't need TTF files)
BUILTIN_PDF_FONTS = {"Helvetica", "Times", "Courier", "Arial"}


def get_available_fonts() -> list:
    """Return list of all available font names (custom + built-in)."""
    fonts = ["Helvetica", "Times", "Courier", "Arial"]
    for name in CUSTOM_FONTS:
        regular = FONTS_DIR / CUSTOM_FONTS[name]["regular"]
        if regular.exists():
            fonts.append(name)
    return fonts


def load_qt_fonts():
    """Register custom TTF fonts with Qt so they show in preview."""
    try:
        from PySide6.QtGui import QFontDatabase
    except ImportError:
        return

    if not FONTS_DIR.exists():
        return

    for family, files in CUSTOM_FONTS.items():
        for style, filename in files.items():
            path = FONTS_DIR / filename
            if path.exists():
                QFontDatabase.addApplicationFont(str(path))


def register_pdf_fonts(pdf, font_family: str):
    """Register a custom font family with fpdf2 for PDF export.

    Returns the family name to use with pdf.set_font().
    For built-in fonts, returns the name unchanged.
    For custom fonts, registers the TTF and returns the family name.
    """
    if font_family in BUILTIN_PDF_FONTS:
        return font_family

    files = CUSTOM_FONTS.get(font_family)
    if not files:
        return "Helvetica"  # fallback

    regular = FONTS_DIR / files["regular"]
    if not regular.exists():
        return "Helvetica"  # fonts not downloaded yet

    # Register with fpdf2
    fname = font_family.replace(" ", "")
    pdf.add_font(fname, "", str(regular))
    if "bold" in files:
        bold_path = FONTS_DIR / files["bold"]
        if bold_path.exists():
            pdf.add_font(fname, "B", str(bold_path))
    if "italic" in files:
        italic_path = FONTS_DIR / files["italic"]
        if italic_path.exists():
            pdf.add_font(fname, "I", str(italic_path))
    if "bolditalic" in files:
        bi_path = FONTS_DIR / files["bolditalic"]
        if bi_path.exists():
            pdf.add_font(fname, "BI", str(bi_path))

    return fname

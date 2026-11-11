"""R18: named interface text sizes (shared/text_sizes.py) and no literal pixel sizes left.

The sizes are read by name (font_px / font_css / qfont); the theme publishes the same numbers as
font_px_<name> tokens. The scan checks that no interface .py file writes `font-size: Npx` itself.
Left out, as in the R17 scan: text drawn onto maps, exports and the 3D view (shared/maps,
views/mapping/view3d*), the export writers (Examen word/pdf/workbook/appendix, Lector exporting/pdf/
dossier, DataEntry/check_export.py, Observatum cleaning_export), Curator's label-preview sizes (they
are variables, not literals), tests, scripts, the archive and the manual's screenshot script.
Allowlist (literal px that must stay): none.
"""
import re
from pathlib import Path

import pytest

from shared import text_sizes
from shared.text_sizes import TEXT_PX, font_css, font_px

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = ("_archive", "tests", "scripts", "docs", "data", "packaging", ".git", "_r17_shots", "_r18_shots")
SKIP_PREFIXES = ("Observatum/src/views/mapping/view3d", "shared/maps/", "Examen/word_export",
                 "Examen/pdf_export", "Examen/workbook_export", "Examen/appendix_export",
                 "Lector/exporting", "Lector/pdf", "Lector/dossier",
                 "Observatum/src/services/cleaning_export", "DataEntry/check_export.py",
                 "shared/text_sizes.py", "Lector/docs")
ALLOWLIST = {}          # {"relative/path.py": "why a literal px size must stay"}
LITERAL = re.compile(r"font-size:\s*\d+(?:\.\d+)?\s*px")


def test_token_table():
    assert [TEXT_PX[k] for k in ("caption", "small", "body", "body_large", "heading", "title")] == \
        [12, 13, 14, 15, 16, 18]
    assert {k: v for k, v in TEXT_PX.items() if k.startswith("display_")} == {
        "display_20": 20, "display_22": 22, "display_24": 24, "display_26": 26,
        "display_28": 28, "display_32": 32, "display_48": 48, "display_64": 64}
    assert all(v >= 12 for v in TEXT_PX.values())


def test_helpers():
    assert font_px("body") == 14
    assert font_css("body") == "14px"
    assert f"font-size: {font_css('small')};" == "font-size: 13px;"
    with pytest.raises(KeyError):
        font_px("nope")


def test_theme_publishes_the_same_numbers():
    from src.themes import theme
    t = theme()
    for name, px in TEXT_PX.items():
        assert t.get(f"font_px_{name}") == px
    assert t.get("font_size_base") == 11          # the point tokens are unchanged
    assert t.get("font_size_xs") == 9


def test_qfont_has_the_pixel_size():
    from PySide6.QtGui import QFont
    f = text_sizes.qfont("body", "Segoe UI", QFont.Weight.Bold, italic=True)
    assert f.pixelSize() == 14 and f.italic() and f.weight() == QFont.Weight.Bold


def test_no_literal_pixel_sizes_in_interface_code():
    found = []
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if rel.split("/")[0] in SKIP_DIRS or rel.startswith(SKIP_PREFIXES) or rel in ALLOWLIST:
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if LITERAL.search(line):
                found.append(f"{rel}:{n}: {line.strip()[:90]}")
    assert not found, "literal font-size px (use shared.text_sizes):\n" + "\n".join(found)

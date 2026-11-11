"""The suite's one setting for the main data tables' text (R19, 11 Nov 2026).

Cell text 13 px (the "small" token), header text 13 px semi-bold, rows 26 px. Observatum's four
data tables (Observations, Contributed, Recording scheme, Collection) take it from here:

    view.setStyleSheet(f"...table styling..." + table_text_css())     # last, so it wins
    apply_table_rows(view)                                            # row height

No theme import: sizes come from shared.text_sizes by name.
"""
from shared.text_sizes import font_css, font_px

TABLE_ROW_PX = 26


def table_text_css():
    """Stylesheet fragment giving cells and headers the table text size (append it last)."""
    return (f"QTableView {{ font-size: {font_css('small')}; }}"
            f"QHeaderView::section {{ font-size: {font_css('small')}; font-weight: 600; }}")


def apply_table_rows(view):
    """Set the table's row height."""
    view.verticalHeader().setDefaultSectionSize(TABLE_ROW_PX)


OLD_CELL_PX = 12        # the size cells had before R19 (Qt's default); default widths were set for it


def scaled_width(px):
    """A column's default width in pixels, grown in step with the cell text (12 -> 13 px) so a
    column that showed its text in full before still does."""
    return round(px * font_px("small") / OLD_CELL_PX)

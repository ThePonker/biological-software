"""Table cells that sort by value, not by their text.

A QTableWidget sorts its cells as text: "1,234" came before "987", and dd/mm/yyyy dates
sorted by day ("01/06/2024" before "28/05/1990"). These cells show the text and sort by
a key: the number, or the ISO date (10 Oct 2026, "not done" list). Empty keys sort first.
"""
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidgetItem


class SortItem(QTableWidgetItem):
    """Shows `text`; sorts by `key` (None = empty, sorts first)."""

    def __init__(self, text: str, key: Any = None):
        super().__init__(text)
        self.sort_key = key

    def __lt__(self, other):
        a, b = self.sort_key, getattr(other, "sort_key", None)
        if a is None or b is None:
            if a is None and b is None:
                return self.text() < other.text()
            return a is None
        return a < b


def number_item(value: Any) -> SortItem:
    """A right-aligned count shown with thousands commas, sorted as a number."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        item = SortItem(f"{value:,}", value)
    else:
        item = SortItem(str(value if value is not None else ""), None)
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item


def iso_to_dmy(iso: Optional[str]) -> str:
    """'2024-06-01' -> '01/06/2024'; anything shorter than a full date -> ''."""
    if not iso or len(iso) < 10:
        return ""
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


def date_item(iso: Optional[str]) -> SortItem:
    """A dd/mm/yyyy date sorted by its ISO value."""
    text = iso_to_dmy(iso)
    return SortItem(text, iso[:10] if text else None)


__all__ = ["SortItem", "number_item", "date_item", "iso_to_dmy"]

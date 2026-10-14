"""Natural sorting for tables: 2 before 11, "Trap 2" before "Trap 10", blanks last."""
from PySide6.QtCore import QSortFilterProxyModel
from PySide6.QtWidgets import QTableWidgetItem

from shared.natural_sort import less_than


class NaturalSortProxy(QSortFilterProxyModel):
    """Compares the displayed text naturally (numbers as numbers)."""

    def lessThan(self, left, right):
        role = self.sortRole()
        return less_than(left.data(role), right.data(role))


class NaturalItem(QTableWidgetItem):
    """A table cell that sorts naturally by its text."""

    def __lt__(self, other):
        return less_than(self.text(), other.text())

"""Ticks held by record id, not row number (review OBS-01, 9 Oct 2026).

Observation Data and Recording Scheme sort by reordering the model's own list of
records. Ticks were held as row numbers, so a sort left them on whatever records
moved into those rows -- and Delete Selected then deleted the wrong records.

Holding the record's id instead means a tick follows its record wherever it is
sorted. One implementation for both tables (they had identical copies of the
row-number version).

A model using this mixin keeps its records in `self._records_attr` (a list of dicts
or objects with an `id`) and calls `_clear_checked()` when the records are replaced.
"""

from typing import Any, Dict, List


def record_key(record: Any):
    """The key a tick is held under: the record's id, else the object itself."""
    rid = record.get("id") if isinstance(record, dict) else getattr(record, "id", None)
    if rid is not None and rid != "":
        return rid
    return ("obj", id(record))          # unsaved row: stable for the object's lifetime


class CheckedByIdMixin:
    """Tick state keyed on record id. Requires `_records_attr` naming the list."""

    _records_attr = "_records"

    def _rows(self) -> List[Any]:
        return getattr(self, self._records_attr)

    def _init_checked(self):
        self._checked: set = set()

    def _clear_checked(self):
        self._checked.clear()

    def is_row_checked(self, row: int) -> bool:
        rows = self._rows()
        return 0 <= row < len(rows) and record_key(rows[row]) in self._checked

    def set_row_checked(self, row: int, checked: bool) -> None:
        rows = self._rows()
        if not (0 <= row < len(rows)):
            return
        key = record_key(rows[row])
        if checked:
            self._checked.add(key)
        else:
            self._checked.discard(key)

    def checked_count(self) -> int:
        """How many shown records are ticked."""
        return sum(1 for r in self._rows() if record_key(r) in self._checked)

    def get_checked_rows(self) -> List[int]:
        """Current row numbers of the ticked records (they change with sorting)."""
        return [i for i, r in enumerate(self._rows()) if record_key(r) in self._checked]

    def get_checked_items(self) -> List[Any]:
        """The ticked records themselves, in their current display order."""
        return [r for r in self._rows() if record_key(r) in self._checked]

    def get_checked_ids(self) -> List[Any]:
        """Database ids of the ticked records (records without an id are left out)."""
        out = []
        for r in self.get_checked_items():
            rid = r.get("id") if isinstance(r, dict) else getattr(r, "id", None)
            if rid is not None and rid != "":
                out.append(rid)
        return out

    def _check_all_keys(self, checked: bool) -> None:
        if checked:
            self._checked = {record_key(r) for r in self._rows()}
        else:
            self._checked.clear()


def describe_records(records: List[Dict], limit: int = 15) -> str:
    """One line per record -- species, date, site -- the first `limit`, then 'and N more'.

    For confirmation dialogs, so a delete names what it will delete.
    """
    def val(r, *keys):
        for k in keys:
            v = r.get(k) if isinstance(r, dict) else getattr(r, k, None)
            if v:
                return str(v)
        return ""

    lines = []
    for r in records[:limit]:
        species = val(r, "species_name", "species") or "(no species)"
        date = val(r, "date")
        if date:
            try:
                from ...utils.date_utils import format_date_display
                date = format_date_display(date, "user") or date
            except Exception:
                pass
        date = date or "no date"
        site = val(r, "site_name", "location") or "no site"
        lines.append(f"• {species} — {date} — {site}")
    extra = len(records) - limit
    if extra > 0:
        lines.append(f"…and {extra} more")
    return "\n".join(lines)

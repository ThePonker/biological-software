"""grid_clipboard -- clipboard text in and out of the Data Entry grid (25 Nov 2026).

Excel's tab-separated format: a cell holding a tab, a line break or a double quote is
wrapped in quotes (inner quotes doubled), so a comment with a line break stays one cell.
And where a pasted block lands: a block shaped like the grid fills the Check / Check note /
Keep columns as copied; a block shaped like the sheets used before 16 Oct (no Check
columns) steps over them, as before.
"""
from __future__ import annotations

import csv
import io
from typing import List, Optional

from DataEntry.grid_columns import COLUMNS, COLIDX, CHECK_YES

CHECK_KEYS = ("check_flag", "check_note", "keep_flag")


def to_text(rows: List[List[str]]) -> str:
    """Rows of cell strings -> Excel-style tab-separated text."""
    def cell(s: str) -> str:
        if any(ch in s for ch in ("\t", "\n", "\r", '"')):
            return '"' + s.replace('"', '""') + '"'
        return s
    return "\n".join("\t".join(cell(s) for s in r) for r in rows)


def same_text(a: Optional[str], b: Optional[str]) -> bool:
    """Equal apart from line endings and a trailing line break (Windows and Excel add them)."""
    def norm(s):
        return (s or "").replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    return a is not None and b is not None and norm(a) == norm(b)


def from_text(text: str) -> List[List[str]]:
    """Clipboard text -> rows of cells. Quoted cells (Excel) are read as one cell."""
    if not text:
        return []
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if '"' in text:
        rows = [list(r) for r in csv.reader(io.StringIO(text), delimiter="\t")]
    else:
        rows = [ln.split("\t") for ln in text.split("\n")]
    while rows and all(c == "" for c in rows[-1]):
        rows.pop()
    return rows


def _grid_shaped(grid, c0: int) -> bool:
    """True when a pasted block starting at column c0 has its values where the grid has them:
    every Check cell blank or a yes, and every VC No. cell blank or a number, with at least one
    of them filled (all blank tells nothing -> treated as the old layout)."""
    flag_at, vcn_at = COLIDX["check_flag"] - c0, COLIDX["vc_number"] - c0
    seen = False
    for row in grid:
        f = row[flag_at].strip().lower() if 0 <= flag_at < len(row) else ""
        n = row[vcn_at].strip() if 0 <= vcn_at < len(row) else ""
        if (f and f not in CHECK_YES and f != "0") or (n and not n.isdigit()):
            return False
        seen = seen or bool(f or n)
    return seen


def target_columns(grid, c0: int, n_cols: int, copied_cols: Optional[List[int]] = None) -> List[int]:
    """The grid column for each pasted value, in order.

    copied_cols: the columns of a block copied in this grid -- it lands at the same spacing,
    Check columns included. Otherwise a block starting on a Check column, or shaped like the
    grid, fills every column; any other block steps over the Check columns (old sheets)."""
    if copied_cols:
        return [c0 + c - copied_cols[0] for c in copied_cols]
    old = [c for c in range(c0, n_cols) if c == c0 or COLUMNS[c][0] not in CHECK_KEYS]
    wider = max((len(r) for r in grid), default=0) > len(old)     # too wide for an old sheet
    if COLUMNS[c0][0] in CHECK_KEYS or wider or _grid_shaped(grid, c0):
        return list(range(c0, n_cols))
    return old

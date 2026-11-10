"""common_name_pick -- which UKSI common name is shown for a taxon (R17 B5). No Qt.

The rule, in order (Wil, 10 Nov 2026):
  1. the preferred name first;
  2. a name starting with a capital letter;
  3. the shorter name;
  4. fewer capital letters  ("Bedstraw Hawk-moth" before "Bedstraw Hawk-Moth");
  5. alphabetical, case-insensitive, then exact -- so the choice is fixed, not whatever
     order SQLite happens to return (1,748 taxa tied on 1-3).

Two forms of the one rule, kept side by side so they cannot drift (a test compares them):
order_by_sql() for queries on common_names, sort_key() for code that already holds the names.
Capitals are A-Z only.
"""
from __future__ import annotations

from typing import Optional

_CAPITALS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def capital_count(name: Optional[str]) -> int:
    """How many capital letters (A-Z) the name has."""
    return sum(1 for ch in (name or "") if "A" <= ch <= "Z")


def sort_key(name: Optional[str], preferred=0) -> tuple:
    """Lowest key wins. `preferred` is the common_names.preferred flag (1 / 0 / None)."""
    name = name or ""
    return (-(preferred or 0), 0 if name[:1].isupper() else 1, len(name),
            capital_count(name), name.lower(), name)


def capitals_sql(col: str) -> str:
    """SQL: the number of capital letters A-Z in `col`. One flat sum of 26 terms (REPLACE is
    case-sensitive in SQLite); 26 nested REPLACEs overflow SQLite's parser stack."""
    terms = " + ".join(f"(LENGTH({col}) - LENGTH(REPLACE({col}, '{ch}', '')))" for ch in _CAPITALS)
    return f"({terms})"


def order_by_sql(col: str = "cn.common_name", preferred: Optional[str] = None) -> str:
    """The ORDER BY terms (no 'ORDER BY', no trailing comma) for the rule above.
    `col` is the common-name column; `preferred` the preferred flag (default: same table prefix)."""
    if preferred is None:
        preferred = col.rsplit(".", 1)[0] + ".preferred" if "." in col else "preferred"
    return (f"{preferred} DESC, CASE WHEN {col} GLOB '[A-Z]*' THEN 0 ELSE 1 END, LENGTH({col}), "
            f"{capitals_sql(col)}, LOWER({col}), {col}")

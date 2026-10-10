"""
Filter builder: the one way Filter Wizard chips (and the filter bars' shared rules)
become SQL, for Observation Data, Recording Scheme and Insect Collection.

10 Oct 2026 (review OBS-06, SRCH1-4, 7-13). Each tab used to translate the wizard
in its own way: Observations in Python (O(n^2), year and notes ignored), Recording
Scheme and Insect Collection by keeping the first chip of a few cards, with the "~"
partial-match marker left in and vice-counties compared by name against a number.
Now every tab declares its columns once (TAB_COLUMNS) and calls build_where().

Rules (one place):
  * Within a key, chips are alternatives (OR): two sites = either site.
  * Within the What, Where, Who and How cards the keys are alternatives too (a record
    matching ANY species / order / family chip) -- as Observation Data always did.
  * The When card's keys and the Status card's two keys are combined with AND.
  * Cards are combined with AND.
  * "~text" = contains (case-insensitive); otherwise equal, ignoring case.
  * Vice-county: a number ("23", "23 - Oxon") matches vc_number, a name matches the
    vice_county name.
  * Grid ref: prefix, ignoring case and spaces.
  * Verification "Accepted" also matches "Accepted - correct" etc. (iRecord's sub-statuses).
  * Dates: ISO text; records with no date never match a date or year filter.
  * A key the tab has no column for is ignored, and reported by unsupported_keys().
"""

import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


# Which card each wizard key belongs to (FilterWizard.set_filters uses this too)
CARD_KEYS: Dict[str, Tuple[str, ...]] = {
    'what': ('species', 'group', 'taxon_group', 'family'),
    'where': ('vice_county', 'grid_ref', 'site_name'),
    'when': ('date_from', 'date_to', 'year'),
    'who': ('recorder', 'determiner'),
    'how': ('method', 'notes_search'),
    'status': ('verification_status', 'record_type'),
}
KEY_TO_CARD: Dict[str, str] = {k: card for card, keys in CARD_KEYS.items() for k in keys}
# Cards whose keys are alternatives; the others are combined with AND
OR_CARDS = ('what', 'where', 'who', 'how')


@dataclass(frozen=True)
class TabColumns:
    """The columns a tab's wizard keys refer to. None = the tab has no such field."""
    table: str
    species: str = 'species_name'
    order: str = 'order_name'            # the wizard's "taxon_group" key (really the order)
    group: Optional[str] = 'taxon_group'  # the wizard's "group" key: real taxon group
    family: str = 'family'
    vc_name: str = 'vice_county'
    vc_number: str = 'vc_number'
    grid_ref: str = 'grid_ref'
    site: str = 'site_name'
    date: str = 'date'
    recorder: Optional[str] = 'recorder'
    determiner: Optional[str] = 'determiner'
    method: Optional[str] = 'method'
    notes: Tuple[str, ...] = ('comment', 'internal_notes', 'sample_comment')
    verification: Optional[str] = 'verification_status'
    record_type: Optional[str] = 'record_type'

    def column_for(self, key: str):
        return {
            'species': self.species, 'taxon_group': self.order, 'family': self.family,
            'group': self.group,
            'vice_county': self.vc_name, 'grid_ref': self.grid_ref, 'site_name': self.site,
            'date_from': self.date, 'date_to': self.date, 'year': self.date,
            'recorder': self.recorder, 'determiner': self.determiner,
            'method': self.method, 'notes_search': self.notes or None,
            'verification_status': self.verification, 'record_type': self.record_type,
        }.get(key)


TAB_COLUMNS: Dict[str, TabColumns] = {
    'observations': TabColumns(table='observations'),
    # Every scheme row is record_type "Recording Scheme": nothing to choose
    'recording_scheme': TabColumns(table='recording_scheme', record_type=None),
    'specimens': TabColumns(table='specimens', date='date_collected', recorder='collector',
                            method=None, notes=('notes', 'label_data'),
                            verification=None, record_type=None),
}
# FilterWizard's tab_name -> TAB_COLUMNS key
TAB_ALIASES = {'observations': 'observations', 'recording_scheme': 'recording_scheme',
               'scheme': 'recording_scheme', 'collection': 'specimens',
               'insect_collection': 'specimens', 'specimens': 'specimens'}


def tab_columns(tab: str) -> TabColumns:
    return TAB_COLUMNS[TAB_ALIASES.get(tab, tab)]


# -- single-value matchers (also used by the filter bars) -----------------------

def as_list(value) -> List[Any]:
    """Chips arrive as a list; older saved filters and callers may pass one value."""
    if value is None or value == '' or value == []:
        return []
    if isinstance(value, (list, tuple, set)):
        return [v for v in value if v not in (None, '')]
    return [value]


def text_match(col: str, value: str) -> Tuple[str, list]:
    """'~x' = contains x; else equal. Both ignore case."""
    value = str(value)
    if value.startswith('~'):
        return f"{col} LIKE ?", [f"%{value[1:].strip()}%"]
    return f"{col} = ? COLLATE NOCASE", [value.strip()]


def vc_match(cols: TabColumns, value) -> Tuple[str, list]:
    """A vice-county chip: number (or '23 - Name') -> vc_number; a name -> vice_county."""
    text = str(value).strip()
    head = text.split(' - ')[0].strip()
    if head.isdigit():
        return f"{cols.vc_number} = ?", [int(head)]
    return text_match(cols.vc_name, text)


def grid_match(col: str, value: str) -> Tuple[str, list]:
    prefix = str(value).lstrip('~').upper().replace(' ', '')
    return f"REPLACE(UPPER({col}), ' ', '') LIKE ?", [f"{prefix}%"]


def status_match(col: str, value: str) -> Tuple[str, list]:
    """'Accepted' matches 'Accepted' and 'Accepted - correct' etc."""
    v = str(value).strip()
    return f"({col} = ? COLLATE NOCASE OR {col} LIKE ?)", [v, f"{v} - %"]


def notes_match(cols: Sequence[str], value: str) -> Tuple[str, list]:
    term = f"%{str(value).lstrip('~').strip()}%"
    return "(" + " OR ".join(f"{c} LIKE ?" for c in cols) + ")", [term] * len(cols)


def same_text(stored, wanted) -> bool:
    """Python twin of text_match for an exact value (filter bars' client-side checks)."""
    return str(stored or '').strip().casefold() == str(wanted or '').strip().casefold()


def status_is(stored, wanted) -> bool:
    """Python twin of status_match: 'Accepted' covers 'Accepted - correct'."""
    s, w = str(stored or '').strip().casefold(), str(wanted or '').strip().casefold()
    return s == w or s.startswith(w + ' - ')


def date_clauses(col: str, date_from=None, date_to=None, year=None) -> Tuple[List[str], list]:
    """Date range / year on ISO text dates. Undated records ('' or NULL) never match."""
    parts, params = [], []
    if date_from or date_to or year:
        parts.append(f"COALESCE({col}, '') <> ''")
    if date_from:
        parts.append(f"{col} >= ?")
        params.append(str(date_from))
    if date_to:
        parts.append(f"substr({col}, 1, 10) <= ?")
        params.append(str(date_to))
    if year:
        parts.append(f"substr({col}, 1, 4) = ?")
        params.append(f"{int(year):04d}")
    return parts, params


# -- the wizard -----------------------------------------------------------------

def _key_clause(cols: TabColumns, key: str, values: List[Any]) -> Tuple[Optional[str], list]:
    """OR of one key's chips, or (None, []) if the key has nothing / no column here."""
    col = cols.column_for(key)
    if not values or not col:
        return None, []
    parts, params = [], []
    if key == 'group':
        # Taxon group (shared/taxon_groups.py): the stored label, else ours from order/family.
        # Display labels like "Beetles (Coleoptera)" or raw iRecord values are both accepted.
        from shared.taxon_groups import group_filter_sql
        labels = [str(v).lstrip('~') for v in values]
        sql, p = group_filter_sql(labels, known=labels, group_col=col,
                                  order_col=cols.order, family_col=cols.family)
        return f"({sql})", p
    for v in values:
        if key == 'vice_county':
            sql, p = vc_match(cols, v)
        elif key == 'grid_ref':
            sql, p = grid_match(col, v)
        elif key == 'verification_status':
            sql, p = status_match(col, v)
        elif key == 'notes_search':
            sql, p = notes_match(col, v)
        else:
            sql, p = text_match(col, v)
        parts.append(sql)
        params.extend(p)
    return ("(" + " OR ".join(parts) + ")"), params


def build_where(tab: str, filters: Dict[str, Any]) -> Tuple[str, list]:
    """(sql, params) for the wizard's filters on this tab; ('', []) when nothing applies."""
    return build_where_cols(tab_columns(tab), filters)


def build_where_cols(cols: TabColumns, filters: Dict[str, Any]) -> Tuple[str, list]:
    """build_where for a table described by its own TabColumns (the Mapping tab reads
    contributed_observations too, which has no wizard tab)."""
    filters = filters or {}
    card_sql, params = [], []
    for card, keys in CARD_KEYS.items():
        if card == 'when':
            parts, p = date_clauses(cols.date, filters.get('date_from'), filters.get('date_to'),
                                    filters.get('year'))
            if parts:
                card_sql.append("(" + " AND ".join(parts) + ")")
                params.extend(p)
            continue
        joiner = " OR " if card in OR_CARDS else " AND "
        parts, p_card = [], []
        for key in keys:
            sql, p = _key_clause(cols, key, as_list(filters.get(key)))
            if sql:
                parts.append(sql)
                p_card.extend(p)
        if parts:
            card_sql.append("(" + joiner.join(parts) + ")")
            params.extend(p_card)
    return " AND ".join(card_sql), params


def unsupported_keys(tab: str, filters: Dict[str, Any]) -> List[str]:
    """Keys with values that this tab has no column for (they are ignored)."""
    cols = tab_columns(tab)
    return [k for k, v in (filters or {}).items()
            if k in KEY_TO_CARD and as_list(v) and not cols.column_for(k)]


def has_filters(filters: Dict[str, Any]) -> bool:
    return any(as_list(v) for k, v in (filters or {}).items() if k in KEY_TO_CARD)


def _connect_ro(db_path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def matching_ids(db_path, tab: str, filters: Dict[str, Any]) -> Optional[Set[int]]:
    """Ids of the tab's rows the wizard keeps; None when the wizard has no filters."""
    sql, params = build_where(tab, filters)
    if not sql:
        return None
    cols = tab_columns(tab)
    conn = _connect_ro(db_path)
    try:
        return {r[0] for r in conn.execute(f"SELECT id FROM {cols.table} WHERE {sql}", params)}
    finally:
        conn.close()


# -- what the wizard's dialogs offer (values present in the tab's own data) -----------

def merge_case_variants(values_with_counts: Iterable[Tuple[str, int]]) -> List[str]:
    """One entry per value ignoring case, spelt as most records spell it ("MV light")."""
    best: Dict[str, Tuple[int, str]] = {}          # casefolded -> (count, spelling)
    for value, n in values_with_counts:
        if value is None or not str(value).strip():
            continue
        v = str(value).strip()
        key = v.casefold()
        if key not in best or n > best[key][0]:
            best[key] = (n, v)
    return sorted((v for _, v in best.values()), key=str.casefold)


def status_groups(values: Iterable[str]) -> List[str]:
    """'Accepted - correct' -> 'Accepted': the choices status_match understands."""
    out = {str(v).split(' - ')[0].strip() for v in values if v and str(v).strip()}
    return sorted(out, key=str.casefold)


def _group_labels(conn, cols: TabColumns) -> List[str]:
    """Taxon-group display labels present in the tab's records (shared/taxon_groups.py)."""
    if not cols.group:
        return []
    from shared.taxon_groups import display_labels, group_sql
    expr = group_sql(group_col=cols.group, order_col=cols.order, family_col=cols.family)
    return display_labels(r[0] for r in conn.execute(f"SELECT DISTINCT {expr} FROM {cols.table}"))


def tab_values(db_path, tab: str, only: Optional[Iterable[str]] = None) -> Dict[str, list]:
    """Distinct values present in the tab's table, for the wizard's dialogs (SRCH12) and
    the filter bars' lists (OBS-15). `only` limits which lists are read."""
    cols = tab_columns(tab)
    t = cols.table
    conn = _connect_ro(db_path)

    def distinct(col):
        if not col:
            return []
        return [r[0] for r in conn.execute(
            f"SELECT DISTINCT {col} FROM {t} WHERE {col} IS NOT NULL AND TRIM({col}) <> '' "
            f"ORDER BY {col} COLLATE NOCASE")]

    def counted(col):
        if not col:
            return []
        return conn.execute(f"SELECT {col}, COUNT(*) FROM {t} GROUP BY {col}").fetchall()

    def years():
        return sorted({int(r[0]) for r in conn.execute(
            f"SELECT DISTINCT substr({cols.date}, 1, 4) FROM {t} WHERE COALESCE({cols.date}, '') <> ''")
            if r[0] and str(r[0]).isdigit()}, reverse=True)

    readers = {
        'species': lambda: distinct(cols.species),
        'orders': lambda: distinct(cols.order),
        'families': lambda: distinct(cols.family),
        'groups': lambda: _group_labels(conn, cols),
        'vice_counties': lambda: merge_case_variants(counted(cols.vc_name)),
        'grid_refs': lambda: distinct(cols.grid_ref),
        'sites': lambda: distinct(cols.site),
        'recorders': lambda: distinct(cols.recorder),
        'determiners': lambda: distinct(cols.determiner),
        'methods': lambda: merge_case_variants(counted(cols.method)),
        'statuses': lambda: status_groups(distinct(cols.verification)),
        'record_types': lambda: distinct(cols.record_type),
        'years': years,
    }
    try:
        return {k: fn() for k, fn in readers.items() if only is None or k in only}
    finally:
        conn.close()


# -- Recording Scheme filter bar: "Source" means the import route ---------------------

# iRecord imports carry irecord_id, NBN Atlas imports nbn_atlas_id (110,510 rows, 9 Oct:
# 35,104 + 75,406, no overlap). The stored `source` is the dataset name, hundreds of them.
SCHEME_SOURCES = {
    'iRecord': "COALESCE(irecord_id, '') <> ''",
    'NBN Atlas': "COALESCE(nbn_atlas_id, '') <> ''",
    'Other': "COALESCE(irecord_id, '') = '' AND COALESCE(nbn_atlas_id, '') = ''",
}

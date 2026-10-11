"""
Species-list dialogs opened from the Personal, Commercial and All stats dashboards.

One copy for the three dashboards (they held three near-identical copies of these five
methods). A dashboard mixes this in and sets LIST_RECORD_TYPE ('Personal', 'Commercial',
or None for all observations).

Decision D2 (Wil, 11 Oct 2026): the lists roll subspecies up into their species and
list "X s.s." as X, the way the cards they are opened from count species
(shared/species_counting.py: species_key_map, the subspecies roll-up on the species
TVK; shared/record_kinds.species_name_for_ss). So "Species in Coleoptera (n species)"
lists the n species the card counts: one row per species, with the first and last
dates across the species and its subspecies. Records the species-counting switches
leave out (genus only, aggregates ...) are left out, as before.
"""

from typing import Iterable, List, Optional

from shared.record_kinds import species_name_for_ss
from shared.species_counting import counted_clause, species_key_map

MONTH_NAMES = ['', 'January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December']


def _uksi_names(db, tvks: Iterable[str]) -> dict:
    """{tvk: UKSI scientific name}; {} when UKSI cannot be read."""
    ids = sorted({t for t in tvks if t})
    out = {}
    try:
        for i in range(0, len(ids), 900):
            chunk = ids[i:i + 900]
            ph = ",".join("?" * len(chunk))
            for r in db.execute_uksi(
                    f"SELECT tvk, scientific_name FROM taxa WHERE tvk IN ({ph})", tuple(chunk)) or []:
                out[r[0]] = r[1]
    except Exception as e:
        print(f"[SpeciesLists] UKSI names unavailable: {e}")
    return out


def rolled_species_list(rows: List[dict], rollup: dict, db=None) -> List[dict]:
    """Merge per-name rows into one row per species, as the cards count them.

    rows: dicts with species_name, species_tvk, n (records), first_date, last_date and
    optionally family. rollup: {tvk: species tvk} (species_key_map). A group's name is its
    species-level name (the most-recorded one; "s.s." dropped); where only subspecies were
    recorded, UKSI's name for the species, else the subspecies name with s.s. dropped.
    Returns dicts with species_name, first_date, last_date (and family when given)."""
    groups = {}
    for r in rows:
        tvk = r.get('species_tvk')
        key = rollup.get(tvk, tvk) if tvk else "name:" + species_name_for_ss(r['species_name'])
        groups.setdefault(key, []).append(r)

    need_names = [k for k, g in groups.items()
                  if not k.startswith("name:") and not any(r.get('species_tvk') == k for r in g)]
    uksi = _uksi_names(db, need_names) if (db is not None and need_names) else {}

    out = []
    for key, g in groups.items():
        g.sort(key=lambda r: (-(r.get('n') or 0), r['species_name']))
        own = [r for r in g if r.get('species_tvk') == key] or (
            g if key.startswith("name:") else [])
        name = (species_name_for_ss(own[0]['species_name']) if own
                else uksi.get(key) or species_name_for_ss(g[0]['species_name']))
        # '' (undated) sorts first, as in the cards' first-year sums: no "new in" year
        firsts = [str(r['first_date']) for r in g if r.get('first_date') is not None]
        lasts = [str(r['last_date']) for r in g if r.get('last_date')]
        row = {'species_name': name,
               'first_date': min(firsts)[:10] if firsts else '',
               'last_date': max(lasts)[:10] if lasts else ''}
        if any('family' in r for r in g):
            row['family'] = next((r['family'] for r in g if r.get('family')), None) or 'Unknown'
        out.append(row)
    return out


class SpeciesListsMixin:
    """The dashboards' species-list dialogs (order, family, month, year, new in year,
    taxon group)."""

    LIST_RECORD_TYPE: Optional[str] = None     # 'Personal' / 'Commercial' / None = all

    # ---- data ---------------------------------------------------------------------
    def _type_clause(self) -> str:
        return f" AND record_type = '{self.LIST_RECORD_TYPE}'" if self.LIST_RECORD_TYPE else ""

    def species_list_rows(self, where: str, params: tuple = (), with_family: bool = False) -> List[dict]:
        """One row per species (subspecies rolled up) among the counted records matching
        `where` (SQL on observations, ? placeholders)."""
        from ...models.database import get_database
        db = get_database()
        if db is None:
            return []
        fam = ", MAX(family) AS family" if with_family else ""
        result = db.execute_main(f"""
            SELECT species_name, species_tvk, COUNT(*) AS n,
                   MIN(date) AS first_date, MAX(date) AS last_date{fam}
            FROM observations
            WHERE species_name IS NOT NULL AND species_name != ''
              AND ({where}){self._type_clause()}
              {counted_clause("observations", db=db)}
            GROUP BY species_name, species_tvk
        """, tuple(params))
        rows = [dict(r) for r in result or []]
        try:
            rollup = species_key_map(db, "observations")
        except Exception as e:
            print(f"[SpeciesLists] subspecies roll-up unavailable: {e}")
            rollup = {}
        return rolled_species_list(rows, rollup, db)

    # ---- dialogs ------------------------------------------------------------------
    def _open_species_list(self, title: str, species_list: list, show_families: bool = False,
                           count_in_title: Optional[str] = None):
        from ..dialogs.species_list_dialog import SpeciesListDialog
        if not species_list:
            return None
        n = len(species_list)
        title = f"{title} ({count_in_title.format(n=n) if count_in_title else f'{n} species'})"
        dlg = SpeciesListDialog(title, species_list, parent=self, show_families=show_families)
        self._species_list_dialog = dlg            # the last one opened (tests)
        dlg.exec()
        return dlg

    def _show_species_for_group(self, field: str, value: str, dialog_title: str):
        """Species in an order or family (field: 'order_name' / 'family')."""
        if field not in ('order_name', 'family'):
            return
        try:
            rows = self.species_list_rows(f"{field} = ?", (value,))
            rows.sort(key=lambda r: r['species_name'])
            self._open_species_list(dialog_title, rows)
        except Exception as e:
            print(f"Error showing species for {field}={value}: {e}")

    def _show_species_for_month(self, month: int):
        """Species recorded in a calendar month (all years); day dates only, as the chart."""
        month_name = MONTH_NAMES[month] if 1 <= month <= 12 else str(month)
        try:
            rows = self.species_list_rows(
                "date IS NOT NULL AND CAST(strftime('%m', date) AS INTEGER) = ? "
                # a day only: year/month/range dates skip month charts (decision 9)
                "AND COALESCE(date_type, 'D') = 'D'", (month,))
            rows.sort(key=lambda r: r['species_name'])
            self._open_species_list(f"Species Recorded in {month_name}", rows,
                                    count_in_title="{n} species, all years")
        except Exception as e:
            print(f"Error showing species for month: {e}")

    def _show_species_for_year(self, year: int):
        try:
            rows = self.species_list_rows("strftime('%Y', date) = ?", (str(year),))
            rows.sort(key=lambda r: r['species_name'])
            self._open_species_list(f"Species Recorded in {year}", rows)
        except Exception as e:
            print(f"Error showing species for year {year}: {e}")

    def _show_new_species_for_year(self, year: int):
        """Species first recorded in `year` (the first record of the species or any of its
        subspecies), oldest first."""
        try:
            rows = [r for r in self.species_list_rows("date IS NOT NULL")
                    if r['first_date'][:4] == str(year)]
            rows.sort(key=lambda r: (r['first_date'], r['species_name']))
            for r in rows:
                r['last_date'] = r['first_date']
            self._open_species_list(f"New Species in {year}", rows, count_in_title="+{n}")
        except Exception as e:
            print(f"Error showing new species for year {year}: {e}")

    def _show_species_for_order_curve(self, group_label: str):
        """Species list when a group chart is clicked."""
        group_values = getattr(self, '_group_label_map', {}).get(group_label)
        if group_values:
            self._show_species_for_taxon_groups(group_values, group_label)
        else:
            self._show_species_for_group('order_name', group_label, f"Species in {group_label}")

    def _show_species_for_taxon_groups(self, group_values: list, label: str):
        """Species in one or more taxon groups, with a By Family tab."""
        from shared.taxon_groups import group_sql   # stored label, else order/family
        try:
            ph = ','.join('?' for _ in group_values)
            rows = self.species_list_rows(f"{group_sql()} IN ({ph})", tuple(group_values),
                                          with_family=True)
            rows.sort(key=lambda r: r['species_name'])
            self._open_species_list(f"Species in {label}", rows, show_families=True)
        except Exception as e:
            print(f"Error showing species for {label}: {e}")

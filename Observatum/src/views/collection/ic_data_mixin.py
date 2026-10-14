"""Insect Collection Tab — Data Loading & Filtering Mixin

Handles data loading from repository/model, in-memory filtering,
sort proxy creation, and proxy wiring.
"""
from typing import Any

from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex

from shared.natural_sort import less_than
from ...models.database import get_database


def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    """Get attribute from object, supporting both dict and dataclass."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class ICDataMixin:
    """Mixin providing data-loading and filtering methods for InsectCollectionTab."""

    # ── Sort proxy ──────────────────────────────────────────────────

    def _create_sort_proxy(self):
        """Create a sort proxy that sorts dates chronologically."""

        class DateAwareSortProxy(QSortFilterProxyModel):
            def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
                # Check for sort data (ISO date stored in UserRole+1)
                left_data = self.sourceModel().data(left, Qt.ItemDataRole.UserRole + 1)
                right_data = self.sourceModel().data(right, Qt.ItemDataRole.UserRole + 1)
                if left_data and right_data:
                    return left_data < right_data
                return less_than(left.data(Qt.ItemDataRole.DisplayRole),
                                 right.data(Qt.ItemDataRole.DisplayRole))

        return DateAwareSortProxy()

    def _connect_proxy_after_load(self):
        """Connect proxy and view after data is loaded for fast startup."""
        if self._proxy_connected:
            return
        self.sort_proxy.setDynamicSortFilter(False)
        self.sort_proxy.setSourceModel(self.table_model)
        self.table_view.setModel(self.sort_proxy)
        self.sort_proxy.setDynamicSortFilter(True)
        self._proxy_connected = True
        if getattr(self, '_widths', None) is not None:
            self._widths.watch(self.table_model)
            self._widths.watch(self.sort_proxy)
            self._widths.apply()
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().setSectionsClickable(True)
        self.table_view.horizontalHeader().setSortIndicatorShown(True)

    def _enable_sorting_on_first_view(self):
        """Enable sorting when tab becomes visible."""
        if not hasattr(self, '_sorting_enabled') or not self._sorting_enabled:
            self.table_view.setSortingEnabled(True)
            self._sorting_enabled = True

    # ── Data loading ────────────────────────────────────────────────

    def query_filters(self, consume: bool = False) -> dict:
        """The filters the next load uses: the filter bar's, the extra ones (from Stats
        navigation; used once when `consume`) and the taxonomic sidebar's."""
        filters = self.filters.get_filters()

        # Merge extra filters (from stats navigation)
        if self._extra_filters:
            filters = {**filters, **self._extra_filters}
            if consume:
                self._extra_filters = {}  # Clear after use

        # Merge taxonomic sidebar filter
        if hasattr(self, '_taxonomic_filter'):
            ft, fv = self._taxonomic_filter
            if ft != 'all' and fv:
                col_map = {
                    'order': 'order', 'family': 'family',
                    'superfamily': 'superfamily', 'species': 'species',
                }
                col = col_map.get(ft)
                if col:
                    filters[col] = fv
        return filters

    def read_specimens(self, filters: dict) -> list:
        """The specimens these filters keep, read from the database. Touches no widget, so
        startup runs it in a background thread (each query opens its own connection)."""
        # Use repository for filtered queries if it has the method
        if self._specimen_repo and hasattr(self._specimen_repo, 'get_filtered'):
            return self._specimen_repo.get_filtered(filters)
        # Fallback to model or repository.get_all()
        if self._specimen_repo and hasattr(self._specimen_repo, 'get_all'):
            specimens = self._specimen_repo.get_all(limit=999999)
        elif self._specimen_model:
            specimens = self._specimen_model.get_all_specimens()
        else:
            specimens = []
        if filters:
            specimens = self._apply_filters(specimens, filters)
        return specimens

    def _load_data(self, prefetched=None):
        """Load specimen data into the table. `prefetched`: the specimens already read for
        query_filters() (startup, Round 5)."""
        if not self._specimen_model and not self._specimen_repo:
            return

        try:
            filters = self.query_filters(consume=True)

            # The Filter Wizard's filters, re-queried on every load (they used to be
            # one-off "extra" filters, lost on the next reload -- SRCH9)
            wizard_ids = None
            if getattr(self, '_wizard_filters', None):
                wizard_ids = self.filter_wizard.matching_ids(self._wizard_filters)

            specimens = (list(prefetched) if prefetched is not None
                         else self.read_specimens(filters))

            if wizard_ids is not None:
                specimens = [s for s in specimens if _get_attr(s, 'id') in wizard_ids]

            species_names = set()
            for s in specimens:
                name = _get_attr(s, 'species_name', '')
                if name:
                    species_names.add(name)
            species_count = len(species_names)
            self.toolbar.set_counts(species_count, len(specimens))

            self.table_model.set_specimens(specimens)
            self._connect_proxy_after_load()
            if hasattr(self, 'filter_wizard'):
                self.filter_wizard.refresh_tab_values()

            # Update column widths after data load
            self._widths.apply()          # each column's own saved width

        except Exception as e:
            print(f"Error loading specimen data: {e}")
            import traceback
            traceback.print_exc()

    def set_extra_filter(self, filter_name: str, value: str):
        """Set an extra filter that will be applied on next load."""
        self._extra_filters[filter_name] = value

    # ── In-memory filtering (fallback) ──────────────────────────────

    def _apply_filters(self, specimens: list, filters: dict) -> list:
        """Apply filters to specimen list (fallback when not using repository)."""
        result = specimens

        if filters.get('species'):   # by TVK through the shared species search (10 Oct 2026)
            from shared.species_filter import species_filter
            sf = species_filter(filters['species'],
                                {_get_attr(s, 'species_tvk', '') or '' for s in result})
            result = [s for s in result if sf.matches(
                _get_attr(s, 'species_tvk', '') or '', _get_attr(s, 'species_name', '') or '',
                _get_attr(s, 'common_name', '') or '')]

        if filters.get('location'):
            search = filters['location'].lower()
            result = [s for s in result if
                      search in (_get_attr(s, 'site_name', '') or '').lower()]

        if filters.get('order'):
            order = filters['order']
            result = [s for s in result if
                      (_get_attr(s, 'order_name', '') or '') == order]

        if filters.get('superfamily'):
            sf = filters['superfamily']
            import sqlite3 as _sq3
            try:
                db = get_database()
                uksi_path = str(db._uksi_db_path)
                _uconn = _sq3.connect(uksi_path)
                _uc = _uconn.execute(
                    "SELECT DISTINCT family FROM taxa WHERE superfamily = ?", (sf,)
                )
                sf_families = {r[0] for r in _uc.fetchall()}
                _uconn.close()
                result = [s for s in result if
                          (_get_attr(s, 'family', '') or '') in sf_families]
            except Exception:
                pass

        if filters.get('family'):
            family = filters['family']
            result = [s for s in result if
                      (_get_attr(s, 'family', '') or '') == family]

        if filters.get('vice_county'):
            vc = filters['vice_county']
            result = [s for s in result if
                      str(_get_attr(s, 'vc_number', '')) == str(vc)]

        if filters.get('collector'):
            search = filters['collector'].lower()
            result = [s for s in result if
                      search in (_get_attr(s, 'collector', '') or '').lower()]

        if filters.get('date_from'):
            date_from = filters['date_from']
            result = [s for s in result if
                      (_get_attr(s, 'date_collected') or '') >= date_from]

        if filters.get('date_to'):
            date_to = filters['date_to']
            result = [s for s in result if
                      (_get_attr(s, 'date_collected') or '') <= date_to]

        if filters.get('condition'):
            condition = filters['condition']
            result = [s for s in result if
                      (_get_attr(s, 'condition', '') or '') == condition]

        if filters.get('preparation_type'):
            prep_type = filters['preparation_type']
            result = [s for s in result if
                      (_get_attr(s, 'preparation_type', '') or '') == prep_type]

        if filters.get('storage_location'):
            storage = filters['storage_location']
            result = [s for s in result if
                      (_get_attr(s, 'storage_location', '') or '') == storage]

        return result

"""Insect Collection Tab — Data Loading & Filtering Mixin

Handles data loading from repository/model, in-memory filtering,
sort proxy creation, and proxy wiring.
"""
from typing import Any

from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex

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
                return super().lessThan(left, right)

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
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().setSectionsClickable(True)
        self.table_view.horizontalHeader().setSortIndicatorShown(True)

    def _enable_sorting_on_first_view(self):
        """Enable sorting when tab becomes visible."""
        if not hasattr(self, '_sorting_enabled') or not self._sorting_enabled:
            self.table_view.setSortingEnabled(True)
            self._sorting_enabled = True

    # ── Data loading ────────────────────────────────────────────────

    def _load_data(self):
        """Load specimen data into the table."""
        if not self._specimen_model and not self._specimen_repo:
            return

        try:
            filters = self.filters.get_filters()

            # Merge extra filters (from stats navigation)
            if self._extra_filters:
                filters = {**filters, **self._extra_filters}
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

            # Use repository for filtered queries if it has the method
            if self._specimen_repo and hasattr(self._specimen_repo, 'get_filtered'):
                specimens = self._specimen_repo.get_filtered(filters)
                species_count = self._specimen_repo.count_unique_species(filters)
                self.toolbar.set_counts(species_count, len(specimens))
            else:
                # Fallback to model or repository.get_all()
                if self._specimen_repo and hasattr(self._specimen_repo, 'get_all'):
                    specimens = self._specimen_repo.get_all(limit=999999)
                elif self._specimen_model:
                    specimens = self._specimen_model.get_all_specimens()
                else:
                    specimens = []

                if filters:
                    specimens = self._apply_filters(specimens, filters)

                species_names = set()
                for s in specimens:
                    name = _get_attr(s, 'species_name', '')
                    if name:
                        species_names.add(name)
                species_count = len(species_names)
                self.toolbar.set_counts(species_count, len(specimens))

            self.table_model.set_specimens(specimens)
            self._connect_proxy_after_load()

            # Update column widths after data load
            header = self.table_view.horizontalHeader()
            widths = self.table_model.get_column_widths()
            for i, width in enumerate(widths):
                if i < header.count():
                    self.table_view.setColumnWidth(i, width)

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

        if filters.get('species'):
            search = filters['species'].lower()
            result = [s for s in result if
                      search in (_get_attr(s, 'species_name', '') or '').lower() or
                      search in (_get_attr(s, 'common_name', '') or '').lower()]

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

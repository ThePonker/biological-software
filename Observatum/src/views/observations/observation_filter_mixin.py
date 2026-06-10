"""
Observation Filter Mixin

Handles filtering logic, data loading, and special views for ObservationTab.
"""

from typing import Optional, Dict, Any, List


class ObservationFilterMixin:
    """Mixin providing filter and data loading functionality."""

    def _on_filters_changed(self, filters: Dict[str, Any]):
        """Handle filter changes."""
        # Guard against filtering before data is loaded
        if not self._all_observations and not self._obs_repo:
            return

        # When filters are explicitly applied, switch back to normal view
        if self._current_view_mode != 'normal':
            self._current_view_mode = 'normal'
            # Re-enable sorting for normal view
            self.table_view.setSortingEnabled(True)
            # Restore default sort by date descending
            from PySide6.QtCore import Qt
            self.table_view.sortByColumn(2, Qt.SortOrder.DescendingOrder)
            # Reset the saved filter dropdown
            self.filter_bar.saved_combo.blockSignals(True)
            self.filter_bar.saved_combo.setCurrentIndex(0)
            self.filter_bar.saved_combo.blockSignals(False)
        self._apply_current_filters(use_cache=True)

    def _on_special_view_selected(self, view_mode: str):
        """Handle special view selection."""
        if view_mode == 'new_species_list':
            self._show_new_species_list()

    def _show_new_species_list(self):
        """Show the New Species List view - unique species by first record date."""
        if not self._observation_model and not self._obs_repo:
            return

        self._current_view_mode = 'new_species_list'
        
        # Disable sorting to preserve query order (newest first)
        self.table_view.setSortingEnabled(False)
        # Clear sort on proxy model to preserve original data order
        self.sort_proxy.sort(-1)

        try:
            # Get data type from filter bar
            data_type = self.filter_bar.get_data_type()

            # Map data type to record_type
            record_type = None
            if data_type == 'personal':
                record_type = 'Personal'
            elif data_type == 'commercial':
                record_type = 'Commercial'

            # Use repository if available
            if self._obs_repo:
                observations = self._obs_repo.get_new_species_first_records(
                    limit=10000
                )
                self.table_model.set_observations_fast(observations)
            if hasattr(self, '_connect_proxy_after_load'):
                self._connect_proxy_after_load()
                self._update_stats(len(observations), len(observations))
            else:
                # Fallback to raw query via model
                record_type_filter = ""
                if data_type == 'personal':
                    record_type_filter = "AND (record_type = 'Personal' OR record_type IS NULL OR record_type = '')"
                elif data_type == 'commercial':
                    record_type_filter = "AND record_type = 'Commercial'"

                query = f"""
                    SELECT * FROM observations
                    WHERE id IN (
                        SELECT MIN(id)
                        FROM observations
                        WHERE species_tvk IS NOT NULL {record_type_filter}
                        AND (species_tvk, date) IN (
                            SELECT species_tvk, MIN(date)
                            FROM observations
                            WHERE species_tvk IS NOT NULL {record_type_filter}
                            GROUP BY species_tvk
                        )
                        GROUP BY species_tvk
                    )
                    ORDER BY date DESC
                """

                results = self._observation_model.db.execute_main(query)
                observations = [self._observation_model._row_to_observation(row) for row in results]
                self.table_model.set_observations_fast(observations)
            if hasattr(self, '_connect_proxy_after_load'):
                self._connect_proxy_after_load()
                self._update_stats(len(observations), len(observations))

        except Exception as e:
            print(f"[ObservationTab] Error loading new species list: {e}")
            import traceback
            traceback.print_exc()

    def show_new_species_list(self):
        """Public method to show New Species List - called from other tabs."""
        self.filter_bar.select_new_species_list()

    def _apply_current_filters(self, use_cache=False):
        """Apply current filter values."""
        filters = self.filter_bar.get_filters()
        # If cached data available and no active filters, skip re-query
        has_active = any(v for k, v in filters.items() if k != 'data_type' or v not in ('all', '', None))
        if use_cache and not has_active and self._all_observations:
            excluded = self._apply_record_exclusion(self._all_observations)
            self.table_model.set_observations_fast(excluded)
            if hasattr(self, '_connect_proxy_after_load'):
                self._connect_proxy_after_load()
            species_count = self._count_species_with_exclusion(excluded)
            self._update_stats(len(excluded), species_count)
            return

        # Use repository for server-side filtering if available
        if self._obs_repo:
            self._apply_filters_via_repository(filters)
        else:
            # Fallback to client-side filtering
            filtered = self._apply_filters(self._all_observations, filters)
            self.table_model.set_observations_fast(observations)
            if hasattr(self, '_connect_proxy_after_load'):
                self._connect_proxy_after_load()
            species_count = self._count_species_with_exclusion(filtered)
            self._update_stats(len(filtered), species_count)

    def _apply_filters_via_repository(self, filters: Dict[str, Any]):
        """Apply filters using repository (server-side filtering)."""
        try:
            # Map filter bar fields to repository search params
            data_type = filters.get('data_type', 'all')
            record_type = None
            if data_type == 'personal':
                record_type = 'Personal'
            elif data_type == 'commercial':
                record_type = 'Commercial'

            # Use repository search
            observations = self._obs_repo.search(
                species_name=filters.get('species'),
                site_name=filters.get('location'),
                date_from=filters.get('date_from'),
                date_to=filters.get('date_to'),
                order_name=filters.get('order'),
                family=filters.get('family'),
                vc_number=int(filters['vice_county']) if filters.get('vice_county') else None,
                recorder=filters.get('recorder'),
                record_type=record_type,
                limit=999999  # Load all records
            )

            # Additional filters not in repository search (client-side)
            if filters.get('method'):
                method = filters['method']
                observations = [o for o in observations if self._get_attr(o, 'method', '') == method]

            if filters.get('verification_status'):
                status = filters['verification_status']
                observations = [o for o in observations if self._get_attr(o, 'verification_status', '') == status]

            excluded = self._apply_record_exclusion(observations)
            self.table_model.set_observations_fast(excluded)
            if hasattr(self, '_connect_proxy_after_load'):
                self._connect_proxy_after_load()

            # Update stats
            species_count = self._count_species_with_exclusion(excluded)

            self._update_stats(len(excluded), species_count)

        except Exception as e:
            print(f"[ObservationTab] Repository search error: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to client-side
            filtered = self._apply_filters(self._all_observations, filters)
            self.table_model.set_observations_fast(observations)
            if hasattr(self, '_connect_proxy_after_load'):
                self._connect_proxy_after_load()

    def _apply_filters(self, observations: List, filters: Dict[str, Any]) -> List:
        """Apply filters to observation list (client-side fallback)."""
        result = list(observations)

        # Data type / Record type filter
        data_type = filters.get('data_type', 'all')
        if data_type == 'personal':
            result = [o for o in result if self._get_attr(o, 'record_type', '').lower() in ('personal', '')]
        elif data_type == 'commercial':
            result = [o for o in result if self._get_attr(o, 'record_type', '').lower() == 'commercial']

        # Species filter (searches species_name and common_name)
        if filters.get('species'):
            search = filters['species'].lower()
            result = [o for o in result if
                      search in self._get_attr(o, 'species_name', '').lower() or
                      search in self._get_attr(o, 'common_name', '').lower()]

        # Location filter
        if filters.get('location'):
            search = filters['location'].lower()
            result = [o for o in result if
                      search in self._get_attr(o, 'site_name', '').lower()]

        # Date from filter
        if filters.get('date_from'):
            date_from = filters['date_from']
            result = [o for o in result if
                      self._get_attr(o, 'date', '') >= date_from]

        # Date to filter
        if filters.get('date_to'):
            date_to = filters['date_to']
            result = [o for o in result if
                      self._get_attr(o, 'date', '') <= date_to]

        # Order filter - field is 'order_name'
        if filters.get('order'):
            order = filters['order']
            result = [o for o in result if
                      self._get_attr(o, 'order_name', '') == order]

        # Family filter
        if filters.get('family'):
            family = filters['family']
            result = [o for o in result if
                      self._get_attr(o, 'family', '') == family]

        # Vice county filter
        if filters.get('vice_county'):
            vc = str(filters['vice_county'])
            result = [o for o in result if
                      str(self._get_attr(o, 'vc_number', '')) == vc]

        # Recorder filter
        if filters.get('recorder'):
            search = filters['recorder'].lower()
            result = [o for o in result if
                      search in self._get_attr(o, 'recorder', '').lower()]

        # Method filter - field is 'method'
        if filters.get('method'):
            method = filters['method']
            result = [o for o in result if
                      self._get_attr(o, 'method', '') == method]

        # Verification status filter
        if filters.get('verification_status'):
            status = filters['verification_status']
            result = [o for o in result if
                      self._get_attr(o, 'verification_status', '') == status]

        return result

    def _get_attr(self, obj, attr: str, default: str = '') -> str:
        """Safely get attribute from object or dict, returning default if not found or None."""
        if isinstance(obj, dict):
            val = obj.get(attr)
        else:
            val = getattr(obj, attr, None)
        if val is None:
            return default
        return str(val)

    def _load_data(self, filters: Optional[Dict[str, Any]] = None):
        """Load observation data into the table."""
        if not self._observation_model and not self._obs_repo:
            return

        try:

            # Use repository if available
            if self._obs_repo:
                self._all_observations = self._obs_repo.search(limit=999999)
            else:
                self._all_observations = self._observation_model.get_observations({})


            # Apply filters
            self._apply_current_filters(use_cache=True)


        except Exception as e:
            print(f"[ObservationTab] Error loading data: {e}")
            import traceback
            traceback.print_exc()

    def _apply_record_exclusion(self, observations) -> list:
        """Filter observation list by species name exclusion rules."""
        from PySide6.QtCore import QSettings
        settings = QSettings()
        exclude = settings.value("display/exclude_incomplete_species", True, type=bool)
        if not exclude:
            return list(observations)
        filtered = []
        for obs in observations:
            tvk = self._get_attr(obs, 'species_tvk', '')
            if not tvk:
                continue
            name = self._get_attr(obs, 'species_name', '')
            if ' ' not in name:
                continue
            name_lower = name.lower()
            if any(x in name_lower for x in ['agg.', 'agg ', ' agg', 's.l.', 'sensu lato']):
                continue
            filtered.append(obs)
        return filtered

    def _count_species_with_exclusion(self, observations) -> int:
        """Count unique species, respecting the exclusion setting."""
        from PySide6.QtCore import QSettings
        settings = QSettings()
        exclude = settings.value("display/exclude_incomplete_species", True, type=bool)
        
        unique_species = set()
        for obs in observations:
            tvk = self._get_attr(obs, 'species_tvk', '')
            if not tvk:
                continue
            
            if exclude:
                name = self._get_attr(obs, 'species_name', '')
                # Skip genus-only (no space in name)
                if ' ' not in name:
                    continue
                # Skip aggregates
                name_lower = name.lower()
                if any(x in name_lower for x in ['agg.', 'agg ', ' agg', 's.l.', 'sensu lato']):
                    continue
            
            unique_species.add(tvk)
        
        return len(unique_species)

    def _update_stats(self, record_count: int, species_count: int):
        """Update the toolbar stats."""
        self.toolbar.set_counts(record_count, species_count)

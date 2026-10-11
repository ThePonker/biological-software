"""
Observation Filter Mixin

Handles filtering logic, data loading, and special views for ObservationTab.
"""

from typing import Optional, Dict, Any, List

from shared.species_counting import default_db, excluded_reasons, kinds_for_search, species_key_map

from ...services.filter_builder import same_text, status_is


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
                    limit=10000, record_type=record_type
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

    def _project_pin(self, observations):
        """Only the pinned commercial project's records (ObservationTab.set_project_filter).

        None when nothing is pinned. Every record of the job is listed (as everywhere,
        the ones the species-counting switches leave out are dimmed)."""
        pin = getattr(self, "_project_filter", None)
        if not pin:
            return None
        project, client = pin
        return [o for o in (observations or [])
                if self._get_attr(o, 'record_type', '') == 'Commercial'
                and self._get_attr(o, 'project_name', '').strip() == project
                and self._get_attr(o, 'client', '').strip() == client]

    def _show_list(self, observations):
        """List these records (dimming / 'only excluded' applied) and count them."""
        self._set_rows(self._apply_record_exclusion(observations))

    def _set_rows(self, rows):
        self.table_model.set_observations_fast(rows)
        if hasattr(self, '_connect_proxy_after_load'):
            self._connect_proxy_after_load()
        counted = rows if self._only_excluded() else self._counted(rows)
        self._update_stats(len(counted), self._count_species_with_exclusion(counted))

    def _apply_current_filters(self, use_cache=False):
        """Apply current filter values."""
        pinned = self._project_pin(self._all_observations)
        if pinned is not None:
            self._show_list(pinned)
            return
        filters = self.filter_bar.get_filters()
        # If cached data available and no active filters, skip re-query
        has_active = any(v for k, v in filters.items() if k != 'data_type' or v not in ('all', '', None))
        if use_cache and not has_active and self._all_observations:
            self._show_list(self._wizard_keep(self._all_observations))
            return

        # Use repository for server-side filtering if available
        if self._obs_repo:
            self._apply_filters_via_repository(filters)
        else:
            # Fallback to client-side filtering
            self._show_list(self._wizard_keep(self._apply_filters(self._all_observations, filters)))

    def _wizard_keep(self, observations) -> list:
        """Only the records the Filter Wizard's applied filters keep (all if none)."""
        ids = getattr(self, '_wizard_ids', None)
        if ids is None:
            return list(observations or [])
        keep = []
        for o in observations or []:
            oid = o.get('id') if isinstance(o, dict) else getattr(o, 'id', None)
            if oid in ids:
                keep.append(o)
        return keep

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

            # Additional filters not in repository search (client-side). Ignoring case:
            # "MV Light" found 19 records of 608 (OBS-15)
            if filters.get('method'):
                method = filters['method']
                observations = [o for o in observations if same_text(self._get_attr(o, 'method', ''), method)]

            if filters.get('verification_status'):
                status = filters['verification_status']
                observations = [o for o in observations
                                if status_is(self._get_attr(o, 'verification_status', ''), status)]

            self._show_list(self._wizard_keep(observations))

        except Exception as e:
            print(f"[ObservationTab] Repository search error: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to client-side
            self._show_list(self._wizard_keep(self._apply_filters(self._all_observations, filters)))

    def _apply_filters(self, observations: List, filters: Dict[str, Any]) -> List:
        """Apply filters to observation list (client-side fallback)."""
        result = list(observations)

        # Data type / Record type filter
        data_type = filters.get('data_type', 'all')
        if data_type == 'personal':
            result = [o for o in result if self._get_attr(o, 'record_type', '').lower() in ('personal', '')]
        elif data_type == 'commercial':
            result = [o for o in result if self._get_attr(o, 'record_type', '').lower() == 'commercial']

        # Species filter: by TVK through the shared species search (10 Oct 2026); records
        # with no TVK by name (species_name / common_name)
        if filters.get('species'):
            from shared.species_filter import species_filter
            sf = species_filter(filters['species'],
                                {self._get_attr(o, 'species_tvk', '') for o in result})
            result = [o for o in result if sf.matches(
                self._get_attr(o, 'species_tvk', ''), self._get_attr(o, 'species_name', ''),
                self._get_attr(o, 'common_name', ''))]

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
                      same_text(self._get_attr(o, 'method', ''), method)]

        # Verification status filter
        if filters.get('verification_status'):
            status = filters['verification_status']
            result = [o for o in result if
                      status_is(self._get_attr(o, 'verification_status', ''), status)]

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

    def read_all_records(self) -> list:
        """Every observation, read from the database. Touches no widget, so startup runs it
        in a background thread (each query opens its own connection)."""
        if self._obs_repo:
            return self._obs_repo.search(limit=999999)
        return self._observation_model.get_observations({})

    def _load_data(self, filters: Optional[Dict[str, Any]] = None, records=None):
        """Load observation data into the table (`records`: already read, Round 5)."""
        if not self._observation_model and not self._obs_repo:
            return

        try:
            self._all_observations = (list(records) if records is not None
                                      else self.read_all_records())

            # The wizard's filters survive a reload (an edit, delete or import): re-query
            if hasattr(self, '_refresh_wizard_ids'):
                self._refresh_wizard_ids()
            if hasattr(self, 'filter_wizard'):
                self.filter_wizard.refresh_tab_values()

            # Apply filters
            self._apply_current_filters(use_cache=True)


        except Exception as e:
            print(f"[ObservationTab] Error loading data: {e}")
            import traceback
            traceback.print_exc()

    def _species_box_text(self) -> str:
        fb = getattr(self, 'filter_bar', None)
        edit = getattr(fb, 'species_edit', None)
        return edit.text().strip() if edit is not None else ''

    # ---- species-counting switches (backlog A; shared/species_counting.py) ----------
    def _counting_db(self):
        return getattr(getattr(self, '_obs_repo', None), '_db', None) or default_db()

    def _only_excluded(self) -> bool:
        chk = getattr(getattr(self, 'filter_bar', None), 'only_excluded_chk', None)
        return bool(chk is not None and chk.isChecked())

    def _record_id(self, o):
        return o.get('id') if isinstance(o, dict) else getattr(o, 'id', None)

    def _apply_record_exclusion(self, observations) -> list:
        """Every record stays listed; those the switches leave out are dimmed (answer 5 of
        note 38). With "Show only excluded" ticked, only those are listed."""
        # a species box naming an aggregate, s.l. or slash pair keeps those counted: they
        # were asked for by name (shared/species_counting.kinds_for_search, decision D4)
        kinds = kinds_for_search("observations", self._species_box_text())
        try:
            reasons = excluded_reasons(self._counting_db(), "observations", kinds)
        except Exception as e:
            print(f"[ObservationTab] species counting unavailable: {e}")
            reasons = {}
        self._excluded_now = reasons
        if hasattr(self.table_model, 'set_dimmed'):
            self.table_model.set_dimmed(reasons)
        rows = list(observations or [])
        if self._only_excluded():
            rows = [o for o in rows if self._record_id(o) in reasons]
        return rows

    def _counted(self, observations) -> list:
        """The records the switches count (the undimmed ones)."""
        reasons = getattr(self, '_excluded_now', None) or {}
        if not reasons:
            return list(observations or [])
        return [o for o in observations or [] if self._record_id(o) not in reasons]

    def _count_species_with_exclusion(self, observations) -> int:
        """Distinct species among these records, subspecies rolled up to their species."""
        try:
            rollup = species_key_map(self._counting_db(), "observations")
        except Exception:
            rollup = {}
        keys = set()
        for o in observations or []:
            tvk = o.get('species_tvk') if isinstance(o, dict) else getattr(o, 'species_tvk', None)
            if tvk:
                keys.add(rollup.get(tvk, tvk))
        return len(keys)

    def _update_stats(self, record_count: int, species_count: int):
        """Update the toolbar stats."""
        self.toolbar.set_counts(record_count, species_count)

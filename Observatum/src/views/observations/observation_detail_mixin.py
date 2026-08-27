"""
Observation Detail Mixin

Handles record detail dialog display and navigation for ObservationTab.
"""

from typing import Dict


class ObservationDetailMixin:
    """Mixin providing record detail and navigation functionality."""

    def _on_row_double_clicked(self, index):
        """Handle row double-click to show record detail."""
        # Map from proxy to source
        source_index = self.sort_proxy.mapToSource(index)
        record = self.table_model.get_observation_at_row(source_index.row())
        if record:
            self._show_record_detail(record)

    def _show_record_detail(self, record: Dict):
        """Show the observation detail dialog."""
        from ..dialogs import RecordDetailDialog
        from ...models.database import get_database

        # Get species count for this species
        species_name = record.get('species_name', '')
        species_tvk = record.get('species_tvk', '')
        species_count = 0

        if species_tvk or species_name:
            try:
                if self._obs_repo and hasattr(self._obs_repo, 'count_by_species'):
                    species_count = self._obs_repo.count_by_species(species_tvk or species_name)
                else:
                    # Fallback query
                    db = get_database()
                    if species_tvk:
                        result = db.execute_main(
                            "SELECT COUNT(*) FROM observations WHERE species_tvk = ?",
                            (species_tvk,)
                        )
                    else:
                        result = db.execute_main(
                            "SELECT COUNT(*) FROM observations WHERE species_name = ?",
                            (species_name,)
                        )
                    species_count = result[0][0] if result else 0
            except Exception as e:
                print(f"[ObservationTab] Error counting species: {e}")

        # Get profile text if available
        profile_text = self._load_species_profile(species_tvk, species_name)

        dialog = RecordDetailDialog(
            record=record,
            species_count=species_count,
            record_type='observation',
            parent=self,
            uksi_model=self._uksi_model,
            profile_text=profile_text
        )

        # Store reference to track dialog
        self._current_detail_dialog = dialog

        # Connect signals for actions
        dialog.edit_requested.connect(self._on_detail_edit_requested)
        dialog.delete_requested.connect(self._on_detail_delete_requested)
        dialog.profile_requested.connect(self._on_profile_requested)
        dialog.navigate_to_observations.connect(self._on_navigate_to_observations)
        dialog.navigate_to_collection.connect(self._on_navigate_to_collection)

        dialog.exec()
        self._current_detail_dialog = None

    def _load_species_profile(self, species_tvk: str, species_name: str) -> str:
        """Load species profile text from database."""
        from ...models.database import get_database
        
        profile_text = None
        try:
            db = get_database()
            if species_tvk:
                result = db.execute_main(
                    "SELECT profile_text FROM species_profiles WHERE species_tvk = ?",
                    (species_tvk,)
                )
                if result and result[0][0]:
                    profile_text = result[0][0]

            if not profile_text and species_name:
                result = db.execute_main(
                    "SELECT profile_text FROM species_profiles WHERE species_name = ?",
                    (species_name,)
                )
                if result and result[0][0]:
                    profile_text = result[0][0]
        except Exception as e:
            print(f"[ObservationTab] Error loading profile: {e}")
        
        return profile_text

    def _on_detail_edit_requested(self, record: Dict):
        """Handle edit request from detail dialog."""
        # Close the detail dialog first
        if self._current_detail_dialog:
            self._current_detail_dialog.accept()

        from ..dialogs.edit_observation_dialog import EditObservationDialog
        from ...models.database import get_database

        uksi_model = getattr(self, '_uksi_model', None)
        vc_service = getattr(self, '_vc_service', None)

        dialog = EditObservationDialog(
            parent=self,
            uksi_model=uksi_model,
            vc_service=vc_service,
            observation=record,
            db=get_database()
        )
        if dialog.exec():
            obs_data = dialog.get_observation_data()
            record_id = record.get('id')
            if record_id:
                try:
                    import sqlite3
                    import paths
                    conn = sqlite3.connect(str(paths.OBSERVATUM_DB))
                    allowed = {'species_name', 'species_tvk', 'common_name', 'family',
                               'order_name', 'date', 'site_name', 'grid_ref',
                               'vice_county', 'vc_number', 'recorder', 'determiner',
                               'comment'}
                    updates = {k: v for k, v in obs_data.items() if k in allowed and v is not None}
                    if updates:
                        set_parts = [f"{k} = ?" for k in updates]
                        values = list(updates.values()) + [record_id]
                        conn.execute(
                            f"UPDATE observations SET {', '.join(set_parts)} WHERE id = ?",
                            values
                        )
                        conn.commit()
                    conn.close()
                    self._load_data()
                except Exception as e:
                    print(f"[ObservationTab] Error updating record: {e}")

    def _on_detail_delete_requested(self, record: Dict):
        """Handle delete request from detail dialog."""
        record_id = record.get('id')
        if record_id:
            try:
                if self._obs_repo:
                    self._obs_repo.delete(record_id)
                elif self._observation_model:
                    self._observation_model.delete(record_id)
                self._load_data()
            except Exception as e:
                print(f"[ObservationTab] Error deleting record: {e}")

    def _on_profile_requested(self, record: Dict):
        """Handle profile view/create request from detail dialog."""
        from ..home.species_profile_dialog import SpeciesProfileDialog
        
        species_data = {
            'scientific_name': record.get('species_name') or record.get('species'),
            'species_name': record.get('species_name') or record.get('species'),
            'tvk': record.get('species_tvk') or record.get('tvk'),
            'common_name': record.get('common_name') or record.get('common'),
        }
        
        profile_dialog = SpeciesProfileDialog(species_data, self)
        
        # Connect with lambda to capture detail dialog reference
        detail_dialog = getattr(self, '_current_detail_dialog', None)
        if detail_dialog and hasattr(detail_dialog, 'update_profile'):
            profile_dialog.profile_saved.connect(lambda text: detail_dialog.update_profile(text))
        
        profile_dialog.exec()

    def _on_navigate_to_observations(self, species_name: str):
        """Handle navigation within Observation tab - apply species filter."""
        # Apply species filter to this tab
        self.filter_bar.set_species_filter(species_name)
        # Sync toolbar button state
        self.toolbar.set_filters_visible(True)
        self._apply_current_filters()

    def _on_navigate_to_collection(self, species_name: str):
        """Handle navigation to Insect Collection tab."""
        self.navigate_to_collection.emit(species_name)

"""Insect Collection Tab — Sidebar & Detail Mixin

Handles the taxonomic sidebar, specimen detail dialogs,
species profile navigation, and bidirectional selection.
"""
from typing import Any

from ...models.database import get_database
from ..dialogs import AddSpecimenDialog, RecordDetailDialog


def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    """Get attribute from object, supporting both dict and dataclass."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class ICSidebarMixin:
    """Mixin providing sidebar and detail-dialog methods for InsectCollectionTab."""

    # ── Specimen detail dialog ──────────────────────────────────────

    def _show_specimen_detail(self, specimen):
        """Show the specimen detail dialog."""
        species_name = _get_attr(specimen, 'species_name', '')
        species_count = 0

        if species_name:
            try:
                if self._specimen_repo and hasattr(self._specimen_repo, 'count_by_species'):
                    species_count = self._specimen_repo.count_by_species(species_name)
                elif self._specimen_model and hasattr(self._specimen_model, 'count_by_species'):
                    species_count = self._specimen_model.count_by_species(species_name)
            except Exception as e:
                print(f"[InsectCollectionTab] Error counting species: {e}")

        # Get profile text if available
        profile_text = None
        try:
            db = get_database()
            species_tvk = _get_attr(specimen, 'species_tvk')
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
            print(f"[InsectCollectionTab] Error loading profile: {e}")

        specimen_dict = specimen if isinstance(specimen, dict) else vars(specimen)

        dialog = RecordDetailDialog(
            record=specimen_dict,
            species_count=species_count,
            record_type='specimen',
            parent=self,
            uksi_model=self._uksi_model,
            profile_text=profile_text
        )

        self._current_detail_dialog = dialog
        dialog.edit_requested.connect(self._on_detail_edit_requested)
        dialog.delete_requested.connect(self._on_detail_delete_requested)
        dialog.profile_requested.connect(self._on_profile_requested)
        dialog.navigate_to_observations.connect(self._on_navigate_to_observations)
        dialog.navigate_to_collection.connect(self._on_navigate_to_collection)

        dialog.exec()
        self._current_detail_dialog = None

    def _on_detail_edit_requested(self, specimen: dict):
        """Handle edit request from detail dialog."""
        if self._current_detail_dialog:
            self._current_detail_dialog.accept()

        dialog = AddSpecimenDialog(
            self,
            self._uksi_model,
            self._vc_service,
            existing_specimen=specimen,
            db=get_database()
        )
        if dialog.exec():
            specimen_data = dialog.get_specimen_data()
            specimen_id = specimen.get('id')
            if specimen_id:
                if self._specimen_repo:
                    self._specimen_repo.update(specimen_id, specimen_data)
                elif self._specimen_model:
                    self._specimen_model.update_specimen(specimen_id, specimen_data)
            self._load_data()
            self.data_changed.emit()

    def _on_detail_delete_requested(self, specimen: dict):
        """Handle delete request from detail dialog."""
        specimen_id = specimen.get('id')
        if specimen_id:
            if self._specimen_repo:
                self._specimen_repo.delete(specimen_id)
                self.data_changed.emit()
            elif self._specimen_model:
                self._specimen_model.delete_specimen(specimen_id)
            self._load_data()
            self.data_changed.emit()

    def _on_profile_requested(self, specimen: dict):
        """Handle profile view/create request from detail dialog."""
        from ..home.species_profile_dialog import SpeciesProfileDialog

        species_data = {
            'scientific_name': specimen.get('species_name') or specimen.get('species'),
            'species_name': specimen.get('species_name') or specimen.get('species'),
            'tvk': specimen.get('species_tvk') or specimen.get('tvk'),
            'common_name': specimen.get('common_name') or specimen.get('common'),
        }

        profile_dialog = SpeciesProfileDialog(species_data, self)

        detail_dialog = getattr(self, '_current_detail_dialog', None)
        if detail_dialog and hasattr(detail_dialog, 'update_profile'):
            profile_dialog.profile_saved.connect(lambda text: detail_dialog.update_profile(text))

        profile_dialog.exec()

    # ── Navigation ──────────────────────────────────────────────────

    def _on_navigate_to_observations(self, species_name: str):
        """Handle navigation to Observation Data tab."""
        self.navigate_to_observations.emit(species_name)

    def _on_navigate_to_collection(self, species_name: str):
        """Handle navigation within Collection tab — apply species filter."""
        self.filters.set_species_filter(species_name)
        self.toolbar.set_filters_visible(True)
        self._load_data()

    # ── Sidebar init / refresh / toggle ─────────────────────────────

    def _init_sidebar(self):
        """Initialize the taxonomic sidebar (called after DB is available)."""
        if self._taxonomic_sidebar:
            return

        from .taxonomic_sidebar import TaxonomicSidebar
        from ...repositories.family_notes_repository import FamilyNotesRepository

        db = get_database()
        main_path = db.get_main_path() if hasattr(db, 'get_main_path') else str(db._main_db_path)
        uksi_path = db.get_uksi_path() if hasattr(db, 'get_uksi_path') else str(db._uksi_db_path)

        self._family_notes_repo = FamilyNotesRepository(main_path)
        self._family_notes_repo.ensure_table()

        self._taxonomic_sidebar = TaxonomicSidebar(
            self._family_notes_repo, uksi_path, self
        )
        self._taxonomic_sidebar.filter_requested.connect(self._on_taxonomic_filter)
        self._taxonomic_sidebar.detail_panel.species_profile_requested.connect(
            self._on_species_profile_requested
        )

        # Replace placeholder with actual sidebar
        old_container = self._sidebar_container
        self._splitter.replaceWidget(0, self._taxonomic_sidebar)
        old_container.deleteLater()

        self._refresh_sidebar()

        # Start hidden
        self._taxonomic_sidebar.setFixedWidth(0)
        self._sidebar_visible = False

    def _refresh_sidebar(self):
        """Refresh the sidebar tree with current specimen data."""
        if not self._taxonomic_sidebar:
            return

        import sqlite3
        db = get_database()
        main_path = db.get_main_path() if hasattr(db, 'get_main_path') else str(db._main_db_path)

        try:
            uksi_path = db.get_uksi_path() if hasattr(db, 'get_uksi_path') else str(db._uksi_db_path)
            conn = sqlite3.connect(main_path)
            conn.execute(f"ATTACH DATABASE '{uksi_path}' AS uksi")
            # subfamily is stored as NULL on some rows and '' on others for the
            # same species; grouping on the raw column splits them in two and
            # the tree then keeps only one. Normalise both to NULL so they
            # group together. 94 specimens were being lost to this.
            cursor = conn.execute("""
                SELECT s.order_name, u.superfamily, s.family,
                       NULLIF(TRIM(COALESCE(s.subfamily, '')), '') AS subfamily,
                       s.species_name, s.species_tvk,
                       s.taxonomic_sort_key, COUNT(*) as specimen_count
                FROM specimens s
                LEFT JOIN uksi.taxa u ON s.species_tvk = u.tvk
                WHERE s.taxonomic_sort_key IS NOT NULL
                GROUP BY s.order_name, u.superfamily, s.family,
                         NULLIF(TRIM(COALESCE(s.subfamily, '')), ''),
                         s.species_name
                ORDER BY s.taxonomic_sort_key
            """)
            specimens = [dict(zip(
                ['order_name', 'superfamily', 'family', 'subfamily', 'species_name',
                 'species_tvk', 'taxonomic_sort_key', 'specimen_count'],
                row
            )) for row in cursor.fetchall()]

            # Sex breakdown per species, classified in Python rather than SQL:
            # the rule for what counts as male or female lives in
            # shared/sex_summary.py and is imported, not restated, so the
            # sidebar and the Data Entry pill cannot come to disagree.
            try:
                from shared.sex_summary import classify_sex
                sexes = {}
                for name, sex, n in conn.execute(
                        """SELECT species_name, sex, COUNT(*) FROM specimens
                           WHERE taxonomic_sort_key IS NOT NULL
                           GROUP BY species_name, sex"""):
                    m, f, o = sexes.get(name, (0, 0, 0))
                    k = classify_sex(sex)
                    if k == "m":
                        m += n
                    elif k == "f":
                        f += n
                    else:
                        o += n
                    sexes[name] = (m, f, o)
                for sp in specimens:
                    m, f, o = sexes.get(sp.get('species_name'), (0, 0, 0))
                    sp['male_count'], sp['female_count'], sp['other_count'] = m, f, o
            except Exception as e:
                print(f"[SIDEBAR] sex breakdown unavailable: {e}")
            try:
                conn.execute("DETACH DATABASE uksi")
            except Exception:
                pass
            conn.close()
            self._taxonomic_sidebar.build_tree(specimens)
        except Exception as e:
            print(f"[SIDEBAR] Error loading tree: {e}")

    def _on_species_profile_requested(self, species_data: dict):
        """Open species profile dialog from sidebar."""
        from ..home.species_profile_dialog import SpeciesProfileDialog
        dialog = SpeciesProfileDialog(species_data, self)
        dialog.exec()

    def _on_table_row_clicked(self, index):
        """When a table row is clicked, highlight the family in the sidebar."""
        if not self._sidebar_visible or not self._taxonomic_sidebar:
            return
        source_index = self.sort_proxy.mapToSource(index)
        specimen = self.table_model.get_specimen_at_row(source_index.row())
        if specimen:
            family = _get_attr(specimen, 'family', '')
            if family:
                self._taxonomic_sidebar.select_by_family(family)

    def toggle_sidebar(self):
        """Toggle the taxonomic sidebar visibility."""
        if not self._taxonomic_sidebar:
            self._init_sidebar()

        self._sidebar_visible = not self._sidebar_visible
        if self._sidebar_visible:
            self._taxonomic_sidebar.setFixedWidth(280)
            self._taxonomic_sidebar.setMinimumWidth(200)
            self._taxonomic_sidebar.setMaximumWidth(500)
        else:
            self._taxonomic_sidebar.setFixedWidth(0)
            self._taxonomic_sidebar.setMinimumWidth(0)
            self._taxonomic_sidebar.setMaximumWidth(0)
            # Clear taxonomic filter and reload all data
            self._taxonomic_filter = ('all', '')
            self._load_data()

    def _on_taxonomic_filter(self, filter_type: str, filter_value: str):
        """Handle taxonomic tree filter — reload data with WHERE clause."""
        self._taxonomic_filter = (filter_type, filter_value)
        self._load_data()

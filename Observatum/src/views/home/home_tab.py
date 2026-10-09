"""Home Tab - Orchestrator"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QMessageBox
from PySide6.QtCore import Qt, Signal
from .quick_entry import QuickEntryForm
from .quick_stats import QuickStatsPanel
from .recent_species import RecentSpeciesPanel
from .species_info import SpeciesInfoPanel
from .species_profile_dialog import SpeciesProfileDialog
from ...models.database import get_database
from ...models.observation import ObservationModel
from ...models.uksi import UKSIModel
from ...services.search_service import get_search_service
from ...themes import theme

# Repository for stats (preferred over model)
try:
    from ...repositories import ObservationRepository
    HAS_REPOSITORY = True
except ImportError:
    HAS_REPOSITORY = False

# Gamification integration
from src.features.gamification import GamificationLauncher


class HomeTab(QWidget):
    # Signal to request navigation to Insect Collection tab with species filter
    navigate_to_collection = Signal(str)  # Emits species TVK or name
    navigate_to_observations = Signal(str)  # Emits species name for filtering observations
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._observation_model = None
        self._obs_repo = None  # Repository for stats
        self._uksi_model = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        t = theme()
        self.setStyleSheet(f"background-color: {t.get('background')};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)  # Align all panels to top

        # Panel 1 - Quick Stats + Gamification (smaller)
        left_column = QVBoxLayout()
        left_column.setSpacing(12)
        left_column.setContentsMargins(0, 0, 0, 0)

        self.stats_panel = QuickStatsPanel()
        left_column.addWidget(self.stats_panel)

        # Gamification launcher card
        self.gamification_card = GamificationLauncher(parent=self)
        left_column.addWidget(self.gamification_card)
        
        left_column.addStretch()  # Push content to top

        left_widget = QWidget()
        left_widget.setLayout(left_column)
        layout.addWidget(left_widget, stretch=2)

        # Panel 2 - Quick Entry (wider)
        self.quick_entry = QuickEntryForm()
        layout.addWidget(self.quick_entry, stretch=5)

        # Panel 3 - Recent New Species
        self.recent_panel = RecentSpeciesPanel()
        layout.addWidget(self.recent_panel, stretch=2)

        # Panel 4 - Species Info
        self.species_info = SpeciesInfoPanel()
        layout.addWidget(self.species_info, stretch=3)

    def _connect_signals(self):
        self.quick_entry.record_saved.connect(self._on_record_saved)
        
        # Recent species selection -> only update Species Info panel (not Quick Entry)
        self.recent_panel.species_selected.connect(self._on_recent_species_selected)
        
        # View All link -> navigate to New Species List filter
        self.recent_panel.view_all_clicked.connect(self._on_view_all_species)

        # Species search in quick entry -> update both Species Info and Quick Entry
        try:
            self.quick_entry.species_search.species_selected.connect(self._on_search_species_selected)
        except AttributeError:
            pass
        
        # Profile button in species info -> open profile dialog
        self.species_info.profile_clicked.connect(self._on_profile_clicked)
        
        # View specimens button -> navigate to Insect Collection
        self.species_info.view_specimens_clicked.connect(self._on_view_specimens)
        
        # View records button -> navigate to Observation Data
        self.species_info.view_records_clicked.connect(self._on_view_records)

    def _on_record_saved(self, record_data):
        self.refresh_data()
        # Clear species info panel after save
        self.species_info.set_species(None)
        QMessageBox.information(self, "Record Saved", "Observation saved successfully!")

    def _on_recent_species_selected(self, species_data: dict):
        """Handle species selection from recent panel - only updates Species Info."""
        enriched = self._enrich_species_data(species_data)
        self.species_info.set_species(enriched)
        # Do NOT update quick entry form - user is just browsing

    def _on_search_species_selected(self, species_data: dict):
        """Handle species selection from search - updates Species Info panel."""
        enriched = self._enrich_species_data(species_data)
        self.species_info.set_species(enriched)
        # Quick Entry is already updated by the search widget itself

    def _on_profile_clicked(self, species_data: dict):
        """Handle profile button click - open profile dialog."""
        dialog = SpeciesProfileDialog(species_data, self)
        dialog.profile_saved.connect(self._on_profile_saved)
        dialog.profile_deleted.connect(self._on_profile_deleted)
        dialog.exec()
    
    def _on_profile_saved(self, profile_text: str):
        """Handle profile saved - update species info panel."""
        self.species_info.set_profile(profile_text)
    
    def _on_profile_deleted(self):
        """Handle profile deleted - clear species info panel profile."""
        self.species_info.set_profile("")
    
    def _on_view_records(self, species_name: str):
        """Handle view records button - navigate to Observation Data."""
        self.navigate_to_observations.emit(species_name)

    def _on_view_specimens(self, species_tvk: str):
        """Handle view specimens button - navigate to Insect Collection."""
        # Get species name for filtering
        species_name = ""
        if self.species_info._current_species:
            species_name = self.species_info._current_species.get('scientific_name', '')
        
        # Emit signal for main window to handle navigation
        self.navigate_to_collection.emit(species_name or species_tvk)

    def _on_view_all_species(self):
        """Handle View All click - navigate to New Species List filter."""
        self.navigate_to_observations.emit("")  # Empty string triggers show_new_species_list

    def _enrich_species_data(self, species_data: dict) -> dict:
        """Normalize field names and add taxonomy from UKSI."""
        # Start with copy to avoid modifying original
        enriched = dict(species_data)

        # Normalize field names
        if 'species_name' in enriched and 'scientific_name' not in enriched:
            enriched['scientific_name'] = enriched['species_name']
        if 'species_tvk' in enriched and 'tvk' not in enriched:
            enriched['tvk'] = enriched['species_tvk']

        # Try to get taxonomy from UKSI if we have a TVK
        tvk = enriched.get('tvk') or enriched.get('species_tvk')
        if tvk and self._uksi_model:
            try:
                species_obj = self._uksi_model.get_species_by_tvk(tvk)
                if species_obj:
                    # Species is an object with attributes, not a dict
                    enriched['order'] = getattr(species_obj, 'order_name', None) or '-'
                    enriched['family'] = getattr(species_obj, 'family', None) or '-'
                    if not enriched.get('scientific_name'):
                        enriched['scientific_name'] = getattr(species_obj, 'taxon_name', 'Unknown')
                    if not enriched.get('common_name'):
                        enriched['common_name'] = getattr(species_obj, 'common_name', '')
            except Exception as e:
                print(f"Error looking up UKSI data: {e}")

        # Get record count from model (repository method could be added later)
        if tvk and self._observation_model:
            try:
                count = self._observation_model.get_species_record_count(tvk)
                enriched['record_count'] = count
            except Exception:
                enriched['record_count'] = 0

        # Check insect collection for specimen count
        if tvk:
            enriched['specimen_count'] = 0
            enriched['in_collection'] = False
            
            try:
                db = get_database()
                # Table is 'specimens', column is 'species_tvk'
                results = db.execute_main(
                    "SELECT COUNT(*) FROM specimens WHERE species_tvk = ?",
                    (tvk,)
                )
                if results:
                    specimen_count = results[0][0]
                    enriched['specimen_count'] = specimen_count
                    enriched['in_collection'] = specimen_count > 0
            except Exception as e:
                print(f"Collection check error: {e}")

        return enriched

    def initialize(self, db_path=None):
        db = get_database()
        self._observation_model = ObservationModel(db)
        
        # Initialize repository for stats (preferred)
        if HAS_REPOSITORY:
            try:
                self._obs_repo = ObservationRepository()
            except Exception as e:
                print(f"[HomeTab] Could not create repository: {e}")
                self._obs_repo = None

        # Initialize UKSI model for taxonomy lookup
        try:
            self._uksi_model = UKSIModel(db)
        except Exception as e:
            print(f"Warning: Could not initialize UKSI model: {e}")

        # Pass database to stats panel for querying all data sources
        self.stats_panel.set_database(db)

        search_service = get_search_service()
        search_service.set_database(db)
        try:
            search_service.refresh_recorded_species()
        except Exception:
            pass
        self.refresh_data()

    def refresh_data(self):
        """Refresh stats and recent species panels."""
        if not self._observation_model and not self._obs_repo:
            return
        try:
            # Use repository for observation stats if available (faster, cleaner)
            if self._obs_repo:
                stats = self._obs_repo.get_quick_stats()
            else:
                stats = self._observation_model.get_stats()
            self.stats_panel.update_stats(stats)
            
            # Refresh Recording Scheme and Insect Collection stats
            self.stats_panel.refresh_all_stats()
            
            # Recent species still uses model (repository method could be added later)
            if self._observation_model:
                recent = self._observation_model.get_recent_new_species(10)
                self.recent_panel.update_species(recent)
        except Exception as e:
            print(f"Error refreshing: {e}")

    def refresh(self):
        self.refresh_data()

    def refresh_display_settings(self):
        """Refresh display settings (e.g., common name visibility, date format)."""
        # Refresh common name setting on recent species panel
        if hasattr(self, 'recent_panel') and hasattr(self.recent_panel, 'refresh_common_name_setting'):
            self.recent_panel.refresh_common_name_setting()
        
        # Refresh common name setting on species info panel
        if hasattr(self, 'species_info') and hasattr(self.species_info, 'refresh_common_name_setting'):
            self.species_info.refresh_common_name_setting()
        
        # Refresh date format on recent panel (rebuilds list with new date format)
        if hasattr(self, 'recent_panel') and self._observation_model:
            try:
                recent = self._observation_model.get_recent_new_species(10)
                self.recent_panel.update_species(recent)
            except Exception as e:
                print(f"Error refreshing recent species: {e}")

    def set_defaults(self, recorder="", determiner=""):
        self.quick_entry.set_defaults(recorder, determiner)

    def apply_theme(self):
        """Apply current theme to this tab and children."""
        t = theme()
        self.setStyleSheet(f"background-color: {t.get('background')};")
        
        # Propagate to children
        if hasattr(self.stats_panel, 'apply_theme'):
            self.stats_panel.apply_theme()
        if hasattr(self.recent_panel, 'apply_theme'):
            self.recent_panel.apply_theme()
        if hasattr(self.quick_entry, 'apply_theme'):
            self.quick_entry.apply_theme()
        if hasattr(self.species_info, 'apply_theme'):
            self.species_info.apply_theme()

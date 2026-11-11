"""Home Tab - Orchestrator"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from PySide6.QtCore import Signal
from .quick_stats import QuickStatsPanel
from .observation_stats_card import ALL, ObservationStatsCard
from . import home_data
from .home_lists import NewSpeciesCard, NotableCard
from .home_map_card import HomeMapCard
from .species_info import SpeciesInfoPanel
from .species_profile_dialog import SpeciesProfileDialog
from ...models.database import get_database
from ...models.observation import ObservationModel
from ...models.uksi import UKSIModel
from ...services.search_service import get_search_service
from ...themes import theme
from ...core.config import TabColors
from ..components.hscroll_strip import PageScroll

# Repository for stats (preferred over model)
try:
    from ...repositories import ObservationRepository
    HAS_REPOSITORY = True
except ImportError:
    HAS_REPOSITORY = False


LEFT_WIDTH, MAP_WIDTH, LIST_WIDTH = 316, 388, 266      # layout A (R19); widths 290/250 in the mock, a little wider for the real card titles


class HomeTab(QWidget):
    # Signal to request navigation to Insect Collection tab with species filter
    navigate_to_collection = Signal(str)  # Emits species TVK or name
    navigate_to_observations = Signal(str)  # Emits species name for filtering observations
    navigate_to_species_lookup = Signal(str, str)  # (name, TVK): Stats > Species lookup (Q55)
    navigate_to_mapping = Signal()  # "Open in Mapping" on the map card (R19)
    navigate_to_notable = Signal(list)  # ids of this year's notable records (R19)
    
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

        # The panels sit in a scroll area: on a narrow (or short) window Home
        # scrolls rather than hold the main window wide (R4, 11 Oct 2026)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panels = QWidget()
        outer.addWidget(PageScroll(panels))
        layout = QHBoxLayout(panels)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Panel 1 - Quick Stats cards (L16 10 Oct; R5 11 Oct): Personal, Commercial,
        # All (the two together), Recording Scheme + Insect Collection. The Achievements
        # card left Home in R5 (the gamification feature itself is untouched).
        left_column = QVBoxLayout()
        left_column.setSpacing(12)
        left_column.setContentsMargins(0, 0, 0, 0)

        self.personal_stats = ObservationStatsCard("Personal")
        left_column.addWidget(self.personal_stats)
        self.commercial_stats = ObservationStatsCard("Commercial")
        left_column.addWidget(self.commercial_stats)
        self.all_stats = ObservationStatsCard(
            ALL, accent=theme().get('accent_observation_dark', TabColors.OBSERVATION_DARK))
        left_column.addWidget(self.all_stats)

        self.stats_panel = QuickStatsPanel()
        left_column.addWidget(self.stats_panel)

        left_column.addStretch()  # Push content to top

        left_widget = QWidget()
        left_widget.setLayout(left_column)
        left_widget.setFixedWidth(LEFT_WIDTH)
        layout.addWidget(left_widget)

        # Centre - where I've recorded (R19)
        self.map_card = HomeMapCard()
        self.map_card.setFixedWidth(MAP_WIDTH)
        layout.addWidget(self.map_card)

        # Right - the species card above the two lists
        right = QVBoxLayout()
        right.setSpacing(16)
        right.setContentsMargins(0, 0, 0, 0)
        self.species_info = SpeciesInfoPanel()
        right.addWidget(self.species_info)
        lists = QHBoxLayout()
        lists.setSpacing(16)
        self.recent_panel = NewSpeciesCard()
        self.recent_panel.setFixedWidth(LIST_WIDTH)
        lists.addWidget(self.recent_panel)
        self.notable_card = NotableCard()
        lists.addWidget(self.notable_card, 1)
        right.addLayout(lists, 1)
        layout.addLayout(right, 1)

    def _connect_signals(self):
        # A species picked in the search box or in the new-species list -> the species card
        # (and the map, in Selected species mode)
        self.species_info.species_chosen.connect(self._on_search_species_selected)
        self.recent_panel.species_selected.connect(self._on_recent_species_selected)
        self.recent_panel.view_all_clicked.connect(self._on_view_all_species)
        self.species_info.profile_clicked.connect(self._on_profile_clicked)
        self.species_info.view_specimens_clicked.connect(self._on_view_specimens)
        self.species_info.view_records_clicked.connect(self._on_view_records)
        self.species_info.lookup_clicked.connect(self.navigate_to_species_lookup.emit)
        self.map_card.open_mapping_clicked.connect(self.navigate_to_mapping.emit)
        self.notable_card.all_clicked.connect(self.navigate_to_notable.emit)

    def _on_recent_species_selected(self, species_data: dict):
        """A row of the new-species list: show it in the species card."""
        self.show_species(species_data)

    def _on_search_species_selected(self, species_data: dict):
        self.show_species(species_data)

    def show_species(self, species_data: dict):
        """A species into the species card (search, new-species list, or Species lookup's
        "Show on Home", Q55); the map follows it in Selected species mode."""
        enriched = self._enrich_species_data(species_data)
        self.species_info.set_species(enriched)
        self.species_info.search.set_species(enriched)
        self.map_card.set_species(enriched.get('tvk') or '', enriched.get('scientific_name') or '')

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

        if tvk:
            try:
                row = get_database().execute_main(
                    "SELECT MIN(date), MAX(date) FROM observations "
                    "WHERE species_tvk = ? AND COALESCE(date, '') <> ''", (tvk,))
                if row and row[0][0]:
                    enriched['first_date'], enriched['last_date'] = row[0][0], row[0][1]
            except Exception as e:
                print(f"First/last record error: {e}")

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
        self.map_card.set_database(db.main_db_path)
        self.notable_card.set_database(db.main_db_path)

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
            # Observation figures, one card per record type (L16) plus All (R5). Only the
            # repository splits by record type; without it the cards keep their last figures.
            if self._obs_repo:
                for card in self._observation_cards():
                    card.update_stats(self._obs_repo.get_quick_stats(
                        record_type=card.query_record_type))
            
            # Refresh Recording Scheme and Insect Collection stats
            self.stats_panel.refresh_all_stats()
            
            if self._obs_repo:
                self.recent_panel.update_species(home_data.last_new_species(self._obs_repo))
            # The map and the notable records are read off the GUI thread
            self.map_card.reload()
            self.notable_card.reload()
        except Exception as e:
            print(f"Error refreshing: {e}")

    def _observation_cards(self):
        """The observation Quick Stats cards: Personal, Commercial, All."""
        return (self.personal_stats, self.commercial_stats, self.all_stats)

    def refresh(self):
        self.refresh_data()

    def refresh_display_settings(self):
        """Refresh display settings (e.g., common name visibility)."""
        self.recent_panel.refresh_common_name_setting()
        self.notable_card.show_data(self.notable_card._data)
        self.species_info.refresh_common_name_setting()

    def apply_theme(self):
        """Apply current theme to this tab and children."""
        t = theme()
        self.setStyleSheet(f"background-color: {t.get('background')};")
        for card in (*self._observation_cards(), self.stats_panel, self.map_card,
                     self.recent_panel, self.notable_card, self.species_info):
            card.apply_theme()

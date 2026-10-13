"""
Species Dashboard Component.

Dashboard for species lookup across all databases.
"""

from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QLineEdit, QGridLayout, QCompleter, QPushButton
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel

from ...models.database import get_database
from ...models.uksi import UKSIModel
from ...models.observation import ObservationModel

from .stat_widgets import StatCard, MonthlyActivityChart
from ...themes import theme
from ...core.config import TabColors, scheme_families


class SpeciesDashboard(QScrollArea):
    """Dashboard for species lookup across all databases."""
    
    # Navigation signals - emit species_name to filter by
    navigate_to_observations = Signal(str)
    navigate_to_collection = Signal(str)
    navigate_to_scheme = Signal(str)        # the Recording Scheme tab, this taxon (R4)
    show_on_home = Signal(dict)             # Home > Species Info, this species (Q55, 13 Oct 2026)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        t = theme()
        
        self.setWidgetResizable(True)
        self.setStyleSheet(f"QScrollArea {{ border: none; background-color: {t.get('background')}; }}")
        
        self._selected_species = None
        self._uksi_model = None
        self._obs_model = None
        self._db = None
        self._search_results = []
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._do_search)
        
        container = QWidget()
        self.setWidget(container)
        
        self._main_layout = QVBoxLayout(container)
        self._main_layout.setContentsMargins(16, 16, 16, 16)
        self._main_layout.setSpacing(24)
        
        # Search Bar
        self._setup_search_bar()
        
        # Placeholder message
        self._setup_placeholder()
        
        # Species detail container (hidden initially)
        self._setup_detail_container()
        
        self._main_layout.addStretch()
    
    def _setup_search_bar(self):
        """Set up search bar."""
        t = theme()
        
        search_frame = QFrame()
        search_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)
        search_layout = QVBoxLayout(search_frame)
        search_layout.setContentsMargins(16, 16, 16, 16)
        
        search_title = QLabel("Species Lookup")
        search_title.setStyleSheet(f"font-weight: 600; color: {t.get('text_heading')}; font-size: {t.font_size('lg')};")
        search_layout.addWidget(search_title)
        
        self.species_search = QLineEdit()
        self.species_search.setPlaceholderText("Search any species by scientific or common name...")
        self.species_search.setMinimumHeight(40)
        self.species_search.setStyleSheet(f"""
            font-size: {t.font_size('lg')}; 
            padding: 8px; 
            border: 1px solid {t.get('border_hover')}; 
            border-radius: {t.get('radius_sm')};
            background-color: {t.get('surface')};
            color: {t.get('text_primary')};
        """)
        self.species_search.textChanged.connect(self._on_search_changed)
        
        # Search row with clear button
        search_row = QHBoxLayout()
        search_row.addWidget(self.species_search)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedSize(40, 40)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get("surface_alt")};
                border: 1px solid {t.get("border")};
                border-radius: {t.get("radius_sm")};
                color: {t.get("text_muted")};
                font-size: 16px;
            }}
            QPushButton:hover {{
                background-color: {t.get("hover")};
                color: {t.get("text_primary")};
            }}
        """)
        self.clear_btn.clicked.connect(self._clear_search)
        self.clear_btn.hide()
        search_row.addWidget(self.clear_btn)
        
        search_layout.addLayout(search_row)
        
        # Completer for dropdown: rows drawn by the suite's shared species list painter
        # (13 Oct 2026); each row's text is still _display(r), so a pick works as before
        self._completer_model = QStandardItemModel(self)
        self._completer = QCompleter(self._completer_model, self)
        self._completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setMaxVisibleItems(15)
        self._completer.activated.connect(self._on_completer_activated)
        self.species_search.setCompleter(self._completer)
        self._painted = False        # the painter is attached when the list first fills
        
        self._main_layout.addWidget(search_frame)
    
    def _setup_placeholder(self):
        """Set up placeholder message."""
        t = theme()
        
        self.placeholder = QFrame()
        self.placeholder.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)
        ph_layout = QVBoxLayout(self.placeholder)
        ph_layout.setContentsMargins(48, 48, 48, 48)
        
        icon = QLabel("🔍")
        icon.setStyleSheet("font-size: 48px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.addWidget(icon)
        
        ph_title = QLabel("Search for a species")
        ph_title.setStyleSheet(f"font-size: {t.font_size('xl')}; color: {t.get('text_secondary')};")
        ph_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_layout.addWidget(ph_title)
        
        ph_desc = QLabel("Enter a scientific or common name above to view comprehensive stats including personal records, specimens, commercial data, scheme records, and phenology.")
        ph_desc.setStyleSheet(f"color: {t.get('text_muted')}; font-size: {t.font_size('sm')};")
        ph_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_desc.setWordWrap(True)
        ph_layout.addWidget(ph_desc)
        
        self._main_layout.addWidget(self.placeholder)
    
    def _setup_detail_container(self):
        """Set up species detail container."""
        self.detail_container = QWidget()
        self.detail_container.hide()
        self._detail_layout = QVBoxLayout(self.detail_container)
        self._detail_layout.setContentsMargins(0, 0, 0, 0)
        self._detail_layout.setSpacing(24)
        self._main_layout.addWidget(self.detail_container)
    
    def initialize(self, main_db_path: str = None, uksi_db_path: str = None):
        """Initialize with database connections."""
        print(f"[SpeciesDashboard] initialize called with main_db={main_db_path}, uksi_db={uksi_db_path}")
        
        db = get_database()
        if db:
            self._db = db
            
            if uksi_db_path:
                db.set_uksi_path(uksi_db_path)
                self._uksi_model = UKSIModel(db)
                print(f"[SpeciesDashboard] Created UKSI model: {self._uksi_model}")
            
            if main_db_path:
                self._obs_model = ObservationModel(db)
                print(f"[SpeciesDashboard] Created Observation model: {self._obs_model}")
    
    def _clear_search(self):
        """Clear the search field and reset view."""
        self.species_search.clear()
        self.placeholder.show()
        self.detail_container.hide()
        self.clear_btn.hide()
        self._selected_species = None
    
    def _on_search_changed(self, text: str):
        """Handle search text change - debounced."""
        # Show/hide clear button
        self.clear_btn.setVisible(len(text) > 0)
        
        if len(text) < 2:
            self.placeholder.show()
            self.detail_container.hide()
            return
        
        self._search_text = text
        self._search_timer.start(300)
    
    def _do_search(self):
        """Perform the actual UKSI search and populate dropdown."""
        text = getattr(self, '_search_text', '')
        print(f"[SpeciesDashboard] _do_search called with text: '{text}'")
        
        if len(text) < 2:
            self._set_results([])
            return
        
        try:   # the shared species search (10 Oct 2026): slips, old names, common names
            from types import SimpleNamespace
            from shared.species_search import SPECIES_LEVEL, search
            results = [SimpleNamespace(**r) for r in search(text, limit=15, ranks=SPECIES_LEVEL)]
        except Exception as e:
            print(f"[SpeciesDashboard] Search error: {e}")
            self._set_results([])
            return
        
        if results:
            self._search_results = results
            self._set_results(results)
            self._completer.complete()
        else:
            self._search_results = []
            self._set_results([])
    
    def _set_results(self, results):
        """The drop-down's rows: text _display(r) (what a pick is matched on), drawn by the
        shared painter -- scientific name in italics, common name, family, any note."""
        from shared.species_list_delegate import HIT_ROLE, SpeciesListDelegate, hit_from_result
        if results and not self._painted:
            # Not in __init__: the pop-up is a top-level window, made only when needed
            # (one made for a dashboard never shown crashed Qt on clean-up)
            self._painted = True
            popup = self._completer.popup()
            popup.setItemDelegate(SpeciesListDelegate(popup, secondary=theme().get("text_secondary")))
        self._completer_model.clear()
        for r in results:
            item = QStandardItem(self._display(r))
            item.setData(hit_from_result(vars(r), family=True), HIT_ROLE)
            self._completer_model.appendRow(item)

    @staticmethod
    def _display(r) -> str:
        if r.common_name:
            display = f"{r.common_name} ({r.scientific_name}) - {r.family or ''}"
        else:
            display = f"{r.scientific_name} - {r.family or ''}"
        if getattr(r, 'old_name', None):
            display += f" \u2014 old name: {r.old_name}"
        elif getattr(r, 'match_type', '') == 'fuzzy':
            display += " \u2014 close spelling"
        return display

    # A species' records: the same selection as the record tabs' species filter
    # (shared/species_filter.py: its TVK, its subspecies and old TVKs; by name where a
    # record has no TVK), so a count here is the count the tab shows when "View N
    # Records" takes you there (review 10 Oct: Corvus corone 95 here, 106 on the tab).
    def _by_species(self, table: str, species_name: str) -> tuple:
        cache = self.__dict__.setdefault('_clause_cache', {})
        key = (table, species_name)
        if key not in cache:
            from shared.species_filter import sql_for_table
            cache[key] = sql_for_table(species_name, lambda q: self._db.execute_main(q), table)
        return cache[key]

    def _counted(self, table: str, species_name: str) -> str:
        """The species-counting switches on observations and scheme records (backlog A);
        specimens are never left out. The taxon picked from the list is never left out
        of its own counts: an aggregate picked by name shows its aggregate records (R9-1)."""
        if table not in ("observations", "recording_scheme"):
            return ""
        from shared.species_counting import counted_clause_for, counted_clause_for_taxon
        if species_name and species_name == getattr(self, '_current_name', None):
            return counted_clause_for_taxon(table, species_name,
                                            getattr(self, '_current_rank', None), db=self._db)
        return counted_clause_for(table, species_name, db=self._db)

    def _taxon_note(self, species_name: str) -> str:
        """'Aggregate records are counted here ...' when the picked taxon's own kind is
        switched off in Settings > Species counting (R9-1), else ''."""
        if species_name != getattr(self, '_current_name', None):
            return ""
        from shared.species_counting import excluded_kinds, kind_label, kinds_for_taxon
        kept = []
        for source in ("observations", "recording_scheme"):
            for k in sorted(excluded_kinds(source)
                            - kinds_for_taxon(source, species_name, self._current_rank)):
                if kind_label(k) not in kept:
                    kept.append(kind_label(k))
        if not kept:
            return ""
        return (f"{' and '.join(kept)} records are counted here because you picked this "
                f"taxon by name. Settings › Species counting leaves them out elsewhere.")

    def _count(self, table: str, species_name: str, extra: str = "") -> int:
        clause, params = self._by_species(table, species_name)
        result = self._db.execute_main(
            f"SELECT COUNT(*) FROM {table} WHERE {clause} {extra}"
            f"{self._counted(table, species_name)}", tuple(params))
        return result[0][0] if result else 0

    def _on_completer_activated(self, text: str):
        """Handle selection from dropdown."""
        for r in self._search_results:
            if self._display(r) == text:
                species_name = r.scientific_name
                self._current_tvk = r.tvk
                self._current_name = species_name           # its own kind counts (R9-1)
                self._current_rank = getattr(r, 'rank', None)
                self._clause_cache = {}          # the tables may have changed since
                
                # Get counts from all data sources
                personal_count = self._get_personal_records_count(species_name)
                observation_count = self._get_observation_count(species_name)
                commercial_count = self._get_commercial_records_count(species_name)
                specimen_count = self._get_specimen_count(species_name)
                scheme_count = self._get_scheme_records_count(species_name)
                scheme_tab_count = self._get_scheme_tab_count(species_name, scheme_count)
                phenology = self._get_phenology_data(species_name)
                
                species_data = {
                    'species': species_name,
                    'common': r.common_name or '',
                    'order': r.order_name or '',
                    'family': r.family or '',
                    'tvk': r.tvk,
                    'personalRecords': personal_count,
                    'observationRecords': observation_count,
                    'specimens': specimen_count,
                    'commercialRecords': commercial_count,
                    'schemeRecords': scheme_count,
                    'schemeTabRecords': scheme_tab_count,
                    'phenology': phenology
                }
                
                self._show_species_detail(species_data)
                break
    
    def show_species(self, species_name: str, tvk: str = "") -> bool:
        """Open one species from elsewhere (Home > Species Info's link, Q55): found by the
        same search as typing, the row with this TVK (else this exact name) picked as a
        click would. False when the search finds nothing for the name."""
        try:
            from types import SimpleNamespace
            from shared.species_search import SPECIES_LEVEL, search
            results = [SimpleNamespace(**r) for r in search(species_name, limit=15,
                                                             ranks=SPECIES_LEVEL)]
        except Exception as e:
            print(f"[SpeciesDashboard] show_species: {e}")
            return False
        pick = (next((r for r in results if tvk and r.tvk == tvk), None)
                or next((r for r in results if r.scientific_name == species_name), None))
        if pick is None:
            return False
        self._search_results = [pick]
        self._search_timer.stop()
        self.species_search.blockSignals(True)
        self.species_search.setText(pick.scientific_name)
        self.species_search.blockSignals(False)
        self.clear_btn.setVisible(True)
        self._on_completer_activated(self._display(pick))
        return True

    def _get_observation_count(self, species_name: str) -> int:
        """All the species' observation records (personal and commercial): what the
        Observations tab shows when "View N Records" opens it (its Data Type is All)."""
        if not self._db:
            return 0
        try:
            return self._count("observations", species_name)
        except Exception as e:
            print(f"[SpeciesDashboard] Error getting observation records: {e}")
            return 0

    def _get_personal_records_count(self, species_name: str) -> int:
        """Get count of personal observation records for a species."""
        if not self._db:
            return 0
        try:
            return self._count("observations", species_name, "AND record_type = 'Personal'")
        except Exception as e:
            print(f"[SpeciesDashboard] Error getting personal records: {e}")
            return 0
    
    def _get_commercial_records_count(self, species_name: str) -> int:
        """Get count of commercial observation records for a species."""
        if not self._db:
            return 0
        try:
            return self._count("observations", species_name, "AND record_type = 'Commercial'")
        except Exception as e:
            print(f"[SpeciesDashboard] Error getting commercial records: {e}")
            return 0
    
    def _get_specimen_count(self, species_name: str) -> int:
        """Get count of specimens for a species."""
        if not self._db:
            return 0
        try:
            return self._count("specimens", species_name)
        except Exception as e:
            print(f"[SpeciesDashboard] Error getting specimen count: {e}")
            return 0
    
    def _get_scheme_records_count(self, species_name: str) -> int:
        """Get count of recording scheme records for a species."""
        if not self._db:
            return 0
        try:
            return self._count("recording_scheme", species_name)
        except Exception as e:
            print(f"[SpeciesDashboard] Error getting scheme records: {e}")
            return 0
    
    def _get_scheme_tab_count(self, species_name: str, scheme_count: int) -> int:
        """The records "View N scheme records" opens: the Scheme Records count, within the
        scheme families the Recording Scheme tab is limited to (Settings), if any."""
        fams = scheme_families()
        if not fams or not self._db or not scheme_count:
            return scheme_count
        try:
            marks = ",".join("?" * len(fams))
            clause, params = self._by_species("recording_scheme", species_name)
            result = self._db.execute_main(
                f"SELECT COUNT(*) FROM recording_scheme WHERE {clause} AND family IN ({marks})"
                f"{self._counted('recording_scheme', species_name)}", (*params, *fams))
            return result[0][0] if result else 0
        except Exception as e:
            print(f"[SpeciesDashboard] Error getting scheme tab count: {e}")
            return 0

    def _get_phenology_data(self, species_name: str) -> list:
        """Get monthly observation counts for phenology chart."""
        if not self._db:
            return [0] * 12
        
        try:
            # Combine data from observations and recording_scheme
            monthly_counts = [0] * 12
            
            # From observations
            clause, params = self._by_species("observations", species_name)
            obs_result = self._db.execute_main(f"""
                SELECT 
                    CAST(strftime('%m', date) AS INTEGER) as month,
                    COUNT(*) as count
                FROM observations 
                WHERE {clause} AND date IS NOT NULL{self._counted("observations", species_name)}
                AND COALESCE(date_type, 'D') = 'D'  -- a day only: year/month/range dates skip month charts (decision 9)
                GROUP BY month
            """, tuple(params))
            
            for row in obs_result or []:
                if row[0] is None:          # a date with no month ('2019'): not placed
                    continue
                month_idx = int(row[0]) - 1  # Convert "01"-"12" to 0-11
                if 0 <= month_idx < 12:
                    monthly_counts[month_idx] += row[1]
            
            # From recording_scheme
            clause, params = self._by_species("recording_scheme", species_name)
            scheme_result = self._db.execute_main(f"""
                SELECT 
                    CAST(strftime('%m', date) AS INTEGER) as month,
                    COUNT(*) as count
                FROM recording_scheme 
                WHERE {clause} AND date IS NOT NULL{self._counted("recording_scheme", species_name)}
                AND COALESCE(date_type, 'D') = 'D'  -- a day only, as observations (decision D3)
                GROUP BY month
            """, tuple(params))
            
            for row in scheme_result or []:
                if row[0] is None:
                    continue
                month_idx = int(row[0]) - 1
                if 0 <= month_idx < 12:
                    monthly_counts[month_idx] += row[1]
            
            return monthly_counts
            
        except Exception as e:
            print(f"[SpeciesDashboard] Error getting phenology data: {e}")
            return [0] * 12
    
    def _show_species_detail(self, species: dict):
        """Show species detail."""
        t = theme()
        self._selected_species = species
        self.placeholder.hide()
        self.detail_container.show()
        
        # Clear existing content
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Header
        header_frame = QFrame()
        header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 16, 16, 16)
        
        name_row = QHBoxLayout()
        name_info = QVBoxLayout()
        
        species_lbl = QLabel(f"<span style='font-size: 20px;'><i>{species['species']}</i></span>")
        species_lbl.setStyleSheet(f"color: {t.get('text_primary')};")
        name_info.addWidget(species_lbl)
        
        if species.get('common'):
            common_lbl = QLabel(species['common'])
            common_lbl.setStyleSheet(f"font-size: {t.font_size('lg')}; color: {t.get('text_secondary')};")
            name_info.addWidget(common_lbl)
        
        name_row.addLayout(name_info)
        name_row.addStretch()
        header_layout.addLayout(name_row)
        
        # Taxonomy
        tax_frame = QFrame()
        tax_frame.setStyleSheet(f"""
            background-color: {t.get('surface_alt')}; 
            border-radius: {t.get('radius_md')}; 
            padding: 12px;
        """)
        tax_layout = QGridLayout(tax_frame)
        
        order_lbl = QLabel(f"<span style='color: {t.get('text_muted')}; font-size: {t.font_size('xs')};'>Order</span><br/><b>{species['order']}</b>")
        tax_layout.addWidget(order_lbl, 0, 0)
        
        family_lbl = QLabel(f"<span style='color: {t.get('text_muted')}; font-size: {t.font_size('xs')};'>Family</span><br/><b>{species['family']}</b>")
        tax_layout.addWidget(family_lbl, 0, 1)
        
        header_layout.addWidget(tax_frame)
        
        self._detail_layout.addWidget(header_frame)
        
        # Stats Grid
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        
        # Personal Records - green if has records
        pr_color = t.get('success') if species['personalRecords'] > 0 else t.get('text_muted')
        pr_card = StatCard("Personal Records", str(species['personalRecords']), "", pr_color)
        stats_row.addWidget(pr_card)
        
        # Specimens - collection color if has specimens
        sp_color = TabColors.COLLECTION if species['specimens'] > 0 else t.get('text_muted')
        sp_card = StatCard("Specimens", str(species['specimens']), "", sp_color)
        stats_row.addWidget(sp_card)
        
        # Commercial Records - purple
        cr_color = t.get('commercial') if species.get('commercialRecords', 0) > 0 else t.get('text_muted')
        cr_card = StatCard("Commercial Records", str(species.get('commercialRecords', 0)), "", cr_color)
        stats_row.addWidget(cr_card)
        
        # Scheme Records - amber
        sr_color = TabColors.RECORDING_SCHEME if species.get('schemeRecords', 0) > 0 else t.get('text_muted')
        sr_card = StatCard("Scheme Records", f"{species.get('schemeRecords', 0):,}", "", sr_color)
        stats_row.addWidget(sr_card)
        
        stats_container = QWidget()
        stats_container.setLayout(stats_row)
        self._detail_layout.addWidget(stats_container)

        note = self._taxon_note(species['species'])
        if note:
            self._counting_note = QLabel(note)
            self._counting_note.setWordWrap(True)
            self._counting_note.setStyleSheet(
                f"color: {t.get('text_muted')}; font-size: {t.font_size('sm')};")
            self._detail_layout.addWidget(self._counting_note)

        # Navigation buttons row
        nav_row = QHBoxLayout()
        nav_row.setSpacing(12)
        buttons = []

        # The button opens the Observations tab, which shows personal AND commercial
        # records: its number is that count (review 10 Oct: said 56, opened 62)
        n_obs = species.get('observationRecords', species['personalRecords'])
        if n_obs > 0:
            buttons.append(self._nav_button(
                f"View {n_obs:,} Record{'s' if n_obs != 1 else ''}",
                "Personal and commercial records, on the Observations tab",
                t.get('success_bg'), t.get('success_text'), t.get('success'),
                lambda checked, s=species['species']: self.navigate_to_observations.emit(s)))

        # Scheme records on the Recording Scheme tab (R4, 11 Oct): the records the Scheme
        # Records card counts, within the scheme families set in Settings, if any
        n_scheme = species.get('schemeTabRecords', 0)
        if n_scheme > 0:
            self._scheme_btn = self._nav_button(
                f"View {n_scheme:,} scheme record{'s' if n_scheme != 1 else ''}",
                "These records on the Recording Scheme tab",
                TabColors.RECORDING_SCHEME_LIGHT, TabColors.RECORDING_SCHEME_DARK,
                TabColors.RECORDING_SCHEME,
                lambda checked, s=species['species']: self.navigate_to_scheme.emit(s))
            buttons.append(self._scheme_btn)

        if species['specimens'] > 0:
            buttons.append(self._nav_button(
                f"View {species['specimens']} Specimens", "",
                t.get('warning_bg'), t.get('warning_text'), t.get('warning'),
                lambda checked, s=species['species']: self.navigate_to_collection.emit(s)))

        # Q55 (13 Oct 2026): the same species in Home > Species Info
        home = {'scientific_name': species['species'], 'tvk': species.get('tvk') or '',
                'common_name': species.get('common', ''), 'family': species.get('family', ''),
                'order': species.get('order', '')}
        buttons.append(self._nav_button(
            "Show on Home", "This species in Home › Species Info",
            TabColors.HOME_LIGHT, TabColors.HOME_DARK, TabColors.HOME,
            lambda checked, h=home: self.show_on_home.emit(h)))

        if buttons:
            for btn in buttons:
                nav_row.addWidget(btn)
            nav_row.addStretch()
            nav_container = QWidget()
            nav_container.setLayout(nav_row)
            self._detail_layout.addWidget(nav_container)

        # Phenology
        if species.get('phenology') and any(v > 0 for v in species['phenology']):
            phenology_chart = MonthlyActivityChart("Phenology")
            phenology_chart.set_data(species['phenology'], t.get('info'))
            phenology_chart.month_clicked.connect(
                lambda m, s=species['species']: self._show_month_records(s, m))
            self._phenology_chart = phenology_chart
            self._detail_layout.addWidget(phenology_chart)

        # Species accounts -- yours, then published review and atlas accounts, newest first
        self._add_accounts(species)

    @staticmethod
    def _nav_button(text: str, tip: str, bg: str, fg: str, border: str, on_click) -> QPushButton:
        """A "View ..." button in the colours of the place it opens."""
        t = theme()
        btn = QPushButton(text)
        if tip:
            btn.setToolTip(tip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: {t.get('radius_md')};
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {border};
                color: white;
            }}
        """)
        btn.clicked.connect(on_click)
        return btn

    def _show_month_records(self, species_name: str, month: int):
        """Click on a phenology month: that month's records (all years), the same
        records the bar counts."""
        if not self._db:
            return
        from .month_records_dialog import MonthRecordsDialog, month_records
        try:
            rows = month_records(self._db.execute_main, self._by_species, species_name, month,
                                 self._counted)
        except Exception as e:
            print(f"[SpeciesDashboard] Error getting records for month {month}: {e}")
            return
        if not rows:
            return
        MonthRecordsDialog(species_name, month, rows, db=self._db, parent=self).exec()

    def _add_accounts(self, species: dict):
        """The same accounts panel as the Record Detail windows, in the Stats colours."""
        try:
            from ..components.species_accounts_panel import SpeciesAccountsPanel
            t = theme()
            panel = SpeciesAccountsPanel(species.get('tvk'), species.get('species'),
                                         TabColors.STATS, TabColors.STATS_LIGHT, TabColors.STATS_DARK,
                                         scroll=False)
            panel.setObjectName("speciesAccounts")
            panel.setStyleSheet(f"QFrame#speciesAccounts {{ background-color: {t.get('surface')}; "
                                f"border: 1px solid {t.get('border')}; border-radius: {t.get('radius_lg')}; }}")
            panel.edit_requested.connect(lambda s=species, p=panel: self._edit_account(s, p))
            self._detail_layout.addWidget(panel)
        except Exception as e:
            print(f"[SpeciesDashboard] Species accounts: {e}")

    def _edit_account(self, species: dict, panel):
        from ..home.species_profile_dialog import SpeciesProfileDialog
        dlg = SpeciesProfileDialog({'scientific_name': species.get('species'),
                                    'species_name': species.get('species'),
                                    'tvk': species.get('tvk'),
                                    'common_name': species.get('common')}, self)
        dlg.exec()
        panel.refresh()
    
    def refresh(self, observation_model=None, uksi_model=None):
        """Refresh the dashboard with models for data lookup."""
        try:
            if observation_model:
                self._obs_model = observation_model
                if hasattr(observation_model, 'db'):
                    self._db = observation_model.db
            if uksi_model:
                self._uksi_model = uksi_model
        except Exception as e:
            print(f"[SpeciesDashboard] Error refreshing: {e}")
    
    def apply_theme(self):
        """Apply the current theme."""
        t = theme()
        self.setStyleSheet(f"QScrollArea {{ border: none; background-color: {t.get('background')}; }}")

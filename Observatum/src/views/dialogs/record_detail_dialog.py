"""
Record Detail Dialog.

Shared modal dialog for viewing specimen/observation details.
Styled consistently across Insect Collection and Observation Data tabs.
Uses configurable tab accent colors and displays appropriate fields per record type.
"""


from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QPushButton, QWidget, QMessageBox, QScrollArea
)
from PySide6.QtCore import Signal, Qt

from ...themes import theme
from ...utils.date_utils import format_date_display
from ...core.config import TabColors, ButtonColors


class RecordDetailDialog(QDialog):
    """
    Shared modal dialog for viewing record details.
    
    Works for both specimens (Insect Collection tab) and observations (Observation Data tab).
    Styled to match the Species Info panel from the Home tab.
    
    Args:
        record: Dict containing record data
        species_count: Number of specimens/records for this species (deprecated, use counts dict)
        record_type: 'specimen' or 'observation'
        parent: Parent widget
        uksi_model: Optional UKSI model for taxonomy lookup
        profile_text: Optional species profile text
        accent_color: Tab accent color (defaults based on record_type)
        accent_light: Tab accent light color
        accent_dark: Tab accent dark color
    """
    
    # Signals
    profile_requested = Signal(dict)
    edit_requested = Signal(dict)     # record data
    delete_requested = Signal(dict)   # record data
    navigate_to_observations = Signal(str)  # species name - go to Observation Data tab
    navigate_to_collection = Signal(str)    # species name - go to Insect Collection tab
    
    def __init__(
        self, 
        record: dict, 
        species_count: int = 0,  # Kept for backwards compatibility
        record_type: str = 'specimen',
        parent=None, 
        uksi_model=None, 
        profile_text: str = None,
        accent_color: str = None,
        accent_light: str = None,
        accent_dark: str = None
    ):
        super().__init__(parent)
        self.record = record
        self.record_type = record_type
        self.uksi_model = uksi_model
        self.profile_text = profile_text
        self._taxonomy = None
        
        # Get counts for both observations and specimens
        self._observation_count = 0
        self._specimen_count = 0
        self._specimen_sexes = (0, 0, 0)   # male, female, not-yet-sexed
        self._load_counts()
        
        # Set tab colors based on record type or use provided colors
        if record_type == 'observation':
            self._accent = accent_color or TabColors.OBSERVATION
            self._accent_light = accent_light or TabColors.OBSERVATION_LIGHT
            self._accent_dark = accent_dark or TabColors.OBSERVATION_DARK
            self._title = "OBSERVATION DETAIL"
        else:
            self._accent = accent_color or TabColors.COLLECTION
            self._accent_light = accent_light or TabColors.COLLECTION_LIGHT
            self._accent_dark = accent_dark or TabColors.COLLECTION_DARK
            self._title = "SPECIMEN DETAIL"
        
        t = theme()
        
        self.setWindowTitle("Record Detail")
        self.setMinimumWidth(1000)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background-color: {t.get('surface')}; }}")
        
        # Lookup taxonomy from UKSI if available
        self._lookup_taxonomy()
        self._setup_ui()
        
        # Set a comfortable default height
        self.setMinimumHeight(600)
        self.resize(1200, 760)
    
    def _load_counts(self):
        """Load observation and specimen counts for this species."""
        species_tvk = self.record.get('species_tvk') or self.record.get('tvk')
        species_name = self.record.get('species_name') or self.record.get('species')
        
        if not species_tvk and not species_name:
            return
        
        try:
            from ...models.database import get_database
            db = get_database()
            
            # Count observations
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
            self._observation_count = result[0][0] if result else 0
            
            # Count specimens
            if species_tvk:
                result = db.execute_main(
                    "SELECT COUNT(*) FROM specimens WHERE species_tvk = ?",
                    (species_tvk,)
                )
            else:
                result = db.execute_main(
                    "SELECT COUNT(*) FROM specimens WHERE species_name = ?",
                    (species_name,)
                )
            self._specimen_count = result[0][0] if result else 0

            # Sex breakdown across the held specimens of this species, for the
            # Collection row. Classification is imported from
            # shared/sex_summary.py so this cannot disagree with the tree, the
            # detail panel or the Data Entry pill.
            try:
                from shared.sex_summary import count_sexes
                if species_tvk:
                    rows = db.execute_main(
                        "SELECT sex FROM specimens WHERE species_tvk = ?",
                        (species_tvk,))
                else:
                    rows = db.execute_main(
                        "SELECT sex FROM specimens WHERE species_name = ?",
                        (species_name,))
                self._specimen_sexes = count_sexes(r[0] for r in (rows or []))
            except Exception:
                self._specimen_sexes = (0, 0, 0)

        except Exception as e:
            print(f"[RecordDetailDialog] Error loading counts: {e}")
    
    def _lookup_taxonomy(self):
        """Look up full taxonomy from UKSI database."""
        if not self.uksi_model:
            return
        
        tvk = self.record.get('species_tvk') or self.record.get('tvk')
        species_name = self.record.get('species_name') or self.record.get('species')
        
        try:
            species = None
            if tvk:
                if hasattr(self.uksi_model, 'get_species_by_tvk'):
                    species = self.uksi_model.get_species_by_tvk(tvk)
                elif hasattr(self.uksi_model, 'get_by_tvk'):
                    species = self.uksi_model.get_by_tvk(tvk)
            
            if not species and species_name:
                if hasattr(self.uksi_model, 'get_species_by_name'):
                    species = self.uksi_model.get_species_by_name(species_name)
                elif hasattr(self.uksi_model, 'search'):
                    results = self.uksi_model.search(species_name)
                    if results:
                        species = results[0]
            
            if species:
                if isinstance(species, dict):
                    self._taxonomy = {
                        'class': species.get('class_name') or species.get('class', ''),
                        'order': species.get('order_name') or species.get('order', ''),
                        'family': species.get('family', ''),
                        'common_name': species.get('common_name', ''),
                    }
                else:
                    self._taxonomy = {
                        'class': getattr(species, 'class_name', '') or getattr(species, 'class_', ''),
                        'order': getattr(species, 'order_name', '') or getattr(species, 'order', ''),
                        'family': getattr(species, 'family', ''),
                        'common_name': getattr(species, 'common_name', ''),
                    }
        except Exception as e:
            print(f"[RecordDetailDialog] UKSI lookup error: {e}")
    
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 12, 16, 12)
        
        # Header with title and close
        self._add_header(layout)
        
        # Species name (large, italic)
        self._add_species_name(layout)
        
        # Taxonomy rows (Order, Family)
        self._add_taxonomy_rows(layout)
        
        # Navigation rows (Records + In Collection)
        self._add_navigation_rows(layout)
        
        # Separator
        self._add_separator(layout)
        
        # Record details (Date, Grid Ref, Location, Vice County, etc.)
        self._add_details_section(layout)
        
        # Observation-specific fields
        if self.record_type == 'observation':
            self._add_observation_fields(layout)
        
        # Notes section (if any)
        self._add_notes_section(layout)
        
        # Species Profile section
        self._add_profile_section(layout)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        from PySide6.QtWidgets import QSplitter
        body = QSplitter(Qt.Orientation.Horizontal)
        body.setChildrenCollapsible(False)
        body.addWidget(scroll)
        body.addWidget(self._accounts_panel)
        body.setSizes([520, 680])
        main_layout.addWidget(body, 1)
        
        # Action buttons (fixed at bottom)
        self._add_action_buttons(main_layout)
    
    def _add_header(self, layout):
        """Add header with title only (window X button handles close)."""
        t = theme()
        header = QHBoxLayout()
        
        title = QLabel(self._title)
        title.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 600;
            color: {t.get('text_secondary')};
            letter-spacing: 0.5px;
        """)
        header.addWidget(title)
        
        header.addStretch()
        
        layout.addLayout(header)
    
    def _add_species_name(self, layout):
        """Add species name and common name."""
        t = theme()
        species_name = self.record.get('species_name') or self.record.get('species', 'Unknown')
        
        # Scientific name (large, italic)
        sci_label = QLabel(species_name)
        sci_label.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 600;
            font-style: italic;
            color: {t.get('text_primary')};
        """)
        layout.addWidget(sci_label)
        
        # Common name
        common_name = None
        if self._taxonomy:
            common_name = self._taxonomy.get('common_name')
        if not common_name:
            common_name = self.record.get('common_name') or self.record.get('common')
        
        if common_name:
            common_label = QLabel(common_name)
            common_label.setStyleSheet(f"""
                font-size: 14px;
                color: {t.get('text_primary')};
            """)
            layout.addWidget(common_label)
    
    def _add_taxonomy_rows(self, layout):
        """Add taxonomy rows."""
        # Get values
        if self._taxonomy:
            order_val = self._taxonomy.get('order', '')
            family_val = self._taxonomy.get('family', '')
        else:
            order_val = self.record.get('order_name') or self.record.get('order', '')
            family_val = self.record.get('family', '')
        
        subfamily_val = self.record.get('subfamily', '')
        
        layout.addSpacing(4)
        
        # Order row
        if order_val:
            self._add_label_value_row(layout, "Order", order_val)
        
        # Family row
        if family_val:
            self._add_label_value_row(layout, "Family", family_val)
        
        # Subfamily row
        if subfamily_val:
            self._add_label_value_row(layout, "Subfamily", subfamily_val)
    
    def _add_navigation_rows(self, layout):
        """Add Records and In Collection navigation rows."""
        t = theme()
        layout.addSpacing(4)
        
        # Records row (observations)
        records_row = QHBoxLayout()
        
        if self._observation_count > 0:
            # Has records - show clickable link with count
            records_label = QLabel("Records")
            records_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 13px;")
            records_label.setFixedWidth(70)
            records_row.addWidget(records_label)
            
            records_link = QPushButton("View records →")
            records_link.setStyleSheet(f"""
                QPushButton {{
                    border: none;
                    background: transparent;
                    color: {TabColors.OBSERVATION};
                    font-size: 12px;
                    padding: 0;
                }}
                QPushButton:hover {{
                    color: {TabColors.OBSERVATION_DARK};
                }}
            """)
            records_link.setCursor(Qt.CursorShape.PointingHandCursor)
            records_link.clicked.connect(self._on_view_records)
            records_row.addWidget(records_link)
            
            records_row.addStretch()
            
            records_count = QLabel(str(self._observation_count))
            records_count.setStyleSheet(f"""
                font-size: 16px;
                font-weight: 700;
                color: {TabColors.OBSERVATION};
            """)
            records_row.addWidget(records_count)
        else:
            # No records - show simple text
            no_records_label = QLabel("No Records")
            no_records_label.setStyleSheet(f"color: {t.get('text_muted')}; font-size: 13px;")
            records_row.addWidget(no_records_label)
            records_row.addStretch()
        
        layout.addLayout(records_row)
        
        # In Collection row (specimens)
        collection_row = QHBoxLayout()
        
        if self._specimen_count > 0:
            # Has specimens - show clickable link with count
            collection_label = QLabel("Collection")
            collection_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 13px;")
            collection_label.setFixedWidth(70)
            collection_row.addWidget(collection_label)
            
            collection_link = QPushButton("View all →")
            collection_link.setStyleSheet(f"""
                QPushButton {{
                    border: none;
                    background: transparent;
                    color: {TabColors.COLLECTION};
                    font-size: 12px;
                    padding: 0;
                }}
                QPushButton:hover {{
                    color: {TabColors.COLLECTION_DARK};
                }}
            """)
            collection_link.setCursor(Qt.CursorShape.PointingHandCursor)
            collection_link.clicked.connect(self._on_view_collection)
            collection_row.addWidget(collection_link)
            
            collection_row.addStretch()

            # Sex breakdown beside the count, smaller and muted, so the large
            # figure stays the thing the eye lands on.
            try:
                from shared.sex_summary import format_sex_summary
                summary = format_sex_summary(*self._specimen_sexes)
            except ImportError:
                summary = ""
            if summary:
                sex_label = QLabel(summary)
                sex_label.setStyleSheet(
                    f"font-size: 12px; color: {t.get('text_secondary')};"
                    " padding-right: 6px;")
                sex_label.setToolTip(
                    f"{self._specimen_sexes[0]} male, {self._specimen_sexes[1]} "
                    f"female"
                    + (f", {self._specimen_sexes[2]} not yet sexed"
                       if self._specimen_sexes[2] else ""))
                collection_row.addWidget(sex_label)

            collection_count = QLabel(str(self._specimen_count))
            collection_count.setStyleSheet(f"""
                font-size: 16px;
                font-weight: 700;
                color: {TabColors.COLLECTION};
            """)
            collection_row.addWidget(collection_count)
        else:
            # No specimens - show simple text
            not_in_collection_label = QLabel("Not in Collection")
            not_in_collection_label.setStyleSheet(f"color: {t.get('text_muted')}; font-size: 13px;")
            collection_row.addWidget(not_in_collection_label)
            collection_row.addStretch()
        
        layout.addLayout(collection_row)
    
    def _add_separator(self, layout):
        """Add a subtle separator line."""
        t = theme()
        layout.addSpacing(8)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {t.get('separator')};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        layout.addSpacing(8)
    
    def _add_details_section(self, layout):
        """Add record details section."""
        # Date (convert YYYY-MM-DD to dd/mm/yyyy)
        date_val = self.record.get('date_collected') or self.record.get('date', '')
        if date_val:
            formatted = format_date_display(str(date_val), "user")
            if formatted:
                date_val = formatted
            self._add_label_value_row(layout, "Date", date_val)
        
        # Grid Ref
        grid_ref = self.record.get('grid_ref') or self.record.get('gridRef', '')
        if grid_ref:
            self._add_label_value_row(layout, "Grid Ref", grid_ref, mono=True)
        
        # Location
        location = self.record.get('site_name') or self.record.get('location', '')
        if location:
            self._add_label_value_row(layout, "Location", location)
        
        # Vice County
        vc = self.record.get('vice_county', '')
        vc_num = self.record.get('vc_number') or self.record.get('vc', '')
        if vc or vc_num:
            vc_display = f"{vc} (VC{vc_num})" if vc and vc_num else vc or f"VC{vc_num}"
            self._add_label_value_row(layout, "Vice County", vc_display)

        if self.record_type == 'specimen':
            self._add_specimen_fields(layout)

    def _add_specimen_fields(self, layout):
        """Fields belonging to the specimen itself.

        These were absent entirely: the dialog showed date, grid ref, location
        and vice county, while sex, collector, determiner and all four
        curatorial fields went unshown -- including the ones added in August
        specifically so they could be recorded.

        Only fields the record actually holds are displayed, so a specimen with
        no curatorial data looks as it did before.
        """
        for label, key in (("Sex", "sex"),
                           ("Collector", "collector"),
                           ("Determiner", "determiner"),
                           ("Preparation", "preparation_type"),
                           ("Condition", "condition"),
                           ("Storage", "storage_location"),
                           ("Drawer", "drawer_number")):
            raw = self.record.get(key)
            value = raw.strip() if isinstance(raw, str) else raw
            if value:
                self._add_label_value_row(layout, label, str(value))
    
    def _add_observation_fields(self, layout):
        """Add observation-specific fields."""
        t = theme()
        
        # Verification status with badge
        status = self.record.get('verification_status', '')
        if status:
            self._add_separator(layout)
            
            status_row = QHBoxLayout()
            
            status_label = QLabel("Status")
            status_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 13px;")
            status_label.setFixedWidth(70)
            status_row.addWidget(status_label)
            
            # Status badge
            badge = QLabel(status)
            badge_styles = {
                'Accepted': f"background: {t.get('success_bg')}; color: {t.get('success_text')};",
                'Pending': f"background: {t.get('warning_bg')}; color: {t.get('warning_text')};",
                'Rejected': f"background: {t.get('error_bg')}; color: {t.get('error_text')};",
                'Unconfirmed': f"background: {t.get('surface_alt')}; color: {t.get('text_secondary')};",
            }
            badge_style = badge_styles.get(status, f"background: {t.get('surface_alt')}; color: {t.get('text_secondary')};")
            badge.setStyleSheet(f"""
                {badge_style}
                padding: 4px 8px;
                border-radius: {t.get('radius_sm')};
                font-weight: 600;
                font-size: 12px;
            """)
            status_row.addWidget(badge)
            status_row.addStretch()
            
            layout.addLayout(status_row)
        
        # Quantity, Sex, Stage row
        qty = self.record.get('quantity')
        sex = self.record.get('sex', '')
        stage = self.record.get('stage', '')
        
        if qty or sex or stage:
            details_parts = []
            if qty and qty > 1:
                details_parts.append(f"×{qty}")
            if sex:
                details_parts.append(sex)
            if stage:
                details_parts.append(stage)
            
            if details_parts:
                self._add_label_value_row(layout, "Details", " · ".join(details_parts))
        
        # Recorder
        recorder = self.record.get('recorder', '')
        if recorder:
            self._add_label_value_row(layout, "Recorder", recorder)
        
        # Determiner
        determiner = self.record.get('determiner', '')
        if determiner and determiner != recorder:
            self._add_label_value_row(layout, "Determiner", determiner)
        
        # Method
        method = self.record.get('method', '')
        if method:
            self._add_label_value_row(layout, "Method", method)
        
        # Observation type
        
        # iRecord ID
        irecord_id = self.record.get('irecord_id')
        if irecord_id:
            self._add_label_value_row(layout, "iRecord", f"iBRC{irecord_id}", mono=True)
    
    def _add_notes_section(self, layout):
        """Add notes if present."""
        t = theme()
        
        # Get notes based on record type
        if self.record_type == 'specimen':
            notes = self.record.get('notes', '')
            import_notes = self.record.get('import_notes', '')
        else:
            notes = self.record.get('comment', '')
            import_notes = self.record.get('internal_notes', '')
        
        if not notes and not import_notes:
            return
        
        self._add_separator(layout)
        
        # Header
        header_text = "Specimen Notes" if self.record_type == 'specimen' else "Notes"
        header = QLabel(header_text)
        header.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 600;
            color: {t.get('text_primary')};
        """)
        layout.addWidget(header)
        
        if notes:
            notes_label = QLabel(notes)
            notes_label.setWordWrap(True)
            notes_label.setStyleSheet(f"""
                color: {t.get('text_primary')};
                font-size: 12px;
                padding: 4px 0;
            """)
            layout.addWidget(notes_label)
        
        if import_notes:
            prefix = "Import: " if self.record_type == 'specimen' else "Internal: "
            import_label = QLabel(f"{prefix}{import_notes}")
            import_label.setWordWrap(True)
            import_label.setStyleSheet(f"""
                color: {t.get('text_muted')};
                font-size: 11px;
                font-style: italic;
            """)
            layout.addWidget(import_label)
    
    def _add_profile_section(self, layout):
        """Species accounts live in the right-hand column (SpeciesAccountsPanel):
        built here in the tab's colours, placed beside the record by _setup_ui."""
        from ..components.species_accounts_panel import SpeciesAccountsPanel
        r = self.record or {}
        self._accounts_panel = SpeciesAccountsPanel(
            r.get('species_tvk') or r.get('tvk') or r.get('taxon_version_key'),
            r.get('species_name') or r.get('scientific_name') or r.get('species'),
            self._accent, self._accent_light, self._accent_dark, self)
        self._accounts_panel.edit_requested.connect(
            lambda: self.profile_requested.emit(self.record))
        self._profile_preview = None
        self._profile_btn = None
    
    def _add_action_buttons(self, layout):
        """Add Edit and Delete buttons."""
        t = theme()
        btn_frame = QFrame()
        btn_frame.setStyleSheet(f"background-color: {t.get('surface')}; border-top: 1px solid {t.get('border')};")
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(16, 12, 16, 12)
        btn_layout.setSpacing(12)
        
        # Edit button (Moss Green - primary action)
        edit_btn = QPushButton("Edit")
        edit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ButtonColors.PRIMARY};
                color: white;
                border: none;
                border-radius: {t.get('radius_md')};
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {ButtonColors.PRIMARY_HOVER};
            }}
        """)
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.clicked.connect(self._on_edit)
        btn_layout.addWidget(edit_btn)
        
        # Delete button (Faded Crimson outlined)
        delete_btn = QPushButton("Delete")
        delete_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {ButtonColors.DANGER};
                border: 1px solid {ButtonColors.DANGER};
                border-radius: {t.get('radius_md')};
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {t.get('danger_bg')};
            }}
        """)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(self._on_delete)
        btn_layout.addWidget(delete_btn)
        
        # Disable edit/delete for iRecord-sourced records
        irecord_id = self.record.get('irecord_id') or ''
        if str(irecord_id).strip():
            edit_btn.setEnabled(False)
            edit_btn.setToolTip("Cannot edit iRecord-sourced records")
            edit_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {t.get('border')};
                    color: {t.get('text_muted')};
                    border: none;
                    border-radius: {t.get('radius_md')};
                    padding: 10px 24px;
                    font-size: 13px;
                    font-weight: 500;
                }}
            """)
            edit_btn.setCursor(Qt.CursorShape.ArrowCursor)
            delete_btn.setEnabled(False)
            delete_btn.setToolTip("Cannot delete iRecord-sourced records")
            delete_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {t.get('text_muted')};
                    border: 1px solid {t.get('border')};
                    border-radius: {t.get('radius_md')};
                    padding: 10px 24px;
                    font-size: 13px;
                    font-weight: 500;
                }}
            """)
            delete_btn.setCursor(Qt.CursorShape.ArrowCursor)

        layout.addWidget(btn_frame)
    
    def _add_label_value_row(self, layout, label: str, value: str, mono: bool = False):
        """Add a label-value row matching Species Info panel style."""
        t = theme()
        row = QHBoxLayout()
        
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 13px;")
        label_widget.setFixedWidth(70)
        row.addWidget(label_widget)
        
        value_widget = QLabel(value if value else "—")
        style = f"font-weight: 600; color: {t.get('text_primary')}; font-size: 13px;"
        if mono:
            style += " font-family: 'Consolas', 'Monaco', monospace;"
        value_widget.setStyleSheet(style)
        value_widget.setWordWrap(True)
        row.addWidget(value_widget)
        
        row.addStretch()
        layout.addLayout(row)
    
    def update_profile(self, profile_text: str):
        """Called by the host after the editor saves: reload the accounts panel."""
        self.profile_text = profile_text
        if getattr(self, '_accounts_panel', None):
            self._accounts_panel.refresh()

    def _on_view_records(self):
        """Handle View all Records click - navigate to Observation Data tab."""
        species_name = self.record.get('species_name') or self.record.get('species', '')
        if species_name:
            self.navigate_to_observations.emit(species_name)
        self.accept()
    
    def _on_view_collection(self):
        """Handle View all In Collection click - navigate to Insect Collection tab."""
        species_name = self.record.get('species_name') or self.record.get('species', '')
        if species_name:
            self.navigate_to_collection.emit(species_name)
        self.accept()
    
    def _on_edit(self):
        """Handle edit click - emit signal but don't close dialog yet."""
        self.edit_requested.emit(self.record)
    
    def _on_delete(self):
        """Handle delete click with confirmation."""
        species_name = self.record.get('species_name', 'this record')
        record_type_text = "specimen" if self.record_type == 'specimen' else "observation"
        
        reply = QMessageBox.warning(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the {record_type_text} of <b>{species_name}</b>?"
            f"\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(self.record)
            self.accept()


# Backwards-compatible aliases
SpecimenDetailDialog = RecordDetailDialog
ObservationDetailDialog = RecordDetailDialog

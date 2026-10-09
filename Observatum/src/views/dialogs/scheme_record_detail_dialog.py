"""
Scheme Record Detail Dialog.

Modal dialog for viewing Recording Scheme record details.
Styled consistently with RecordDetailDialog (Observation/Specimen).
"""


from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QPushButton, QWidget, QMessageBox, QScrollArea
)
from PySide6.QtCore import Signal, Qt

from ...themes import theme
from ...core.config import TabColors, ButtonColors


class SchemeRecordDetailDialog(QDialog):
    """
    Modal dialog for viewing Recording Scheme record details.
    
    Styled to match RecordDetailDialog for consistency across tabs.
    Uses Recording Scheme tab accent colors (Dusty Purple).
    """

    # Signals
    profile_requested = Signal(dict)
    edit_requested = Signal(dict)
    delete_requested = Signal(dict)
    navigate_to_observations = Signal(str)  # species name - go to Observation Data tab
    navigate_to_collection = Signal(str)    # species name - go to Insect Collection tab

    def __init__(
        self,
        record: dict,
        parent=None,
        uksi_model=None,
        profile_text: str = None
    ):
        super().__init__(parent)
        self.record = record
        self.uksi_model = uksi_model
        self.profile_text = profile_text
        self._taxonomy = None
        self._profile_preview = None  # Reference to update after save

        # Load counts
        self._observation_count = 0
        self._specimen_count = 0
        self._load_counts()

        # Recording Scheme tab colors
        self._accent = TabColors.RECORDING_SCHEME
        self._accent_light = TabColors.RECORDING_SCHEME_LIGHT
        self._accent_dark = TabColors.RECORDING_SCHEME_DARK
        self._title = "RECORDING SCHEME RECORD"

        t = theme()

        self.setWindowTitle("Record Detail")
        self.setMinimumWidth(1000)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background-color: {t.get('surface')}; }}")

        # Lookup taxonomy from UKSI if available
        self._lookup_taxonomy()
        self._setup_ui()

        self.setMinimumHeight(600)
        self.resize(1200, 760)

    def _load_counts(self):
        """Load observation and specimen counts for this species."""
        species_name = self.record.get('species') or self.record.get('species_name')

        if not species_name:
            return

        try:
            from ...models.database import get_database
            db = get_database()

            # Count observations
            result = db.execute_main(
                "SELECT COUNT(*) FROM observations WHERE species_name = ?",
                (species_name,)
            )
            self._observation_count = result[0][0] if result else 0

            # Count specimens
            result = db.execute_main(
                "SELECT COUNT(*) FROM specimens WHERE species_name = ?",
                (species_name,)
            )
            self._specimen_count = result[0][0] if result else 0

        except Exception as e:
            print(f"[SchemeRecordDetailDialog] Error loading counts: {e}")

    def _lookup_taxonomy(self):
        """Look up full taxonomy from UKSI database."""
        if not self.uksi_model:
            return

        species_name = self.record.get('species') or self.record.get('species_name', '')

        try:
            species = None
            if species_name:
                if hasattr(self.uksi_model, 'get_species_by_name'):
                    species = self.uksi_model.get_species_by_name(species_name)
                elif hasattr(self.uksi_model, 'search'):
                    results = self.uksi_model.search(species_name)
                    if results:
                        species = results[0]

            if species:
                if isinstance(species, dict):
                    self._taxonomy = {
                        'order': species.get('order_name') or species.get('order', ''),
                        'family': species.get('family', ''),
                        'common_name': species.get('common_name', ''),
                    }
                else:
                    self._taxonomy = {
                        'order': getattr(species, 'order_name', '') or getattr(species, 'order', ''),
                        'family': getattr(species, 'family', ''),
                        'common_name': getattr(species, 'common_name', ''),
                    }
        except Exception as e:
            print(f"[SchemeRecordDetailDialog] UKSI lookup error: {e}")

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

        # Header with title
        self._add_header(layout)

        # Species name (large, italic)
        self._add_species_name(layout)

        # Taxonomy rows (Order, Family, Subfamily)
        self._add_taxonomy_rows(layout)

        # Navigation rows (Records + In Collection)
        self._add_navigation_rows(layout)

        # Separator
        self._add_separator(layout)

        # Record details (Date, Grid Ref, Location, Vice County)
        self._add_details_section(layout)

        # Separator before status
        self._add_separator(layout)

        # Verification status
        self._add_status_section(layout)

        # Recorder/Determiner
        self._add_people_section(layout)

        # Source section
        self._add_source_section(layout)

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
        """Add header with title."""
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
        species_name = self.record.get('species') or self.record.get('species_name', 'Unknown')

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
            common_name = self.record.get('common') or self.record.get('common_name')

        if common_name:
            common_label = QLabel(common_name)
            common_label.setStyleSheet(f"""
                font-size: 14px;
                color: {t.get('text_primary')};
            """)
            layout.addWidget(common_label)

    def _add_taxonomy_rows(self, layout):
        """Add taxonomy rows."""
        t = theme()

        # Get values from UKSI lookup or record
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

        # Subfamily row (important for Recording Scheme - Cerambycidae)
        if subfamily_val:
            self._add_label_value_row(layout, "Subfamily", subfamily_val)

    def _add_navigation_rows(self, layout):
        """Add Records and In Collection navigation rows."""
        t = theme()
        layout.addSpacing(4)

        # Records row (observations)
        records_row = QHBoxLayout()

        if self._observation_count > 0:
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
            no_records_label = QLabel("No Records")
            no_records_label.setStyleSheet(f"color: {t.get('text_muted')}; font-size: 13px;")
            records_row.addWidget(no_records_label)
            records_row.addStretch()

        layout.addLayout(records_row)

        # In Collection row (specimens)
        collection_row = QHBoxLayout()

        if self._specimen_count > 0:
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

            collection_count = QLabel(str(self._specimen_count))
            collection_count.setStyleSheet(f"""
                font-size: 16px;
                font-weight: 700;
                color: {TabColors.COLLECTION};
            """)
            collection_row.addWidget(collection_count)
        else:
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
        # Date
        date_val = self.record.get('date', '')
        if date_val:
            self._add_label_value_row(layout, "Date", date_val)

        # Grid Ref
        grid_ref = self.record.get('gridRef') or self.record.get('grid_ref', '')
        if grid_ref:
            self._add_label_value_row(layout, "Grid Ref", grid_ref, mono=True)

        # Location
        location = self.record.get('location') or self.record.get('site_name', '')
        if location:
            self._add_label_value_row(layout, "Location", location)

        # Vice County
        vc_name = self.record.get('vcName') or self.record.get('vice_county', '')
        vc_num = self.record.get('vc') or self.record.get('vc_number', '')
        if vc_name or vc_num:
            if vc_name and vc_num:
                vc_display = f"{vc_name} (VC{vc_num})"
            elif vc_name:
                vc_display = vc_name
            else:
                vc_display = f"VC{vc_num}"
            self._add_label_value_row(layout, "Vice County", vc_display)

    def _add_status_section(self, layout):
        """Add verification status with badge."""
        t = theme()
        status = self.record.get('verification') or self.record.get('verification_status', '')
        
        if not status:
            return

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

    def _add_people_section(self, layout):
        """Add recorder and determiner."""
        # Recorder
        recorder = self.record.get('recorder', '')
        if recorder:
            self._add_label_value_row(layout, "Recorder", recorder)

        # Determiner
        determiner = self.record.get('determiner', '')
        if determiner and determiner != recorder:
            self._add_label_value_row(layout, "Determiner", determiner)

    def _add_source_section(self, layout):
        """Add source with styled badge."""
        t = theme()
        source = self.record.get('source', '')
        
        if not source:
            return

        source_row = QHBoxLayout()

        source_label = QLabel("Source")
        source_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 13px;")
        source_label.setFixedWidth(70)
        source_row.addWidget(source_label)

        # Source badge
        badge = QLabel(source)
        source_colors = {
            'iRecord': f"background: {t.get('info_bg')}; color: {t.get('info_text')};",
            'NBN': f"background: {t.get('info_bg')}; color: {t.get('info_text')};",
            'Email': f"background: {t.get('surface_alt')}; color: {t.get('text_secondary')};",
            'BWARS database': f"background: {t.get('surface_alt')}; color: {t.get('text_secondary')};",
        }
        badge_style = source_colors.get(source, f"background: {t.get('surface_alt')}; color: {t.get('text_secondary')};")
        badge.setStyleSheet(f"""
            {badge_style}
            padding: 4px 8px;
            border-radius: {t.get('radius_sm')};
            font-weight: 600;
            font-size: 12px;
        """)
        source_row.addWidget(badge)
        source_row.addStretch()

        # Source key if present
        source_key = self.record.get('sourceKey')
        if source_key:
            key_label = QLabel(source_key)
            key_label.setStyleSheet(f"""
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
                color: {t.get('text_muted')};
            """)
            source_row.addWidget(key_label)

        layout.addLayout(source_row)

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
        """Handle View records click - navigate to Observation Data tab."""
        species_name = self.record.get('species') or self.record.get('species_name', '')
        if species_name:
            self.navigate_to_observations.emit(species_name)
        self.accept()

    def _on_view_collection(self):
        """Handle View all In Collection click - navigate to Insect Collection tab."""
        species_name = self.record.get('species') or self.record.get('species_name', '')
        if species_name:
            self.navigate_to_collection.emit(species_name)
        self.accept()

    def _on_edit(self):
        """Handle edit click."""
        self.edit_requested.emit(self.record)

    def _on_delete(self):
        """Handle delete click with confirmation."""
        species_name = self.record.get('species', 'this record')

        reply = QMessageBox.warning(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the record of <b>{species_name}</b>?"
            f"\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(self.record)
            self.accept()

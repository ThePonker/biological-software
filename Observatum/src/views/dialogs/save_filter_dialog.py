"""
Save Filter Dialog.

Generic dialog for saving filter configurations.
Can be used by Recording Scheme, Observation, and Collection tabs.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QPushButton, QLineEdit
)

from ...themes import theme
from ...core.config import ButtonColors


class SaveFilterDialog(QDialog):
    """Dialog for saving current filter configuration."""

    def __init__(self, current_filters: dict, parent=None):
        super().__init__(parent)
        self.current_filters = current_filters
        self.setWindowTitle("Save Filter")
        self.setFixedWidth(350)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        t = theme()
        self.setStyleSheet(f"QDialog {{ background-color: {t.get('surface')}; }}")

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Name input
        name_label = QLabel("Filter Name")
        name_label.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 600;
            color: {t.get('text_primary')};
        """)
        layout.addWidget(name_label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Oxfordshire records, Pending 2024...")
        self.name_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px 12px;
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_md')};
                font-size: 13px;
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
            }}
            QLineEdit:focus {{
                border-color: {t.get('primary')};
            }}
        """)
        layout.addWidget(self.name_input)

        # Current filters display
        filters_frame = QFrame()
        filters_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface_alt')};
                border-radius: {t.get('radius_md')};
                padding: 12px;
            }}
        """)
        filters_layout = QVBoxLayout(filters_frame)
        filters_layout.setContentsMargins(12, 12, 12, 12)

        filters_header = QLabel("CURRENT FILTER SETTINGS")
        filters_header.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 600;
            color: {t.get('text_secondary')};
            letter-spacing: 0.5px;
        """)
        filters_layout.addWidget(filters_header)

        # Show active filters
        active_filters = self._get_active_filters()

        if active_filters:
            for f in active_filters:
                lbl = QLabel(f)
                lbl.setStyleSheet(f"color: {t.get('text_primary')}; font-size: 12px;")
                filters_layout.addWidget(lbl)
        else:
            no_filters = QLabel("No filters applied")
            no_filters.setStyleSheet(f"color: {t.get('text_muted')}; font-style: italic;")
            filters_layout.addWidget(no_filters)

        layout.addWidget(filters_frame)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        # Save button (primary)
        save_btn = QPushButton("Save Filter")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ButtonColors.PRIMARY};
                color: white;
                border: none;
                border-radius: {t.get('radius_md')};
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {ButtonColors.PRIMARY_HOVER};
            }}
        """)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn, 1)

        # Cancel button (outlined)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_secondary')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_md')};
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _get_active_filters(self) -> list:
        """Get list of active filter descriptions."""
        active = []
        
        # Common filter keys
        filter_labels = {
            'source': 'Source',
            'species': 'Species',
            'location': 'Location',
            'site_name': 'Location',
            'date_from': 'Date From',
            'date_to': 'Date To',
            'subfamily': 'Subfamily',
            'vice_county': 'Vice County',
            'vc_number': 'Vice County',
            'status': 'Status',
            'verification_status': 'Status',
            'data_type': 'Data Type',
            'record_type': 'Record Type',
            'order': 'Order',
            'family': 'Family',
            'recorder': 'Recorder',
            'method': 'Method',
        }

        for key, label in filter_labels.items():
            value = self.current_filters.get(key)
            if value and value != 'all' and value != 'All':
                active.append(f"{label}: {value}")

        return active

    def get_filter_name(self) -> str:
        """Get entered filter name."""
        return self.name_input.text().strip()

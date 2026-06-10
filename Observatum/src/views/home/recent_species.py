"""
Recent Species Panel Component.

Displays recently recorded new species with stacked layout:
- Common name (bold) - if enabled in settings
- Scientific name (italic)
- Date (dd/mm/yyyy)
"""

from typing import List, Dict

from PySide6.QtWidgets import (
    QListWidget, QListWidgetItem, QStyledItemDelegate, QStyle
)
from PySide6.QtCore import Qt, Signal, QSize, QRectF, QSettings
from PySide6.QtGui import QTextDocument

from .card import Card
from ...utils.date_utils import format_date_display
from ...themes import theme
from ...core.config import Settings, Defaults


class HtmlItemDelegate(QStyledItemDelegate):
    """Custom delegate to render HTML/rich text in list items."""

    def paint(self, painter, option, index):
        """Paint the item with HTML support."""
        options = option
        self.initStyleOption(options, index)

        painter.save()

        doc = QTextDocument()
        doc.setHtml(options.text)
        doc.setTextWidth(options.rect.width())

        options.text = ""
        options.widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, options, painter)

        painter.translate(options.rect.left(), options.rect.top())
        clip = QRectF(0, 0, options.rect.width(), options.rect.height())
        doc.drawContents(painter, clip)

        painter.restore()

    def sizeHint(self, option, index):
        """Calculate size hint for the item."""
        options = option
        self.initStyleOption(options, index)

        doc = QTextDocument()
        doc.setHtml(options.text)
        doc.setTextWidth(options.rect.width() if options.rect.width() > 0 else 280)

        # Add extra padding for 3-line items
        return QSize(int(doc.idealWidth()), int(doc.size().height()) + 12)


class RecentSpeciesPanel(Card):
    """Panel showing recently recorded new species."""

    species_selected = Signal(dict)  # Emits full species data
    view_all_clicked = Signal()  # Emits when "View All" is clicked

    def __init__(self, parent=None):
        super().__init__("Recent New Species", parent)
        self._species_data: List[Dict] = []
        self._show_common_names = True
        self._load_common_name_setting()
        self._setup_ui()

    def _load_common_name_setting(self):
        """Load the common name display setting."""
        settings = QSettings()
        self._show_common_names = settings.value(
            Settings.COMMON_NAMES_HOME, 
            Defaults.SHOW_COMMON_NAMES, 
            type=bool
        )

    def _setup_ui(self):
        """Set up the panel UI."""
        t = theme()

        self.species_list = QListWidget()
        self.species_list.setItemDelegate(HtmlItemDelegate())
        self.species_list.setStyleSheet(f"""
            QListWidget {{
                border: none;
                background-color: transparent;
            }}
            QListWidget::item {{
                padding: 8px 4px;
                border-bottom: 1px solid {t.get('border')};
            }}
            QListWidget::item:hover {{
                background-color: {t.get('success_bg')};
            }}
            QListWidget::item:selected {{
                background-color: {t.get('success_bg')};
                color: {t.get('text_primary')};
            }}
        """)
        self.species_list.itemClicked.connect(self._on_item_clicked)
        self.species_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.add_widget(self.species_list)
        
        # Add "View All" link to header
        from PySide6.QtWidgets import QPushButton
        self.view_all_btn = QPushButton("View All")
        self.view_all_btn.setFlat(True)
        self.view_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.view_all_btn.setStyleSheet(f"""
            QPushButton {{
                color: {t.get("success_text")};
                font-size: 11px;
                padding: 2px 8px;
                border: none;
                background: transparent;
            }}
            QPushButton:hover {{
                text-decoration: underline;
            }}
        """)
        self.view_all_btn.clicked.connect(self.view_all_clicked.emit)
        self.add_header_widget(self.view_all_btn)

    def update_species(self, species_list: list):
        """Update the species list with stacked 3-line display."""
        t = theme()
        self.species_list.clear()
        self._species_data = species_list

        for i, species in enumerate(species_list):
            sci_name = species.get('species_name', '')
            first_date = species.get('first_date', '')
            common_name = species.get('common_name', '')

            # Format date using user's preferred format
            display_date = format_date_display(first_date, "user")

            # Build stacked HTML:
            # Line 1: Common name (bold) - or scientific name if no common (only if setting enabled)
            # Line 2: Scientific name (italic) - only if common name exists and shown
            # Line 3: Date (muted)

            if common_name and self._show_common_names:
                display = f"""
                    <div style="line-height: 1.4;">
                        <div><b>{common_name}</b></div>
                        <div><i style="color: {t.get('text_secondary')};">{sci_name}</i></div>
                        <div style="color: {t.get('text_muted')}; font-size: 0.9em;">{display_date}</div>
                    </div>
                """
            else:
                # No common name or setting disabled - show scientific name only
                display = f"""
                    <div style="line-height: 1.4;">
                        <div><i><b>{sci_name}</b></i></div>
                        <div style="color: {t.get('text_muted')}; font-size: 0.9em;">{display_date}</div>
                    </div>
                """

            item = QListWidgetItem(display.strip())
            item.setData(Qt.ItemDataRole.UserRole, i)

            # Tooltip - always include common name in tooltip for reference
            tooltip = sci_name
            if common_name:
                tooltip = f"{common_name}\n{sci_name}"
            tooltip += f"\nFirst recorded: {display_date}"
            item.setToolTip(tooltip)

            self.species_list.addItem(item)

    def refresh_common_name_setting(self):
        """Refresh the common name display setting and update list."""
        old_setting = self._show_common_names
        self._load_common_name_setting()
        
        # Only rebuild if setting changed and we have data
        if old_setting != self._show_common_names and self._species_data:
            self.update_species(self._species_data)

    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle single click on species item."""
        idx = item.data(Qt.ItemDataRole.UserRole)
        if idx is not None and idx < len(self._species_data):
            species = self._species_data[idx]
            self.species_selected.emit(species)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on species item."""
        self._on_item_clicked(item)

    def apply_theme(self):
        """Apply the current theme."""
        t = theme()

        self.species_list.setStyleSheet(f"""
            QListWidget {{
                border: none;
                background-color: transparent;
            }}
            QListWidget::item {{
                padding: 8px 4px;
                border-bottom: 1px solid {t.get('border')};
            }}
            QListWidget::item:hover {{
                background-color: {t.get('success_bg')};
            }}
            QListWidget::item:selected {{
                background-color: {t.get('success_bg')};
                color: {t.get('text_primary')};
            }}
        """)
        
        # Rebuild list to apply theme colors
        if self._species_data:
            self.update_species(self._species_data)

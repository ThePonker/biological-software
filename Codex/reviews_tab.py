"""Reviews tab — browse loaded reviews with metadata."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame
)

from . import theme


class ReviewsTab(QWidget):
    """Browse loaded reviews."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Summary cards
        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.total_card = self._make_card("Total Species", "—")
        self.reviews_card = self._make_card("Reviews Loaded", "—")
        self.sqs_card = self._make_card("SQS Scores", "—")
        cards.addWidget(self.total_card)
        cards.addWidget(self.reviews_card)
        cards.addWidget(self.sqs_card)
        cards.addStretch()
        layout.addLayout(cards)

        # Reviews table
        table_label = QLabel("LOADED REVIEWS")
        table_label.setStyleSheet(
            f"font-weight: 600; color: {theme.TEXT_HEADING}; "
            f"font-size: 11px; letter-spacing: 1px;"
        )
        layout.addWidget(table_label)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Review Name", "Author", "Group", "Track",
            "Species", "Date Published"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {theme.BORDER};
                gridline-color: {theme.SEPARATOR};
                font-size: 12px;
            }}
            QTableWidget::item {{
                padding: 6px 8px;
            }}
            QHeaderView::section {{
                background-color: {theme.SURFACE_ALT};
                border: none;
                border-bottom: 1px solid {theme.BORDER};
                padding: 8px;
                font-weight: 600;
                font-size: 11px;
                color: {theme.TEXT_HEADING};
            }}
        """)
        layout.addWidget(self.table, 1)

        # JNCC base info
        self.jncc_label = QLabel()
        self.jncc_label.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 11px;"
        )
        layout.addWidget(self.jncc_label)

    def _make_card(self, label_text, value_text):
        card = QFrame()
        card.setFixedSize(180, 70)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {theme.SURFACE};
                border: 1px solid {theme.BORDER};
                border-radius: {theme.RADIUS_MD};
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 8, 12, 8)
        lbl = QLabel(label_text)
        lbl.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 10px; "
            f"font-weight: 600; letter-spacing: 1px;"
        )
        cl.addWidget(lbl)
        val = QLabel(value_text)
        val.setObjectName("card_value")
        val.setStyleSheet(
            f"color: {theme.ACCENT}; font-size: 20px; font-weight: 700;"
        )
        cl.addWidget(val)
        return card

    def _set_card_value(self, card, value):
        lbl = card.findChild(QLabel, "card_value")
        if lbl:
            lbl.setText(str(value))

    def refresh(self):
        try:
            from shared.repositories.codex_repository import CodexRepository
            repo = CodexRepository()
            reviews = repo.get_reviews()
            meta = repo.get_metadata()
            count = repo.get_species_count()
            repo.close()

            import sqlite3, paths
            conn = sqlite3.connect(str(paths.CODEX_DB))
            sqs_count = conn.execute("SELECT COUNT(*) FROM sqs_scores").fetchone()[0]
            conn.close()
        except Exception as e:
            self.jncc_label.setText(f"Error: {e}")
            return

        self._set_card_value(self.total_card, f"{count:,}")
        self._set_card_value(self.reviews_card, str(len(reviews)))
        self._set_card_value(self.sqs_card, f"{sqs_count:,}")

        self.table.setRowCount(len(reviews))
        for row, r in enumerate(reviews):
            self.table.setItem(row, 0, QTableWidgetItem(str(r.get("id", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(r.get("review_name", "")))
            self.table.setItem(row, 2, QTableWidgetItem(r.get("author", "")))
            self.table.setItem(row, 3, QTableWidgetItem(r.get("taxon_group", "")))
            self.table.setItem(row, 4, QTableWidgetItem(r.get("status_track", "")))
            self.table.setItem(row, 5, QTableWidgetItem(str(r.get("species_count", ""))))
            self.table.setItem(row, 6, QTableWidgetItem(
                theme.format_date(r.get("date_published", ""))))

        jncc_date = theme.format_date(meta.get("jncc_date", "unknown"))
        build_date = theme.format_date(meta.get("build_date", "unknown"))
        self.jncc_label.setText(
            f"Base: JNCC Conservation Designations {jncc_date}  |  "
            f"Last rebuild: {build_date}"
        )

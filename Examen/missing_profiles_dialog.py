"""
Examen -- the Missing profiles dialog: which species of the analysed survey have no account of
Wil's own.

"Account of yours" is shared.species_accounts.get_species_accounts(tvk, name).own -- the one
reader; nothing here queries species_profiles. The species, status, common name and record
count come from the survey's detail.species_list (what the Species tab shows), so no figure is
recounted. Write account... (or a double-click) opens Observatum's own profile editor; when it
closes the list is read again, so a species that now has an account drops off.
"""
import paths
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel,
                               QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout)

from Examen.presentation import status_name, vernacular
from Examen.site_analysis_view import BTN_OUTLINE, BTN_PRIMARY, TABLE_STYLE
from Examen.style import TEXT_SECONDARY
from shared.species_accounts import get_species_accounts
from shared.text_sizes import font_css

HEADS = ["Species", "Common name", "Status", "Records", "Review account"]
TIER_ORDER = {"Rare": 0, "Scarce": 1, "Priority": 2}      # any other tier follows, then non-key
NO_EDITOR = ("The species account editor could not be opened from Examen.\n\n"
             "Write the account in Observatum (Home, then the species' account).")


def editor_class():
    """Observatum's SpeciesProfileDialog, or None where Observatum is not on the path."""
    try:
        from src.views.home.species_profile_dialog import SpeciesProfileDialog
        return SpeciesProfileDialog
    except Exception:  # noqa: BLE001 -- a missing or broken Observatum must not crash Examen
        return None


def point_observatum_database():
    """The editor reads and writes through Observatum's get_database() singleton. Point it at
    the suite's databases only where nothing has set it already (Observatum's own start does)."""
    from src.models.database import get_database
    db = get_database()
    if db.main_db_path is None:
        db.set_main_path(str(paths.OBSERVATUM_DB))
    if db.uksi_db_path is None:
        db.set_uksi_path(str(paths.UKSI_DB))


def _rank(sp):
    tier = getattr(sp, "tier", "") or ""
    return (TIER_ORDER.get(tier, 3) if tier else 4, (sp.name or "").lower())


class MissingProfilesDialog(QDialog):
    def __init__(self, detail, parent=None):
        """detail: the analysed survey's SiteDetail (its species_list, invertebrates as counted)."""
        super().__init__(parent)
        self.setWindowTitle("Missing profiles")
        self.resize(860, 520)
        self._species = sorted(getattr(detail, "species_list", None) or [], key=_rank)
        self._missing = []            # [(SiteSpecies, has_review)] without an account of yours
        self._unreadable = []         # SiteSpecies whose account of yours could not be READ
        self._shown = []              # the SiteSpecies behind each table row
        self._key_total = self._key_missing = self._all_total = 0
        lay = QVBoxLayout(self)
        self.header = QLabel()
        self.header.setWordWrap(True)
        self.header.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {font_css('body')};")
        lay.addWidget(self.header)
        self.show_all = QCheckBox("Show all species")
        self.show_all.toggled.connect(self._fill)
        lay.addWidget(self.show_all)
        self.table = QTableWidget(0, len(HEADS))
        self.table.setHorizontalHeaderLabels(HEADS)
        self.table.setStyleSheet(TABLE_STYLE)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(lambda r, _c: self.write_account(r))
        lay.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        self.write_btn = QPushButton("Write account…")
        self.write_btn.setStyleSheet(BTN_PRIMARY)
        self.write_btn.setToolTip("Open the species account editor for the selected species.")
        self.write_btn.clicked.connect(lambda: self.write_account(self.table.currentRow()))
        buttons.addWidget(self.write_btn)
        buttons.addStretch(1)
        close = QPushButton("Close")
        close.setStyleSheet(BTN_OUTLINE)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        lay.addLayout(buttons)
        self.refresh()

    # ------------------------------------------------------------------ data
    def refresh(self):
        """Read the accounts again (the editor may have saved one) and redraw."""
        self._missing = []
        self._unreadable = []
        self._key_total = self._key_missing = 0
        for sp in self._species:
            acc = get_species_accounts(sp.tvk or None, sp.name)
            key = bool(getattr(sp, "tier", ""))
            self._key_total += key
            if not acc.own and acc.own_read_error:
                self._unreadable.append(sp)       # not "no account": we could not look
                continue
            if not acc.own:
                self._missing.append((sp, acc.current_review is not None))
                self._key_missing += key
        self._all_total = len(self._species)
        self._fill()

    def _header_text(self):
        if not self._key_total:
            text = "This survey has no Key Species."
        else:
            text = (f"{self._key_missing} of {self._key_total} Key Species "
                    "have no account of yours.")
        if self.show_all.isChecked():
            text += (f" {len(self._missing)} of {self._all_total} species in all "
                     "have no account of yours.")
        if self._unreadable:
            names = ", ".join(sp.name or "" for sp in self._unreadable[:8])
            more = len(self._unreadable) - 8
            text = (f"\u26a0 Your accounts could not be read for {len(self._unreadable)} species "
                    f"({names}{f' and {more} more' if more > 0 else ''}), so they are not "
                    "listed or counted below. Close Observatum and try again.\n" + text)
        return text

    def _fill(self, _checked=None):
        rows = [(sp, rev) for sp, rev in self._missing
                if self.show_all.isChecked() or getattr(sp, "tier", "")]
        self._shown = [sp for sp, _ in rows]
        self.header.setText(self._header_text())
        self.table.setRowCount(len(rows))
        italic = QFont(self.table.font())
        italic.setItalic(True)
        for i, (sp, review) in enumerate(rows):
            name = QTableWidgetItem(sp.name or "")
            name.setFont(italic)
            common = vernacular(getattr(sp, "common_name", ""), getattr(sp, "family", ""),
                                getattr(sp, "order_name", ""))
            records = QTableWidgetItem(str(sp.count))
            records.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            flag = QTableWidgetItem("yes" if review else "")
            flag.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            for col, item in enumerate((name, QTableWidgetItem(common),
                                        QTableWidgetItem(status_name(sp.status)), records, flag)):
                self.table.setItem(i, col, item)

    # ------------------------------------------------------------------ editor
    def write_account(self, row):
        if not 0 <= row < len(self._shown):
            return
        sp = self._shown[row]
        cls = editor_class()
        if cls is None:
            QMessageBox.information(self, "Write account", NO_EDITOR)
            return
        try:
            point_observatum_database()
            cls({"tvk": sp.tvk, "scientific_name": sp.name,
                 "common_name": getattr(sp, "common_name", "") or ""}, self).exec()
        except Exception as e:  # noqa: BLE001 -- say so; never crash the survey view
            QMessageBox.warning(self, "Write account", f"{NO_EDITOR}\n\n({e})")
            return
        self.refresh()

"""The form for one extracted record: what a BHL page says (Round 15b).

"Record from this page…" in the reading list opens it with the species and the page's
citation filled in; Edit on the Extracted records screen opens it with a stored record.
Saving goes through LectorService (add_record / update_record); a field that fails its
check is explained in the dialog and nothing is saved.
"""
from PySide6.QtWidgets import (QDialog, QGridLayout, QHBoxLayout, QLineEdit, QPlainTextEdit,
                               QSpinBox, QVBoxLayout, QWidget)

from Lector.service import LectorError
from Lector.ui import style as S
from shared.fit_to_screen import scroll_body

BLANK = 0          # a spin box at its minimum shows nothing: the field is left blank
TEXT_FIELDS = (("date_printed", "Date as printed", "e.g. 14th June 1873"),
               ("place", "Place as printed", "e.g. Darenth Wood, near Dartford"),
               ("grid_ref", "Grid reference", "optional, e.g. TQ5571"),
               ("recorder", "Recorder / collector as printed", "e.g. Mr. J. Smith"),
               ("determiner", "Determiner", "if the page says who named it"),
               ("count", "Count", "e.g. 2, or “several”"),
               ("sex", "Sex", "e.g. female"),
               ("stage", "Stage", "e.g. adult"))
SOURCE_FIELDS = (("source_title", "Title"), ("source_volume", "Volume"),
                 ("source_page", "Page"), ("bhl_url", "BHL page address"))


def _spin(high, tip):
    box = QSpinBox()
    box.setRange(BLANK, high)
    box.setSpecialValueText(" ")
    box.setToolTip(tip + " Leave blank if the page does not say.")
    box.setMinimumWidth(80)
    return box


class RecordDialog(QDialog):
    """New record from a page (search_id, page_id), or an edit (record_id)."""

    def __init__(self, svc, search_id=None, page_id=None, record_id=None, parent=None):
        super().__init__(parent)
        self.svc, self.search_id, self.page_id, self.record_id = svc, search_id, page_id, record_id
        self.saved_id = None
        self.setWindowTitle("Edit record" if record_id else "Record from this page")
        self.setStyleSheet(S.app_qss())
        self.setMinimumWidth(680)
        outer = QVBoxLayout(self)
        body = QWidget()
        v = QVBoxLayout(body)
        v.setSpacing(8)
        v.addWidget(S.label("Type what the page says, as it is printed. Only the species is "
                            "needed; leave out anything the page does not give.",
                            "muted", wrap=True))
        self.edits = {}
        v.addWidget(S.label("Species (as UKSI names it)", "small"))
        srow = QHBoxLayout()
        self.species_edit = self._edit("species", "e.g. Lamia textor")
        self.check_btn = S.button("Check name", "outline",
                                  "Look the name up in UKSI, as the search builder does",
                                  self.check_species)
        srow.addWidget(self.species_edit, 1)
        srow.addWidget(self.check_btn)
        v.addLayout(srow)
        self.species_note = S.label("", "small", wrap=True)
        v.addWidget(self.species_note)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        v.addLayout(grid)
        for i, (key, text, hint) in enumerate(TEXT_FIELDS):
            self._cell(grid, key, text, hint, i)
        row = (len(TEXT_FIELDS) + 1) // 2 * 2
        grid.addWidget(S.label("Parsed date (any part may be blank)", "small"), row, 0, 1, 2)
        dates = QHBoxLayout()
        self.day = _spin(31, "Day of the month.")
        self.month = _spin(12, "Month, 1 to 12.")
        self.year = _spin(2100, "Year.")
        self.vc = _spin(112, "Vice county number (1 to 112).")
        for name, box, text in (("day", self.day, "Day"), ("month", self.month, "Month"),
                                ("year", self.year, "Year"), ("vice_county", self.vc,
                                                              "Vice county")):
            box.setObjectName("rec_" + name)
            dates.addWidget(S.label(text, "small"))
            dates.addWidget(box)
        dates.addStretch(1)
        grid.addLayout(dates, row + 1, 0, 1, 2)
        v.addWidget(S.label("Comment", "small"))
        self.comment = QPlainTextEdit()
        self.comment.setObjectName("rec_comment")
        self.comment.setFixedHeight(60)
        self.comment.setPlaceholderText("Anything else the page says, or doubts about the OCR")
        v.addWidget(self.comment)
        v.addWidget(S.label("Where it was read", "caps"))
        src = QGridLayout()
        src.setHorizontalSpacing(10)
        src.setVerticalSpacing(4)
        v.addLayout(src)
        for i, (key, text) in enumerate(SOURCE_FIELDS):
            self._cell(src, key, text, "", i)
        self.source_year = _spin(2200, "Year of the publication.")
        self.source_year.setObjectName("rec_source_year")
        yrow = QHBoxLayout()
        yrow.addWidget(S.label("Publication year", "small"))
        yrow.addWidget(self.source_year)
        yrow.addStretch(1)
        v.addLayout(yrow)
        v.addWidget(S.label("Full citation", "small"))
        self.citation = QPlainTextEdit()
        self.citation.setObjectName("rec_citation")
        self.citation.setFixedHeight(54)
        v.addWidget(self.citation)
        v.addStretch(1)
        outer.addWidget(scroll_body(body), 1)
        self.message = S.label("", "warn", wrap=True)
        outer.addWidget(self.message)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.save_btn = S.button("Save record", "primary", slot=self.save)
        self.cancel_btn = S.button("Cancel", "cancel", slot=self.reject)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.cancel_btn)
        outer.addLayout(buttons)
        self._load()

    def _edit(self, key, hint):
        edit = QLineEdit()
        edit.setObjectName("rec_" + key)
        edit.setPlaceholderText(hint)
        self.edits[key] = edit
        return edit

    def _cell(self, grid, key, text, hint, i):
        """Field number i in a two-column grid, its label above the box."""
        row, col = i // 2 * 2, i % 2
        grid.addWidget(S.label(text, "small"), row, col)
        grid.addWidget(self._edit(key, hint), row + 1, col)

    # --- load / values -------------------------------------------------------------------
    def _load(self):
        if self.record_id:
            r = self.svc.get_record(self.record_id)
        else:
            r = self.svc.record_prefill(self.search_id, self.page_id)
        for key, edit in self.edits.items():
            edit.setText(str(r.get(key) or ""))
        for key, box in (("day", self.day), ("month", self.month), ("year", self.year),
                         ("vice_county", self.vc), ("source_year", self.source_year)):
            box.setValue(int(r.get(key) or BLANK))
        self.comment.setPlainText(r.get("comment") or "")
        self.citation.setPlainText(r.get("citation") or "")

    def values(self):
        f = {k: e.text() for k, e in self.edits.items()}
        f.update(day=self.day.value() or None, month=self.month.value() or None,
                 year=self.year.value() or None, vice_county=self.vc.value() or None,
                 source_year=self.source_year.value() or None,
                 comment=self.comment.toPlainText(), citation=self.citation.toPlainText())
        return f

    # --- actions -------------------------------------------------------------------------
    def check_species(self):
        """Look the name up in UKSI as the builder does; a found name replaces what was typed."""
        t = self.svc.resolve_taxon(self.edits["species"].text())
        if not t["found"]:
            self.species_note.setText(f"“{t['typed']}” is not in UKSI: check the spelling. "
                                      "You can still save it, but Observatum will not take "
                                      "the record until the name is one UKSI knows."
                                      if t["typed"] else "Type a species first.")
        elif t.get("uksi_missing"):
            self.species_note.setText("UKSI is not installed here, so the name is kept as "
                                      "typed and is not checked.")
        else:
            how = f" (you typed {t['typed']}, an older name)" if t["matched_as"] == "synonym" \
                else ""
            self.species_note.setText(f"UKSI: {t['name']}{how} · {t['tvk']}.")
            self.edits["species"].setText(t["name"])
        return t

    def save(self):
        try:
            if self.record_id:
                self.svc.update_record(self.record_id, self.values())
                self.saved_id = self.record_id
            else:
                self.saved_id = self.svc.add_record(self.search_id, self.page_id, self.values())
        except LectorError as exc:
            self.message.setText(str(exc))
            return None
        self.accept()
        return self.saved_id

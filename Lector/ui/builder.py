"""Search builder: species, names to search, filters, preview; save and run (mock-up screen 2).

Nothing is saved until "Save as draft" or "Save and run". The preview uses BHL's last
answers held in lector.db (instant); "Refresh count" asks BHL (one request per name)
in the background.
"""
from PySide6.QtCore import QStringListModel, Qt, QTimer
from PySide6.QtWidgets import (QComboBox, QCompleter, QGridLayout, QHBoxLayout, QLineEdit,
                               QVBoxLayout)

from Lector.ui import style as S
from Lector.ui.builder_filters import FiltersPanel
from Lector.ui.builder_names import NamesPanel
from Lector.ui.common import Screen

SPECIES_HELP = ("Type a species and press Find. A family (e.g. Cerambycidae) "
                "searches every UKSI species of the family.")
TEXT_HELP = ("Free-text search: type an author or a place (several terms separated by "
             "semicolons) and press Use terms. Terms are not checked against UKSI.")
PREVIEW_ROWS = (("found", "Found on BHL"), ("within_filters", "Within filters"),
                ("already_held", "Already in database"), ("to_download", "To download"))


class BuilderScreen(Screen):
    def __init__(self, win):
        super().__init__(win, "New search")
        self.show_back()
        self.search_id, self.target = None, None
        cols = QHBoxLayout()
        cols.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(12)
        left.addWidget(self._species_card())
        self.names = NamesPanel()
        self.names.changed.connect(self._schedule_preview)
        left.addWidget(self.names)
        self.filters = FiltersPanel(self.svc, win.say)
        self.filters.changed.connect(self._schedule_preview)
        left.addWidget(self.filters)
        left.addStretch(1)
        cols.addLayout(left, 1)
        cols.addLayout(self._preview_column())
        self.body.addLayout(cols)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.update_preview)

    # --- layout -------------------------------------------------------------
    def _species_card(self):
        card = S.Card("1. Species")
        self.mode_box = QComboBox()
        self.mode_box.addItem("Species, family or TVK (UKSI names)", "species")
        self.mode_box.addItem("Free text: an author or a place", "text")
        self.mode_box.setToolTip("Free-text searches send your terms to BHL as typed, with no "
                                 "UKSI name checks, and find whole books and articles")
        self.mode_box.activated.connect(lambda _i: self._mode_changed())
        mode_row = QHBoxLayout()
        mode_row.addWidget(S.label("Search for", "small"))
        mode_row.addWidget(self.mode_box)
        mode_row.addStretch(1)
        card.body.addLayout(mode_row)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        self.species_edit = QLineEdit()
        self.species_edit.setPlaceholderText("Species, family or TVK, e.g. Lamia textor")
        self.species_edit.returnPressed.connect(self.find_species)
        self.completer = QCompleter(QStringListModel(self), self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.activated.connect(self._suggestion_chosen)
        self.species_edit.setCompleter(self.completer)
        self._suggest_timer = QTimer(self)
        self._suggest_timer.setSingleShot(True)
        self._suggest_timer.setInterval(150)
        self._suggest_timer.timeout.connect(self.show_suggestions)
        self.species_edit.textEdited.connect(lambda _t: self._suggest_timer.start())
        self.find_btn = S.button("Find", "view", "Look the name up in UKSI", self.find_species)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Lamia textor — British literature")
        grid.addWidget(S.label("Species (UKSI)", "small"), 0, 0)
        grid.addWidget(S.label("Search name", "small"), 0, 2)
        grid.addWidget(self.species_edit, 1, 0)
        grid.addWidget(self.find_btn, 1, 1)
        grid.addWidget(self.name_edit, 1, 2)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(2, 2)
        card.body.addLayout(grid)
        self.matched = S.label(SPECIES_HELP, "muted", wrap=True)
        card.body.addWidget(self.matched)
        return card

    def _preview_column(self):
        col = QVBoxLayout()
        col.setSpacing(8)
        card = S.Card("Preview")
        card.setFixedWidth(290)
        grid = QGridLayout()
        grid.setVerticalSpacing(6)
        self.preview_values = {}
        for r, (key, text) in enumerate(PREVIEW_ROWS):
            bold = key == "to_download"
            name = S.label(text, "body")
            value = S.label("—", "body")
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            if bold:
                for w in (name, value):
                    w.setStyleSheet(w.styleSheet() + " font-weight: 700;")
            grid.addWidget(name, r, 0)
            grid.addWidget(value, r, 1)
            self.preview_values[key] = value
        card.body.addLayout(grid)
        self.preview_note = S.label("", "small", wrap=True)
        card.body.addWidget(self.preview_note)
        self.refresh_btn = S.button("Refresh count", "outline",
                                    "Ask BHL how many pages each name has (one request per "
                                    "name)", self.refresh_counts)
        card.body.addWidget(self.refresh_btn)
        col.addWidget(card)
        self.run_btn = S.button("Save and run", "primary", "Save, then fetch the pages from BHL",
                                lambda: self.save(run=True))
        self.draft_btn = S.button("Save as draft", "outline", "Save without running",
                                  lambda: self.save(run=False))
        self.cancel_btn = S.button("Cancel", "cancel", "Back to where you came from "
                                   "(nothing saved)", lambda: self.win.back())
        for b in (self.run_btn, self.draft_btn, self.cancel_btn):
            b.setFixedWidth(290)
            col.addWidget(b)
        col.addStretch(1)
        return col

    # --- open / load --------------------------------------------------------
    def open(self, search_id=None, **_kw):
        self.search_id = search_id
        self.species_edit.setReadOnly(search_id is not None)
        self.find_btn.setEnabled(search_id is None)
        self.mode_box.setEnabled(search_id is None)
        self.names.remember.setChecked(False)
        if search_id is None:
            self.mode_box.setCurrentIndex(0)
            self._mode_changed(refresh=False)
            self.title.setText("New search")
            self.target = None
            self.species_edit.clear()
            self.name_edit.clear()
            self.matched.setText(SPECIES_HELP)
            self.names.set_names([])
            self.svc.warm_suggestions()
            self.filters.set_filters(self.svc.default_filters())
            self.species_edit.setFocus()
        else:
            s = self.svc.get_search(search_id)
            self.mode_box.setCurrentIndex(1 if s["kind"] == "text" else 0)
            self._mode_changed(refresh=False)
            self.title.setText(f"Edit search: {s['name']}")
            self.target = {"found": True, "tvk": s["target_tvk"], "name": s["target_name"],
                           "kind": s["kind"]}
            self.species_edit.setText(s["target_name"] or "")
            self.name_edit.setText(s["name"])
            self.matched.setText(f"{s['target_name']} · {s['target_tvk'] or s['kind']}. "
                                 "The species of a saved search cannot change: duplicate it "
                                 "or make a new search." if s["kind"] != "text" else
                                 "A free-text search: edit its terms below.")
            if s["kind"] == "text":
                self.species_edit.setText("; ".join(n["name"] for n in s["names"]))
            defaults = None
            if s["kind"] == "species" and s["target_tvk"]:
                defaults = {c["name"]: c["included"] for c in
                            self.win.call(self.svc.candidate_names, s["target_tvk"]) or []}
            # stored names, plus the names the UKSI checks hold back (with the reasons)
            self.names.set_names(self.win.call(self.svc.edit_names, search_id) or s["names"],
                                 defaults)
            self.filters.set_filters(s["filters"])
        self.update_preview()

    def is_text(self):
        return self.mode_box.currentData() == "text"

    def _mode_changed(self, refresh=True):
        text = self.is_text()
        self.names.set_text_mode(text)
        self.find_btn.setText("Use terms" if text else "Find")
        self.find_btn.setToolTip("Use the terms typed" if text else "Look the name up in UKSI")
        self.species_edit.setPlaceholderText(
            "An author or a place; separate several with semicolons, e.g. Waterhouse; Rannoch"
            if text else "Species, family or TVK, e.g. Lamia textor")
        self.completer.setCompletionPrefix("")
        if refresh:
            self.target = None
            self.names.set_names([])
            self.matched.setText(TEXT_HELP if text else SPECIES_HELP)
            self.update_preview()

    def show_suggestions(self):
        """Fuzzy suggestions under the species box: typos and partial words are fine."""
        if self.is_text() or self.search_id is not None:
            return
        try:
            found = self.svc.suggest_taxa(self.species_edit.text())
        except Exception:  # noqa: BLE001 - no UKSI at hand: just no suggestions
            found = []
        self.completer.model().setStringList([f["name"] for f in found])
        if found and self.species_edit.hasFocus():
            self.completer.complete()

    def _suggestion_chosen(self, name):
        self.species_edit.setText(name)
        self.find_species()

    def use_terms(self):
        """Free text: the typed terms (separated by semicolons) become the names."""
        terms = [" ".join(t.split()) for t in self.species_edit.text().replace("\n", ";").split(";")]
        terms = list(dict.fromkeys(t for t in terms if t))
        if not terms:
            self.matched.setText("Type at least one term first.")
            return
        self.target = {"found": True, "name": terms[0], "tvk": None, "kind": "text"}
        self.matched.setText(f"{len(terms)} term{'s' if len(terms) != 1 else ''}: "
                             + "; ".join(terms) + ". No UKSI checks for a free-text search.")
        if not self.name_edit.text().strip():
            self.name_edit.setText(" / ".join(terms))
        self.names.set_names([{"name": t, "origin": "user_added", "included": True,
                               "held_back_reason": None, "accepted_name": t} for t in terms])
        self.update_preview()

    def find_species(self):
        if self.search_id is not None:
            return
        if self.is_text():
            return self.use_terms()
        t = self.svc.resolve_taxon(self.species_edit.text())
        if not t["found"]:
            self.target = None
            self.matched.setText(f"“{t['typed']}” is not in UKSI — check the "
                                 "spelling." if t["typed"] else "Type a species first.")
            self.names.set_names([])
            self.update_preview()
            return
        kind = "family" if (t["rank"] or "").lower() == "family" else "species"
        self.target = dict(t, kind=kind)
        bits = [t["tvk"], (t["rank"] or "").lower(), t["family"] or ""]
        how = (f" (you typed {t['typed']}, an older name)" if t["matched_as"] == "synonym"
               else "")
        others = (f" Also in UKSI: {', '.join(a['name'] for a in t['alternatives'][:3])}."
                  if t["alternatives"] else "")
        if kind == "family":
            names = self.svc.family_names(t["name"])
            self.matched.setText(f"Matched {t['name']} · family · {len(names)} UKSI "
                                 "species, accepted names only.")
        else:
            names = self.win.call(self.svc.candidate_names, t["tvk"], t["name"]) or []
            if t.get("uksi_missing"):
                self.matched.setText(f"UKSI is not installed here, so <i>{t['name']}</i> is "
                                     "searched by the name as typed: no synonyms, no spelling "
                                     "check. Add other names yourself if you need them.")
            else:
                self.matched.setText(f"Matched <i>{t['name']}</i>{how} · "
                                     + " · ".join(b for b in bits if b) + "." + others)
        self.matched.setTextFormat(Qt.TextFormat.RichText)
        if not self.name_edit.text().strip():
            self.name_edit.setText(t["name"])
        self.species_edit.setText(t["name"])
        self.names.set_names(names)
        self.update_preview()

    # --- preview ------------------------------------------------------------
    def _schedule_preview(self):
        self._timer.start()

    def update_preview(self, result=None):
        """Preview from BHL's last answers (instant), or show a counted result."""
        if result is None:
            if not self.names.names():
                self._show_preview(None)
                return
            result = self.win.call(self.svc.preview_draft, self.names.names(),
                                   self.filters.filters(), text=self.is_text())
        self._show_preview(result)

    def _show_preview(self, p):
        for key, w in self.preview_values.items():
            w.setText("—" if p is None else f"{p[key]:,}" + (
                " pages" if key == "to_download" else ""))
        if p is None:
            self.preview_note.setText("Find a species to see what a run would fetch.")
            return
        self.names.set_counts(p.get("name_found"))
        note = (f"{S.fmt_seconds(p['est_seconds']).capitalize()} at one request per second "
                f"({p['requests']:,} requests).")
        if self.is_text():
            note = ("Free-text results are whole books and articles: no page text is "
                    "downloaded. " + note)
        if p["not_counted"]:
            note += (f" Not counted yet: {', '.join(p['not_counted'])} — press "
                     "Refresh count to ask BHL.")
        self.preview_note.setText(note)

    def refresh_counts(self):
        if not self.names.names():
            self.win.say("Find a species first.")
            return
        self.win.run_task("Counting names on BHL", self.svc.preview_draft, self.names.names(),
                          self.filters.filters(), use_network=True, text=self.is_text(),
                          on_done=self._counted)

    def _counted(self, result):
        if self.win.current() is self:
            self._show_preview(result)

    # --- save ---------------------------------------------------------------
    def save(self, run=False):
        """Save the search (and run it). Returns the search id, or None."""
        if self.is_text() and self.search_id is None and not self.target:
            self.use_terms()                     # terms typed but "Use terms" not pressed
        if not self.target:
            self.win.say("Type the terms and press Use terms first." if self.is_text()
                         else "Type a species and press Find first.")
            return None
        if not self.names.ticked():
            self.win.say("Tick at least one name to search.")
            return None
        name = " ".join(self.name_edit.text().split()) or self.target["name"]
        if self.is_text() and self.target.get("kind") != "text":
            self.target = dict(self.target, kind="text")
        names, filters = self.names.names(), self.filters.filters()
        if self.search_id is None:
            sid = self.win.call(self.svc.create_search, self.target, name=name,
                                kind=self.target.get("kind", "species"), names=names,
                                filters=filters)
        else:
            sid = self.search_id
            if self.win.call(self.svc.update_search, sid, name=name, filters=filters,
                             names=names) is None:
                sid = None
        if sid is None:
            return None
        if self.names.remember.isChecked() and self.target.get("kind") == "species":
            for n, include in self.names.choices_to_remember():
                self.svc.remember_name_choice(n, include, species=self.target["name"],
                                              reason="chosen in Lector")
        self.search_id = sid
        if run:                    # Back from there skips this editor
            self.win.go("history", replace=True, search_id=sid, run="fetch")
        else:
            self.win.go("searches")
        return sid

"""Search builder, part 2: the names to search, each ticked or held back with its reason."""
from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout)

from Lector.ui import style as S
from Lector.ui.common import clear_layout

ORIGIN_TEXT = {"accepted": "accepted name", "uksi_synonym": "UKSI synonym",
               "user_added": "added by you"}


class NamesPanel(S.Card):
    """names() -> the list to save: [{name, origin, included, held_back_reason, ...}]."""
    changed = Signal()

    def __init__(self):
        super().__init__("2. Names to search")
        self.body.addWidget(S.label(
            "BHL indexes names exactly as printed, so older names find older papers. Each "
            "name is checked before it is used; a name UKSI gives for this species but which "
            "looks wrong is held back (not ticked) with the reason.", "muted", wrap=True))
        self.box = QFrame()
        self.box.setObjectName("namesBox")
        self.box.setStyleSheet(f"QFrame#namesBox {{ border: 1px solid {S.c('border')};"
                               f" border-radius: {S.c('radius_md')}; background: {S.c('surface')}; }}")
        self.rows_layout = QVBoxLayout(self.box)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(0)
        self.body.addWidget(self.box)
        add = QHBoxLayout()
        self.add_edit = QLineEdit()
        self.add_edit.setPlaceholderText("Add a name, e.g. an original combination")
        self.add_edit.returnPressed.connect(self._add_typed)
        add.addWidget(self.add_edit, 1)
        add.addWidget(S.button("Add name", "primary", slot=self._add_typed))
        self.body.addLayout(add)
        self.remember = QCheckBox("Remember my choices for these names in every search "
                                  "of this species")
        self.remember.setToolTip("Writes your ticks and added names to data\\lector_synonyms.txt "
                                 "when you save, so the next search of this species starts "
                                 "with them.")
        self.body.addWidget(self.remember)
        self._names, self._defaults, self._counts, self._checks = [], {}, {}, {}

    # --- state --------------------------------------------------------------
    def set_names(self, names, defaults=None):
        """names: dicts as candidate_names()/get_search(); defaults: {name: included}
        as Lector suggested them (to know which choices to remember)."""
        self._names = [dict(n) for n in names]
        self._defaults = dict(defaults or {n["name"]: n.get("included", True) for n in names})
        self._rebuild()

    def names(self):
        return [dict(n) for n in self._names]

    def ticked(self):
        return [n["name"] for n in self._names if n.get("included", True)]

    def set_counts(self, name_found):
        self._counts.update(name_found or {})
        for n in self._names:
            lab = self._checks.get(n["name"], (None, None))[1]
            if lab is not None:
                lab.setText(self._count_text(n["name"]))

    def choices_to_remember(self):
        """[(name, include)] that differ from what Lector suggested (or were added)."""
        out = []
        for n in self._names:
            default = self._defaults.get(n["name"])
            inc = bool(n.get("included", True))
            if default is None or bool(default) != inc:
                out.append((n["name"], inc))
        return out

    # --- rows -----------------------------------------------------------------
    def _count_text(self, name):
        n = self._counts.get(name)
        return "not counted yet" if n is None else f"{n:,} page{'s' if n != 1 else ''}"

    def _rebuild(self):
        clear_layout(self.rows_layout)
        self._checks = {}
        if not self._names:
            empty = S.label("Find a species first: its names appear here.", "muted")
            empty.setContentsMargins(12, 10, 12, 10)
            self.rows_layout.addWidget(empty)
        for i, n in enumerate(self._names):
            self.rows_layout.addWidget(self._row(i, n))

    def _row(self, i, n):
        row = QFrame()
        row.setObjectName("nameRow")
        held = bool(n.get("held_back_reason"))
        bg = S.c("warning_bg_light") if held and not n.get("included", True) else S.c("surface")
        sep = f"border-top: 1px solid {S.c('separator')};" if i else ""
        row.setStyleSheet(f"QFrame#nameRow {{ background: {bg}; border: none; {sep} }}")
        grid = QHBoxLayout(row)
        grid.setContentsMargins(12, 8, 12, 8)
        check = QCheckBox()
        check.setChecked(bool(n.get("included", True)))
        check.setToolTip("Ticked names are searched on BHL")
        check.toggled.connect(lambda on, name=n["name"]: self._toggle(name, on))
        grid.addWidget(check, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(2)
        origin = ORIGIN_TEXT.get(n.get("origin"), n.get("origin") or "")
        title = QLabel(f"<i>{escape(n['name'])}</i> <span style='color:{S.c('text_secondary')}'>"
                       f"— {escape(origin)}</span>")
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setWordWrap(True)
        title.setStyleSheet("background: transparent; border: none;")
        text.addWidget(title)
        if held:
            reason = S.label(n["held_back_reason"], "warn", wrap=True)
            if n.get("included", True):
                reason.setText(n["held_back_reason"] + " — ticked by you")
            text.addWidget(reason)
        grid.addLayout(text, 1)
        count = S.label(self._count_text(n["name"]), "small")
        count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        grid.addWidget(count, 0, Qt.AlignmentFlag.AlignTop)
        if n.get("origin") == "user_added":
            grid.addWidget(S.button("Remove", "link", "Take this name off the list",
                                    lambda _=False, name=n["name"]: self._remove(name)),
                           0, Qt.AlignmentFlag.AlignTop)
        self._checks[n["name"]] = (check, count)
        return row

    def _toggle(self, name, on):
        for n in self._names:
            if n["name"] == name:
                n["included"] = on
        self._rebuild()
        self.changed.emit()

    def _remove(self, name):
        self._names = [n for n in self._names if n["name"] != name]
        self._rebuild()
        self.changed.emit()

    def add_name(self, name):
        name = " ".join((name or "").split())
        if not name or name.lower() in {n["name"].lower() for n in self._names}:
            return False
        self._names.append({"name": name, "origin": "user_added", "included": True,
                            "held_back_reason": None})
        self._rebuild()
        self.changed.emit()
        return True

    def _add_typed(self):
        if self.add_name(self.add_edit.text()):
            self.add_edit.clear()

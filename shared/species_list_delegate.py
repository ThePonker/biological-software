"""How one row of a species search list is drawn (F49, 12 Oct 2026) -- one look for the
species drop-down lists (Codex's search, Examen's Species Database, Observatum's species
box in Quick Entry / Add Specimen / the import wizards).

Plain text on one line, no boxes: the scientific name in italics, the common name after it
in the secondary colour, then any note ("old name: ...", "close spelling") and the rank of
anything above species ("Genus", "Family") smaller, in the secondary colour. A whole group
found by a common word reads "All <i>Coleoptera</i> (beetles) — group".

The row height comes from the font actually used (QFontMetrics at run time, plus a little
space above and below), never a fixed number of pixels: on Windows a fixed 32 px row or a
squeezed label cut the tails of g, p and y ("Aclypea opaca", "Agabus brunneus").

    from shared.species_list_delegate import SpeciesListDelegate, HIT_ROLE, hit_from_result
    view.setItemDelegate(SpeciesListDelegate(view, secondary="#6b6560"))
    item.setData(HIT_ROLE, hit_from_result(r))         # r: a shared.species_search result
"""
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

HIT_ROLE = Qt.ItemDataRole.UserRole + 40     # the row's dict (see hit_from_result)
_SPECIES_RANKS = {"Species", ""}


def hit_from_result(r: dict, note: str = "", recorded: Optional[bool] = None,
                    family: bool = False) -> dict:
    """The parts of a row, from a shared.species_search result (or a dict shaped like one:
    scientific_name / label, common_name, rank, group_label, old_name, match_type).
    family: show the family too (the record-entry boxes)."""
    if not note:
        note = (f"old name: {r['old_name']}" if r.get("old_name")
                else "close spelling" if r.get("match_type") == "fuzzy" else "")
    rank = r.get("rank") or ""
    return {
        "scientific": r.get("label") or r.get("scientific_name") or "",
        "group_of": r.get("scientific_name") or "",
        "common": r.get("common_name") or "",
        "rank": "" if rank in _SPECIES_RANKS or r.get("group_label") else rank,
        "note": note,
        "group_label": r.get("group_label") or "",
        "recorded": bool(r.get("is_recorded") if recorded is None else recorded),
        "family": (r.get("family") or "") if family else "",
    }


def row_text(hit: dict) -> str:
    """The row as plain text (for tests, tooltips and accessibility)."""
    if hit.get("group_label"):
        return hit["group_label"]
    parts = [hit.get("scientific", ""), hit.get("common", ""), hit.get("family", ""),
             hit.get("note", ""),
             hit.get("rank", ""), "★" if hit.get("recorded") else ""]
    return "  ".join(p for p in parts if p)


class SpeciesListDelegate(QStyledItemDelegate):
    """Draws a row from its HIT_ROLE dict; a row without one is drawn as usual."""

    def __init__(self, parent=None, secondary: Optional[str] = None, role=HIT_ROLE,
                 selected_text: Optional[str] = None):
        """secondary: the colour of common names, notes and ranks. selected_text: the text
        colour of a selected row, for a list whose style sheet gives selected rows a light
        background (a style sheet's ::item:selected colour does not reach a delegate)."""
        super().__init__(parent)
        self.secondary = secondary
        self.role = role
        self.selected_text = selected_text

    # ------------------------------------------------------------ the pieces

    def _fonts(self, option):
        base = QFont(option.font)
        italic = QFont(base)
        italic.setItalic(True)
        small = QFont(base)
        if base.pointSizeF() > 0:
            small.setPointSizeF(max(6.0, base.pointSizeF() * 0.85))
        elif base.pixelSize() > 0:
            small.setPixelSize(max(8, round(base.pixelSize() * 0.85)))
        return base, italic, small

    def _runs(self, hit: dict, option):
        """[(text, font, secondary?)] in order along the row."""
        base, italic, small = self._fonts(option)
        label = hit.get("group_label") or ""
        sci = hit.get("group_of") or hit.get("scientific") or ""
        if label:
            if label.startswith("All ") and sci and sci in label:
                before, after = label.split(sci, 1)
                return [(before, base, False), (sci, italic, False), (after, base, True)]
            return [(label, base, False)]
        runs = [(hit.get("scientific", ""), italic, False)]
        if hit.get("common"):
            runs.append(("  " + hit["common"], base, True))
        if hit.get("family"):
            runs.append(("  · " + hit["family"], base, True))
        if hit.get("note"):
            runs.append(("  — " + hit["note"], small, True))
        if hit.get("rank"):
            runs.append(("  " + hit["rank"], small, True))
        if hit.get("recorded"):
            runs.append(("  ★", base, False))
        return runs

    @staticmethod
    def _pad(option) -> int:
        return max(3, QFontMetrics(option.font).height() // 4)

    # ------------------------------------------------------------ Qt

    def sizeHint(self, option, index):
        hit = index.data(self.role)
        if not isinstance(hit, dict):
            return super().sizeHint(option, index)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        runs = self._runs(hit, opt)
        line = max(QFontMetrics(f).height() for _, f, _ in runs)
        width = sum(QFontMetrics(f).horizontalAdvance(t) for t, f, _ in runs)
        pad = self._pad(opt)
        return QSize(width + 3 * pad, line + 2 * pad)

    def paint(self, painter, option, index):
        hit = index.data(self.role)
        if not isinstance(hit, dict):
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        widget = opt.widget
        style = widget.style() if widget is not None else None
        painter.save()
        if style is not None:      # the row's background (hover, selected, style sheet ::item)
            style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, opt, painter, widget)
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        light = selected and self.selected_text          # a light selected background
        if light:
            text_colour = QColor(self.selected_text)
        else:
            text_colour = (opt.palette.highlightedText() if selected
                           else opt.palette.text()).color()
        if selected and not light:
            second = text_colour                         # on the dark highlight
        else:
            second = (QColor(self.secondary) if self.secondary
                      else opt.palette.placeholderText().color())
        pad = self._pad(opt)
        rect = opt.rect.adjusted(pad * 2, 0, -pad, 0)
        painter.setClipRect(opt.rect)
        runs = self._runs(hit, opt)
        metrics = [QFontMetrics(f) for _, f, _ in runs]
        ascent = max(fm.ascent() for fm in metrics)
        line = max(fm.height() for fm in metrics)
        baseline = rect.top() + (rect.height() - line) // 2 + ascent   # one baseline for all
        x = rect.left()
        for text, font, secondary in runs:
            if not text or x >= rect.right():
                continue
            fm = QFontMetrics(font)
            painter.setFont(font)
            painter.setPen(second if secondary else text_colour)
            w = fm.horizontalAdvance(text)
            shown = text if x + w <= rect.right() else fm.elidedText(
                text, Qt.TextElideMode.ElideRight, rect.right() - x)
            painter.drawText(x, baseline, shown)
            x += w
        painter.restore()


__all__ = ["SpeciesListDelegate", "HIT_ROLE", "hit_from_result", "row_text"]

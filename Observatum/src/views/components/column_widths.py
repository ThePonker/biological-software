"""Column widths that stay put (14 Oct 2026).

The Observation Data and Insect Collection tables saved each column's width under its
position ('col_3'), so a new column (the camera column) shifted every width after it, and a
refill (search, sort) could leave a column at another column's width. Widths are now kept
under the column's key and put back after every refill of the table.

    ColumnWidthKeeper(view, model.get_columns, "observation_table_columns")

`get_columns()` returns [(key, header, default width, ...)] in view order. The old
position-keyed values are read once, for columns that have no key-saved width yet, and kept
under the column's key from then on. The last column (stretched to fill the table) is never
saved or set. Saved widths follow the table text size: when it changes, they are scaled once
(R20, 11 Nov 2026).
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, QTimer

from shared.table_text import scaled_width
from shared.text_sizes import font_px

TEXT_PX_KEY = "_text_px"      # the table text size the saved widths were made at (R20)
PRE_R20_TEXT_PX = 13           # widths saved before R20 were made at 13 px table text


class ColumnWidthKeeper(QObject):
    def __init__(self, view, columns_fn, prefix: str, parent=None):
        super().__init__(parent or view)
        self.view, self.columns_fn, self.prefix = view, columns_fn, prefix
        self._applying = False
        self._models = []
        view.horizontalHeader().sectionResized.connect(self._save)
        self.watch(view.model())

    def watch(self, model) -> None:
        """Put the widths back after this model is reset or re-laid out (call it for the
        source model and the proxy)."""
        if model is None or model in self._models:
            return
        self._models.append(model)
        model.modelReset.connect(self.apply_soon)
        model.layoutChanged.connect(self.apply_soon)

    def _key_value(self, s: QSettings, i: int, key: str, default: int) -> int:
        v = s.value(f"{self.prefix}/{key}", None)
        if v is None and key != 'photos':
            # the older, position-keyed value: read once, then kept under the column's key
            old = s.value(f"{self.prefix}/col_{i}", None)
            try:
                v = int(old) if old is not None and int(old) > 0 else default
            except (TypeError, ValueError):
                v = default
            s.setValue(f"{self.prefix}/{key}", v)
        try:
            v = int(v)
        except (TypeError, ValueError):
            return default
        return v if v > 0 else default

    def _rescale_saved(self, s: QSettings, cols) -> None:
        """When the table text size changed since the widths were saved (R20: 13 -> 14 px),
        widen (or narrow) every saved width in proportion, once, so Wil's columns keep
        showing what they showed instead of cutting the larger text off."""
        now = font_px("small")
        try:
            was = int(s.value(f"{self.prefix}/{TEXT_PX_KEY}", PRE_R20_TEXT_PX))
        except (TypeError, ValueError):
            was = PRE_R20_TEXT_PX
        if was == now or was <= 0:
            return
        for col in cols:
            v = s.value(f"{self.prefix}/{col[0]}", None)
            try:
                v = int(v)
            except (TypeError, ValueError):
                continue
            if v > 0:
                s.setValue(f"{self.prefix}/{col[0]}", round(v * now / was))
        s.setValue(f"{self.prefix}/{TEXT_PX_KEY}", now)

    def apply(self) -> None:
        cols = list(self.columns_fn() or [])
        header = self.view.horizontalHeader()
        s = QSettings()
        self._rescale_saved(s, cols)
        self._applying = True
        try:
            last = header.count() - 1 if header.stretchLastSection() else -1
            for i, col in enumerate(cols):
                if i >= header.count():
                    break
                if i == last:
                    continue
                w = self._key_value(s, i, col[0], scaled_width(col[2]))
                if self.view.columnWidth(i) != w:
                    self.view.setColumnWidth(i, w)
        finally:
            self._applying = False

    def apply_soon(self, *args) -> None:
        QTimer.singleShot(0, self.apply)

    def _save(self, logical_index: int, _old: int, new_size: int) -> None:
        if self._applying or new_size <= 0:
            return
        header = self.view.horizontalHeader()
        if header.stretchLastSection() and logical_index == header.count() - 1:
            return                     # the last column is stretched to fill: not Wil's width
        cols = list(self.columns_fn() or [])
        if 0 <= logical_index < len(cols):
            QSettings().setValue(f"{self.prefix}/{cols[logical_index][0]}", new_size)


__all__ = ["ColumnWidthKeeper"]

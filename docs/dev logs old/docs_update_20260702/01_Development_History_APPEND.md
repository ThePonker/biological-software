### Session 27 (July–August 2026) — Data Entry View build ⚠️ UNDOCUMENTED

The Data Entry View moved from design (`26_Data_Entry_Design.md`) to running code during
this period, across chats that were not logged into these docs. Evidenced at launch by
`[DataEntry] go-live backup written: data/_backups/observatum_prelive_<stamp>.db`, and by
in-grid work on Enter-key navigation (Enter now commits a cell and moves to the Species
column of the next row, intercepted at the editor's `eventFilter` via
`move_down_from_editor()` rather than the table's `keyPressEvent`).

**This entry is a placeholder.** Fill in from your own notes: which build steps of §7 in
`26_Data_Entry_Design.md` are complete, what the go-live backup mechanism does, and what
remains before the view is considered delivered.

### Session 28 (27 Aug 2026) — Observations tab: Delete Selected + two latent bugs

- **Delete Selected** added to the Observations tab: `delete_selected_requested` signal,
  red-outlined toolbar button, `_on_delete_selected()` handler acting on checked rows with
  a count-naming confirmation dialog, then clear-checks and reload. Enabling logic added
  to both branches of `set_selected_count()`.
- **`_mark_as_commercial` fixed**: `sorted(self.table_model._checked, QMessageBox)` passed
  `QMessageBox` as the sort key — a guaranteed `TypeError`. Latent, never triggered.
- **Toolbar mojibake repaired**: `observation_toolbar.py` held double-encoded `â–´` /
  `â–¾` / `â€¢` for `▴` / `▾` / `•` on five lines, rendering visibly in the UI. Corruption
  was on disk, confirmed against the intact sibling toolbars; file rewritten UTF-8 without
  BOM.
- **Rule captured**: PowerShell 5's `-Encoding UTF8` writes a BOM and corrupts Python
  source for direct-text tooling — use `[IO.File]::WriteAllText(..., UTF8Encoding $false)`.
- **Left open**: 9 source files still carry a UTF-8 BOM (Infrastructure item 32).

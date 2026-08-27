## Session 28 Additions (27 August 2026)

### 32. UTF-8 BOM on 9 Source Files — OPEN (low priority)

Nine files under `Observatum/src/` begin with a UTF-8 BOM (`EF BB BF`):
`models/database.py`, `repositories/uksi_repository.py`,
`services/recording_scheme_stats_service.py`, `views/dialogs/species_list_dialog.py`,
`views/scheme/recording_scheme_tab.py`, `views/scheme/scheme_record_model.py`,
`views/stats/scheme_dashboard.py`, `views/stats/species_dashboard.py`,
`views/stats/stat_widgets.py`.

Harmless to normal imports — Python 3 strips a leading BOM. It *does* break direct text
reads (`ast.parse`, lint/format tooling, any `open(...).read()` parse) with
`SyntaxError: invalid non-printable character U+FEFF`, and it shows as a spurious diff
when a file is rewritten.

**Detect:**
```powershell
Get-ChildItem Observatum\src -Recurse -Filter *.py | ForEach-Object {
  $b = [IO.File]::ReadAllBytes($_.FullName)
  if ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF) { $_.FullName }
}
```

**Action:** strip in one commit. See rule 33 to avoid re-introducing them.

---

### 33. PowerShell `-Encoding UTF8` Writes a BOM — RULE (Session 28 lesson)

In Windows PowerShell 5.1, `Set-Content` / `Add-Content` / `Out-File` with
`-Encoding UTF8` write **UTF-8 with BOM**. Editing a Python file this way inserts
`U+FEFF` at the top and breaks direct-text parsing (see item 32). PowerShell 7's
`-Encoding utf8NoBOM` is correct but is not what runs by default here.

**Always write source files with:**
```powershell
[IO.File]::WriteAllText($path, $text, (New-Object Text.UTF8Encoding $false))
```

Related trap: `$text.Replace([char]0xE2 + [char]0x2013, [char]0x25B4)` resolves to the
single-`char` overload of `Replace` and throws. Build multi-character patterns as
explicit `[string]` variables first, then call `Replace($old, $new)`.

This sits alongside the existing **VBA Encoding Rule** (Session 23) — same class of
problem, different runtime.

---

### 34. Observations Toolbar Mojibake — FIXED (Session 28)

`views/observations/observation_toolbar.py` held double-encoded literals on lines
45, 117, 226, 278, 286: `â–´` / `â–¾` / `â€¢` where `▴` (U+25B4) / `▾` (U+25BE) /
`•` (U+2022) were intended. The UI showed `â–´ Hide Filters` and
`23866 records â€¢ 3072 species`.

Diagnosed as corruption **on disk**, not a display fault, by comparing against
`collection_toolbar.py` and `scheme_toolbar.py`, which carry the same glyphs intact.
Cause: a past read-as-UTF-8 / write-as-cp1252 round trip on that one file.

Repaired by targeted replacement; file rewritten UTF-8 without BOM. **If any other file
develops the same symptom, the sibling toolbars are the reference for the correct
glyphs.**

---

### 35. `_mark_as_commercial` `sorted()` Key Bug — FIXED (Session 28)

`views/observations/observation_tab.py` (~line 577):

```python
for row_idx in sorted(self.table_model._checked, QMessageBox):
```

`sorted()`'s second positional argument is `key`, so `QMessageBox` was passed as the sort
key function — a guaranteed `TypeError` the first time Mark as Commercial was used.
Latent dead-on-arrival code, never triggered in the field. Second argument removed.

Same class as item 26 (`mark_synced()` column mismatch): a code path that had never been
exercised. **Worth a pass over other rarely-used toolbar actions for the same pattern.**

---

### 36. Delete Selected — DELIVERED (Session 28)

Observations tab now has a Delete Selected action following the existing
signal → toolbar button → tab handler pattern. Operates on **checked** rows via
`table_model.get_checked_observations()`, confirms with a count-naming warning dialog,
deletes via `db.execute_main_write()`, then clears checks and reloads.

Note: `ObservationRepository.delete_many(ids)` already exists and is the tidier call, but
the handler mirrors the sibling `_mark_as_commercial` write path instead, since
`self._obs_repo` availability on the tab was not verified. Swap it in if confirmed.

Build lesson: new toolbar buttons constructed with `setEnabled(False)` must also be added
to **both** branches of `set_selected_count()`, or they stay permanently greyed and
swallow clicks silently with no error.

# Field Entry App v3.0

Lightweight standalone tool for field data entry with UKSI species autocomplete.

## Features

### Data Entry
- **Species Autocomplete** - Type 2+ characters to search UKSI
  - Searches scientific names, common names, and synonyms
  - Old names shown as "OldName → PreferredName"
  - Genus search: type "Bembidion" to see all Bembidion species
  - Family search: type "Cerambycidae" for all longhorn beetles
- **Auto-population** - TVK, Common Name, Family, Order filled automatically
- **Grid Reference Validation** - Invalid refs highlighted in red
- **Vice County Lookup** - Auto-populated from valid grid reference
- **Quick Fill** - Compact bar for bulk applying Date, Location, Recorder etc.
- **1000 Rows on Startup** - Ready for rapid data entry

### Excel-like Editing
| Shortcut | Action |
|----------|--------|
| Ctrl+C | Copy |
| Ctrl+X | Cut |
| Ctrl+V | Paste (multi-cell) |
| Ctrl+Z | Undo |
| Ctrl+Y | Redo |
| Ctrl+D | Fill down |
| Ctrl+Shift+D | Duplicate row |
| Ctrl+I | Insert row |
| Delete | Clear selection |
| F2 | Edit cell |
| Tab | Next cell |
| Ctrl+F | Find |
| Ctrl+H | Find & Replace |
| Ctrl+Enter | Apply Quick Fill |

### File Operations
- **Import CSV** - Auto-detects iRecord column format
- **Export CSV** - Exports in iRecord-compatible format
- **Auto-Save** - Periodic save to recovery file (every 60s)
- **Crash Recovery** - Prompts to restore on startup if recovery exists

### Column Management
- **Show/Hide Columns** - Toggle visibility of any column
- **Hide Auto-Filled** - Quick button to hide TVK, Family, Order, etc.
- **Persistent** - Settings saved between sessions

### Settings (Persisted)
- Default Recorder and Determiner names
- Certainty defaults to "Certain"
- Data Type defaults to "Personal"
- Column visibility
- Settings saved to `data/field_entry_settings.json`

## Running

Double-click `field_entry.bat` or run:

```powershell
python -m scripts.field_entry.main
```

## Requirements

- Python 3.10+
- PySide6
- data/uksi.db (species database)
- data/vc_lookup.db (vice county lookup)

---

## Current Columns (v3.0)

| Column | Editable | Auto | Sticky | Notes |
|--------|:--------:|:----:|:------:|-------|
| Species | ✓ | | ✓ | Autocomplete from UKSI |
| TVK | | ✓ | | TaxonVersionKey (can hide) |
| Common Name | | ✓ | | From UKSI (can hide) |
| Family | | ✓ | | From UKSI (can hide) |
| Order | | ✓ | | From UKSI (can hide) |
| Date | ✓ | | ✓ | YYYY-MM-DD (defaults to today) |
| Grid Ref | ✓ | | ✓ | Validates format |
| Vice County | | ✓ | | From grid ref (can hide) |
| Location | ✓ | | ✓ | Site name |
| Qty | ✓ | | ✓ | Default: 1 |
| Sex | ✓ | | ✓ | Dropdown |
| Stage | ✓ | | ✓ | Dropdown |
| Method | ✓ | | ✓ | Updated iRecord termlist |
| Certainty | ✓ | | ✓ | Default: Certain |
| Recorder | ✓ | | ✓ | From settings |
| Determiner | ✓ | | ✓ | From settings |
| Comment | ✓ | | ✓ | Notes |
| Data Type | ✓ | | ✓ | Personal/Commercial |
| Never Upload | ✓ | | ✓ | Exclude from iRecord |

---

# Development Complete

## ✅ All Phases Complete (v3.0)

### Phase 1 - Core Features
- [x] Species autocomplete from UKSI
- [x] Auto-population of taxonomy fields
- [x] Grid reference validation
- [x] Vice county auto-lookup
- [x] Copy/paste/undo/redo
- [x] CSV import/export

### Phase 2 - UI/UX Improvements
- [x] Quick Fill bar with Clear button
- [x] Compact layout
- [x] 1000 empty rows on startup
- [x] Certainty defaults to "Certain"
- [x] Settings for default Recorder/Determiner

### Phase 3 - Column & Field Updates
- [x] Removed "Observation Type" column
- [x] Updated Method termlist to match iRecord
- [x] "Never Upload" wording fixed
- [x] Added Data Type column (Personal/Commercial)

### Phase 4 - Species Search Enhancements
- [x] Synonym search with "OldName → PreferredName"
- [x] Genus-level search
- [x] Family-level search

### Phase 5 - Advanced Features
- [x] Find & Replace dialog (Ctrl+H)
- [x] Column visibility management
- [x] Auto-save with crash recovery
- [x] Recovery file detection on startup

---

## Workflow

1. App opens with 1000 rows ready (or recovery prompt if crashed)
2. Set Quick Fill defaults (Date, Location, Grid Ref, Recorder)
3. Type species name → select from autocomplete → taxonomy auto-fills
4. Tab through to fill other fields
5. Grid ref auto-validates and looks up Vice County
6. Data auto-saves every 60 seconds
7. Export CSV when done (clears recovery file)
8. Import CSV into Observatum via Import Wizard

## Files

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 30 | Package init |
| `main.py` | 125 | Entry point |
| `settings.py` | 165 | Persistent settings |
| `constants.py` | 225 | Column definitions |
| `uksi_lookup.py` | 372 | Species search |
| `vc_lookup.py` | 193 | Vice county lookup |
| `grid_ref.py` | 213 | Grid ref validation |
| `delegates.py` | 313 | Cell editors |
| `undo_manager.py` | 199 | Undo/redo |
| `table_operations_mixin.py` | 435 | Row/cell operations |
| `table.py` | 470 | Main table |
| `csv_handler.py` | 258 | CSV import/export |
| `find_dialog.py` | 192 | Find dialog |
| `find_replace_dialog.py` | 170 | Find & Replace |
| `column_dialog.py` | 175 | Column management |
| `auto_save.py` | 135 | Auto-save/recovery |
| `window_helpers.py` | 344 | Quick Fill bar |
| `window.py` | 380 | Main window |

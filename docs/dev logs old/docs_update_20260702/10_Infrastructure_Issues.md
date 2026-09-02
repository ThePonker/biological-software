# Biological Software — Infrastructure Issues

## Date: 25 March 2026 (Session 23)

---

## Identified Issues

### 1. Build Order Dependency (Codex → Pantheon)
**Status**: Noted — low priority (Pantheon is effectively static)
**Issue**: Codex depends on pantheon.db for SQS scores and TVK bridge. If Pantheon is rebuilt, Codex must be rebuilt after.
**Realistic scenario**: Only JNCC spreadsheet updates trigger a Codex rebuild. Pantheon data is from 2017, unlikely to update. If NHM releases new UKSI TVKs, the chain is UKSI → Pantheon → Codex.
**Action**: Create `rebuild_codex.bat` that runs `build_codex_db.py` then `seed_codex.py`. Add note to Codex spec about when to rebuild UKSI first.

### 2. Examen Depends on Observatum/src/ Code
**Status**: Noted — address when building Examen views
**Issue**: `CodexRepository`, `PantheonRepository`, and `PantheonAnalysisService` live in `Observatum/src/`. Examen reaches them via PYTHONPATH.
**Impact**: Examen cannot be distributed without shipping Observatum's src/ directory.
**Action**: Extract shared repositories and services to a `shared/` directory at project root. Do this when actively building Examen views.

### 3. Manual Codex Entries Not Portable
**Status**: ✅ Fixed (Session 24 — parallel bot wrote manual_entry_dialog.py with JSON storage)
**Issue**: Manual entries (from species reviews not in JNCC) are hardcoded in `seed_codex.py`. Not user-friendly, not portable.
**Action**: Move to `data/codex_manual_entries.json`. Build script auto-loads. Examen Species Database view provides GUI editor that writes to the same JSON.

### 4. UKSI.mdb Path Not in paths.py
**Status**: Noted — trivial fix
**Issue**: The UKSI Access file is outside the project (moved to save 781 MB OneDrive sync). Extractor script hardcodes its location.
**Action**: Add `UKSI_MDB` constant to paths.py.

### 5. build_pantheon_db.py Location Unknown
**Status**: Noted — check backups
**Issue**: Was at project root pre-restructure, not found during migration. May have been lost during cleanup.
**Action**: Search backups. If lost, can be reconstructed from the NERC data download instructions.

### 6. paths.py Single Point of Failure
**Status**: ✅ Mitigated
**Issue**: Every project depends on paths.py. Deletion breaks everything.
**Actions taken**: Permanent banner added to file header. `run.bat` checks for existence before launching.

### 7. Database Backup for examen.db and munia.db
**Status**: Noted — address when building Examen / extending backup system
**Issue**: Both `examen.db` (frozen assessments) and `munia.db` (project allocations, day logs) accumulate irreplaceable user data. No backup mechanism beyond OneDrive passive version history.
**Existing**: Observatum has backup-on-close prompt and settings panel options.
**Action**: Include both databases in Observatum's backup mechanism, or add backup to each app independently.

### 8. Concurrent Database Access
**Status**: ✅ Mitigated
**Issue**: Observatum writing during import while Examen reads from same observatum.db.
**Actions taken**: WAL mode handles multiple readers + one writer. All Examen connections use `PRAGMA query_only = ON` (3 connections patched).

### 9. Tabella Generator Location
**Status**: ✅ Fixed (Session 22)
**Action taken**: Moved `create_data_entry_workbook.py` into `Tabella/`. Launcher updated.

### 10. Tabella VBA Macro Missing
**Status**: ✅ Fixed (Session 23)
**Issue**: Workbook generator created .xlsx with empty auto-populate columns. VBA macro was referenced in instructions but never written.
**Actions taken**: Complete DataEntry VBA module written (`vba_source.py`). Merged `build_xlsm.py` into the generator for single-script pipeline. VBA uses header-driven column lookup with cache invalidation — entry sheet columns freely reorderable. Pure ASCII encoding with explicit CRLF to avoid VBA editor corruption.

### 11. Broken Reset Launchers (6 files)
**Status**: ✅ Fixed (Session 23)
**Issue**: `reset.bat`, `reset_insect_collection.bat`, `reset_observations.bat`, `reset_observations_commercial.bat`, `reset_observations_personal.bat`, `reset_recording_scheme.bat` all had orphaned `) else (` blocks with no matching `if` statement. Would error when run.
**Action taken**: Stripped to working `python scripts/...` calls. All headings updated from "Observatum V2" to "Biological Software".

### 12. Game.bat Orphaned
**Status**: Noted — check if target exists
**Issue**: `launchers/Game.bat` points to `Observatum\src\features\gamification\game_launcher.py`. Gamification is listed as "not implemented, Winter 2026". Target may not exist.
**Action**: Verify whether `game_launcher.py` exists. If not, delete `Game.bat`.

### 13. MUNIA_DB Not in paths.py
**Status**: Noted — trivial fix
**Issue**: Munia's `munia_data.py` derives the path from `DATA_DIR` as a fallback. Works, but inconsistent with other `*_DB` constants.
**Action**: Add `MUNIA_DB = DATA_DIR / "munia.db"` to paths.py.

---

## Schema Change Rule (Session 22 Lesson)

When adding columns to multi-table reset scripts, always run a **per-table audit** — not a whole-file search. The audit must extract each CREATE TABLE statement independently and verify the column exists within that specific block.

Session 21's audit reported "ALL OK" because `superfamily` appeared in the observations CREATE TABLE, but was missing from the specimens and recording_scheme CREATE TABLE statements in the same file. This caused import failures (table has no column named superfamily) that were only caught during the definitive import test.

---

## VBA Encoding Rule (Session 23 Lesson)

VBA code injected via `AddFromString` must be pure ASCII with explicit `\r\n` line endings:
- No em-dashes (`—`) or other non-ASCII characters — VBA editor is ANSI, multi-byte UTF-8 corrupts
- No `Attribute VB_Name` line — valid in .bas imports but causes compile error via programmatic injection
- Store as concatenated Python string literals with `\r\n`, not triple-quoted blocks
- `Select Case` with `Case "X", "Y": Exit Sub` may need splitting across two lines depending on injection method


### 14. Shared Library — COMPLETED
CodexRepository, PantheonRepository, PantheonAnalysisService in shared/. Re-export stubs. db_config.py for standalone packaging.

### 15. Rebuild Procedures — DOCUMENTED
See 23_Rebuild_Procedures.md. UKSI→Pantheon→Codex chain.

### 16. Atrium Redesign — COMPLETED
Tinted icons, pin toggle, taskbar, auto-delete workbooks, pythonw launcher.

### 17. Species Search Rewrite — COMPLETED (Session 25)
QCompleter replaced with manual QListWidget popup. Arrow keys, Enter, Tab, Escape, mouse click all handled directly. ToolTip window flag prevents focus steal. OneDrive file lock required delete-and-rewrite workaround.

### 18. Specimen Date Migration — COMPLETED (Session 25)
All 2,454 specimen dates converted from DD/MM/YYYY to YYYY-MM-DD (ISO). IC and RS table sort proxies updated to convert display dates to ISO for sort keys. All display dates now flow through settings-aware format_date_display utility.

### 19. Observation Edit Lock — FIXED (Session 25)
Changed from checking `irecord_id OR record_key` to only `irecord_id`. Records without iRecord ID are now editable. New EditObservationDialog built and wired.

### 20. CSV Backup — FIXED (Session 25)
Changed from `if self._data_changed` to always offer backup. Added `recording_scheme` to backup tables.

### 21. Tabella Pending Records System — COMPLETED (Session 25)
`refresh_records.py` enhanced to scan Active Record Books folder for un-imported workbook entries. VBA updated to count own-workbook entries (file lock workaround) and display pending alongside confirmed counts. Generator updated with new VBA + 8-column Records sheet. Active folder: `~\OneDrive\Active Record Books`. Lifecycle: generate → copy to active folder → rename per site → field season → import → move out.

### 22. Tabella Sheet Protection — PENDING (Next Session)
Lock auto-populated columns (Conservation, Red List, TVK, Common Name, etc.) to prevent accidental edits. Use `UserInterfaceOnly:=True` so VBA can still write. Update generator + 3 existing workbooks.

### 23. Active Record Books Path — PENDING (Next Session)
Currently hardcoded in `refresh_records.py`. Move to Observatum Settings panel for user configuration.

### 24. Observatum Data Entry View — DESIGNED (Winter)
MapMate-style grid entry within Observatum. Saves directly to observatum.db. Species search, auto-populate, protected fields, keyboard-driven. Replaces Excel for desk-based data entry. **Now fully designed** — see `25_Data_Entry_Research.md` and `26_Data_Entry_Design.md`. Schema prerequisite (3 columns) done. Revised estimate 4–6 days, Phase 3b winter.

---

## Session 25–26 Additions (2 July 2026 reconciliation)

### 25. Observation Edit `update()` Signature — FIXED (Session 25)
`ObservationRepository.update()` expects an `Observation` object, but `observation_detail_mixin.py` was calling `update(record_id, obs_data)` → *"takes 2 positional arguments but 3 were given"* when editing dates on commercial records. Fixed with a direct SQL `UPDATE` (allowed-column whitelist) in the mixin. Mis-dated commercial rows (`2026-07-10` → 2025) corrected via the now-working dialog.

### 26. `mark_synced()` Column Mismatch — FIXED (Session 25)
`observation_repository.py` `mark_synced()` wrote `synced_at`; schema column is `last_synced`. Dead code (no caller on any sync path) but a latent crash if ever invoked. Renamed `synced_at` → `last_synced`.

### 27. Tabella `refresh_records.py` Double-Count + Name Lookup — FIXED (Session 25)
Two issues, one fix: (a) `_scan_workbooks` scanned every `.xlsm` including the calling workbook, which VBA `CountOwnPending` also counted → non-deterministic inflated pending counts; (b) `_build_name_to_tvk` keyed on `scientific_name` so aggregates / `s.l.` / `s.s.` entries silently failed to match. Fix: `refresh_records.py` now reads the workbook **TVK column** (already VBA-populated) and honours `--skip <path>`; VBA `RefreshRecords` passes `ThisWorkbook.FullName` as `--skip`. `_build_name_to_tvk` redundant.

### 28. iRecord `irecord_id` Nulled on Update — FIXED (Session 25)
Sync update path was nulling `irecord_id`. Permanent fix in `wizard_import_mixin.py`; 180 IDs recovered, 295 new personal records imported cleanly. Post-recovery audit matched exactly (Commercial 1,178 / Personal 18,758 with irecord_id).

### 29. Phase 0 Hygiene — DONE (Session 26)
Git (`main` + `stable`, `.gitignore`); WAL checkpoint on Observatum close; examen.db + munia.db backup-on-close; `MUNIA_DB` in paths.py (closes Issue 13). Known friction: OneDrive locks `.git/objects` during `gc` — pause sync / `taskkill OneDrive.exe`.

### 30. Mixed Line Endings — NOTED (low priority)
`observation_repository.py` is LF; `wizard_import_mixin.py` / `vba_source.py` are CRLF. Confuses Git diffs when auto-CRLF flips. Normalise via `.gitattributes` if it becomes noisy. Not blocking.

### 31. Future-Dated Commercial Record — OPEN
One commercial row dated `2026-07-10`. Could be a scheduled survey or a typo (Session 25 fixed eight 2027→2026 typos). Eyeball and one-line `UPDATE` if wrong.

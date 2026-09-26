# Biological Software — Complete Development History

## Updated 29 August 2026 (through Session 29)

## Project Overview

**Biological Software** is a suite of Latin-themed tools for naturalist field recording and
invertebrate survey reporting, built with Python/PySide6/SQLite, following a Victorian
naturalist theme. Sole developer: Wil Heeney, trading as Flauna.

### The Software Suite

| Name | Purpose | Status |
|------|---------|--------|
| **Observatum** | Main recording app — observations, specimens, recording scheme, **Data Entry** | Active; Data Entry now in production use |
| **Examen** | Invertebrate assemblage assessment (Pantheon replacement) | Desktop retired 16 Apr 2026; desktop rebuild is the next major build |
| **Codex** | Conservation manager GUI + database pipeline | 11-track, biodiversity-wide, clean baseline |
| **Curator** | Insect collection organiser | Built |
| **Tabella** | Field workbook generator (Excel+VBA) + runtime app | v2. **Development paused Aug 2026** — superseded by Data Entry |
| **Munia** | Capacity planner | v2, MUNIA_DB registered |
| **Atrium** | Suite launcher (system tray) | Built (4 apps + 2 tools) |

---

## Session 24 (25–26 Mar 2026) — Import Pipeline, RS Integration, Multi-Bot

**Observatum fixes (17 items):** specimen enrichment root cause (`uksi_conn` →
`uksi_model`); subfamily parent-chain lookup; import-notes combine on all 3 wizards; RS
stats cache invalidation + refresh; RS export wired; VC lookup fix + recovery (94.5% →
99.2%); Species Match Report on all wizards; persistent Resolve Species button; stats
refresh after import.

**Parallel bot:** Examen polish; Curator (Hemiptera sort, Coleoptera suborder grouping);
Atrium system-tray launcher.

## Session 25 (28 Apr – May 2026) — Field-Season Fixes + Codex Widening

**Field fixes:** species search rewritten (QCompleter → QListWidget popup, full keyboard
control); specimen editing end-to-end; all 2,454 specimen dates migrated to ISO;
EditObservationDialog built, edit lock narrowed to `irecord_id`; CSV backup always offered;
Atrium polish; Tabella pending-records system.

**iRecord recovery (≈9 May):** sync audit closed clean. `irecord_id`-nulling bug found and
fixed in `wizard_import_mixin.py`; 295 new personal records imported, 180 IDs preserved.
`refresh_records.py` rewritten to read the TVK column and honour `--skip`. `mark_synced()`
column mismatch fixed.

**Codex 11-track widening (Apr):** rebuilt biodiversity-wide for conservation,
invertebrate-only for SQS. 14,395 species / 11 tracks. Cleanup: 109 zero-SQS + 6,231
non-invertebrate collisions removed; build script patched so rebuilds stay clean.

## Session 26 (June 2026) — Phase 0 Hygiene, Strategy, Data Entry Design

- **Phase 0 hygiene:** Git initialised (`main` + `stable`); WAL checkpoint on close;
  examen.db + munia.db added to backup-on-close; `MUNIA_DB` added to `paths.py`.
- **Data integrity:** `sub_location`, `trap_number`, `visit_number` added to `observations`;
  taxonomy refresh diagnostic — 30 records / 3 stale TVKs resolved.
- **UKSI extractor v5:** English-only common names, sort_code/sort_order, `preferred` flag.
- **Strategy:** evolve-don't-rewrite; Examen desktop-first; frozen-report-as-record; UKSI
  confirmed CC BY 4.0.
- **Design:** Data Entry View researched (`25`) and designed (`26`).

## Session 27 (July–August 2026) — Data Entry View build ⚠️ PARTIALLY DOCUMENTED

The Data Entry View moved from design to running code across chats that were not logged.
What is evidenced from the code and from later sessions:

- `DataEntry/` built as a drop-in package with 23 modules — staging repo, entry grid,
  session header, commit and write services, jobs list, info panel, three map widgets,
  theme, bootstrap, embed, standalone `__main__`.
- **Staging model**: `entry_jobs` + `entry_staging` tables in observatum.db. Typing writes
  through immediately; commit is a separate deliberate act.
- **Preview / go-live split** in `embed.py` — preview points at a dev copy with commit
  disabled; go-live points at observatum.db and takes a pre-live `.db` snapshot first.
  Observatum's main window calls it with `go_live=True`.
- **Maps**: raster OS-tile mini map, vector VC-outline fallback, and a GB distribution map
  with per-source legend toggles, built from martinjc/UK-GeoJSON reprojected.
- **Enter-key navigation** fixed to commit a cell and move to the Species column of the next
  row, intercepted at the editor's `eventFilter`.
- Naturalist-theme restyle; pan/zoom mixin; "This workbook" summary card.

**Still to fill in from Wil's notes:** which of the seven build steps in
`26_Data_Entry_Design.md` §7 were completed, and in what order.

## Session 28 (27 Aug 2026) — Observations tab, encoding, workbook migration

**Observations tab:** Delete Selected delivered; `_mark_as_commercial`
`sorted(..., QMessageBox)` crash fixed; toolbar mojibake repaired.

**Encoding:** 9 UTF-8 BOMs stripped. Rule captured — PowerShell 5's `-Encoding UTF8` writes
a BOM.

**UKSI common names ⭐ — the session's most valuable find.**
`_get_preferred_common_name()`'s GLOB filter ended `...ŵŷwy`; the bare `w`/`y` excluded
**7,997 of 20,897** common names instead of the 22 accented ones intended. The filter was
then found obsolete entirely and replaced with `ORDER BY preferred DESC` against UKSI's own
flag.

**Workbook migration:** `scripts/load_workbook_to_staging.py` written; **11 Tabella
workbooks / 1,787 records** loaded as staging jobs 3–13. Commit batch stamping added, with
`scripts/entry_batches.py` to list and undo.

**Grid:** copy marker, paste-to-selection, VC No. column, individuals total, per-order
breakdown as distinct species with record counts.

## Session 29 (28–29 Aug 2026) — Data safety, grid features, Insect Collection

**Data safety:** durability confirmed (WAL + `synchronous=FULL`, per-edit commits).
`DataEntry/csv_backup.py` added — rolling staging and observations CSVs outside OneDrive.
Pre-live snapshots pruned from **3.9 GB / 35 files** to a rolling 2.

**Grid:** taxon columns; click-header sorting with entry-order restore; row insert/delete;
Traps card; default column order; header state guarded against column changes; VC always
derived from grid ref; pending counts widened across all jobs.

**Insect Collection:** Add Specimen rebuilt two-column with a location map; Local Site Name
removed from the dialog; Collector/Determiner defaults from Settings; curatorial fields
added with taxon-based prep-type defaults.

**Date audit:** storage confirmed ISO throughout; one hardcoded display format fixed.

---

## Performance Metrics (from the optimisation pass)

| Operation | Before | After |
|-----------|--------|-------|
| Total startup | 16.5s | 3.6s |
| Stats switching | 6.5s | 0.000s |
| Scheme stats | 2.6s | 0.026s |
| Column sort | 5+ sec | 0.018s |
| RS enrichment (79k rows) | Hung at 29% | Completes in seconds |

## Remaining Work

See `28_Development_Backlog.md` for the itemised list and `24_Phase_Plan.md` for the
strategic sequence.

# Biological Software — Suite Overview

## Date: 25 March 2026

---

## The Suite

Six Latin-themed tools for naturalist field recording and invertebrate survey reporting, plus Atrium launcher, sharing a common database layer via `paths.py`.

| Name | Latin Meaning | Type | Purpose | Status |
|------|--------------|------|---------|--------|
| **Observatum** | "That which has been observed" | Main app | Biological recording — observations, specimens, recording scheme | Active |
| **Examen** | "Examination / Swarm of bees" | Standalone app | Species assessment tool (Pantheon replacement) | Three-view shell built, wiring pending |
| **Codex** | "Book of law" | Database + pipeline | Conservation authority — statuses, SQS, TVK bridge | Built |
| **Curator** | "The one who takes care" | Standalone app | Insect collection organiser — box planning, labels | Built |
| **Tabella** | "Writing tablet" | Generator + app | Field data entry workbook (Excel+VBA) + runtime data entry | Built — VBA macro complete |
| **Munia** | "Duties / obligations" | Standalone app | Workload capacity manager | Built |

---

## Observatum

The main biological recording desktop application. Manages three core data types across tabbed views with import wizards, stats dashboards, embargo management, and iRecord integration.

**Tabs**: Observations, Insect Collection, Recording Scheme, Mapping (in progress), Stats, Settings

**Key features**: Three import wizards with UKSI validation and enrichment. Filter Wizard on all tabs. Embargo system for commercial data. Taxonomic sidebar on IC tab. iRecord sync with commercial field preservation.

**Databases used**: observatum.db, uksi.db, gamification.db (+ codex.db and pantheon.db for future display integration)

**Launcher**: `run.bat` or `$env:PYTHONPATH = "$PWD;$PWD\Observatum"; python -m src.main`

---

## Examen

Standalone species assessment tool replacing the online Pantheon website. One application with three views.

**Species Database view**: Browse and edit Codex conservation statuses + Pantheon ecology data (habitats, guilds, SATs, associations). Search by species name. Manual entry editor for adding statuses from published reviews.

**Site Analysis view**: Load a species list (from Observatum commercial observations or paste/import directly). Computes: key species %, SQI, habitat breakdowns, SAT representation, guild composition. Compare Codex Full vs Pantheon Only modes. Taxonomic sort on all outputs. Export analysis report and species appendix. Freeze assessment for reports.

**Assessment Archive view**: Browse all frozen assessments by site, project, client, year. Compare sites. Pull up historical figures exactly as reported. The frozen record stands even when Codex updates.

**Databases used**: codex.db, pantheon.db, examen.db (frozen assessments), optionally observatum.db (commercial observations)

**Launcher**: `launchers\run_examen.bat` or `python -m Examen`

**Current state**: Three-view shell built and themed (Session 22). Live query wiring pending.

---

## Codex Manager + Database

Standalone GUI (8 files, 4 tabs) for browsing species conservation status, importing reviews, and managing data. 7,612 species, 3 reviews imported. Launcher: `python -m Codex`

### Database
The conservation and scoring authority database. Not a user-facing application — it's infrastructure that Examen and Observatum query.

**What it stores**:
- Conservation designations across 8 status tracks (GB red list, GB rarity, Section 41, legal protection, etc.) from JNCC Dec 2023 spreadsheet
- SQS scores re-keyed from Pantheon to current UKSI TVKs, plus 1,314 derived scores
- TVK bridge mapping 2,513 old Pantheon TVKs to current UKSI TVKs
- Manual entries that survive rebuilds (for statuses from reviews not yet in JNCC)

**Build pipeline**: `scripts/build_codex_db.py` (JNCC → codex.db), `scripts/seed_codex.py` (manual entries + SQS gap-fill)

**Key consumers**: Examen (all three views), Observatum (species profiles, stats, exports — pending integration)

**User editing**: Currently via seed script. GUI editor planned as part of Examen's Species Database view.

---

## Curator

Standalone PySide6 tool for planning the physical layout of an insect collection. Reads specimen data from observatum.db and taxonomy from uksi.db.

**Features**: Mounting profile selection (micro, side, standard, spread, large). Family-to-box allocation with growth allowance. Superfamily boundary-aware splitting. Printable labels and box layout PDF export.

**Databases used**: observatum.db (read-only), uksi.db (read-only)

**Launcher**: `launchers\run_curator.bat` or `python -m Curator`

---

## Tabella

Two components: a workbook generator and a runtime data entry application.

### Workbook Generator
Creates a macro-enabled Excel workbook (.xlsm) for field data entry. The VBA macro auto-populates conservation and taxonomy fields when a species name is typed. Completed workbooks are imported back into Observatum via the import wizards.

**The data pipeline**: UKSI + Codex → Tabella generator → .xlsm workbook → fieldwork → completed workbook → Observatum import wizard

**VBA macro features**:
- Exact match via Application.Match (instant on ~140k species)
- Fuzzy search — type partial names (e.g. "rut mac" for Rutpela maculata)
- Numbered picker dialog for multiple matches (shows species, common name, family)
- Auto-populates 12 columns: Conservation, Red List, Rarity, S41, Legal Protection, BAP, TVK, Common Name, Class, Order, Family, Sort Code
- Header-driven column lookup — users can freely reorder entry sheet columns
- Works across all three entry sheets (Personal, Commercial, Insect Collection)

**Pending records**: Alt+F8 RefreshRecords scans all `.xlsm` workbooks in the Active Record Books folder (`~\OneDrive\Active Record Books`), counts un-imported species entries, and displays pending counts alongside confirmed database records. Format: `Personal: 3 (+2p)`. Own-workbook entries counted by VBA (handles Excel file lock); other workbooks scanned by Python via openpyxl.

**Output**: `Tabella/output/Tabella_Field_Entry_YYYYMMDD.xlsm`

**Generator launcher**: `launchers\create_data_entry.bat` or `python -m Tabella.create_data_entry_workbook`

### Runtime App
Full PySide6 data entry application with UKSI species lookup, grid reference validation, vice county resolution, find/replace, undo/redo, auto-save, and CSV import/export.

**App launcher**: `launchers\run_tabella.bat` or `python -m Tabella`

**Databases used**: uksi.db, codex.db, vc_lookup.db (all read-only)

---

## Munia

Standalone PySide6 workload capacity manager for tracking field days, microscope days, and report days across the year. Prevents oversubscription and provides a visual overview of the work calendar.

**Features**:
- Annual capacity tracking with editable budget per day type (field/microscope/report)
- Project allocation table with add/edit/delete (project name, client, days, months, status)
- Year-at-a-glance heatmap — custom-painted calendar grid colour-coded by work type
- Click heatmap cells to add or remove day entries
- Oversubscription warnings per day type and overall banner
- Year selector (2020-2040)
- Titan CalDAV sync (stubbed — button present, implementation pending)

**Database**: munia.db — created automatically on first launch. Three tables: capacity (annual budget), projects (allocations with status), day_entries (individual logged days with half-day support).

**Databases used**: munia.db (read/write)

**Launcher**: `launchers\run_munia.bat` or `python -m Munia`

---

## Shared Infrastructure

### paths.py
Central path registry at project root. Every project imports from here:
```python
import paths
db = sqlite3.connect(str(paths.OBSERVATUM_DB))
```

### data/
Shared database directory. All eight databases live here, accessed by multiple projects.

### scripts/
Build and utility scripts: Codex builder, UKSI extractor, reset scripts, commercial marking.

### launchers/
All `.bat` files. Pattern: `cd /d "%~dp0\.."`, `set PYTHONPATH=%CD%`, `python -m ProjectName`.

---

## Database Dependency Map

| Database | Observatum | Examen | Curator | Tabella | Munia |
|----------|-----------|--------|---------|---------|-------|
| observatum.db | Read/Write | Read | Read | — | — |
| uksi.db | Read | — | Read | Read | — |
| codex.db | Read (pending) | Read/Write | — | Read | — |
| pantheon.db | Read (pending) | Read | — | — | — |
| vc_lookup.db | Read | — | — | Read | — |
| examen.db | — | Read/Write | — | — | — |
| gamification.db | Read/Write | — | — | — | — |
| munia.db | — | — | — | — | Read/Write |

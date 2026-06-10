# Biological Software — Suite Overview

## Date: 10 June 2026 (supersedes 25 March 2026)

---

## The Suite

Five Latin-themed desktop tools plus the Atrium launcher and the Codex infrastructure database, sharing a common data layer via `paths.py`. The desktop Examen was retired on 16 April 2026 in favour of a planned web-based replacement (see `08_Examen_Web_Design_Spec.md`).

| Name | Latin Meaning | Type | Purpose | Status |
|------|--------------|------|---------|--------|
| **Observatum** | "That which has been observed" | Main app | Biological recording — observations, specimens, recording scheme | Active |
| **Examen** | "Examination / Swarm of bees" | Web app (planned) | Invertebrate assemblage assessment — Pantheon website replacement | Desktop retired 16 Apr 2026; web build pending |
| **Codex** | "Book of law" | Database + Manager GUI | Conservation authority — statuses, SQS, TVK bridge | Built — 11-track schema, clean baseline |
| **Curator** | "The one who takes care" | Standalone app | Insect collection organiser — box planning, labels | Built |
| **Tabella** | "Writing tablet" | Generator + app | Field data entry workbook (Excel+VBA) + runtime data entry | Built — pending records system live |
| **Munia** | "Duties / obligations" | Standalone app | Workload capacity manager | Built |
| **Atrium** | "Entrance hall" | Launcher | System tray suite launcher | Built |

---

## Observatum

The main biological recording desktop application. Manages three core data types across tabbed views with import wizards, stats dashboards, embargo management, and iRecord integration.

**Tabs**: Observations, Insect Collection, Recording Scheme, Mapping, Stats, Settings

**Key features**: Three import wizards with UKSI validation and enrichment. Filter Wizard on all tabs. Embargo system for commercial data. Taxonomic sidebar on IC tab. iRecord sync with commercial field preservation. WAL checkpoint on close (added June 2026) folds side-files into the main database before exit, protecting against incomplete OneDrive sync states.

**Backup on close**: CSV export of observations, specimens, and recording_scheme, plus file-level backups of examen.db (frozen assessments) and munia.db (added June 2026).

**Databases used**: observatum.db, uksi.db, gamification.db (+ codex.db and pantheon.db for pending display integration)

**Launcher**: `run.bat` or `$env:PYTHONPATH = "$PWD;$PWD\Observatum"; python -m src.main`

---

## Examen (Web — planned)

The desktop Examen was retired on 16 April 2026; its code is archived at `_archive/Examen_desktop_20260416/`. The replacement is a web-based, donation-supported assessment tool. Architecture, privacy model, and Codex sync strategy are specified in `07_Codex_Design_Spec.md` section 7 and `08_Examen_Web_Design_Spec.md`.

**Status of examen.db**: holds historical frozen assessments; currently orphaned (no live application reads it). It is included in Observatum's backup-on-close. A decision on where full frozen assessments live in the web era is pending (see `24_Phase_Plan.md`, Phase 2).

---

## Codex Manager + Database

Standalone GUI (4 tabs) for browsing species conservation status, importing reviews, and managing data. The only application that writes to codex.db. Launcher: `python -m Codex` or `launchers/run_codex.bat`

### Database (verified 10 June 2026)

The conservation and scoring authority. Eleven status tracks across five conceptual categories (threat / rarity / specialist panel / legal / priority + regional red lists). Biodiversity-wide for conservation status; invertebrate-only for SQS and key-species logic.

| Table | Rows | Notes |
|-------|-----:|-------|
| designations | 27,062 | Raw JNCC Dec 2023 + manual, full provenance |
| status_summary | 23,123 | Best status per species per track — the consuming view |
| sqs_scores | 6,082 | Invertebrate-only (Pantheon + derived) |
| manual_entries | 0 | Clean baseline — populated by review imports |
| reviews | 0 | Clean baseline |
| species_profiles | 0 | Accumulates via review imports |

**Build pipeline**: `scripts/build_codex_db.py` (JNCC → codex.db), `scripts/seed_codex.py` (manual entries + invertebrate SQS gap-fill)

**Key consumers**: Tabella generator (workbook reference sheet), Observatum (display integration pending), web Examen (planned, via file-synced read-only copy)

---

## Curator

Standalone PySide6 tool for planning the physical layout of an insect collection. Reads specimen data from observatum.db and taxonomy from uksi.db.

**Features**: Mounting profile selection. Family-to-box allocation with growth allowance. Superfamily boundary-aware splitting. Suborder grouping (Coleoptera) and sort overrides (Hemiptera). Printable labels and box layout PDF export.

**Databases used**: observatum.db (read-only), uksi.db (read-only)

**Launcher**: `launchers\run_curator.bat` or `python -m Curator`

---

## Tabella

Two components: a workbook generator and a runtime data entry application.

### Workbook Generator
Creates a macro-enabled Excel workbook (.xlsm) for field data entry. The VBA macro auto-populates conservation and taxonomy fields when a species name is typed. Conservation data is embedded from Codex at generation time (import-time re-enrichment from live Codex is planned — Phase 1).

**Pending records**: RefreshRecords scans all `.xlsm` workbooks in the Active Record Books folder (`~\OneDrive\Active Record Books`), counting un-imported entries and displaying them alongside confirmed database records (`Personal: 3 (+2p)` format).

**Generator launcher**: `launchers\create_data_entry.bat`

### Runtime App
Full PySide6 data entry application with UKSI species lookup, grid reference validation, vice county resolution, find/replace, undo/redo, auto-save, and CSV import/export.

**App launcher**: `launchers\run_tabella.bat` or `python -m Tabella`

**Databases used**: uksi.db, codex.db, vc_lookup.db (all read-only)

---

## Munia

Standalone PySide6 workload capacity manager for tracking field, microscope, and report days across an April–March year. Capacity budgets, project allocations, year-at-a-glance heatmap, oversubscription warnings, revenue tracking. Titan CalDAV sync stubbed.

**Database**: munia.db (read/write) — now registered as `MUNIA_DB` in paths.py and included in Observatum's backup-on-close.

**Launcher**: `launchers\run_munia.bat` or `python -m Munia`

---

## Atrium

System tray suite launcher. Five tinted Victorian-palette app buttons (Observatum beetle, Curator mushroom, Tabella acorn, Munia bat — Examen's bird removed at retirement) plus Codex Manager and Generate Workbook tool buttons. Pin toggle, taskbar presence, pythonw launcher (no console). No database access.

---

## Shared Infrastructure

### paths.py
Central path registry at project root. Permanent — never delete. Defines ROOT, DATA_DIR, all `*_DB` constants (including MUNIA_DB as of June 2026), project directories, and the JNCC source folder.

### shared/
UI-agnostic library: `CodexRepository`, `PantheonRepository`, `PantheonAnalysisService`, `db_config.py`. This is the analysis engine the web Examen will be built on.

### Version control (added June 2026)
Local git repository at project root. Branches: `main` (development), `stable` (field-season tool). Excluded from history: `data/`, `_archive/`, `_backups/`, `Observatum/BackUps/`, `Observatum/test data/`, generated output, and `.bak` files. Databases are protected by the backup system, not git.

### data/
Shared database directory. All databases live here, accessed by multiple projects.

---

## Database Dependency Map

| Database | Observatum | Curator | Tabella | Codex Mgr | Munia | Web Examen (planned) |
|----------|-----------|---------|---------|-----------|-------|----------------------|
| observatum.db | Read/Write | Read | — | — | — | — |
| uksi.db | Read | Read | Read | Read | — | server copy possible |
| codex.db | Read (pending) | — | Read | Read/Write | — | Read (synced copy) |
| pantheon.db | Read (pending) | — | — | — | — | Read (synced copy) |
| vc_lookup.db | Read | — | Read | — | — | — |
| examen.db | Backup only | — | — | — | — | TBD (Phase 2 decision) |
| munia.db | Backup only | — | — | — | Read/Write | — |
| gamification.db | Read/Write | — | — | — | — | — |

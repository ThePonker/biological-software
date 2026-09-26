# Biological Software — Current State Analysis

## Date: 29 August 2026 (Session 29)
## Supersedes: 2 July 2026 version

---

## Project Architecture

```
Biological Software/
├── paths.py                       Suite-wide path registry (permanent)
├── run.bat                        Observatum launcher
├── .git/  .gitignore              Version control (main + stable)
├── shared/                        Shared library package
│   ├── db_config.py               Per-app config
│   ├── repositories/              CodexRepository, PantheonRepository
│   └── services/                  PantheonAnalysisService
├── Observatum/                    Main app — stubs re-export from shared/
├── DataEntry/                     Data Entry package (23 modules) — see 27
├── Examen/                        Retired desktop (archived); rebuild pending
├── Codex/                         Conservation manager GUI
├── Curator/                       Collection organiser
├── Tabella/                       Workbook generator + app — development paused
├── Munia/                         Capacity planner
├── Atrium/                        Suite launcher — 4 apps + 2 tools
├── data/                          8 databases (git-excluded, backup-protected)
│   └── _backups/                  Pre-live snapshots — rolling 2, self-pruning
├── scripts/                       Build/reset/import tools
├── launchers/                     All .bat files
├── _archive/Examen_desktop_20260416/
└── docs/                          Dev logs + design docs

C:\BiologicalSoftware_Backups\     CSV safety net — outside OneDrive by design
```

## Component Status

| App | State |
|-----|-------|
| Observatum | Stats audited, sync verified, mapping functional, embargo, filter wizard. WAL checkpoint + expanded backup-on-close. Observations tab has Delete Selected. Add Specimen rebuilt two-column with map + curatorial fields. |
| **DataEntry** | **In production.** 11 jobs / ~1,787 records staged. Sorting, row insert/delete, Traps card, CSV safety net, batch-stamped undo. See `27_Data_Entry_State.md`. |
| Examen | Desktop retired 16 Apr 2026 (archived). Rebuild is the next major build. |
| Codex Manager | 4 tabs, 11-track schema, clean baseline, fuzzy search |
| Curator | Suborder support, Hemiptera sort, label preview. Does not write curatorial fields. |
| Tabella | **Development paused Aug 2026.** Workbooks migrated into Data Entry staging. |
| Munia | Capacity planner; `MUNIA_DB` registered + backed up |
| Atrium | 4 tinted app icons + 2 tool buttons |
| shared/ | The analysis engine the Examen rebuild will sit on |

## Database State (29 Aug 2026)

| Database | State |
|----------|-------|
| observatum.db | **24,034 observations** (Commercial 4,511 / Personal 19,414); with irecord_id 1,178 / 18,758. **2,549 specimens** (ISO dates). ~110,510 RS. Plus `entry_jobs` / `entry_staging` holding ~1,787 staged records across 11 jobs. WAL, `synchronous=FULL`. ~114 MB. |
| codex.db | 14,395 species, 11 tracks. designations 27,062, status_summary 23,123, sqs_scores 6,082. manual_entries / reviews / species_profiles = 0. |
| uksi.db | ~122k taxa, extractor v5. `common_names`: 20,897 rows over 16,351 TVKs, each with exactly one `preferred=1`. No `language` column — English-only at extraction. |
| pantheon.db | ~14k species, ecology only |
| vc_lookup.db | Vice-county lookup — functional, drives VC derivation in Data Entry |
| examen.db | Frozen assessments; orphaned since desktop retirement; backed up on close |
| munia.db | Project allocations / day logs; backed up on close |
| gamification.db | Achievements — functional |

**Note on specimens:** all six curatorial columns (`preparation_type`, `storage_location`,
`drawer_unit`, `condition`, `label_data`, `specimen_code`) are empty across all 2,549 rows.
New specimens now capture four of them; the backfill needs the bulk editor (backlog A1).

## Data Protection

Six layers, documented in `27_Data_Entry_State.md` §5 and `05_Session_Handover.md`.

**Untested.** No restore has ever been performed from any layer, and everything is on one
machine — OneDrive is sync, not backup. Both are backlog items (D1, D2).

## Version Control

Local git at project root. `main` (development) / `stable` (field-season tool). **`stable`
has not been updated since June** — the whole Data Entry build and both August sessions sit
on `main` only. Excluded from history: `data/`, `_archive/`, `_backups/`,
`Observatum/BackUps/`, test data, `.bak` variants.

Known friction: OneDrive locks `.git/objects` during `gc`.

See `23_Rebuild_Procedures.md` for rebuild chains, `24_Phase_Plan.md` for the strategic
sequence, and `28_Development_Backlog.md` for the itemised work list.

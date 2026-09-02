# Biological Software — Current State Analysis

## Date: 2 July 2026 (reconciled to Session 26 / June 2026)
## Supersedes: 29 March 2026 version

---

## Project Architecture

```
Biological Software/
├── paths.py                       Suite-wide path registry (permanent; MUNIA_DB added Jun 2026)
├── run.bat                        Observatum launcher
├── .git/  .gitignore              Version control (main + stable), added Jun 2026
├── shared/                        Shared library package
│   ├── db_config.py               Per-app config (env/paths.py/auto-discover)
│   ├── repositories/              CodexRepository, PantheonRepository
│   └── services/                  PantheonAnalysisService
├── Observatum/                    Main app — stubs re-export from shared/
├── Examen/                        Retired desktop (archived); web/desktop rebuild pending
├── Codex/                         Conservation manager GUI
├── Curator/                       Collection organiser
├── Tabella/                       Field entry workbook generator + app
├── Munia/                         Capacity planner
├── Atrium/                        Suite launcher — 4 apps + 2 tools (Examen removed at retirement)
├── data/                          8 databases (git-excluded, backup-protected)
├── scripts/                       Build/reset/import tools
├── launchers/                     All .bat files
├── _archive/Examen_desktop_20260416/   Retired desktop Examen (reference only)
└── docs/                          Dev logs + design docs
```

## Component Status

| App | Key Features / State |
|-----|-------------|
| Observatum | Stats audited, sync verified + recovered, mapping functional, embargo, filter wizard. WAL checkpoint + expanded backup-on-close. Observation editing fixed. +3 schema columns. |
| Examen | **Desktop retired 16 Apr 2026** (archived). Desktop rebuild chosen first (winter); web = future layer on `shared/`. `examen.db` holds frozen assessments, now backed up on close. |
| Codex Manager | 4 tabs, 11-track schema, clean baseline, fuzzy search. Validated against widened DB. |
| Curator | Suborder support, Hemiptera sort, label preview |
| Tabella | Pending records + cross-workbook scan; `refresh_records.py` reads TVK column + `--skip`; VBA CSV `ParseCSVLine` fix |
| Munia | Capacity planner, April–March year, revenue tracking; `MUNIA_DB` registered + backed up |
| Atrium | 4 tinted app icons + 2 tool buttons, pin toggle, taskbar (Examen bird removed at retirement) |
| shared/ | CodexRepository + PantheonRepository + PantheonAnalysisService — the web/desktop Examen analysis engine |

## Database State

| Database | State |
|----------|-------|
| observatum.db | 23,925 obs (Commercial 4,511 / Personal 19,414); with irecord_id 1,178 / 18,758. 2,454 specimens (ISO). ~110,510 RS. +`sub_location`/`trap_number`/`visit_number`. |
| codex.db | **14,395 species, 11 tracks** (biodiversity-wide conservation, invertebrate-only SQS). designations 27,062, status_summary 23,123, sqs_scores 6,082. manual_entries/reviews/species_profiles = 0 (clean baseline). Build script patched. |
| uksi.db | ~122k taxa, extractor v5 (English-only common names, sort_code/sort_order, preferred flag) |
| pantheon.db | ~14k species, ecology only |
| vc_lookup.db | Vice-county lookup — functional |
| examen.db | Frozen assessments; orphaned since desktop retirement; backed up on close |
| munia.db | Project allocations / day logs; backed up on close |
| gamification.db | Achievements — functional |

## Version Control (added June 2026)

Local git at project root. `main` (development) / `stable` (field-season tool). Excluded from history: `data/`, `_archive/`, `_backups/`, `Observatum/BackUps/`, test data, generated output, `.bak`. Databases protected by the backup system, not git. Known friction: OneDrive locks `.git/objects` during `gc` — pause sync or kill OneDrive before repacking.

See `23_Rebuild_Procedures.md` for database rebuild chains and `24_Phase_Plan.md` for the live development plan.

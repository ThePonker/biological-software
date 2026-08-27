# Biological Software — Current State Analysis (Updated 29 Mar 2026 — Final)

## Project Architecture

```
Biological Software/
├── paths.py                       Suite-wide path registry
├── run.bat                        Observatum launcher
├── verify_restructure.py          Post-restructure test (29/29)
├── shared/                        Shared library package
│   ├── db_config.py               Per-app config (env/paths.py/auto-discover)
│   ├── repositories/              CodexRepository (597), PantheonRepository (240)
│   └── services/                  PantheonAnalysisService (241)
├── Observatum/                    Main app — stubs re-export from shared/
├── Examen/                        Pantheon replacement — imports from shared/
├── Codex/                         Conservation manager GUI (8 files, ~1,350 lines)
├── Curator/                       Collection organiser
├── Tabella/                       Field entry workbook generator + app
├── Munia/                         Capacity planner (8 files)
├── Atrium/                        Suite launcher — 5 apps + 2 tools, tinted icons
├── data/                          8 databases
├── scripts/                       Build/reset/import tools
├── launchers/                     All .bat files (pythonw for Atrium)
└── docs/                          Dev logs + design docs
```

## All Components Working ✅

| App | Key Features |
|-----|-------------|
| Observatum | Stats audited, sync verified, mapping functional, embargo, filter wizard |
| Examen | 3 views wired + polished, imports from shared/ |
| Codex Manager | 4 tabs, 3 reviews imported, 7,612 species, fuzzy search |
| Curator | Suborder support, Hemiptera sort, label preview |
| Tabella v2 | Recording history, pending records from active workbooks, cross-workbook scanning |
| Munia v2 | Capacity planner, April-March year, revenue tracking |
| Atrium | 5 tinted icons, 2 tool buttons, pin toggle, taskbar, auto-delete old workbooks |
| shared/ | CodexRepository + PantheonRepository + PantheonAnalysisService | |

## Atrium — Redesigned

5 main app buttons with distinct Victorian-palette tinted silhouettes:
- **Observatum** (beetle) — Royal purple `#6b4c8a`
- **Examen** (bird) — Burnt sienna `#a0522d`
- **Curator** (mushroom) — Moss green `#4a7c59`
- **Tabella** (acorn) — Antique gold `#b8860b`
- **Munia** (bat) — Slate blue `#4a6580`

2 centred tool buttons: Codex Manager, Generate Workbook (auto-deletes old .xlsm).
Pin toggle, taskbar presence, draggable header, no console window.

## Database State

| Database | State |
|----------|-------|
| observatum.db | 23,630 obs + 2,454 spec (all ISO dates) + 110,510 RS. 8 date fixes applied. |
| codex.db | 7,612 species, 3 reviews, 12,795 SQS, schema v4 |
| uksi.db | 122k taxa, v5 |
| pantheon.db | 14k species, ecology only |
| Others | vc_lookup, examen, munia, gamification — all functional |

See `23_Rebuild_Procedures.md` for database rebuild chains.

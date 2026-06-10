# Biological Software — Restructure Plan

## Date: 24 March 2026
## Status: ✅ EXECUTED — Session 22

---

## Summary

Renamed `Observatum_V2/` to `Biological Software/`, separated six development projects into own folders with Latin names, created central `paths.py` module. All path references migrated. Smoke test passed.

**Execution time**: ~3 hours (planned 2.5, additional time for import placement fixes)

---

## What Was Done

### Folder Structure
```
Biological Software/
├── paths.py                       Central path registry
├── run.bat                        Observatum launcher
├── Observatum/                    Main app (src/ moved here)
├── Examen/                        Pantheon replacement (was Site_Register)
├── Curator/                       Collection organiser (was Collection_Organiser)
├── Tabella/                       Field entry (was scripts/field_entry)
├── Munia/                         Workload manager (placeholder)
├── data/                          Shared databases
├── scripts/                       Build/reset tools
├── launchers/                     All .bat files
└── docs/                          dev_logs/ + design/ + archive/
```

### Files Migrated
- 51 Python files updated to use `import paths`
- 12 launchers updated with PYTHONPATH
- 3 Examen files renamed (register_* → examen_*/snapshot_manager)
- All internal Examen cross-references updated

### Issues During Execution
1. Migration script placed `import paths` inside docstrings, multi-line imports, and try/except blocks (10 files needed manual correction)
2. `paths.py` was accidentally deleted (looked like a temp utility script)
3. `Paths.data_dir()` in config.py and gamification still resolved to Observatum/data/ — replaced with `paths.DATA_DIR`
4. OneDrive file lock prevented initial root folder rename — resolved by closing sync
5. Examen `__main__.py` and `examen_ui.py` still referenced old filenames — fixed

### Verification
- Observatum: ✅ launches, all tabs load
- Curator: ✅ launches
- Examen: ✅ launches
- paths.py: ✅ resolves correctly (`ROOT`, all DB paths, all directory paths)

---

## Latin Names — Final

| Name | Meaning | Project |
|------|---------|---------|
| Observatum | "That which has been observed" | Main recording app |
| Examen | "Examination / Swarm of bees" | Pantheon replacement |
| Codex | "Book of law" | Conservation database |
| Curator | "The one who takes care" | Collection organiser |
| Tabella | "Writing tablet" | Field entry workbook |
| Munia | "Duties / obligations" | Workload manager |

---

## paths.py — Central Path Registry

Resolves from `__file__` location (primary), `BIOSOFT_ROOT` env var (fallback), or common OneDrive/Documents locations (last resort).

Defines: `ROOT`, `DATA_DIR`, `MAPS_DIR`, all 7 `*_DB` constants, `VC_GEOJSON`, `SAVED_FILTERS`, `JNCC_DIR`, all 8 `*_DIR` project directories, `db_path()` helper.

**This file is permanent. Do not delete.**

---

## Lessons for Future Migrations

1. Use AST-aware import insertion, not regex/string matching
2. Audit method-call path patterns (`Paths.data_dir()`) not just `Path(__file__)` patterns
3. Clearly mark permanent infrastructure files vs temporary utility scripts
4. Close OneDrive before renaming root folders
5. Test internal cross-references after file renames (not just path constants)

# Parallel Development — Status & Assignments

## Date: 10 June 2026 (supersedes 26 March 2026)

---

## Current Mode

Field season — single-bot maintenance and hygiene work only. No parallel development active. The desktop Examen workstream is closed (retired 16 April 2026, archived at `_archive/Examen_desktop_20260416/`); all Examen entries in the previous version of this plan are void.

---

## Completed Since Last Version

| Item | Session | Notes |
|------|---------|-------|
| Codex 11-track rebuild | Apr 2026 | 9 files rewritten; clean baseline; SQS invertebrate-only; data quality issues (zero-SQS, TVK collisions) cleaned |
| Desktop Examen retirement | Apr 2026 | Archived; Atrium entry removed |
| Session 25 field fixes | Apr–May 2026 | Species search rewrite, specimen/observation editing, date standardisation, Tabella pending records |
| Phase 0 hygiene | Jun 2026 | Git repo (main + stable), WAL checkpoint on close, examen/munia backups, MUNIA_DB in paths.py, docs refresh |

---

## Future Parallelisable Work (Winter 2026)

### Safe for a second bot (fully isolated directories)

| Task | Directory | Notes |
|------|-----------|-------|
| Curator PDF export polish, sort overrides | `Curator/` | No shared files |
| Munia CalDAV sync | `Munia/` | Needs Titan server details |
| Codex review imports (macro-moth, micro-moth, NECR390) | `scripts/` + CSV prep | Coordinate on scripts/; macro-moth blocked on PDF extraction |

### This bot only (touches Observatum core or shared infrastructure)

| Task | Risk area |
|------|-----------|
| Phase 1: taxonomy refresh script, import-time Codex enrichment | `scripts/`, import wizards |
| Codex display integration in Observatum | `Observatum/src/views/` |
| Mapping tab polish | `Observatum/src/views/mapping/` |
| Modularisation (tab registry, first-run setup) | `Observatum/src/` core |
| Web Examen build | New project directory |

---

## File Ownership Rules

| Directory | Owner | Rule |
|-----------|-------|------|
| `Observatum/src/` | This bot | No parallel modifications |
| `shared/` | This bot | Read-only for any second bot |
| `Curator/`, `Munia/` | Second bot eligible | Isolated |
| `Tabella/` | Coordinate | VBA + generator changes affect live field workbooks |
| `Codex/` | Coordinate | Manager GUI |
| `paths.py`, `scripts/` | Coordinate | Notify before editing |
| `.gitignore`, git workflow | This bot | Single source of repo discipline |

## Git Discipline for Parallel Work

When parallel development resumes: second-bot deliveries are applied on `main`, tested, then merged to `stable` only after a field-tested session. Never apply unreviewed parallel deliveries directly to `stable`.

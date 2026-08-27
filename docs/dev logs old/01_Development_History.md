# Biological Software — Complete Development History (Updated 26 Mar 2026 — Session 24 Complete)

## Project Overview

**Biological Software** is a suite of Latin-themed tools for naturalist field recording and invertebrate survey reporting, built with Python/PySide6/SQLite. It follows a Victorian naturalist theme.

### The Software Suite

| Name | Purpose | Status |
|------|---------|--------|
| **Observatum** | Main biological recording app — observations, specimens, recording scheme | Active development |
| **Examen** | Species assessment tool (Pantheon replacement) — 3 views, 5 polish features | Views wired + polished |
| **Codex** | Conservation manager GUI + database pipeline | Phase 3 complete |
| **Curator** | Insect collection organiser — suborders, Hemiptera sort fix | Built + enhanced |
| **Tabella** | Field data entry workbook generator (Excel+VBA) + runtime app | v2 complete |
| **Munia** | Capacity planner + pipeline manager | v2 complete |
| **Atrium** | Suite launcher (system tray) | Built |

### Session 24 (25-26 Mar 2026) — Import Pipeline, RS Integration & Multi-Bot Development ⭐⭐⭐

**This bot — Observatum fixes (17 items):**
- Specimen enrichment root cause (`uksi_conn` → `uksi_model`)
- Subfamily parent-chain lookup (UKSI has no subfamily column)
- Import notes combine pattern on all 3 wizards
- RS stats filter toggles → cache invalidation + data table refresh
- RS tab export wired (Export All + Export Selected)
- VC lookup dialog fix + recording gaps per county tab
- VC number recovery (94.5% → 99.2%) + permanent import fix
- Species Match Report on all 3 wizards
- Persistent Resolve Species button on observation wizard
- Row handling UI consistency, stray widget fix
- Stats refresh after import (dedup + invalidation)

**Parallel bot — 3 deliveries:**
- Examen Polish: manual entry editor, import species list, appendix export, site comparison, historical export
- Curator: Hemiptera sort override, Coleoptera suborder grouping, suborder labels
- Atrium: system tray suite launcher with themed popup panel

---

## Performance Metrics

| Operation | Before | After |
|-----------|--------|-------|
| Total startup | 16.5s | 3.6s |
| Stats switching | 6.5s | 0.000s |
| Scheme stats | 2.6s | 0.026s |
| Column sort | 5+ sec | 0.018s |
| RS enrichment (79k rows) | Hung at 29% | Completes in seconds |

---

## Remaining Work

| Category | Hours | Status |
|----------|-------|--------|
| Stats audit + sync + mapping + restructure + Atrium | — | All done |
| Mapping remaining | 3 | Winter |
| Codex display integration (Observatum) | 4-6 | Pending |
| Examen remaining (paste/import refinements, export refinements) | 3-5 | Core features done |
| Observatum Data Entry View | 16-24 | Winter 2026 |
| Gamification | 8-12 | Winter 2026 |
| **Total** | **~18-26 hrs** | |

### Session 25 (28 Apr 2026) — Field Season Bug Fixes

**Bug fixes during testing:**
- Species search: QCompleter replaced with QListWidget popup (full keyboard control)
- Specimen editing: `site_name_local` column added, edit chain working end-to-end
- Date standardisation: all 2,454 specimen dates migrated to ISO, sort fixes for IC + RS tabs
- Observation editing: new EditObservationDialog, edit lock only on iRecord-sourced records
- Add Specimen: validation warnings, Ctrl+Enter save, dynamic date placeholder
- CSV backup: always offers on close, includes recording_scheme table
- Data fixes: 8 Kent Deadwood records 2027 → 2026
- Atrium: tinted icons, pin toggle, taskbar, centred layout, no console
- Tabella pending records: refresh_records.py scans active workbooks, VBA counts own entries
- Cross-workbook pending display: "Personal: 3 (+2p)" format in info panel
- Generator + vba_source.py updated for future workbooks

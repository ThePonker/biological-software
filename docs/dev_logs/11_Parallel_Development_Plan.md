# Parallel Development — Status & Future Assignments

## Date: 26 March 2026 (Updated post-Session 24)

---

## Completed by Parallel Bot (Session 24)

### ✅ Examen View Wiring
All 3 views rewired to CodexRepository, PantheonRepository, PantheonAnalysisService.

### ✅ Examen Polish (5 features)
Manual entry editor, import species list, appendix export, site comparison, historical export. Project-level grouping.

### ✅ Curator Fixes
Hemiptera sort override, Coleoptera suborder grouping, suborder labels in preview/export.

### ✅ Atrium Suite Launcher (redesigned Session 24)
### ✅ Munia v2 + Tabella v2
### ✅ Codex Phase 1-3 + Manager GUI + 3 Imports
System tray app with themed popup panel, 5 app buttons, status dots.

---

## Safe to Parallelise Next

### Task A: Examen Refinements (Other Bot)
**Risk: None.** Only `Examen/` files.
- Paste/import UX polish (better error handling, format detection)
- Export format options (PDF as well as Excel)
- Mode comparison side-by-side display

### Task B: Curator PDF Export (Other Bot)
**Risk: None.** Only `Curator/` files.
- Verify PDF export includes suborder labels
- Other orders: add sort overrides as alphabetical UKSI sorting discovered

### Task C: Munia CalDAV (Other Bot)
**Risk: None.** Only `Munia/` files.
- Titan CalDAV sync implementation
- Project status workflow

---

## This Bot Handles

### Task D: Codex Display Integration
**Risk: Touches Observatum/src/views/.** This bot only.
- Species Profile dialog
- Stats dashboards — key species counts
- Export — conservation status column

### Task E: Mapping Tab Polish
**Risk: Low.** Only `views/mapping/` files.
- Filter panel wiring
- Export image
- Could be parallelised if other bot stays out of main_window.py

---

## File Ownership Rules

| Directory | Owner | Rule |
|-----------|-------|------|
| `Observatum/src/views/` | This bot | No parallel modifications |
| `Observatum/src/services/` | Read-only | Both bots can read, neither modifies |
| `Observatum/src/repositories/` | Read-only | Both bots can read, neither modifies |
| `Examen/` | Other bot | This bot doesn't touch |
| `Curator/` | Other bot | This bot doesn't touch |
| `Munia/` | Other bot | This bot doesn't touch |
| `Atrium/` | Other bot | This bot doesn't touch |
| `Tabella/` | Other bot | This bot doesn't touch |
| `paths.py` | Coordinate | Notify before editing |
| `scripts/` | Coordinate | Notify before editing |

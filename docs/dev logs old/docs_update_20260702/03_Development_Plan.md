# Biological Software — Development Plan

## Updated 2 July 2026 (through Session 26)

> **Live plan is now `24_Phase_Plan.md`.** This file is retained as the higher-level status roll-up; the phase-by-phase build breakdown, estimates, and risk register live in `24`. Where the two overlap, `24` wins.

---

## Completed

### ✅ Pre-season (Sessions 22–24)
Observatum core phases 0–10; Curator, Munia v2, Tabella v2; stats audit; Codex Phase 1–3; iRecord sync + backup; mapping phases A–D; shared-library extraction + per-app config; codebase cleanup; Atrium redesign.

### ✅ Session 25 (field season)
Species-search rewrite; specimen/observation editing (+ update() fix); date standardisation; Tabella pending records. iRecord recovery (180 IDs preserved, sync bug fixed). Tabella `refresh_records.py` TVK/`--skip` fix; `mark_synced` fix; CSV `ParseCSVLine` fix.

### ✅ Codex 11-track widening
Biodiversity-wide conservation, invertebrate-only SQS. 14,395 species; clean baseline; build script patched. Codex Manager + Tabella validated.

### ✅ Session 26 (June)
Phase 0 hygiene (Git, WAL checkpoint, examen/munia backups, MUNIA_DB). Three schema columns for Data Entry. Taxonomy refresh (0 stale). Examen desktop retired; desktop-first strategy set. Data Entry View designed. Examen web spec rewritten (no-storage core).

---

## Remaining Work

### Phase 1 — Data Integrity (field-season-safe)
- Taxonomy refresh script (deprecated observatum.db TVKs → current via UKSI synonym resolution).
- Import wizards re-enrich conservation columns from live Codex (kill workbook staleness).
- Reconstruct `build_pantheon_db.py`; write rebuild-all chain (UKSI → Pantheon → Codex → seed).
- Tabella pending hour: sheet protection + Active Record Books path in Settings.
- Eyeball future-dated commercial record.

### Winter builds (one major per winter, solo)
| Build | Est. (focused days) |
|-------|------|
| Desktop Examen (personal) | 5–8 |
| Desktop Examen (distributable add-on) | +3–5 |
| Data Entry View | 4–6 |
| Distributable Observatum | ~5–6 |
| Web Examen (future) | 10–15 |

### Deferred (as time allows)
Codex display integration in Observatum (opportunistic, one touchpoint per session); mapping polish; gamification; Codex review imports (macro-moth blocked on PDF extraction, micro-moth, NECR390).

---

## Field-Season Status — ALL READY

| App | Status |
|-----|--------|
| Observatum | ✅ Audited, sync verified + recovered, edit fixes in |
| Examen | Desktop retired; rebuild = winter |
| Codex Manager | ✅ 11-track, clean baseline |
| Curator | ✅ Working |
| Tabella v2 | ✅ Enhanced workbooks + refresh fix |
| Munia v2 | ✅ Capacity planner |
| Atrium | ✅ Launcher (4 apps + 2 tools) |

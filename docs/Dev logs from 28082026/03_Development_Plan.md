# Biological Software — Development Plan

## Updated 29 August 2026 (Session 29)

> **Live plan is `24_Phase_Plan.md`.** Itemised work is in `28_Development_Backlog.md`.
> This file is the higher-level status roll-up. Where they overlap, `24` and `28` win.

---

## Completed

### ✅ Pre-season (Sessions 22–24)
Observatum core phases 0–10; Curator, Munia v2, Tabella v2; stats audit; Codex Phase 1–3;
iRecord sync + backup; mapping phases A–D; shared-library extraction; Atrium redesign.

### ✅ Session 25 (field season)
Species-search rewrite; specimen/observation editing; date standardisation to ISO; iRecord
recovery (180 IDs preserved, sync bug fixed); Tabella pending records.

### ✅ Codex 11-track widening
Biodiversity-wide conservation, invertebrate-only SQS. 14,395 species; clean baseline.

### ✅ Session 26 (June)
Phase 0 hygiene; three schema columns for Data Entry; taxonomy refresh; Examen desktop
retired; Data Entry View designed.

### ✅ Session 27 (July–August) — Data Entry View built
Out of sequence, driven by the field season. Staging model, entry grid, maps, preview/go-live
split, commit path. See `27_Data_Entry_State.md`.

### ✅ Session 28 (27 Aug)
Delete Selected; two latent crashes fixed; 9 BOMs stripped; **common-name filter bug fixed**
(was excluding 38% of names); 11 workbooks / 1,787 records migrated to staging; batch-stamped
undo.

### ✅ Session 29 (28–29 Aug)
CSV safety net; backup pruning (3.9 GB → 228 MB); grid sorting, row insert/delete, Traps
card, column order, VC derivation; Add Specimen rebuilt two-column with map and curatorial
fields; date-format audit.

---

## Remaining Work

### Now — field-season-safe
- **Bulk curatorial editor** — blocking the collection data (backlog A1)
- **Verify curatorial edit on existing specimens** (A2)
- Import wizards re-enrich conservation from live Codex (C2)
- Doubled import notes (C1)
- **Test a restore** (D1)
- Merge `main` → `stable` once staging work is committed

### Winter builds
| Build | Est. (focused days) |
|-------|------|
| **Desktop Examen (personal)** | **5–8** |
| Desktop Examen (distributable add-on) | +3–5 |
| Insect Collection curation (bulk editor, labels, rename) | 1.5–2 |
| Data Entry remainder (clicker, repeat key) | ~1 |
| Distributable Observatum | ~5–6 |
| Web Examen (future) | 10–15 |

### Deferred
Codex display integration in Observatum (opportunistic); mapping polish; gamification; Codex
review imports (macro-moth blocked on PDF extraction).

### Paused / cancelled
**Tabella** — development paused Aug 2026; superseded by Data Entry for desk work.

---

## Suite Status

| App | Status |
|-----|--------|
| Observatum | ✅ Active; Data Entry in production |
| DataEntry | ✅ In production — 11 jobs staged, commits pending |
| Examen | Desktop retired; rebuild is the next major build |
| Codex Manager | ✅ 11-track, clean baseline |
| Curator | ✅ Working |
| Tabella | ⏸ Paused |
| Munia | ✅ Capacity planner |
| Atrium | ✅ Launcher (4 apps + 2 tools) |

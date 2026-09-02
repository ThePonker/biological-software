# Development Phase Plan

## Updated 29 August 2026 (Session 29)
## Supersedes: 10 June 2026 version

---

## What changed since June

The June plan sequenced **Desktop Examen → Data Entry View → distributable work**, with Data
Entry pencilled at 4–6 focused days in winter.

**Data Entry was built instead, out of sequence, over July and August**, and is now in
production holding the season's records. That was the right call — the field season created
the need — but it means the June plan no longer describes reality. This revision reconciles
it.

Desktop Examen remains the next major build.

---

## Strategic Decisions (unchanged unless noted)

1. **Evolve, don't rewrite.** The current codebase is the final software.
2. **Modularisation is a registry layer, not a rebuild.** Observatum tabs become
   config-driven modules for distribution.
3. **Pilot distribution** target: 2–3 trusted colleagues, not public release.
4. **Examen: desktop first, web later.** Unchanged.
5. **Examen builds fresh** on current `shared/` + Codex; the retired desktop is reference only.
6. **Data Entry — DELIVERED** (revised). Was Phase 3b; built early. Remaining scope is the
   clicker count-mode and repeat key only.
7. **Tabella — PAUSED** (new, Aug 2026). Data Entry supersedes the workbook round-trip for
   desk entry. Sheet protection and the Settings path are no longer pursued.

---

## Phase 0 — Hygiene ✅ COMPLETE (June 2026)

Git; WAL checkpoint on close; examen/munia backups; `MUNIA_DB` in paths.py; docs refresh.

## Phase 1 — Data Integrity (partly done, field-season-safe)

| # | Item | Status |
|---|------|--------|
| 5 | Taxonomy refresh | ✅ Done as a re-runnable diagnostic (30 records resolved). Judged not to need a standing script. |
| 6 | Import wizards re-enrich from live Codex | **Open** — backlog C2 |
| 7 | Reconstruct `build_pantheon_db.py`; rebuild-all chain | **Open** — backlog D3 |
| 8 | Tabella pending hour | **Cancelled** — Tabella paused |
| — | Schema columns for Data Entry | ✅ Done June |
| — | Data protection audit + CSV safety net | ✅ Done Session 29 |

## Phase 2 — Decisions ✅ RESOLVED (June 2026)

Frozen assessments need no server storage; UKSI is CC BY 4.0; build priority set.

## Phase 3 — Desktop Examen (NEXT MAJOR BUILD)

**Spec:** `08_Examen_Web_Design_Spec.md` defines the analysis and report model;
`24` → "desktop first" is the chosen path. The retired desktop is structural reference only.

**Update model:** manual `codex.db` drop-in. No update server.

| Tier | Scope | Est. (focused days) |
|---|---|---|
| **Personal** | Wil's machine, local Codex, Excel/PDF/Word reports | **5–8** |
| **Distributable** | Others' machines, Codex drop-in, de-personalised, packaged | **+3–5** |

**Breakdown (personal tier):** window shell on `shared/` 1 day; paste/import + species
matching 1–1.5; analysis + on-screen results 1; reports Excel → PDF → Word 2–3; polish,
version stamping, testing 1.

**Audience:** fellow consultants relying on the unmaintained, 2017-stale Pantheon website.

## Phase 3b — Data Entry ✅ LARGELY DELIVERED

Built July–August 2026. See `27_Data_Entry_State.md` for what exists.

**Remaining:** clicker count-mode (~0.5 day), repeat key (small). Both matter for
microscope work on trap samples. Backlog B2, B3.

## Phase 3c — Insect Collection curation (NEW)

Raised during Session 29 and not previously planned.

| Item | Est. |
|------|------|
| Bulk curatorial editor (2,549 specimens with empty fields) | 0.5–1 day |
| `label_data` composition from the record | 0.5 day |
| `drawer_unit` → `drawer_number` schema rename | 0.5 day |

The bulk editor is the blocker: without it the curatorial fields added in Session 29 only
serve new specimens.

## Phase 3d — Distributable Observatum (winter / later)

| Component | Est. |
|-----------|------|
| Module registry — config-driven tabs | 1 day |
| Conditional dependents — stats, filters, exports, backups | 1 day |
| First-run setup wizard | 1 day |
| De-personalisation sweep | 0.5 day |
| PyInstaller packaging (~150 MB with databases) | 1–2 days |
| Licensing/attribution screens | 0.5 day |

Shares first-run, packaging and de-personalisation work with the distributable Examen tier.

## Phase 4 — Web Examen (FUTURE, if reach justifies it)

Not foreclosed. The `shared/` engine is UI-agnostic, so web becomes front-end plus
deployment. ~10–15 focused days; soft estimate, new stack. Gating items already researched
(hosting ~£4–7/mo, accounts declined, tax within the likely £1,000 allowance).

---

## Estimate Summary

| Build | Est. (focused days) | When |
|---|---|---|
| Phase 1 remainder (wizards, rebuild chain) | ~1.5–2 | field-season-safe |
| Data Entry remainder (clicker, repeat key) | ~1 | as needed |
| **Insect Collection curation** | **1.5–2** | soon — blocking the collection data |
| **Desktop Examen (personal)** | **5–8** | winter, first major build |
| Desktop Examen (distributable) | +3–5 | winter, follow-on |
| Distributable Observatum | ~5–6 | winter / later |
| Web Examen | 10–15 | future |

**Caveat:** these are *focused* days. Done in evenings and rainy days, each multiplies into
weeks of calendar time — one major build per winter is realistic for a solo developer.

---

## Risk Register

| Issue | Severity | Status |
|-------|----------|--------|
| No version control | High | ✅ Closed (Phase 0) |
| SQLite WAL + OneDrive sync | High | ✅ Mitigated; durability verified Session 29 |
| **`stable` branch stale since June** | **Medium** | **Open** — the whole Data Entry build is on `main` only |
| **No tested restore** | **Medium** | **Open** — backlog D1 |
| **Single machine; no off-site copy** | **Medium** | **Open** — backlog D2, offline server |
| **Curatorial fields empty across 2,549 specimens** | Medium | Open — backlog A1 |
| Never-executed code paths | Medium | 3 found and fixed; sweep outstanding — backlog D5 |
| Tabella bakes Codex at generation time | Medium | Reduced — Tabella paused, workbooks migrated |
| Stale TVKs in observatum.db | Low, compounding | Diagnostic exists; re-run after UKSI updates |
| Observatum's unmigrated Codex touchpoints | Low–medium | Opportunistic |
| `build_pantheon_db.py` missing | Low | Backlog D3 |
| Doc drift | Low | ✅ Closed (this revision) |

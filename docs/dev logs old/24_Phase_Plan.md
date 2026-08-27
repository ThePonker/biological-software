# Development Phase Plan

## Date: 10 June 2026 (Session 26)
## Origin: Suite-wide architecture evaluation, June 2026

---

## Strategic Decisions (settled this session)

1. **Evolve, don't rewrite.** The current codebase is the final software. Development continues in place, protected by git branching (`stable` for field season, `main` for development).
2. **Modularisation is a registry layer, not a rebuild.** Observatum tabs become config-driven modules so distributed copies can omit e.g. Recording Scheme or ship Mapping as "preview". Estimated ~5–6 days (winter).
3. **Pilot distribution** target: 2–3 trusted colleagues, not public release.
4. **Examen: desktop first, web later (revised this session).** A **desktop** Examen is built first — far cheaper (~5–8 days vs ~10–15 for web), on the stack already in use, reusing existing species-matching and the `shared/` engine, no hosting/privacy/tax/operational burden. The web version becomes a *future* layer on the **same `shared/` engine** if public reach ever justifies the cost — building desktop first forecloses nothing. See §Examen below.
5. **Examen builds fresh.** The retired desktop Examen (`_archive/Examen_desktop_20260416/`) is a **structural reference only**, not a foundation — it predates the 11-track Codex and this session's entry/report decisions. Crib layout ideas; build on current `shared/` + Codex.
6. **Data Entry View** (Observatum) follows Examen — design complete (`26_Data_Entry_Design.md`), build ~4–6 days, winter.

---

## Phase 0 — Hygiene ✅ COMPLETE (10 June 2026)

| # | Item | Outcome |
|---|------|---------|
| 1 | Git repository | Installed Git 2.54; repo initialised with `main` + `stable`; ignore rules for data/, archives, backups, user CSV backups, test data, .bak variants. Clean history: 466 objects, 14.7 MiB pack. Commits: initial baseline → WAL/backup patch |
| 2 | WAL safety | `PRAGMA wal_checkpoint(TRUNCATE)` on Observatum close for observatum.db + uksi.db. Finding: DatabaseManager uses per-operation connections, so WAL side-files exist only during operations — risk window smaller than assumed; checkpoint retained as crash/orphan safety net. Checkpoint path proven: result (0, 0, 0) |
| 3 | Backup coverage | examen.db and munia.db added to Observatum backup-on-close via SQLite online backup API. MUNIA_DB constant added to paths.py (closes Infrastructure Issue 13) |
| 4 | Docs refresh | 06 / 08 / 11 updated for desktop Examen retirement; this plan filed |

**Data correction recorded**: codex.db verified at the April clean baseline — designations 27,062; status_summary 23,123; sqs_scores 6,082; manual_entries / reviews / species_profiles 0. The "7,612 species, 3 reviews" figures in 02/04/05 are stale (pre-April-rebuild) and should not be carried forward.

**Known friction**: OneDrive locks `.git` object directories during gc. Workarounds: pause sync or `taskkill OneDrive.exe` for repack operations; `$env:GIT_ASK_YESNO="false"` suppresses retry prompts. Revisit moving the repo out of OneDrive if it worsens.

---

## Phase 1 — Data Integrity (1–2 sessions, field-season-safe)

| # | Item | Why |
|---|------|-----|
| 5 | Taxonomy refresh script (observatum.db deprecated TVKs → current via UKSI synonym resolution) | Compounding debt; grows with every UKSI release |
| 6 | Import wizards re-enrich conservation columns from live Codex instead of trusting workbook values | Kills the workbook-staleness path into permanent records |
| 7 | Reconstruct `build_pantheon_db.py`; write rebuild-all chain script (UKSI → Pantheon → Codex → seed) | Unverifiable link in the rebuild chain |
| 8 | Tabella pending hour: sheet protection (`UserInterfaceOnly:=True`) + Active Record Books path into Observatum Settings | Item 8b doubles as de-personalisation work |

## Phase 2 — Decisions ✅ RESOLVED THIS SESSION

| # | Decision | Outcome |
|---|----------|---------|
| 9 | Frozen assessments home | **No saved storage needed.** The downloaded report (stamped with date + Codex version) *is* the frozen record, held by the user. Deep private history, if ever wanted, lives on the user's own desktop, not a server. |
| 10 | UKSI licence | **CC BY 4.0** (NHM/GBIF) — public, commercial-capable use permitted, attribution the only condition. JNCC + Pantheon are OGL. No blocker. |
| 11 | Build priority | **Desktop Examen first** (cheap, owned stack, no operational burden), then Data Entry View, then modular-distributable work. Web Examen = future layer on the same engine. |

## Examen — desktop first (chosen path)

**Spec:** `08_Examen_Web_Design_Spec.md` defines the *web* target; the desktop build delivers the same analysis + reports model locally. The retired desktop build is reference only (decision 5).

**Update model (decided): option (a) — manual `codex.db` drop-in.** Wil maintains Codex centrally (rebuild from JNCC / import reviews via Codex Manager — *already easy, already built*). To update any user's conservation data, ship them a fresh `codex.db` to drop in; the app reads it live. No update server, no fetch logic, no version-check infrastructure — trivial, works day one, fine for a small set of trusted consultant users. (Options b/c — auto-fetch or packaged re-release — remain future upgrades if the user base grows.)

**Two tiers of ambition:**

| Tier | Scope | Est. (focused days) |
|---|---|---|
| **Personal** | Runs on Wil's machine, reads local Codex, reports to Excel/PDF/Word | **~5–8** |
| **Distributable** | Runs on others' machines; ships Codex updates via drop-in (a); de-personalised; packaged | **+3–5** on top |

The distributable tier **shares packaging work with Observatum distribution** (first-run setup, no hardcoded paths, PyInstaller) — doing one teaches the other. And maintaining-central-Codex-and-shipping-it is the *same data-distribution job* the web version would need, so this builds toward web, not away from it.

**Desktop build breakdown (personal tier):**

| Piece | Est. |
|---|---|
| Window shell + wire to `shared/` engine | 1 day |
| Paste/import list + species matching (reuse existing wizard logic) | 1–1.5 days |
| Analysis + on-screen results | 1 day |
| Reports: Excel → PDF → Word | 2–3 days |
| Polish, Codex-version stamping, testing | 1 day |

**Audience:** fellow consultants who currently rely on the unmaintained, 2017-stale Pantheon website. Real group, real pain point.

## Phase 3 — Web Examen (FUTURE, if reach justifies it)

Not foreclosed. Because the analysis lives in the UI-agnostic `shared/` engine, the desktop build proves the tool/reports/analysis end-to-end, and web later becomes "just" the front-end + deployment + the gating items already researched (hosting ~£4–7/mo, accounts declined for a mailing list, tax within likely £1,000 allowance — see `08_Examen_Web_Design_Spec.md` §8). Est. ~10–15 focused days *if* it goes well; soft estimate (new stack).

## Phase 3b — Distributable Observatum (winter / as time allows)

| Component | Est. |
|-----------|------|
| Module registry — config-driven tab list, tabs self-register | 1 day |
| Conditional dependents — stats, filters, exports, backup tables check enabled modules | 1 day |
| First-run setup wizard (data location, modules, db provisioning via db_config.py) | 1 day |
| De-personalisation sweep (iRecord account → settings, no user-specific paths) | 0.5 day |
| PyInstaller packaging (~150 MB with databases) | 1–2 days |
| Licensing/attribution screens (UKSI CC BY, JNCC + Pantheon OGL) | 0.5 day |

Shares first-run/packaging/de-personalisation work with the distributable Examen tier.

## Estimate summary (focused working days, not calendar time)

| Build | Est. | When |
|---|---|---|
| Phase 1 — taxonomy refresh script | 0.5–1 | field-season-safe, now |
| Phase 1 — schema columns (data-entry prereq) | 0.5 | now |
| Phase 1 — rebuild-all chain + build_pantheon recovery | ~1 | now |
| **Desktop Examen (personal)** | **5–8** | winter, first |
| Desktop Examen (distributable add-on) | +3–5 | winter, follow-on |
| **Data Entry View** | **4–6** | winter, after Examen |
| Distributable Observatum | ~5–6 | winter / later |
| Web Examen | 10–15 | future, if justified |

**Caveat:** these are *focused* days. Done in evenings and rainy days, each multiplies into weeks of calendar time — hence the big builds are winter work, one major build per winter being realistic for a solo developer.

---

## Risk Register (from June 2026 evaluation, post-Phase-0)

| Issue | Severity | Status |
|-------|----------|--------|
| No version control | High | ✅ Closed (Phase 0) |
| SQLite WAL + OneDrive sync | High | ✅ Mitigated (Phase 0; per-operation connections narrow the window) |
| Stale TVKs in observatum.db | Medium, compounding | Phase 1 item 5 |
| Tabella bakes Codex at generation time | Medium | Phase 1 item 6 |
| examen.db orphaned by desktop retirement | Medium | Backup added (Phase 0); home decision = Phase 2 item 9 |
| Observatum's unmigrated Codex touchpoints (conservation_override.py, rare.py, profile display) | Low–medium | Opportunistic; checklist item per Observatum session |
| build_pantheon_db.py missing | Low | Phase 1 item 7 |
| examen/munia backup gap | Low | ✅ Closed (Phase 0) |
| Doc drift | Low | ✅ Closed (Phase 0) |
| UKSI licensing for redistribution | Pre-launch | Phase 2 item 10 |

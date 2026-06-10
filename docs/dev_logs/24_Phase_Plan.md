# Development Phase Plan

## Date: 10 June 2026 (Session 26)
## Origin: Suite-wide architecture evaluation, June 2026

---

## Strategic Decisions (settled this session)

1. **Evolve, don't rewrite.** The current codebase is the final software. Development continues in place, protected by git branching (`stable` for field season, `main` for development).
2. **Modularisation is a registry layer, not a rebuild.** Observatum tabs become config-driven modules so distributed copies can omit e.g. Recording Scheme or ship Mapping as "preview". Estimated ~5–6 days (winter).
3. **Pilot distribution** target: 2–3 trusted colleagues, not public release.
4. **Priority recommendation** (not yet confirmed): distributable modular Observatum before web Examen.

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

## Phase 2 — Decisions (one session, paper only)

| # | Decision | Gates |
|---|----------|-------|
| 9 | Frozen assessments home: web "full freeze" on owner account vs slim local archive tool | Web accounts schema |
| 10 | UKSI licence confirmation for redistribution | Both web Examen and desktop distribution |
| 11 | Priority: web Examen vs distributable Observatum first | Phase 3 scope |

## Phase 3a — Web Examen Build (winter, if chosen)

Stack decisions → analysis API around `shared/` → anonymous flow end-to-end → report generation → accounts/donor tier → Codex file-sync + version stamping → species profiles. Spec: `08_Examen_Web_Design_Spec.md`.

## Phase 3b — Distributable Observatum (winter, if chosen)

| Component | Est. |
|-----------|------|
| Module registry — config-driven tab list, tabs self-register | 1 day |
| Conditional dependents — stats, filters, exports, backup tables check enabled modules | 1 day |
| First-run setup wizard (data location, modules, db provisioning via db_config.py) | 1 day |
| De-personalisation sweep (iRecord account → settings, no user-specific paths) | 0.5 day |
| PyInstaller packaging (~150 MB with databases) | 1–2 days |
| Licensing/attribution screens (UKSI check, JNCC + Pantheon OGL) | 0.5 day |

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

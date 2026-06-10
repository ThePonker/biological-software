# Examen Web — Design Spec

## Date: 10 June 2026
## Supersedes: 08_Examen_Design_Spec.md (24 March 2026 — desktop application)

---

## Status

The desktop Examen was **retired on 16 April 2026**. Code archived at `_archive/Examen_desktop_20260416/`; removed from Atrium. The three desktop views (Species Database, Site Analysis, Assessment Archive) reached working state before retirement and remain the functional reference for what the web product must do.

The replacement is a **web-based, donation-supported application** — the Wikipedia model, not subscription. The build has not started; this document captures the agreed design so the build phase starts from settled decisions. The authoritative treatment of Codex's role is `07_Codex_Design_Spec.md` section 7.

---

## What It Is

A browser-based replacement for the Natural England / CEH Pantheon website for invertebrate assemblage assessment. Users submit a species list (paste or file upload), receive analysis (SQI, key species, biotopes, SATs, guilds, full status appendix), and download a report.

## Why

The Pantheon website is manually operated, clunky, unfunded, and frozen on 2017 conservation data. Examen runs the same class of analysis on current Codex data (JNCC Dec 2023 + ongoing review imports) with Pantheon's irreplaceable ecology tables underneath.

---

## Architecture

| Layer | Decision |
|-------|----------|
| Analysis engine | `shared/services/pantheon_analysis_service.py` + `CodexRepository` + `PantheonRepository` — the same code that powered desktop Examen, already UI-agnostic |
| Reference data | Read-only copies of codex.db and pantheon.db on the server |
| Sync | **Option 1 — file sync.** Local Atrium Codex is authoritative; after each rebuild, upload codex.db (and pantheon.db if changed) to the server. Version stamp from `build_log` |
| Versioning | Every analysis result carries the Codex build version it was computed against; saved summaries record it permanently |
| Accounts storage | Summary metrics only — site name, survey year, species count, SQI, key species count |
| Web framework / hosting / auth / donations | **Undecided — Phase 3a opening decisions** (see 24_Phase_Plan.md) |

## Privacy Model (agreed)

- Species lists submitted for analysis are **never stored, logged, or cached** — processed, returned, discarded
- Logged-in users may opt to save **summary metrics only** per assessment
- Codex/Pantheon are reference data carrying no user information

## Tiers

| Tier | Gets |
|------|------|
| Anonymous (free) | Full analysis, full report download, all conservation statuses |
| Logged-in donor | Saved assessment history, averages across past sites, species profiles inline |

Species profiles (`species_profiles` table, populated by review imports) are the donor differentiator — coverage grows with every imported review at no extra infrastructure cost.

---

## Runtime Data Flow

1. Browser sends species list to server
2. Server resolves each species via CodexRepository (status, SQS, profile) and PantheonRepository (ecology)
3. PantheonAnalysisService computes SQI, key species, assemblage breakdown
4. Browser renders results; server generates downloadable PDF/Excel report
5. Optional "Save summary" → one row of numbers to the user's account
6. Species list discarded

---

## Open Decisions Before Build (Phase 2 / 3a)

1. **Frozen assessments**: the web model stores summaries only, but the suite's own commercial workflow needs full reproducible frozen assessments (species list + all metrics + Codex version), formerly examen.db's job. Options: a "full freeze" capability on the owner account, or a slim local archive tool. Gates the accounts schema.
2. **UKSI licensing**: confirm terms for serving UKSI-derived taxonomy from a public server. JNCC content is OGL (attribution required); Pantheon is OGL.
3. **Stack**: framework (Flask / FastAPI / Django), hosting target, auth provider, donation mechanism.

## Build Order (when Phase 3a starts)

1. Stack decisions
2. Analysis API wrapping `shared/` services
3. Anonymous flow end-to-end (submit → results)
4. Report generation (PDF/Excel server-side)
5. Accounts + donor tier
6. Codex sync + version stamping
7. Species profile display

---

## Inherited Functional Reference (from desktop)

The archived desktop views define the expected outputs: key species count and three-tier percentages, SQI overall and per biotope/habitat/SAT, habitat breakdowns, SAT representation, guild composition, taxonomically sorted species appendix with status columns, Codex Full vs Pantheon Only comparison mode, freeze workflow. The web product should match or consciously simplify — not silently drop — these.

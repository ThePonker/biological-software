# Examen — Revival Assessment

## Created 29 August 2026 (Session 29)
## **REVISED 5 September 2026 (Session 32) — §4 was wrong. Examen was run.**
## Companions: `08_Examen_Web_Design_Spec.md`, `02_Current_Session_Summary.md`

---

## 0. Correction notice (Session 32)

This file's central finding — that `examen_data.py` queries dead 8-track names and would
report **zero key species** — was **wrong**, and it was carried forward into four other
documents and used to gate the whole revival with "Examen must not be run".

Examen was run on 5 September. It worked. Glory Park returned 128 species and 12 key species
with tiers, statuses, SQS and Pantheon ecology all populated.

Two things had been conflated:

- **`_load_codex_data` had already been fixed.** It delegates to
  `CodexRepository.get_statuses_batch` and `get_sqs_scores`, with a docstring saying
  explicitly that it does so "rather than querying codex.db directly … so Examen and the
  analysis service cannot disagree." Someone did this after §4 was written.
- **`PANTHEON_GB_STATUS_MAP` and `_classify_tier` do use names like `gb_rarity` and
  `section_41`** — but those are **local dictionary keys built from Pantheon's own
  `conservation_status` categories**, inside the `PANTHEON_ONLY` path. They never touch
  codex.db. The comment "Mirror of CodexRepository mapping — keep in sync" is misleading.

**The stale 8-track mirror was real, but it was in `species_database_view.py`** — where it
had left the Conservation status panel blank for every species since April, and crashing for
any legally protected one. Fixed Session 32.

The lesson stands, but it is a different lesson: *a finding written from reading is a
hypothesis until the thing is run.* Five documents repeated this one without testing it.

§§1–3 and 5–9 below remain accurate. §4 is retained for the record with this correction.

---

## 1. Why this file exists

Session 26 decided Examen would be **built fresh**, treating
`_archive/Examen_desktop_20260416/` as "structural reference only". That judgement was made
without reading the archived code.

Reading it showed the retirement decision was too pessimistic. **Running it showed the
revival was already largely done.**

Revised estimate: not 5–8 days, not 2–3 days of repair — a **working tool needing
presentation fixes**. See §8.

---

## 2. What Wil actually wants from it

Examen is not primarily "an app" — it is **two reference databases plus an analysis layer**:

- **Pantheon ecology** (`pantheon.db`) — biotopes, habitats, SATs, guilds, fidelity,
  associations. No alternative source; frozen at 2017. Consumed as-is.
- **Codex** (`codex.db`) — conservation status and legal protection. His to maintain.
- **Species profiles** — see §6; a three-way split, unbuilt.
- **The analysis** — a site list checked against both.
- **Consumers** — Observatum displays it; the report generator writes it up.

Pantheon ecology has **no editor at all**. That gap remains (backlog G8).

---

## 3. What was read

| File | Verdict (updated Session 32) |
|---|---|
| `shared/repositories/codex_repository.py` | **Current.** 11-track. Now also jurisdiction-aware. |
| `shared/services/pantheon_analysis_service.py` | **Current.** Now carries structured tracks on `KeySpeciesEntry` and normalises guild casing. |
| `shared/repositories/pantheon_repository.py` | Current. |
| `examen_data.py` | **Not stale in the way claimed** — see §0. Real issues in §4.3. |
| `site_analysis_view.py` | Sound. Runs. |
| `overview_tab.py` | Sound. Two punctuation slips in the generated sentence. |
| `habitat_tab.py` | Sound. |
| `assemblage_tab.py` | Sound; `sat_thresholds.json` present and verified. |
| `conservation_tab.py` | **Was inventing Section 41** — fixed Session 32. |
| `species_database_view.py` | **Was the stale 8-track file** — fixed Session 32. |
| `appendix_export.py` | Sound; labelling fixed via `display_status`. |
| `assessment_archive_view.py` · `snapshot_manager.py` | Read; fate undecided (G6). |
| `import_species_dialog.py` · `manual_entry_dialog.py` · `examen_ui.py` | Read. |

---

## 4. The original finding (retained, superseded — see §0)

*The claim was that `examen_data.py` carries its own copy of the status mapping, that the
April rebuild moved Codex from 8 tracks to 11, and that the copy did not follow, so
`_classify_tier` would receive a nearly empty dict and key species would come back as zero.*

*That was described as "the dangerous failure mode: plausible-looking output that is silently
wrong."*

**It was not happening.** But the description of the failure mode was exactly right — it
just applied to `conservation_tab`, which was **inventing** a Section 41 count rather than
losing one, and to `species_database_view`, which was showing nothing.

### 4.3 What is genuinely still wrong in `examen_data.py`

Smaller than "strip 250 lines", but real:

1. **`_classify_tier` duplicates `CodexRepository._classify` and has drifted.** It puts RDB3
   and RDBK in *scarce*; the repository treats the legacy RDB categories differently. So
   Codex-full and Pantheon-only modes classify tiers by different rules, which makes mode
   comparison unsound.
2. **The SQI arithmetic appears four times** — `round(sqs_total / sqs_count * 100)` and
   `sqs_count >= 15` in `load_site_detail`, `load_project_detail`, `_enrich_sites` and
   `_enrich_projects` — rather than calling `compute_sqi`.
3. **Two parallel enrichment paths on one screen.** The project table is enriched by
   `examen_data`, the detail tabs by `PantheonAnalysisService`. The visible cost is two
   different key-species percentages on the same screen (Infrastructure 62), and an appendix
   whose key and non-key rows come from different sources.

---

## 5. Secondary issues — status Session 32

- **`conservation_tab`** ✅ fixed. Reads structured tracks; priority jurisdictions and legal
  instruments counted under their own names; bars rescaled.
- **`sat_thresholds.json`** ✅ found and verified against Pantheon's own output.
- **Hardcoded colours** — still open (G9). Every view defines its own palette.
- **Guild casing** ✅ fixed in the analysis service. Habitats, biotopes and SATs were checked
  and have no case variants, so no SQI was affected.

---

## 6. Species profiles — a three-way split (agreed, unbuilt)

Both tables are empty and neither is aware of the other:

- `codex.db.species_profiles` — keyed on `tvk`, for review imports, ships with the database
- `observatum.db.species_profiles` — richer (`flight_period`, `habitat`, `image_path`,
  `notes`), with an editing dialog and ~8 display sites wired

**A decision is needed on which wins before either is filled** (backlog H1).

Content model: **review source text** (verbatim, cited, static) · **Wil's species account**
(reusable) · **the site paragraph** (per species *per assessment*, **generated** from the
records, not stored on the species or it is overwritten at the next site).

~100 profiles exist across ~10 Word documents.

---

## 7. Open questions

- **Freeze / snapshots** — Session 26 said the frozen record is the downloaded report;
  Session 29 said key-species exclusions should persist per assessment, which implies stored
  state. Now that jurisdiction filtering handles the main exclusion case automatically, the
  argument for storage is weaker. Reconsider (G6).
- **Which profile store wins?**
- **Does Pantheon ecology need an editor?**
- **The jurisdiction selector** — the parameter exists and defaults to England; Examen has no
  UI control. Needed before the tool is trusted on a Scottish or Welsh job.

---

## 8. Revised plan (Session 32)

Examen **works**. What remains is presentation and the report layer.

| Step | Content | Est. |
|---|---|---|
| ✅ | Restore the archive; run it; fix the 8-track view, guild casing, invented S41, appendix labels, jurisdiction | done |
| 1 | `examen_data` tidy-up — remove `_classify_tier`, route the four SQI copies through `compute_sqi`, resolve the parallel paths (G1, rescoped) | 0.5 day |
| 2 | Jurisdiction selector in the UI | small |
| 3 | Presentation items — G14, G15, G16, the two percentages, the stray punctuation | ~1 day |
| 4 | Compartment analysis (G10) | 0.5 day |
| 5 | Report renderers: Excel → PDF → Word (G7) | 2–3 days |
| 6 | Saproxylic SQI + IEC (G12) | ~3 days |
| 7 | Species profiles (H1–H3) | 1–2 days |

---

## 9. Lessons for the record

**The April rebuild renamed the status tracks.** `CodexRepository` was updated; two
hand-written mirrors were not — and the one that mattered was in a file this assessment
listed as "not yet read". *When a mapping is copied "to keep in sync", it will not stay in
sync.*

**A finding written from reading is a hypothesis.** This document's §4 was repeated in
`02`, `05`, `24`, `28` and `README` and gated the revival for a week. Ten minutes of running
the application would have disproved it. **Run the thing before writing that it cannot be
run.**

# Examen — Revival Assessment

## Created 29 August 2026 (Session 29)
## Supersedes the assumption in `24_Phase_Plan.md` that Examen is a fresh build
## Companions: `08_Examen_Web_Design_Spec.md` (analysis + report model),
## `08_Examen_Design_Spec.md` (superseded desktop design)

---

## 1. Why this file exists

Session 26 decided Examen would be **built fresh**, treating
`_archive/Examen_desktop_20260416/` as "structural reference only" because it predates the
11-track Codex. That judgement was made without reading the archived code.

It has now been read in full — all sixteen files, plus the three `shared/` modules it
depends on. **The retirement decision was too pessimistic.** Most of the archive is sound
and current; one file is stale, and it is stale in a specific, contained way.

Revised estimate: **2–3 focused days** to a working desktop Examen, not 5–8. Report
renderers are additional.

---

## 2. What Wil actually wants from it

Restated from the Session 29 discussion, because it differs from how the specs frame it.
Examen is not primarily "an app" — it is **two reference databases plus an analysis layer**,
with several consumers:

- **Pantheon ecology** (`pantheon.db`) — biotopes, habitats, SATs, guilds, fidelity,
  associations. No alternative source; frozen at 2017. Consumed as-is.
- **Codex** (`codex.db`) — conservation status and legal protection, from JNCC plus Wil's
  own status-review imports. His to maintain and extend.
- **Species profiles** — see §6; a three-way split, currently unbuilt.
- **The analysis** — a site list checked against both, producing the Pantheon metrics.
- **Consumers** — Observatum displays it; the report generator writes it up.

Both databases must be **easily editable** over the long term. Codex Manager covers Codex;
Pantheon ecology has **no editor at all** and is a read-only import. That is a gap the
current design does not address. (Natural England has funding for Pantheon again as of
2026, so upstream updates may resume — but Codex remains ahead on conservation, which is
the part that goes stale fastest.)

---

## 3. What was read

| File | Size | Verdict |
|---|---|---|
| `shared/repositories/codex_repository.py` | — | **Current.** v5, explicitly 11-track, `is_key`, `tier`, `get_statuses_batch`, `get_sqs_scores`, `compute_sqi`, `compare_modes`, invertebrate-only key-species logic. |
| `shared/services/pantheon_analysis_service.py` | — | **Current.** Calls CodexRepository correctly. Computes SQI overall and per biotope/habitat/SAT, key species by tier, guild composition, Codex-vs-Pantheon comparison. |
| `shared/repositories/pantheon_repository.py` | — | **Current.** Batch ecology lookups, chunked at 500. |
| `examen_data.py` | 22.2 KB | **STALE — see §4.** |
| `site_analysis_view.py` | 14.9 KB | Sound. Already takes `analysis_service` and calls it correctly. |
| `overview_tab.py` | 8.6 KB | Sound. Consumes `AnalysisResult`. |
| `habitat_tab.py` | 9.6 KB | Sound. Biotope→habitat tree, % representation, fidelity. |
| `assemblage_tab.py` | 6.0 KB | Sound, but needs `sat_thresholds.json` — **not present in the archive listing.** |
| `conservation_tab.py` | 7.0 KB | Works, but reverse-engineers status codes from a string — see §5. |
| `species_database_view.py` | 13.7 KB | Not yet read. |
| `assessment_archive_view.py` | 16.6 KB | Not yet read. Possibly obsolete — see §7. |
| `snapshot_manager.py` | 11.2 KB | Not yet read. Possibly obsolete — see §7. |
| `appendix_export.py` | 7.5 KB | Not yet read. The species table that goes in reports. |
| `import_species_dialog.py` | 9.9 KB | Not yet read. Paste/import path. |
| `manual_entry_dialog.py` | 9.7 KB | Not yet read. |
| `examen_ui.py` | 5.8 KB | Not yet read. Three-view shell. |

---

## 4. The core finding — a stale duplicate, not a stale app

`examen_data.py` does **not** use `CodexRepository`. It opens `codex.db` directly and
carries its own copy of the status mapping and tier classification. Line 20 says so:

```python
# Mirror of CodexRepository mapping — keep in sync
```

It did not stay in sync. The April rebuild moved Codex from 8 tracks to 11; this copy did
not follow. It queries `status_summary` for:

`gb_rarity`, `gb_rarity_legacy`, `gb_red_list`, `gb_red_list_legacy`, `section_41`

Codex now stores:

`rarity_modern`, `rarity_legacy`, `threat_iucn_2001`, `threat_iucn_legacy`, `priority`,
`legal_protection`, `bocc`, `specialist_panel`, `red_list_england`, `red_list_wales`,
`threat_global_iucn`

Only `legal_protection` survived the rename. So `_classify_tier` receives a nearly empty
dict, every species gets `tier = ""` and `short_status = ""`, and **key species count comes
back as zero**. SQI still computes, because `sqs_scores` is keyed on TVK and unchanged.

**This is the dangerous failure mode**: plausible-looking output that is silently wrong.
An SQI with zero key species would not obviously look broken in a report.

### 4.1 Two parallel analysis paths

`site_analysis_view` imports `load_all_projects` from `examen_data` **and** takes
`analysis_service` in its constructor. So:

- The **project table** at the top is enriched by the stale path → would show 0 key species
- The **detail tabs** below call `PantheonAnalysisService` → would show the correct figure

On the same screen. The inconsistency would at least be visible rather than silent.

### 4.2 The fix is a deletion

Remove from `examen_data.py`: `_load_codex_data`, `_load_pantheon_only_data`,
`_classify_tier`, `PANTHEON_GB_STATUS_MAP`, `_enrich_sites`, `_enrich_projects`, and the
SQI arithmetic inside `load_site_detail` and `load_project_detail`. Route all of it through
`PantheonAnalysisService`.

Keep what the file uniquely does: query `observatum.db` for sites, projects, pooled species
lists and accumulation curves.

Roughly **250 of 625 lines removed**, replaced by service calls.

---

## 5. Secondary issues

**`conservation_tab._parse_status`** reconstructs status codes by string-matching
`short_status` and falling back to the tier. Now that `CodexRepository` returns structured
tracks, it should read those directly. Its `CATEGORIES` list also has no `bocc`,
`red_list_england`, `red_list_wales` or `threat_global_iucn`.

**`sat_thresholds.json`** is required by `assemblage_tab` for Favourable Condition
thresholds and did not appear in the archive file listing. Locate it or the FC column is
dead.

**Hardcoded colours.** Every view file defines its own palette constants rather than using
`theme()`. Contrary to the project's own coding rule 6. Cosmetic, but it means a restyle
touches six files.

---

## 6. Species profiles — a three-way split (agreed, unbuilt)

Both profile tables are **empty**:

- `codex.db.species_profiles` — keyed on `tvk`, designed to receive review imports
- `observatum.db.species_profiles` — keyed on `species_tvk` *and* `species_name`, richer
  schema (`flight_period`, `habitat`, `conservation_status`, `image_path`, `notes`), written
  by `species_profile_dialog.py`, read by ~8 display sites

Two stores, two schemas, neither aware of the other, both unpopulated. **A decision is
needed on which wins before either is filled.**

Agreed content model:

1. **Review source text** — the account from the published review, verbatim, with citation.
   Static per species. Reference material.
2. **Wil's species account** — his own text, written from the source plus his own knowledge.
   Reusable across reports.
3. **The site paragraph** — *"three individuals were found on these dates from these
   parcels"*. This is **per species per assessment**, not a property of the species. It
   should be **generated** by the report writer from the records, then edited — not stored
   on the species, or it gets overwritten at the next site.

Wil has ~100 profiles already written, spread across ~10 Word documents. Extraction with
`python-docx` is feasible; difficulty depends on whether they are one-per-heading or prose
embedded in survey reports.

---

## 7. Open questions

- **Is `snapshot_manager` / `assessment_archive_view` still wanted?** Session 26 decided the
  frozen record is the downloaded report, not a stored assessment. `examen.db` holds
  historical frozen assessments and is currently orphaned. If freeze is dropped, two files
  and a database go with it — but the historical assessments would need somewhere to live.
- **Which profile store wins?** See §6.
- **Does Pantheon ecology need an editor?** Nothing can currently correct or extend it.
- **Sequencing** — Wil needs assessments working as identifications wrap up. Profiles can
  follow; the site paragraph depends on the report writer existing anyway.

---

## 8. Revised plan

| Step | Content | Est. |
|---|---|---|
| 0 | Read the six unread files (`examen_ui`, `species_database_view`, `appendix_export`, `import_species_dialog`, `manual_entry_dialog`, `snapshot_manager`) | 0.5 day |
| 1 | Restore the archive to `Examen/`; strip the stale enrichment from `examen_data.py`; route through `PantheonAnalysisService` | 0.5–1 day |
| 2 | Fix `conservation_tab` to read structured tracks; add the missing track categories | 0.5 day |
| 3 | Locate or rebuild `sat_thresholds.json` | small |
| 4 | Test against a real staged job; compare against a known Pantheon result | 0.5 day |
| 5 | Report renderers: Excel → PDF → Word | 2–3 days |
| 6 | Species profiles: schema decision, editor, Word extraction of the ~100 | 1–2 days |

**Steps 0–4: 2–3 days to a working assessment tool.** Steps 5–6 are the report layer and
can follow.

---

## 9. Lesson for the record

The April Codex rebuild renamed the status tracks. `CodexRepository` was updated;
`examen_data.py`'s hand-written mirror was not, and nothing detected it because Examen had
already been retired. The retirement then meant nobody looked again.

This is the third instance in two days of **the same rule written down twice and drifting**
— alongside `SRC_SETTING_KEYS` in the info panel and the doubled import-notes append. Worth
treating as a standing risk: when a mapping is copied "to keep in sync", it will not stay
in sync.

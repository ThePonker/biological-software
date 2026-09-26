## Session 29 additions — Examen and species profiles

> Paste at the end of `28_Development_Backlog.md`, before section F.
> Full analysis in `29_Examen_Revival_Assessment.md`.

---

## G. Examen (Pantheon replacement)

### G1. Strip the stale enrichment from `examen_data.py` — **HIGH**
**Size:** 0.5–1 day
**Trigger:** blocking the whole Examen revival. The archived file queries Codex for
8-track names that no longer exist, so key species would come back as **zero** while SQI
computed normally — plausible-looking, silently wrong output.

Delete `_load_codex_data`, `_load_pantheon_only_data`, `_classify_tier`,
`PANTHEON_GB_STATUS_MAP`, `_enrich_sites`, `_enrich_projects` and the inline SQI arithmetic.
Route through `PantheonAnalysisService`, which is current. Keep the Observatum queries.

### G2. Restore the archive to `Examen/` — **HIGH**
**Size:** small
`Examen/` is empty; all sixteen files are in `_archive/Examen_desktop_20260416/`. Do this
with G1, not before — the stale path should never run against live Codex.

### G3. Fix `conservation_tab` to read structured tracks
**Size:** 0.5 day
`_parse_status` reverse-engineers codes from a display string. Read `SpeciesStatus` tracks
directly instead. `CATEGORIES` is also missing `bocc`, `red_list_england`,
`red_list_wales`, `threat_global_iucn`.

### G4. Locate or rebuild `sat_thresholds.json`
**Size:** small
`assemblage_tab` needs it for Favourable Condition thresholds; it was not in the archive
listing. Without it the FC and PtT columns are dead.

### G5. Read the six unread archive files
**Size:** 0.5 day
`examen_ui`, `species_database_view`, `appendix_export`, `import_species_dialog`,
`manual_entry_dialog`, `snapshot_manager`. Needed before the estimate is firm.

### G6. Decide the fate of freeze / snapshots
**Size:** decision, then small
Session 26 decided the frozen record is the downloaded report, not a stored assessment. If
that holds, `snapshot_manager.py`, `assessment_archive_view.py` and `examen.db` are
obsolete — but the historical assessments in `examen.db` need a home first.

### G7. Report renderers — Excel, then PDF, then Word
**Size:** 2–3 days
Three rendering paths from one computed result. Excel first (proves the pipeline), PDF is
the flagship, Word is the editable one.

### G8. Pantheon ecology has no editor
**Size:** unscoped
`pantheon.db` is a read-only import with no way to correct or extend it. Natural England
has funding again as of 2026, so upstream updates may resume — but nothing can be fixed
locally in the meantime.

### G9. Views hardcode their own colour palettes
**Size:** 0.5 day
Every Examen view defines its own constants rather than using `theme()`. Contrary to coding
rule 6; a restyle currently means editing six files.

---

## H. Species profiles

### H1. Decide which profile store wins — **HIGH, blocks H2–H4**
**Size:** decision
Two empty tables with different schemas: `codex.db.species_profiles` (keyed on `tvk`,
built for review imports, ships with the database) and `observatum.db.species_profiles`
(richer — `flight_period`, `habitat`, `image_path`, `notes` — with an editing dialog and
~8 display sites already wired). Neither is aware of the other.

### H2. Three-way content model
**Size:** 0.5–1 day after H1
Agreed structure:
1. **Review source text** — verbatim from the published review, with citation. Static.
2. **Wil's species account** — his own text, written from the source. Reusable.
3. **The site paragraph** — *"three individuals on these dates from these parcels"*.
   Per species **per assessment**; must be **generated** by the report writer from the
   records, not stored on the species, or it is overwritten at the next site.

### H3. Extract ~100 existing profiles from Word
**Size:** 0.5–1 day
Roughly 100 profiles across ~10 `.docx` files. `python-docx` handles the reading; the work
is in whether they are one-per-heading or prose embedded in survey reports.

### H4. Profiles are written only for species with a conservation status, or groups of
interest (e.g. Cerambycidae)
**Not a task** — a scoping decision, recorded so nobody plans for full coverage.

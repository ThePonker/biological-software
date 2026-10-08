# Examen

## Invertebrate assemblage assessment
## Updated 8 October 2026
## Supersedes `29_Examen_Revival_Assessment.md`, whose central finding was wrong,
## and the desktop portion of `08_Examen_Web_Design_Spec.md`.

---

## 1. What it is

A desktop tool that takes a species list and produces a conservation and
assemblage assessment: SQI, key species, habitat and SAT breakdowns, guild
composition, and a species appendix.

It replaces the Pantheon website for the thing most people use it for. Pantheon
is unfunded, manually operated, and its conservation data is frozen at 2017.
Examen uses **Pantheon's ecology** — which has no alternative source — with
**Codex's conservation status**: JNCC's June 2026 spreadsheet plus 35 published
reviews imported directly (among them the 2019 macro-moth Red List, which JNCC
does not carry), on the July 2025 UKSI.

**It works, it exports, and it reproduces the Pantheon website.** Glory Park's
SQI, species analysed, key species and two habitat SQIs match the issued report
exactly (§6). It reads your records and contributed records together (§12). What
remains is PDF, Word, presentation — and one decision about the summary sentence
(§9).

---

## 2. A correction worth keeping

For a week, five documents said `examen_data.py` was stale, would report **zero
key species**, and that Examen must not be run.

All of that was wrong. `_load_codex_data` had already been fixed to delegate to
`CodexRepository`. The 8-track names in that file are local dictionary keys in
the Pantheon-only path and never touch `codex.db`. Examen was run on 5 September
and worked first time.

The stale 8-track mirror was real, but in `species_database_view.py`.

**The lesson, now in `05_Rules.md`: a finding written from reading is a
hypothesis until the thing is run.** Ten minutes would have disproved it.

---

## 3. Architecture

```
Examen/
├── examen_ui.py                 Three-view shell
├── examen_data.py               assessment_records queries; survey-year scoping;
│                                load_taxonomy() -- the one UKSI lookup
├── site_analysis_view.py        Project table + five detail tabs
├── overview_tab.py              SQI, key species, tier split, biotopes
├── habitat_tab.py               Biotope → habitat tree, fidelity indices
├── assemblage_tab.py            SATs with FC thresholds and PtT %
├── species_tab.py               Full species table with filters
├── conservation_tab.py          Status breakdown by category
├── species_database_view.py     Per-species browser
├── appendix_export.py           The single-sheet species appendix
├── workbook_export.py           The multi-sheet assessment workbook (E2)
├── import_species_dialog.py     Paste / import a list
├── manual_entry_dialog.py       DISABLED 6 Oct -- could empty Codex's
│                                manual_entries; delete with backlog I8
├── snapshot_manager.py          Freeze — fate undecided
└── sat_thresholds.json          Verified against Pantheon's own output
```

Analysis lives in `shared/` — `CodexRepository`, `PantheonRepository`,
`PantheonAnalysisService` — so a web front end could sit on the same engine
later.

---

## 4. The survey-year model

**A project may hold several surveys.** Bicester Graven Hill is 2023 (367
species, synced to iRecord) and 2025 (254 species, embargoed) under one name.
Pooled, they make a 519-species list that corresponds to no report.

The project table shows **one row per project per survey year** by default, with
a "Pool years" checkbox to combine them deliberately. Selecting a row scopes the
whole analysis to that survey.

This matters more than it sounds. The file submitted to Pantheon for the 2025
Bicester report holds 1,163 records **all dated 2025**, of which 181 species are
absent from the 2025 iRecord template and 166 are known 2023 records. The
report's headline of 433 species is the cumulative list, submitted with every
date restamped into the 2025 window because the tool needed a single date range.
**Survey-year scoping removes the reason for that.**

Known limit: a survey spanning a year boundary would split across two rows. No
current work does.

---

## 5. Jurisdiction

Key-species classification is **jurisdiction-aware, defaulting to England**. See
`02_Current_State.md` §4 for the reasoning and the resulting figures.

Short version: Section 41 is England's list, made under English law, and a
Scottish Ministers' list carries no weight in an English planning determination.
For an English site, S41 and UK BAP confer key status; SBL, NI Priority and Env
(Wales) Act S7 do not. Rarity and threat are GB-wide and unfiltered. Every
designation is still stored and displayed.

**The jurisdiction is a property of the site, not the session**, so it is read
from the data rather than left as a mode that can be forgotten. The combo
defaults to *Auto (vice-county)*, takes the commonest country across the
survey's records, and the header states the result:

> *BAM Glory Park — 2024 — Nicholsons — assessed under England (from vice-county)*

| Watsonian VC | Country |
|---|---|
| 1–34, 36–40, 53–70 | England |
| 35, 41–52 | Wales |
| 71 | Isle of Man |
| 72–112 | Scotland |

Where no usable VC exists — an imported list, or records without one — it falls
back to England and says *"(default)"*, so an assumption is never presented as a
reading. Explicit settings remain for cross-border projects; Northern Ireland has
no Watsonian VC and must be chosen. Changing the combo asks you to re-select the
project rather than silently re-running, so the header and the figures never
disagree.

The workbook stamp records the jurisdiction actually used.

---

## 6. Validation

**Glory Park 2024 reproduces the issued report** (Pantheon website, v3.7.6):

| | Report | Examen |
|---|---:|---:|
| Species / analysed by Pantheon | 128 / 123 | 128 / 123 |
| Key species | 8 | 8 — the same eight |
| SQI | 117 | 117 |
| Tall sward & scrub | 53 spp / 123 | 53 / 123 |
| Short sward & bare ground | 41 spp / 129 | 41 / 129 |
| Open habitats | 96 spp / 123 | 96 / 125 |

**This was not true until 2 October.** The September comparison stopped at key
species; Examen's SQI was 134. Two faults lay behind the gap — 4,026 Pantheon
scores dropped by the Codex build, and the wrong divisor. See `06_Faults.md`. The
open-habitats residual is most likely a 3.7.4 / 3.7.6 score difference.

The comparison also found three status disagreements **within the report** — the
prose accounts give *Hypera meles*, *Larinus carlinae* and *Hippodamia variegata*
as Na, while table 5.4 gives all three as Nb. Examen resolves them. That is
exactly the hand-transcription slip a generated appendix removes.

**Bicester validated the jurisdiction rule in both directions.** The 2025 report
names four S41 species — Grizzled Skipper, Dingy Skipper, Small Heath, Wall
Brown. Small Heath and Wall Brown each carry five priority jurisdictions; the
filter **keeps** them because one is Section 41, while dropping bees listed only
in Scotland and Northern Ireland.

**The reports already do things the software should support.** The Multiple Visit
table lists *Tyria jacobaeae* as "Section 41 Research Only" — the distinction
that opened the whole investigation, handled by hand. And the 2025 report gives
seven compartments with their own counts and a stated 5% threshold, which is a
worked specification for backlog E6.

---

## 7. The two frameworks

**Pantheon** — SQI, key species, habitats, SATs, guilds. Used for Bicester,
Badshot Lea, Glory Park. **Implemented.**

**Saproxylic Quality Index + Index of Ecological Continuity** — Fowles 1999 /
Alexander 2024. Used for Kent Deadwood. **Not implemented at all.**

The saproxylic framework needs the **598-species** SQI list (not 605 — one species
was in the published list in error) and the 180-species IEC list graded 1–3. Both
are online at **khepri.uk**, along with the national site rankings that every
saproxylic report uses to position its site.

Thresholds must be configurable: Fowles puts national importance at SQI 500 and
international at 590, but Alexander — who revised the IEC — considers 500 *"set
much too high"* and works to 300+. IEC: >15 regional, >25 national, >80
international.

The two indices answer different questions and can disagree. Petworth Deer Park
is 27th in Britain on SQI and 17th on IEC; Piercefield Park has the highest IEC
of the Wye Valley sites but is *"not significantly better"* on SQI. A report
gives both and says so.

Until it exists, saproxylic work stays manual. Backlog E7, ~3 days.

---

## 8. What is fixed, and what it cost

Everything below was found and fixed on 5 September. Full detail in
`06_Faults.md`.

| | |
|---|---|
| **Conservation tab invented Section 41** | Inferred from the tier; Glory Park reported four S41 species with none on S41 |
| **Species Database view blank since April** | 8-track names; crashed on legally protected species |
| **3,666 species had no ecology** | `PantheonRepository` never used the TVK bridge |
| **Habitat tree was a cross-product** | Every habitat under every biotope with site-wide counts |
| **Guild counts split by casing** | Larval predators were 37 and 4; they are 41 |
| **Appendix labelled everything "S41/BAP"** | Now names the jurisdiction |
| **Two different key-species percentages** | Settled on total species recorded, matching the reports |
| **SQI arithmetic in four places** | Now one call to `compute_sqi` |
| **`_classify_tier` duplicated and drifted** | Removed; both modes now classify identically |
| **Per-TVK ecology loops** | Batched; over 1,500 round trips for a large project |

Found and fixed 2 October:

| | |
|---|---|
| **4,026 Pantheon scores dropped** | Codex build's invertebrate filter keyed on designations. Every SQI inflated |
| **SQI divisor** | Divided by scoring species; Pantheon divides by species analysed |
| **Derived scores unmarked** | Mixed into the SQI while the stamp said "Pantheon published" |
| **Research-only S41 / UK BAP counted as key** | Cinnabar, Latticed Heath — now never key |
| **Habitats under every biotope a species had** | Now Pantheon's own tree (`habitat_traits`) |
| **"Priority" / "Legal (1)" unexplained in exports** | Now jurisdiction- and instrument-named, greyed |
| **Order, family, common name blank in the workbook** | One `load_taxonomy()` for tab and exports |
| **Project table squeezed away** | Splitter floor, pinned across clicks; table sortable, dd/mm/yyyy |

Found and fixed 6 October, by static analysis:

| | |
|---|---|
| **"+ Add Manual Entry" could empty Codex** | The Species Database tab's dialog cleared every review status; button and routine disabled |

---

## 9. Remaining work

| | Item | Size |
|---|---|---|
| ~~E1~~ | ~~Jurisdiction in the UI~~ | ✅ done |
| ~~E2~~ | ~~Excel report renderer~~ | ✅ done |
| ~~E2b~~ | ~~Export button~~ | ✅ done |
| **E16** | **Decide the SQI verdict wording** | **decision** |
| E3 | PDF renderer | 1–1.5 days |
| E4 | Word renderer | 0.5–1 day |
| E5 | Resolve the two parallel enrichment paths | 0.5 day |
| E6 | Compartment analysis | 0.5 day |
| E7 | Saproxylic SQI + IEC | ~3 days |
| E8–E12 | Presentation, punctuation, palettes | ~1.5 days |
| E13 | Decide the fate of freeze / snapshots | decision |

**The SQI verdict needs deciding.** The Overview's summary sentence ends by
calling a site *of national importance* at SQI ≥200, *regional* at ≥150, *of some
conservation value* at ≥125. No published source has been found for those bands
— they are neither Pantheon's nor Fowles's. It is prose written to be lifted into
a report, asserting a conclusion the literature does not support in those terms.
Options: remove it; replace it with Telfer's sourced test; or keep the bands with
a stated source. See `06_Faults.md` F14.

**Then the PDF** — the document that actually gets attached to a report.

Done 8 October: E9 (red ▲ on an SQI from under 15 scoring species, on the
Overview, the project table and the assemblage table), E10 (Favourable Condition
stated with its evidence), E17 (the appendix export matches the workbook), E18
(dates and mode labels), E19 (taxonomic order, one rule: `examen_data.in_taxonomic_order`,
the specimen collection's order × 1,000,000 + UKSI sort_code), E20 (both SQIs on the
Overview), E21 (contributed records credited). Still open: E22 cosmetics.

---

## 10. The Excel workbook

`Examen/workbook_export.py`, delivered 6 September. Structure and conventions
follow `38_Report_Survey.md` — eleven published reports surveyed for what a
report actually contains.

| Sheet | Content |
|---|---|
| Summary | Metrics, both threshold conventions as notes, and the stamp |
| Key species | Rare Key first per Telfer, with accounts and occurrence evidence |
| Species appendix | Full list, computed footer (species, no-TVK, scoring, SQS, SQI) |
| Habitats | Biotope → habitat, SQI, % national pool |
| Assemblages | SATs with FC threshold and PtT, colour-coded at 100% and 80% |
| Guilds | Larval and adult composition |
| Status definitions | The three-version annex, generated |

Four principles, drawn from practice:

**Every figure carries its evidence.** "Favourable — 19 spp., threshold 15", not
"Favourable". "SQI 134 from 61 scoring species", not "SQI 134".

**Withhold what cannot be supported.** Below 15 scoring species the SQI is not
shown; the count appears instead.

**Show the arithmetic.** Each SQI note gives sum ÷ species analysed, how many
scored, and how many unscored Pantheon species counted 0.

**State the basis — both of them.** The Summary gives the SQI on current scoring
and on Pantheon's published scores alone; derived scores read "16 (derived)";
species Pantheon lacks read "no Pantheon data".

**Grey what does not count.** Designations from another jurisdiction, research-only
listings and Northern-Ireland-only legal instruments are shown, named, in grey
italic.

**Report the percentages, not a verdict.** Two conventions are in circulation —
Telfer (~10% Key and >1% Rare Key) and Kirby-Lambert (5–10% high, >10%
exceptional). The author cites whichever they use.

**Exclusions are visible.** Species without a TVK and species Pantheon cannot
analyse are counted in the footer rather than quietly dropped.

Species accounts come from both layers: published review accounts in Codex
(open-licence ones quoted with citation, others as a pointer) and your own in
`observatum.db.species_profiles` -- 141, which cover every key species on the
current surveys bar five. The site-specific closing sentence is **written**, with the workbook supplying the evidence after a
`[write occurrence]` marker — count, places, months.

---

## 11. What every report must carry

- **The Codex version, build date, JNCC designation date and Pantheon version**
  — from `codex.db.metadata` and `build_log`
- **Which SQS basis** — both are now always given: Pantheon's published scores,
  and current scoring including derived scores, with the derived species named
- **Which jurisdiction** the key-species filter used
- **Whether years were pooled**, and which
- **Attribution:** taxonomy from the UK Species Inventory (C. Raper, NHM),
  CC BY 4.0; conservation designations from JNCC, OGL; ecology from Pantheon
  (Natural England / CEH), OGL

Plus **two dates, not one**: when the fieldwork was done and when the assessment
was run. They can be years apart, and for a repeat survey or a cumulative
saproxylic index both are material. CIEEM gives survey data a two-year validity.

The first items are what make a figure reproducible in 2029. The attribution is a
licence condition.

---

## 12. Contributed records

Built 2 October 2026 for a joint survey (Birmingham – Wheels Park, with J. Moore).

A collaborator's records go into `observatum.db.contributed_observations`, never
into `observations`, so stats, mapping and the iRecord export cannot see them —
by construction, not by a filter every query must remember. Examen reads the
`assessment_records` view: `observations` UNION ALL `contributed_observations`,
with an `origin` column. All 13 of Examen's record queries read the view.

`scripts/import_contributed.py` takes a collaborator's spreadsheet: columns by
heading, UKSI matching via the review importer's `resolve()`, a site-centre grid
reference where none is given, VC derived, stage and method mapped, provenance on
every row, `--replace` for a corrected file. Apply refuses on any unmatched name.

Credited in the workbook (E21, 8 Oct): a "Contributed records" line in the Summary
stamp, and "contributed by …" in each species' occurrence evidence. Not yet built:
a browsing tab (K1).

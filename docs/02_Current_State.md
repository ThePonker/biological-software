# Current State

## 6 September 2026
## The only home for these figures. If a number appears elsewhere, it is a copy
## and it will drift.

---

## 1. Component status

| Component | State |
|---|---|
| **Observatum** | Active. Stats audited, iRecord sync verified, mapping functional, embargo, filter wizard. Delete Selected on the Observations tab. Add Specimen rebuilt two-column with a map and curatorial fields. |
| **Data Entry** | **In production.** 13 jobs, 12 active, ~2,373 staged rows. Nothing committed to `observations` yet. |
| **Examen** | **Runs, validated, and exports.** Site Analysis and Species Database working, survey-year scoping, **Excel workbook export delivered**. Remaining: PDF, Word, presentation. |
| **Codex** | Correct and reproducible as of today. 11 tracks, biodiversity-wide for status, invertebrate-only for SQS. |
| **Curator** | Working. Suborder support, Hemiptera sort override, label preview. Does not write curatorial fields. |
| **Tabella** | **Paused** August 2026. Workbooks migrated into Data Entry staging. |
| **Munia** | Capacity planner. Unchanged since June. |
| **Atrium** | Launcher — 4 app icons, 2 tool buttons. |

---

## 2. Database figures

### codex.db — 45.1 MB, rebuilt 5 September

| Table | Rows |
|---|---:|
| designations | 27,062 |
| status_summary | 25,426 |
| sqs_scores | 5,568 (all Pantheon-sourced; **0 derived**) |
| tvk_bridge | 14,161 |
| manual_entries / reviews / species_profiles | 0 |

`metadata` carries the provenance the report stamp needs: `version` 5.0,
`build_date` 2026-09-05, `jncc_date` 2023-12-06. `build_log.notes` gives
"JNCC Dec 2023, Pantheon v3.7.4, 11-track scheme".

Status tracks:

| Track | Rows |
|---|---:|
| threat_iucn_2001 | 9,455 |
| priority | 5,231 |
| rarity_modern | 3,107 |
| legal_protection | 2,579 |
| red_list_england | 1,819 |
| threat_iucn_legacy | 1,499 |
| rarity_legacy | 1,249 |
| threat_global_iucn | 271 |
| bocc | 173 |
| specialist_panel | 43 |

Bridge: 8,648 direct · 2,513 name · 3,000 synonym · 1,847 of those merged onto a
species another taxon already claimed · **68 unmatched** (mostly Odonata stored
under vernacular names in Pantheon — backlog F1).

1,519 designation rows reach no track. Most is deliberate (`NR-excludes` 732,
`NS-excludes` 666, `WL` 76); the rest is backlog F2.

### observatum.db — ~114 MB, WAL, `synchronous=FULL`

| | |
|---|---:|
| Observations | 24,034 (Commercial 4,511 / Personal 19,414) |
| With `irecord_id` | 1,178 / 18,758 |
| Specimens | 2,549, all ISO dates |
| Recording scheme | ~110,510 |
| Staging rows | ~2,373 across 13 jobs |
| Species profiles | 0 — table now carries `origin`, `source_review`, `source_year` |

All six curatorial columns are empty across all 2,549 specimens. New specimens
capture four of them; the backfill needs the bulk editor (backlog A1).

### The rest

| Database | |
|---|---|
| uksi.db | ~122k taxa. `common_names` 20,897 rows over 16,351 TVKs, one `preferred=1` each. English-only at extraction. |
| pantheon.db | 14,229 species, ecology only, frozen at 2017 v3.7.4. **11,311 SQS scores on five values — 0, 1, 4, 8, 16, 32. No score of 2 exists anywhere.** |
| vc_lookup.db | Functional; drives VC derivation in Data Entry |
| examen.db | Historical frozen assessments; orphaned; backed up on close |
| munia.db | Project allocations, day logs |
| gamification.db | Achievements |

---

## 3. Examen — validated

Glory Park 2024 reports **8 key species of 128**, which is exactly what the
issued report says: *"a total of 128 species were identified, eight of which had
a Nature Conservation Status and are considered Key Species."* Same eight
species, same tiers.

Bicester could not be compared directly. Examen scoped to 2025 gives 254 species;
the 2025 report says 433. The difference was traced: the file submitted to
Pantheon (`For_Pantheon_2025.xlsx`) holds 1,163 records **all dated 2025**
covering 440 species, of which **181 are not in the 2025 iRecord template and 166
are known 2023 species**. The report's headline is the cumulative 2023+2025 list,
submitted with every date restamped into the 2025 window because the tool needed
a single date range. **Examen's 254 is correct for the 2025 fieldwork.**

Survey-year grouping now removes the reason for that restamping.

### Key species by survey, after jurisdiction filtering

| Site | Year | Species | Key | SQI |
|---|---|---:|---:|---:|
| BAM Glory Park | 2024 | 128 | 8 | 134 |
| Badshot Lea | 2023 | 167 | 10 | 121 |
| Bicester Graven Hill | 2025 | 254 | 19 | 155 |
| Bicester Graven Hill | 2023 | 367 | 18 | 123 |
| Derby | 2025 | 230 | 5 | 119 |

Bicester pooled across years gives 519 species / 31 key / SQI 145 — a list that
corresponds to no report, which is why pooling is now an explicit choice.

SQI 134 from 61 scoring species.

**SQI figures moved on 5 and 6 September** through the ecology bridge fix, the
removal of derived SQS, the collision merges and the DD/NT correction. Anything
computed earlier will not reproduce. Issued reports are not being revised; what
matters is that every figure produced from now on carries a stamp saying what it
was computed against.

### Key Species vs Codex tiers — two vocabularies, deliberately

Codex's `_classify` gives Rare / Scarce / Priority and drives Examen's on-screen
tiers. **Telfer's Key Species / Rare Key Species is the published evaluation
framework** the profession cites, and it splits RDB differently: all Red Data
Book categories are Rare Key, where Codex puts RDB3 and RDBK in Scarce.

The workbook computes Key / Rare Key **in the report layer**, following Telfer
exactly, and leaves Codex's tiers untouched. Changing `_classify` would shift
every tier shown in the UI for no benefit.

Glory Park: 8 Key Species, **0 Rare Key** — none is RDB, IUCN Threatened, Data
Deficient or Nationally Rare. The site meets neither the 10% nor the 1%
threshold, consistent with the issued report's assessment of its value.

---

## 4. Where the numbers come from — jurisdiction

Key-species classification is **jurisdiction-aware, defaulting to England**.

Section 41 of the NERC Act requires a list of species of principal importance
*in England*, and the section 40 duty points public bodies at that list.
Reviewed English EcIAs scope S41 and never cite the Scottish Biodiversity List.
JNCC's own UK BAP invertebrate list is published with per-country Y/N columns.

So for an English site: **S41 and UK BAP confer key status; SBL, NI Priority and
Env (Wales) Act S7 do not.** Legal protection counts except the
Northern-Ireland-only instruments. Rarity and threat are GB-wide and unfiltered.

Every designation is still stored and displayed — an SBL listing recorded in
England remains visible in the appendix and worth a sentence. It simply does not
make the species a key species there.

**There is no UI control yet** (backlog E1). Needed before a Scottish or Welsh
job.

---

## 5. Recent history

### Session 33 — 6 September 2026

**Eleven published reports read in full** to establish what a report actually
contains — table formats, threshold conventions, status vocabulary, account
structure. Written up as `38_Report_Survey.md`, the specification for the report
layer. The authors include Telfer, who defined the Key Species framework, and
Alexander, who revised the IEC, both in their own words.

**The Excel renderer was built** (E2). Seven sheets, generated from a real
assessment, stamped with Codex version and build date, JNCC designation date and
Pantheon version. Validated against Glory Park.

**DD and NT were inflating 200 derived SQS scores.** `sqs_derivation.py` treated
Data Deficient as conferring Nationally Rare status and gave Near Threatened its
own score of 2, both documented as "Pantheon's practice". Neither is: no species
in `pantheon.db` scores 2, and Pantheon's published criteria list DD and NT only
as things a rare or scarce species *may also be*. 156 species were scoring 8 for
a DD alone — eight times the correct value. All corrected downward.

**Four quick checks, two of which came back clean.** `pantheon.db` correctly
distinguishes Wall and Small Heath from the research-only group, and carries no
bracketed unreliable-status flag — that is a website rendering, not stored data.

**Species profile provenance** added: `origin`, `source_review`, `source_year`,
so an account seeded from a published review stays distinguishable from Wil's own
writing.

### Session 32 — 5 September 2026

Started with a question about the S41 research-only moths. Ended with sixteen
patches, five Codex rebuilds and a validated assessment tool.

**Codex.** The priority track collapsed five jurisdictions into one slot per
species, losing 2,303 facts — UK BAP was at 12% of true coverage. Collapse ties
were broken by row order rather than by date, resolving 12 contests wrongly. The
TVK bridge had never consulted `uksi.synonyms`, dropping 3,000 species. All three
fixed; the bridge then took the 1,847 merged taxa too, with the incumbent's SQS.
Gap-filled SQS is now derived live from the published rule rather than stored —
525 of the 816 stored values did not follow it.

**Examen.** The revival premise was wrong: `examen_data.py` had already been
fixed, and the tool ran first time. The stale 8-track mirror was in
`species_database_view.py`, where it had left the status panel blank since April
and crashed for any legally protected species.

The worst find: `conservation_tab` inferred "Section 41" from the key-species
tier, so Glory Park — in Northamptonshire — reported four Species of Principal
Importance in England, **none of which is on Section 41**. Every other fault this
year lost or mis-chose facts; that one manufactured them.

Also: guild counts split by Pantheon's inconsistent casing; the appendix
labelling every priority listing "S41/BAP"; the habitat tree built from a global
join so every habitat appeared under every biotope with site-wide counts; and
3,666 species with no ecology because `PantheonRepository` never used the bridge.

**Three mistakes of mine worth recording**, all in `05_Rules.md`: a patch anchor
that was not unique, module constants placed after the class that used them as
defaults, and a diagnostic that imported the gap-fill table as though it were
Pantheon's published rule and produced a confidently wrong result.

### Sessions 30–31 — 2 and 4 September 2026

Backup system rebuilt around `shared/backup_service.py`; every `.db` copy now
uses SQLite's online backup API. **A restore was tested end to end for the first
time.** The Restore button was found never to have worked (`Path + str`). 568 MB
of obsolete databases cleared, including a July dev copy the standalone Data
Entry launcher would have opened by default. `uksi_extractor.py` found missing.
Examen researched across six documents.

### Session 29 — 28–29 August 2026

CSV safety net; pre-live snapshots pruned from 3.9 GB to two; grid sorting, row
insert/delete, Traps card, VC derivation; Add Specimen rebuilt with a map and
curatorial fields.

### Session 28 — 27 August 2026

Delete Selected; two latent crashes; 9 BOMs stripped. **The common-name filter
bug** — a GLOB class ending `...ŵŷwy` whose bare `w` and `y` excluded 7,997 of
20,897 names. 11 Tabella workbooks / 1,787 records migrated to staging.

### Session 27 — July–August 2026

The Data Entry View built, out of sequence, driven by the field season. Not
logged at the time; `09_Data_Entry.md` is reconstructed from the code.

### Sessions 22–26 — March to June 2026

Restructure into the Latin-named folders with `paths.py`. Codex widened to 11
tracks, biodiversity-wide. Field-season fixes including the species-search
rewrite and ISO date migration. iRecord recovery, 180 IDs preserved. Phase 0
hygiene: git, WAL checkpoint, backup coverage. Desktop Examen retired (a
decision later reversed).

# Current State

## 2 October 2026
## The only home for these figures. If a number appears elsewhere, it is a copy
## and it will drift.

---

## 1. Component status

| Component | State |
|---|---|
| **Observatum** | Active. Stats audited, iRecord sync verified, mapping functional, embargo, filter wizard. Insect Collection sidebar corrected; specimen sex shown in five places. Profile displays read both account layers through `shared/species_accounts.py`. |
| **Data Entry** | **In production, first real commit made 2 October** (Birmingham – Wheels Park, 172 records). Commit now sets `embargo_status`. |
| **Examen** | **Runs, and reproduces an issued report's SQI exactly** (Glory Park, 117). Reads `assessment_records`, so contributed records count. Workbook export carries both SQS bases, jurisdiction-greyed statuses and Pantheon's habitat nesting. Remaining: PDF, Word, presentation, the SQI verdict. |
| **Codex** | Rebuilt 2 October with the invertebrate filter corrected: **9,611 Pantheon SQS** (was 5,568). Review accounts stored per species per review. |
| **Contributed records** | **New, 2 October.** `contributed_observations` + `assessment_records` view + `scripts/import_contributed.py`. One collaborator so far (J. Moore). No browsing tab yet. |
| **Curator** | Working. Does not write curatorial fields. |
| **Tabella** | **Paused** August 2026. |
| **Munia** | Unchanged since June. |
| **Atrium** | Launcher — 4 app icons, 2 tool buttons. |

---

## 2. Database figures

### codex.db — 46.0 MB, rebuilt 2 October

| Table | Rows |
|---|---:|
| designations | 27,062 |
| status_summary | 25,426 (+ manual entries applied) |
| sqs_scores | **9,611**, all Pantheon-sourced; 0 stored derived |
| tvk_bridge | 14,161 |
| manual_entries | 1,148 (NECR702) |
| reviews | 1 — NECR702, id 1, licence not yet recorded |
| species_profiles | 287 — NECR702 review accounts, keyed `(tvk, review_id)` |

**SQS import, before and after the 2 October fix:**

| | Before | After |
|---|---:|---:|
| Invertebrate TVKs recognised | 7,076 (designations only) | 66,322 (UKSI: Animalia outside Chordata) |
| Pantheon scores kept | 5,568 | **9,611** |
| Dropped as "non-invertebrate collision" | 4,085 | 59 |
| Dropped as zero-SQS | 109 | 109 |

Status tracks and bridge passes unchanged from September (threat_iucn_2001 9,455;
priority 5,231; rarity_modern 3,107; legal 2,579; red_list_england 1,819;
threat_iucn_legacy 1,499; rarity_legacy 1,249; global 271; bocc 173; specialist
43 — bridge 8,648 direct / 2,513 name / 3,000 synonym / 68 unmatched; 1,847
merged).

**Research-only:** Pantheon lists 72 species as S41 research only; **62** reach
current TVKs through the bridge. The other 10 are treated as ordinary S41
(backlog F5).

### observatum.db — ~114 MB, WAL, `synchronous=FULL`

| | |
|---|---:|
| Observations | ~24,206 (24,034 + 172 committed 2 October) — *not re-measured* |
| Contributed observations | 162 (J. Moore, Birmingham – Wheels Park) |
| Vice-county filled | 4,169 backfilled 26 September; 0 missing where a grid ref exists |
| species_profiles (your own) | 0 — keyed on TVK; review accounts now live in Codex |

### Specimens — measured 26 September

| | |
|---|---:|
| Specimens | **2,745** |
| With a taxonomic sort key | 2,743 |
| Sex recorded | **602** (22%) |
| Preparation / condition / storage / drawer | 204 / 8 / 2 / 0 |

### The rest

| Database | |
|---|---|
| uksi.db | ~122k taxa. `common_names` 20,897 rows over 16,351 TVKs. |
| pantheon.db | 14,229 species, frozen at 2017 v3.7.4. 11,311 SQS scores on 0, 1, 4, 8, 16, 32. Holds Pantheon's biotope→habitat tree in `habitat_traits`. |
| vc_lookup.db, examen.db, munia.db, gamification.db | unchanged |

---

## 3. Examen — validated against an independent figure

**Glory Park 2024 reproduces its issued report**, whose figures came from the
Pantheon website:

| | Report | Examen |
|---|---:|---:|
| Species recorded | 128 | 128 |
| Analysed by Pantheon | 123 | 123 |
| Key species | 8 | 8 |
| **SQI** | **117** | **117** (144 ÷ 123) |
| Tall sward & scrub — species / SQI | 53 / 123 | 53 / 123 |
| Short sward & bare ground — species / SQI | 41 / 129 | 41 / 129 |
| Open habitats — species / SQI | 96 / 123 | 96 / **125** |

The one residual (open habitats, +2 in the sum over the same 96 species) is most
likely a score differing between Pantheon 3.7.4 here and 3.7.6 on the website.

**Until 2 October Examen gave Glory Park 134.** The September "validation" matched
key species and never compared the SQI. See `06_Faults.md`.

### Every survey, 2 October

SQI on current scoring (Pantheon's scores plus any derived) and on Pantheon's
published scores alone. Key species after the jurisdiction and research-only
rules.

| Survey | Species | Key | SQI | SQI (Pantheon only) | SQI before 2 Oct |
|---|---:|---:|---:|---:|---:|
| BAM Glory Park 2024 | 128 | 8 | 117 | 117 | 134 |
| Badshot Lea 2023 | 167 | 8 | 111 | 111 | 121 |
| Bicester Graven Hill 2023 | 367 | 17 | 108 | 107 | 123 |
| Bicester Graven Hill 2025 | 254 | 19 | 127 | 126 | 155 |
| Birmingham – Wheels Park 2026 | 195 | 7 | 118 | 105 | 146 |
| Derby 2025 | 230 | 4 | 101 | 100 | 119 |
| Fermyn Hall Wood Deadwood 2024 | 49 | 8 | 157 | 154 | 197 |
| Kent Deadwood 2024 | 393 | 76 | 181 | 175 | 247 |
| Long Hanborough 2025 | 118 | 10 | 112 | 111 | 122 |
| Machen 2024 (Wales) | 321 | 17 | 121 | 115 | 144 |
| Tilbury 2025 | 238 | 4 | 101 | 100 | 106 |

Saved as `sqi_after_denominator.txt` (and `sqi_before.txt`) for comparison by
`scripts/check_sqi_table.py`.

**Issued reports are not being revised** — they were built on the Pantheon
website and are unaffected. Any SQI taken from **Examen** between April and
2 October was inflated by 3–66 points. Badshot Lea's key species have moved from
the issued 10 to 8 (jurisdiction, then research-only).

### Birmingham – Wheels Park 2026 — the first joint survey

195 species: 130 Wil, 121 J. Moore, 56 shared. 7 key species (3.6%), 1 Rare Key
(*Cistogaster globosa*, RDB1). SQI **118** (217 ÷ 184), **105** on Pantheon's scores
(192 ÷ 182). Four derived scores: *Cistogaster globosa* 16, *Phaonia mediterranea*
4, *P. siebecki* 4, *Olibrus corticalis* 1.

### Key Species vs Codex tiers — two vocabularies, deliberately

Unchanged: the workbook computes Telfer's Key / Rare Key in the report layer and
leaves Codex's Rare / Scarce / Priority tiers alone.

---

## 4. Where the numbers come from

### Jurisdiction
Derived from the vice-county; England by default. For an English site, S41 and
UK BAP confer key status; SBL, NI Priority and Env (Wales) Act S7 do not. Legal
protection counts except the Northern-Ireland-only instruments. Rarity and threat
are GB-wide. **Research-only S41 and UK BAP listings confer key status nowhere.**
Every designation is still stored and shown — greyed where it does not count.

### SQI
**Sum of scores ÷ every species Pantheon analysed × 100** — scored species plus
those Pantheon holds ecology for but never scored, which count 0. This is
Pantheon's definition, and the issued reports' method sections say the same.

**Two bases are always reported.** *Pantheon only* uses the scores Pantheon
published (comparable with the website and the literature). *Current scoring*
adds scores derived by Pantheon's published rule from current Codex status, for
species Pantheon lacks or never scored — marked "(derived)" on every sheet.

### Habitats
A species' habitats are nested only under the biotope Pantheon places them in
(`habitat_traits`). Wet woodland sits under both tree-associated and wetland.

---

## 5. Recent history

### Session 36 — 2 October 2026

Started as a way to include a collaborator's records in an assessment; ended by
making Examen reproduce a Pantheon-website SQI exactly, which it had never done.

**Contributed records.** J. Moore's 162 records for Birmingham – Wheels Park went
into a new `contributed_observations` table, kept apart from `observations` so
stats and iRecord cannot see them by construction. Examen reads an
`assessment_records` view of both — 13 queries changed one word. Built in about
ten minutes on existing pieces. **The first real Data Entry commit** followed,
and found that commit set the embargo date but not `embargo_status`, so the batch
would have uploaded to iRecord. Fixed in code and data.

**The Birmingham workbook, reviewed line by line, exposed six faults in turn.**
Order/family/common blank in exports (one UKSI lookup now serves all). Cinnabar
and Latticed Heath counted as key though S41 research only — and then still key
through **UK BAP**, where the research-only category originated. A bare "Priority"
and "Legal (1)" that were really SBL, NI Priority and the NI Wildlife Order —
now named and greyed. Habitats nested under every biotope a species had — now
Pantheon's own tree. A derived SQS of 16 included silently while the stamp said
"Pantheon published".

**Then the big one.** "No Pantheon data" on the 7-spot Ladybird led to the Codex
build's invertebrate filter, which recognised a species as an invertebrate only
if it held a conservation designation. **4,026 Pantheon scores of common species
had been discarded since April**, inflating every SQI. Fixed from UKSI taxonomy.
Glory Park went 134 → 120 against its report's 117; the last 3 points were
Pantheon dividing by every species analysed, not just scored ones. With that,
**117 exactly.**

Also: the Site Analysis splitter no longer swallows the project table; the table
sorts by any column with numbers and dates sorted properly; dates dd/mm/yyyy;
7 Kent Deadwood records moved 2025 → 2024; `scripts/show_funcs.py` for reading
code without dumping files.

### Session 35 (continued) — 26 September evening

**Vice-county backfill**: 4,169 records filled from grid references; Machen now
assessed under Wales. Eight grid-ref/date errors corrected first (SV→SU,
dropped digits, a date in the grid-ref column). **Jurisdiction grey-out** on the
Conservation tab and workbook. **NECR702** (leaf beetles, Lane 2026) imported:
1,148 statuses, 287 accounts. **Species accounts split into two layers** — review
text in Codex keyed `(tvk, review_id)`, your own in `observatum.db` keyed on TVK —
with review ids now preserved across rebuilds, the importer writing to Codex, and
one shared reader behind every Observatum display. Editor and workbook column
still to do.

### Session 35 — 26 September 2026
Loose ends closed; two days of patches committed; off-site copy made and verified;
the jurisdiction patch found never to have applied, then applied.

### Session 34 — 12–13 September 2026
Specimen sex shown in five places; 338 specimens found missing from the Insect
Collection tree and restored; `SpecimenRepository` whitelists fixed.

### Session 33 — 6 September 2026
Eleven reports surveyed (`38_Report_Survey.md`); Excel renderer built; DD/NT
derivation corrected; profile provenance added.

### Session 32 — 5 September 2026
Sixteen patches, five Codex rebuilds: priority collapse, collapse tiebreak, bridge
synonyms, bridge-aware ecology, the invented Section 41, habitat cross-product.

### Earlier
Sessions 22–31: restructure, 11-track Codex, field-season fixes, iRecord recovery,
Data Entry built, backup system rebuilt, restore tested.

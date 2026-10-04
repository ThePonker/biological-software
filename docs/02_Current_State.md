# Current State

## 4 October 2026
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

### codex.db — 49.2 MB, rebuilt 4 October (rebuild test passed)

| Table | Rows |
|---|---:|
| designations | 27,062 |
| status_summary | 27,927 (JNCC 26,822 + manual entries applied) |
| sqs_scores | **9,611**, all Pantheon-sourced; 0 stored derived |
| tvk_bridge | 14,161 |
| manual_entries | 5,900 -- review statuses, withdrawals, superseded and old-name clearances |
| reviews | **21** |
| species_profiles | **2,263** review accounts, keyed `(tvk, review_id)` |

**Reviews loaded** (id: what, accounts; *S* = statuses written too):

| id | Review | Accounts |
|---|---|---:|
| 1 | Leaf beetles, NECR702 (Lane 2026) *S* | 287 |
| 2–4 | Sawflies Phases 1–3 (Musgrove 2022–24) *S*, internal reference only | 540 |
| 5 | Butterflies Red List (Fox et al. 2022) *S*, threat only | 0 |
| 6–15 | NE Species Status: darkling, soldier, wood-boring, clown, longhorn, scarab, Tachyporinae beetles; stoneflies; aquatic bugs; mayflies | 1,000 |
| 16 | Millipedes, centipedes, woodlice (Lee 2015) | 179 |
| 17 | Ground beetles (Telfer 2016), PDF | 51 |
| 18 | Larger Brachycera (Drake 2017), PDF | 33 |
| 19 | Dolichopodidae (Drake 2018) *S*, PDF | 59 |
| 20 | Lonchopteridae, Platypezidae, Opetiidae (Chandler 2017), PDF | 9 |
| 21 | Calyptratae, provisional (Falk & Pont 2017) *S* from data sheets, PDF | 300 |

**Status corrections (4 Oct), all surviving a rebuild:** 272 NS-excludes routed;
71 old statuses superseded by newer reviews; 9 withdrawn by review (judgement,
"not British", misapplied names); 3 old names; NECR234's 300 provisional statuses.
Rarity_modern 3,107 → 4,503. `check_legacy_conflicts.py` 0 / 0;
`check_old_names.py` 0; `check_newest_review.py` (2) 0, (1) 419 -- 265
Staphylinidae (scope, correct), ~130 acalyptrates (NECR217 next), ~20 loose.

**SQS import, before and after the 2 October fix:**

| | Before | After |
|---|---:|---:|
| Invertebrate TVKs recognised | 7,076 (designations only) | 66,322 (UKSI: Animalia outside Chordata) |
| Pantheon scores kept | 5,568 | **9,611** |
| Dropped as "non-invertebrate collision" | 4,085 | 59 |
| Dropped as zero-SQS | 109 | 109 |

JNCC status tracks (threat_iucn_2001 9,455;
priority 5,231; rarity_modern 4,503; legal 2,579; red_list_england 1,819;
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

### Every survey, 4 October

SQI on current scoring (Pantheon's scores plus any derived) and on Pantheon's
published scores alone. Key species after the jurisdiction and research-only
rules.

| Survey | Species | Key | SQI | SQI (Pantheon only) | SQI before 2 Oct |
|---|---:|---:|---:|---:|---:|
| BAM Glory Park 2024 | 128 | 8 | 117 | 117 | 134 |
| Badshot Lea 2023 | 167 | 8 | 111 | 111 | 121 |
| Bicester Graven Hill 2023 | 367 | 17 | 108 | 107 | 123 |
| Bicester Graven Hill 2025 | 254 | 20 | 127 | 126 | 155 |
| Birmingham – Wheels Park 2026 | 195 | 6 | 116 | 105 | 146 |
| Derby 2025 | 230 | 4 | 101 | 100 | 119 |
| Fermyn Hall Wood Deadwood 2024 | 49 | 8 | 157 | 154 | 197 |
| Kent Deadwood 2024 | 393 | 77 | 181 | 175 | 247 |
| Long Hanborough 2025 | 118 | 11 | 112 | 111 | 122 |
| Machen 2024 (Wales) | 321 | 17 | 121 | 115 | 144 |
| Tilbury 2025 | 238 | 4 | 101 | 100 | 106 |

Saved as `sqi_after_denominator.txt` (and `sqi_before.txt`) for comparison by
`scripts/check_sqi_table.py`.

**Issued reports are not being revised** — they were built on the Pantheon
website and are unaffected. Any SQI taken from **Examen** between April and
2 October was inflated by 3–66 points. Badshot Lea's key species have moved from
the issued 10 to 8 (jurisdiction, then research-only).

### Birmingham – Wheels Park 2026 — the first joint survey

195 species: 130 Wil, 121 J. Moore, 56 shared. **6 key species**, 1 Rare Key
(*Cistogaster globosa*, RDB1 -- tachinids are outside NECR234's scope). SQI **116**
(213 ÷ 184), **105** on Pantheon's scores (192 ÷ 182). *Phaonia siebecki* lost its
1991 Notable (withdrawn by NECR234, 4 Oct); *P. mediterranea* and *Blaesoxipha
plumicornis* now hold NECR234's provisional statuses.

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

### Session 37 — 4 October 2026

**Species accounts from the status reviews, and every status the newest one.**
Tie-ups first (off-site copy, licence). A coverage check against Pantheon found
**272 species' Nationally Scarce status discarded** by the build (NS-excludes)
-- hoverflies, water beetles, Empidoidea -- fixed. Sawflies (Musgrove, 3 phases)
extracted and loaded with a new generic `load_review.py`; butterflies 2022
(threat only); then 15 Natural England Species Status reviews -- ten from
spreadsheet columns, five from PDFs (ground beetles, Larger Brachycera,
Dolichopodidae with statuses, Lonchopteridae, Calyptratae) -- every account
verified sentence by sentence against an independent extraction. **2,263 review
accounts.** The accounts editor and a Record Detail accounts column (tab colours)
built; the workbook quotes open-licence accounts with citation.

Then the rule: **each species takes its status from the newest review that
assessed it**, judgement-exclusions included, scope-exclusions not. JNCC had not
enforced it: 71 old statuses beside newer ones, 9 withdrawn by later reviews, 7
old names, and the calyptrate review's 300 provisional statuses never imported.
All corrected; a full Codex rebuild then reproduced every figure. Birmingham 7 → 6
key, Kent 78 → 77. Backups pruned 2.8 GB; off-site copy 4–5× faster.

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

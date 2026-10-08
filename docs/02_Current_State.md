# Current State

## 8 October 2026
## The only home for these figures. If a number appears elsewhere, it is a copy
## and it will drift.

---

## 1. Component status

| Component | State |
|---|---|
| **Observatum** | Active. Stats audited, iRecord sync verified, mapping functional, embargo, filter wizard. Insect Collection sidebar corrected; specimen sex shown in five places. Profile displays read both account layers through `shared/species_accounts.py`. **141 of your own species profiles**, from eight reports (6 Oct). |
| **Data Entry** | **In production, first real commit made 2 October** (Birmingham – Wheels Park, 172 records). Commit now sets `embargo_status`. Species account opens from the grid (6 Oct). **Five more commits 8 October**: Elmley 47 (no embargo, by choice), Alsager 296, Sundon 198, Slade Green 445, Bristol 150 -- 1,136 records. A check the same morning found gaps (fault F28); fixed, and `scripts/check_data_entry_batches.py` now runs after a commit. |
| **Examen** | **Runs, and reproduces an issued report's SQI exactly** (Glory Park, 117). Reads `assessment_records`, so contributed records count. Workbook export carries both SQS bases, jurisdiction-greyed statuses and Pantheon's habitat nesting. Remaining: PDF, Word, presentation, the SQI verdict. |
| **Codex** | Rebuilt 6 October on **JNCC June 2026** and **UKSI July 2025**, translating old TVKs to current on every build. **35 reviews**, ~3,870 review accounts. |
| **UKSI** | **Updated 6 October to the NHM July 2025 release** (`build_uksi_from_release.py`); the December 2023 file kept as `uksi_2023.db`. |
| **Contributed records** | **New, 2 October.** `contributed_observations` + `assessment_records` view + `scripts/import_contributed.py`. One collaborator so far (J. Moore). No browsing tab yet. |
| **Curator** | Working. Does not write curatorial fields. |
| **Tabella** | **Retired 7 October 2026**, archived to `_archive\Tabella_20261007`. |
| **Lector** | **Joined 7 October 2026.** BHL harvester for species-profile literature; `data\lector.db`. No BHL API key yet. |
| **Munia** | Unchanged since June. |
| **Atrium** | Launcher. Tabella's buttons removed 7 October. |

---

## 2. Database figures

### codex.db — 53.8 MB, rebuilt 6 October (JNCC June 2026, UKSI July 2025)

| Table | Rows |
|---|---:|
| designations | 27,152 (JNCC `taxon-designations-20260609.xlsx`, 15,211 species) |
| status_summary | JNCC 26,908 + manual entries applied; 15,841 species with a status |
| sqs_scores | **9,594**, all Pantheon-sourced; 0 stored derived (9,600 before the 8 Oct bridge rebuild) |
| tvk_bridge | **14,215** (8,588 direct / 5,618 name, of which 5,575 by NAMES key / 9 synonym; 14 unmatched). Rebuilt 8 Oct: was 14,146 with 83 unmatched |
| manual_entries | **10,092** -- review statuses, withdrawals, superseded and old-name clearances, 52 JNCC-2023 restorations, 13 clearances after the UKSI swap (6 Oct; was given as 10,079, counted before them -- corrected 8 Oct by `check_reference_figures.py`) |
| reviews | **35** |
| species_profiles | **3,874** review accounts, keyed `(tvk, review_id)` |

Rebuild of 6 October: **153 rows translated** from old TVKs to current via
`uksi.tvk_remap`; no account collisions. Unrouted designations: 119 rows, 14 codes.

**Reviews loaded** (id: what, accounts; *S* = statuses written too; *IR* = internal reference only):

| id | Review | Accounts |
|---|---|---:|
| 1 | Leaf beetles, NECR702 (Lane 2026) *S* | 287 |
| 2–4 | Sawflies Phases 1–3 (Musgrove 2022–24) *S*, *IR* | 540 |
| 5 | Butterflies Red List (Fox et al. 2022) *S*, threat only | 0 |
| 6–15 | NE Species Status: darkling, soldier, wood-boring, clown, longhorn, scarab, Tachyporinae beetles; stoneflies; aquatic bugs; mayflies | 1,000 |
| 16 | Millipedes, centipedes, woodlice (Lee 2015) | 179 |
| 17 | Ground beetles (Telfer 2016), PDF | 51 |
| 18 | Larger Brachycera (Drake 2017), PDF | 33 |
| 19 | Dolichopodidae (Drake 2018) *S*, PDF | 59 |
| 20 | Lonchopteridae, Platypezidae, Opetiidae (Chandler 2017), PDF | 9 |
| 21 | Calyptratae, provisional (Falk & Pont 2017) *S* from data sheets, PDF | 300 |
| 22 | Acalyptratae, provisional (Falk, Ismay & Chandler 2016) *S* from data sheets, PDF | 244 |
| 23 | Orthoptera and allies (Sutton 2015), PDF | 7 |
| 24 | Caddis flies (Wallace 2016), PDF | 36 |
| 25 | Shieldbugs and allies (Bantock 2016), table | 69 |
| 26 | Hoverflies (Ball & Morris 2014, Species Status 9), PDF | 81 |
| 27 | Fungus gnats, Nematocera, Aschiza (Falk & Chandler 2005, SS 2), PDF | 281 |
| 28 | Pill beetles and allies (Lane 2021, SS 17), table | 65 |
| 29 | Dance flies, Empidoidea (Falk & Crossley 2005, SS 3), PDF | 221 |
| 30 | Water beetles (Foster 2010, SS 1), PDF | 77 |
| 31 | Rove beetles, NECR390 (Boyce 2022) -- 54 data sheets + 190 table notes; *S* for *Dropephylla heeri* only | 244 |
| 32 | Carrion beetles, NECR316 (Lane 2020), spreadsheet | 21 |
| 33 | Bees, wasps and ants (Falk 1991, RSNC 35), *IR* | 246 |
| 34 | Non-marine molluscs (Seddon et al. 2014, NRW), *IR* | 19 |
| 35 | **Macro-moths (Fox et al. 2019) *S* -- 766 statuses, first time in Codex**; no accounts | 0 |

Not loaded: spiders 2017 (rationales only, all rights reserved); dragonflies 2008
(rationales and web pointers); micro-moths 2012 (status list only); Hyman 1992/94
and Falk 1991 flies Part 1 (print only -- statuses are in Codex via JNCC).

**Status corrections:**
- *4–5 Oct:* 272 NS-excludes routed; 71 old statuses superseded; withdrawals now
  33 (NECR234, NECR217, NECR192, NECR195, SS 9, SS 1, SS 3); 3 old names; NECR234's
  300 provisional statuses; 63 legacy statuses stored with a detail cleared.
- *5 Oct, JNCC 2026 rebuild:* 52 statuses on 43 species that JNCC dropped or
  re-keyed without a newer review restored (`added_by='restored-jncc2023'`).
- *6 Oct, after the UKSI swap:* *Sepedophilus testaceus*'s stale Notable cleared;
  12 legacy-detail rows cleared where translation joined a "pro parte" TVK to its
  current species.
- Checks after the 6 Oct rebuild: `check_legacy_conflicts.py` 0 stale;
  `clear_legacy_detail.py` 0; `check_newest_review.py` (2) 0, (1) 173 -- 157
  Staphylinidae outside NECR390's subfamilies (scope, correct), moth subspecies,
  loose plants.

**SQS import, before and after the 2 October fix:**

| | Before | After |
|---|---:|---:|
| Invertebrate TVKs recognised | 7,076 (designations only) | 66,322 (UKSI: Animalia outside Chordata) |
| Pantheon scores kept | 5,568 | **9,611** |
| Dropped as "non-invertebrate collision" | 4,085 | 59 |
| Dropped as zero-SQS | 109 | 109 |

JNCC status tracks, 6 October, before manual entries (threat_iucn_2001 10,610;
priority 5,228; rarity_modern 3,635; legal 2,579; red_list_england 1,831;
threat_iucn_legacy 1,383; rarity_legacy 1,156; global 270; bocc 173;
specialist 43).

**Research-only:** Pantheon lists 72 species as S41 research only; **62** reach
current TVKs through the bridge. The other 10 are treated as ordinary S41
(backlog F5).

### observatum.db — ~114 MB, WAL, `synchronous=FULL`

| | |
|---|---:|
| Observations | ~24,206 (24,034 + 172 committed 2 October) — *not re-measured* |
| On TVKs newer than UKSI July 2025 | 42 records on 7 TVKs -- left as they are, names stored on the records |
| Contributed observations | 162 (J. Moore, Birmingham – Wheels Park) |
| Vice-county filled | 4,169 backfilled 26 September; 0 missing where a grid ref exists |
| species_profiles (your own) | **141** -- 70 Kent Deadwood, 71 from seven other reports (6 Oct), keyed on TVK |
| Remapped to current TVKs, 6 Oct | 12 observations, 1 specimen, 1 own profile (`remap_record_tvks.py`) |

### Specimens — measured 26 September

| | |
|---|---:|
| Specimens | **2,745** -- all keyed on the July 2025 UKSI since 8 Oct except the two with no TVK |
| With a taxonomic sort key | 2,743 |
| Sex recorded | **602** (22%) |
| Preparation / condition / storage / drawer | 204 / 8 / 2 / 0 |

### The rest

| Database | |
|---|---|
| uksi.db | **July 2025 release.** taxa 113,291 (113,258 current + 33 kept: 9 your data uses, 24 beetles kept at your request); synonyms 98,415; common_names 23,171; designations 40,551; plus `name_map` 335,060, `tvk_remap` 13,569, `taxon_qualifiers`. JNCC TVKs unknown to it: 66 of 15,211. |
| uksi_2023.db | The December 2023 file, kept beside it: 122,435 taxa. |
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

### Every survey, 6 October

SQI on current scoring (Pantheon's scores plus any derived) and on Pantheon's
published scores alone. Key species after the jurisdiction and research-only
rules, on JNCC June 2026, 35 reviews and UKSI July 2025.

| Survey | Species | Key | SQI | SQI (Pantheon only) | SQI before 2 Oct |
|---|---:|---:|---:|---:|---:|
| BAM Glory Park 2024 | 128 | 8 | 117 | 117 | 134 |
| Badshot Lea 2023 | 167 | 8 | 111 | 111 | 121 |
| Bicester Graven Hill 2023 | 367 | 17 | 108 | 107 | 123 |
| Bicester Graven Hill 2025 | 254 | 19 | 127 | 126 | 155 |
| Birmingham – Wheels Park 2026 | 195 | 7 | 116 | 105 | 146 |
| Derby 2025 | 230 | 4 | 101 | 100 | 119 |
| Fermyn Hall Wood Deadwood 2024 | 49 | 7 | 157 | 153 | 197 |
| Kent Deadwood 2024 | 393 | 75 | 181 | 175 | 247 |
| Long Hanborough 2025 | 118 | 10 | 112 | 111 | 122 |
| Machen 2024 (Wales) | 321 | 16 | 121 | 115 | 144 |
| Tilbury 2025 | 238 | 4 | 101 | 100 | 106 |

Changes since 4 October: the JNCC 2026 rebuild brought the 2022 rove beetle
statuses (Kent 77 → 75, Bicester 2025, Fermyn, Long Hanborough and Machen each
−1, all to LC); the 2019 macro-moth Red List added *Chiasmia clathrata* as Key
(Birmingham 6 → 7). The UKSI swap moved only Pantheon-only figures (Kent 175 → 176,
Machen and Badshot Lea scoring counts ±1). Snapshot `before_uksi2025.txt` for
`scripts/check_sqi_table.py`.

**Accounts:** every key species on every survey has an account (review or your
own) except five -- *Oligota apicata* (Kent), *Xysticus luctuosus* (Bicester 2025),
*Liocyrtusa minuta* (Machen), *Chiasmia clathrata* (Birmingham), *Zophomyia
temula* (Tilbury). `scripts/list_missing_accounts.py`.

**Issued reports are not being revised** — they were built on the Pantheon
website and are unaffected. Any SQI taken from **Examen** between April and
2 October was inflated by 3–66 points. Badshot Lea's key species have moved from
the issued 10 to 8 (jurisdiction, then research-only).

### Birmingham – Wheels Park 2026 — the first joint survey

195 species: 130 Wil, 121 J. Moore, 56 shared. **7 key species** (6 until the
macro-moth Red List made *Chiasmia clathrata* Key, 5 Oct), 1 Rare Key
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

### Session 42 — 8 October 2026

**Step 4 done: Claude Code can now be used on this folder.** `CLAUDE.md` (rules, safety,
where the docs are, `py -3.14`) and `.claude/settings.json` (deletion and destructive
git denied, bypass and auto modes off). **`scripts/check_reference_figures.py`**
freezes every survey's species, key species and both SQIs plus the Codex counts, and
compares; its first run matched all 44 survey figures and found doc 02's
`manual_entries` stale (10,079 → 10,092: the 13 clearances after the UKSI swap).

**The morning's Data Entry commits checked.** 59 blank site names (Alsager 17, Sundon
9, Slade Green 33), Alsager's 31 June pitfall records with no trap or grid ref (now
Pitfall 3, SJ 77573 55037, VC58), "Cricket bat spid" committed with no TVK (now
*Mangora acalypha*), three doubled sex-split entries merged (*Poecilus cupreus*,
*Nebria brevicollis*, *Agriotes lineatus*: 3 records removed, quantities summed).
Backups `observatum_pre_alsager_pitfall3_*` and `observatum_pre_sitenames_*` in
`reference\`. The **iRecord export** that "had no Save dialog" had excluded all 279
embargoed records and stopped silently; it now says so, and suggests
`<project or site>_<date>.csv`.

**Found:** Pantheon species without a TVK all stored under one blank key (F26) --
which also explains F5: 9 of the 72 research-only rows, not 10 unbridged species.
Specimen 1752's sort key corrupted by the 6 Oct remap, and the specimen keys
possibly on two UKSI numberings (F27). **Done:** B3, E18 (with one shared formatter
for dates and mode labels). **Run 2:** four Slade Green re-entries deleted, every
specimen re-keyed on the July 2025 UKSI (no visible change to the tree order),
review 21's Track filled; all reference figures still match.

**The Pantheon bridge now follows the NAMES sheet by key** (F14 / fault F25). Each
Pantheon TVK is a UKSI name key, and NAMES says which current species that key
belongs to; the bridge had matched by name instead, and for a name with several
targets kept the first met. 104 bridge rows disagreed with NAMES; after two Codex
rebuilds 37 remain, all deliberate (species kept over an aggregate; subspecies/forms
to their species; four kept by judgement -- *Tasgius globulifer*, *Ectemnius
rubicola*, *Hydrobia ventrosa*, *Cimex dissimilis*). 69 more Pantheon taxa now reach
a species (unmatched 83 → 14), including the Odonata Pantheon holds under English
names. The first rebuild let NAMES-key merges escape the J2 rule (*Anthonomus
pomorum* 1 → 4, Badshot Lea 111 → 113); the second applies it to every merge.
Figures that moved: Kent Pantheon-only 176 → 175 (*Nomada panzeri* now scored -- F19),
Fermyn Pantheon-only 154 → 153 (*Cantharis flavilabris* now scored); no
current-scoring SQI and no key-species count moved. Backups
`codex_pre_bridge_names_*` in `reference\`. *O. linearis* and *P. recurva* are not in the July 2025 UKSI
and stay without a TVK.

### Session 41 — 7 October 2026 (evening)

Species search in Add Specimen uses the Data Entry ranking (`shared/species_rank.py`).
Folder tidy: Tabella retired to `_archive`, 135 one-off scripts and 128 `.bak` files
archived, `build_gb_basemap.py` to `scripts/` (log `_archive/tidy_20261007_log.txt`).
Lector joined the suite; Spider Extract moved to `Natural History Tools`. Codex Loaded
Reviews counts species live. Fault F25 (`uksi.synonyms` wrong targets) found through
Lector. Private GitHub repo `ThePonker/biological-software` set up, `main` and
`stable` pushed; the `D:\` copy refreshed.

### Session 40 — 6 October 2026

**The UKSI updated to the July 2025 release.** The NHM portal copy turned out to
carry the Nameserver mapping in its NAMES sheet, so a new builder
(`build_uksi_from_release.py`) writes a `uksi.db` with the same schema from it:
current taxa only, every other name a synonym, a `tvk_remap` for every old TVK
the suite holds, and taxa your data uses kept even where the UKSI flags them
redundant. A detailed review before switching found five faults in the build
itself (cross-kingdom name matches, dead-end parents, 'species pro parte'
refused as a species rank, uncarried English names, sort-code collisions) -- and
an assumption that duplicate rows explained 24 valid British beetles being
flagged redundant, which measured false: the UKSI flags them itself. Kept at your
request. `build_codex_db.py` now translates old TVKs on every build; records and
profiles remapped; survey figures unchanged bar Pantheon-only shifts.

**Your own species profiles from eight reports** -- 70 Kent Deadwood, then 71
from Bicester 2025, Graven Hill, Machen, Fermyn Hall Wood, Badshot Lea, BAM and
Long Hanborough, in four layouts, verbatim, with survey-specific sentences held
back (`import_own_profiles.py`). Five survey key species remain without an
account. The staging grid opens the species account (row-number double-click,
right-click, Ctrl+I).

**A whole-codebase static analysis** (597 files, ~97,500 application lines):
2 undefined names; all application code compiles on Python 3.12. It found the
**Examen manual-entry dialog able to empty Codex's `manual_entries`** -- all
10,079 review statuses -- from a button in the Species Database tab; disabled.
Also fixed: both observation-filter fallbacks, a `List` import that only Python
3.14 tolerated, and the staging grid's column-header menu. Rest queued (I7–I12).

### Session 39 — 5 October 2026 (evening)

**JNCC's June 2026 spreadsheet** (27,152 rows) built into Codex -- bringing the
2022 rove beetle review (Kent 77 → 75) -- and 52 statuses JNCC had dropped or
re-keyed without a newer review restored. Reviews 27–34 loaded (Species Status
1, 2, 3, 17; rove and carrion beetles; Falk's 1991 aculeates; molluscs) and the
**2019 macro-moth Red List, whose 766 statuses had never reached Codex**.
`withdraw_statuses.py` would have let a 2005 exclusion clear Drake's 2018
statuses; caught at the dry run, now dated. The UKSI copy found to be December
2023, older than three public releases.

### Session 38 — 5 October 2026

Acalyptratae (NECR217) loaded with statuses from its data sheets and its 21
excluded species withdrawn -- whereupon four 'Taxonomy' exclusions turned out to
resolve, through UKSI synonyms, to valid species the same review had assessed;
their new NS was cleared and restored, and withdrawals now match exact names
only. Then a hidden class: 63 legacy statuses stored with a detail (RDBK /
Insufficiently Known, '1994 IUCN') had escaped every check; cleared, verified.
Orthoptera, caddis, shieldbug and hoverfly accounts added (26 reviews, ~2,700
accounts). Spiders 2017 has no accounts; Hyman 1992/94 is print-only, so key
beetles from it are yours to write.

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

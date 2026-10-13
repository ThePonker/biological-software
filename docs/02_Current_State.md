# Current State

## 12 October 2026 (after Round 8 and the outstanding tests)
## The only home for these figures. If a number appears elsewhere, it is a copy
## and it will drift. Session history is in `02b_History.md` (split out 12 Oct).

---

## 1. Component status

| Component | State |
|---|---|
| **Observatum** | Active. Since 10 Oct: species-counting switches everywhere (Settings › Species counting; excluded rows dimmed, "Show only excluded"); Cleaning Report (Stats/Reports); Recording Scheme records read-only; Home cards Personal, Commercial, All, Scheme & Collection (Achievements card gone); Open in iRecord in record details and the Mapping square list; Species lookup "View N scheme records"; Edit Specimen "Field record" box; laptop sizes (dialogs fit 1280×720 and scroll with their buttons kept on screen; the window narrows to about 1,100 px). **Startup "window early, rest behind"** (§1a). Mapping: VC labels, VC boundaries (each border once), Local authority districts switch (2013 ONS for now), Square opacity slider, County view, Current-view atlas PNG. |
| **Data Entry** | In production. Commits 2 Oct (Birmingham 172) and 8 Oct (1,136 records, five jobs). Count mode (F9) and repeat key (Ctrl+R) built 9 Oct. **Check before commit (B8) passed Wil's test 12 Oct.** A count of 0 is pink and blocks that row's commit; conservation chips read S.41 / SBL / S7 / Protected; "Showing: entry order" / "sorted by … (view only)" with Back to entry order; the banner cards narrow to fit the window. At 1280×720 the grid shows about 7 rows (compact banner agreed, Q54). |
| **Examen** | Reproduces an issued report's SQI exactly (Glory Park, 117). Reads `assessment_records`, so contributed records count. Excel, PDF and Word reports; compartments (E6), saproxylic SQI + IEC (E7), taxonomic summary (E8b). **PDF passed Wil's review 12 Oct (E3)**; style changes wait for the report-contents work. "1 sp." singular. Fits a laptop screen (minimum 1000×560, toolbar scrolls sideways). |
| **Codex** | Rebuilt 9 October (D5) on **JNCC June 2026** and **UKSI July 2025**. **63 reviews** (35 status reviews + 28 atlases, accounts only), 6,566 review accounts. Known stale status: *Philanthus triangulum* still carries RDB2 (12 Oct). |
| **UKSI** | NHM July 2025 release since 6 Oct; the December 2023 file kept as `uksi_2023.db`. Synonym fix applied 9 Oct (98,415 → 98,013). |
| **Contributed records** | `contributed_observations`, **757 records** from J. Moore: Birmingham 162, Slade Green 339, **Sundon 256** (11 Oct). Read-only Contributed tab. On Mapping only when chosen. |
| **Insect Collection** | 2,745 specimens. Field record links: the Edit Specimen box, link / unlink scripts and `specimens.no_field_record_checked` (added on the PC 11 Oct). Read-only breakdown of specimens with no field record (§2). |
| **Curator** | Working. Genus-only specimens get their own "<Genus> sp." row (Leiopus 3 = *L. nebulosus* 2 + Leiopus sp. 1). Does not write curatorial fields. |
| **Lector** | **In the suite with a desktop window (Round 7, 12 Oct)**: saved searches, search builder with name checks and a preview, runs and what changed, reading list, exports (Word dossier, Excel index, PDF, text). Atrium tile; console in Atrium's Tools row. `lector.db` schema v3 (Round 8). Lector tests 9 of 9 passed; the user manual's ~130-item checklist not started. **Paused by Wil 12 Oct** (Q7). |
| **Munia** | Multi-year projects split across business years (Round 2). Not in use; no development until work comes in. Only its look from Atrium is to be checked (with the Atrium icon job). |
| **Atrium** | Launcher. One copy at a time (a second start brings the open one forward). Tiles for Examen and Lector (book icon); Lector console in the Tools row. Icons and restyle agreed as one job (Q52/53). |
| **Tabella** | Retired 7 October 2026 (`_archive\Tabella_20261007`). |

---

## 1a. Startup, tests and what Wil has tested

**Startup ("window early, rest behind", Round 6, Wil's choice 11 Oct).** Under the splash:
Home, Observation Data, Contributed and Insect Collection. Behind the open window: Recording
Scheme records, Stats/Reports, Mapping, Settings, then the species-search index, with a
"Still loading: …" line in the status bar. A tab clicked early shows "Finishing loading…" and
moves to the front of the queue. `run.bat --timing` prints the phases and every GUI pause over
100 ms with where it happened.

| PC, `run.bat --timing` | Round 5 (11 Oct) | Round 6 (12 Oct) | **Round 8 (12 Oct 15:41)** |
|---|---:|---:|---:|
| Window shown | 14.7 s | 5.75 s | **5.72 s** |
| Everything ready | 15.3 s | 16.33 s | **12.05 s** |
| Longest GUI pause | — | 1,231 ms | **106 ms** (stats order grid build) |

**Automated tests (13 Oct):** on the PC, `py -3.14 -m pytest tests -q -n 6` (pytest-xdist,
installed 13 Oct): 1,366 passed, 3 skipped in 1 min 55 s at `19e4a1c` (one process: 7 min 43 s).
Task 4 added 2 tests (`test_species_lookup_list.py`). The test-order failures are cured: offscreen
Qt on Windows had no fonts, so the 1280 px layout tests passed only when an earlier test had
started Qt with real fonts; `tests/conftest.py` now sets `QT_QPA_FONTDIR` (backlog small fix 9).

**Wil's manual test rounds, all passed:**

| Test round | Covers (build) | Result |
|---|---|---|
| Round 9 (tests 1–43) | Round 2 build, 10 Oct | 1–29 on 10/11 Oct; 30–38, 41–43 on 12 Oct (30, 31, 34, 35 with `tests/manual_import_files/`). 39 superseded by Round 12 Test 4; 40 (Munia) skipped by Wil |
| Round 10 (23) | Round 3, 11 Oct | 23 of 23 |
| Round 11 (13) | Round 4 and Sundon, 11 Oct | 13 of 13 |
| Round 12 (4) | Rounds 5–6, 11 Oct | 4 of 4, plus the 150 % scaling check |
| Lector (9) | Round 7, 12 Oct | 9 of 9 |
| Outstanding tests (18) | Round 8 opacity, B8, E3, Round 9 leftovers | all passed 12 Oct |

Not yet tested: the Lector manual checklist (`docs/Lector_User_Manual.md`, sections A–N) and
the test on a clean `lector.db` (paused); Observatum and Lector on a real laptop.

---

## 2. Database figures

### codex.db — rebuilt 9 October (D5; JNCC June 2026, UKSI July 2025); atlases added 10 October

| Table | Rows |
|---|---:|
| designations | 27,152 (JNCC `taxon-designations-20260609.xlsx`, 15,211 species) |
| status_summary | JNCC 26,908 + manual entries applied; 15,841 species with a status |
| sqs_scores | **9,599** (9 Oct, after the D5 Pantheon rebuild; was 9,594), all Pantheon-sourced; 0 stored derived (9,600 before the 8 Oct bridge rebuild) |
| tvk_bridge | **15,307** (9 Oct, after the D5 rebuild: the 1,114 NOTVK Pantheon species now bridge; 14,215 on 8 Oct) |
| manual_entries | **10,092** -- review statuses, withdrawals, superseded and old-name clearances, 52 JNCC-2023 restorations, 13 clearances after the UKSI swap (6 Oct; was given as 10,079, counted before them -- corrected 8 Oct by `check_reference_figures.py`) |
| reviews | **63** -- 35 status reviews + 28 atlases (10 Oct, `load_atlases.py`, accounts only; no survey figure moved) |
| species_profiles | **6,566** review accounts (3,874 before the atlases), keyed `(tvk, review_id)` |

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
| Observations | **24,962** (measured 10 Oct on the 9 Oct copy). Counted with the default switches on the PC, 12 Oct: **24,827 records, 3,163 species** (Personal 19,043 + Commercial 5,784; Home's All card matches Observation Data) |
| Changed on the PC 11 Oct | *Melanotus* 10 records to the click-beetle genus (F43); 16 records off TVKs not in UKSI (28 left with no match, Q61); 39 iRecord-format sort keys recomputed (10/11 Oct) |
| Recording Scheme | **110,510**; 35,104 with an iRecord ID (restored 9 Oct, F40); taxon groups backfilled 10 Oct (75,406 rows). **11 Oct:** 11,149 records from 18 padding datasets moved from exact 1 January dates to year-only (`fix_jan1_dates_20261011.py`; the January bar 11,648 → 499); 39 "unclear" iRecord-longhorn and 173 small-dataset 1 January dates left for the final dataset (Q57/58). Counted with the default switches: 108,577 records, 82 species (12 Oct) |
| On TVKs not in UKSI July 2025 | 28 records left after the 11 Oct remap (*Astur gentilis*, redpolls, *Collybia*, *Cnephaeus*, the earwig agg.); waiting for the next UKSI (Q61) |
| Contributed observations | **757** (J. Moore: Birmingham – Wheels Park 162, Slade Green 339, Sundon 256 on 11 Oct) |
| Vice-county filled | 4,169 backfilled 26 September; 0 missing where a grid ref exists |
| species_profiles (your own) | **141** -- 70 Kent Deadwood, 71 from seven other reports (6 Oct), keyed on TVK |
| Remapped to current TVKs, 6 Oct | 12 observations, 1 specimen, 1 own profile (`remap_record_tvks.py`) |

### Specimens — measured 26 September; links 11 Oct

**Specimens with no field record** (`scripts/report_specimens_without_records.py`, read only,
PC 11 Oct): 863 of Wil's, complete, would make **794 new records**; **506 near misses** to link
by hand (Q28); 2 missing details; 33 other people's (Wil's use only, never exported); 37 already
in the Recording Scheme (list only). Certain links found by `link_specimens_to_observations.py`:
about 1,115 (dry run 11 Oct).

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
| lector.db | Schema v3 (Round 8). On the PC, 12 Oct: 3 saved searches -- *Emus hirtus* (499 pages, most without text), *Rutpela maculata* (50), *Lamia textor* (160 pages before filters; Run 4 with "British periodicals": 87 kept of 1,104 found). Updated with backups (`data\_backups\lector_pre_v2_*`, `lector_pre_v3_*`). |
| vc_splits.db | 14,455 boundary 1 km squares and 42 squares with no VC (9 Oct, F29) |
| data/maps | `vc_brc_wgs84.geojson`: rebuilt on the PC 13 Oct from `vc_brc.shp` (112 VCs, 15.0 MB; the old coarse 2 MB file kept as `vc_brc_wgs84_before_20261013_195800.geojson`); `gb_outline.json` on the PC = 2013 ONS districts (380), no build script |

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

### Every survey, 9 October (frozen in `scripts/reference_figures.json`; Sundon and the strict key counts updated 12 Oct, below)

Current scoring and Pantheon's published scores alone; key species after the jurisdiction and research-only rules. *Strict* = Examen's Pantheon Only mode.

| Survey | Species | Key | SQI | SQI (Pantheon only) | Key (strict) |
|---|---:|---:|---:|---:|---:|
| Alsager 2026 | 191 | 5 | 109 | 109 | 5 |
| BAM Glory Park 2024 | 128 | 8 | 117 | 117 | 9 |
| Badshot Lea 2023 | 167 | 8 | 111 | 111 | 9 |
| Bicester Graven Hill 2023 | 367 | 18 | 107 | 107 | 19 |
| Bicester Graven Hill 2025 | 254 | 19 | 126 | 125 | 21 |
| Birmingham - Wheels Park 2026 | 195 | 7 | 116 | 105 | 8 |
| Bristol 2026 | 122 | 4 | 106 | 105 | 5 |
| Derby 2025 | 230 | 4 | 100 | 99 | 6 |
| Elmley 2026 | 44 | 7 | 182 | 184 | 7 |
| Fermyn Hall Wood Deadwood 2024 | 49 | 7 | 157 | 153 | 8 |
| Kent Deadwood 2024 | 393 | 75 | 181 | 175 | 82 |
| Long Hanborough 2025 | 118 | 10 | 112 | 111 | 12 |
| Machen 2024 | 321 | 16 | 120 | 114 | 19 |
| Slade Green 2026 | 344 | 44 | 153 | 147 | 44 |
| Sundon 2026 (with Jon Moore's records; see below) | 231 | 19 | 125 | 114 | 19 |
| Tilbury 2025 | 238 | 4 | 100 | 99 | 5 |

**Sundon with Jon Moore's records (11 Oct).** 256 contributed records (150 species) joined
Wil's 198: Examen gives **231 species (54 shared), 19 key species, SQI 125** over 5 visits
(1 May – 5 Aug). Wil accepted Jon's identifications as recorded (Q66, 12 Oct);
`reference_figures.json` was updated 12 Oct (small fix 7) from Examen's own calculation on a
copy with Jon's file imported: Codex Full 231 / 19 / 125; SQI on Pantheon's scores 114 (also
114 for Wil's records alone -- the same figure, not a stale one); Pantheon Only SQI 114, key 20
before the bridge correction and 19 after. (Wil's records alone were 135 / 12 / 132 / 114 / 12.)

**Local bridge correction (Q67, 12 Oct).** Pantheon's *Sympetrum nigrescens* (Highland Darter,
Nationally Scarce, SQS 4; two Pantheon taxa, NBNSYS0000005646 and NBNSYS0000167746) was linked
by name to *S. striolatum* (UKSI holds nigrescens as its synonym), so in Pantheon Only mode
every *S. striolatum* record took NS and became a key species. The links are dropped by
`shared/pantheon_bridge_corrections.csv` (pantheon.db and codex.db unchanged) and the species
carries "local correction: …" in its status note. Pantheon Only key species fall by one at
every survey with *S. striolatum*: Bicester 2023 20→19, Birmingham 9→8, Bristol 6→5, Machen
20→19, Slade Green 45→44, Sundon 20→19. No SQI moved (striolatum keeps its own SQS 1); Codex
Full is unaffected.

**Ad hoc lists (not stored).** Betteshanger Park (M.G. Telfer, 437 records, 27–28 Apr 2026),
analysed 12 Oct outside the databases: 296 taxa; Codex Full 29 Key (9.8 %), 5 Rare Key (1.7 %),
SQI 123; Pantheon only 31 Key, SQI 120.

The 6 October table (11 surveys, with the pre-2 October figures) is in git history. Moves since then are the 9 Oct fix round: one SQI path, the bridge J2 rule in strict mode, invertebrates from UKSI, s.l./s.s. merged (`claude/33`).

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

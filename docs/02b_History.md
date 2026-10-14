# History

## Split out of `02_Current_State.md` on 12 October 2026. One paragraph per session,
## newest first. Figures quoted here were true on the day; the current ones are in `02`.

---

### Session 49 — 13–14 October 2026 (night to evening)

**Photos B2, B3, B5 and the iRecord round trip.** Record ↔ photo links (`photo_links`, by
script for the microscope photos with one matching specimen); a Photos window on the record
(the species folder's photos, this record's first, link / unlink); a re-det moves the record's
linked photos (logged, reversible). The download returned all 46 IRTEST keys (A1). A2: the
sync keeps local edits, lists real conflicts, holds an Observatum key that names several records
(F83). The A2/A3 review found the Observatum keys repeating since 25 Mar (F82): one key rule,
`renumber_duplicate_keys.py` run on the PC (2,719 records), the export refuses shared keys.
**Bench photos:** a Photo… button on a Data Entry row (capture folder `Desktop\image`, views
head / gen / your own, names "Amara aenea male gen 5.vi.26"); `standardise_specimen_names.py`
renamed 30 old names. Wil's testing showed a typing slip left a species folder behind, so
**take 2** holds bench photos in `Photos\_Bench` until commit (filed only for a species picked
from the list), asks before deleting rows with photos, and adds a Photos list to the cleaning
report (empty folders to `_archive`, photos waiting, missing files, names). Personal jobs now
commit plainly; records go to iRecord by Observatum's bulk export (External key), then the sync.
An Opus review before each of the three deliveries found defects, all fixed before delivery.
**Afternoon, photo rounds 2–4** (Wil testing between each; full suite 1,464 passed at the end):
bench photo names follow a sex or date change; a photo can be taken off a Data Entry row; the
copy-context tick says when sorting has switched it off; a 📷 column in Observation Data and
Insect Collection (count of linked photos, double-click opens them, sorts by count); deleting a
record asks where its photos go (`_Bench` or left), never deleting a file; an in-app photo viewer
(arrow keys, actual size); photos of another record marked OTHER RECORD in orange; column widths
kept per column through searches and sorts (Insect Collection used to reset them on every
search); every named dialog in the suite remembers its size (`shared/dialog_geometry.py`);
the cleaning report's Waiting in _Bench tab moves unlinked photos back to the capture folder or
to `_archive`. Pace: each sitting ran
20–40 minutes against estimates of 1–2.5 hours.
**Evening, round 5** (a review of the photo and iRecord work for loopholes; full suite 1,480
passed on the PC): an "exported on" stamp so a second bulk export skips records already sent
(F85; column added on the PC, 25,008 rows); Photo… only on the live database; a failed commit
can no longer write a record twice; bench photos on a record filed with it; links to deleted
records listed and tidied (0 left on the PC); clears count as edits for the sync; numbers sort
as numbers in every table. Wil merged `main` into `stable` (F2). **Round 6** (built the same
evening, to test): records from phone photos through Data Entry, the review sheet for photos
with several candidate specimens, grid refs on photos, records from specimens as Data Entry
rows (a dry run on the 14 Oct copy: 540 to stage, 87 season-only, 167 held) with an Insect
Collection "Specimens to check" window, and the observation imports' sort keys (F34).

### Session 48 — 13 October 2026

**Handover tasks 1–4 and a faster way of working.** (1) One place for saved filters: the
filter bar's top row saves the bar's boxes and the Filter Wizard's chips together; the wizard's
own Load saved / bin / Save as / Save / Reset / Apply Filter row is gone, and a card dialog's
Apply now filters the table (it only updated the cards before). (2) Cleaning report: a row
opens Record Detail (Edit / Delete with the iRecord box for a live Observation row, through the
Observation tab's own flows; scheme, contributed and hidden rows view only); a "Hidden here"
tile with Show again. The Opus review found hidden rows feeding the synonym check (F80) and a
failed build leaving another source's rows editable (F81); both fixed before delivery.
(3) Every button style greys out when disabled. (4) Species Lookup's drop-down drawn by the
shared species list painter (search and picks unchanged). Working method: `claude_deliver.py
prepare` runs ruff; Claude stages read-only copies of the databases so data tests run before
delivery; Wil runs targeted tests per task and the full suite with `-n 6` (2 min) for data
changes and at session end; layout tests no longer depend on test order (F79).

**Evening: the iRecord round trip and the photos.** Wil's test upload proved iRecord keeps an
External key Observatum supplies (46 Farthinghoe records, `OBS-WJH-IRTEST-…`). Built read-only:
`check_irecord_download.py` (the sync's own matching, run on a download without importing) and
`plan_photo_consolidation.py`. Wil answered the 304-row review sheet; `build_photo_moves.py` and
`move_photos.py` (dry run, log, reverse; never delete or overwrite; Opus review found four
defects, fixed before delivery) then moved **1,469 specimen photos into the Life tree** at
23:44, 191 renamed to the new standard (`15.ix.17`, sex in lower case). The photos design was
cut back to a lean plan (~8 h: sync guard with re-det conflicts, personal jobs like
commercial, record ↔ photo links, Photos window, one intake screen for Mosaic and phone).

### Session 47 — 12 October 2026

**Round 7: Lector in the suite.** The lost fix2 work restored exactly (whole-word title
filter, page types, excerpts with the name in bold, index-page detection, duplicate scans
grouped, the post-1930 rights note, the Word dossier with its Excel index, `forget`); LEC1–6
(authors and titles, PDF, tighter duplicate test, misapplied synonyms held back with a reason,
year ranges, filters stored per search and applied on every re-run, tolerant name matching);
saved searches, runs and review notes in `lector.db`; `Lector/service.py` as the only API the
window uses; the desktop window (`python -m Lector gui`, Atrium's Lector tile, "Lector console"
in Atrium's Tools row), in the Observatum theme with a Steel Blue accent. Wil's three searches
(Emus hirtus, Rutpela maculata, Lamia textor; 709 pages) were updated with a backup. Lector
tests 9 of 9 passed. **Round 12 tests** (Rounds 5–6) 4 of 4 passed; startup on the PC: window
5.75 s, everything ready 16.3 s, but one GUI pause of 1,231 ms.

**Round 8 (afternoon):** Lector L1–L16 from Wil's tests (Back buttons, Edit on every row,
Fetch missing text, held-back names no longer ticked by the update, a proper tick mark shared
with Observatum (`shared/tick_mark.py`), outlined Notes, per-search run numbers, one cancel
sentence, request counts split, no withdrawals from an incomplete run, one scope wording,
keys 1–4 move on, empty Authors/Article title columns left out, a question before closing
during a run; `lector.db` schema v3). Observatum O1: the 1.2 s pause found (a table sizing its
columns behind the loading thread, and garbage collection) and removed; `--timing` lists every
pause over 100 ms and where it happened. O2: a Square opacity slider on the Mapping tab. The
Lector user manual (`docs/Lector_User_Manual.md`, project note 46). An independent review fixed
a map cache-key fault (VC boundaries drawn from the land's borders after the first paint, on a
PC without `gb_outline.json`), the "on the your list" wording, console commands overwriting a
saved search, console exports overwriting the window's, and two Lector keyboard/close races.
1,219 tests pass here; on the PC 1,218 passed, 2 skipped, 1 test-only failure (fixed).
**PC `--timing` after Round 8: window 5.72 s, everything ready 12.05 s, longest pause 106 ms.**

**Then the outstanding tests**, one at a time, all passed: Square opacity; Round 9 tests 32,
33, 34 (Data Entry), 36–38, 41–43 (40 Munia skipped by Wil; 39 superseded); B8 Check before
commit; E3 Examen PDF (style changes deferred to report writing); and, with new test files in
`tests/manual_import_files/`, Round 9 tests 30, 31, 34 and 35 in all three wizards. Display
faults and small items found on the way are the small-fixes round in `03`. The 97 open
questions (project note 45) were answered; the answers are in `03`. Agreed working rule: one
main line at a time, tested and committed before the next round. Lector paused (its manual
tests not started). Betteshanger Park (M.G. Telfer, 437 records) analysed outside the databases:
296 taxa, Codex Full 29 Key, 5 Rare Key, SQI 123; Pantheon only 31 Key, SQI 120.

### Session 46 — 11 October 2026

**Round 2 committed (`a75c065`). Round 3** (eight agents and a review; 73 files): Mapping
R9-4 to R9-6 (reversed dates flagged, VC labels and the selected VC outlined, Current-view
footer counts what is in view); Species lookup shows an aggregate's own records when picked
(R9-1); Open in iRecord everywhere (`shared/irecord_links.py`, R9-3); Data Entry banner
(R9-8); the Field record box in Edit Specimen with link, unlink and "checked, none" scripts;
batch maps as a script (`scripts/batch_maps.py`, R9-7); photo groundwork (file-name parser,
matcher, `check_media_library.py`). Then Wil's decisions D1–D8 (Commercial Reports follow the
counting switches, subspecies roll-up in dashboard lists, scheme month charts skip vague dates,
slash pairs as aggregates, TVKs not in UKSI, hybrids by rank, the lat/long cleaning check,
dataset parents, the kingdom/taxon group backfill). **Round 10 tests: 23 of 23.** Data on the
PC: *Melanotus* 10 records moved to the beetle genus (F43), 16 TVKs remapped, the specimen
check column added; media library 9,090 files, 45 GB, all local.

**Round 4** (evening): VC labels drawn in screen pixels (no garbling under zoom) and nudged
off squares; VC boundaries switch; the thin lines identified as 2013 ONS districts (own
switch, off); the coast from sea-facing edges only; startup speed (window first, tabs built
on first opening); the main window narrows to about 1,100 px; "View N scheme records" from
Species lookup; 1 January placeholder dates (11,149 scheme records D → Y, applied); the read-
only specimen breakdown; Sundon: Jon Moore's 256 records imported as contributed, combined
231 species / 19 key / SQI 125. **Round 11 tests: 13 of 13.** **Round 5:** each VC border drawn
once (`vc_topology.py`), draw order fixed (`map_layers.py`), everything preloaded under the
splash, Home's All card (Achievements card removed), laptop sizes (`shared/fit_to_screen.py`).
Startup became 14.7 s on the PC; Wil chose **Round 6, "window early, rest behind"**.

### Session 45 — 10 October 2026 (evening)

**Round 2** (seven agents, merged, independently reviewed; 124 files; 831 tests): the
species-counting switches everywhere (`shared/record_kinds.py`, `shared/species_counting.py`;
fault F45 closed), the Cleaning Report, Recording Scheme records read-only, the scheme
duplicate report, Home Personal and Commercial cards, the small wins L8–L34 and the note-36
decisions (group choices in species search, close spellings in imports, count of 0, vague
dates, Quick Entry projects, tetrads on maps, Change-database buttons removed, Munia year
split, read-only reports for embargo, tetrads, duplicates and specimen links). 39 iRecord-
format sort keys recomputed on the PC. **Round 9 tests 1–29 passed that night**; 30–43 were
finished on 12 Oct.

### Session 44 — 10 October 2026

**Morning:** 28 BRC/ITE/Cox/BSBI atlases loaded as accounts-only reviews (reviews 35 → 63,
accounts 3,874 → 6,566; no survey figure moved); Species lookup shows the accounts panel;
Lector given an interactive mode (its "crash" was argparse with no command).

**Day build (backlog 1–5 of 9 Oct), seven agents on separate copies, merged, independently
reviewed (4 bugs found and fixed), 147 files delivered:** one shared fuzzy species search
(`shared/species_search.py`, `species_filter.py`); Filter Wizard and filter bars on all tabs
(`services/filter_builder.py`); one taxon grouping (`shared/taxon_groups.py`; backfill
applied: 75,406 scheme rows, 3 specimens relabelled); Mapping selection (several taxa,
ranks, groups, richness, legend, VC/recorder/site/source filters); the Tier 2 review fixes.
Then filtering sped up (13 files) and small fixes 1–7 (28 files: phenology click-through,
Clear All beside Species, Codex group view, colour per mapped taxon, County view and the
multi-part VC outline fault F44). **Eight test rounds with Wil, all passed**; 626 tests pass
on the PC; `check_reference_figures.py` ALL MATCH. Items found while testing (L8–L34) and
the specification for counting switches everywhere and a cleaning report (`claude/38`) are
in `03`. Full status: `claude/39_Development_Status_20261010.md`.

### Session 43 — 9 October 2026

Full suite review (~140 findings, `claude/32`); Tier 1 fixed and tested the same evening
(steps 1–10). Built: C2, C3, C4 stages 1–2, D5 (`build_pantheon_db.py`), D7, E6, E8, E8b,
E13, F2, F9, H1–H6 (own map in the Mapping tab), I5 (ruff + hook), K1 (Contributed tab);
I7b scheme and specimen import repairs on `shared/import_core.py`; E7 saproxylic SQI + IEC;
I3b/I3c geo fixes (560 VCs corrected, 3,332 lat/longs recomputed). Data: Recording Scheme
iRecord IDs restored (F40, 35,104), taxonomy backfill (41,892 values), 54 records moved
from s.l./agg. to the species, Codex rebuilt twice (JNCC date reads 2026-06-09), Jon
Moore's Slade Green records imported (339). Committed `548a6fa`.

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

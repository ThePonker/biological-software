# Backlog

## Updated 14 October 2026 (photos and the iRecord round trip; see "Next")
## Check this before starting a session.

This file is the working list: how we work, what is next, what is decided but not built,
what is still Wil's to decide, and reminders. The area lists were split out on 12 Oct:
`03b_Backlog_Observatum.md` (Insect Collection, Data Entry, imports, infrastructure,
mapping, contributed records) and `03c_Backlog_Examen_Codex.md` (Examen, Codex, species
profiles, code hygiene, closed decisions). Question numbers (Q1–Q97) are project note
`claude/45_Open_Questions_20261012.md`; Wil's answers are at its end and are applied here.

---

## How we work (agreed 12 Oct, 15:46)

- **One main line at a time.** A round is built, Wil tests it, it is committed and pushed,
  and only then does the next round start. No parallel big jobs.
- Tests are given one at a time, with exact clicks and what Wil should see.
- After a data-changing session: commit, push, refresh the `D:\` copy (`01` §7).
- Delivered rounds are byte-checked on the PC; `py -3.14 -m pytest -q tests` first.

**State on 12 Oct:** Rounds 2–8 built, tested and committed (Wil's PC and GitHub at the
Round 8 commit, `6b76546` in the agents' clone). Every outstanding test passed (`02` §1a).
Lector is paused. **Q1 (the next big job) is still Wil's to decide**; the small-fixes round
comes first either way.

---

## Next: the small-fixes round (agreed 12 Oct, 16:40)

| # | Fix | Source / decision |
|---|---|---|
| 1 | **Species search lists:** row text clipped at the bottom (descenders: *Aclypea opaca*, *Agabus brunneus*); each name drawn in a bordered box; a plant genus offered for "beetle" ("All Leptochloa (beetle-grass) — group"); doubled brackets ("All Curculionidae (beetles (weevils)) — group"); **when the typed word is a group word, the "All … — group" choices come first** (change to R9-32) | 12 Oct outstanding Test 2; **built Round 9 A, to test** |
| 2 | **See-through drop-down popups:** Quick Entry's Project list draws over the form behind it with a text shadow. Give popups an opaque background; check every combo popup in the suite | Test 3; **built Round 9 A, to test** |
| 3 | **Import wizards, picked names:** the observation wizard's double-click pick keeps no "File had …" note and loses the original name (bug); one wording for "picked by you" / "resolved by you as"; the same row numbering in all three wizards (scheme counts from 1, the others from 2) | Import test files, 12 Oct; **built Round 9 A, to test** |
| 4 | ✅ *Built 12 Oct (R9 B1), Wil to run the relabel.* **Butterflies labelled "insect – moth":** the map was already one (`shared/taxon_groups.py`, since 10 Oct; the old wizard copies are gone); relabel the 42 records with `backfill_taxon_groups.py --relabel-only --tables observations` (dry run first; new option: corrects labels, fills no blanks) | Q63 |
| 5 | ✅ *Built 12 Oct (R9 B2).* **"Date before 1700" check** in the cleaning report (*Alosterna tabacicolor* 1500; *Acanthocinus aedilis*, *Agapanthia villosoviridescens* 1675); 132 scheme records on the 10 Oct copy; Contributed added as a third source | Q65 |
| 6 | ✅ *Built 12 Oct (R9 B3), Wil to run `mark_scheme_irecord_duplicates.py`.* **Scheme iRecord duplicates:** mark the 34,121 NBN "Longhorn beetle data from iRecord" copies that share an iRecord ID so each record counts once, keeping the iRecord copy. A flag, not a delete; reversible. Other tiers wait for the final dataset | Q59 |
| 7 | ✅ *Done 12 Oct (R9 B4a).* **Sundon reference figures:** `reference_figures.json` now 231 species / 19 key / SQI 125, Pantheon 114, strict 114 / 19 (Jon's IDs accepted as recorded) | Q66 |
| 8 | ✅ *Built 12 Oct (R9 B4b).* ***Sympetrum nigrescens*** linked to *S. striolatum* in Pantheon Only mode: a local correction to the bridge, flagged (`shared/pantheon_bridge_corrections.csv`; strict key −1 at six surveys, `02`) | Q67 |
| 9 | ✅ *Fixed 13 Oct (F79).* **Test-order flake:** offscreen Qt on Windows had no fonts; `tests/conftest.py` sets `QT_QPA_FONTDIR`, so the layout tests pass in any order and in parallel | Q89, note 43 |
| 10 | ✅ *Done 13 Oct (warm-up).* **Retire the scheme month chart's never-built species dropdown** (`stat_widgets.py` `_species_combo`): removed; the code kept in `_archive/month_chart_species_filter_20261013/removed_code.txt` (the service's `get_monthly_counts_by_species` left in place) | Q64 |
| 11 | **Suite-review leftovers sweep** (Tier 3 and 4: OBS-22/23, INF5–11, CDX-4, OBS-25/27, SRCH20/22, MAP13/15/16, DE10–14, IMP-18): verify each, fix or close; about half a session | Q90, note 39 §4.11 |
| 12 | **Data Entry compact banner:** a toggle that folds the cards to one line, for short laptop screens (about 7 grid rows at 1280×720) | Q54 |
| 13 | ✅ *Done 13 Oct (warm-up).* **Species lookup ↔ Species Info:** Home › Species Info "Open in Species lookup →" opens Stats/Reports › Species on that species; Species lookup "Show on Home" shows it in Species Info | Q55 |
| 14 | ✅ *Built 13 Oct (R10 A1, F68).* **What filter group choices filter:** "All Coccinellidae (ladybirds) — group" picked in the Species box keeps every record at or below the taxon (by TVK); the chip names the group | Round 9 test 11 |
| 15 | ✅ *Built 13 Oct (R10 A2, F69).* **Species box drop-down on the quick filter bars** (Observation Data, Recording Scheme, Contributed): the shared species list with group choices, scoped to the tab's species; typed text still filters | Round 9 test 15 |
| 16 | ✅ *Built 13 Oct (R10 A3, F70).* **Examen Species Database:** group rows drawn like the others; a clicked group lists its species with "Back to search results"; cap 1,000 with "First 1,000 shown — type more to narrow" | Round 9 test 31 |
| 17 | ✅ *Built 13 Oct (R11 A), to test.* **One search box in What that finds everything:** one box "Search species, groups, families, orders…" and one list -- groups the text names first (a common word: "All Coccinellidae (ladybirds) — group"; the tab's orders and families), then taxon groups (found by their iRecord value too: "insect - butterfly" → Butterflies (Lepidoptera)), then species with common name and family ("Turdus merula  Blackbird · Turdidae"), all drawn by the shared painter; each pick a chip saying what it is (Species / Family / Order / Taxon group); the filters keep the old keys, so saved filters load unchanged and counts are the same (ladybird 901, Coleoptera 8,174, Cerambycidae 795, insect - butterfly 996, *Rutpela maculata* 62). Also F77 (Enter wiped the chips) | Wil, Round 9 test 11 |
| 18 | ✅ *Built 13 Oct (R10 B1), to test.* **Cleaning report:** the checks shown once (tiles; the tab strip under them retired; the clicked tile stays marked); iRecord ID cell drawn as a link and "Open in iRecord" enabled only for a row that has one (tooltip says why); the scheme's marked NBN copies left out by THE rule (`shared/scheme_duplicates.py`) with a tick box "Include NBN copies of iRecord records" (off) -- header line and the export's Summary say which; on Wil's PC 110,510 checked drops to 76,389 | F71, Round 9 Test 16 |
| 19 | ✅ *Built 13 Oct (R10 B2), Wil to run `add_hidden_at_column.py`.* **iRecord-safe delete and edit:** Delete on an observation with an iRecord ID asks (Open in iRecord / Deleted in iRecord -- remove here / Cancel); "remove here" HIDES (`observations.hidden_at`, `hidden_irecord_ids`; `shared/hidden_records.py` is THE rule, through `species_counting.copies_sql`, the repository's list queries and the `assessment_records` view); a download that brings the record again keeps it hidden and the cleaning report lists it under "Came back from iRecord -- check" with Show again; Edit shows a note (the local edit stays possible). The sync already UPDATES a held record (F73: not a fault) | F72, F73; agreed 12 Oct late |

✅ *Done 13 Oct (warm-up).* The Mapping switch "Districts (modern)" is now "**Local authority
districts**" (Q39; the source swap to Boundary-Line is in the map-layers job).

### Round 10 (13 Oct): quick fixes from Round 9 testing — C (Drawer in hand, calendar, sort keys)

| # | Fix | Source / decision |
|---|---|---|
| C1 | ✅ *Built 13 Oct, to test.* **Drawer in hand tick boxes** drew nothing when ticked: the list's tick is the suite's `TickDelegate` in its own column, rows like the Insect Collection table; the "Show" radio buttons use `tick_mark.radio_qss` (F74) | Tests 20–25 |
| C2 | ✅ *Built 13 Oct, to test.* **"Not yet / Already in a drawer"** boxes replaced by one "Show:" choice — Not yet in a drawer (default) / All specimens / Only this drawer; the drawer's own specimens always show (F75) | Wil, Round 9 |
| C3 | ✅ *Built 13 Oct, to test.* **Date calendar pop-ups** styled once for the application (`shared/calendar_style.py`): readable Moss Green header, themed arrows, amber weekends, today in the accent — Quick Entry, When filter, Mark commercial, import wizard, Data Entry, date filters (F76) | Test 7 |
| C4 | ✅ *Built 13 Oct, Wil to run.* **Old-format sort keys** (`'000204…'` strings on 41 observations in the 10 Oct copy, incl. *Isoaeschna isoceles* 10743–4, whose TVK is superseded — the key comes from the current taxon *Aeshna isoceles*): `backfill_taxon_groups.py --fix-odd-keys` (dry run, backup, `--apply`) | Wil, Round 9 |

---

### Next (14 Oct, `claude/50`)

Photos only until the photos job is finished (Wil, 14 Oct: "no more branches"). Built and on the
PC: A1–A3, B1–B3, B5, bench photos, take 2 and photo rounds 2–4 (viewer, 📷 columns, OTHER
RECORD, dialog sizes, column widths, _Bench clean-up; `02b` Session 49). What is left of photos:
1. **Wil's review:** records/specimens with two photos that are different individuals -- sort 📷
   descending in Insect Collection / Observation Data, "Not this record" on the wrong one.
2. **Review spreadsheet for the 181 "several specimens" photos** -- 63 identical groups pair one to
   one by script; 28 differ and need Wil; a link per photo to open it.
3. **B4 phone Inbox intake** (Mosaic photos now come through Data Entry's Photo… button instead).
4. **Grid refs on photos** -- from the linked record; a box in intake; optional EXIF write.
5. Later, if wanted: "exported on" stamp so a second bulk export before the sync skips records
   already sent; main photo in the record dialog; photos in reports.

Later / parked: Specimens to check tab (design agreed; build after the Data Entry jobs Hook,
Notts, Coedely, Scunthorpe, Warwick are entered and committed). Lector walkthrough and tests. Test 36 (Drawer in hand on the
1280×720 laptop). F72's uncovered raw queries for hidden records: decide whether to sweep.

## Then: the big jobs (Q1 open; suggested order below, `04_Roadmap.md`)

| Job | Size | State of the decisions |
|---|---|---|
| **Specimens → records** | about half a day | All answered 12 Oct (Q23–Q33, below). Recommended first |
| **Final Recording Scheme dataset** (M1) | 1 h of questions, 2 sessions | Q4: questions straight after the next big job. Q72/Q73 answered; Q57–Q59 feed it |
| **iRecord round trip, then Photos** (lean plan below) | about 8 hours | A1–A3, B1–B3, B5 and bench photos done 13–14 Oct; left: viewer, review sheet, B4 intake, grid refs (Next, above) |
| **Partner's laptop install** | 8–11 days | **Winter**, after photos and the scheme dataset (Q2). Full suite (Q68). Separate databases, data moved by export/import (Q3). Her own empty database plus an optional practice database with sample data (Q69) |
| Optional: **map background layers** | 3–4 days | Q6, Q34–Q40 answered |
| Optional: **Atrium icons and restyle** | about 1 session | Q52/Q53: Claude drafts a silhouette for each app from the Observatum logo for Wil to approve; icon files in git are fine; Munia's look checked here |
| Optional: **splash and loading redesign** | about 1 session | Q51: after the Round 8 `--timing` (done): the bar follows the real steps, smooth animation |
| Winter: **C4 import wizard merge** | 4–7 days | Q84–Q87 answered (Q85 to confirm) |
| Winter: **report contents** | 2–3 sessions | Q74–Q80, Q83 answered |
| Later: **batch maps screen** | 1 session | Q41–Q50 answered; the script is enough for now |

### iRecord round trip and photos: the lean plan (agreed 13 Oct, late; replaces the staged plan)

Why the sync comes first: a photo link hangs on a record, so the record must keep one identity
from Data Entry through iRecord and back. Detail: `docs/drafts/photos_design_update.md`,
sections "13 October (late)" and "13 October (night)".

**Finding, 13 Oct 22:29:** iRecord **keeps an External key we supply.** Wil uploaded his 46
Farthinghoe records (26/06/2026, SP521403) with keys `OBS-WJH-IRTEST-20261013-0001…0046`
through the spreadsheet uploader; record 57539766 shows `OBS-WJH-IRTEST-20261013-0026`. The
download sent the same evening was older (newest input 19/06/2026, highest ID 53,796,418) and
does not hold them yet. The new importer fails with "Call to a member function load_values()
on false" (Wil to ask iRecord).

**Re-determinations (agreed 13 Oct):** the sync takes species and determiner from iRecord, so a
re-det made only in Observatum is put back by the next sync. Fix with A2: one side changed since
the last sync → that side wins; both changed → listed to choose. Editing a record that has an
iRecord ID shows "This record is in iRecord -- change it there too (Open in iRecord)". When a
record's species changes, its linked specimen photos move and rename with it (logged, undo).
A determination history is left until wanted.

| # | Stage | Est. | Notes |
|---|---|---|---|
| A1 | **Test the sync's matching** with the returned IRTEST records | ~5 min | ✅ *Done 14 Oct:* all 46 keys returned and matched (`check_irecord_download.py`) |
| A2 | **Sync guard:** key or ID naming several records held, not added; backup before every sync; **conflict check** (re-dets, local edits); the iRecord note on edit | ~1.5 h | ✅ *Done 14 Oct* (F83; `add_local_edited_column.py` run). Keys made unique first (F82) |
| A3 | **Personal jobs work like commercial:** Data Entry creates the record and its key at commit; the CSV carries it as External key; the sync pairs by key. "Check iRecord return" pairing retires | ~1 h | ✅ *Done 14 Oct; changed same day:* personal jobs just **Commit**; records go to iRecord in bulk from Observatum's export (External key), then the sync. Routine: export → upload → sync before the next export |
| B1 | **Consolidate specimen photos into Life** | -- | ✅ *Done 13 Oct 23:44* (below) |
| B2 | **Record ↔ photo links:** one small table (migration, dry run, backup); the 987 microscope photos with exactly one matching specimen linked by script. **No index of the library**: the species folder is the index | ~1 h | ✅ *Done 13–14 Oct* |
| B3 | **Photos button and window:** the species folder's photos, this record's first; "file not found" shown if a linked file is gone | ~1 h | ✅ *Done 13–14 Oct* (link / unlink by hand) |
| B4 | **Photo intake** -- one screen for the Mosaic folder and a phone Inbox folder: thumbnails with date and GPS grid ref; type the species once for a selection; then species only / attach to a record (suggested by species, date, place) / make a record (Data Entry row) / leave. Move and rename to the standard, log, undo | ~3.5 h | After A3. Check Pixel motion photos/RAW and phone GPS first |
| B5 | **Re-det moves the record's photos** (same move code) | ~30 min | ✅ *Done 13–14 Oct*, also for a re-det that arrives by sync |
| B6 | **Bench photos in Data Entry:** Photo… on a row (capture folder `Desktop\image`, setting; views head / gen / add your own); names "Amara aenea male gen 5.vi.26" (no capitals but the genus); photos wait in `Media\Photos\_Bench` and go to the species' Specimen folder at commit (species picked from the list only); a species change renames them in `_Bench`; deleting rows asks "back to capture folder / leave in _Bench". A specimen is never made from a record (added to the Insect Collection by hand) | -- | ✅ *Done 14 Oct* (take 2 after Wil's test; F84) |
| | **Total** | **~8 h** | Later, when wanted: main photo in the record dialog, determination history, photos in reports, stacking |

### Decided, waiting for its build

**Specimens → records (Q23–Q33):** a specimen is Wil's when the collector field names him,
alone or with others (Q23); the 147 "unknown" specimens are held back until those surveys'
field data are entered (Q24); commercial specimens matched only by season are **reviewed one
by one** (Q25); new Bicester Graven Hill records (97 from 109 specimens) take that survey's
embargo (Q26); none of the Personal top sites are surveys (Q27); **all 506 near misses linked
by hand**, no script (Q28); the 39 possible re-identifications checked by hand first (Q29); the
37 already in the scheme listed only (Q30); no other collection marked shareable yet (Q31);
the 2 with missing details left (Q32); no bulk "checked" script, drawer by drawer (Q33). Earlier:
one record per species/date/place with the count as a minimum; other people's specimens for
Wil's use only, never exported, unless "historic, unpublished: OK to share".

**Photos (Q5, Q13–Q22, Q71):** phone photos reach the PC by OneDrive camera upload into an
Inbox; Google Photos for viewing (Q5). The media library (45 GB) goes in the backup mirror,
**and the backup moves from the USB pen to one of Wil's larger external drives** (Q13, to
discuss). New-species Inbox photos go to `Life\_New species\<Genus species>\` (Q16); phone GPS
6-figure by default, 8 optional, a record only on "Make a new record" (Q17); credit "Wil
Heeney / Flauna Ecology", All rights reserved, changeable per photo (Q18); unlinked photos link
to the species (Q19); P10–P13 as recommended (Q20); the four Inbox choices are enough (Q21);
**a photo edited in Google Photos replaces the original** (Q22, not the recommendation; the
build must say what happens to the original file). **Microscope (Q71): capture to the Inbox,
not only stacked images** (single captures too, so P3 changes); a live view maybe; look into
coding focus stacking or driving the free stacking software Wil uses.

**Map layers (Q6, Q34–Q40):** OS Open Zoomstack, one 3.8 GB download (Q6); rivers and lakes on
by default, the rest off (Q34); **districts from current OS Boundary-Line** (Q35, not the
recommendation) under the label "Local authority districts" (Q39); the atlas PNG prints what is
ticked (Q36); phase 2 (SSSI/NNR, ancient woodland) later (Q37); the map credit built from the
layers drawn (Q38); VC boundary colour and width kept (Q40).

**Batch maps (Q41–Q50):** screen later (Q41); date classes pre-1970 / 1970–99 / 2000–19 / 2020+,
editable (Q42); class by first record, latest as an option (Q43); cumulative frames, new squares
in a second colour (Q44); decades from 1950 plus "to 1949" (Q45); `Genus_species_grid_area.png`
(Q46); `Documents\Observatum batch maps\<date>_<label>\` (Q47); one A4 page per species (Q48);
keep an empty species' page and index row (Q49); longhorn checklist order (Q50).

**Scheme dataset and data clean-up:** statuses not reviewed / in the final dataset / set aside
with a reason (Q72); review by rules, exceptions by hand (Q73); the 39 "unclear" and 173
small-dataset 1 January dates left and flagged in the final dataset (Q57, Q58); month charts do
not follow the counting switches (Q56); the 5 genus "hybrids" fixed in iRecord (Q62).

**Reports and Examen (Q74–Q83):** the Word export stays an appendix (Q74); no visit table for
now (Q75); no auto-drafted limitations (Q76); **a project field for ISIS compliance** (Q77); a
generated data-sharing sentence **and** a Codex "sensitive species" flag (Q78); no LERC import
(Q79); quote the CIEEM 2019 validity bands (Q80); **keep the SQI 150/125 colour bands** (Q81,
F14 closed as Wil's choice); no approach to Adrian Fowles: Wil exports and keeps his own
saproxylic lists per site (Q82); Examen appendices in order → family → genus, then alphabetical
(Q83; revisit for Examen; drawers not answered).

**C4 wizard merge (Q84–Q87):** taxonomy overwritten from UKSI on a match (Q84); the stored name
becomes the UKSI name (Q85) -- **this differs from the note-41 answer "keep the recorded name"
on synonym remaps; suggested: keep the recorded name in a separate "name as recorded" field.
Confirm when building C4**; a name not found in a sync is a warning (Q86); a re-import changes
a narrow field list and never blanks a field (Q87).

**Housekeeping:** merge `main` into `stable` now that Round 8 is committed (Q88, D3, F2);
Spider Extract SPD1–3 at the next free slot (Q91; separate repo).

---

## Lector (paused 12 Oct, Q7)

Built and tested: Rounds 7 and 8 (9 of 9 tests). Decided, to build when Lector resumes:
- "N runs" on the dashboard counts fetch runs only (Q94).
- A "+" line in `data\lector_synonyms.txt` wins over the suite corrections list (Q95).
- "Archive" a saved search: hidden from the dashboard, kept, restorable (Q97).
- Kept as built: Steel Blue accent and ticks (Q8, Q92); console keeps saved searches unless
  `--replace-search` (Q93). (Q96, the Square opacity slider, is Observatum's: kept as built.)
- Later, only if wanted: species-list searches (Q9); non-English journals with Argos offline
  translation for French/German, stored beside the OCR text and marked as machine translation
  (Q10); whether literature records become Observatum records is to decide later (Q11).

Waiting when Lector resumes: a rundown of how Lector works, then the test on a clean
`lector.db` (the current file set aside, not deleted); the manual checklist (A–N, about 130
items) in `docs/Lector_User_Manual.md`; later, final manuals for Lector and Observatum built
from annotated screenshots.

Wil's own steps in the window: untick the four held-back *Lamia* names (*L. rosenmulleri*,
*sartor*, *sutor*, *titillator*) in Edit and Save draft (his Test 2 Save and run stored them as
his choices, so `fix_lector_name_choices.py` rightly changes nothing); turn on "Skip index
pages" for *Lamia textor* (Q12); check the *Lamia* withdrawn list for wrongly dropped British
titles (Entomologist's Monthly Magazine apostrophe; Scottish Naturalist); re-export (the
`Lamia_textor.txt` / `_index.csv` in the exports folder are the old 111-page ones).

---

## Still Wil's to decide

| Q | Question | Note |
|---|---|---|
| Q1 | The next big job after the small fixes | Recommended: specimens → records |
| Q13 | Where the backup goes: move from the USB pen to a larger external drive | To discuss with the photos job |
| Q14, Q15 | Photos: stacked/no videos; no auto-confirm, one "Confirm all" button | No preference given: the recommendation stands unless changed (Q71 already widens P3) |
| Q60 | Embargo of Badshot Lea (190), Bicester 2023 (960), Kent Deadwood (28) | Revisit |
| Q61 | The 28 no-match names | Default: wait for the next UKSI; *Astur* → *Accipiter gentilis* by hand if wanted |
| Q70 | ✅ *Answered 13 Oct:* **TrueChrome 4K Pro**, captured with its own software **Mosaic** | Photos design note, 13 Oct section |
| Q71 | Which free stacking software Wil uses (not on the current PC; Mosaic does not stack). Stacking is not needed for the first stage (13 Oct) | Needed to decide "drive it" vs "code it" |
| Q83 | Checklist order for the collection drawers | Examen part answered |
| Q85 | Confirm the "name as recorded" field idea | When building C4 |
| Q11 | Literature records into Observatum | Later, with Lector |

---

## Reminders (no answer needed)

- `D:\` copy refreshed 13 Oct (robocopy run; confirm FAILED 0 and the read-only integrity check
  next time it is run).
- Test Observatum and Lector on a real laptop (the 150 % scaling check passed).
- Partner install: check `uk_vice_counties.svg` and `family_common_names.json` are present.
- ✅ VC outline file rebuilt on the PC 13 Oct (112 VCs, 15.0 MB; the old 2 MB file kept as
  `vc_brc_wgs84_before_20261013_195800.geojson`). Watch whether Mapping opens slower; if so,
  raise `SIMPLIFY_KEEP_EVERY` (now 5) in the script and re-run.
- `fix1_lector_years_dupes.py` can go from the project root (copy in `_archive\lector_fix1_20261011\`).
- Photos: before the Inbox build, check how the OneDrive app handles Pixel motion photos and RAW.
- Photos, 14 Oct: 30 specimen names standardised (log `data\photo_moves\redet_20261014_113022_938260.csv`;
  "Stenus similis B" became "b" -- check). `Philonthus laminatus gen 31.iii` has no year.
  Cleaning report > Photos… lists empty folders, `_Bench`, missing files and names to fix.
- Keys renumbered 14 Oct (2,719): old -> new in `scripts\_oneoff\renumbered_keys_20261014.csv`;
  backup `observatum_pre_renumber_keys_20261014_113137_100438.db`.
- 47 Elmley records (8 Oct entry, OBS-WJH-20261008-000001…047) not yet in iRecord: include
  four non-invertebrates (Cattle Egret, Mediterranean Gull, *Ballota nigra*, *Rumex crispus* ×2).
- Read NERR005 Table 17, p. 86, from Wil's copy before settling the report template.
- Slade Green: waiting for Wil's instruction.
- Photos moved 13 Oct 23:44 (1,469; log `scripts\_oneoff\photo_moves_log_20261013_234407.csv`;
  undo with `move_photos.py --reverse <log>`). Backup in
  `C:\BiologicalSoftware_Backups\photos_before_move_20261013\`. The emptied Microscope Photos,
  Dead Spiders and Dead Craneflies folders are left in place (Thumbs.db etc.): Wil retires them
  when happy. 15 photos in `Photos\_Photo review\`, 5 copies in `Photos\_duplicates_20261013\`.
- iRecord test upload (13 Oct): send the next download once it holds the 46 IRTEST records;
  Claude checks all 46 keys read-only before the sync. Ask iRecord about the new importer's
  `load_values()` error and whether an External key survives a verifier's edit. Survey shows
  "iRecord Import" and observation type "MV light trap": check before a real upload.
- iRecord: delete the 635 double submissions (D11); check the next sync, then retire
  `observatum_pre_sync_20261009.db` (D12).
- Download the Welsh S7 2026 xlsx (F6); questions for Chris Raper, including the *Lamia* rows (F11).
- Five survey key species still need accounts (`02` §3).
- Munia: no development; check its look from Atrium during the icon job.

---

## Gathered 12 Oct: mentioned somewhere, not yet on a list

From the sweep of notes 30–46, the repo docs, the drafts, the agent briefs and reports, and
`40_Code_Sweep` / `41_Groundwork`. Each still needs a decision or a slot.

| Item | Source |
|---|---|
| Final user manuals for Lector and Observatum from annotated screenshots | note 44 (plan 15:46) |
| Lector: `py -m Lector gui` from a bare prompt needs Observatum on `PYTHONPATH` (the launcher sets it); make it find it itself or say so | R8 docs agent report |
| Splash and loading: Wil wants to discuss them again (separate from the Q51 redesign?) | note 44, R12 Test 2 |
| Startup: one pause over 100 ms remains (stats order grid build, 106 ms) | PC `--timing` 12 Oct |
| Recording Scheme tab: the loading overlay (`_stack`, `_loading_label`) is never built, so **load errors are never shown** | `40_Code_Sweep` §1 (open, low) |
| Observation edit dialog: changing the species leaves taxon rank, kingdom, taxon group, superfamily, subfamily and sort key stale; the VC cannot be cleared | `40_Code_Sweep` §2 (latent) |
| `ObservationModel.create` fixed column list omits `import_notes`, survey and sort-key columns (callers patch with an UPDATE) | `40_Code_Sweep` §2 (latent) |
| Observation import: the Observatum key sequence falls back to 0 on a DB error, uses 4 digits against the model's 6, and finds the last key by string sort | `40_Code_Sweep` §3; `41_Groundwork` §1.3 |
| Observation import: personal duplicate check still inside `except: pass`? (check whether the 9 Oct repair made it loud) | `41_Groundwork` §1.3 |
| Specimen import: the fuzzy lookup is unguarded (an error hangs the wizard on validation); cp1252 files refused; sex never imported | `41_Groundwork` §1.2 P5 |
| Scheme import: "Skipped duplicates" always 0; cf./agg. retry swallows errors; `SchemeImportRow` declares ~20 fields twice | `41_Groundwork` §1.1 S9 (check after I7b) |
| Scheme records can't be deleted in the app (by design since Round 2): a wrongly imported scheme file can only be undone by script. Say so in the scheme import wizard, or give a "remove this import batch" script | import test files agent, 12 Oct |
| Saproxylic E7 follow-ups: cumulative scope (other record types for a site), SQI for non-beetles, families with no modern review scored on 1999 statuses, show Alexander's 300 band | `41_Groundwork` E7 §8 Q4–Q7 |
| `shared/checklist_order.py` and the drawer and batch-map hooks exist, but there are no checklist files yet (`shared/checklists/*.csv`) | code; A1, Q50, Q83 |
| Longhorn checklist CSV for batch-map order (Q50) | `drafts/batch_maps_design.md` Q9 |
| Batch maps: "decade" period option in the Mapping tab was never implemented | `03b` H1–H6 note |
| Specimen links: has `link_specimens_to_observations.py --apply` (about 1,115 certain links) been run on the PC? The notes say "held" (note 40) and "optional" (note 41) | notes 40, 41 |
| Observation Data autoload: settled by Round 6 (loads under the splash) | note 42 open decision (closed) |
| Species search index built last in the background: settled | note 43 (closed) |
| Gamification display issues (long term) | note 39 §4.10 |
| Exploratory: Observatum as host for IUCN Red List assessment support | note 39 §4.6 |
| Repo inside OneDrive: `.git` lock friction; revisit if it worsens | note 39 §4.9 |
| Performance list (cache_size/mmap, Qt model flags, fixed row heights, virtual table model) | note 39 §4.9 |
| DataEntry map shims: land the switch to `shared/maps` when Wil is not entering data | `03b` H1–H6; note 39 §4.8 |
| Philanthus triangulum carries an outdated RDB2 in Codex: check for a newer status and record it | Betteshanger analysis, 12 Oct |
| Map credit, boundary colour, district label: answered (Q38–Q40) | note 42 |

---

## Done since 10 October (for the record; detail in `02b_History.md`)

| Round | Built | Tested |
|---|---|---|
| Round 2 (10 Oct) | Old backlog A–F: counting switches everywhere, Cleaning Report, scheme read-only, scheme duplicate report, Home cards; small wins L8–L34; the note-36 decisions | Round 9, tests 1–43 (39 superseded, 40 skipped) |
| Round 3 (11 Oct) | R9-1 to R9-8, F43 script, specimen Field record box and scripts, batch maps script, photo groundwork; decisions D1–D8 | Round 10, 23 of 23 |
| Round 4 (11 Oct) | VC labels and boundaries, districts switch, coast, startup on first opening, narrow window, View scheme records, 1 January dates, specimen breakdown, Sundon | Round 11, 13 of 13 |
| Rounds 5–6 (11 Oct) | Borders drawn once, draw order, Home All card, laptop sizes, then "window early, rest behind" | Round 12, 4 of 4 |
| Round 7 (12 Oct) | Lector stage A (fix2, LEC1–6, saved searches, service) and the desktop window | Lector, 9 of 9 |
| Round 8 (12 Oct) | Lector L1–L16, Observatum O1 (pause) and O2 (square opacity), Lector manual, review fixes | Outstanding tests, all passed 12 Oct |
| Tests only (12 Oct) | B8 Check before commit; E3 Examen PDF; import test files (`tests/manual_import_files/`) | passed |
| Handover tasks (13 Oct) | One place for saved filters; cleaning report rows open Record Detail + Hidden here tile; disabled look on every button style; Species Lookup list painter; tests in parallel (`-n 6`) | all passed 13 Oct |
| 13–14 Oct | B2 links, B3 Photos window, B5 re-det moves; A2 sync guard (F83), A3; one key rule and renumber (F82); bench photos and take 2 (F84); cleaning report Photos | Wil, 14 Oct: tests and full suite 1,431 passed (bench photos); take 2 being tested |
| 13 Oct (night) | A1 download check; B1 plan, review sheet, standard photo names (`15.ix.17`, sex lower case), move list, mover with log and reverse; 1,469 photos moved into Life | Wil, 13 Oct: tests, full suite 1,386, dry run 0 problems, move checked |

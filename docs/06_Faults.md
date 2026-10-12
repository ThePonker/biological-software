# Faults

## Updated 12 October 2026
## Open faults carry an action. Closed ones are kept in brief, because knowing
## what has already gone wrong is how the rules in `05` were earned. Older closed
## faults are in `06b_Faults_Closed.md` (split out 12 Oct). New faults take the
## next free number (F68 next).

---

## Open

### F2. `stable` branch stale since June
The Data Entry build and four months of work sit on `main` only. The branching
discipline exists precisely so `stable` can be the field-season tool.
**Action:** merge once the staging jobs are committed and proven — backlog D3.
*12 Oct:* Rounds 2–8 are committed and pushed on `main`; Wil decided to merge into `stable` now (Q88).

### F49. Species search lists: clipped rows, boxed names, odd group choices -- FIXED 12 Oct (Round 9 A, to test)
*Found 12 Oct (outstanding Test 2, search "beetle").* The list's rows are cut at the bottom
(descenders of *Aclypea opaca*, *Agabus brunneus*); each name and common name is drawn in a
bordered box; a plant genus is offered as a group ("All Leptochloa (beetle-grass) — group");
brackets are doubled ("All Curculionidae (beetles (weevils)) — group"). Wil also wants the
group choices at the top when the typed word is a group word. **Action:** small-fixes round,
item 1.
**Fixed (Round 9 A):** Codex's list was a column of labels in a frame whose `QFrame { border }`
rule reached every label (a QLabel is a QFrame) -- the boxes -- and 25 rows were squeezed
into the space above the profile -- the cut tails. One shared row painter
(`shared/species_list_delegate.py`: italic name, grey common name, small grey rank; row
height from the font) now draws Codex, Examen's Species Database and Observatum's species
box (its fixed 32 px rows gone). Group labels have one level of brackets ("All Curculionidae
(weevils) — group"; "flies", not "flys"). The lists offer groups of animals only
(`LIST_GROUP_KINGDOMS`); the filter boxes still see every kingdom, so what they select is
unchanged. A typed group name ("beetle", "ladybird", "longhorn", "moth") lists its group(s)
first; a species named exactly as typed ("Dor Beetle") still comes first.

### F50. Drop-down popups are see-through -- FIXED 12 Oct (Round 9 A, to test)
*Found 12 Oct (Test 3, Quick Entry).* The Project list's popup has no solid background: its
items draw over the form behind (the hint, the iRecord tick, the Dropdown Options box) with a
text shadow. Probably every styled combo popup. **Action:** small-fixes round, item 2.
**Fixed (Round 9 A):** the cause was a panel style sheet with no selector
(`background: transparent; border: none;` round the Project box) -- it reaches the combo's
pop-up list too. 30 such sheets in the suite, 58 combo boxes. `shared/opaque_popups.install()`
(called once at start-up in Observatum, Data Entry, Examen, Codex, Curator and Lector) gives
any pop-up list that comes out see-through a solid theme background; lists already solid
are left alone.

### F51. Observation import: a species picked by double-click loses what the file had -- FIXED 12 Oct (Round 9 A, to test)
*Found 12 Oct (import test files).* In the observation wizard a double-click pick keeps no
"File had …" note and the original name is lost; the pick list says "resolved by you as",
the double-click (scheme and specimen) "picked by you as"; the scheme wizard numbers rows
from 1, the others from 2. **Action:** small-fixes round, item 3.
**Fixed (Round 9 A):** the observation wizard's double-click applies the pick as the other two
do (⚠ "File had 'Ab'; picked by you as …", note "Imported as 'Ab'; picked by you as …"), and
a later revalidation of the row keeps the pick; the Species cell is no longer typed in.
"picked by you" in all three wizards and the stored note. All three number rows as a
spreadsheet does (heading = row 1, first record = row 2); the Row column's tooltip says so.

### F52. Butterflies labelled "insect – moth"
The importer's order → group map sent every Lepidoptera record to "insect – moth"; 42
butterfly records carry it. The map has been the one in `shared/taxon_groups.py` since 10 Oct
(butterfly families first). **Action (12 Oct, R9 B1):** Wil runs
`backfill_taxon_groups.py --relabel-only --tables observations` (dry run: 42
'insect - moth' → 'insect - butterfly', nothing else), then `--apply`.

### F53. Scheme records held twice (iRecord and NBN copies)
34,121 pairs share an iRecord ID: NBN's "Longhorn beetle data from iRecord" is iRecord again
(`report_scheme_duplicates.py`, read only; also 910 exact, 11,269 likely, 7,694 possible).
Scheme counts and maps count such a record twice. **Action:** small-fixes round, item 6:
flag the NBN copy so it counts once (Q59; flag, not delete, reversible); the other tiers in
the final dataset (M1). *Built 12 Oct (R9 B3):* `recording_scheme.duplicate_of` (added and
filled by `scripts/mark_scheme_irecord_duplicates.py`, `--undo` clears it), one rule in
`shared/scheme_duplicates.py` used through `shared/species_counting.py`; the Scheme tab's
"Show duplicates" lists them. Wil to run the script (dry run 34,121 on the 10 Oct copy).

### F54. Pantheon links *Sympetrum nigrescens* to *S. striolatum*
*Found 11 Oct (Sundon).* A fault in Pantheon's link table, seen in Pantheon Only mode; Codex
Full is unaffected. **Action:** a flagged local correction to the bridge (Q67), small-fixes
round, item 8. *Built 12 Oct (R9 B4b):* `shared/pantheon_bridge_corrections.csv` (two Pantheon
taxa: the Latin and the English-named nigrescens); strict key species −1 at six surveys (`02`).

### F55. *Philanthus triangulum* carries an outdated RDB2 in Codex
*Found 12 Oct (Betteshanger analysis).* An old status still shows for a now common wasp.
**Action:** find the newer assessment (Falk 1991 is loaded as internal reference only) and
record it the usual way (`07_Codex.md` §8); check for other aculeates in the same state.

### F56. 1 January placeholder dates in the Recording Scheme
11,363 scheme records sat on exact 1 January dates (year-only records padded). **Fixed for
18 padding datasets 11 Oct:** 11,149 records set to year-only (`fix_jan1_dates_20261011.py`,
backup taken; January bar 11,648 → 499); the NBN importer now reads date precision. **Left
by decision:** the "unclear" iRecord longhorn dataset (39) and 27 small datasets (173), to be
flagged in the final dataset (Q57, Q58).

### F57. Dates before 1700 in the scheme
*Alosterna tabacicolor* 1500; *Acanthocinus aedilis* and *Agapanthia villosoviridescens* 1675.
They put squares in the earliest date class. **Action:** a cleaning-report check (Q65),
small-fixes round, item 5. *Built 12 Oct (R9 B2):* "Date before 1700" tile, list and sheet;
132 scheme records on the 10 Oct copy (121 Cerambycidae Dataset 1675, 7 ISR 1500, …).

### F58. A test-order flake
`test_window_width_r4` fails when run before `test_small_fixes_20261010` (note 43). Not the
map flake fixed on 12 Oct (F47), as far as the notes show. **Action:** small-fixes round,
item 9.

### F59. The Recording Scheme tab never shows a load error
`recording_scheme_tab.py`'s loading overlay (`_stack`, `_loading_label`) is guarded but never
built, so a failed load shows nothing (`40_Code_Sweep` §1, open, low). Round 6 added its own
"Finishing loading…" cover; check whether a background load error is now shown.
**Action:** the review-leftovers sweep (small-fixes round, item 11).

### F22. The July 2025 UKSI flags 24 British beetles redundant
No current replacement for *Nialus varians*, *Trichonotulus scrofa*, *Subrinus
sturmi*, *Bolitobius formosus*, *Ochthebius difficilis*, *Cypha ovulum* and 18
more, all of which you consider accepted British species. Kept selectable in
`uksi.db`, marked "not current in UKSI 2025 -- kept at your request" in
`taxon_qualifiers`; *Nialus*, *Trichonotulus* and *Subrinus* shown under the
accepted combination. **Action:** raise with Chris Raper -- backlog F11.

### F23. Names newer than the July 2025 UKSI
66 JNCC TVKs (statuses held in Codex but attached to no UKSI species) and 7 record
TVKs on 42 observations; one review account (*Tetartopeus ciceronii*) unloadable.
No survey figure affected now. **Action:** a newer UKSI -- backlog F11, F13.
*11 Oct:* `report_tvks_not_in_uksi.py` and a one-off fix remapped 16 records; **28 records are left with no match** (*Astur gentilis*, redpolls, *Collybia*, *Cnephaeus*, the earwig agg.). Default: wait for the next UKSI (Q61, no preference given).

### F25. `uksi.synonyms`: what is left (search and Lector only)
Fixed 9 Oct (`fix_uksi_synonyms.py`, 403 rows; the history is in `06b_Faults_Closed.md`).
**Still open:** the 366 CONFLICT rows carried over from the old file, and NAMES-sheet errors
such as the *Lamia* rows, which are excluded locally (`scripts/uksi_synonym_corrections.csv`)
and must be reported to the NHM (F11). Lector holds such names back with a reason; on 12 Oct
Wil decided his own "+" line in `data\lector_synonyms.txt` should win over the suite list (Q95,
to build when Lector resumes). **Action:** backlog F14 (`03c`).

### F34. Imports never store the taxonomic sort key, superfamily or subfamily
*9 Oct (C4):* still open -- the observation worker reads `self.uksi_conn`, which is never set;
left alone during the wizard merge because fixing it changes import outputs.

*Found 8 October 2026 by the code sweep, §1.* The observation validation worker reads
UKSI through `self.uksi_conn`, which is never set; the error is swallowed, and the
row builder would not copy the values anyway. The specimen worker swallows the same
lookup's failure -- a NULL sort key hides a specimen from the collection sidebar (the
244-specimen fault below). **Action:** backlog I7b.
*12 Oct:* the scheme and specimen halves were fixed with I7b on 9 Oct (`shared/import_core.py`; specimen sort keys from each row's final species). Left: the observation worker, which costs nothing because nothing reads these fields for observations. In C4, swap it for `taxonomy_for_tvks`.

### F41. The import wizards' Species Match Report never opened
*Found and fixed 9 Oct 2026 (I8 import check).* `species_match_report_dialog.py` sits in
`views/dialogs/` but imported `....themes` (four dots: one level too far), so opening the
report raised ImportError, which the wizards caught and printed ("Match report error").
Behind it, re-matching a name set the row's status with the stale wizard set's `RowStatus`,
a different enum from the wizard's own, so a re-matched row would have equalled neither
VALID nor WARNING. Both fixed: three dots, and `type(row.status)`. Not yet tried in the app.
*12 Oct:* the Resolve Unmatched Species window was used in all three wizards in the import tests (Round 9 tests 30–31, passed); the separate Species Match Report has still not been seen opened.

### F5. Curatorial fields almost empty across the collection
Of 2,745 specimens: preparation 204, condition 8, storage 2, drawer 0. Curator
does not write them; the Add Specimen dialog captures four, but only for new
specimens. **Action:** bulk editor — backlog A1.
*12 Oct:* the bulk editor (A1, "Drawer in hand…") is built; filling is ongoing, drawer by drawer.
Wil reset all drawers on 12 Oct (428 specimens) because nothing could be removed or moved;
Round 9 C added remove, move and "Empty this drawer…" (03b, A1), and fixed F67.

### F6. Two parallel enrichment paths in Examen
`site_analysis_view` imports `load_all_projects` from `examen_data` **and** takes
`analysis_service`. The project table and the detail tabs are populated from
different sources, so their figures can disagree. The percentage denominators
have been reconciled, but the structural split remains.
**Action:** backlog E5.

### F7. Stored SQS does not follow Pantheon's published rule — INFORMATIONAL
Not a fault in this codebase, but it governs every SQI produced. Applying the
published rule to current Codex statuses agrees with **85%** of Pantheon-sourced
invertebrate scores. The remainder has three causes: genuine post-2017 review
updates, undocumented Pantheon overrides, and Pantheon not applying its own
arithmetic — *Phengaris arion* stored at 8 while Critically Endangered;
*Anastrangalia sanguinolenta* NR + CR stored at 8 where the rule gives 32.

**Decision: compute both, state the basis, do not switch by default.**
Comparability with published SQIs is the point of a standard index.
See `35_SQS_Stored_vs_Derived.md`.

### F8. Unrouted designation codes
1,519 rows across 16 codes reach no track. Most is deliberate (`NR-excludes` 732,
`NS-excludes` 666, `WL` 76), but European Red List, bird breeding-season RE/DD
and some Global pre-94 codes fall through unmapped. **Action:** backlog F2.
*12 Oct:* routed in code 9 Oct (backlog F2); confirm at the next Codex rebuild that the +37 rows arrived.

### F9. England assessments in the GB threat track
2014 England vascular plant entries carry GB abbreviations
(`RedList_GB_post2001-EX`) despite an England source, so they route to
`threat_iucn_2001` rather than `red_list_england`. JNCC's labelling, not a fault
here. Vascular plants only. **Action:** backlog F3.

### F15. Two specimens without a TVK
*Phoracantha recurva* (id 1263) and *Oberea linearis* (id 1356). No TVK, so no
sort key, so invisible to the sidebar. Both came in from the March import as
"Species not found" against the 2023 UKSI. **Action:** backlog A5 -- fix script
run 8 Oct: **neither is in the July 2025 UKSI**. Left as they are, by decision --
no TVK, no sort key -- until a UKSI release includes them.

### F16. `subfamily` stored inconsistently
NULL on some rows and `''` on others for the same species. The sidebar now
normalises; the data does not. **Action:** backlog A7.

---

### F18. Does Env (Wales) Act S7 carry the research-only qualification?
At a Welsh site, Cinnabar and Latticed Heath still count as key through S7.
Whether S7 inherited the UK BAP research-only category needs the Welsh source
documents, not an assumption. Machen's key species did not move. **Action:**
backlog F6. *Researched 8 Oct (`39_Research_Notes.md` §2):* the Welsh S42/S7 lists
carry **no** research-only flag; Cinnabar is on S7 -- current behaviour is correct by
the list. A new Welsh S7 spreadsheet (May 2026) is still to be compared with Codex.

### F19. Taxa split since 2017 lose their Pantheon data
*Nomada panzeri*: records carry the sensu lato TVK; the bridge mapped Pantheon's
2017 *N. panzeri* to the sensu stricto TVK, so the record got nothing. **Fixed for
*N. panzeri* and the 17 other same-name cases on 8 Oct** by the NAMES-by-key bridge
(F25): NAMES sends the 2017 key to the concept the records use (Kent Pantheon-only
SQI 176 → 175). **Action:** F7 (read-layer fallback by name) only if another case
turns up.

### F20. Open habitats SQI 2 points above the Pantheon website at Glory Park
125 against the report's 123, same 96 species. Every other figure matches
exactly. Most likely one score differing between Pantheon 3.7.4 (held) and 3.7.6
(website). **Action:** none unless it recurs; note only.

### F11. Mixed line endings
Some files LF, some CRLF. `.gitattributes` added, but existing files are
unconverted, so multi-line string anchors still fail unpredictably.
**Action:** prefer line-based patching. See `05_Rules.md`.

---

## Closed since 10 October

### F47. VC boundary layer drawn from the land's borders after the first paint -- FIXED 12 Oct
*Found by the Round 8 review.* On a PC without `gb_outline.json` the land is drawn from the
VC rings, and its edge split was cached under the same key as the VC boundary layer
(`("vc", geojson, "r5")`). Whichever was worked out first served both: after a first paint
(coast first) the boundaries were the land's unsnapped borders, every shared border twice
(32,165 km instead of 19,136 km). Also the cause of a test-order failure
(`test_mapping_r5.py::test_real_vc_borders_drawn_once`). The boundary layer now has its own
key (`shared/maps/map_layers.py`). **Rule:** a cache key names every input (`05`).

### F48. A 1.2 s pause while Observatum finished loading -- FIXED 12 Oct
Round 6 on the PC: longest GUI pause 1,231 ms (Linux about 145 ms). Causes (Round 8 O1): a
table sizing its columns to their contents behind the map-loading thread, and Python's
garbage collector running during loading; also big geojson pieces and Settings built in one
go. Fixed: `settle_headers`, garbage collection off during loading then frozen, smaller
pieces, Settings per panel. PC after Round 8: longest pause 106 ms; `--timing` now lists
every pause over 100 ms and where it happened (`Observatum/src/views/pause_watch.py`).

### F60. Closing during the background load crashed Observatum -- FIXED 11 Oct
"QThread destroyed while running": closing while the Recording Scheme still loaded aborted
the process. `closeEvent` now stops and waits for the load before the WAL checkpoint (Round 4
review). Retested Round 12 Test 3.

### F61. Settings changed before the Scheme tab opened showed the old records -- FIXED 11 Oct
Records loaded in the background were not re-read when Settings (scheme families, species
counting) changed first (110,510 records shown with families = Carabidae). Fixed (Round 4
review); retested Round 11 Test 12.

### F62. VC labels garbled on Windows when zoomed -- FIXED 11 Oct
Outline and fill drawn with different spacing under the zoom transform (red and blue
fringes, doubled letters). Labels are now drawn in device pixels as one path (Round 4).

### F63. Every shared VC border drawn twice; slivers in the tint -- FIXED 11 Oct
Neighbouring VC rings, thinned separately, crossed every few hundred metres: double grey
lines at 300 dpi and pale slivers. `shared/maps/vc_topology.py` snaps shared borders to
common points and each edge is drawn once (Round 5).

### F64. Data Entry forced the window to at least 1,563 px -- FIXED 11 Oct
Found on the PC by `test_banner_cards_fit_the_window` (Round 3). The banner now measures its
cards at runtime and never forces the window wider than it is.

### F65. Lector: the update ticked held-back names as Wil's choices -- FIXED 12 Oct
The first `lector.db` update recorded the names of old `--synonyms` fetches as Wil's own
choices, overriding the hold-back (*Lamia* rosenmulleri, sartor, sutor, titillator). The
update now checks old names as a new search does (Round 8 L5);
`scripts/fix_lector_name_choices.py` clears the update's choices. On Wil's PC it found
nothing, because his Test 2 "Save and run" stored those ticks as his own: he unticks them in
Edit and saves (`03_Backlog.md`, Lector).

### F66. Lector console overwrote a saved search -- FIXED 12 Oct
`python -m Lector fetch` and the interactive console replaced a species' saved names and
filters (losing ticks made in the window), and console exports overwrote the window's files.
Now they leave a saved search alone unless `--replace-search`, and console exports are named
`<Species>_all_pages…` (Round 8 review).

### F67. Edit Specimen blanked preparation, condition, storage and drawer -- FIXED 12 Oct
Found in Round 9 C (checking Edit Specimen as the fallback for moving one specimen). The
dialog never filled these four boxes from the specimen being edited, but saved them, so
saving ANY edit wrote them back blank (or the order's default preparation): a specimen put in
a drawer by Drawer in hand lost its drawer the moment it was edited. Storage was also a fixed
list ("Cabinet", "Useful Box", "Storage box"), so "Cabinet 1" could not be shown or typed.
Now the four are filled from the specimen and the three lists accept any value. Specimens
already edited cannot be told apart in the data: any drawer, storage, condition or
preparation lost that way has to be set again.

### F45. Records and species counted differently from screen to screen -- FIXED 10 Oct
Backlog A (Round 2): one counting rule per source (`shared/record_kinds.py`,
`shared/species_counting.py`), applied on Home, Stats, Mapping, Species lookup, achievements,
exports and the Data Entry map; tables dim excluded rows. Retested 12 Oct: Home's All card
and Observation Data agree (24,827 records, 3,163 species).

### F14. The SQI colour bands (150 / 125) -- CLOSED 12 Oct as Wil's choice
The verdict sentence went on 8 Oct (E16). The table colours keep 150 / 125 for green / amber
by Wil's decision (Q81). The fault's history is in `06b_Faults_Closed.md`.

### F43. "Melanotus" on the fungus genus TVK -- FIXED 11 Oct
The one-off script moved the 10 records to NHMSYS0000079906 on the PC (backup first); see
`06b_Faults_Closed.md`.

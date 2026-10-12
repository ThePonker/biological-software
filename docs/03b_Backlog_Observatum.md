# Backlog by area: Observatum, Data Entry, imports, mapping, infrastructure

## Updated 12 October 2026
## Split out of `03_Backlog.md` on 12 Oct (it had reached 866 lines). The working list
## (what to do next, open decisions, reminders) is `03_Backlog.md`; Examen, Codex,
## species profiles and code hygiene are in `03c_Backlog_Examen_Codex.md`.
## Done items keep a one-line record of when; the detail is in git history.

---

## A. Insect Collection

**A1. Bulk curatorial editor.** ✅ Built 8 Oct ("Drawer in hand…"); only the checklist-order
question below is open, parked by Wil. *Original:* 0.5–1 day. Of 2,745 specimens: condition
8, storage 2, drawer 0, preparation 204. Those are properties of a tray, not a
specimen — select everything in a drawer, set Storage and Drawer once.
Per-record editing is not viable. Never touches biological data.
*Built 8 Oct — "Drawer in hand…"* on the Insect Collection toolbar
(`views/collection/drawer_assign_dialog.py`, rules in `shared/drawer_assign.py`, tested):
pick storage + drawer, tick specimens in taxonomic order under genus headings
(order › family › genus tree), optional condition/preparation (empty fields only),
preview, backup, one guarded write; "Next drawer" steps the number. Specimens recorded
in another drawer are greyed. Records where specimens are; Curator plans layouts.
Mock-ups (incl. tidy values, from a spreadsheet: not built) on the "Bulk Curatorial
Editor" canvas. **Open question:** "taxonomic order" is the collection's sort key, i.e.
UKSI's sort code -- alphabetical by genus within a family (Carabidae: *Abax*,
*Acupalpus*, *Agonum*…), not checklist order (*Carabus* first).

*12 Oct:* Examen's appendix order is answered (Q83: order → family → genus, then
alphabetical); **the drawer order is not**. The engine exists (`shared/checklist_order.py`,
used by `drawer_assign.py` and the batch maps) but no checklist file has been made
(`shared/checklists/*.csv`).

Sex is the exception: it needs the animal under the scope, and is being worked
through by hand (602 so far).

**A2. Verify curatorial edit on existing specimens.** ✅ Tested by Wil 9 Oct: saves and reloads. Small. May already be
closed by the Session 29 dialog work — test by editing one and confirming it
saves and reloads.

**A3. `label_data` composition from the record.** 0.5 day. Deferred.

**A4. `drawer_unit` → `drawer_number` rename.** ✅ Done 9 Oct -- code in 16 files;
the database column via `_oneoff/rename_drawer_column_20261009.py` (backup first). 0.5 day. The UI already says
Drawer Number. Column empty, no data risk; touches four files plus reset scripts.

**A5. Two specimens without a TVK.** ✅ Closed by decision 8 Oct (not in the July 2025 UKSI). Minutes. *Phoracantha recurva* (id 1263) and
*Oberea linearis* (id 1356) — both longhorns. With no TVK they get no sort key
and stay invisible to the sidebar. *8 Oct:* **neither is in the July 2025 UKSI.**
Left as they are by decision; set them when a UKSI release includes them.

**A9. Re-key specimens on the current UKSI numbering** — ✅ **DONE** (8 October).
All 2,743 keys recomputed on the July 2025 `sort_code`; 0 of 2,742 changed position
in the tree, 1752 back in place (fault F27). Note `backfill_sort_keys.py
--apply` as it stands rewrites every key it judges "stray", with a test that
matches almost all of them -- don't use it for this.

**A6. Live sidebar refresh — parked.** Small. After editing a specimen the tree
keeps its old counts until restart. `_refresh_sidebar()` exists; it simply isn't
called after a save. Parked by choice: rebuilding collapses the tree and loses
your place, which may annoy more than a periodic restart.

**A7. Normalise `subfamily` storage.** Small, low. Stored as NULL on some rows
and `''` on others for the same species. The sidebar now copes; the data is
still inconsistent and any other query grouping on it would split the same way.


**A8 / A8b status, 12 Oct.** Groundwork built 11 Oct (Round 3, nothing wired in):
`shared/photo_names.py` (file-name parser), `shared/photo_match.py` (UKSI and specimen
matching), `scripts/check_media_library.py` (read only; on the PC: **9,090 files, 45 GB, all
local**, 966 microscope photos match exactly one specimen). Plan and decisions P1–P13:
`docs/drafts/photos_design_update.md`; Wil's answers (Q5, Q13–Q22, Q71) are in `03_Backlog.md`.
A big job of about 3 sessions (Q1). The 7 Oct notes below are kept as background.

**A8. Species photos linked to species and specimens — POTENTIAL, fact-finding
only (7 October).** Nothing decided or built. Library: `OneDrive\Documents\Media`,
44.3 GB (7,391 jpg/jpeg, plus 192 videos). Two trees carry species:
- `Photos\Life\<taxonomic folders>\Genus species\Genus species - Common name N.jpg`
  (field photos; very consistent; the species folder gives the name).
- `Photos\Microscope Photos\<Order>\…\<Family>\…\Genus species D.month.YY.jpg`
  (specimen photos; the date, e.g. `6.vi.21`, could link a photo to the one
  specimen of that species and date, with ambiguous cases going to review).
`All Other Photos` and `Originals` are not species photos. Seen in a 30-file sample:
typos (`Perostichus`), annotations (`(1a)`), mixed `.JPG`/`.jpg`.

Approach discussed: **no renaming and no TVKs in filenames** (TVKs change; see the
6 Oct remap). Instead, a `photos` table in `observatum.db`: path relative to a
photos root in `paths.py`, a content fingerprint so moved or renamed files
re-link, a link to a specimen / observation / TVK, plus type, view, sex, date,
credit and licence. TVKs are kept current by `remap_record_tvks.py`. A scanner
registers files in place; uncertain matches go to a review list (lesson of F25).
Shown in the species account, record detail, specimen dialog and Data Entry info
panel, and later in Examen reports. The folder taxonomy no longer needs keeping
current (e.g. Lymantriidae → Erebidae).

**Open questions before any build:** where the library lives long term; backup
(44 GB, currently OneDrive only, not on the `D:\` copy); stacked vs original
microscope images; whether videos are in scope. **Estimate if built:** ~2 days
(table, scanner, review list, viewer, Add photo button). After A1.

**A8b. Photo intake ("inbox") — POTENTIAL, fact-finding only (7 October).** The
safeguard for A8's naming dependence: names chosen from the UKSI pick list, not
typed. Drop a day's camera files (birding trip, plants) into an Inbox folder; a
screen shows thumbnails with each photo's date (and GPS, if the camera or phone
records it); select one or several, pick the species with the same ranked search
as Data Entry; the tool renames to the house convention, files into the `Life`
tree and writes the photo card. Optional: create the observation record at the
same time (date from the photo; grid ref and VC from GPS, or one site set for the
batch), linking photo to record. Would also clear the unsorted `Originals` /
"Photos To Do" folders over time. Never deletes: originals moved, not removed.
**Estimate if built:** ~2–3 days on top of A8. Sources (7 Oct): the microscope
camera (no location; photos link to specimens) and a Google Pixel 10 Pro (stores
GPS in the photo when location saving is on). Location is a low priority: use it
when present, never require it.

**A10. Specimen ↔ field record links.** ✅ Built 11 Oct (Round 3, tested Round 10): the Field
record box in Edit Specimen (Pick…, Clear, "Checked: no field record exists"), the rules in
`shared/specimen_links.py` and `shared/record_match.py`, `link_specimens_to_observations.py`
(writes a CSV of what it set), `unlink_specimens_from_observations.py`,
`add_specimen_link_check_column.py` (applied on the PC 11 Oct). Linked specimens count
against an observation's quantity. *Open:* whether the ~1,115 certain links were applied
(`03_Backlog.md`, Gathered).

**A11. Specimens with no field record → records.** Big job, about half a day; **recommended
next (Q1)**. Read-only breakdown built 11 Oct (`scripts/report_specimens_without_records.py`):
on the PC 794 new records from 863 specimens, 506 near misses, 33 other people's, 37 already
in the scheme, 2 missing details. Every decision answered 12 Oct (Q23–Q33, in `03_Backlog.md`).

---

## B. Data Entry

**B1. Clicker count-mode.** ✅ Done 9 Oct (held until Data Entry is closed) -- "Count mode (F9)"
button; Space / + / F13 add one to the current row's No., - takes one off (never below 1),
Enter moves on; a large counter shows the count and the species. Keys in QSettings
`DataEntry/countUpKeys` / `countDownKeys`. *Original:* 0.5 day. A keystroke increments Qty; foot-pedal
compatible. For counting many individuals under the microscope without mental
tallying. Design in `26_Data_Entry_Design.md` §3.3.

**B2. Repeat key for sex splits.** ✅ Done 9 Oct (held) -- Ctrl+R copies the row's species, stage
and context into a new row just below, Sex and No. blank, and lands on Sex.

**B3. Reject `?` and `#N/A` as TVKs on load** — ✅ **DONE** (8 October).
`load_workbook_to_staging.py` loads placeholder and Excel-error TVKs (`?`, `#N/A`,
`#REF!`, `-`, `0` ...) as no TVK and reports them; `check_data_entry_batches.py` lists
any still sitting in staging. None found in observations or specimens.

**B4. Species-name paste resolution.** ✅ Done 9 Oct (held) -- a pasted name goes through the
typing rules (`shared/species_rank.resolve_name`): matched when certain, otherwise kept as
text and listed in a message; never guessed. *Original:* 0.5 day. Pasted names store as text with
no TVK and commit anyway, with only a count as warning.

**B6. Common names typed in the species column.** ✅ Done 9 Oct (held) -- a single hit reached
only through part of a common name (or an old name) is no longer filled silently: typing
shows the picker to confirm, a paste leaves it unresolved. Exact matches still fill. *Original:* Small. "Cricket bat spider"
reached staging with no TVK. Same class as B4; UKSI has no common name for many
taxa, so matching on common names is not a fix (it would have found Cricket-Bat
Willow). *8 Oct:* it went on to be **committed** (Bristol, "Cricket bat spid", no
TVK); set by hand to *Mangora acalypha*. B8 would have stopped it.

**B8. Warn before commit** — built 8 October; ✅ **passed Wil's test 12 Oct**.
`commit_service.precommit_issues()` (pure; tested on the 8 Oct Alsager rows: 17 no site,
31 no grid ref, 5 doubles) and a "Check before commit" box in `entry_grid._do_commit`,
default "Go back and fix". Original note: 0.5 day. Commit flags only a missing TVK or a future date. On 8 Oct five
commits carried 59 blank site names, 31 records with no trap or grid ref, a common
name as a species and three doubled entries (fault F28). Show the same counts as
`scripts\check_data_entry_batches.py` in the commit dialog, with the rows, before
writing. Until then, run the script after every commit.

**B5. Row insert below the new-row marker.** Small. Attempted, committed, does
not work. There is a workaround.

**B7. Species account from the grid** — ✅ **DONE** (6 October). Row-number
double-click, right-click → Species account…, or Ctrl+I; a cell double-click
still edits.

**B9. Round 2 items.** ✅ Built 10 Oct, tested 10–12 Oct: a count of 0 is pink and blocks
that row's commit (decision 8); vague dates committed with their date type; conservation
chips in short form (S.41 / SBL / S7 / Protected, full label on hover; L22); "Showing: entry
order" / "sorted by … (view only)" with Back to entry order (L21); the "All my records" map
leaves out records the counting switches exclude.

**B10. Banner on narrower windows (R9-8).** ✅ Built 11 Oct (Round 3): buttons no longer
clipped, Back to entry order on the Showing line, cards narrow (Traps steps aside first,
then This workbook), sorting keeps Copy context; the window is never forced wider than the
screen. Standalone Data Entry opens fitted to the screen (Round 5).

**B11. Compact banner.** Decided 12 Oct (Q54): a toggle that folds the cards to one line,
for short laptop screens (about 7 grid rows at 1280×720). In the small-fixes round.

---

## C. Import wizards

**C1. Re-enrich conservation from live Codex.** ✅ Done 9 Oct, as far as it still applies:
nothing stores conservation per record any more (Examen, Data Entry and the gamification
read Codex live). The one display still reading uksi.db's old 2023 status columns -- the
Insect Collection sidebar's species detail -- now reads Codex (falls back to the old
columns, marked "(UKSI 2023)", only if Codex can't be opened). Report workbooks already
sent out keep the Codex data of their day: re-export any that matter. *Original:* 0.5–1 day. **Raised in value:**
generated workbooks bake in Codex data that now predates five corrections.

**C2. Route wizards through `_get_preferred_common_name()`.** ✅ Done 9 Oct -- the three UKSI
common-name queries in `models/uksi.py` now order preferred first, then capitalised, then shortest. Small. Safe since
the Session 28 fix.

**C3. 175 rows with doubled import notes.** ✅ Script 9 Oct -- `_oneoff/fix_doubled_import_notes_20261009.py`
(drops a " | " segment only when identical to the one before; dry run, backup). Cosmetic. A one-line UPDATE whenever
it matters.

**C4. Merge the three import wizards — WINTER.** 3–5 days, mostly testing against
real imports. Observation, specimen and scheme wizards are near-copies: four
mixins in up to four versions, and the species lookup three times (complexity
54–71, the hardest code in the suite). Every change to species matching -- a UKSI
update, kept taxa, synonyms -- must be made three times. The biggest
maintainability gain available; pays off most at the next UKSI release.
**Stage 1 done 9 Oct:** one species lookup, `shared/species_lookup.py`, called by all
three validation workers; the wizards' differences are kept as named options
(`SPECIMEN`, `OBSERVATION`, `SCHEME`) and their wordings side by side in
`shared/species_lookup_entries.py`. Proved identical on 559 names x 6 import modes
against the real uksi.db, every field of every row (`tests/golden/`,
`test_species_lookup_characterisation.py`; skipped if uksi.db is a different copy --
re-record with `tests\species_lookup_harness.py --write`). **Stage 2 partly done:** the mode card,
progress / summary pages, validation table model and problem export are one copy each
in `Observatum/src/views/dialogs/import_common/`. **Left:** the validation, file and
import mixins (genuinely different, 10–50% alike -- not a mechanical merge); then decide
whether the wizards should agree on the differences listed in `species_lookup_entries.py`
(e.g. the observation wizard never searches UKSI for an unmatched name; specimen lets a
saved alias beat an exact name, observation the reverse; only observation reads "CF." /
"AGG.", only specimen and scheme read "cf" without its dot). Also seen: specimen and scheme
accept a loose top search hit with only a warning ("Ab" -> *Populus alba*).
*Decided 12 Oct (Q84–Q87):* taxonomy overwritten from UKSI on a match; the stored name
becomes the UKSI name (**confirm**: keep the recorded name in a separate field?); a name not
found in a sync is a warning; a re-import changes a narrow field list and never blanks.

**C5. Close spellings and picked names (decision 3, L23, L24).** ✅ Built 10 Oct, tested
12 Oct with `tests/manual_import_files/`: all three wizards accept a close spelling of one
species of the same genus, warned "Close spelling" (`shared/species_close_spelling.py`); a
picked species says what the file had; the specimen wizard shows ✓ ⚠ ✗; observation imports
refuse a count of 0 and accept year / month / range dates with a "vague date" warning.
*Found 12 Oct (small-fixes round, item 3):* the observation wizard's double-click pick keeps
no "File had …" note; "picked by you" vs "resolved by you as"; row numbers start at 1 in the
scheme wizard and 2 in the others.

---

## D. Infrastructure

**D1. Reconfigure the offline server.** Unscoped; documentation lost. The proper
answer to single-machine risk.

**D2. External drive copy** — ✅ **DONE** (26 September; last refreshed 9 October, 0 failed). `D:\BiologicalSoftware_Offsite`,
3.8 GB, verified by `integrity_check` on the copy. **Refresh after any session
that changes data** — re-run the two `robocopy /MIR` lines in `01_Architecture.md`
§7; only changes copy.

**D3. Merge `main` → `stable`.** 15 minutes. Stale since June. *Decided 12 Oct (Q88):* do it
now that Round 8 is committed.

**D4. UKSI rebuild** — ✅ **DONE** (6 October), without the extractor:
`build_uksi_from_release.py` builds `uksi.db` from the NHM *Simplified Copy*
spreadsheet. Procedure in `01_Architecture.md` §5. The Access extractor is no
longer needed.

**D5. Reconstruct `build_pantheon_db.py`.** ✅ Built 9 Oct -- `scripts/build_pantheon_db.py`
reproduces the March `pantheon.db` table for table from the 3.7.4 CSVs (checked row by row in
legacy mode against UKSI 2023), except: the **1,114** species Pantheon gives without a TVK
(797 with only a preferred name) are keyed `NOTVK:<name>` instead of one blank key (F26).
Codex's bridge resolves those via Pantheon's preferred TVK, then name and synonym: 1,092 bridge,
758 UKSI taxa get Pantheon ecology for the first time, 5 gain an SQS, no existing SQS changes
(incumbent rule). All 9 research-only rows of F5 now bridge. `--out` builds to a file;
`--replace` backs up, retires the old file to `_archive`, swaps in. Then rebuild Codex. *Original:* ~1 day. Open since March. Pantheon
has not moved since 2017, so this is insurance rather than need -- **except** that
the current `pantheon.db` stored every species without a TVK under one blank key
(fault F26), losing their ecology. The rebuild must key those on name. Source: the
Pantheon 3.7.4 CSVs in `Observatum\test data\` (part of that folder's ~120 MB --
keep them; not in git, so check they are on the `D:\` copy).

**D6. Sweep for never-executed code paths.** ✅ Swept 8 Oct (`40_Code_Sweep_20261008.md`
§1): 57 static hits → 2 real crashes and one wrong-data export, all three fixed; the
rest dead code or guarded (into I8 / I7b). pyflakes finds no undefined names.

**D7. Rebuild-twice-and-compare check.** ✅ Done 9 Oct -- `scripts/check_codex_repeatable.py`
builds Codex from copies of the live file twice, in separate processes with different hash
seeds, and compares every table: **identical**. Part 2 lists what the next real rebuild will
change versus live (on 9 Oct: the 37 F2 rows). Live codex.db only read. 0.5 day. Build Codex into two files and
diff them; any difference means something is order-dependent. Would have caught
the collapse tiebreak in April, and converts the version-stamping promise from an
assumption into a tested fact.

**D9. Read-only connections for reference databases.** ✅ Done 9 Oct -- `shared/db_open.connect_ro()`;
every app connection to UKSI, Codex (outside Codex Manager's own writes), Pantheon and the VC
lookup now goes through it (26 sites, and `DatabaseManager.uksi_connection`, which also used
to switch uksi.db to WAL on every open). A stray write now fails: "attempt to write a
readonly database". Tests: `tests/test_db_open.py`. *Original note:* Half a day. 97
`sqlite3.connect()` calls across 55 files, 13 read-only. "Only Codex Manager
writes to Codex" is a convention the code does not enforce -- the Examen
manual-entry route (fixed 6 Oct) is where it broke. A shared helper, read-only by
default for UKSI, Codex and Pantheon.

**D10. After a UKSI swap, `restore_dropped_statuses.py` can false-positive.** ✅ Done
8 Oct. The script now maps each old TVK through `build_codex_db._tvk_translator`
(tvk_remap, then name_map — imported, not copied) and lists a species whose current
TVK already holds a status under "MOVED", not under "RESTORE".

**D11. Tidy iRecord's double submissions — LATER (Wil, 9 Oct).** ~1 hr in iRecord.
iRecord holds 635 sightings twice (an app sample sent twice: same external key and
content, two iRecord numbers) -- the root cause of F38 and of 35 of the 283 copies in
F39. The sync now copes, but the doubles still sit in iRecord and in every iRecord
download. List: `scripts/_oneoff/irecord_duplicate_submissions_20261008.csv`; delete the
second number of each pair in iRecord.

**D12. Next iRecord sync — check it (no hurry; Wil may add few records over winter).**
Restart Observatum first, sync, then `scripts/_oneoff/check_irecord_sync_20261009.py`.
Expect no added copies, the 36 key-only records given their iRecord ID, twins 0 apart
from the known pair. Then retire `observatum_pre_sync_20261009.db` (backups folder) to
`_archive`.

**D8. Laptop / second-machine access.** **Decided 12 Oct (Q3): each machine keeps its own
databases; data moves by export and import.** (SQLite over a syncing folder from two
machines risks corruption; one-at-a-time and a server were the other options.)

**D13. Partner's laptop install.** Winter, after photos and the scheme dataset (Q2). The
full suite (Q68). Her own empty database, plus perhaps a separate practice database seeded
with sample data (Q69). Before it: the real-laptop check (dialogs fit 1280×720 since
Round 5, `shared/fit_to_screen.py`), `uk_vice_counties.svg` and `family_common_names.json`
present, the packaging work (`04_Roadmap.md`).

**D14. Backup drive.** The media library (45 GB) joins the `D:\` mirror (Q13), and the
off-site copy should move from the USB pen to one of Wil's larger external drives (to
discuss).

---

## H. Mapping tab

**10 Oct:** selection by several species / genus / family / order / taxon group (chips, each its own
colour, overlap squares split), richness and date-class styles with an on-screen legend, real VC /
recorder / site / source / project filters, old names searched, County view (choosing a VC zooms to it;
multi-part VC outlines fixed -- fault F44), atlas PNG with legend.

**10–12 Oct, built and tested:** Round 2 polish L8–L34 (data sources as tick boxes, date
error clears, draggable divider, outline left out of exports, Full extent / Current view,
one Clear all, VC45 islets kept as a dot ring, tetrads on by default, embargo wording);
Round 3 R9-4 to R9-6 (reversed dates flagged, VC labels, the selected VC outlined, the
Current-view footer counts what is in view) and Open in iRecord in the square list; Round 4
(labels in screen pixels and off squares, VC boundaries switch, districts switch, coast from
sea-facing edges, faster first opening); Round 5 (each border drawn once, draw order, no
tint slivers); Round 8 (Square opacity slider, 0–100 %, remembered; the atlas PNG follows;
batch maps stay solid) and the review's cache-key fix (`06` F47).

**Open (12 Oct):**
- **Map background layers** (big, optional; 3–4 days): OS Open Zoomstack, decisions Q6,
  Q34–Q40 answered (`03_Backlog.md`); design `docs/drafts/map_layers_survey.md`. Districts
  move to current OS Boundary-Line, labelled "Local authority districts" (Q35, Q39).
- **Batch maps screen** (later; Q41–Q50 answered): `scripts/batch_maps.py` is the engine;
  design `docs/drafts/batch_maps_design.md`.
- Rebuild the PC's coarse 2 MB VC outline file (`convert_vc_shapefile.py`; L34).
- The "decade" period option was never implemented (below).

**H1–H6.** ✅ Built 9 Oct. The Mapping tab draws its own map (`shared/maps/grid_map.py`) in place
of the Leaflet/WebEngine one (`map_widget.py` retired): hectad / tetrad / monad squares
(a record only in squares at least as fine as its grid ref; the coarse ones counted on the map),
presence / density / date classes, click a square for its records, A4 300 dpi atlas PNG, species
search by any words of scientific or common name (UKSI common names too). The five Data Entry map
modules moved to `shared/maps/`; **the DataEntry shims land when Wil is not entering data**.
Found and fixed: `observation_stats_service` lettered tetrads rows-first (counts were right, labels
wrong). Not yet seen with the real coastline files (not in the test copy). The "decade" period
option was never implemented.

**H1. Adopt the Data Entry map widgets.** 0.5 day. `raster_map`, `vc_map`,
`species_dist_map`, `gb_basemap`, `_panzoom` are built and proven.

**H2. Move the map modules to `shared/`.** Small, do with H1 — two copies would
drift, which is this codebase's dominant failure mode.

**H3. Polygon grids** (hectad / tetrad / monad). 0.5 day.
`observation_stats_service` already computes all three.

**H4. Grid-square click → filtered records.** 0.5 day. The signal exists.

**H5. Atlas export.** 0.5 day. Render at print resolution.

**H6. Common-name search.** Small.

---

## K. Contributed records

Built 2 October. `contributed_observations` (with contributor, source file, date
received, permission, import batch); `assessment_records` view for Examen;
`scripts/import_contributed.py` (columns by heading, UKSI matching, `--replace`).
Stats and iRecord never see contributed data; Mapping shows it only when chosen as a source. **757 records by 11 Oct** (J. Moore: Birmingham 162, Slade Green 339, Sundon 256). Sundon: a new method "Pitfall" mapped to "Pitfall trap"; one name fixed in the file ("Bobus" → *Bombus pascuorum*); `combined_species_list.py --project` reads committed records for Wil's side.

**K1. Contributed tab in Observatum.** ✅ Built 9 Oct -- read-only tab after Observation Data:
tree contributor › project › batch with counts, free-text filter, sortable table
(`views/contributed/`, `repositories/contributed_repository.py`). ~20–30 min. Read-only browse by
collaborator, project and batch.

**K2. Credit in reports.** ✅ Done with E21 (8 Oct).

---

## M. Recording Scheme

**Built 10–11 Oct:** records read-only everywhere (no Edit / Delete; L15); Dataset / provider
choice in the Filter Wizard, with sub-surveys under their parent (decision 4, D7); the
counting chips and Settings › Species counting share one set of switches; month charts skip
year-only, month-only and range dates (D3); read-only duplicate report (L12); the cleaning
report's lat/long check (D6); 1 January placeholder dates (fault F56).

**M1. Final Recording Scheme dataset.** Each scheme record gets a status: not reviewed / in
the final dataset / set aside, with a reason (Q72, agreed). Review by rules -- the cleaning-
report checks, then whole datasets accepted -- with exceptions by hand (Q73). The aim is a
curated Longhorn dataset, especially historic records and records not in a published atlas.
Raw imports are never edited. Must allow more than one user (Wil's partner co-runs the
scheme). Feeds in: the iRecord/NBN duplicates (Q59, flagged in the small-fixes round), the
remaining 1 January dates (Q57, Q58), dates before 1700 (Q65). **Timing (Q4): the design
questions come straight after the next big job.** About 1 h of questions, then 2 sessions.

**M2. Shared access** to the final dataset (and possibly observation data) with Wil's
partner. Q3 settled the approach: separate databases, data moved by export and import.
After M1 and the laptop install.

**M3. Scheme imports can't be undone in the app.** Records are read-only by design, so a
wrongly imported file needs a script (or cancelling before Import). Consider a "remove this
import batch" script with a dry run (found 12 Oct by the import-test agent).

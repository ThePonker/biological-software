# Faults: closed

## Split out of `06_Faults.md` on 12 October 2026 (it had reached 969 lines).
## Closed faults kept in brief, because knowing what has already gone wrong is how
## the rules in `05` were earned. Newly closed faults go to the top of `06_Faults.md`
## first and move here at the next tidy.

---

## Moved from the open list on 12 October 2026

### F24. Reference databases opened read-write — FIXED 9 Oct
97 connections, 13 read-only. Nothing in the code stopped a view writing to Codex
or UKSI; the Examen manual-entry route (closed below) is where that broke.
**Fixed 9 Oct (backlog D9):** every app connection to UKSI, Codex, Pantheon and the
VC lookup goes through `shared/db_open.connect_ro()`; a stray write fails.

### F25. `uksi.synonyms` maps other species' old names to the wrong taxon — FIXED 9 Oct
**Fixed 9 Oct 2026, 16:28:** `scripts/fix_uksi_synonyms.py` (backlog F14) removed 403 rows
(399 carried-over links contradicting the NAMES sheet, e.g. *Andrena albofasciata* →
*A. ovatula*; 4 *Lamia* rows from `scripts/uksi_synonym_corrections.csv`) and added
*Cerambyx textor* → *Lamia textor*: synonyms 98,415 → 98,013. Backup
`data/_backups/uksi_pre_synonym_fix_20261009_162827.db`; list of changes in
`scripts/_oneoff/uksi_synonym_changes.csv`. `build_uksi_from_release.py` applies the same rules.
*Found 7 October 2026 by Lector testing (Lamia textor).* *Lamia sartor*, *Lamia
sutor*, *Lamia titillator* and *Lamia rosenmulleri* all point at *Lamia textor*
(NBNSYS0000011050). The first two are *Monochamus sartor* / *sutor*, which UKSI holds
as their own taxa (NHMSYS0020704740 / …741). The genuine synonym *Cerambyx textor* is
missing. It looks like old combinations were resolved at genus level rather than
by each name's own recommended TVK. So far this is one example, not an audit.

**Where the rows came from matters.** The live `uksi.db` (since 6 Oct) was built by
`build_uksi_from_release.py`. Its `synonyms` table is the July 2025 NAMES sheet
**plus every synonym carried over from the old extractor-built file**, remapped to
current. So errors in the old table were inherited, and the same name may now
point at two TVKs: the right one from NAMES and the wrong one carried over.

**Who reads it:** the Codex TVK bridge (name route) and so `PantheonRepository` /
Examen ecology; the stale-TVK refresh (`remap_record_tvks.py`, rebuild procedure);
Lector `--synonyms`; the species search (finding a species by an old name). The
NECR217 withdrawal fault below (closed) was the same failure through a different
door.

**Measured 8 October** (`scripts/check_uksi_synonyms.py`, then
`_oneoff/f14_followup_20261008.py`):
- **The *Lamia* rows are the NHM's own data, not inherited.** The July 2025 NAMES
  sheet itself gives *Lamia sartor*, *sutor*, *titillator* and *rosenmulleri* status S
  with recommended taxon *Lamia textor* (NBNSYS0000149843-6). *Cerambyx textor* is not
  in it. The hypothesis above was wrong for the case that found the fault.
- Of 98,415 synonyms rows: 97,113 from NAMES, 936 carried over from 2023 with no
  NAMES evidence, **366 carried rows that NAMES contradicts** (CONFLICT -- mostly
  plants and fungi). 2,193 names map to more than one TVK.
- **Exposure:** no record, specimen or contributed record stored under a flagged
  name. 147 Pantheon-bridge rows matched through a flagged name -- **all through
  NAMES-sheet rows, none through a carried or CONFLICT row.** 121 are an epithet
  heuristic (most look like genuine synonyms: *Acupalpus dorsalis* → *parvulus*);
  **26 are names NAMES maps to more than one species**, where the bridge took one
  (*Aphodius pusillus* → *Agrilinus ater*, not *Esymus pusillus*; *Arion lusitanicus*
  → *A. flagellus*). Those 26 can attach the wrong Pantheon ecology to a species.
  List: `scripts/_oneoff/f14_bridge_exposure.csv`.

**Bridge part FIXED 8 Oct.** The 26 were a symptom: the bridge matched Pantheon taxa
by name and kept the first target of a multi-target synonym. A full comparison found
104 bridge rows disagreeing with NAMES-by-key; `build_codex_db.py` now bridges by key
first (07_Codex.md section 6), and after the rebuild only 37 deliberate exceptions
remain. Analyses are no longer exposed to `uksi.synonyms` errors.
**Still open (search and Lector only):** the 366 CONFLICT carried rows -- the build
fix (carried rows yield to NAMES); *Lamia* and any other NAMES-sheet errors -- a local
exclusions list, and report to the NHM (F11). Backlog F14.

### F26. Pantheon species without a TVK collapsed onto one blank key
**Fixed in code 9 Oct (D5), live once `pantheon.db` and Codex are rebuilt.** *Measured:* 1,114
species, not 150-250 (797 of them give only a preferred name). `build_pantheon_db.py` keys each
`NOTVK:<name>`; the Codex bridge resolves 1,092 of them (758 UKSI taxa gain ecology, 5 an SQS,
no existing SQS moves); F17's nine research-only rows all bridge.

*Found 8 October 2026, chasing F17.* Every Pantheon species that came without a TVK
was stored under the same key, `''`. In `pantheon.db` that one key holds 1,287
conservation-status rows, 2,018 habitat-trait rows, 246 habitat rows, 234 biotope
rows and one SQS (4); `species` keeps a single row for it (*Acalypta platychila*),
so the other names are gone from the database. The same blank key carries 9 of the
72 research-only rows (F17).

**Not harmful, but lossy.** `codex.tvk_bridge` has no entry for `''`, so none of it
reaches an analysis; Glory Park and the other surveys still match. What is lost is
the ecology and score of every species stored that way -- perhaps 150-250 species,
an estimate from the row counts, **not measured**. Pantheon's own `uksi_match` maps
`''` to *Acalypta platycheila*'s TVK; nothing found reads that table.

**Action:** name them from the Pantheon 3.7.4 source CSVs (`Observatum\test data\`)
and fix with backlog D5 (rebuild `build_pantheon_db.py`): key a species without a
TVK on its name, never on an empty string.
*Closed 9 Oct*: D5 rebuild and Codex rebuild done.

### F27. Specimen sort keys: one corrupted, and the numbering may now be mixed
*Found 8 October 2026.* Specimen 1752 (*Phaonia signata*) has a 50-character key --
UKSI's `sort_order` path, not the 8-digit number every other specimen carries.
`remap_record_tvks.py` wrote it on 6 Oct: it guesses the key format from existing
values and takes `sort_code` only if they are **at most 7 digits**; specimen keys
are 8 (order position × 1,000,000 + `sort_code`), so it chose `sort_order`.

Second, possibly wider: `build_uksi_from_release.py` renumbered `sort_code`, and
keys made before 6 Oct used the 2023 numbers. Specimens added since then get the new
numbering. **Measured 8 Oct: all 2,742 numeric keys are on the 2023 numbering**;
none added since 6 Oct, so the tree is consistent today, but the next specimen
added would sort out of place.
**Re-keyed 8 Oct:** all 2,743 keys on the July 2025 numbering, 1752 included; 0 of
2,742 changed tree position (`observatum_pre_rekey_*` in `reference\`).
**`remap_record_tvks.py` fixed 8 Oct:** specimens get the formula (imported); other
tables get a key only where the row already had one and the table's format is
unambiguous. 42 observations still hold a 50-character key from the 6 Oct remap in a
table otherwise without keys -- harmless, left as they are.

### F28. Data Entry commits carried gaps
*Found 8 October 2026* in the morning's five commits (1,136 records): 59 with no site
name, 31 pitfall records with no trap or grid ref, one common name typed as a species
("Cricket bat spid" -- B6), three species entered twice with sex left "Not recorded".
Commit flags only a missing TVK or a future date. All of those fixed the same morning
(`scripts\_oneoff\fix_*_20261008.py`). Of the further doubles the check found, four
Slade Green re-entries were deleted (Run 2); Elmley's ladybirds, *Philanthus*, *Tephritis*
and *Odynerus* confirmed as genuine; three pairs with different quantities (*Kalama*,
*Melanogaster*, *Margarinotus*) left as separate lines.
**Action:** a warning before commit (B8, built 8 Oct -- to test on the next Observatum
restart); `scripts\check_data_entry_batches.py` after commit. Both use one definition
of a double entry, `DataEntry/commit_service.DOUBLE_KEY`.
*12 Oct:* Check before commit (B8) passed Wil's test. Closed.

### F29. Vice-county from a 1 km lookup is wrong in boundary squares
**Fixed 9 Oct 2026.** `data/vc_splits.db` (built by `scripts/build_vc_splits.py` from
`data/maps/vc_brc.shp`) holds the 14,455 1 km squares a VC boundary crosses -- each VC's
share and the outline of its part -- and 42 squares that had no VC (centre in the sea or in
a gap between boundaries). `VCLookupService.assess()` uses it: a 100 m or finer ref gets the
VC it is in (a 100 m square is tested at its centre and corners); a 1 km square on a
boundary is flagged with each VC's share; 2 km tetrads and 10 km squares look at every 1 km
square inside them, not the south-west one. `get_vc_from_grid_ref` and `get_vc_batch` give
the same answer, so Data Entry, the import wizards and the backfill all use it; Data Entry's
info panel shows "On the VC35/VC34 boundary: ... -- check the VC". `vc_lookup.db` is
unchanged. Checked against your records (`_oneoff/vc_disagree_20261009.py`, read-only):
560 records were wholly in another VC -- 553 Machen 2024 GPS points VC35 -> VC41, 7 Bredon
Hill (iRecord 2022) VC37 -> VC33 -- set by `_oneoff/fix_vc_20261009.py` (backup
`pre-vc-fix`); 940 records on a boundary have one of its VCs and were left alone; no
contributed record disagreed. Tests: `tests/test_vc_boundaries.py`.
*Found 8 October 2026 by the I3 grid-ref test.* `vc_lookup.db` gives each 1 km square
one VC, and both Data Entry and the 26 Sep backfill derive VC through it. In a square
that straddles a boundary, a record on the minority side gets the wrong VC. Measured:
125 iRecord records (iRecord computes VC from the precise position) disagree with what
the 1 km lookup would give -- 111 at 6-figure precision. Two cross the England/Wales
line: **Highbury Wood (SO539092) and Cadora Woods (SO539069) are VC34
Gloucestershire; the lookup says VC35 Monmouthshire** -- so a new Data Entry record
there would be assessed under Welsh rules. Stored VCs are not touched (the backfill
only fills blanks). **Action:** backlog I3b -- derive VC by point-in-polygon from the
VC boundaries for references finer than 1 km in boundary squares; flag a square that
straddles the boundary instead of choosing silently.

### F30. Imported records' latitude/longitude ~110 m off
**Fixed 9 Oct 2026.** One converter, `shared/osgb.py` (OS Helmert; within 5 m of all 40 OS
test points, median ~2 m), used by the import wizard, Data Entry's maps and the Mapping
tab. A grid ref's point is the CENTRE of its square (iRecord uses the same: 14,688 of its
records match). `_oneoff/fix_latlong_20261009.py` moved the 3,334 no-shift records (3,332
commercial + 2 iRecord) to the centre with the shift, 107-130 m; backup `pre-latlong-fix`.
**Correction to the text below:** `grid_converter_service` (OSGridConverter) is *not* sound
-- its grid -> lat/long is up to 1.4 km out away from 2 deg W (~200 m in Kent), and the
Mapping tab drew squares with it; now routed through `shared/osgb.py`. The 1,301 records
with a grid ref but no lat/long were filled the same way (9 Oct, same script and backup),
and Data Entry now sets lat/long (centre, WGS84) when it commits a record.
*Found 8 October 2026 by the I3 test.* The import wizard's `_osgb36_to_wgs84` (and
`DataEntry/osgb.lonlat_to_en`, its inverse) omit the OSGB36 → WGS84 datum shift: the
result is OSGB36 latitude/longitude labelled WGS84. Measured against pyproj on all
3,250 distinct grid refs: median 111 m, max 136 m. **3,332 records** imported through
the wizard carry these coordinates; the 20,702 from iRecord are correct. No VC, SQI
or export uses stored lat/long; maps plotted from it are ~110 m out, and Data Entry's
VC boundary overlay is shifted the same way. `grid_converter_service` (the
OSGridConverter library) does apply the shift. **Action:** backlog I3c -- one
converter (import, not copy), then recompute the 3,332 (dry run first).

### F32. Observation import's update path blanks fields it wasn't given
*Found 8 October 2026 by the code sweep (`40_Code_Sweep_20261008.md` §2); not yet
reproduced.* On an iRecord re-sync that finds a changed record, the wizard builds a
whole `Observation` from the fields it has and `ObservationModel.update` writes every
field -- so ~15 it was not given (`internal_notes`, `identification_qualifier`,
`site_name_local`, `individual_count`, `rights_holder`...) go to NULL and
`basis_of_record` resets. With "skip duplicates" off, a personal-upload row matching
species + date + grid ref overwrites the existing record (a second sex or stage row
replaces the first). **Action:** backlog I7b -- measure first, then UPDATE only the
supplied columns.
**Observation import fixed 9 Oct 2026** (`wizard_import_mixin.py`): an iRecord re-sync
writes only the sync fields it was given and never blanks a stored value; in the upload
modes an unskipped duplicate is added, not overwritten. The import also backs up
observatum.db first, and a failed batch is retried row by row with the failures shown
(the observation half of F35). Scheme import (F33) still open.
*Closed 9 Oct* (observation) and with I7b (scheme, `shared/import_core.py`).

### F33. Scheme import drops optional columns batch by batch
*Found 8 October 2026 by the code sweep, §2.* The batch INSERT takes its column list
from the first row's non-empty fields; a column empty in row 1 of a 500-row batch is
dropped for all 500 (comment, verifier, lat/long, irecord_id, nbn_atlas_id).
**Action:** backlog I7b -- fixed column list; measure how many rows lost values.
*Closed 9 Oct* with I7b: fixed column list in `shared/import_core.py`.

### F35. Import duplicate checks fail silently
*Found 8 October 2026 by the code sweep, §3.* The iRecord-sync and NBN duplicate
lookups (unbatched `IN (...)`) are wrapped in `except: pass`. If one fails, the
observation import loses the whole 500-row batch to the `irecord_id` UNIQUE
constraint (printed, not shown), and the scheme import re-imports an NBN file as
duplicates. A BOM-prefixed iRecord CSV loses every `irecord_id` (utf-8 tried before
utf-8-sig). **Action:** backlog I7b -- batch the lookups, fail loudly, try utf-8-sig
first; check read-only for duplicate keys first.
*Closed 9 Oct* with I7b: chunked, loud duplicate checks; BOM-safe reader.

### F37. iRecord sync matched records by a key shared across records
*Found 8 October 2026 measuring F35 on the 09:42 backup.* The iRecord-sync duplicate
check matched an incoming record on its **external key first**, then its iRecord ID.
The external key is not unique: **1,276 keys are shared by 4,303 different records**
(one per app sample). Every record of such a sample matched one existing record, and the
update path then overwrote it -- species and all -- keeping its iRecord ID. **Fixed in
code** (`observation_import_wizard/validation_worker.py`): iRecord ID first; the external
key only when it names exactly one record not tied to a different iRecord ID; lookups
chunked; failures printed, not swallowed. *Checked 8 Oct against a fresh iRecord download
(20,656 records):* **no record was overwritten** -- all 20,045 matched by iRecord ID agree
on date; the only differences are 3 names updated since (e.g. *Aeshna* → *Isoaeschna
isoceles*) and 12 grid refs iRecord shows coarser. Closed.

### F38. 374 personal iRecord records held twice since the 25 March import
*Found 8 October 2026, same measurement.* Each iRecord number held by two records: one
with `irecord_id`, one with it blank but the same number in `irecord_key`, otherwise
identical. Personal counts, maps and the iRecord export see both. **Done 8 Oct:**
`_oneoff/fix_irecord_twins_20261008.py` removed the 373 copies without the iRecord ID
(backup `pre-irecord-twins`; one pair differing in record type left). **The cause is in
iRecord:** it holds 635 pairs of submissions sharing one external key (632 identical,
mostly entered in the same minute -- the app sending a sample twice), and the 25 March
import mirrored them under one iRecord number. The sync now recognises such a second
copy (same external key, species and date) as already held instead of importing it
again. List for tidying iRecord: `_oneoff/irecord_duplicate_submissions_20261008.csv`.

### F40. All 35,104 iRecord rows in the Recording Scheme had lost their iRecord ID
*Found 9 Oct 2026 by `_oneoff/measure_imports_20261009.py`; repaired the same morning.* The
scheme wizard read files as plain UTF-8 before UTF-8-with-BOM, so an iRecord download's
byte-order mark stayed on the first heading and the 'ID' column was never found. Any
re-import would have added all 35,104 again (no ID to match). **Repaired:**
`_oneoff/fix_scheme_data_20261009.py` filled `irecord_id` from `record_key` ('iBRC' + ID,
sometimes with a trailing '!'; format confirmed on all 20,293 observations holding both),
and corrected 13 counts stored as 1 whose text survived ("2", "5 (Exact)"); backup
`pre-scheme-repair`. **Fixed in code (I7b):** `shared/import_core.py` — BOM-safe reader,
fixed column list (F33), chunked loud duplicate checks also on `record_key` (F35), counts
parsed ("c.20" → 20, text kept); scheme updates touch only verification/name/determiner
fields; specimen sort keys from each row's final species; backup first in both wizards.
*Checked and found sound:* comments, verifiers and site names show no batch loss; up to
~2,400 determiners may be missing in the big longhorn/iRecord datasets but the pattern fits
those datasets' natural sparseness (re-importing a source file with "Update duplicates"
fills any real gaps). The 3,679 same-species/date/place groups are separate records in the
source data (own IDs), not import duplicates.

### F39. The 9 Oct iRecord sync added 283 records already held
*Found and repaired 9 October 2026, the first sync after F37.* 248 records from the
25 March import held their iRecord number only in `irecord_key` (`irecord_id` blank), so
the sync -- matching on `irecord_id` -- added them again. 35 more were the second number of
a sighting iRecord holds twice (F38), missed because their external key was shared by more
than one record held. **Repaired:** `_oneoff/fix_sync_doubles_20261009.py` removed the 35
(backup `pre-sync-doubles`), then `fix_irecord_twins_20261008.py` the 248 old copies
(backup `pre-irecord-twins`); 24,962 records, as before the sync. Pre-sync copy kept as
`C:\BiologicalSoftware_Backups\observatum_pre_sync_20261009.db`. **Fixed in code:** the
sync matches a number held in either field and fills in `irecord_id`; a twice-held
sighting is recognised when the key is shared and is left alone. 36 records still hold
their number only in `irecord_key` -- the next sync fills those in. Everything else in
the sync was sound: nothing blanked, none of our fields touched, 48 verifications in.

### F4. `build_pantheon_db.py` missing
Same event. Pantheon has not been updated since 2017 v3.7.4, so this is insurance
rather than need. **Action:** backlog D5.
*Closed 9 Oct* (D5): `scripts/build_pantheon_db.py` rebuilt.

### F12. `drawer_unit` column name
The UI reads "Drawer Number"; the column is `drawer_unit`. Rename touches four
files plus reset scripts. Column empty, no data risk. **Action:** backlog A4.
*Closed 9 Oct* (A4): renamed `drawer_number`.

### F17. Research-only species that do not reach the bridge
Pantheon lists 72 rows as S41 research only. *Measured 8 October:* **63 carry a
TVK and all 63 are bridged**; they reach 62 current TVKs only because *Euxoa crypta*
and *E. tritici* merge into one -- correct, not a gap. The other **9 rows have no TVK
at all** in `pantheon.db` (F26), so they cannot be bridged, and those species are
treated as ordinary S41 -- able to confer key status. (Previously recorded as "62
of 72, 10 unbridged".) **Action:** backlog F5, which depends on D5.
*Closed 9 Oct* by D5: all nine rows bridge.

### F14. The Overview gives a site-importance verdict with no source
`overview_tab.py` ends its summary sentence with *"This indicates a site of
national importance"* at SQI ≥200, *regional* at ≥150, *some conservation value*
at ≥125. **No published source found for those bands.** They are not Pantheon's;
Fowles's thresholds are 500 and 590 and for the saproxylic index. The surveyed
reports cite percentages and name their convention because thresholds are
contested — Alexander thinks even Fowles's are too high.

The same class as the invented Section 41: plausible, confident, unsourced, in
prose written to be lifted into a report. Left unchanged pending a decision.

*2 October:* every SQI has since fallen 3–66 points (see the closed entries
below), so the bands now attach to different sites than when they were written —
another reason they cannot stand unsourced.
*8 October:* Pantheon's own page says benchmarks have not been produced; no source
for 200/150/125 exists anywhere searched (`39_Research_Notes.md` §1). Pantheon's
small-sample wording is "15 **or less**" -- the code treats exactly 15 as reliable.
**Closed 8 October:** the sentence is removed (backlog E16). The SQI colours on the
project and assemblage tables still use 150 / 125 for green / amber -- the same
unsourced bands, unlabelled; worth a decision of their own.

---

## Closed before 12 October

### F44. Multi-part vice-counties drawn from one ring -- FIXED 10 Oct
`convert_vc_shapefile.py` wrote each multi-part VC as one polygon whose extra
parts became "holes", and the loader kept only the first ring: 40 of 112 VCs
(every one with islands or detached parts) drew partly or wrongly -- VC1 West
Cornwall showed as a triangle in the new County view. The loader now rebuilds the
parts and the converter writes MultiPolygons. `scripts/check_vc_outlines.py`
compares every VC's drawn area and extent with the shapefile: 0 of 112 wrong on the
test copy; on the PC 1 (VC45: The Smalls stored as a 2-3 point ring in the older
2 MB geojson and dropped -- rebuild that file, backlog L34).

### Filter boxes reloaded on every keystroke -- FIXED 10 Oct
Typing in a filter bar reloaded the table per character, Clear All and saved
filters reloaded several times, and the scheme loader copied every row to an
unused signal. Now: 350 ms debounce, one reload, no copy; county firsts 2.07 s ->
0.019 s with `idx_scheme_tvk_vc_date` (`scripts/add_filter_indexes.py`).

### Toolbar "Clear Filters" did not clear on Recording Scheme or Collection -- FIXED 10 Oct
On the Scheme it cleared only the bar (the wizard stayed on); on the Collection it
did nothing. Both now clear bar + wizard + saved choice in one reload; the toolbar
button is hidden and the bar's Clear All (beside Species) is the one button.

### F36. Commercial Data Entry jobs could be committed with no project
*Found 8 October 2026 (Commercial Reports' new drill-in).* The New job dialog checked
only the name, so Commercial jobs were created with Project and Client blank and 1,129
records (Alsager, Bristol, Elmley, Slade Green, Sundon) committed as "(no project)".
Now: a Commercial job needs a Project (dialog), the commit refuses without one (grid,
and `commit_job` as a backstop), and Jobs > **Edit details** sets it on an existing
job. Repair: `_oneoff/fix_no_project_20261008.py` -- project = site; client Richard
Wilson (Elmley), Andy Jukes (the rest), by Wil's decision.

### F31. Data Entry commits dropped the Comment column
*Found and fixed 8 October 2026 (code sweep).* The grid has a Comment column and the
workbook loader fills it, but `build_kwargs_from_row` never passed it on, and the
staging row is deleted on commit -- so every comment was lost from the day Data
Entry went live. Now carried through (`commit_service`, `write_service`), with a
test. Comments already committed can come back only from source sheets.

### Recording Scheme: Reset crashed; Export Selected exported the wrong rows when sorted
*Fixed 8 October 2026 (code sweep).* Filter Wizard → Reset called `self.filters`
(copied from the collection tab; the bar is `filter_bar`). Export Selected mapped
through a `proxy_model` that does not exist -- a `hasattr` guard hid it -- so with
the table sorted it exported the rows at the same *positions* in the unsorted data.
Also fixed: the Data Entry info panel crashed on build when the distribution map
could not load.

### Appendix export reported one SQI (was F21)
*Fixed 8 October 2026 -- backlog E17.*

### iRecord export stopped silently when every record was embargoed
*Fixed 8 October 2026.* Choosing iRecord format for 279 embargoed Alsager records
said "0 records will be exported" and then did nothing -- no Save dialog, no file,
no reason. It read as a missing dialog. It now says that all are excluded and that
a client export needs "All columns". The suggested filename is now
`<project or site>_<date>.csv`, not always `observations_export.csv`, so one job's
export cannot silently replace another's.

### Examen's manual-entry dialog could empty Codex
*Fixed 6 October 2026. Found by static analysis, never triggered.* "+ Add Manual
Entry" in the Species Database tab ran `DELETE FROM manual_entries`, then
reloaded from `codex_manual_entries.json` -- the pre-review-load design. Since
September the table holds every review status, withdrawal and clearance (10,079),
none of them in that file. Button hidden, routine disabled; proven against a
stand-in table of 10,079 rows. See `05_Rules.md` (a `DELETE` with no `WHERE`).

### Observation filter fallbacks used the wrong list
*Fixed 6 October 2026.* Both client-side fallbacks -- no repository, and after a
repository error -- passed `observations` instead of `filtered`: a `NameError`, or
the wrong list shown. pyflakes flagged one; the patch's match count found the
second.

### `vc_lookup_service` loaded only on Python 3.14
*Fixed 6 October 2026.* `List` in an annotation, never imported. 3.14 defers
annotations; 3.13 and earlier would fail to import the module, and vice-county
lookup with it -- on a colleague's machine.

### Data Entry column-header menu raised `NameError`
*Fixed 6 October 2026.* Three lines of the row menu, pasted into `_header_menu`,
referred to `real`, undefined there. Right-clicking a column header did nothing.

### The UKSI build's first versions
*Fixed 6 October 2026, before the switch.* A review of `build_uksi_from_release.py`
found: same-name matching across kingdoms (*Morus*, bird → plant); parents
pointing at redundant taxa; English names not carried over; kept taxa colliding
on `sort_code`; then "species pro parte" refused as a species rank, which kept
*Sepedophilus testaceus* off its current TVK. All fixed; parent links outside the
file 0. A sixth "fix" -- for duplicate rows -- addressed a cause that measured
absent (0 duplicates).

### `uksi_extractor.py` missing -- the UKSI could not be rebuilt
*Closed 6 October 2026.* Lost in the March 2026 restructure. Superseded rather than
rewritten: `build_uksi_from_release.py` builds `uksi.db` from the NHM *Simplified
Copy* spreadsheet, whose NAMES sheet carries the Nameserver mapping the Access
extraction never had. December 2023 → July 2025. Was F3.

### Withdrawals ignored dates
*Caught 5 October 2026 at the dry run.* A 2005 exclusion list (Empidoidea) would
have cleared 2018 Dolichopodidae statuses -- 38 species, *Chrysotus collini* NR/VU
among them. `withdraw_statuses.py` now clears only statuses older than the
excluding review; every earlier batch re-checked and found sound.

### JNCC 2026 dropped statuses without a newer review
*Fixed 5 October 2026.* 52 statuses on 43 species -- spiders, *Ectobius*,
*Eloeophila* and others -- lost or moved to TVKs newer than the UKSI then held.
Restored as manual entries (`restore_dropped_statuses.py`).

### The macro-moth Red List had never reached Codex
*Fixed 5 October 2026.* Fox et al. 2019 is not in JNCC's spreadsheet; 766 Red List
and rarity statuses loaded from its Appendix 1, totals checked against its own
Table 1. Moths are now Key on decline as well as rarity, as for every group.

### Withdrawals hit the wrong species through synonyms
*Fixed 5 October 2026.* NECR217's 'Taxonomy' exclusions (*Chlorops citrinellus*…)
resolved through UKSI synonyms to valid current species the same review had
assessed (*Chlorops rufinus*…), and cleared their new NS. Restored by
`restore_wrong_withdrawals.py`; withdrawals now require an exact name.

### Legacy statuses with a detail escaped every check
*Fixed 5 October 2026.* 63 old statuses (RDBK / Insufficiently Known, 1994 IUCN)
stored with a status_detail survived review loads and clearances, which looked
only at empty-detail rows; 19 fly species were Rare Key on them. Cleared with the
detail recorded; verified gone. Survival confirmed: 0 to clear after the 5 October
JNCC rebuild (the 12 found on 6 October were new, created by TVK translation).

### Old statuses shown instead of the newest review's
*Fixed 4 October 2026.* Codex's statuses mostly arrive via JNCC's spreadsheet,
which does not enforce "newest review wins". Four forms, all fixed and proven
to survive a rebuild:
- **Old beside new** (71 species): a 1987–94 Nb / Notable / RDB kept beside a
  later review's status. 9 changed key standing -- *Anaglyptus mysticus* was Key
  at Kent Deadwood on a 1992 Nb the 2019 longhorn review reassessed as LC.
  `clear_stale_legacy.py`.
- **Excluded by judgement** (NECR234, 5 species incl. *Phaonia siebecki*, Key at
  Birmingham on a withdrawn 1991 Notable). `withdraw_statuses.py`.
- **Provisional reviews only part-imported by JNCC**: NECR234's 300 statuses
  (158 pNS, 77 pNT…) never reached Codex; 1991 Notables stood in their place.
  Loaded from the data sheets with `load_review.py --add-statuses`.
- **Old names** (7): the newer review assessed the current name; the old name
  kept its status (*Hercostomus nigrocoerulea*, *Phaonia lugubris*…).
  `withdraw_statuses.py`, `check_old_names.py --apply`.

Birmingham 7 → 6 key species (SQI 118 → 116); Kent Deadwood 78 → 77.
Checks: `check_legacy_conflicts.py`, `check_newest_review.py`, `check_old_names.py`.

### NS-excludes discarded -- 272 species lost their Nationally Scarce status
*Fixed 4 October 2026.* JNCC's "NS-excludes"/"NR-excludes" (Nationally Scarce/Rare
excluding Red-Listed taxa) were dropped as duplicates of "-includes". For 272
species -- Empidoidea 2005, water beetles 2010, **hoverflies 2014** -- they were the
only rarity code. Routed (ranked below -includes). Unrouted 1,519 → 121; Glory
Park still 8 key (it matches its report).

### Two backups in one second overwrote each other
*Fixed 4 October 2026.* `backup()` named files to the second; sawfly Phases 2 and 3
shared a name. Microseconds added; refuses to overwrite.

### Review import left files locked; resume path untested
*Fixed 4 October 2026.* openpyxl read-only workbooks were never closed, so
removing the originals from Downloads failed after extraction. Now closed; a
locked original no longer stops a verified copy.

### A dead-code removal crashed on a ✓
*Fixed 4 October 2026.* The import check ran Python with captured output; a
module printing ✓ at import crashed the cp1252 pipe -- and a failure after
deletion was not restored. UTF-8 forced; any failure after the first change
restores from git.

### F42. Stats service lettered tetrads rows-first
*Found 9 Oct during H3.* `observation_stats_service._extract_grid_squares` numbered tetrad
letters across rows (A–E along the bottom row) where DINTY runs A–E up the first column, and
its "skip O" step was off by one. Tetrad **counts** were right; tetrad **labels** disagreed with
`shared/osgb.py`. **Fixed 9 Oct**, test in `tests/test_osgb.py`.

### F43. "Melanotus" records on the fungus genus TVK
*Found 9 Oct by the E8b taxonomic summary.* 10 Kent Deadwood records named "Melanotus" carry
BMSSYS0000020490, the Agaricales genus, so they appear as an "Agaricales" group in Examen.
`saproxylic_scores.csv` gives the beetle genus the same TVK (harmless there: genus entries match
by name). **Script ready (11 Oct)**: `scripts/_oneoff/fix_melanotus_tvk_20261011.py` (dry run,
then `--apply`) moves them to NHMSYS0000079906 and re-derives kingdom / order / family / taxon
group (also on iRecord rows -- none on the 10 Oct copy). Closed once Wil has run it.

### F44-F46. Suite review, 9 Oct 2026
The full review is in the project (`claude/32_Suite_Review_20261009.md`), finding IDs OBS/SRCH/MAP/
DE/EXA/CDX/IMP/CUR/MUN/ATR/LEC/SPD/INF. Tier 1 fixed and tested the same night (see 03_Backlog
"Next"). Two were regressions from that day's own work and are fixed: IMP-2 (scheme import refused
every row -- I7b) and INF1/EXA6 (Pantheon Only mode lost SQS through NOTVK twins -- D5). Moving
records from an s.l. TVK to the species (Nomada panzeri) briefly dropped Pantheon's SQS from two
surveys until the species-over-s.l. fallback was extended to Pantheon data and stored SQS.

Older closed faults (the 2 October SQI faults and everything before): `06c_Faults_Closed_Earlier.md`.

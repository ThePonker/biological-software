# Photos (A8 / A8b): design update after the groundwork code

## 13 October 2026: Wil's aims, the microscope workflow, and the library measured

**Aim.** A microscope photo may be any of: evidence attached to a specimen or record, a
picture for a report or species account, and a reference set for identification.

**Workflow Wil wants (microscope first).**
- Camera **TrueChrome 4K Pro**, captured with its software **Mosaic** (Q70). Mosaic's save
  folder can be changed but seemed to revert when Mosaic closed, so the suite must remember
  the folder itself and say plainly when it is empty or missing.
- While entering data **in Data Entry**, with the specimen in front of him, attach the
  capture to that row. The file is **moved** (not copied; nothing left in the Mosaic folder)
  into the species folder and named by his convention.
- Clicking a record anywhere: **all photos of that species**, with the one(s) for this record
  / specimen labelled.
- Focus stacking: not needed for the first stage. Today: photos saved to the desktop, then a
  free stacking program (name not known; not on this PC). Mosaic does not stack (Q71 open).

**Today's files.** Spiders: `Photos\Life\Dead Spiders\<Genus species>\`, names such as
`Arctosa leopardus male`, `Ozyptila simplex (2)`, `Xysticus acerbus 2`, recently with a date
so a photo can be tied to a record. Beetles (a few years ago): `Photos\Microscope Photos\
<Order>\...\<Family>\` with `Genus species D.month.YY` names.

**Library check, run on the PC 13 Oct** (`scripts/check_media_library.py`, read only; rows in
`scripts\_oneoff\media_library_check_20261013.csv`):

| | |
|---|---|
| Library | 9,095 files, 45.27 GB; **all local, none cloud-only**; 8,916 "always keep on this device" (P1 met) |
| Life | 2,682 images; 2,638 (98.4 %) follow the Life convention; 16 named from the folder only |
| Microscope Photos | 1,428 images; 1,310 (91.7 %) follow the microscope convention; 1,307 with a date |
| Elsewhere | 3,441 images (All Other Photos, Originals); 41 with a species name |
| UKSI (5,060 named files, 1,497 names) | exact 4,586; exact review 7; synonym 283; fuzzy 140; none 44 |
| Microscope photo ↔ specimen (1,316 with species and date) | **exactly one specimen 966**; several 180; none 170 |
| Folder vs file name disagree | 17 (old names and slips, e.g. *Pyronia tithonis*, "Pardose monticola" folder) |
| Not photos | 908 `.db` + 343 `.ini` (Windows thumbnail caches), 192 videos (17.4 GB in Videos) |

**Issues for the design (noted 13 Oct, not decided):**
1. A Data Entry row has no record id until it is committed: the photo link must be held with
   the staging row and carried through the commit.
2. The name reader must learn `male` / `female` (today "male" would be read as an infraspecific
   name) and both numbering styles, `(2)` and ` 2`; the 5 unread Dead Spiders names are these.
3. Spider photo names mostly carry no date, so they link to the species; a record link needs a
   date or a pick by hand.
4. A move within OneDrive is a rename (atomic); a move across drives is copy, check, then
   remove the original -- the build must verify before the original goes.
5. New tables (photos and links) are a schema change: migration script with dry run and backup,
   `reset_database.py` audited, independent review.
6. Does a record hold sex? If Data Entry has the field, the photo name can take it from there.

**Suggested first stage** (to confirm): index the existing photos (link by name; the 966
single-specimen matches confirmed with the one "Confirm all" button, Q15); "Add photo" in Data
Entry from the Mosaic folder (move and rename); a photo strip on Record Detail, Species lookup
and Species Info, this record's photos first. Later: reports and species accounts, the phone
Inbox, stacking.

## 13 October (night): B1 done, the lean plan, intake and re-dets

**B1 done (23:44).** 1,469 specimen photos (Microscope Photos, Dead Spiders, Dead Craneflies)
moved into `Life\...\<species>\Specimen\` by `scripts\move_photos.py` from the move list
(`build_photo_moves.py`: the plan's 1,165 planned rows plus Wil's review sheet). 191 renamed:
spelling and current UKSI names, dates to the standard, sex in lower case. 15 to
`Photos\_Photo review\` (left blank in the sheet), 5 Labs copies to
`Photos\_duplicates_20261013\`. Nothing deleted; emptied folders left. Backup and log: see
`03` Reminders. Library check afterwards: 9,095 files (unchanged); Life 4,090 images; UKSI exact
4,756 (was 4,586), fuzzy 46 (was 140); microscope photos with exactly one matching specimen 987.

**The naming standard** (`shared/photo_names.py`: `format_photo_date`, `standard_photo_stem`;
everything that names a photo uses them): `<UKSI name> [male|female] <D.roman.YY> [n]`, e.g.
`Erigone dentipalpis male 30.ix.26`. Older forms are still read: `18.11.16`, `29092026`,
`14.VII.2023`. A date with no year is never guessed. Subgenus brackets are left out of folder and
file names. Field photos keep `Genus species - Common name N`.

**The lean plan (agreed; replaces the index-and-review design).** Wil's aims are three: attach a
photo while entering the record; click a record and see the species' photos with this
specimen's marked; reports later. So: no index of the 9,000 files (the species folder is the
index); one small record ↔ photo link table; the Photos button reads the folder; a re-det moves
the record's photos when it happens. Dropped from the earlier design: match states,
fingerprints, the review workflow, a housekeeping screen, the setting. Left until wanted: main
photo, determination history, reports, stacking. Plan and estimates: `03_Backlog.md`.

**Photo intake (B4): one screen for the Mosaic folder and a phone Inbox.** Phone files have
camera names, so Wil types the species once for a selection; the date and GPS come from the
photo (6-figure grid ref). Each photo: species only (Life folder, field naming) / attach to a
record (suggested by species, date and place) / make a record (Data Entry row) / leave. Mosaic
captures go to the `Specimen` subfolder with the specimen naming. Moved, never copied; logged;
undo.

**Re-determinations.** The sync takes species from iRecord: a re-det made only in Observatum is
put back by the next sync. Agreed: A2's conflict check (one side changed → it wins; both → Wil
chooses), the "in iRecord, change it there too" note on edit, and photos following a re-det.

## 13 October (late): decisions, the iRecord round trip, and the staged plan

**Decided in discussion (no code yet):**
- **Where photos live:** Microscope Photos, Dead Spiders and dead craneflies are consolidated
  into the Life tree, `Life\<order>\<family>\<species>\`, with specimen photos in a
  **`Specimen`** subfolder. **Hemiptera's extra level is the suborder.**
- **Folder rule for a new photo:** reuse the species' existing folder; else the per-group rule
  from UKSI; else `Life\_New species\<Genus species>\`.
- **File name:** `<UKSI name> <sex> <D.month.YY> <n>`. Grid ref **not** in the name (an
  optional setting, off by default).
- **Viewing:** a **Photos (n)** button on a record or specimen opens a separate window (all
  photos of the species, this record's marked); one photo can be the **main photo**, shown
  small in the record dialog. Field and microscope photos both.
- **Bench photos are moved, not copied**, and attached **in Data Entry**.
- **Uncertainty kept, not hidden:** each link is proposed / confirmed / rejected with how it was
  matched; dates trusted name > camera (EXIF) > file date; a fingerprint re-finds a moved
  file; a missing file is marked missing, never removed.

**Consolidation figures** (from `media_library_check_20261013.csv`): 1,469 source photos;
1,174 match UKSI exactly (594 species: 143 already have a Life folder, holding 341 of them;
833 photos need new folders; no name clashes); about 150 to review; about 145 cannot be placed.

**Why the iRecord sync comes first.** A photo link hangs on a record, so the record needs one
identity from Data Entry through iRecord and back. Today personal jobs go to iRecord as a CSV
with no key and are paired on their return by species, date, grid ref and recorder; commercial
records are created in Observatum, but none has yet made the round trip by its key.
**Test, 13 Oct 22:29:** iRecord kept the External keys Wil supplied
(`OBS-WJH-IRTEST-20261013-0001…0046`, 46 Farthinghoe records, record 57539766 checked). These
keys cannot collide with the key generator (it counts only `OBS-WJH-YYYYMMDD-…`). The new
iRecord importer failed ("load_values() on false"); the spreadsheet uploader worked.

**Staged plan** (about 4 sessions; table in `03_Backlog.md`): A1 test the sync's matching with
the returned IRTEST records (~30 min) → A2 sync guard: hold, don't add, backup first (~0.5) → A3
personal jobs create the record and key at commit, like commercial (~0.5) → B1 consolidate
into Life with dry run, log and reverse (~0.5) → B2 photo index and review list (~1) → B3
Photos button, window and main photo (~0.5) → B4 attach in Data Entry, move and rename (~0.75).

> **Decisions answered 12 Oct 2026** (Q5, Q13–Q22, Q71 in project note
> `claude/45_Open_Questions_20261012.md`; the draft below is unchanged). P1 settled 11 Oct (all
> 9,090 files, 45 GB, local). **P2:** yes, Media into the `D:\` mirror, and discuss moving the
> backup from the USB pen to a larger external drive (Q13). **P3, P4:** no preference given, so
> the recommendation stands (Q14) -- **but Q71 widens P3: microscope captures go to the Inbox,
> not only stacked images**; look into focus stacking or driving Wil's free stacking software.
> **P5:** no preference given: no auto-confirm, one "Confirm all" button (Q15). **P6**
> `Life\_New species\<Genus species>\` (Q16). **P7** 6-figure default, 8 optional; a record
> only on "Make a new record" (Q17). **P8** "Wil Heeney / Flauna Ecology", All rights reserved,
> per-photo change (Q18). **P9** yes (Q19). **P10–P13** accept all four (Q20). Inbox: the four
> choices are enough (Q21); phone photos by OneDrive camera upload into the Inbox, Google
> Photos for viewing (Q5); **a photo edited in Google Photos replaces the original** (Q22, not
> the recommendation).

*Draft, 11 October 2026. Background work only. Nothing is wired into any app, no table was
added and no database was written. Earlier material: `docs/41_Groundwork_Notes_20261009.md`
Part A (photos) and the 9 Oct discussion note (photo workflow).*

## 1. What was built

| File | What it does |
|---|---|
| `shared/photo_names.py` | Reads a photo's path and returns a `PhotoName` with the genus, epithet, infra rank and name, the name to look up, the common name, number, bracket notes, date and warnings. It handles both conventions: `Genus species - Common name N` (Life) and `Genus species D.month.YY [N]` (microscope). Roman months i–xii in either case are read, and a 2-digit year becomes 20YY. A bad month, an impossible day or a year before 1900 is a warning, and no date is kept. A future date is kept, with a warning. A month written in digits is accepted with a warning. The folder acts as a second witness. In `Life`, the species folder is compared with the file name. A camera name such as `IMG_…` inside a species folder takes the folder's name and is marked `name_source='folder'`. In `Microscope Photos`, the Order and Family folders are recorded. It has no Qt and no database, and it never opens the file. |
| `shared/photo_match.py` | `PhotoMatcher` matches the names in one batch and caches the results. (1) Exact names and (2) synonyms come from `shared/species_lookup.lookup_names`, the import wizards' rule, unchanged. A synonym is always marked "review" (F25). A name that UKSI holds more than once is settled by the photo's common name when exactly one candidate has it. (3) Fuzzy matching uses difflib with a cutoff of 0.85 on the rest of the name within the genus. When the genus is unknown, the close genera are found first with `fuzzy_words.FuzzyVocab`, then difflib's cutoff is applied. These matches are always marked "review". The name table is `species_search`'s in-memory index, so nothing is loaded twice. A subspecies that UKSI does not hold falls back to its species, marked "review". `folder_warnings()` does the soft Order/Family check. `SpecimenIndex` finds the specimens with the same TVK, or the same species name, and the same `date_collected`. |
| `scripts/check_media_library.py` | **Read-only** library check (build step 1 of the groundwork). It walks the library with `os.scandir` only and never opens a file. It tells local from cloud-only using the attribute bits. It reports counts by folder, kind and extension, the parse hit rate per convention, the UKSI exact/synonym/fuzzy/none counts with the top unmatched names, folder disagreements, and microscope photos with one, several or no date-matched specimen. It writes one CSV row per file and ends with "READ ONLY. Nothing has been changed. No cloud-only file was opened." |
| `tests/test_photo_names.py`, `tests/test_photo_match.py` | 24 tests. They cover the 7 names from the brief, date warnings and the folder witness. They check matching against the `uksi.db` copy, specimen candidates on an in-memory DB, and the scanner on a temp tree of tiny Pillow JPEGs, with `open`, `io.open` and `PIL.Image.open` patched to raise during the scan. The cloud-only count is tested by faking the attribute bits. |

**Measured** (sandbox, which is slower than Wil's PC):
- Parsing 7,400 paths takes 0.8 s.
- Building the UKSI index takes 7–8 s here. `species_search` documents about 1 s on the PC.
- Matching 2,000 real UKSI species names takes 2.5 s. Of those, 300 had one letter deleted at random. 281 of the 300 were matched to the right species, 18 to none and 1 to a synonym. **None was matched to a wrong species.**
- Before the FuzzyVocab pre-filter, the unknown-genus path took about 0.3 s per name and 15 s for the batch.

**Not measured:** the real library. The script has not been run on Wil's PC, so every library figure is still to come (see section 5).

## 2. How this changes the earlier plan

- **Build step 1 of the checklist (the read-only count script) is done**, apart from running it on the PC.
- **The scanner shrinks.** `photo_scan.py` (groundwork A6) now only has to do the walk, the fingerprint, EXIF and the re-link. Parsing and matching are done and tested. Estimate: 0.75 → about 0.5 day.
- **Matching reuses what exists.** Exact and synonym matching is `lookup_names`, so photos and imports follow one rule (qualifiers, species over broad group). The name table is the shared search index. `species_rank.rank_matches` was not needed, because the photo matcher never ranks free text.
- **New facts for the schema** (groundwork A5), with no change made:
  - Add `name_source` (`file` / `folder`) and `parse_warnings`, or put them in `parse_note`.
  - `match_method` needs `'folder'` as a value, for camera-named files in species folders.
  - The match status labels used are `exact`, `exact, review`, `synonym, review`, `fuzzy, review` and `none`. These map onto `link_status='proposed'` plus `confidence`.
- **UKSI writes subspecies without "ssp."**, e.g. `Zygaena filipendulae stephensi`. The parser drops `ssp.`, `subsp.`, `var.` and `f.` before the lookup but keeps them in `written_name`.
- **"Genus sp" links to the genus TVK.** That is an exact match at rank Genus. A date match against specimens is still attempted, but specimens are stored at species level, so expect "none" for these.
- **Specimen dates are clean.** All 2,744 dated specimens in the 10 Oct copy are `YYYY-MM-DD`, with 1 blank, so an exact date comparison works. The specimen index matches on the TVK **or** the species name, in case a specimen still carries an older TVK.

## 3. Decisions P1–P9 (recommended option first)

| # | Question | Recommended | Why (one line) |
|---|---|---|---|
| P1 | Where does the library live; is it local? | **Keep it in `OneDrive\Documents\Media`. After running the check, set `Photos\Life` and `Photos\Microscope Photos` to "Always keep on this device" if the disk allows.** | Linking, thumbnails and fingerprints need local bytes, and these two trees are the ones that get linked. |
| P2 | Add Media to the `D:\` mirror? | **Yes, as a third robocopy line, run after P1's pinning.** | OneDrive is sync, not backup. A robocopy of cloud-only files would hydrate them all anyway. |
| P3 | Stacks: outputs only, or source frames too? | **Stacked outputs only.** Wil confirmed this on 9 Oct, so it only needs writing down. | The frames are near-duplicates and add nothing to a species account. |
| P4 | Videos (192) in scope? | **No. Count them only.** The check script reports them under "videos". | Wil said no videos (9 Oct). They can be registered later as `media_type='video'`. |
| P5 | Auto-confirm exact name + one date-matched specimen? | **No auto-confirm on the first run. Offer one "Confirm all exact + single specimen" button in the review list instead.** | Wil sees the list once, and the click is cheap. Afterwards the same rule could auto-confirm. |
| P6 | Inbox destination when a species has no folder | **`Life\_New species\<Genus species>\`** | Visible and easy to file by hand later, and the links survive the move by fingerprint. |
| P7 | Grid-ref precision from phone GPS; make observations? | **6-figure (100 m) by default, with 8-figure as an option. Make an observation only when Wil picks choice 3 ("Make a new record").** | Phone GPS is 5–10 m but often worse under trees, and 6 figures matches how sites are usually recorded. Records stay deliberate. |
| P8 | Default credit / licence | **"Wil Heeney / Flauna Ecology", "All rights reserved". Override per photo.** | This is the safe default for client reports. A CC licence can be chosen photo by photo. |
| P9 | Photos with no record: TVK-only links? | **Yes, by design.** | Most field photos have no record (9 Oct). The species account still shows them. |

**New questions found while building:**
- **P10.** A camera-named file (`IMG_…`) inside a species folder: link it by the folder's name, marked "review"? **Recommended: yes**, as `match_method='folder'`. The check script reports how many there are ("named from the folder only").
- **P11.** A subspecies that UKSI does not hold: link it to the species, marked "review"? **Recommended: yes**, with the note shown in the review list.
- **P12.** A file in a species folder whose name gives a different species: trust the file or the folder? **Recommended: neither. It goes to review with both names shown.** The check script lists these.
- **P13.** Common names: should a mismatch between the file's common name and UKSI's be flagged? It is not done now. **Recommended: no.** Common names vary ("7-spot" vs "Seven-spot"), and the scientific name decides.

## 4. The first full build (after Wil runs the check and answers P1–P13)

| # | Step | Est. |
|---|---|---|
| 1 | `paths.py`: add `PHOTOS_ROOT`, `PHOTO_INBOX` and `THUMB_CACHE_DIR` (append only). `scripts/add_photo_tables.py` (dry run, `conn.backup()` first, idempotent). Add the same CREATE strings to `reset_database.py`. Add `photo_links` to `remap_record_tvks.py`'s table tuple. | 0.25 day |
| 2 | `shared/photo_scan.py`: the walk (reusing `scan_tree`), `fp_fast` for local files only, EXIF with Pillow, re-link by `(file_size, fp_fast)`, `missing` status, and proposals from `photo_match`. First run is a dry run. Tests for re-link and the cloud-only skip. | 0.5 day |
| 3 | Thumbnail cache (outside OneDrive), the `PhotoStrip` widget and a simple viewer | 0.5 day |
| 4 | Review dialog: Proposed / Unmatched / Missing, Confirm / Choose species / Choose specimen / Reject, and the bulk button from P5 | 0.5 day |
| 5 | Show photos in the species account, record detail, specimen dialog and Data Entry info card | 0.5 day |
| | **A8 total** | **~2.25 days** (was ~2–3) |
| 6 | A8b Inbox screen (four choices), the mover (rename to the convention, next free N, never delete), and an optional observation through Data Entry staging | 2–2.5 days |

## 5. What Wil runs now (read-only)

```
py -3.14 scripts\check_media_library.py
```

It takes a few seconds and opens no photo. Send back the printed summary. The CSV in
`scripts\_oneoff\media_library_check_<date>.csv` lists every file, with columns for the
parse, match and specimen candidates. The cloud-only line answers P1. The top-unmatched and
folder-disagreement lists show how much review the first link run will need.

# Backlog

## Updated 9 October 2026
## Check this before starting a session.

---

## Next

| | Item | Size |
|---|---|---|
| 0 | **I7b** — scheme + specimen import repairs. Fully planned in `41_Groundwork_Notes_20261009.md` Part 1 (~2.5 days); run its read-only measurement queries first. Then E7 (Part 2), photos/geo (Part 3) | ~2.5 days |
| 1 | **F11** — email Chris Raper (c.raper@nhm.ac.uk): the 24 British beetles the July 2025 UKSI flags redundant, and any copy newer than July 2025 | 10 min |
| 2 | **F14** — remaining (search and Lector only): build fix for the 366 CONFLICT carried synonyms; exclusions for NAMES errors (*Lamia*); add to the F11 email. Bridge part done 8 Oct | ~0.5 day |
| 3 | **G13** — your own accounts for the five survey key species with none: *Oligota apicata*, *Xysticus luctuosus*, *Liocyrtusa minuta*, *Chiasmia clathrata*, *Zophomyia temula* | ~1 hr |
| 4 | **E16** — decide the SQI verdict wording | decision |
| 5 | **D3** — merge `main` → `stable` | 15 minutes |
| 5b | **B8** — built 8 Oct; test on the next restart: commit a job with a blank site and a doubled row, expect "Check before commit" | 5 min test |
| 6 | **I7–I9** — rainy-day hygiene from the 6 October analysis: dead code, silent errors, read-only connections | ~1 day |

---

## A. Insect Collection

**A1. Bulk curatorial editor — HIGH.** 0.5–1 day. Of 2,745 specimens: condition
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

Sex is the exception: it needs the animal under the scope, and is being worked
through by hand (602 so far).

**A2. Verify curatorial edit on existing specimens.** Small. May already be
closed by the Session 29 dialog work — test by editing one and confirming it
saves and reloads.

**A3. `label_data` composition from the record.** 0.5 day. Deferred.

**A4. `drawer_unit` → `drawer_number` rename.** 0.5 day. The UI already says
Drawer Number. Column empty, no data risk; touches four files plus reset scripts.

**A5. Two specimens without a TVK.** Minutes. *Phoracantha recurva* (id 1263) and
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
---

## B. Data Entry

**B1. Clicker count-mode.** 0.5 day. A keystroke increments Qty; foot-pedal
compatible. For counting many individuals under the microscope without mental
tallying. Design in `26_Data_Entry_Design.md` §3.3.

**B2. Repeat key for sex splits.** Small. Clone the row, land on Sex.

**B3. Reject `?` and `#N/A` as TVKs on load** — ✅ **DONE** (8 October).
`load_workbook_to_staging.py` loads placeholder and Excel-error TVKs (`?`, `#N/A`,
`#REF!`, `-`, `0` ...) as no TVK and reports them; `check_data_entry_batches.py` lists
any still sitting in staging. None found in observations or specimens.

**B4. Species-name paste resolution.** 0.5 day. Pasted names store as text with
no TVK and commit anyway, with only a count as warning.

**B6. Common names typed in the species column.** Small. "Cricket bat spider"
reached staging with no TVK. Same class as B4; UKSI has no common name for many
taxa, so matching on common names is not a fix (it would have found Cricket-Bat
Willow). *8 Oct:* it went on to be **committed** (Bristol, "Cricket bat spid", no
TVK); set by hand to *Mangora acalypha*. B8 would have stopped it.

**B8. Warn before commit** — built 8 October, **awaiting a test** after restart.
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

---

## C. Import wizards

**C1. Re-enrich conservation from live Codex.** 0.5–1 day. **Raised in value:**
generated workbooks bake in Codex data that now predates five corrections.

**C2. Route wizards through `_get_preferred_common_name()`.** Small. Safe since
the Session 28 fix.

**C3. 175 rows with doubled import notes.** Cosmetic. A one-line UPDATE whenever
it matters.

**C4. Merge the three import wizards — WINTER.** 3–5 days, mostly testing against
real imports. Observation, specimen and scheme wizards are near-copies: four
mixins in up to four versions, and the species lookup three times (complexity
54–71, the hardest code in the suite). Every change to species matching -- a UKSI
update, kept taxa, synonyms -- must be made three times. The biggest
maintainability gain available; pays off most at the next UKSI release.

---

## D. Infrastructure

**D1. Reconfigure the offline server.** Unscoped; documentation lost. The proper
answer to single-machine risk.

**D2. External drive copy** — ✅ **DONE** (26 September; last refreshed 9 October, 0 failed). `D:\BiologicalSoftware_Offsite`,
3.8 GB, verified by `integrity_check` on the copy. **Refresh after any session
that changes data** — re-run the two `robocopy /MIR` lines in `01_Architecture.md`
§7; only changes copy.

**D3. Merge `main` → `stable`.** 15 minutes. Stale since June.

**D4. UKSI rebuild** — ✅ **DONE** (6 October), without the extractor:
`build_uksi_from_release.py` builds `uksi.db` from the NHM *Simplified Copy*
spreadsheet. Procedure in `01_Architecture.md` §5. The Access extractor is no
longer needed.

**D5. Reconstruct `build_pantheon_db.py`.** ~1 day. Open since March. Pantheon
has not moved since 2017, so this is insurance rather than need -- **except** that
the current `pantheon.db` stored every species without a TVK under one blank key
(fault F26), losing their ecology. The rebuild must key those on name. Source: the
Pantheon 3.7.4 CSVs in `Observatum\test data\` (part of that folder's ~120 MB --
keep them; not in git, so check they are on the `D:\` copy).

**D6. Sweep for never-executed code paths.** ✅ Swept 8 Oct (`40_Code_Sweep_20261008.md`
§1): 57 static hits → 2 real crashes and one wrong-data export, all three fixed; the
rest dead code or guarded (into I8 / I7b). pyflakes finds no undefined names.

**D7. Rebuild-twice-and-compare check.** 0.5 day. Build Codex into two files and
diff them; any difference means something is order-dependent. Would have caught
the collapse tiebreak in April, and converts the version-stamping promise from an
assumption into a tested fact.

**D9. Read-only connections for reference databases.** Half a day. 97
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

**D8. Laptop / second-machine access.** Unscoped. **SQLite over a syncing folder
from two machines risks corruption.** Options: strict one-at-a-time; export a job
and reimport; or the server. Needs a decision before it is attempted.

---

## E. Examen

Examen runs and reproduces the Pantheon website's SQI for Glory Park exactly. See
`08_Examen.md`.

**E1. Jurisdiction in the UI** — ✅ **DONE** (26 September). Derived from the
vice-county, with an override. See `08_Examen.md` §5.

**E2. Excel report renderer** — ✅ **DONE** (6 September). `Examen/workbook_export.py`.
Seven sheets: Summary with the stamp, Key species (Rare Key first, per Telfer,
with accounts and occurrence evidence), full species appendix with computed
footers, Habitats, Assemblages with FC thresholds and colour-coded PtT, Guilds,
and a generated status-definitions annex. Structure follows
`38_Report_Survey.md`. *September's "validation" (SQI 134) compared key species
only; the SQI was wrong. Now 117, matching the report — see `02` §3.*

**E2b. Workbook export button** — ✅ **DONE**. Beside Export Appendix.

**E3. PDF renderer.** ✅ First version 8 Oct, **awaiting Wil's review of the Glory Park
sample**. `Examen/pdf_export.py`, an **Export PDF** button beside Export Workbook. Laid
out FROM the workbook (built to a temp file), so every figure is the workbook's own:
basis of assessment, summary with notes, key species table and accounts with survey
evidence, habitats, assemblages, guilds, species list, status definitions; page header
and footer with run date and Codex version. Needs `py -3.14 -m pip install reportlab`.
Found on the way and fixed: the workbook's appendix footer gave a second SQI (scoring
species as denominator: Glory Park 120 against the Summary's 117) -- it now repeats the
Summary's figure.

**E4. Word renderer.** ✅ 8 Oct -- Wil's choice for now (copy and paste into reports
until the report contents are settled over winter). `Examen/word_export.py`, **Export
Word** in Examen: the PDF's sections as real Word headings and tables. Both renderers
read the workbook through one module, `Examen/report_model.py`, so they cannot drift.
Needs `py -3.14 -m pip install python-docx`.

**E5. `examen_data` tidy-up.** 0.5 day. `_classify_tier` has been removed and the
SQI arithmetic consolidated, but the **two parallel enrichment paths remain**:
the project table comes from `examen_data`, the detail tabs from
`PantheonAnalysisService`. That is the cause of any remaining figure mismatch.

**E6. Compartment analysis.** 0.5 day. Maps onto `sub_location`, already captured
by Data Entry. Standard practice — the 2025 Bicester report gives seven
compartments with their own counts and a stated 5% threshold, which is a worked
specification.

**E7. Saproxylic SQI + IEC.** ~3 days. **Neither exists in the software**, and the
Kent Deadwood report uses both.

The SQI list is **598 species**, not 605 — *"excluding Pseudovadonia livida
(Cerambycidae) which was included in the published list in error"* (Telfer 2020).
The IEC list is 180 species in three grades, scoring 3 / 2 / 1.

*Groundwork 8 Oct: sources, formulae, thresholds, licence and a design sketch in
`39_Research_Notes.md` §4.* Corrections to what follows: the rankings now hold ~241
sites; there is no download; khepri carries no licence (derive the SQI from Codex
statuses rather than ship its list).

**Both the scoring list and the national site rankings are online at khepri.uk**
(`khepri.uk/main` for scores, `khepri.uk/rankings/` for the 212-site league
table). Not a PDF to transcribe. The rankings are also how every saproxylic
report positions its site — *"the 27th highest British SQI"*.

**Thresholds must be configurable.** Fowles sets national importance at SQI 500
and international at 590; Alexander, who revised the IEC, considers 500 *"set
much too high"* and works to 300+ as the mark of a top British site. IEC
thresholds: >15 regional, >25 national, >80 international.

SQI needs 40+ qualifying species, a complete list, and equal attention to common
and rare species. IEC is cumulative across all surveys of a site, post-1950
records only, so every value is a minimum.

**E8. Presentation items.** ~1 day total. Several are now delivered in the
workbook and want carrying into the on-screen views: SQI at biotope and habitat
level, Key and Rare Key percentages, stenotopic count, status definitions.
Outstanding: the conservation column as species names not codes; vernacular
fallback ("A spider"); explicit SQI scale labelling.

**E8b. Taxonomic summary table.** Small. Group | sub-groups | Taxa | Spp. with
status | % with status, including "all saproxylic beetles" as a row. Standard
practice (EMG2 Table 2) and it shows where the interest sits.

**E9. Low-sample warning on the figure.** ✅ Done 8 Oct. A red ▲ with a tooltip on
the Overview SQI card, the project table and the assemblage table (was an
unexplained `*`); the habitat tree still withholds the index below threshold.

**E10. "Favourable (97 species, 19 required)".** ✅ Done 8 Oct. Assemblage tab: the
verdict with its evidence on each PtT cell and in the summary line. Favourable now
means species ≥ threshold; it was a rounded PtT ≥ 100%, which let 199 of 200 pass.

**E11. Overview sentence punctuation** — ✅ **DONE** (26 September). Also the
key-species card label, which read "of Pantheon species" when the figure is out
of total species recorded.

**E12. Views hardcode their own colour palettes.** 0.5 day. Six files define
their own constants rather than using `theme()`, contrary to coding rule 6.

**E13. Decide the fate of freeze / snapshots.** The case for stored state has
weakened — jurisdiction filtering now handles the main exclusion automatically,
and Session 26 decided the frozen record is the downloaded report. But
`examen.db` holds historical assessments that would need a home.

**E14. Pantheon ecology has no editor.** Unscoped. `pantheon.db` is a read-only
import with no way to correct or extend it. Musgrove et al. independently call
for an expert-consensus update mechanism. Natural England has funding again as of
2026, so upstream updates may resume.

**E16. The SQI verdict bands.** ✅ **Decided and done 8 Oct:** the verdict sentence is
removed; the reliability rule stays at **15 or more scoring species** (Telfer's reading,
the one reports cite -- Pantheon's own wording, "15 or less should not be used", would
make it 16; kept at 15 by decision). History: the Overview sentence ended *"This
indicates a site of national / regional importance / some conservation value"*
at SQI 200 / 150 / 125. **No published source found** — not Pantheon's, not
Fowles's (whose are 500 and 590, for a different index). The report survey found
authors citing percentages and naming their convention, precisely because
thresholds are contested. Options: remove the verdict; replace it with Telfer's
sourced test (~10% Key, >1% Rare Key); or keep the bands with a stated source.
Leaning to Telfer. See `06_Faults.md` F14.
*Researched 8 Oct (`39_Research_Notes.md` §1):* Pantheon says benchmarks don't exist;
no source for 200/150/125 anywhere. Telfer's definitions are confirmed but the
10%/1% numbers were not found in his own text; NECR624/628 (2026) are the citable
source for ">10% exceptional". Recommend removing the band sentence. Also found:
Pantheon's small-sample rule is "15 **or less**" — the code treats exactly 15 as
reliable (§1a, decision).

**E23. Managing a commercial job after commit.** ✅ Done 8 Oct. Commercial Reports
(Observatum → Stats/Reports): click a project to see its records by survey year and
site; **Add records** opens Data Entry on the project's job (reopened, or created for
imported projects) with the exact project, client and current embargo; **View / edit**
opens Observation Data filtered to the project -- editing and deleting stay there. **Edit project / client** renames
a project or changes its client across own records, contributed records and jobs in one
transaction (`shared/project_rename.py`), backed up first, warning when it would merge
into an existing project.
Data Entry: Project and Client are pickers of names already used (case/spacing
differences snap to the existing spelling); **Show committed** + **Reopen**. Observation
Data now pins the project (a banner with "Show all records"), surviving the reload
after an edit or delete.

**E17. Appendix export to match the workbook.** ✅ Done 8 Oct. Statuses through the
workbook's `status_parts`/`status_cell` (other jurisdictions greyed), "(derived)",
both SQIs, the SQI withheld below 15 scoring species. It no longer opens UKSI
writable (it had its own sort query).

**E18. Summary sheet presentation** — ✅ **DONE** (8 October). Survey and run
dates dd/mm/yyyy, "Analysis mode" reads "Codex Full". Dates and mode labels now come
from one place, `shared/display_format.py`, used by the workbook, the Site Analysis
table and Examen's status bar (three copies before).

**E19. "Taxonomic order" claimed but not delivered.** ✅ Done 8 Oct. One rule,
`examen_data.in_taxonomic_order`: insect order position × 1,000,000 + UKSI sort_code
(Observatum's `compute_taxonomic_sort_key`, imported), other orders after the
insects, no-TVK last. Key species sheet (within each tier), workbook appendix and
the appendix export all use it. The on-screen Species tab is unchanged.

**E20. Second SQI on the Overview.** ✅ Done 8 Oct. When any score was derived, the
SQI card and the summary sentence give the Pantheon-scores-only figure too.

**E21. Contributed records credited in the workbook.** ✅ Done 8 Oct. Summary stamp:
"Contributed records — 162 records contributed by Moore, J.; included in every
figure". Occurrence evidence: "contributed by Moore, J." on species with
contributed records.

**E22. Cosmetic display items.** Parked 26 September: Conservation tab layout;
record-detail profile preview width; the Project column's share of the table.

**E15. Survey-year edge case.** Small. A survey spanning a year boundary —
October to March fieldwork — would split across two rows. No current work does.

---

## F. Codex data

**F1. Odonata under vernacular names in `pantheon.db`.** Small. "Azure
Damselfly", "Banded Demoiselle", "Black Darter" and others sit in the
scientific-name column. Part of the 68 that resolve by no route. Few enough to
hand-map.

**F2. Unrouted designation codes.** 0.5 day. 1,519 rows across 16 codes reach no
track. Most is deliberate, but European Red List, bird breeding-season RE/DD and
some Global pre-94 codes fall through unmapped.

**F3. England assessments in the GB threat track.** Low. 2014 England vascular
plant entries carry GB abbreviations (`RedList_GB_post2001-EX`) despite an
England source, so they route to `threat_iucn_2001` rather than
`red_list_england`. JNCC's labelling, not a fault here. Vascular plants only.

**F4. The *Hylaeus annularis* group.** For an entomologist. Three segregates
carried SQS 8; the incumbent carries 1 while holding RDB 3, which the published
rule scores at 8. Under incumbent-wins it stays at 1 and the disagreement remains
visible as a Pantheon-vs-rule case rather than being silently patched.

**F5. Nine research-only rows with no TVK.** Small, after D5. *Re-measured 8 Oct:*
of Pantheon's 72 research-only rows, 63 have a TVK and all are bridged (62 current
TVKs after the *Euxoa* merge). The other 9 have no TVK in `pantheon.db` (fault F26),
so which species they are can only be read from the Pantheon source CSVs. Until
then those species count as ordinary S41.

**F6. Env (Wales) Act S7 and research-only.** Decision, from sources. Did S7
inherit the UK BAP research-only category? If so, extend the rule; at present
Cinnabar is key at a Welsh site.
*Researched 8 Oct (`39_Research_Notes.md` §2):* no — the Welsh S42/S7 lists carry no
research-only flag; Cinnabar is on S7. Current behaviour is correct by the letter.
A new Welsh S7 spreadsheet (Mar/May 2026) exists — download it to compare with Codex.

**F7. Fallback by name for unbridged record TVKs.** 0.5 day, **probably not needed**:
the NAMES-by-key bridge (8 Oct) fixed *Nomada panzeri* and 17 other same-name cases.
Keep only if another split turns up with no bridge.

**F8. NECR702 licence.** ✅ Confirmed set 9 Oct (dry run: "Already set"). Checked 8 Oct: OGL v3.0, © Natural England 2026, author
Steve A. Lane. `import_status_review.py --licence-only --licence "Open Government
Licence v3.0"` sets it (command in `39_Research_Notes.md` §3) — **to run, apps closed.**
New imports take `--licence` directly.

**F9. Retire Codex Manager's Import Review tab.** ~30 min. Writes accounts keyed on
TVK alone, the old way. `import_status_review.py` is now the one importer. Remove
the tab's import or have it call the script.

**F10. Importer dry-run message.** ✅ Done — checked 8 Oct: the importer now
says the patch is "already applied"; nothing left to change.

**F11. UKSI questions for Chris Raper.** 10 minutes. (1) The July 2025 UKSI
flags 24 British beetles redundant with no current replacement (*Bolitobius
formosus*, *Ochthebius difficilis*, *Cypha ovulum*, the *Aphodius* segregates...);
kept selectable at your request, marked "not current in UKSI 2025". (2) 66 JNCC
TVKs and 7 record TVKs (42 records) are newer than July 2025; ask for a current
copy. Then rebuild as `01` §5.

**F12. *Mycetoporus piceolus* → 'species A'.** Accepted 6 Oct as the UKSI's
concept transfer (*erichsonanus* → current *piceolus*). Revisit if you disagree:
the two Tachyporinae accounts moved with it.

**F13. *Tetartopeus ciceronii* account.** Rove beetle review, no UKSI match until
a release newer than July 2025. Load with `load_review.py --add-accounts` then.

**F14. Wrong targets in `uksi.synonyms`** (fault F25). ~1 hr to diagnose, read-only:
(1) every synonym whose epithet differs from its target's epithet *and* matches another
current taxon in the same family (a differing epithet alone is not proof, e.g.
*Ranunculus ficaria* → *Ficaria verna*); (2) synonym names mapped to more than one TVK;
(3) of those, which came from the July NAMES sheet and which were carried over from
the old file; (4) exposure: `codex.tvk_bridge` rows with `match_method = 'name'`
using a flagged name, and any record re-keyed through one; (5) is *Cerambyx textor*
in the NAMES sheet? Report counts, then choose: (A) fix `build_uksi_from_release.py`
so carried rows yield to NAMES and conflicts are reported, then rebuild UKSI → Codex
(preferred); (B) consumers filter flagged rows (Lector's stopgap, built in its own
chat); (C) a `synonym_exclusions` list applied at build. Handover:
project doc `claude/27_UKSI_Synonyms_Handover.md`.

*Measured 8 Oct (fault F25):* *Lamia* comes from the NAMES sheet itself, so (A) alone
does not fix it.

**Bridge part DONE 8 Oct:** the Pantheon bridge now goes by NAMES key (two Codex
rebuilds; 104 disagreements → 37 deliberate; reference figures updated with each change
explained in `02`). Left: (C) exclusions for NAMES errors such as *Lamia*, reported to
Chris Raper with F11; (A) for the 366 CONFLICT rows -- both affect search and Lector,
not analyses.

---

## G. Species profiles

**Two layers, never mixed — decided and built 26 September.**
Review accounts: `codex.db.species_profiles`, one per species **per review**, keyed
`(tvk, review_id)`, verbatim and cited, never edited; superseded ones kept.
Your accounts: `observatum.db.species_profiles`, one per species, keyed on TVK.
Every display reads both through `shared/species_accounts.py`. *Supersedes G1's
September decision to keep review text in `observatum.db`.*

**G5, G6 — done 4 October.** Editor (review accounts read-only above, yours
below); Record Detail shows all accounts in a right-hand column in the tab's
colours; the workbook quotes open-licence accounts with citation, points to the
rest, and marks the source in an Account source column.

**G7, G8, G9 — done 4–5 October.** Acalyptratae (with statuses), Orthoptera,
caddis, shieldbugs, hoverflies loaded. Spiders: nothing to load (rationales
only, all rights reserved).

**G7 (was). Acalyptratae (NECR217).** 263 pp, provisional (2016). Accounts from
data sheets **and** statuses (JNCC carried only part, as with NECR234; ~130
species in `check_newest_review.py` list (1) wait on it). Read its excluded list.

**G8. Remaining PDF reviews.** Orthoptera (187), caddis (191) -- accounts in PDF;
shieldbugs (190) -- table has no accounts, PDF not yet downloaded.

**G9. Not yet downloaded.** Spiders 2017 (149 of your species), hoverflies 2014.

**G10. Old JNCC reviews.** Falk 1991 aculeates ✅ loaded 5 Oct (typed text, not a
scan; *IR*). Hyman 1992/94 and Falk 1991 flies Part 1 are print only (Hyman is
in the Internet Archive's lending library -- read there, but do not capture
pages). No survey figure depends on them: their statuses are in Codex via JNCC.
Routes when wanted: your own copies scanned; ask JNCC for a digital copy (would
also make them quotable); or write your own.

**G11. Supersession links.** When two loaded reviews cover the same group, set
`reviews.supersedes_id` so the older account shows as superseded. Not yet needed.

**G12. Loose names.** *Cantharis nigra* (NECR134) does not match UKSI -- check
name; *Macronychia dolini* absent from NECR234 -- check; Staphylinidae (265 in
the newest-review list) are scope, correctly left.

**G3. Your profiles from your reports** — ✅ **DONE** (6 October). 141 imported
from eight reports (four layouts: heading + paragraph, numbered paragraph,
appendix accounts, a Word table), verbatim, survey sentences held back.
`scripts/import_own_profiles.py` skips any species that already has one.

**G4. Scope.** Profiles only for species with a conservation status, or groups of
interest such as Cerambycidae. Disagreement with a published status goes in your
account — **no override field**.

---

## K. Contributed records

Built 2 October. `contributed_observations` (with contributor, source file, date
received, permission, import batch); `assessment_records` view for Examen;
`scripts/import_contributed.py` (columns by heading, UKSI matching, `--replace`).
Stats, mapping and iRecord never see contributed data.

**K1. Contributed tab in Observatum.** ~20–30 min. Read-only browse by
collaborator, project and batch.

**K2. Credit in reports.** ✅ Done with E21 (8 Oct).

---

## H. Mapping tab

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

## I. Codebase hygiene

From `37_Code_Review_Findings.md`, an independent static-analysis pass.
**Unverified** — treat each as a claim.

**I1. Verify the claimed crash bugs** — ✅ **DONE** (6 October) by a full
static analysis: two undefined names in ~97,500 lines, both fixed
(`vc_lookup_service` `List`, the observation-filter fallbacks).

**I2. Delete `scripts/sqs_derivation.py`** — ✅ **DONE** (26 September), along
with the superseded `check_bridge_gap.py`. Confirmed nothing imported either.

**I3. Consolidate grid-ref maths.** (`Tabella/grid_ref.py`'s `OS_GRID_LETTERS`
table is unused and its values are wrong -- delete it with this.) Three implementations —
`grid_ref_service.py`, `DataEntry/osgb.py`, `Tabella/grid_ref.py`. **The
highest-value item here:** a subtle disagreement produces *wrong vice-counties*,
not a crash, and VC is derived rather than typed so nothing would question it.

*I3 measured 8 Oct* (pyproj and the OS spec as oracle, on all 3,250 distinct grid refs
in your records): `vc_lookup_service.parse_grid_ref` agrees with the spec on every one,
and its letter table is right (only offshore squares missing). `Tabella/grid_ref.py` is
archived. `grid_ref_service.to_coordinates()` is an unimplemented stub with no callers --
delete. The real problems are VC in boundary squares (F29) and lat/long without the
datum shift (F30):

**I3b. VC by point-in-polygon at boundaries** (fault F29). ~0.5 day. Use the VC
boundaries (`data/maps/vc_brc_wgs84.geojson`) for refs finer than 1 km whose 1 km square
straddles a boundary; report "on a boundary" for a ref too coarse to decide. Then a
read-only list of records whose stored VC disagrees, for your judgement.

**I3c. One lat/long converter, and recompute the 3,332** (fault F30). ~1 hr + a dry
run. The import wizard and `DataEntry/osgb.py` call `grid_converter_service` (or a
shared function with the Helmert shift) instead of their own maths.

**I4. Remove the stale wizard set.** Five files, ~1,700 lines. Only
`species_match_report_dialog.py:398` still imports `RowStatus` from it.

**I5. `ruff.toml` + pre-commit hook.** So the lint counts stop growing.

**I6. Tests for the pure functions.** ✅ Done 8 Oct — `tests/test_pure_functions.py`,
102 tests, no database touched, under a second: date utils, SQS derivation (every
rarity × threat × legacy combination stays on the 0/1/4/8/16/32 ladder), species
ranking, sex summary, display format, Examen's taxonomic order, `precommit_issues` and `build_kwargs_from_row`,
grid-ref parsing and the 1 km square, the specimen sort key. Run
`py -3.14 -m pytest tests` (`pip install pytest` once) after touching any of them.
Next candidates as they are touched: `grid_converter_service`, the import wizards'
species matching (C4).

**I7. Review silent errors.** Swept 8 Oct (`40_Code_Sweep_20261008.md` §3): 189
silent handlers; three can lose or duplicate records (F35), several more import
records with missing fields (F34).

**I7b. Import wizard repairs** (faults F32–F35). ~1 day, then testing against real
imports -- overlaps C4 (merge the three wizards), so best done with it. **Measure
first, read-only:** records with NULL sort key by import batch; scheme rows from
iRecord files with NULL `irecord_id`; duplicate `nbn_atlas_id` / `observatum_key`.
Then: UPDATE only supplied columns; fixed column list in the scheme batch insert;
batched duplicate lookups that fail loudly; `utf-8-sig` first; sort key / superfamily
/ subfamily computed and stored; row warnings instead of `pass`.

**I8. Remove dead code.** 1–2 hours. 10 modules nothing imports (~1,900 lines:
`conservation_override.py`, `DataEntry/entry_page.py`, `session_picker.py`,
`column_config_dialog.py`, the two theme files, `shared/db_config.py`,
`uksi_diagnostic.py`, `gamification_widgets.py`, `build_gb_basemap.py` -- **keep
the last**, see `01` §2); a 52-line block pasted twice in `scheme_dashboard.py`;
duplicated functions in Curator; 399 unused imports (automatable). Delete Examen's
disabled `manual_entry_dialog.py` with them.

**I9. Duplicated UI components.** 1–2 days. FilterChip ×6, FuzzyCompleter ×3,
FuzzyFilterProxyModel ×3, RowStatus ×4 -- confirmed by the analysis.

**I10. Split the two most complex functions** when next touched:
`ObservationTab._apply_wizard_filters` (99) and
`ObservationStatsService._refresh` (92). Half a day each.

---

## Closed, worth not relitigating

**Tabella** — development paused August 2026. Superseded by Data Entry for desk
work. Sheet protection and the Settings path are not being pursued.

**Species status override** — will not build. Statuses are taken at face value
from the last review; disagreement goes in the profile text.

**`specimen_code`** — will not do. No retro-labelling.

**The S41 research-only distinction** — solved 2 October. `pantheon.db` carries 72
species under *"Section 41 Priority Species - research only"*. Mapped through the
bridge and applied in **both** analysis modes, to the S41 **and** UK BAP entries;
`_priority_applies` rejects research-only everywhere. Remaining gaps: F5, F6.

**Vice-county from grid reference** — done 26 September (4,169 backfilled).

**Contributed data via staging** — rejected 2 October. Committing a
collaborator's records into `observations` would count them in your stats and
offer them to iRecord. They go to `contributed_observations`.

# Backlog

## Updated 7 October 2026
## Check this before starting a session.

---

## Next

| | Item | Size |
|---|---|---|
| 1 | **F11** — email Chris Raper (c.raper@nhm.ac.uk): the 24 British beetles the July 2025 UKSI flags redundant, and any copy newer than July 2025 | 10 min |
| 2 | **F14** — investigate `uksi.synonyms` mapping other species' old names to the wrong taxon (*Lamia sartor* → *L. textor*); read-only counts first — fault F25 | ~1 hr |
| 3 | **G13** — your own accounts for the five survey key species with none: *Oligota apicata*, *Xysticus luctuosus*, *Liocyrtusa minuta*, *Chiasmia clathrata*, *Zophomyia temula* | ~1 hr |
| 4 | **E16** — decide the SQI verdict wording | decision |
| 5 | **D3** — merge `main` → `stable` | 15 minutes |
| 6 | **I7–I9** — rainy-day hygiene from the 6 October analysis: dead code, silent errors, read-only connections | ~1 day |

---

## A. Insect Collection

**A1. Bulk curatorial editor — HIGH.** 0.5–1 day. Of 2,745 specimens: condition
8, storage 2, drawer 0, preparation 204. Those are properties of a tray, not a
specimen — select everything in a drawer, set Storage and Drawer once.
Per-record editing is not viable. Never touches biological data.

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
and stay invisible to the sidebar. Assign one by hand.

**A6. Live sidebar refresh — parked.** Small. After editing a specimen the tree
keeps its old counts until restart. `_refresh_sidebar()` exists; it simply isn't
called after a save. Parked by choice: rebuilding collapses the tree and loses
your place, which may annoy more than a periodic restart.

**A7. Normalise `subfamily` storage.** Small, low. Stored as NULL on some rows
and `''` on others for the same species. The sidebar now copes; the data is
still inconsistent and any other query grouping on it would split the same way.

---

## B. Data Entry

**B1. Clicker count-mode.** 0.5 day. A keystroke increments Qty; foot-pedal
compatible. For counting many individuals under the microscope without mental
tallying. Design in `26_Data_Entry_Design.md` §3.3.

**B2. Repeat key for sex splits.** Small. Clone the row, land on Sex.

**B3. Reject `?` and `#N/A` as TVKs on load.** Trivial. Two rows slipped through
the workbook migration.

**B4. Species-name paste resolution.** 0.5 day. Pasted names store as text with
no TVK and commit anyway, with only a count as warning.

**B6. Common names typed in the species column.** Small. "Cricket bat spider"
reached staging with no TVK. Same class as B4; UKSI has no common name for many
taxa, so matching on common names is not a fix (it would have found Cricket-Bat
Willow).

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

**D2. External drive copy** — ✅ **DONE** (26 September). `D:\BiologicalSoftware_Offsite`,
3.8 GB, verified by `integrity_check` on the copy. **Refresh after any session
that changes data** — re-run the two `robocopy /MIR` lines in `01_Architecture.md`
§7; only changes copy.

**D3. Merge `main` → `stable`.** 15 minutes. Stale since June.

**D4. UKSI rebuild** — ✅ **DONE** (6 October), without the extractor:
`build_uksi_from_release.py` builds `uksi.db` from the NHM *Simplified Copy*
spreadsheet. Procedure in `01_Architecture.md` §5. The Access extractor is no
longer needed.

**D5. Reconstruct `build_pantheon_db.py`.** ~1 day. Open since March. Pantheon
has not moved since 2017, so this is insurance rather than need.

**D6. Sweep for never-executed code paths.** 0.5 day. **Seven found this year**,
all crash-on-first-use. Two more claimed by the September code review and
unverified — see `37_Code_Review_Findings.md`.

**D7. Rebuild-twice-and-compare check.** 0.5 day. Build Codex into two files and
diff them; any difference means something is order-dependent. Would have caught
the collapse tiebreak in April, and converts the version-stamping promise from an
assumption into a tested fact.

**D9. Read-only connections for reference databases.** Half a day. 97
`sqlite3.connect()` calls across 55 files, 13 read-only. "Only Codex Manager
writes to Codex" is a convention the code does not enforce -- the Examen
manual-entry route (fixed 6 Oct) is where it broke. A shared helper, read-only by
default for UKSI, Codex and Pantheon.

**D10. After a UKSI swap, `restore_dropped_statuses.py` can false-positive.** It
compares old TVKs; statuses that moved to the current TVK look dropped
(*Mycetoporus baudueri*, 6 Oct). Check the current TVK before restoring; teach the
script to follow `uksi.tvk_remap`. Small.

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

**E3. PDF renderer.** 1–1.5 days. The flagship — the document that gets attached.

**E4. Word renderer.** 0.5–1 day. The editable one, for pasting into templates.

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

**E9. Low-sample warning on the figure.** Small. Pantheon's red triangle — show
the SQI and flag it where the species count is under 15. Partly done: the habitat
tree now withholds the index below threshold and shows the scoring count instead.

**E10. "Favourable (97 species, 19 required)".** Small. State the verdict with
its evidence, as Pantheon does.

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

**E16. The SQI verdict bands — DECISION.** The Overview sentence ends *"This
indicates a site of national / regional importance / some conservation value"*
at SQI 200 / 150 / 125. **No published source found** — not Pantheon's, not
Fowles's (whose are 500 and 590, for a different index). The report survey found
authors citing percentages and naming their convention, precisely because
thresholds are contested. Options: remove the verdict; replace it with Telfer's
sourced test (~10% Key, >1% Rare Key); or keep the bands with a stated source.
Leaning to Telfer. See `06_Faults.md` F14.

**E17. Appendix export to match the workbook.** Small. Both SQIs in the totals
line; "(derived)" on derived scores; jurisdiction-named, legal-named status.

**E18. Summary sheet presentation.** Small. Survey and run dates in dd/mm/yyyy;
"Analysis mode" shows `codex_full`, not "Codex Full".

**E19. "Taxonomic order" claimed but not delivered.** Small. The key species sheet
says taxonomic order within each tier but sorts by SQS; the workbook appendix is
key species then alphabetical. `appendix_export.py` already sorts taxonomically —
reuse that rule.

**E20. Second SQI on the Overview.** Small. The screen shows one figure; the
workbook shows both bases.

**E21. Contributed records credited in the workbook.** ~10–15 min. A stamp line
("includes 162 records contributed by J. Moore") and recorders named in the
occurrence evidence.

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

**F5. Ten research-only species unbridged.** Small. Pantheon lists 72; 62 reach
current TVKs. Find the other 10 and map them, or they count as ordinary S41.

**F6. Env (Wales) Act S7 and research-only.** Decision, from sources. Did S7
inherit the UK BAP research-only category? If so, extend the rule; at present
Cinnabar is key at a Welsh site.

**F7. Fallback by name for unbridged record TVKs.** 0.5 day. *Nomada panzeri* s.l.
on the records, Pantheon's data bridged to s.s. When a record's TVK has no bridge
entry, try another current TVK of the same name. Catches every post-2017 split.

**F8. NECR702 licence.** Minutes. Check the report's front matter (very likely
OGL v3.0) and set `reviews.licence` — survives rebuilds.

**F9. Retire Codex Manager's Import Review tab.** ~30 min. Writes accounts keyed on
TVK alone, the old way. `import_status_review.py` is now the one importer. Remove
the tab's import or have it call the script.

**F10. Importer dry-run message.** Trivial. Still says "apply
`patch_codex_manual_apply.py` first" — long since done.

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

**K2. Credit in reports.** See E21.

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

**I4. Remove the stale wizard set.** Five files, ~1,700 lines. Only
`species_match_report_dialog.py:398` still imports `RowStatus` from it.

**I5. `ruff.toml` + pre-commit hook.** So the lint counts stop growing.

**I6. Tests for the pure functions.** Grid-ref parsing, SQS derivation, date
utils, VC lookup — cheap to cover, and exactly where the claimed bugs live. One
test file currently covers ~105k lines.

**I7. Review silent errors.** 2–3 hours. 131 handlers that only `pass`; start
with the import validation workers (26), where one could hide a record failing
to import.

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

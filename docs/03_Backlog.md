# Backlog

## Updated 2 October 2026
## Check this before starting a session.

---

## Next

| | Item | Size |
|---|---|---|
| 1 | **G5** — species account editor (review text above, yours below) | ~30 min |
| 2 | **E16** — decide the SQI verdict wording | decision |
| 3 | **A1** — bulk curatorial editor | 0.5–1 day |
| 4 | **E3** — PDF renderer | 1–1.5 days |
| 5 | **D3** — merge `main` → `stable` | 15 minutes |

Examen now reproduces an issued report's SQI exactly (Glory Park, 117). The
verdict sentence (E16) matters more than before: every SQI fell on 2 October, so
its unsourced bands now attach to different sites.

*Sizes are focused time. Estimate in exchanges: ~2–3 minutes each once the code
has been read (`05_Rules.md`).*

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

---

## C. Import wizards

**C1. Re-enrich conservation from live Codex.** 0.5–1 day. **Raised in value:**
generated workbooks bake in Codex data that now predates five corrections.

**C2. Route wizards through `_get_preferred_common_name()`.** Small. Safe since
the Session 28 fix.

**C3. 175 rows with doubled import notes.** Cosmetic. A one-line UPDATE whenever
it matters.

---

## D. Infrastructure

**D1. Reconfigure the offline server.** Unscoped; documentation lost. The proper
answer to single-machine risk.

**D2. External drive copy** — ✅ **DONE** (26 September). `D:\BiologicalSoftware_Offsite`,
3.8 GB, verified by `integrity_check` on the copy. **Refresh after any session
that changes data** — re-run the two `robocopy /MIR` lines in `01_Architecture.md`
§7; only changes copy.

**D3. Merge `main` → `stable`.** 15 minutes. Stale since June.

**D4. Rewrite `uksi_extractor.py`.** ~1 day. Needed when NHM next release UKSI.
`uksi.db` is the specification.

**D5. Reconstruct `build_pantheon_db.py`.** ~1 day. Open since March. Pantheon
has not moved since 2017, so this is insurance rather than need.

**D6. Sweep for never-executed code paths.** 0.5 day. **Seven found this year**,
all crash-on-first-use. Two more claimed by the September code review and
unverified — see `37_Code_Review_Findings.md`.

**D7. Rebuild-twice-and-compare check.** 0.5 day. Build Codex into two files and
diff them; any difference means something is order-dependent. Would have caught
the collapse tiebreak in April, and converts the version-stamping promise from an
assumption into a tested fact.

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

---

## G. Species profiles

**Two layers, never mixed — decided and built 26 September.**
Review accounts: `codex.db.species_profiles`, one per species **per review**, keyed
`(tvk, review_id)`, verbatim and cited, never edited; superseded ones kept.
Your accounts: `observatum.db.species_profiles`, one per species, keyed on TVK.
Every display reads both through `shared/species_accounts.py`. *Supersedes G1's
September decision to keep review text in `observatum.db`.*

**G5. The editor — NEXT.** ~30 min. `species_profile_dialog.py`: review text
read-only with its citation above, your account editable below, wider window.
Key on TVK; never write without one; never touch review text. Until it is done
the editor opens blank for leaf beetles — correct, since that box is yours.

**G6. Workbook account column.** ~15 min. Your account where written, else the
review text marked as quoted and cited, with a column saying which. The workbook
still reads only `observatum.db`.

**G3. Extract ~100 existing profiles from Word.** 0.5–1 day. Roughly 10 `.docx`
files.

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

**I1. Verify the four claimed crash bugs.** Start with `vc_lookup_service`, the
fastest to disprove.

**I2. Delete `scripts/sqs_derivation.py`** — ✅ **DONE** (26 September), along
with the superseded `check_bridge_gap.py`. Confirmed nothing imported either.

**I3. Consolidate grid-ref maths.** Three implementations —
`grid_ref_service.py`, `DataEntry/osgb.py`, `Tabella/grid_ref.py`. **The
highest-value item here:** a subtle disagreement produces *wrong vice-counties*,
not a crash, and VC is derived rather than typed so nothing would question it.

**I4. Remove the stale wizard set.** Five files, ~1,700 lines. Only
`species_match_report_dialog.py:398` still imports `RowStatus` from it.

**I5. `ruff.toml` + pre-commit hook.** So the lint counts stop growing.

**I6. Tests for the pure functions.** Grid-ref parsing, SQS derivation, date
utils, VC lookup — cheap to cover, and exactly where the claimed bugs live. One
test file currently covers ~105k lines.

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

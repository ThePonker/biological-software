# Faults

## Updated 8 October 2026
## Open faults carry an action. Closed ones are kept in brief, because knowing
## what has already gone wrong is how the rules in `05` were earned.

---

## Open

### F2. `stable` branch stale since June
The Data Entry build and four months of work sit on `main` only. The branching
discipline exists precisely so `stable` can be the field-season tool.
**Action:** merge once the staging jobs are committed and proven — backlog D3.

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

### F24. Reference databases opened read-write
97 connections, 13 read-only. Nothing in the code stops a view writing to Codex
or UKSI; the Examen manual-entry route (closed below) is where that broke.
**Action:** backlog D9.

### F25. `uksi.synonyms` maps other species' old names to the wrong taxon — INVESTIGATE
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

**Action:** backlog F14, revised: (1) the 366 CONFLICT rows -- the build fix
(carried rows yield to NAMES) still applies, but affects search and Lector only;
(2) the 26 multi-target bridge rows -- review, then pin by hand; (3) *Lamia* and any
other NAMES errors -- a local exclusions list, and report to the NHM (F11).

### F26. Pantheon species without a TVK collapsed onto one blank key
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
**Action still open:** fix `remap_record_tvks.py` to use the specimens' formula, not a
guess, before the next UKSI update -- or the next update repeats both problems.

### F28. Data Entry commits carried gaps
*Found 8 October 2026* in the morning's five commits (1,136 records): 59 with no site
name, 31 pitfall records with no trap or grid ref, one common name typed as a species
("Cricket bat spid" -- B6), three species entered twice with sex left "Not recorded".
Commit flags only a missing TVK or a future date. All of those fixed the same morning
(`scripts\_oneoff\fix_*_20261008.py`). Of the further doubles the check found, four
Slade Green re-entries were deleted (Run 2); Elmley's ladybirds, *Philanthus*, *Tephritis*
and *Odynerus* confirmed as genuine; three pairs with different quantities (*Kalama*,
*Melanogaster*, *Margarinotus*) left as separate lines.
**Action:** run `scripts\check_data_entry_batches.py` after every commit; a warning
in Data Entry before commit -- backlog B8.

### F4. `build_pantheon_db.py` missing
Same event. Pantheon has not been updated since 2017 v3.7.4, so this is insurance
rather than need. **Action:** backlog D5.

### F5. Curatorial fields almost empty across the collection
Of 2,745 specimens: preparation 204, condition 8, storage 2, drawer 0. Curator
does not write them; the Add Specimen dialog captures four, but only for new
specimens. **Action:** bulk editor — backlog A1.

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

### F9. England assessments in the GB threat track
2014 England vascular plant entries carry GB abbreviations
(`RedList_GB_post2001-EX`) despite an England source, so they route to
`threat_iucn_2001` rather than `red_list_england`. JNCC's labelling, not a fault
here. Vascular plants only. **Action:** backlog F3.

### F17. Research-only species that do not reach the bridge
Pantheon lists 72 rows as S41 research only. *Measured 8 October:* **63 carry a
TVK and all 63 are bridged**; they reach 62 current TVKs only because *Euxoa crypta*
and *E. tritici* merge into one -- correct, not a gap. The other **9 rows have no TVK
at all** in `pantheon.db` (F26), so they cannot be bridged, and those species are
treated as ordinary S41 -- able to confer key status. (Previously recorded as "62
of 72, 10 unbridged".) **Action:** backlog F5, which depends on D5.

### F18. Does Env (Wales) Act S7 carry the research-only qualification?
At a Welsh site, Cinnabar and Latticed Heath still count as key through S7.
Whether S7 inherited the UK BAP research-only category needs the Welsh source
documents, not an assumption. Machen's key species did not move. **Action:**
backlog F6.

### F19. Taxa split since 2017 lose their Pantheon data
*Nomada panzeri*: records carry the sensu lato TVK; the bridge maps Pantheon's
2017 *N. panzeri* (which has a score and a biotope) to the sensu stricto TVK. The
record gets nothing. Pantheon's concept predates the split, so s.l. is arguably
the better match. **Action:** read-layer fallback by name when a record's TVK is
unbridged — backlog F7.

### F20. Open habitats SQI 2 points above the Pantheon website at Glory Park
125 against the report's 123, same 96 species. Every other figure matches
exactly. Most likely one score differing between Pantheon 3.7.4 (held) and 3.7.6
(website). **Action:** none unless it recurs; note only.

### F21. The Appendix export still reports one SQI
`appendix_export.py`'s totals line gives a single SQI and does not mark derived
scores. The workbook is the document that goes out; this should still match it.
**Action:** backlog E17.

### F11. Mixed line endings
Some files LF, some CRLF. `.gitattributes` added, but existing files are
unconverted, so multi-line string anchors still fail unpredictably.
**Action:** prefer line-based patching. See `05_Rules.md`.

### F12. `drawer_unit` column name
The UI reads "Drawer Number"; the column is `drawer_unit`. Rename touches four
files plus reset scripts. Column empty, no data risk. **Action:** backlog A4.

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
**Action:** backlog E16.

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

## Closed — the ones worth remembering

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

### 4,026 Pantheon scores discarded — every SQI inflated since April
*Fixed 2 October 2026. The most consequential fault found this year.*

`build_codex_db.py` imported a Pantheon SQS only if the species was in
`invert_tvks` — built from **designations with category 'Invertebrate'**. Common
species hold no designation, so their Pantheon scores (almost all SQS 1) were
discarded as "non-invertebrate TVK collisions": **4,085**, of which 59 were real
collisions. Species that arrived with Pantheon ecology still appeared in Examen;
those with a score but no biotope coding — 7-spot Ladybird, Common Greenbottle,
Marmalade Hoverfly — vanished from the SQI entirely.

Effect: fewer than half of each list scoring, the common SQS-1 species missing,
**every SQI too high** — Glory Park 134, Kent Deadwood 247, Birmingham 146.

Found from a label: "no Pantheon data" against the 7-spot Ladybird, which Pantheon
certainly contains. Fixed by deciding "invertebrate" from **UKSI taxonomy**
(Animalia outside Chordata; 66,322 TVKs) unioned with the designations set.
Pantheon scores kept: 5,568 → 9,611.

**The September validation never compared the SQI.** It matched Glory Park's key
species to the report and stopped. The report's SQI was 117 throughout.

### SQI divided by scoring species, not species analysed
*Fixed 2 October 2026.* `SQIResult.calculate` divided by `species_with_sqs`.
Pantheon divides by every species it analysed, an unscored one counting 0 — the
issued reports' method sections say so. Glory Park after the score fix: 144 ÷ 120
= 120; Pantheon: 144 ÷ 123 = **117, the report exactly.** Every SQI now reports
both counts, and the workbook notes give the sum and divisor.

### Derived scores included silently
*Fixed 2 October 2026.* `get_sqs_scores` returns Pantheon's score, else one
derived from the rule, in one dict with nothing marking which. The SQI mixed them
while the stamp said "SQS basis: Pantheon published"; "Analysed by Pantheon"
counted derived-only species. Birmingham: four derived scores, *Cistogaster
globosa* 16 among them. Now `get_stored_sqs_tvks()` separates them; both SQIs are
reported; derived scores read "16 (derived)"; species Pantheon lacks read "no
Pantheon data".

### Research-only moths counted as Key Species
*Fixed 2 October 2026.* Pantheon distinguishes 72 "S41 research only" species;
JNCC lists them as plain S41, so Codex Full counted Cinnabar and Latticed Heath as
key. The workbook's own definitions sheet said they were not. First fix
relabelled the S41 entry — and they **stayed key through UK BAP**, where the
category came from. Both entries are now labelled research-only, and
`_priority_applies` rejects them everywhere. Birmingham 9 → 7, Badshot Lea 9 → 8,
Bicester 2023 18 → 17; Glory Park unchanged.

### Habitats nested under every biotope a species had
*Fixed 2 October 2026.* `pantheon.db` stores a species' biotopes and habitats as
unlinked lists, so a species both open-habitat and tree-associated put "decaying
wood" under open habitats. The September fix removed the site-wide cross-product
but not this per-species one. Pantheon's own tree is in `habitat_traits`
(`parent_trait_id`); pairings it does not make are now skipped. Totals unchanged.

### Exports said "Priority" and "Legal (1)" without saying where
*Fixed 2 October 2026.* Non-key species exported Codex's short status. Six
Birmingham species read "Priority" — they were SBL or NI Priority; Holly Blue read
"Legal (1)" — the NI Wildlife Order. A reader takes both as English. Exports now
carry the jurisdiction-named label and each legal instrument by name, greyed by
the classifier's own rules.

### Data Entry commit set the embargo date but not the status
*Fixed 2 October 2026.* The iRecord export excludes a record only when
`embargo_status == 'Active'` **and** the date is in the future. The first real
commit (Birmingham, 172 records) set only the date, so the batch was uploadable.
Found by checking the first commit's rows, before any export. `commit_job` now
sets the status; the 172 corrected. The other 3,332 embargoed records were fine.

### Order, family and common name blank in the workbook
*Fixed 2 October 2026.* `SiteSpecies` had no such fields; the Species tab looked
them up separately and the Appendix export did so a third time. One
`load_taxonomy()` in `examen_data` now serves all three.

### The project table vanished when a project was selected
*Fixed 2 October 2026.* A maximum height and no minimum on the table, in a
collapsible splitter. Now a floor, non-collapsible, remembered, and pinned across
clicks.

### Future-dated and mis-dated Kent Deadwood records
*Fixed 26 September and 2 October 2026.* One *Melanotus* dated 2026-07-10 and
seven Ashenbank Wood records dated 2025-07-10 — all the 10 July 2024 visit
(evidence: matching grid refs among 57 records that day). Kent Deadwood is now a
single 2024 survey of 1,021 records. Was F10.

### Rebuilds renumbered reviews
*Fixed 26 September 2026.* Preservation saved every review column except `id`;
the restore let AUTOINCREMENT assign new ones. With one review it was harmless;
after any deletion, every `manual_entries.review_id` and `supersedes_id` would
have pointed at the wrong review. Ids now preserved explicitly.

### 338 specimens missing from the Insect Collection tree
*Fixed 12–13 September 2026.*

The sidebar had been under-reporting for six months. Found only when a sex
breakdown — counted independently — sat beside the totals and did not add up.
Coleoptera read 1,550 against a true 1,613.

**244 had no `taxonomic_sort_key`**, and the tree filters `WHERE
taxonomic_sort_key IS NOT NULL`. Every specimen added since March, including all
35 then sexed.

The cause ran two layers deep:

1. `AddSpecimenDialog.get_specimen_data()` copied four fields off the selected
   species and never computed the sort key.
2. When patched to compute it, **the next specimen still came out without one**.
   `SpecimenRepository`'s `create()`, `update()` and `create_many()` whitelists
   had never included `taxonomic_sort_key` or `superfamily`, and dropped them
   silently. This is the true root cause, older than March.

The key is `INSECT_ORDER_POSITION[order] × 1,000,000 + uksi.taxa.sort_code` —
measured against 2,323 of 2,324 existing specimens rather than assumed, since
UKSI holds both `sort_code` and `sort_order` and neither matched directly. The
one exception, *Tillus elongatus*, carried a key from the 99 fallback — the same
March fault caught mid-failure.

**94 more were lost** to `subfamily` stored as NULL or `''` for the same species.
The query grouped them apart, and `build_tree` did `d[species] = count` — an
assignment — so the second row overwrote the first. 81 species affected.

All backfilled; the dialog and all three repository whitelists fixed. Proven by
saving a real specimen and reading the row back, and by editing one across
orders (key prefix 19 → 23). A batch of 184 added afterwards all carried keys.

### The record detail dialog hid most of a specimen
*Fixed 13 September 2026.* For a specimen it showed date, grid reference,
location and vice-county — and nothing else. Sex, collector, determiner and all
four curatorial fields went undisplayed. **Collector and determiner are recorded
on every one of the 2,568 specimens held at the time**, and had never been shown.

### The jurisdiction patch never applied
*Fixed 26 September 2026.* Written in early September, run, reported as done — and
refused, because `site_analysis_view.py` did not import `QComboBox`. It wrote
nothing, correctly. The service half had applied, so the two were out of step,
harmlessly: every assessment ran under the England default. Found only by
opening Examen and looking for the header. A process fault, not a code one —
see `05_Rules.md`.

### Single machine, no off-site copy
*Closed 26 September 2026.* `D:\BiologicalSoftware_Offsite`, 3.8 GB, 1,249 files,
zero failures. **Verified** by running `integrity_check` against the copied
`observatum.db` and counting specimens — the same standard that closed the
restore test in September.

### Generated prose had stray punctuation
*Fixed 26 September 2026.* Clauses were joined with `". "`, turning "across 4
visits" into a sentence of its own and doubling the final full stop. The card
beside it read "6.2% of Pantheon species" for a figure out of total species
recorded.

### DD and NT inflated 200 derived SQS scores
*Fixed 6 September 2026.*

`shared/sqs_derivation.py` treated **Data Deficient** as conferring Nationally
Rare status, and gave **Near Threatened** its own score of 2. Both were
documented in the module as *"not in the published lexicon, but Pantheon's
practice"*.

Neither is Pantheon's practice. Measured: **no species in `pantheon.db` scores
2** — 11,311 scores across 0, 1, 4, 8, 16, 32 only. And Pantheon's
scoring-systems page sets out five criteria in which DD and NT appear solely as
things a rare or scarce species *may also be*:

> "Nationally Scarce species that do not qualify under any of the other criteria.
> They may be classed as IUCN Least Concern, **Near Threatened**, or **Data
> Deficient**, Not Evaluated, or Not Assessed."

The score is driven by **rarity**, and by **threat only from Vulnerable upwards**.

| Case | Was | Now | Species |
|---|---:|---:|---:|
| NT alone | 2 | 1 | 40 |
| DD alone | 8 | 1 | 156 |
| DD + Nationally Scarce | 8 | 4 | 4 |
| DD + Nationally Rare | 8 | 8 | 23 (already correct) |

**200 species corrected, every one downward.** The DD-plus-scarce case was an
error inside the group assumed correct: DD forced `is_rare`, pushing scarce
species into the rare tier.

**The module's own docstrings were right and the code had drifted from them.**

**Judgement reversed deliberately.** `35_SQS_Stored_vs_Derived.md` recorded
"DD → rare" as a considered reading — Data Deficient means reviewed but
unassessable, not common, so treating it as potentially rare is a defensible
precaution. It is not Pantheon's rule, and the purpose of the derived score is
comparability with published SQIs.

### The priority collapse — 2,303 conservation facts lost
*Fixed 5 September 2026.*

`build_codex_db.py` collapses designations with `key = (track, detail or "")`.
All five priority jurisdictions mapped to `status_detail = None`, so they
competed for **one slot per species** and four were discarded by row order.

| Jurisdiction | True | Was stored |
|---|---:|---:|
| UK BAP | 1,150 | 142 |
| Scottish Biodiversity List | 2,088 | 1,537 |
| Env (Wales) Act S7 | 568 | 80 |
| NERC S.41 England | 943 | 687 |
| NI Priority Species | 482 | 482 |

The table was *built* to hold one row per jurisdiction — the primary key is
`(tvk, status_track, status_detail)`. `legal_protection` was implemented
correctly and `priority` was not. `CodexRepository` needed no change: it was
starved of data, not written wrongly.

Key species counts did not change — every species kept at least one priority row.
The damage was confined to *which* jurisdictions were reported.

### Collapse ties resolved by row order
*Fixed 5 September 2026.*

All modern Red List codes score 100 in `ABBR_PRIORITY`, so ties were common and
broken by whichever row came back first. `date_designated` was carried in the
tuple and never consulted. Twelve contests of 34 resolved wrongly — eleven
vascular plants where a 2014 England list said EX/EW and the 2021 GB list said
RE.

The twelfth shaped the fix. *Cercyon nigriceps* is stored `Nb` (Hyman 1992)
against a 1994 review saying the generic `Notable`; plain "most recent wins"
would have replaced a specific value with a vaguer one, overriding a deliberate
precedence rule.

**Rule: precedence first, date only as a tiebreak.**

### The TVK bridge never consulted `uksi.synonyms`
*Fixed 5 September 2026.*

3,068 of 14,229 Pantheon species matched neither the direct-TVK nor the name pass
and were dropped. **3,000 of them resolve through the synonyms table** — ordinary
post-2017 taxonomy: *Aedes* → *Ochlerotatus*, *Achaearanea* → *Parasteatoda*.
Bridge 11,161 → 14,161; unmatched down to 68.

Of the 1,847 that landed on a species another taxon already claimed, only 89 held
ecology nothing else could reach and 85 a higher SQS — most were spelling
corrections recording the same animal twice. They are now bridged, with ecology
unioned and **the incumbent's SQS kept**.

*A first attempt kept the highest score instead. That inflated* Sympetrum
striolatum *— Common Darter, one of the commonest British dragonflies — from 1 to
4, by inheriting the score of the Highland Darter form sunk into it. Corrected
the same day.*

### `PantheonRepository` never used the bridge
*Fixed 5 September 2026.*

Every ecology lookup passed **current UKSI TVKs** to a database keyed on
**Pantheon's 2017 TVKs**. For the 8,648 directly matched species that worked; for
the **3,666 resolved by name or synonym it silently returned nothing** — of 400
sampled, zero were found in `pantheon.habitats`.

Visible symptom: species carrying an SQS but no biotope and no habitat in the
Glory Park appendix. Less visible: habitat and SAT SQIs, biotope breakdowns and
the dominant-biotopes line were computed over the directly matched species only,
in every assessment the tool had produced.

`PantheonRepository` is now bridge-aware and every caller is fixed at once.

### The Conservation tab was inventing Section 41
*Fixed 5 September 2026. The worst find of the year.*

`_parse_status` reverse-engineered status codes from a display string. For a
priority species that string is the literal `"Priority"`, which matches no token,
so it fell through to a tier fallback that stamped **S41** on all of them.

Glory Park, in Northamptonshire, reported "Section 41: 4". Its four priority
species are on the Scottish Biodiversity List and the NI Priority Species List;
**none is on Section 41.**

**Every other fault found this year lost or mis-chose facts. This one
manufactured them**, and it is the only one that could have put a false statement
in a client report.

### The Species Database view had been blank since April
*Fixed 5 September 2026.*

`_display_codex_status` read the pre-April 8-track attribute names. All but one
returned `""` and were skipped silently, so the panel showed **nothing for any
species**. `legal_protection` does exist and is a **list** — truthy, reaching
`QLabel(val)` and raising `TypeError`. Blank or crashing for five months; found
only because a legally protected species was selected.

### The habitat tree was a cross-product
*Fixed 5 September 2026.*

`_load_biotope_habitat_mapping` queried every biotope/habitat pair in the whole
of `pantheon.db`, then filled each row with the **site-wide** count. Glory Park
showed "coastal" holding one species with "short sward & bare ground: 41" beneath
it, and every habitat under every biotope with the same SQI repeated.

The analysis service now computes real pairs from the sample. Unreliable SQI
values are withheld and the scoring count shown instead — "SQI 200*" on three
species invites misreading in a report.

### Key species were not jurisdiction-aware
*Fixed 5 September 2026.* See `02_Current_State.md` §4 for the reasoning and the
resulting figures.

### Feeding guild counts split by casing
*Fixed 5 September 2026.* `pantheon.db` stores four guild values in two casings.
Glory Park read `predator (37)` and `Predator (4)`; larval predators are 41.
Habitats, biotopes and SATs were checked and have no case variants.

### Gap-filled SQS computed by the wrong rule
*Fixed 5 September 2026.* `seed_codex.SQS_DEFAULTS` scores RDB3 at 16 "per Fowles
original SQI" — a different index — and takes max-of-pairs where the published
rule is a function of rarity *and* threat together. **525 of 816 (64%) disagreed
with the rule.** Derived scores are no longer stored; `CodexRepository` computes
them on demand from `shared/sqs_derivation.py`, so `sqs_scores` now holds only
what Pantheon published.

### The appendix labelled every priority listing "S41/BAP"
*Fixed 5 September 2026.* `display_status` used a label predating the 11-track
scheme, so the exported appendix printed "S41/BAP (2)" against species with no
English listing at all. Not invented, but a client's ecologist would read it as
Section 41. Now names the jurisdiction.

### Unsafe database copies throughout
*Fixed 2–4 September 2026.* Three mechanisms copied a WAL-mode `observatum.db`
with `shutil.copy2` while it was open, while `DatabaseManager.backup_main()` did
it correctly and **had no callers at all**.

### The Restore button had never worked
*Fixed 4 September 2026.* `self.db_manager.main_db_path + ".pre_restore"` —
`Path + str` raises `TypeError`, so it failed before touching anything. Replaced
with `scripts/restore_database.py`, which runs with the app closed and verifies
before and after.

### The common-name filter excluded 38% of names
*Fixed 27 August 2026.* A GLOB class ending `...ŵŷwy`; the bare ASCII `w` and `y`
excluded **7,997 of 20,897** common names instead of the 22 accented ones
intended. The filter was then found obsolete entirely.

### Pre-live snapshots reached 3.9 GB
*Fixed 2 September 2026.* 35 files at 114 MB each, inside OneDrive, no pruning.
Retired in favour of the before-commit backup.

### Obsolete databases in `data/`
*Cleared 4 September 2026.* 568 MB, including a July dev copy that
`python -m DataEntry` would have opened by default — a standalone launch would
have written into a two-month-old database.

### Import wizard doubled every warning
*Fixed 2 September 2026.* The insert path mutated `row.import_notes`, then
`_combine_import_notes` read it back and appended the same warning again. 175
existing rows retain doubled notes; cosmetic.

### Earlier, in brief
`reset_database.py` given the profile provenance columns (26 Sep) · a
superseded diagnostic and a drifted duplicate of `sqs_derivation.py` deleted
(26 Sep) · Data Entry readout card widened when the specimen pill clipped
(13 Sep) · Codex → Pantheon build order documented · `shared/` extracted so Examen no longer
depends on Observatum's `src/` · manual Codex entries made portable · `paths.py`
given a permanent banner · concurrent access handled with WAL and
`PRAGMA query_only` · Tabella generator relocated and its VBA written · six
broken reset launchers repaired · `MUNIA_DB` added to `paths.py` · species search
rewritten from `QCompleter` to a `QListWidget` popup · 2,454 specimen dates
migrated to ISO · observation edit lock narrowed to `irecord_id` · CSV backup
always offered · 9 UTF-8 BOMs stripped · toolbar mojibake repaired ·
`sorted(..., QMessageBox)` crash fixed · Delete Selected delivered · a hardcoded
date format replaced · staging given CSV coverage · header state guarded against
column changes.

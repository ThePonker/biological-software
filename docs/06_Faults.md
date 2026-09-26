# Faults

## Updated 26 September 2026
## Open faults carry an action. Closed ones are kept in brief, because knowing
## what has already gone wrong is how the rules in `05` were earned.

---

## Open

### F2. `stable` branch stale since June
The Data Entry build and four months of work sit on `main` only. The branching
discipline exists precisely so `stable` can be the field-season tool.
**Action:** merge once the staging jobs are committed and proven — backlog D3.

### F3. `uksi_extractor.py` missing
Referenced by `Observatum/src/models/uksi.py` and `scripts/__init__.py` but not
present anywhere — searched the whole C: drive, all of OneDrive, and git history.
Most likely lost in the March 2026 restructure, the same event that lost
`build_pantheon_db.py` and in which `paths.py` was itself accidentally deleted.

**Consequence:** the documented UKSI rebuild cannot be performed. Not urgent —
`uksi.db` works and both it and the 781 MB `UKSI.mdb` are backed up outside
OneDrive — but a rewrite is needed before NHM's next release.
**Action:** backlog D4. `uksi.db` is the specification.

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

### F10. Future-dated commercial record
One row dated `2026-07-10`. Typo, or a scheduled survey. **Action:** eyeball —
backlog D9. Open since July.

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
**Action:** backlog E16.

### F15. Two specimens without a TVK
*Phoracantha recurva* (id 1263) and *Oberea linearis* (id 1356). No TVK, so no
sort key, so invisible to the sidebar. **Action:** backlog A5.

### F16. `subfamily` stored inconsistently
NULL on some rows and `''` on others for the same species. The sidebar now
normalises; the data does not. **Action:** backlog A7.

---

## Closed — the ones worth remembering

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

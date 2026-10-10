# Codex

## The conservation authority
## Updated 6 October 2026 — supersedes `07_Codex_Design_Spec.md` (16 Apr 2026),
## whose schema and priority-track descriptions no longer match the build.

---

## 1. What it is

One authoritative database of conservation status for British species, answering
a single question reliably: **what conservation designations apply to this
species?**

No upstream source answers it alone. JNCC's spreadsheet is close to
comprehensive but updates irregularly. UKSI holds some status fields, partial and
stale. Published reviews are authoritative but scattered. Codex consolidates all
of them with provenance on every fact — which source, which review, what year,
which IUCN version.

**Codex is infrastructure, not a product.** Nobody uses it directly. Its measure
of success is whether Observatum, Examen and Tabella always get accurate data.

**Codex does not interpret.** It does not compute key-species flags or SQI. It
records what a species has been designated as, by whom, and when. Interpretation
belongs to the consumer — primarily Examen, which applies invertebrate-specific
scoring and jurisdiction rules on top.

---

## 2. Scope

**Conservation status: all British taxonomic groups.** Threat assessments, rarity
measures, legal protections, priority listings, specialist panels, regional red
lists.

**SQS: invertebrates only, by design.** A lichen does not get a Species Quality
Score because it has a Red List designation. The framework is ecologically
meaningful for invertebrate assemblage analysis and nowhere else.

Not owned by Codex: taxonomy (`uksi.db`), ecology (`pantheon.db`), user
observations (`observatum.db`), and all interpretation (`shared/` services).

---

## 3. The eleven tracks

A **track** is a type of conservation statement. A species can hold entries in
several simultaneously.

### Threat

| Track | Values |
|---|---|
| `threat_iucn_2001` | CR, EN, VU, NT, LC, DD, NE, NA, RE, EX, EW, WL. Bird entries split breeding / non-breeding via `status_detail` |
| `threat_iucn_legacy` | RDB1, RDB2, RDB3, RDBK, and 1994-IUCN equivalents |
| `threat_global_iucn` | Global assessment, not GB-specific |

### Rarity

| Track | Values |
|---|---|
| `rarity_modern` | NR (≤15 hectads), NS (16–100). Marine variants via `status_detail` |
| `rarity_legacy` | Na, Nb, Notable |

### Specialist panels

| Track | Values |
|---|---|
| `bocc` | Birds of Conservation Concern — Red, Amber |
| `specialist_panel` | Spider Amber List; future panels here |

### Regional red lists

`red_list_england` and `red_list_wales`, CR through NA. Distinct from GB-wide
because a species can be VU in England and LC across GB. **No Scotland track** —
Scotland maintains no standalone national Red List.

### Legal protection

One track, value uniformly `"Protected"`, with the **instrument in
`status_detail`** — WACA schedules, Habitats Regs, NI Wildlife Order, Bern,
CITES, CMS, the Directives, OSPAR. A species holds one row per instrument.

### Priority

One track, with the **jurisdiction in both `status_value` and `status_detail`** —
NERC S.41 England, Env (Wales) Act S7, Scottish Biodiversity List, NI Priority
Species, UK BAP. A species holds one row per jurisdiction.

> The duplication is deliberate. `status_detail` is part of the primary key and
> part of the collapse key, so it must carry the jurisdiction; `status_value`
> keeps it too so that nothing reading only the value breaks. Before 5 September
> 2026 the detail was null and **2,303 facts were being discarded** — see
> `06_Faults.md`.

---

## 4. Schema, as built

```sql
designations (
    id, tvk, species_name, common_name, taxon_group, category,
    reporting_category, designation, designation_abbreviation,
    designation_description, source, source_description, date_designated,
    iucn_version, criteria_description, comments, origin
)

status_summary (
    tvk, status_track, status_value, status_detail, source,
    iucn_version, date_designated, origin,
    PRIMARY KEY (tvk, status_track, status_detail)     -- note the third column
)

sqs_scores (tvk PRIMARY KEY, sqs, source)              -- 'pantheon' or 'manual'
tvk_bridge (pantheon_tvk PRIMARY KEY, uksi_tvk, species_name, match_method)
manual_entries (... review_id)
reviews (id, review_name, ..., supersedes_id, notes, licence)
species_profiles (tvk, review_id NOT NULL DEFAULT 0, species_name, profile_text,
                  source, date_added, date_updated, added_by,
                  PRIMARY KEY (tvk, review_id))       -- one account per review
metadata · build_log
```

`status_summary`'s three-column primary key is what allows several legal
instruments and several priority jurisdictions per species.

`sqs_scores` holds **only what Pantheon published**. Gap-filled scores were
removed on 5 September; `CodexRepository` derives them on demand from
`shared/sqs_derivation.py`, and `get_stored_sqs_tvks()` tells the two apart so
every SQI can state its basis.

**Which Pantheon scores are imported.** A score is kept if its (bridged) TVK is an
invertebrate. Until 2 October "invertebrate" meant *holds a designation with
category 'Invertebrate'*, which excluded every common species: 4,085 scores
dropped, 4,026 of them wrongly. It now means that set **or** UKSI kingdom Animalia
outside Chordata (from `uksi.db`). Counts per build are in `02_Current_State.md`.

**Rebuilds preserve** `manual_entries`, `reviews` (**including `id`**, since
`manual_entries.review_id`, `supersedes_id` and `species_profiles.review_id` all
point at it) and `species_profiles` with their review link.

---

## 5. How `status_summary` is built

`designations` is raw. `status_summary` is the consuming view, one row per
`(tvk, track, detail)`. Where several designations compete for one slot:

```python
if (key not in best
        or (prio, date_d or "") > (best[key][6], best[key][4] or "")):
```

**Precedence first, date as tiebreak.** `ABBR_PRIORITY` encodes deliberate
judgements — `Notable-B` at 40 beats the generic `Notable` at 30, so a newer but
vaguer review cannot displace a specific one. Where precedence ties, as it does
across all modern Red List codes at 100, the later `date_designated` wins. An
undated designation sorts last and cannot displace a dated one.

---

## 6. The TVK bridge

`pantheon.db` is keyed on 2017 TVKs. The bridge maps them to current UKSI TVKs
(rebuilt 8 Oct 2026, fault F25):

| Pass | Method | 8 Oct |
|---|---|---:|
| 1 | Pantheon TVK already exists in `uksi.taxa` | 8,588 |
| 2 | **NAMES sheet by key**: `uksi.name_map` gives the current taxon for that Pantheon TVK; else the exact name | 5,618 |
| 3 | Name matches `uksi.synonyms` -- **single-target names only**; a name with several targets is reported, never guessed | 9 |
| — | Resolve by no route | 14 |

Pass 2 decides by key, so it also handles British misapplied names (Pantheon's
*Noctua janthina* → *N. janthe*). Exceptions, in `build_codex_db.py`: where NAMES
gives an aggregate or "a/b" concept and the Pantheon name is a current species, the
species is kept (records are species-level); a subspecies or form resolves to its
species; `BRIDGE_KEEP` holds four keys kept on the old bridge by judgement.
Rows from passes 2 and 3 are all labelled `'name'` -- `CodexRepository` reads only
that label. `scripts/_oneoff/f14_bridge_vs_namemap_20261008.py` compares the bridge
with NAMES; after the rebuild only the 37 deliberate exceptions differ.

**Some synonym matches land on a species another taxon already claimed** —
UKSI has merged two Pantheon taxa into one. Both are bridged; the merge happens
at read time.

**Merge rule: ecology unioned, incumbent's SQS kept.** The incumbent is the taxon
whose own TVK, else exact name, is the current species; every other taxon on that
species is a collider, however it was bridged (since 8 Oct -- before, merges found
by name escaped the rule and row order decided). Not the highest score — the sunk taxon usually carries
the higher one because it was a scarce segregate, so taking the maximum inflates
the merged species.

Odonata stored under **vernacular names** in Pantheon's scientific-name column
("Azure Damselfly") now resolve by key in pass 2. 14 remain unresolved, plus
*Sphaeriestes ater* (two synonym targets, no NAMES key).

---

## 7. Sources

| Source | Authority | Cadence | Role |
|---|---|---|---|
| **JNCC Conservation Designations** | Official consolidation | Irregular, ~annual | Primary. Rebuilds everything. Currently **9 June 2026** (`data/conservation-designations-20260609/`). OGL. |
| **Pantheon SQS** | Pantheon-authoritative | Frozen at 2017 v3.7.4 | Imports to `sqs_scores`, re-keyed via the bridge. OGL. |
| **Manual review imports** | Published literature | Per review | Gap-fills the 6–18 months before JNCC consolidates a new review |
| **UKSI** | NHM / NBN | 2–3 yearly | TVK authority. CC BY 4.0. Currently the **July 2025** *Simplified Copy* (NHM Data Portal). |
| **The TVK bridge** | Computed | Per rebuild | Connects Pantheon to current taxonomy |

JNCC's Master List: headers on row 2, data from row 3, TVK in the "Recommended
taxon version" column. Column 17 is "Criteria description" and carries the
qualifier behind a designation — currently imported to `designations` but not
surfaced.

---

## 8. Maintenance

### New JNCC spreadsheet

1. Back up `codex.db` to `reference/`
2. Download and extract to `data/conservation-designations-YYYYMMDD/`
3. Update `JNCC_DIR` in `paths.py`
4. `python scripts/build_codex_db.py`
5. `python scripts/seed_codex.py`
6. Spot-check a known species in Codex Manager
7. Commit the path change

**Preserved across a rebuild:** `manual_entries`, `reviews`, `species_profiles`.
**Rebuilt:** everything else. The script deletes and recreates the file, so
schema changes need no migration.

### Importing a published review

Reviews live in `data\reviews\<order_group_author_year>\` with `source\` (as
published, never edited) and `extracted\` (`review.csv`, `statuses.csv`,
`accounts.csv`). Extraction is per layout (spreadsheet column or PDF data
sheets) and verbatim-checked; **`scripts/load_review.py` is the one loader**:

- dry run by default, `--apply` to write; backup first; one transaction
- `review.csv` `tracks_assessed`: `threat,rarity` (default) | `threat` (Red List
  only; rarity untouched) | `accounts` (statuses already in Codex via JNCC)
- legacy tracks cleared for every species the review assessed (newest wins)
- rarity-only rows (e.g. provisional NS) clear the Red List track
- `--add-statuses` / `--add-accounts`: extend a review already loaded
- matching, `apply_status`, `key_tiers`, `backup` imported from
  `import_status_review.py`, so every review obeys the same rules

Record each review's licence; OGL accounts are quoted in reports, others are
internal reference. Codex Manager's Import Review tab writes the old way -- **do
not use it** (backlog F9).

### BRC provisional atlases (species accounts only)

The Biological Records Centre's provisional atlases (NORA, 1970s–2003) and two
later scheme atlases (soldierflies 2018; Cox's seed and leaf beetles 2007, Word
supplement) are loaded as **accounts-only reviews**: `tracks_assessed` =
`accounts`, an empty `statuses.csv`, nothing written to `status_summary`.
Folders: `data\reviews\<group>_brc_atlas_<year>\` (also `_ite_`, `_cox_`, `_bsbi_`).

- **Text is re-read from the page images** (tesseract, 400 dpi, black and
  white); the PDFs' own scanned text is too broken to use. Each account is
  compared with that scanned text as a second reading.
- **Scanning slips are corrected only where both readings agree**, or where an
  italic Latin slip ("Popiilts spp.") leads to exactly one UKSI name. Anything
  else is left as printed. `extracted\extraction_check.csv` lists every name
  match, every correction and every unconfirmed word, per account.
- **Names** resolve as for reviews (TVK, name, synonym), plus near-misses within
  the atlas's family/order; a synonym of an aggregate goes to the species it is
  named after (species wins). Two printed names that are now one species are
  kept as one account, each part headed "[As printed: …]".
- **Licence:** NERC copyright, free for personal research with citation;
  recorded as internal reference, so the Examen workbook cites the atlas rather
  than quoting it. Observatum shows the text in full.
- **Order:** accounts show newest first, so an atlas account sits under any
  later review's account for the same species.
- Load: `py -3.14 scripts\load_atlases.py` (dry run), then `--apply` -- one
  backup, then `load_review.py` on each atlas not yet in Codex.
- Extraction scripts: `scripts\_oneoff\atlas_extraction\` (need tesseract;
  run in Claude's workspace, kept as the record of how the text was made).

### Keeping every status the newest review's

JNCC's spreadsheet does not enforce it. After any review load or JNCC update run
`check_legacy_conflicts.py`, `check_newest_review.py`, `check_old_names.py`.
Corrections are manual entries with value `'none'` (status removed), naming the
review that superseded or withdrew the status -- they survive rebuilds (proven
4 Oct): `clear_stale_legacy.py [--all]`, `withdraw_statuses.py`,
`check_old_names.py --apply`, `clear_legacy_detail.py` (rows stored with a
status_detail). Withdrawals match exact names only, and clear only statuses
**older than the excluding review**; newer ones are reported as kept.
`restore_wrong_withdrawals.py` undoes any that hit a different species.

After a **JNCC** rebuild also run `restore_dropped_statuses.py`: JNCC's own update
can drop or re-key statuses with no newer review behind it (52 in June 2026).

Reviews missing from JNCC entirely can be loaded statuses-only from their tables
(`tracks_assessed` threat,rarity, no accounts) -- the 2019 macro-moth Red List,
checked against the review's own category totals.

### After a UKSI update

The Codex build translates every TVK it stores -- JNCC's, and the review
statuses, accounts and manual SQS it restores -- through `uksi.tvk_remap`
(then `name_map`) to the current taxon, and reports how many. Records and your
own profiles are remapped separately (`remap_record_tvks.py`). Full sequence in
`01_Architecture.md` §5.

Then the usual checks. Expect `clear_legacy_detail.py` / `clear_stale_legacy.py`
to find a few rows where translation joined a JNCC "pro parte" TVK to its current
species (6 Oct: 12 and 1). **`restore_dropped_statuses.py` compares old TVKs** and
will list statuses that merely moved to the current TVK as dropped (*Mycetoporus
baudueri*); check the current TVK before restoring anything (backlog D10).

*June 2026, before the remap tooling: 30 records across 3 TVKs, hand-resolved.
6 October 2026: 12 observations, 1 specimen, 1 own profile by script.*

---

## 9. Known gaps

**Review accounts** accumulate through review imports (35 reviews; count in
`02`); superseded accounts are kept so old reports stay reproducible. Your own
profiles live in `observatum.db`, not here.

**Research-only.** Pantheon's 72 "S41 research only" species are applied in both
modes, to the S41 and UK BAP entries, and never confer key status. 62 reach
current TVKs; 10 do not (backlog F5). Whether Welsh S7 carries the same
qualification is open (F6).

**1,519 designation rows reach no track.** Mostly deliberate. See `06_Faults.md`
F8.

**No mechanism for disputing JNCC data.** If Codex inherits an error there is no
local override short of a conflicting manual entry. Low priority; JNCC quality is
generally high and disputes can go to JNCC.

**Rebuild reproducibility is not proven.** Two order-dependencies have been found
and fixed. A build-twice-and-compare check would settle the rest — backlog D7.

**Pantheon's "unreliable status" flag is not in the database.** Published reports
use square brackets — `[Nationally Scarce (Nb)]` — to mark a status Pantheon's
specialists consider unreliable pending reassessment. A search of `pantheon.db`
finds **zero** bracketed values. The convention is rendered by the Pantheon
website, not stored. Nothing to implement; recorded so nobody hunts for it.

**Research-only classification confirmed correct.** Pantheon revised its
research-only list after 2020, moving Wall and Small Heath off it. `pantheon.db`
already distinguishes them, so the 72-species list needs no adjustment.

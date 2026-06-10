# Codex — Strategy and Design

**Date:** 16 April 2026
**Supersedes:** `07_Codex_Design_Spec.md` (22 March 2026)

---

## 1. Purpose

Codex is the single authoritative database of conservation status information for British species, used across the Biological Software suite and the forthcoming web-hosted Examen.

It exists to answer one question reliably and consistently: **"what conservation-related designations apply to this species?"**

That question has no good answer from any one upstream source. JNCC's Conservation Designations spreadsheet is close to comprehensive but updates irregularly. UKSI taxonomy holds some status fields but they're partial and not always current. Published species status reviews are authoritative but scattered across specialist journals and reports. Codex consolidates all of these into one place, with clear provenance on every fact — which source, which review, what year, which IUCN version used.

Codex also holds concise species profile text, drawn from published reviews, to provide users with descriptive context alongside status information.

Codex is **infrastructure**, not a product. Users don't interact with Codex directly. They use Observatum, which displays Codex data. They use Tabella workbooks, which embed Codex data. They use the web Examen, which queries Codex for analysis. Codex's measure of success is whether those downstream tools always get accurate, current, well-sourced conservation data — not whether anyone enjoys using Codex itself. The Codex Manager GUI exists only as a maintenance tool for the person keeping Codex current.

Codex does not interpret. It does not compute "key species" flags. It does not derive Species Quality Scores for non-invertebrate groups. It records what a species has been designated as, by whom, and when. Interpretation is the job of the consuming application — primarily Examen, which applies invertebrate-specific scoring and key-species logic on top of Codex data.

---

## 2. Scope

### What Codex owns

Codex owns **conservation status information across all British taxonomic groups**. That includes threat assessments (IUCN Red Lists), rarity measures (hectad-based NR/NS counts), legal protections (Wildlife and Countryside Act, Habitats Regulations, international conventions), biodiversity priority listings (Section 41, Scottish Biodiversity List, UK BAP), and specialist non-IUCN assessments (Birds of Conservation Concern, Spider Amber List).

Codex owns one derived product: **invertebrate Species Quality Scores** (SQS). Pantheon's SQS values are imported as read-only reference data. Codex additionally derives SQS values for invertebrate species with GB rarity or Red List status but no Pantheon score — the gap-fill pass. **SQS is invertebrate-scope only, by design.** A lichen does not get an SQS score just because it has a Red List designation; the SQS framework is ecologically meaningful for invertebrate assemblage analysis and nowhere else.

Codex also owns **species profile text** — one paragraph per species, drawn from imported review data, giving users a brief descriptive context (habitat, ecology, identification notes as authored by the review's taxonomists).

### What Codex does not own

| Domain | Owner | Notes |
|---|---|---|
| Taxonomy (names, TVKs, sort codes, hierarchy) | `uksi.db` | Codex stores TVKs but does not define them |
| Ecology (habitats, biotopes, SATs, guilds, associations) | `pantheon.db` | Pantheon and Codex are siblings, both consumed by Examen |
| User observations | `observatum.db` | Codex never sees user data |
| Frozen reports and assessments | Examen (web, per-user) | Codex provides reference data used at the moment of assessment |
| Key-species interpretation, SQI calculation, assemblage analysis | `shared/` analysis services | Examen product logic; Codex just supplies the raw status values |

The principle: **Codex is biodiversity-wide for conservation status, but invertebrate-focused for ecology-adjacent data.** Conservation facts apply to everything. SQS and anything structurally invertebrate (tier classification, SQI, ISIS assemblage thinking) only apply to invertebrates and are absent elsewhere. This is honest — Codex tells you what it knows, and doesn't manufacture data where the underlying theory doesn't support it.

### Codex in the Atrium ecosystem

Codex is read by the following apps:

- **Observatum** — species profile dialogs, stats dashboards (future integration), exports
- **Tabella** — workbook generator embeds Codex data into the .xlsm UKSI reference sheet; VBA macro looks up status columns at species-entry time
- **Codex Manager** — the only application that writes to Codex, via the review import workflow

And by the forthcoming:

- **Web Examen** — consumes Codex as a read-only reference when analysing species lists

Curator and Munia do not read Codex. The desktop Examen is being retired; see `11_Parallel_Development_Plan.md` for the reasoning and `_archive/Examen_desktop_*/` for the archived code.

---

## 3. Contents

Codex consists of seven working tables plus one logging table. All data in Codex is keyed by TVK (the taxon version key from UKSI). Every fact carries provenance — which source, which review, what date, which methodology version.

### The tables

| Table | Purpose | Rows (current) |
|---|---|---:|
| `designations` | Every designation fact, one row per species per designation, preserved as-found from JNCC or a manually imported review | 27,062 |
| `status_summary` | The single best current status per species per track. Computed from `designations` with precedence rules. This is what consuming applications query. | 21,112 |
| `sqs_scores` | Invertebrate Species Quality Scores — Pantheon's original scores plus Codex-derived scores for species Pantheon missed | 15,663 |
| `tvk_bridge` | Mapping from Pantheon's 2017-era TVKs to current UKSI TVKs, so we can re-key Pantheon's SQS data to live taxonomy | 11,161 |
| `manual_entries` | Facts added by manually importing published reviews not yet in the JNCC spreadsheet. Survives rebuilds. | 0 |
| `reviews` | Register of which species status reviews have been imported, with metadata (author, date, species count, track used) | 0 |
| `species_profiles` | One paragraph of descriptive text per species, sourced from reviews. Survives rebuilds. | 0 |
| `build_log` | Audit trail of each build: row counts, date, source file version | 1 |

The three empty tables (`manual_entries`, `reviews`, `species_profiles`) are populated by the Codex Manager's review-import workflow. They're empty right now because we just rebuilt with a clean baseline.

### Status tracks — the eleven-track design

A **track** is a type of conservation statement. Different tracks encode fundamentally different kinds of information. A species can have entries in multiple tracks simultaneously — they're not mutually exclusive.

Tracks group into five conceptual categories:

#### Threat assessments

Tell you *how close to extinction* a species is, according to IUCN's formal assessment methodology.

| Track | Values | Meaning |
|---|---|---|
| `threat_iucn_2001` | CR, EN, VU, NT, LC, DD, NE, NA, RE, EX, WL | Modern GB Red List using 2001 IUCN Regional Guidelines. `WL` = Waiting List (assessment pending). |
| `threat_iucn_legacy` | RDB1, RDB2, RDB3, RDBK, Rare, Endangered, Vulnerable, Insufficiently Known, Indeterminate, Extinct | Pre-2001 Red Data Book systems, from Shirt 1987, Falk 1991, Bratton 1991 era reviews |
| `threat_global_iucn` | LC, NT, VU, EN, CR, DD, EX | Global IUCN assessment, not GB-specific |

#### Rarity measures

Tell you *how geographically restricted* a species is. Not the same thing as threat — a species can be nationally rare but Least Concern (common where it occurs, just nowhere else).

| Track | Values | Meaning |
|---|---|---|
| `rarity_modern` | NR, NS | Modern hectad-based rarity. NR = ≤15 hectads, NS = 16-100 hectads, from IUCN-compatible reviews. |
| `rarity_legacy` | Na, Nb, Notable, NR_marine, NS_marine | Pre-2001 rarity systems (Falk 1991 Na/Nb, later "Notable"), plus marine-specific variants |

#### Specialist non-IUCN panels

Species-group communities that run their own red-listing processes outside the formal IUCN framework.

| Track | Values | Meaning |
|---|---|---|
| `bocc` | Red, Amber | Birds of Conservation Concern. A traffic-light system used by ornithologists. Green is omitted (not a concern flag). |
| `specialist_panel` | Spider Amber List (currently the only member) | Catches specialist-community listings that aren't IUCN-shaped. Future specialist panels can be added here. |

#### Legal protection

*"This species is legally protected somewhere, under something."* One track covering all instruments, with the specific law stored in `status_detail`.

| Track | Value | Meaning |
|---|---|---|
| `legal_protection` | "Protected" (uniform) with `status_detail` naming the instrument | WACA 1981 schedules, Protection of Badgers 1992, Habitats Regulations 2010, NI Wildlife Order 1985, NI Habitats Regs 1995, Bern Convention, EU Birds Directive, EU Habitats Directive, CMS (and sub-agreements AEWA/EUROBATS/ASCOBANS), CITES, OSPAR |

Storing the instrument in `status_detail` rather than as a separate track preserves the distinction (a species protected under WACA Schedule 5 Section 9.1 for killing/injuring is different from Schedule 8 for possession) without multiplying tracks into illegibility.

#### Priority listings

*"Some jurisdiction has identified this as a priority for conservation."* Again one track, with the jurisdiction in `status_detail`.

| Track | Value | Meaning |
|---|---|---|
| `priority` | "Priority" (uniform) with `status_detail` naming the jurisdiction | UK BAP, England NERC Section 41, Welsh Environment Act S7, Scottish Biodiversity List, Northern Ireland Priority Species |

#### Regional red lists

Formal, published red lists at country-within-GB level. Distinct from the GB-wide `threat_iucn_2001` track because a species can legitimately be VU in England but LC for GB as a whole.

| Track | Values | Meaning |
|---|---|---|
| `red_list_england` | CR, EN, VU, NT, LC, DD, NE, NA | England Vascular Plant Red List 2014; future England-specific red lists as they emerge. Follows 2001 IUCN methodology. |
| `red_list_wales` | CR, EN, VU, NT, LC, DD, NE, NA | Welsh Red List (2014, revised 2021 for vascular plants); will accept future Welsh red lists for other groups |

No `red_list_scotland` track. Scotland does not maintain a standalone national Red List — Scottish priorities are captured via the GB-wide `threat_iucn_2001` track and the Scottish Biodiversity List entry in `priority`.

### Schema — row structure

The `designations` table is the raw data. One row per species per designation.

```
designations
  tvk                       TEXT   UKSI taxon version key
  species_name              TEXT   Scientific name
  common_name               TEXT   Vernacular name
  taxon_group               TEXT   e.g. "insect - beetle (Coleoptera)"
  category                  TEXT   Broad category: Invertebrate, Bird, Mammal, Vascular plant, etc.
  reporting_category        TEXT   JNCC's grouping: "Red listing based on 2001 IUCN guidelines", etc.
  designation               TEXT   Full designation name as published
  designation_abbreviation  TEXT   Short code from JNCC
  designation_description   TEXT   Free-text description
  source                    TEXT   The review or instrument that produced this designation
  source_description        TEXT   Fuller citation
  date_designated           TEXT   When the designation was made
  iucn_version              TEXT   "2001", "1994", "pre 1994", or empty
  criteria_description      TEXT   IUCN criteria used (e.g. "A2c, B1ab")
  comments                  TEXT   Free-text notes
  origin                    TEXT   "jncc" or "manual"
```

The `status_summary` table is the consuming view. One row per species per track, computed from `designations` using precedence rules.

```
status_summary
  tvk                       TEXT   (primary key with status_track)
  status_track              TEXT   One of the 11 tracks
  status_value              TEXT   The categorical value (e.g. "VU", "NR")
  status_detail             TEXT   Additional specificity (e.g. "WACA Sch5 Sect9.1" for legal_protection)
  source                    TEXT   Which review produced this status
  iucn_version              TEXT   Methodology version, where applicable
  date_designated           TEXT   When the assessment was made
  origin                    TEXT   "jncc" or "manual"
```

The `sqs_scores` table carries invertebrate-only quality scores.

```
sqs_scores
  tvk      TEXT
  sqs      INTEGER     1, 2, 4, 8, 16, or 32
  source   TEXT        "pantheon" (imported from pantheon.db) or "derived" (gap-filled from status)
```

The `tvk_bridge` resolves Pantheon's 2017 taxonomy to UKSI's current one.

```
tvk_bridge
  pantheon_tvk    TEXT   Old TVK from Pantheon's schema
  uksi_tvk        TEXT   Current TVK from UKSI
  species_name    TEXT   For auditing
  match_method    TEXT   "direct" (both use same TVK) or "name" (name-based resolution)
```

The `manual_entries` table holds review imports.

```
manual_entries
  tvk             TEXT
  species_name    TEXT
  status_track    TEXT
  status_value    TEXT
  source_review   TEXT   The published review name
  date_added      TEXT
  added_by        TEXT
  notes           TEXT
```

The `reviews` table registers each imported review.

```
reviews
  id                INTEGER PRIMARY KEY
  review_name       TEXT    e.g. "GB Sawfly Red List"
  author            TEXT    e.g. "Musgrove"
  taxon_group       TEXT    e.g. "Hymenoptera: Symphyta"
  status_track      TEXT    Which track this review populates
  date_published    TEXT
  date_imported     TEXT
  source_file       TEXT    Path to the CSV used for import
  species_count     INTEGER
  supersedes_id     INTEGER References reviews.id if this review supersedes a previous one
  notes             TEXT
```

The `species_profiles` table holds one paragraph of descriptive text per species.

```
species_profiles
  tvk           TEXT PRIMARY KEY
  profile_text  TEXT    One paragraph, plain text
  source        TEXT    e.g. "Fox et al. 2022 — GB Butterfly Red List"
  date_added    TEXT
  date_updated  TEXT
  added_by      TEXT    "manual", "review-import", "user-contributed"
```

### Key species determination — invertebrates only

A key species flag is **not** stored in Codex. It's computed on demand by the analysis service consuming Codex data, and only applied to invertebrate species. The logic (to be implemented in the analysis service, currently in `shared/services/`):

An invertebrate species is a key species if it has **any** of:

- `rarity_modern` entry (NR or NS)
- `rarity_legacy` entry with value Na, Nb, Notable, or marine variant
- `threat_iucn_2001` entry with value CR, EN, VU, or NT (not LC, DD, NE, NA, WL)
- `threat_iucn_legacy` entry with value RDB1, RDB2, RDB3, or RDBK (not Insufficiently Known or Indeterminate — too weak)
- `legal_protection` entry of any kind
- `priority` entry of any kind

Non-invertebrate species are never classified as key species, because the key-species concept comes from Pantheon/ISIS assemblage analysis, which is invertebrate-only.

---

## 4. Data sources

Codex is assembled from five sources. Each has its own character, authority level, and update cadence.

### Source 1 — JNCC Conservation Designations spreadsheet

**Published by:** Joint Nature Conservation Committee
**Update cadence:** Irregular, roughly annual
**Licence:** Open Government Licence (free for commercial use with attribution)
**Current version used:** `conservation-designations-20231206.xlsx` (December 2023)
**Location:** `data/conservation-designations-20231206/Taxon-designations-20231206.xlsx`
**Download:** [JNCC Resource Hub](https://hub.jncc.gov.uk/assets/478f7160-967b-4366-acdf-8941fd33850b)

The spreadsheet's "Master List" sheet contains 27,761 rows across 14,395 species in all British taxonomic categories. It consolidates dozens of published reviews, legal instruments, and priority lists, each row bearing full provenance (source, date, IUCN version, criteria description).

This is Codex's primary source. The build script (`scripts/build_codex_db.py`) reads this file, applies a mapping from `designation_abbreviation` to `status_track` (via `DESIG_TO_TRACK`), and populates `designations` and `status_summary`. When JNCC releases a new spreadsheet, running the build script refreshes Codex completely from this source.

**What it's good for:** up-to-date IUCN-based assessments, legal protection listings, priority lists, international conventions, regional red lists. Near-universal coverage for all but the most recently published reviews.

**What it's not good for:** it lags real publication. A review published in March 2025 won't appear in JNCC's spreadsheet until they issue their next consolidation — potentially 6–18 months later. For the gap, we use source 3 (manual reviews).

### Source 2 — Pantheon Species Quality Scores

**Published by:** Natural England / CEH (via NERC EIDC)
**Update cadence:** Effectively frozen — last version was v3.7.4 in 2017
**Licence:** Open Government Licence
**Location:** `data/pantheon.db`
**DOI:** 10.5285/2a353d2d-c1b9-4bf7-8702-9e78910844bc

Pantheon is a separate database in its own right — see `data/pantheon.db` and the broader discussion in `06_Software_Suite_Overview.md`. Codex consumes **only** the `sqs_scores` table from Pantheon (11,311 invertebrate species). The rest of Pantheon (biotopes, habitats, SATs, guilds, fidelity, associations) stays in `pantheon.db` and is consumed directly by Examen, not by Codex.

The SQS import is done during Codex build. Pantheon's 2017-era TVKs are re-keyed to current UKSI TVKs via the TVK bridge (source 4), because Pantheon's taxonomy is stale.

**Why the data is invertebrate-only:** Pantheon was built for invertebrate assemblage analysis. The scoring system and underlying datasets cover insects, spiders, molluscs, crustaceans, etc. It does not cover plants, birds, mammals, or fungi. This is the reason Codex's SQS coverage is invertebrate-only.

### Source 3 — Manually imported species status reviews

**Published by:** Specialist societies, individual taxonomists, statutory agencies
**Update cadence:** Ongoing, species-group-specific
**Licence:** Varies (most are freely citable; reproduction of full review data requires checking the source)
**Storage:** `manual_entries` and `reviews` tables in Codex, plus `species_profiles` when the review contains a profile-text column

Used when a published review covers species not yet incorporated into JNCC's spreadsheet. Typically a review lags JNCC by 6–18 months after publication before appearing in a JNCC consolidation.

Many modern reviews (Fox 2022 Butterflies, Musgrove 2022 Sawflies, etc.) include a column with a paragraph of ecological context per species — habitat, foodplants/prey, distribution notes. When present in the import CSV, this text populates `species_profiles` at the same time the conservation status lands in `manual_entries`. Both records share the review as their source.

Currently empty — we've wiped the previous manual imports to establish a clean baseline. Future imports will go via the Codex Manager's Import Review workflow (sections 5 and 6 below).

Examples of reviews that would typically be imported this way:
- Fox et al. 2022 (GB Butterfly Red List) — now in JNCC, may not need manual import next rebuild
- Musgrove 2022-2024 (GB Sawfly Red List and Rarity)
- Forthcoming macro-moth Red List (Fox 2019) — blocked on PDF data extraction
- Future Hymenoptera, Diptera, beetle family reviews

### Source 4 — UKSI taxonomy

**Published by:** Natural History Museum on behalf of NBN
**Update cadence:** Every 2-3 years
**Licence:** UKSI terms (commercial use worth confirming for web redistribution)
**Location:** `data/uksi.db` (~122,000 taxa)

UKSI provides the TVK authority. Codex TVKs must exist in UKSI, or the species cannot be resolved by consuming applications. When UKSI updates, Codex must be rebuilt so the TVK bridge regenerates against the new taxonomy.

UKSI also carries some conservation status columns (`red_list_status`, `rarity_status`, `legal_protection`, `bap_status`, `nnss_status`, `international_status`). Codex **does not use these** as primary sources — they're typically stale and incomplete. They're retained in UKSI only as fallback for Tabella's workbook generator when Codex has no entry for a non-invertebrate species.

### Source 5 — The TVK bridge

**Published by:** Codex itself (built by `build_codex_db.py`)
**Update cadence:** Regenerated whenever Codex is rebuilt
**Storage:** `tvk_bridge` table

Not an external source — it's a computed artefact. When Codex imports Pantheon's SQS data, it needs to translate Pantheon's 2017 TVKs to current UKSI TVKs. The bridge does this by two methods:

- **Direct match:** the Pantheon TVK is already the current UKSI TVK (8,648 species)
- **Name match:** the Pantheon TVK is obsolete, but its scientific name matches a current UKSI species (2,513 species)

Unresolved (3,068 species): Pantheon has data for these but neither method can map them to a current TVK. These get dropped during SQS import. Historically this has been a known gap — species like *Pemphredon lethifer* that had old Pantheon TVKs that don't resolve.

### Source summary

| Source | Authority | Cadence | Coverage | Codex role |
|---|---|---|---|---|
| JNCC spreadsheet | High — official consolidation | Irregular, roughly annual | All British taxa | Primary, rebuilds everything |
| Pantheon SQS | High — Pantheon-authoritative | Frozen (2017) | Invertebrate only | Imports to `sqs_scores` |
| Manual reviews | High — published literature | Per review | Per review scope | Gap-fills ahead of JNCC; provides profile text |
| UKSI | High — taxonomy authority | 2-3 yearly | All British taxa | Validation and TVK resolution |
| TVK bridge | Computed | Per rebuild | 8,648 direct + 2,513 name | Connects Pantheon TVKs to UKSI |

---

## 5. How Codex is updated

Codex has six distinct update triggers, each with a defined procedure. Some are occasional and large (new JNCC spreadsheet), others are frequent and small (adding one species profile). All are safe to run without specialist knowledge, provided backups are taken first.

### Trigger 1 — New JNCC Conservation Designations spreadsheet

**When:** JNCC publishes an updated Conservation Designations spreadsheet. Check the [JNCC Resource Hub](https://hub.jncc.gov.uk/resources/478f7160-967b-4366-acdf-8941fd33850b) periodically — roughly annual, though cadence has varied.

**Why it matters:** This is Codex's primary source. A new spreadsheet brings fresh IUCN assessments, newly-published reviews that have been consolidated, updated legal designations, and corrections. Everything downstream — Observatum's status columns, Tabella's workbook, Examen's analysis — improves when this is refreshed.

**Procedure:**

1. Back up `codex.db` to `_backups/codex_YYYYMMDD/`
2. Download the new ZIP from the JNCC hub
3. Extract to `data/conservation-designations-YYYYMMDD/`
4. Edit `paths.py`: update `JNCC_DIR` to the new folder
5. Run `python scripts/build_codex_db.py`
6. Run `python scripts/seed_codex.py`
7. Spot-check: open Codex Manager, search for a known species, confirm statuses look right
8. Commit the path change and note the update in the `build_log` table

**What's preserved:** `manual_entries`, `reviews`, `species_profiles`. These survive the rebuild because the build script clears only the tables it rebuilds from JNCC (`designations`, `status_summary`, `tvk_bridge`, `sqs_scores` where source=pantheon).

**What changes:** Everything derived from the spreadsheet — designations, status_summary, bridge mappings, imported SQS scores. Manually-imported reviews stay but may now be redundant if JNCC has caught up on the relevant taxon group; that's visible in the `reviews` table and can be pruned after review.

### Trigger 2 — Importing a newly-published species review

**When:** A published review covers species not yet in the JNCC spreadsheet — typically in the 6–18 month window between publication and JNCC incorporation.

**Why it matters:** Keeps Codex current ahead of JNCC. Examples include the Fox et al. 2019 macro-moth Red List, the Musgrove 2022-2024 sawfly reviews, and new Hymenoptera family reviews as they appear.

**Procedure (via Codex Manager GUI):**

1. Obtain the review data as a CSV. At minimum: `species_name`, `status_value`. Ideally also `tvk` and `profile_text`.
2. Launch Codex Manager: `python -m Codex` (or the tray icon)
3. Go to the Import Review tab
4. Browse to the CSV
5. Fill metadata: review name, author, publication date, taxon group, which `status_track` this review populates
6. Click Preview → check the UKSI match rate (aim for ≥95%)
7. Click Import → review is registered in `reviews`, statuses land in `manual_entries` and `status_summary`. If the CSV included a `profile_text` column, those paragraphs land in `species_profiles` at the same time.

**Procedure (via CLI):**

```
python scripts/import_codex_review.py review.csv \
    --name "GB Macro-moth Red List" \
    --author "Fox et al." \
    --date 2019-05-01 \
    --group Lepidoptera \
    --track threat_iucn_2001
```

**What's preserved:** Existing imports, JNCC data, profiles. Each review is additive — it adds rows to `manual_entries`, doesn't overwrite.

**Supersession:** If a new review supersedes an older one (e.g. a revised macro-moth Red List would supersede Fox 2019), the `supersedes_id` field in `reviews` links them. The consuming application uses the newest non-superseded review per track when resolving conflicts. Superseded data is retained for reproducibility of older reports.

### Trigger 3 — New UKSI release

**When:** NHM releases a new UKSI version. Roughly every 2–3 years.

**Why it matters:** UKSI is the taxonomy authority. Species names can split, merge, or be renamed. TVKs can be deprecated. Codex's TVKs must match UKSI's current state; otherwise consuming applications can't find species.

**Procedure:**

1. Back up `uksi.db` and `codex.db`
2. Obtain the new UKSI Access database (.mdb)
3. Run `python scripts/uksi_extractor_v5.py` to rebuild `uksi.db`
4. Rebuild Codex: `python scripts/build_codex_db.py` followed by `python scripts/seed_codex.py`. This regenerates the TVK bridge against new UKSI state and re-resolves Pantheon SQS scores
5. Audit: any review imports done before this update may now point to deprecated TVKs. The `reviews` import log includes a date — reviews older than the UKSI update should be spot-checked

**Known limitation:** Observatum's historic observations store TVKs at import time. If UKSI updates and a TVK becomes deprecated, Observatum observations point at the old TVK. There's no automated taxonomy refresh for observation data. This is noted in `23_Rebuild_Procedures.md` as a known gap.

### Trigger 4 — Pantheon update (rare)

**When:** Natural England releases a new NERC EIDC Pantheon dataset. Effectively never since 2017 v3.7.4, but possible.

**Why it matters:** Would bring updated SQS scores and potentially fill gaps Codex has currently filled with derived values.

**Procedure:**

1. Download from NERC EIDC
2. Rebuild `pantheon.db` using `build_pantheon_db.py` (location of this script needs verification — see issue 5 in `10_Infrastructure_Issues.md`)
3. Rebuild Codex — Pantheon's updated SQS scores are re-imported

### Trigger 5 — Editing a species profile

**When:** Correcting or extending an existing profile, or adding a profile for a species not covered by any imported review.

**Why it matters:** Most profiles arrive via review imports (Trigger 2). This trigger covers the cases where you want to hand-edit: fixing an error, adding context from a secondary source, or filling a gap for a species you care about that hasn't been reviewed.

**Procedure (via Codex Manager GUI):**

1. Launch Codex Manager
2. Go to the Species Profiles tab (to be added — see section 9)
3. Search for the species by name
4. Edit the existing profile or paste a new one
5. Set the source (e.g. "Falk 1991 Aculeata Review, p. 147")
6. Save — `added_by` is set to `manual`, `date_updated` is set to now

**What's preserved:** All other Codex data, including the profile's original import metadata if it came from a review import. Manual edits can be reverted by consulting the `source` field (if it still names a review, the original could be re-imported).

### Trigger 6 — Fixing a mapping error (`DESIG_TO_TRACK`)

**When:** A designation from the JNCC spreadsheet isn't being routed to a track correctly. The most visible symptom is a species showing in `designations` but missing from `status_summary`.

**Why it matters:** Codex's value depends on its routing being correct. A bird with BoCC Red status that doesn't appear in the `bocc` track is effectively invisible to consumers.

**Procedure:**

1. Identify the unrouted designation codes (query `designations` LEFT JOIN `status_summary`)
2. Edit `scripts/build_codex_db.py`: add the new entries to `DESIG_TO_TRACK` mapping the code to the correct track
3. Rebuild: `python scripts/build_codex_db.py` then `python scripts/seed_codex.py`
4. Verify the unrouted count has dropped

This is how we'll resolve the 74 unrouted codes identified in this session.

---

## 6. How Codex is consumed

Codex is read by five consuming applications: Observatum, Tabella's workbook generator, the Codex Manager, the web Examen (forthcoming), and — via `shared/services/pantheon_analysis_service.py` — the analysis logic that powers Examen's site assessments.

### Observatum

**What it reads:** Conservation status per species, for display in species profiles, the Insect Collection taxonomic sidebar, stats dashboards, and export columns. Will read species profile text once wired (currently pending).

**How it reads:** Via `shared/repositories/codex_repository.py`, the canonical access layer. Methods include `get_status_summary(tvk)`, `get_sqs(tvk)`, `is_key_species(tvk)`, `get_all_designations(tvk)`. Batch methods exist for scanning thousands of species efficiently (used by stats dashboards).

**What it writes to Codex:** Nothing. Observatum is read-only.

**Future wiring needed:** Three touchpoints haven't been migrated to `CodexRepository` yet:

1. `conservation_override.py` — likely still using its own logic, should delegate to Codex
2. `rare.py` — 40 conservation-related grep hits, some may duplicate Codex
3. Species profile display — currently derived from UKSI's partial columns; should read Codex's `species_profiles` when that table is populated

These are captured in the Parallel Development Plan as "Codex Display Integration" and are not blocking current work.

### Tabella — workbook generator

**What it reads:** Full Codex data for every species, to populate the UKSI reference sheet embedded in generated `.xlsm` workbooks.

**How it reads:** Direct SQL against `codex.db`, with UKSI fallback for non-invertebrates where Codex has no entry. After the invertebrate-filter removal and the 11-track redesign, Codex will cover many more non-invertebrates and the fallback becomes less necessary — but it's correctly retained for species JNCC has never designated at all (which UKSI might still have partial data for).

**What it writes to Codex:** Nothing. Tabella is read-only.

**Future behaviour:** The VBA macro inside the generated workbook performs species lookups against the embedded UKSI sheet. When the user types a species name, the macro auto-populates conservation columns (Red List, Rarity, S41, Legal, BAP, TVK, Common Name, Class, Order, Family). All of this data is Codex-sourced at generation time. Field-entered workbooks get imported back to Observatum which trusts those columns as authoritative.

### Codex Manager

**What it reads:** Everything, for display in its tabs (Reviews, Import Review, Species Search, Unresolved, Species Profiles).

**What it writes:** Review imports (via Import Review tab), species profile edits (via the Species Profiles tab — not yet built).

**How it reads/writes:** Direct SQL through the Codex Manager codebase, not via `shared/repositories/`. This is intentional — the Manager is Codex's maintenance tool, so it operates at a lower level than the read-only consumer repository.

### Examen analysis service (`shared/services/pantheon_analysis_service.py`)

**What it reads:** Conservation status per species, SQS scores, and the invertebrate key-species flag logic (computed on demand, not stored).

**How it reads:** Via `CodexRepository`, same pattern as Observatum.

**What it computes:** Invertebrate-scope metrics — SQI (Species Quality Index) per biotope/habitat/SAT, key species counts and percentages, tier classifications (Rare/Scarce/Priority). These are not stored in Codex; they're computed per-analysis from Codex + Pantheon + the species list being analysed.

**Codex Full vs. Pantheon Only mode:** The analysis service can run in either `CODEX_FULL` (using current Codex data, the default) or `PANTHEON_ONLY` (falling back to Pantheon's 2017 conservation data, for validation against what the Pantheon website would produce). This is a consumer-side concern and doesn't affect Codex itself.

### Apps that do NOT read Codex

**Curator** — reads `observatum.db` for specimens and `uksi.db` for taxonomy. Doesn't need conservation data in its current design (physical layout planning doesn't depend on status). Could be extended to display Codex-sourced status labels on printed labels if desired; that's a future enhancement.

**Munia** — capacity management, no species-level data.

**Atrium** — process launcher only, no database access.

---

## 7. How Codex serves the web Examen

The web Examen will be a browser-based species assessment tool, serving registered users who submit species lists and receive analysis reports. Codex is its primary reference source.

### The relationship

Codex lives in the local Atrium environment. When it's rebuilt or updated, the local `codex.db` changes. The hosted web Examen needs to reflect those changes in a controlled, versioned way.

The relationship is **one-way sync**: local Codex is authoritative, hosted Codex is a copy. The web Examen never writes back to Codex — any user-contributed profile edits or review imports happen locally first, then propagate.

### Proposed sync mechanism

**Option 1 — Read-only database file sync.** After a local Codex rebuild, upload `codex.db` to the hosted server. The web Examen loads it as a read-only SQLite file. Version stamp is based on the `build_log` table's most recent entry.

- **Pro:** Simple, atomic, no schema mismatch risk.
- **Pro:** Fast — SQLite reads are trivially performant for this data volume.
- **Con:** Requires a deployment step (upload + swap file). Not a zero-downtime operation, though the window is small.
- **Con:** Codex is now a file you ship, with all the discipline that implies.

**Option 2 — API-driven sync.** The hosted service pulls from a structured export (JSON or SQL dump) the local environment publishes on a known endpoint or file store.

- **Pro:** Self-updating. Deployments happen without manual file transfers.
- **Con:** More moving parts (endpoint, authentication, scheduling).
- **Con:** Version management is harder to reason about.

**Recommendation:** Option 1 for launch. It's boringly reliable. Option 2 can come later if manual deployment becomes a pain point.

### Versioning

Every user's analysis result stored in their account should record the Codex version used. This matters because:

- When Codex updates, existing analyses shouldn't silently change. If a user's report said "SQI = 178, based on Codex v2026-04-15", that's fact. A later rebuild saying "actually 182" would undermine trust.
- If a user disputes a status, they can see which version produced their result.
- The `build_log` table makes this trivial — each build records a timestamp; the web frontend reads the most recent entry on load and stamps it onto outputs.

### What the web Examen shows from Codex

For each species a user submits:

- Scientific name, common name, TVK, family, order (from `designations` + UKSI cross-reference)
- All relevant status track entries — CR/EN/VU/NT from `threat_iucn_2001`, NR/NS from `rarity_modern`, any legal protections with their specific instrument, any priority listings with their jurisdiction
- Source provenance — which review or instrument produced each status, what date, what IUCN version
- SQS score (invertebrates only; blank for other groups)
- Species profile paragraph, if present, with attribution to the review it came from

### Privacy and data flow

This is the important one. The agreed model is:

- The web Examen **does not store species lists** submitted for analysis
- It **does store** aggregated summary metrics per user (site name, survey year, species count, SQI, key species count, etc.) if the user chooses to save
- Codex itself is reference-only data, carries no user information, and is therefore outside GDPR scope

When a user submits a list:

1. Browser sends list to server
2. Server calls `CodexRepository` locally, computes metrics, returns results
3. Browser renders results, generates downloadable report (PDF/Excel)
4. If user clicks "Save summary": one row inserted into the user's assessment history — summary numbers only, no species names
5. Species list is discarded; not logged; not cached

Codex's role in this flow is purely lookup. It processes one species at a time via its repository methods and has no memory of anything.

### Donor value

Species profiles are one of the differentiators between web Examen and free Pantheon:

- **Free tier (anonymous):** Analyse any species list, download a report, see statuses on each species
- **Logged in (donor):** Everything above, plus save summary metrics to account, track averages across past assessments, see species profiles inline with status lookups

The profiles paragraph is the kind of content that makes the tool feel finished rather than merely functional. It's also content that accumulates over time — every new review imported, every new profile written, improves the tool without needing new infrastructure.

---

## 8. Known gaps and design debt

An honest catalogue of what's broken, incomplete, or imperfect. Each item has a severity — whether it affects current users, whether it affects planned web-Examen launch, or whether it's a longer-term concern.

### 8.1 Unrouted designation codes (moderate severity)

74 distinct JNCC designation codes aren't mapped to any Codex track. The effect: 490 species appear in the `designations` table but not in `status_summary`, so they're effectively invisible to consumers.

Most are bird-specific (BoCC codes, Birds Directive annexes, bird-specific IUCN Red List breeding/non-breeding variants), regional Red Lists for England and Wales, or international conventions (CITES, CMS, Bern, OSPAR). The 11-track redesign in section 3 addresses most of these — `bocc`, `red_list_england`, `red_list_wales`, and the consolidated `legal_protection` track together cover the bulk.

**Resolution:** Update `DESIG_TO_TRACK` in `scripts/build_codex_db.py` to add the new routing rules. Rebuild. Planned as immediate follow-up work after this document lands.

### 8.2 Non-invertebrate derived SQS scores (moderate severity)

4,352 SQS scores currently in `sqs_scores` with `source='derived'` include an unknown number of non-invertebrates — the `seed_codex.py` gap-fill ran without a taxonomic filter. The current estimate (from the investigation in this session) is roughly 3,000 non-invertebrate species got SQS scores they shouldn't have.

These scores are mathematically valid but ecologically meaningless. SQS was designed against invertebrate rarity categories; applying the same 1/2/4/8/16 scale to a lichen or a plant produces numbers that mean nothing in an assemblage-analysis context.

**Resolution:** Modify `seed_codex.py` to filter on `category = 'Invertebrate'` (once the `category` column is added — see 8.3) before deriving scores. A one-shot cleanup script can also remove the existing non-invert derived entries. This is a straightforward fix deferred until after the track redesign is in, because the derivation logic references track names that are about to change.

### 8.3 `category` column missing from `designations` table (low severity, easy fix)

The JNCC spreadsheet has a `Category` column — Invertebrate, Bird, Vascular plant, etc. The build script currently reads it to perform filtering but doesn't persist it. This means downstream code has to join back to `taxon_group` and classify via heuristic.

**Resolution:** Add `category` TEXT column to the `designations` table schema. Populate during build. The column costs almost nothing in storage and makes many consumer queries cleaner.

### 8.4 TVK bridge has 3,068 unresolved Pantheon TVKs

Pantheon's SQS data for 3,068 species can't be re-keyed to current UKSI because neither direct TVK match nor name match succeeds. These species are silently dropped during SQS import. Known examples include Pemphredon lethifer and a handful of other hymenopterans.

**Resolution:** Investigate case-by-case — may be genuine taxonomic changes (species synonymised, split, or removed), may be UKSI gaps. Not urgent but worth auditing once the track redesign is complete. For now, manually-imported reviews can re-provide SQS-relevant statuses for any affected species.

### 8.5 "Waiting List" entries in IUCN 2001 data (resolved by design)

76 species have IUCN 2001 methodology but category "Waiting List" — an administrative marker meaning "assessment pending". Previously these were silently routed into the `gb_red_list` track alongside real assessments.

**Resolution in design:** Kept as `threat_iucn_2001` with value `WL`, preserving the signal that an assessment has been started but isn't complete. Consumers can filter these out of reports while still seeing "pending review" status in species lookups.

### 8.6 Review supersession model untested (low severity)

The `reviews` table has a `supersedes_id` field for linking newer reviews to the older ones they replace. The logic for how consumers handle superseded data — showing only the newest, hiding the older, or showing both with a flag — isn't yet implemented in `CodexRepository`.

**Resolution:** Design and implement when the first supersession scenario arises. Most likely candidate: the macro-moth Red List (Fox 2019) will eventually supersede the older moth rarity listings when Fox's review is imported.

### 8.7 Observatum's historic observations carry stale TVKs

When UKSI updates and a TVK becomes deprecated, existing Observatum observations still point at the old TVK. There's no taxonomy refresh script. This is a known issue documented in `23_Rebuild_Procedures.md` (issue: "Taxonomy refresh").

**Resolution:** Build a refresh script that maps deprecated TVKs to their current equivalents in Observatum data. Not a Codex issue directly but affects how reliably Codex lookups work from Observatum's stored records. Parked.

### 8.8 Global Red List routing (low severity)

Global IUCN Red List entries (299 rows) are currently routed to the old `global_red_list` track. Under the 11-track scheme this becomes `threat_global_iucn`. The rename is cosmetic but should happen for consistency.

**Resolution:** Done as part of the same rebuild that updates `DESIG_TO_TRACK`.

### 8.9 Species profiles empty

The `species_profiles` table is defined and supported by the architecture, but holds zero rows. Profiles accumulate through review imports — any review CSV that includes a profile-text column populates profiles at the same time as statuses.

**Resolution:** This is intentional. Profile coverage grows naturally with review coverage. No separate curation pass needed. The Codex Manager's forthcoming Species Profiles tab will handle the rare case where manual editing is wanted (correcting errors or filling gaps for species no review has covered).

### 8.10 No mechanism for disputing or correcting JNCC data

If Codex inherits an error from JNCC's spreadsheet — a misidentified species, an incorrect status code — there's no way for the local Codex maintainer to override it while still consuming the rest of the JNCC data. An override would require editing the JNCC spreadsheet itself or adding a manual entry that happens to conflict.

**Resolution:** Low priority. JNCC data quality is generally high and disputes can be flagged to JNCC directly. If this becomes a real pain point, a `corrections` table similar to `manual_entries` but with explicit override semantics could be added.

---

## 9. Decisions we need to make

Open questions that weren't resolved in earlier sections. Each has options, my recommendation, and the reasoning. These should be resolved before the web Examen goes live, and ideally before the next Codex rebuild.

### 9.1 How aggressively should we fix the 74 unrouted codes?

**Options:**

**A. Full fix.** Add all new tracks (`red_list_england`, `red_list_wales`, `bocc`, `specialist_panel`, `threat_global_iucn`) and update `DESIG_TO_TRACK` to route every known code. Zero unrouted codes.

**B. Minimum viable.** Route only the bird codes (because they're the biggest group and most visible gap) and leave regional Red Lists + international conventions for later.

**C. Defer entirely.** Accept 490 species have missing statuses for now. Document the gap. Fix in a later pass.

**Recommendation:** A. The 11-track redesign in this document already anticipates all of this; leaving it half-implemented creates exactly the kind of inconsistency this document is meant to prevent. The work is mechanical — adding entries to a mapping dictionary — and a rebuild afterwards is standard procedure.

### 9.2 Should non-invertebrate derived SQS be removed now, or at the next rebuild?

**Options:**

**A. Write a one-shot cleanup script now.** Script runs once, deletes non-invert derived SQS, job done.

**B. Fix `seed_codex.py` and rebuild.** Modify the derivation logic to filter on `category = 'Invertebrate'`, then do a full rebuild. Non-invert SQS never gets created.

**C. Let it persist.** Live with the technical debt; consuming applications that care can filter client-side.

**Recommendation:** B. It's cleaner and prevents the problem from reoccurring. The rebuild to fix 9.1 is already coming; this piggy-backs on it with negligible extra work.

### 9.3 Profiles for species not covered by any imported review

The profile-import mechanism handles species covered by reviews cleanly. But what about species with conservation status only from JNCC (not a review we've imported) and no associated profile text?

**Options:**

**A. Leave them blank.** Profile coverage grows naturally with review coverage. No pressure to fabricate content.

**B. Manually write profiles for priority species.** You or a trusted contributor writes short profiles for the most commonly-looked-up species, regardless of review coverage.

**C. AI-extracted fallback.** Scrape descriptive text from other sources (Wikipedia, iRecord, BRC pages) and mark the profiles as `source=ai-extracted`.

**Recommendation:** A for now. Profile absence is honest. If profile coverage becomes a business-critical feature for the web Examen, B can fill the most important gaps with modest effort.

### 9.4 Observatum migration — how urgent?

Three Observatum touchpoints still don't use `CodexRepository`: `conservation_override.py`, `rare.py`, and the species profile display.

**Options:**

**A. Migrate before web Examen launches.** Treat it as launch-blocking.

**B. Migrate opportunistically.** Whenever Observatum is being worked on, fix one touchpoint. No hard deadline.

**C. Defer indefinitely.** Observatum works with its current logic; web Examen uses Codex; they don't need to match.

**Recommendation:** B. Option A adds pressure without corresponding benefit — Observatum users won't be affected by the web Examen launch. Option C is tempting but leaves Observatum silently diverging from Codex over time, which will eventually bite. Fixing one touchpoint per development session keeps the divergence bounded.

### 9.5 Should we expose Codex Manager to collaborators / donors / colleagues?

Currently it's a local desktop tool. If the web Examen grows into a collaborative product, there's a case for letting trusted contributors submit review imports or species profiles via a web interface.

**Options:**

**A. Keep Codex Manager desktop-only forever.** Simpler. Trust model is obvious (you're the only person editing).

**B. Web-enable Codex Manager for trusted contributors.** Adds significant complexity (authentication, role-based permissions, conflict resolution, audit trails).

**C. Build a contribution pipeline for profiles only.** Donors can submit profile text via the web; you approve or reject. Reviews and other schema-level data stay desktop-only.

**Recommendation:** A for now, reconsider C when profile coverage plateaus. Don't add product surface area you don't need. If and when profile contribution becomes a real bottleneck, the work to add a review queue is modest.

---

## 10. Schema appendix

The full SQL schema for Codex, for reference. Consult this when writing migration scripts, audit queries, or when the architecture of a specific table is unclear.

```sql
-- =========================================================
-- designations: raw JNCC + manual entries, one row per designation
-- =========================================================
CREATE TABLE designations (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    tvk                       TEXT NOT NULL,
    species_name              TEXT,
    common_name               TEXT,
    taxon_group               TEXT,
    category                  TEXT,
    reporting_category        TEXT NOT NULL,
    designation               TEXT,
    designation_abbreviation  TEXT,
    designation_description   TEXT,
    source                    TEXT,
    source_description        TEXT,
    date_designated           TEXT,
    iucn_version              TEXT,
    criteria_description      TEXT,
    comments                  TEXT,
    origin                    TEXT NOT NULL CHECK (origin IN ('jncc', 'manual'))
);

CREATE INDEX idx_designations_tvk ON designations(tvk);
CREATE INDEX idx_designations_reporting ON designations(reporting_category);
CREATE INDEX idx_designations_origin ON designations(origin);
CREATE INDEX idx_designations_category ON designations(category);

-- =========================================================
-- status_summary: computed best-status per species per track
-- =========================================================
CREATE TABLE status_summary (
    tvk             TEXT NOT NULL,
    status_track    TEXT NOT NULL,
    status_value    TEXT NOT NULL,
    status_detail   TEXT,
    source          TEXT,
    iucn_version    TEXT,
    date_designated TEXT,
    origin          TEXT,
    PRIMARY KEY (tvk, status_track)
);

CREATE INDEX idx_status_summary_track ON status_summary(status_track);

-- =========================================================
-- sqs_scores: invertebrate-only quality scores
-- =========================================================
CREATE TABLE sqs_scores (
    tvk     TEXT PRIMARY KEY,
    sqs     INTEGER NOT NULL CHECK (sqs IN (1, 2, 4, 8, 16, 32)),
    source  TEXT NOT NULL CHECK (source IN ('pantheon', 'derived', 'manual'))
);

-- =========================================================
-- tvk_bridge: maps 2017 Pantheon TVKs to current UKSI TVKs
-- =========================================================
CREATE TABLE tvk_bridge (
    pantheon_tvk  TEXT NOT NULL,
    uksi_tvk      TEXT NOT NULL,
    species_name  TEXT,
    match_method  TEXT NOT NULL CHECK (match_method IN ('direct', 'name')),
    PRIMARY KEY (pantheon_tvk)
);

CREATE INDEX idx_tvk_bridge_uksi ON tvk_bridge(uksi_tvk);

-- =========================================================
-- manual_entries: additions from reviews not yet in JNCC
-- =========================================================
CREATE TABLE manual_entries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    tvk            TEXT NOT NULL,
    species_name   TEXT,
    status_track   TEXT NOT NULL,
    status_value   TEXT NOT NULL,
    source_review  TEXT,
    date_added     TEXT NOT NULL,
    added_by       TEXT,
    notes          TEXT
);

CREATE INDEX idx_manual_entries_tvk ON manual_entries(tvk);
CREATE INDEX idx_manual_entries_track ON manual_entries(status_track);

-- =========================================================
-- reviews: register of imported species status reviews
-- =========================================================
CREATE TABLE reviews (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    review_name    TEXT NOT NULL,
    author         TEXT,
    taxon_group    TEXT,
    status_track   TEXT,
    date_published TEXT,
    date_imported  TEXT NOT NULL,
    source_file    TEXT,
    species_count  INTEGER,
    supersedes_id  INTEGER REFERENCES reviews(id),
    notes          TEXT
);

-- =========================================================
-- species_profiles: curated species description paragraphs
-- =========================================================
CREATE TABLE species_profiles (
    tvk           TEXT PRIMARY KEY,
    profile_text  TEXT NOT NULL,
    source        TEXT,
    date_added    TEXT NOT NULL,
    date_updated  TEXT,
    added_by      TEXT CHECK (added_by IN ('manual', 'review-import', 'user-contributed'))
);

-- =========================================================
-- build_log: audit trail per build
-- =========================================================
CREATE TABLE build_log (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    build_date            TEXT NOT NULL,
    jncc_source_file      TEXT,
    jncc_file_date        TEXT,
    designations_count    INTEGER,
    species_count         INTEGER,
    status_summary_count  INTEGER,
    sqs_scores_count      INTEGER,
    manual_entries_count  INTEGER,
    notes                 TEXT
);
```

---

## Changelog

**16 April 2026** — Major revision. Widened Codex scope from invertebrate-only to all British taxonomic groups for conservation status; retained invertebrate-only scope for SQS. Redesigned `status_track` scheme from 8 tracks to 11 across five conceptual categories (threat / rarity / specialist-panel / legal / priority), plus regional red list tracks for England and Wales. Added `species_profiles` table, populated primarily through review imports. Added `category` column to `designations`. Committed to Option 1 (file sync) for web Examen deployment. Archived previous design spec (22 March 2026).

**22 March 2026** — Original Codex v2 spec. Invertebrate-only scope. 8-track system. (Superseded.)

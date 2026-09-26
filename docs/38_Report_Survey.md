# What Published Invertebrate Reports Actually Contain

## A survey of practice — 6 September 2026
## Basis for the Examen report generator (backlog E2–E4)

---

## 1. What this is

Eleven published reports read in full, plus Wil's own four, to answer one question:
**across the profession, which outputs actually appear in a report, in what order, at
what level of detail, and how are the species accounts written?**

This is a survey of practice, not a validation exercise. Any given author may have
corrected a Pantheon oddity, excluded a species they didn't believe, or scoped the list
differently, and there is no way to tell from the outside. Reproducing someone's SQI
would prove little; failing to reproduce it would prove less.

### The sample

| Report | Author | Type |
|---|---|---|
| Intermodal Logistics Park North, 2025 | Richard Wilson | DCO, Pantheon |
| East Midlands Gateway 2, 2025 | Christopher Kirby-Lambert (FPCR) | DCO, **both frameworks** |
| Wye Valley Woodlands SAC, 2017 | **Keith Alexander** | Agency evidence, saproxylic |
| H2 Teesside, 2023 | Wilson / Musgrove / **Steven Falk** | DCO, compartmented |
| Tilbury Ashfields, 2022 | **Mark Telfer** | DCO, 1,222 species |
| Petworth Deer Park, 2020 | **Mark Telfer** | Buglife / NT, saproxylic |
| Sea Link Suffolk, 2025 | National Grid | DCO, **no Pantheon** |
| Barton Common, 2024 | Bryan Pinchen | Parish council, monitoring |
| Norwich to Tilbury SPI, 2025 | National Grid | DCO, SPI catch-all |
| New Forest Spider Surveys, 2019 | Richard Wilson | Agency, **single group** |
| NatureScot deadwood guidance, rev. 2026 | NatureScot | Habitat assessment method |

Telfer defined the Key Species framework the others cite; Alexander revised the IEC.
Both are in the sample in their own words.

---

## 2. The evaluation frameworks — and they disagree

### Telfer's Key Species rule, in his own words

Three parallel "versions" of British conservation status:

- **v1** Shirt (1987) RDB + Nationally Scarce, from JNCC reviews
- **v2** IUCN-based (Species Status series) — CR / EN / VU / NT / DD
- **v3** Simplified GB Rarity — Nationally Rare / Nationally Scarce

> **Key Species** = RDB and Nationally Scarce from v1; Threatened, Near Threatened and
> Data Deficient from v2; Nationally Rare or Nationally Scarce from v3.
>
> **Rare Key Species** = RDB from v1; Threatened and Data Deficient from v2; Nationally
> Rare from v3.

Wilson adds **Least Concern** to the Scarce tier — because a species can be LC on threat
and Nationally Scarce on rarity. Telfer's own status strings confirm it: `LC, NS`.
**Threat and rarity are independent axes and both are reported.** Codex already models
this correctly.

Wilson and Telfer both add SPI to the definition, and both exclude research-only.

### The threshold conventions differ

| Source | Rule |
|---|---|
| **Telfer (2017/2023)**, used by Wilson, H2, ILPN | ~10% Key Species **and** >1% Rare Key = potentially national significance |
| **Kirby-Lambert** | 5–10% with formal status = high quality; >10% = exceptional |

Two conventions in circulation. **Examen should report the percentages and let the
author cite the rule**, not bake one in.

Observed values for calibration: Tilbury Ashfields 16.0% / 3.2% (very high, national);
Petworth 15.3% (national); New Forest spiders 20% / 3%; H2 Teesside 5.1% / 1.0%;
EMG2 3.4%; ILPN 0.7% (district value only).

### Research-only is excluded, in every report that mentions it

Four of the eleven state it explicitly. Telfer's is the fullest:

> "the 'research only' SPI are all moths or butterflies… added to the UK Biodiversity
> Action Plan for research action only… Conservation action for these species is focused
> on further research rather than protection of individual sites."

**But the list has changed.** Telfer (2020) gives Small Heath as "NT, S41 (research
only)"; Telfer (2022) says *"Natural England's Pantheon application no longer treats
these two butterflies as 'research only'"* because Fox et al. (2022) assessed Wall as EN
and Small Heath as VU.

⚠️ **`pantheon.db` is frozen at 2017 and will carry the old classification.** Bicester's
S41 count depends on Small Heath and Wall. Needs checking.

The counter-example: the **Sea Link** desk study lists ~30 research-only moths as SPI
with no distinction at all — Garden Tiger, White Ermine, Cinnabar, Grey Dagger. In a
National Grid DCO submission.

---

## 3. The saproxylic framework

Not implemented in Examen at all (backlog E7). The sample gives its specification.

### SQI (Fowles et al. 1999)

- Scored against a standard list of **598 species** — *"excluding Pseudovadonia livida
  (Cerambycidae) which was included in the published list in error"*. Backlog says 605;
  correct it.
- Geometric scale, **1 point for common through to 32 for the rarest**. Observed: 0, 1,
  2, 4, 8, 16, 32.
- Status vocabulary is **informal**: common (1), local (2), very local (4), Nb (4),
  NS/N (8), NR/RDB3 (24), rarest (32). The list is the authority, not the designation.
- SQS ÷ scoring species × 100.
- **Requires 40+ qualifying species**, a complete list, and *"the same attention applied
  to recording common species as rare ones"*. An SQI from a rarity-chasing survey is
  invalid.
- Thresholds: >500 national, >590 international (Fowles).

**But Alexander disputes his own published threshold:**

> "Fowles et al. (1999) were unable to present data for more than 14 sites with an SQI of
> 500 or more and it does seem likely that the threshold is set much too high. Many sites
> which are nationally famous for their saproxylic beetles have SQI figures in the 300s
> and 400s."

His working rule: **300+ places a site among the best in Britain.** And a caveat worth
printing: *"Effectively the SQI is an index of rarity values rather than 'site quality'."*

**Thresholds must be configurable.**

### IEC (Alexander 2004)

- **180 saproxylic beetles** in three grades. Grade 1 = 3 points, Grade 2 = 2, Grade 3 = 1.
- Cumulative across all surveys of a site; **post-1950 records only**; rises with effort,
  so all values are minimums.
- Thresholds: >15 regional, >25 national, >80 international.

### They answer different questions

Petworth: SQI 569.2 (27th in Britain), IEC 87 (17th). Piercefield Park has the **highest
IEC** of the Wye Valley sites but is *"not significantly better"* on SQI. Alexander:
analysing for old growth *"results in the emergence of a very different picture."*

**Report both, and say they can disagree.**

### khepri.uk

Both the current scoring list (Fowles 2024, `khepri.uk/main`) and the **national site
rankings** (`khepri.uk/rankings/`, 212 sites) are online. That is where E7's data comes
from — not a PDF to transcribe. It is also how every saproxylic report positions its
site: *"the 27th highest British SQI"*, *"the third highest Sussex SQI"*.

---

## 4. Table formats worth copying

### Species quality metrics, with neighbours (ILPN Table 4)

Species-richness · Key Species · % Key · Priority Species · Stenotopic Taxa · %
Stenotopic · Scoring Taxa · SQI — one column per site, comparing against adjacent sites.
The cleanest summary in the sample.

### Metrics by compartment (H2 Table 7)

The same rows with a **Combined** column and one per sub-compartment. Note it includes
**"Analysed by Pantheon"** as an explicit row (1,102 of 1,251) — the coverage gap is
reported, not hidden. And the combined SQI (124) is **higher** than any individual
compartment (113–120): pooling is not averaging.

### SAT × compartment matrix (H2 Table 8)

SATs as rows, compartments as columns, each cell `34 (178%)` — count and Proportion to
Threshold together, with an FCT column. **Colour-coded: green where the threshold is
exceeded, amber where PtT ≥ 80%.** One table answering "which assemblages matter, and
where".

### The full Pantheon hierarchy in one table (EMG2 Table 4)

Broad biotope | Habitat | SAT | No. spp | %age | Spp. with national status | **Reported
condition**. The %age column is *"the proportion of the national fauna coded for the
biotope, habitat or assemblage"* — which confirms our "% National Pool" reading. And
Reported condition combines verdict with evidence: **"Favourable — 19 spp., threshold
11"**. That is backlog E10, in Pantheon's own phrasing.

### SQI per habitat with Key Species named (New Forest Table 13)

Broad biotope | Habitat | No. of species | **SQI** | No. of Key Species | the Key Species
listed with statuses. Better than any of the others — the habitat figure with its
evidence attached.

### Taxonomic summary (EMG2 Table 2)

Group | important sub-groups | Taxa | Spp. with status | % with status. Including **"All
saproxylic beetles — 42, 11, 26.2%"** as a row, which is how the report demonstrates
where the interest sits. Backlog E8's NCS-per-group item.

### Saproxylic species table (EMG2 Table 5)

Family | Species | Status | SQI score | IEC score, with footer rows for SQI, IEC, species
count and species with status.

### IEC contribution table (Petworth Table 7)

Grade | Number of species | Score | Contribution — with total. Auditable in four rows.

### Site comparison (Petworth Table 8, Wye Valley Table 1)

Site | County | No. of scoring species | SQI | IEC | Survey period. Note Petworth's
survey period spans **1988–2020** — SQI and IEC are cumulative across all surveys of a
site, a different model from Pantheon's per-sample analysis.

### Species appendix

Two conventions:

- **Wilson**: Class | Order | Family | Species | Vernacular | National Status | SQS |
  one column per site with a bullet — plus **footer rows computing Species recorded,
  Scoring Taxa, SQS and SQI per column**. The appendix computes the metrics.
- **Telfer**: Rare Key Species listed **first**, then Scarce Key Species, taxonomic order
  within each; compartment columns marked `1`.

### Species × visit matrix (Barton Common)

Species down, visit dates across, asterisks for presence, grouped by compartment then
taxonomic group. None of the large reports do this, and it suits a monitoring report.

### Desk study (Sea Link, Norwich to Tilbury)

Common name | Scientific name | Legally protected | SoPI | Other notable | Present on
Site | Present in wider ZoI | Latest record (distance, direction, year) | Closest record.

### Scoping-out table (Norwich to Tilbury)

Taxon Group | Species | **Reason**. Documents what was excluded and why. **That is the
right home for research-only moths and non-English priority listings** — it turns an
exclusion from something invisible into something defended.

---

## 5. Status conventions

**Comma-separated, both axes**: `VU, NR` · `LC, NS, S41` · `RDBK, S41` · `NT, NR` ·
`Nationally Scarce (Nb)`.

**Square brackets = unreliable or expected to change.** `[Nationally Scarce (Nb)]` is
Pantheon's own flag that a status has not been formally reassessed. H2 uses it for
statuses expected to be downgraded, with a note in the account explaining why.

**`p` prefix = provisional**: `pNationally Scarce`, `pNear Threatened`.

**Each status cited with its authority** (Sea Link): `Nationally Scarce, Notable (Hyman &
Parsons, 1992)` · `RDB-3 (Bantock, 2016)` · `Notable A (Telfer, 2016)`. **That is exactly
what Codex's `source` column holds**, and a strong argument for the appendix printing the
review alongside the code.

**Informal categories are used throughout**, not only in the saproxylic index: common,
local, **very local** — *"a much more subjective, but nevertheless useful, measure of
scarcity based on personal experience, published and unpublished records"*.

**"Well represented"** — Telfer's term for an assemblage with 15+ recorded species, the
threshold at which he presents an SQI at all. Cleaner than an asterisk.

**Status definitions annex.** Every report has one, covering all three versions. Examen
can generate it verbatim rather than the author pasting it each time.

---

## 6. Species accounts

One paragraph per Key Species, consistently in this order:

1. What it looks like — *"a small beetle with a leaden reflection"*, *"this striking
   species is arguably the best bumblebee mimic in Britain"*
2. Ecology and host associations
3. National distribution, with the review cited
4. **The site record** — compartment, month, method, count

Presented in taxonomic order, or in Telfer's case ordered by status with the rarest first.

**Authors state disagreement with a status in the account.** This is universal and it is
the model your backlog already specifies — no override field, say it in the text:

> *"in the author's opinion, it is likely that in a future assessment, the status will be
> downgraded to 'frequent'"* — Wilson
>
> *"It no longer deserves any conservation status."* — Wilson
>
> *"this has become a commoner species than when it was allocated RDBK status"* — Telfer
>
> *"it is doubtful whether it should still be regarded as a Nationally Scarce species"* —
> Telfer

Telfer goes further and questions the **indicator value** of species whose range has
expanded: *"Though considered to be a Grade 3 Indicator of Ecological Continuity by
Alexander (2004), it is expanding its range to the extent that it no longer has any value
as an indicator."*

---

## 7. Report structure — the common shape

Executive summary as bullets · Introduction and site description · Legislation and policy
· Methodology (desk study, field methods, **evaluation methodology stated explicitly**,
personnel with credentials) · Results (species totals, taxonomic summary, key species
with accounts, Pantheon analysis, saproxylic analysis where relevant) · Nature
conservation evaluation (individual species, habitat assemblages, taxonomic assemblages,
against SSSI and Local Wildlife Site guidelines) · Conclusion with a stated geographic
value · Mitigation · References · Annexes: status definitions, species lists,
compartment details, photographs.

**The value statement is always geographic and always hedged**: "no more than District
value" · "high local importance" · "national nature conservation value" · "very high
conservation importance in a national context" · "medium invertebrate interest… below a
site of local importance".

**Limitations are stated at length.** Weather, access, season, methods not used,
taxonomic gaps. EMG2 and ILPN both devote a page. This is not boilerplate — it is what
makes the figures defensible.

---

## 8. Things Examen cannot currently do

| | Source |
|---|---|
| Saproxylic SQI and IEC | E7 — data at khepri.uk |
| Compartment analysis | E6 — H2 and Tilbury give the format |
| Rare Key Species as a separate tier | New. Telfer's definition maps onto Codex tracks |
| Phenology table for target species | New Forest — when to survey for what |
| Comparison against neighbouring sites | Needs a site database; Fowles has one for saproxylic |
| Range-extension table | Needs NBN distribution data — out of scope |
| Recording-gap analysis by decade | Observatum could do this from its own data |
| Additional fidelity schemes | Boyce acid-mire A/B/C; Scott et al. peat-bog indicators |
| Habitat feature assessment | NatureScot deadwood checklist — see below |

### NatureScot deadwood habitat assessment

Not species-based at all. Record the presence and condition of eight components:
white/red-rotten heartwood · loose bark and moss · insect boring holes · standing and
fallen dead trunks, stumps and roots · rot holes with water or debris · fissured bark,
especially touching standing water · dead sections on live trees · sap runs · fungal
fruiting bodies. Plus clearings: size, change since last monitoring, scrub encroachment,
planting, grazing, nectar sources.

> "Habitat quality is more important than deadwood volume."

Photographs identified by **date, coordinates and compass bearing**. Observatum already
captures all three.

---

## 9. What this means for the generator

**Report the percentages, not a verdict.** Two threshold conventions are in circulation
and the author cites whichever they use.

**Every figure carries its evidence.** "Favourable — 19 spp., threshold 11", not
"Favourable". "SQI 569.2 based on 198 scoring species", not "SQI 569.2".

**Withhold what cannot be supported.** Below 15 species Pantheon's SQI is not presented;
below 40 the saproxylic SQI is not calculable. Say so rather than printing a number with
an asterisk.

**Print the source with the status.** Codex holds it; no other tool does.

**Exclusions are stated, not silent.** Research-only moths, non-English priority
listings, species Pantheon cannot analyse — each gets a row in a scoping-out table with a
reason.

**Thresholds are configurable.** The author of the IEC thinks the published SQI threshold
is wrong. That is not a detail to hard-code.

**The stamp**: Codex version · which SQS basis · which jurisdiction · whether years were
pooled · attribution for UKSI (CC BY 4.0), JNCC (OGL) and Pantheon (OGL) · and CIEEM's
**two-year survey validity**.

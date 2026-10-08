# Research notes — E16, F6, F8, E7

## 8 October 2026

Background research done between data-entry sessions. Each section gives the
answer, the evidence with its source, and the decision left for you. Where a
source could not be opened it says so; nothing here is inferred and presented
as found.

---

## 1. E16 — the SQI verdict bands

**Answer: there is still no source for 200 / 150 / 125, and Pantheon says
outright that none exists.**

- Pantheon, *Scoring systems* (pantheon.brc.ac.uk/content/scoring-systems):
  *"More work is required to refine these scores and produce benchmarks and site
  ranking."* No band values anywhere on the page.
- The nearest thing in print: Colin Plant Associates (2017), Lake Lothing ES App
  11G, §2.4.5 — *"Natural England suggest that an SQI score of 150 is the
  approximate threshold corresponding to a 'good' site which supports a
  regionally important invertebrate fauna."* Second-hand; no NE document cited.
  Nothing anywhere for 200 or 125.
- JNCC SSSI Selection Guidelines ch. 20 (Invertebrates, 2019) names the
  *saproxylic* SQI and IEC as indices whose scores can show national importance —
  not Pantheon's SQI. The 500 / 590 bands belong to that other index (§5 below).

**Telfer's percentages — partly sourced.** Telfer's *definitions* of Key and Rare
Key Species are confirmed word for word (Tilbury Ashfields 2023, §3.7.1, p.45 —
matches `workbook_export.telfer_tier`). He calls the percentage *"a useful
starting point for assessing the overall importance of a site"* (p.44). But in
the Telfer reports that could be read, **the "~10% Key / >1% Rare Key" numbers do
not appear as a stated threshold** — he describes values qualitatively (Petworth
15.3%: *"a very high percentage, indicating a site of national importance"*). The
numbers are attributed to Telfer by Wilson, H2 and ILPN (`38_Report_Survey.md`);
the Tilbury supplement (TR010032-005274) may hold the original wording but could
not be opened here.

**"Kirby-Lambert" (5–10% high, >10% exceptional)** has no traceable original. It
appears unattributed as *"a robust rule of thumb"* in consultants' reports, and
Natural England's own NECR624 and NECR628 (2026) say *"Sites where this exceeds
10% indicate exceptional quality."* — the most citable form of it.

**Decision for you.** Leaning was Telfer; the evidence now says:
1. Remove the SQI band sentence from the Overview — it has no source and Pantheon
   says benchmarks don't exist. *(Recommended.)*
2. Keep reporting % Key and % Rare Key with no verdict (as the workbook does).
3. The workbook's Summary notes currently say *"Telfer: close to 10% suggests
   potential national significance"* and *"Telfer: more than 1% …"*. Until the
   primary wording is found, either cite where you have seen it (e.g. Wilson's
   report citing Telfer 2017) or soften to "Telfer describes high percentages as
   indicating national importance (e.g. Petworth 15.3%)". Cite NECR624/628 for the
   >10% "exceptional" convention instead of "Kirby-Lambert".

If you have Tilbury DL7 Appendix 3.2 (or the 2017 Telfer report Wilson cites) on
file, one look would settle point 3.

### 1a. New: Pantheon's small-sample rule is "15 or less", not "fewer than 15"

Pantheon, same page: *"It is suggested that scores derived from **15 or less**
species should not be used."* The software uses `species_with_sqs >= 15` as
reliable (`SQIResult.calculate`, and `SQI_MIN_SPECIES = 15` in the workbook), so an
SQI from **exactly 15** scoring species is shown as reliable where Pantheon says
not to use it. Telfer paraphrases it as "fewer than 15", which is probably where
the code's reading came from.

No headline survey is affected (all have far more than 15 scoring species); it
bites on habitat and assemblage sub-SQIs with exactly 15. **Decision:** follow
Pantheon's words (≥16) — a two-line change in `pantheon_analysis_service.py` and
`workbook_export.py`, plus the tooltips' wording.

---

## 2. F6 — does Wales Section 7 carry "research only"?

**Answer: no, as far as could be verified.** Cinnabar (*Tyria jacobaeae*) is on the
Welsh list, with no research-only flag.

- The interim Section 7 list was *"derived from the original Section 42 list"*
  (Welsh Government, gov.wales/node/75773). The Section 42 list (Denbighshire
  copy) reads *"Tyria jacobaeae The cinnabar Teigr y benfelen"*; its only key is
  *"Wales only species; † original S74 species"* — no research-only marker.
- Swansea Council's Section 7 page lists Cinnabar, no note.
- The flag exists only in the UK BAP list and England's S41 (Butterfly
  Conservation: *"UK BAP: Priority species (Research only)"*; Essex Field Club:
  *"Section 41 Priority Species - research only"*).

**Gap:** the Welsh Government published a **new Section 7 spreadsheet** — first
published 20 March 2026, updated 11 May 2026 —
`gov.wales/sites/default/files/publications/2026-05/section-7-list-species-and-habitats-principal-importance-wales.xlsx`.
It couldn't be downloaded from here. It is worth having anyway: it came out only
weeks before the JNCC June 2026 designations Codex is built on, so JNCC's
Section 7 column may not include it yet, and Codex's Welsh list may be out of step. **Action for you:** download it into
`data\` (two minutes) and I'll compare it with Codex's Section 7 track and check
for any research-only column.

**Decision:** by the letter of the Welsh list, Cinnabar *is* a species of principal
importance in Wales, so the current behaviour (Key at a Welsh site) is correct.
The reports surveyed exclude research-only species, but all of them are English
sites under S41. Recommend: leave as is, and say so in the status definitions
sheet; revisit if the new spreadsheet has a qualifier.

---

## 3. F8 — NECR702 licence — **resolved**

From the PDF in `data\reviews\coleoptera_chrysomelidae_necr702_2026\source\`, page 2:

> *"This publication is published by Natural England under the Open Government
> Licence v3.0 for public sector information. … © Natural England 2026.
> Catalogue code: NECR702."* Author: **Steve A. Lane**.

`import_status_review.py` now takes `--licence` (stored on import) and
`--licence-only` (sets it on a review already imported, found by its
spreadsheet's file name). Until it is set, the workbook writes *"Not quoted
(licence)"* for every NECR702 account; once set, they are quoted and cited.
Run with **Observatum and Examen closed** (it writes codex.db; backup first, as
usual):

```
py -3.14 scripts\import_status_review.py "data\reviews\coleoptera_chrysomelidae_necr702_2026\source\NECR702_Chrysomelidae_2026.xlsx" --licence-only --licence "Open Government Licence v3.0"
```
then the same with `--apply`. Other reviews imported by this script may be in the
same state — worth a look at `SELECT review_name, licence FROM reviews`.

---

## 4. E7 — saproxylic SQI and IEC: what the software would need

### 4.1 The sources

| | Saproxylic Quality Index (SQI) | Index of Ecological Continuity (IEC) |
|---|---|---|
| Origin | Fowles, Alexander & Key (1999), *The Coleopterist* 8: 121–141 | Harding & Rose (1986); revised Alexander (2004), ENRR574; revised again Alexander (2024), *BJENH* 37: 33–45 |
| Online | khepri.uk (Fowles) — rankings, search, submit a list | Pantheon holds the 1986 and 2004 grades |
| List | 598 (Telfer 2020) / 596 or 605 (khepri — its two live pages disagree) | 180 species (2004) in grades 1–3 |
| Formula | SQS ÷ qualifying species recorded × 100 — common species count in the denominator | Σ grade scores: grade 1 = 3, grade 2 = 2, grade 3 = 1; records from 1950 on |
| Minimum | 40 qualifying species (Telfer 2020; khepri rankings). Denton & Chandler used 50 | — |
| Thresholds | >500 national, >590 international (Fowles et al. 1999). Alexander (2019, NRW 320): 500 "probably set too high"; ≥300 "amongst the best quality sites" | >15 regional, >25 national, >80 international (Alexander 2004; boundaries inclusive or not is ambiguous between ENRR574's text and table) |

**Scores.** khepri.uk now scores on IUCN status: *"CE, CR, EN & RE = 32; VU = 24;
DD = 2"*; NT that is also Nationally Rare = 24, otherwise 16; LC by original GB
distribution — Common 1, Local 2, others 4. The 1999 table (Common 1 / Local 2 /
Occasional 4 / Nb 8 / Na 16 / RDB 24–32) is **not confirmed** — needs the paper.

**Rankings.** khepri.uk/rankings: ~241 sites (Telfer counted 212 in 2020), columns
Site · Region · spp. · SQS · SQI · IEC · Survey period. New Forest tops it at
771.6 (2500 ÷ 324). No download, no date. Reports cite rank position ("the 27th
highest British SQI"), so the software would want a rank against a dated snapshot.

**Licence.** khepri.uk carries no licence, no terms, no contact address: treat as
all rights reserved. The 1999 list is © *The Coleopterist*; ENRR574 © English
Nature 2004. Pantheon's database (incl. its IEC columns) is OGL with the DOI
10.5285/2a353d2d-c1b9-4bf7-8702-9e78910844bc.

### 4.2 Design sketch

1. **Data, in codex.db, versioned.** `sap_list(scheme, tvk, name, score, basis)` and
   `iec_list(version, tvk, name, grade)`. `scheme` named on every output ("Fowles
   1999", "khepri IUCN 2020s"). Synonyms through the existing TVK bridge;
   exclusions (*Pseudovadonia/Anoplodera livida*) as data, not code.
2. **Score rules as a table**, not code — the IUCN mapping above, and the 1999
   mapping once checked. The khepri IUCN scheme can then be *derived* from Codex
   statuses, as `sqs_derivation` does for Pantheon — which avoids shipping khepri's
   own list at all.
3. **Configurable numbers:** minimum species (40), SQI thresholds (500 / 590,
   optional 300), IEC thresholds (15 / 25 / 80) and inclusivity, the 1950
   cut-off.
4. **Outputs:** SQS, qualifying species, SQI to one decimal, IEC with its grade
   breakdown (Telfer's "8 × 3 + 12 × 2 + 39 × 1 = 87"), and optionally rank against
   a dated khepri snapshot entered by hand.
5. **Licensing:** IEC grades from Pantheon (OGL) can ship. The SQI list should be
   derived from Codex statuses under the published rule, or imported by the user
   from their own copy — not shipped — until Adrian Fowles agrees otherwise. Fine
   for your own use either way; it matters only for the distributable copy.

**Still to obtain before building:** the 1999 paper's score table; Alexander 2024's
grade changes and any new thresholds; the Pantheon A211 / A212 favourable-condition
targets (A213 = 8).

### 4.3 Noticed in passing — your Cobham NNR report (2024)

The report (Kent Downs annex 7n) gives the combined IEC as **92** in §5.1.2 but **93**
in Table 4.4 and the summary, and attributes the >80 threshold to Fowles et al. 1999
in §5.1.2 but to Alexander 2004 in §4.4.4 (the latter is right). Worth knowing
when the Kent Deadwood figures become the E7 test case.

---

## Sources

- Pantheon — Scoring systems: https://pantheon.brc.ac.uk/content/scoring-systems
- Pantheon — Reported condition: https://pantheon.brc.ac.uk/node/418
- Colin Plant Associates (2017), Lake Lothing ES App 11G: https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010023-000333-6.3%20-%20ES%20Vol%203%20-%20App%2011G%20-%20Invertebrate%20Survey.pdf
- JNCC SSSI Guidelines ch. 20 (2019): https://data.jncc.gov.uk/data/747968a5-a8a7-4bd6-b12c-3329c3b5b6ca/SSSI-Guidelines-20-Invertebrates-2019.pdf
- Telfer (2023) Tilbury Ashfields: https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010032-005280-DL7%20-%20Appendix%203.1%20to%20Natural%20England's%20DL7%20response%20Invertebrate%20survey%20of%20Tilbury%20Ashfields%20in%202022%20-%20Mark%20G%20Telfer.pdf
- Telfer (2020) Petworth Deer Park: https://cdn.buglife.org.uk/2022/01/Saproxylic-invertebrate-survey-of-Petworth-Park-2021-01-27.pdf
- NECR624: https://publications.naturalengland.org.uk/publication/6358593262321664 · NECR628: https://publications.naturalengland.org.uk/publication/5457946035879936
- Welsh Government, Section 7: https://www.gov.wales/node/75773 · Section 42 list (Denbighshire): https://www.sirddinbych.gov.uk/en/documents/planning-and-building-regulations/planning/biodiversity-section-42-priority-species.pdf
- khepri.uk: https://khepri.uk/ · https://khepri.uk/rankings/
- Alexander (2004) ENRR574: https://publications.naturalengland.org.uk/file/133007 · Alexander (2011) NECR072: https://publications.naturalengland.org.uk/file/83002
- Alexander (2019) NRW Evidence Report 320: https://cdn.cyfoethnaturiol.cymru/688202/eng-report-320-saproxylic-invertebrate-survey-of-wye-valley-woodlands-sac-copy.pdf
- Pantheon database (EIDC, OGL): https://catalogue.ceh.ac.uk/id/2a353d2d-c1b9-4bf7-8702-9e78910844bc

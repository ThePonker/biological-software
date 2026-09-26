# Current Session Summary

## Date: 5 September 2026 (Session 32)
## Supersedes: 4 September 2026 version (Sessions 30–31)

---

## In one line

Codex was found to be losing, mis-choosing and hiding conservation facts; Examen was
found to be **inventing** one. All fixed and verified. Examen now runs, and Glory Park
reports the 8 key species Wil said it should — arrived at from the data, not by hand.

---

## How the session started

A question about the S41 "research only" moths — common, widespread species added to the
UK BAP on decline data rather than rarity, which Wil had been removing from key-species
counts by hand. Chasing where that distinction lived opened everything below.

It ended up answered from data already held: `pantheon.db` carries **72 species** under the
reporting category *"Section 41 Priority Species - research only"*, already mapped by
`CodexRepository._apply_pantheon_row`. Butterfly Conservation's published list has 71. No
new source needed.

---

## Part 1 — Codex

### The priority collapse (Infrastructure 56) ✅

`build_codex_db.py` collapses designations with `key = (track, detail or "")`. All five
priority jurisdictions mapped to `status_detail = None`, so they competed for **one slot per
species** and four were discarded — winner decided by row order.

**2,303 species-jurisdiction facts were missing.** UK BAP was at 12% of its true coverage.

| Jurisdiction | True | Was | Now |
|---|---:|---:|---:|
| UK BAP | 1,150 | 142 | 1,150 |
| Scottish Biodiversity List | 2,088 | 1,537 | 2,088 |
| Env (Wales) Act S7 | 568 | 80 | 568 |
| NERC S.41 England | 943 | 687 | 943 |
| NI Priority Species | 482 | 482 | 482 |

The table was *built* to hold one row per jurisdiction — the primary key is
`(tvk, status_track, status_detail)`. `legal_protection` was implemented correctly.
`priority` was designed the same way and implemented with the detail left null. **The same
rule, applied to one track and forgotten for the other, in the same dictionary.**

`CodexRepository` needed no change: `status.priority` was already a list. It had been
starved of data, not written wrongly.

**Key species counts did not change** — every species kept at least one priority row.
SQS unchanged. The damage was confined to which jurisdictions were reported.

### Collapse ties resolved by row order (Infrastructure 57) ✅

All modern Red List codes score 100 in `ABBR_PRIORITY`, so ties were common and broken by
whichever row the database returned first. `date_designated` was in the tuple and never
consulted.

Of 34 disagreeing contests, 12 resolved wrongly — 11 vascular plants where a 2014 England
list said EX/EW and the 2021 GB list said **RE**.

The 12th shaped the fix. *Cercyon nigriceps* is stored `Nb` (Hyman 1992) against a 1994
review saying the generic `Notable`; plain "most recent wins" would have replaced a specific
value with a vaguer one, overriding a deliberate precedence rule. So: **precedence first,
date only as a tiebreak.** After rebuild, 33 of 34 resolve to the most recent and *Cercyon*
correctly does not move.

### The TVK bridge never consulted `uksi.synonyms` (Infrastructure 58) ✅ partly

3,068 of 14,229 Pantheon species matched neither the direct-TVK nor the name pass and were
dropped — their SQS and ecology never reaching Codex. The bridge never tried the synonyms
table, which exists precisely for this.

**3,000 of the 3,068 (98%) resolve through it.** Ordinary post-2017 taxonomy: *Aedes* →
*Ochlerotatus*, *Achaearanea* → *Parasteatoda*, *Acronicta megacephala* → *Subacronicta*.

A third pass was added, accepting a synonym match **only where no other Pantheon species has
already claimed that UKSI TVK**:

| | Before | After |
|---|---:|---:|
| Bridge total | 11,161 | 12,314 |
| Synonym-resolved | — | 1,153 |
| Unmatched | 3,068 | 1,915 |
| Pantheon SQS imported | 4,971 | 5,522 |
| Gap-filled SQS | 1,112 | 816 |
| Total SQS | 6,083 | 6,338 |

The gap-fill *dropping* is the good news: 296 species that previously had a derived guess
now carry their real Pantheon score. *Larinus carlinae* went from `SQS:1(derived)` to
`SQS:4(pantheon)`.

**Still open — the 1,847 collisions (backlog J2).** Characterised:

| Kind | Count | Treatment |
|---|---:|---|
| Spelling / gender variants | 986 | Same animal, merge |
| Subgenus reformatting | 26 | Same animal, merge |
| Real merge, SQS agrees | 638 | Trivial |
| Real merge, one side scored | 101 | Take the one |
| Real merge, neither scored | 78 | Nothing to merge |
| **Real merge, SQS disagrees** | **18** | Rule needed |
| Ecology sets differ | 70 | Union |

Rule decided: **incumbent wins, union the ecology.** The 18 disagreements are 8% of merge
incumbents against 15% overall, so merged species are not special. **None of the merging
species appears in Wil's own records** under the old name.

Two flagged for an entomologist: the *Hylaeus annularis* group (three segregates at SQS 8,
incumbent at 1 while carrying RDB 3), and *Sigara striata* → *dorsalis* — the latter
confirmed correct from NBN, a misapplied name rather than a true synonym.

---

## Part 2 — Examen

### The revival premise was wrong

Five documents said `examen_data.py` was stale and would report **zero key species**, and
that Examen must not be run. Both claims are void.

`_load_codex_data` had **already been fixed** — it delegates to
`CodexRepository.get_statuses_batch` and `get_sqs_scores`, with a docstring saying so.
`PANTHEON_GB_STATUS_MAP` and `_classify_tier` do use names like `gb_rarity`, but those are
**local dictionary keys built from Pantheon's own categories** in the `PANTHEON_ONLY` path.
They never touch codex.db.

Examen was run. It worked. Glory Park: 128 species, 12 key, SQI 134.

**The stale 8-track mirror was real — but in `species_database_view.py`.**

### The Species Database view had been broken since April ✅

`_display_codex_status` read `gb_red_list`, `gb_rarity`, `section_41`, `bap`,
`global_red_list` — none of which exist on `SpeciesStatus`. All returned `""` and were
skipped silently, so the Conservation status panel showed **nothing for any species**.
Except `legal_protection`, which does exist and is a **list** — truthy, reaching
`QLabel(val)` and raising `TypeError`.

Blank or crashing, for five months. The seventh never-executed-or-untested path this year.

Rewritten against the real 11 tracks with list handling. *Lucanus cervus* now shows three
legal instruments with their schedules and three priority jurisdictions with citations.

### Feeding guild counts were split ✅

`pantheon.db` stores four guild values in two casings — Herbivore/herbivore,
Predator/predator, Saprophagous/saprophagous, Unknown/unknown. The `Counter` keyed on the
raw string counted each pair twice. Glory Park read `predator (37)` and `Predator (4)`;
larval predators are **41**.

Checked: habitats (17 values), broad_biotope (4) and SATs (26) have **no** case variants, so
no SQI figure was affected. Normalised at the two counting points in the analysis service.

### The Conservation tab was inventing Section 41 ✅ — the session's worst find

`_parse_status` reverse-engineered codes from `short_status`. For a priority species that
string is the literal `"Priority"`, which matches no token, so it fell through to a tier
fallback and stamped **S41** on every one.

Glory Park reported "Section 41: 4". Checked against Codex, its four priority species are on
the **Scottish Biodiversity List and the NI Priority Species List. None is on Section 41.**
Glory Park is in Northamptonshire.

Every other fault this session lost or mis-chose facts. **This one manufactured them**, and
it is the only one that could have put a false statement in a client report.

Fixed by adding structured tracks to `KeySpeciesEntry` (`rarity`, `threat`, `threat_legacy`,
`priority`, `legal`) and having the tab read them. Bars also rescaled — they were
`count * 40` capped at 200, so five species and fifty both filled the bar.

### The appendix said "S41/BAP" ✅

`display_status` rendered any priority listing as `S41/BAP (n)` — a label predating the
11-track scheme. The exported appendix uses it, so species with no English listing were
printed as S41/BAP. Not invented, but a client's ecologist would read it as Section 41.

Now names the jurisdiction: **"NI Priority, SBL"**. Unrecognised values pass through
unchanged rather than being guessed at.

### Key species are now jurisdiction-aware ✅ — the substantive change

`_classify` conferred the Priority tier for **any** priority listing or legal protection,
regardless of where the site was. So English sites gained key species on Scottish and NI
listings. One was *Osmia bicornis*, the Red Mason Bee.

Checked against practice before building: Section 41 of the NERC Act requires a list of
species of principal importance **in England**, and the section 40 duty points public bodies
at that list. Reviewed English EcIAs consistently scope "species of principal importance
(Section 41 list)" and never cite the SBL. JNCC's own UK BAP invertebrate list is published
with **per-country Y/N columns** — the profession already treats these as jurisdiction-
specific at source.

Rarity and threat are GB-wide and untouched. Only priority and legal_protection are
filtered, and only for conferring key status — every designation is still stored, returned
and displayed.

| Site | Key spp before | After |
|---|---:|---:|
| BAM Glory Park | 12 | **8** |
| Badshot Lea | 11 | 10 |
| Bicester Graven Hill | 42 | **31** |
| Derby | 10 | 5 |
| Fermyn Hall Deadwood | 8 | 8 |

**Glory Park's 8 is the number Wil said was right at the start of the day.** Fermyn Hall is
unchanged, as expected for a saproxylic site where key species come from rarity and threat.

⚠️ **Bicester and Derby moved substantially. Check both against what was issued.**

---

## Part 3 — SQS, and a mistake worth recording

A diagnostic was written to test whether merge incumbents carried scores contradicting their
own status. It imported `seed_codex.SQS_DEFAULTS` as "the rule" and reported 52% agreement
and 408 bad incumbents.

**Both figures were artefacts.** `SQS_DEFAULTS` is the *gap-fill* table, not Pantheon's
published rule. It scores RDB3 at 16 "per Fowles original SQI" — a different index — and
maps single `(track, value)` pairs taking the maximum, where the published rule is a
function of rarity **and** threat together.

Re-run against `shared/sqs_derivation.py`:

- **85% agreement** on Pantheon-sourced scores (close to the 79.8% in finding 54; the
  difference is today's better statuses)
- Merge incumbents differing: **135 of 1,708 (8%)** — so incumbent-wins is safe
- **525 of 816 gap-filled scores (64%) do not match the published rule**

That last figure promotes D9 from tidy-up to correctness problem. Wil's own reading — that
the derived scores have no provenance and should be computed live rather than stored — is
the right one, and would remove the instability of finding 59 as a side effect.

**Decision confirmed: compute live.** Not yet built.

---

## What was written

**Patches** (all in `scripts/`, ✓/✗ form, backup + compile-and-import check):
`patch_priority_detail` · `patch_status_tiebreak` · `patch_bridge_synonyms` ·
`patch_species_db_view` · `patch_guild_casing` · `patch_key_species_tracks` ·
`patch_conservation_tab` · `patch_display_status` · `patch_jurisdiction`

**Diagnostics** (read-only): `check_summary_loss` · `check_priority_impact` ·
`check_contested_status` · `check_bridge_collisions` · `check_sqs_vs_status` ·
`check_pantheon_casing` · `check_research_only`

`check_bridge_gap.py` is **superseded** — it re-derives the unmatched set from the old
two-pass logic and now reports every recovery as a collision. Delete it.

**Docs:** `37_Code_Review_Findings.md` (independent static analysis, unverified).

---

## Open

- **J2** — the 1,847 bridge collisions. Rule decided, not applied.
- **J3** — 68 unresolvable, including Odonata under vernacular names in `pantheon.db`.
- **D9** — derive gap-filled SQS live.
- **Jurisdiction selector** — the parameter exists and defaults to England; no UI control.
- **The two percentages** — the project table shows key/total (6.2%), the Overview card
  shows key/species-in-Pantheon (8.0%). Same screen, same quantity, two answers.
- **Stray punctuation** in the generated Overview sentence: "recorded. across 4 visits",
  "conservation value..".
- Bulk curatorial editor; external drive copy; merge `main` → `stable`.

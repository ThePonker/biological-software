### Session 32 (5 Sept 2026) — Codex corrected; Examen proven working ⭐⭐⭐

Began with a question about the S41 "research only" moths — common, widespread species added
to the UK BAP on decline data rather than rarity, which Wil had been removing from key-species
counts by hand. Chasing where that distinction lived opened everything below. It was
eventually answered from data already held: `pantheon.db` carries **72 species** under
*"Section 41 Priority Species - research only"*, already mapped by `CodexRepository`.

**Codex — three faults, all fixed and verified.**

*The priority collapse.* `build_codex_db.py` collapses designations with
`key = (track, detail or "")`, and all five priority jurisdictions mapped to
`status_detail = None` — so they competed for one slot per species and four were discarded
by row order. **2,303 species-jurisdiction facts were missing**; UK BAP sat at 12% of its
true coverage. The table was *built* to hold one row per jurisdiction; `legal_protection` was
implemented correctly and `priority` was not. The same rule, applied to one track and
forgotten for the other, in the same dictionary. Priority rows 2,928 → 5,231. Key species and
SQS unchanged — the damage was confined to which jurisdictions were reported.

*Ties by row order.* All modern Red List codes score 100, so ties were common and broken by
whichever row came back first; `date_designated` was carried and never consulted. Twelve
contests resolved wrongly, eleven of them vascular plants where a 2014 England list said
EX/EW and the 2021 GB list said RE. The twelfth shaped the fix — *Cercyon nigriceps*, where
plain "most recent wins" would have replaced a specific `Nb` with a vaguer `Notable`,
overriding a deliberate precedence rule. So: precedence first, date as tiebreak. 33 of 34
now resolve to the most recent; *Cercyon* correctly does not move.

*The bridge.* The TVK bridge had never consulted `uksi.synonyms` — the table that exists
precisely to map an old name to a current TVK. **3,000 of 3,068 unmatched Pantheon species
resolve through it**: *Aedes* → *Ochlerotatus*, *Achaearanea* → *Parasteatoda*, ordinary
post-2017 taxonomy. A third pass recovered the 1,153 that map to an unclaimed TVK; bridge
11,161 → 12,314, SQS 6,083 → 6,338. The gap-fill *fell* from 1,112 to 816, which is the good
news — 296 species that had a derived guess now carry their real published score. The
remaining **1,847 are collisions** where UKSI has merged two Pantheon taxa into one; rule
decided (incumbent wins, union the ecology), not yet applied.

**Examen — the revival premise was wrong, and it was inventing a fact.**

Five documents said `examen_data.py` was stale, would report zero key species, and that
Examen must not be run. `_load_codex_data` had **already been fixed** to delegate to
`CodexRepository`; the 8-track names in that file are local keys in the Pantheon-only path
and never touch codex.db. Examen was run. It worked.

The stale 8-track mirror was real but sat in **`species_database_view.py`**, where it had left
the Conservation status panel blank for every species since April — and crashing for any
legally protected one, because `legal_protection` is a list and reached `QLabel()`. The
seventh never-executed-or-untested path this year.

**The worst find:** `conservation_tab._parse_status` reverse-engineered codes from a display
string, and for a priority species that string is the literal `"Priority"` — matching nothing,
falling through to a tier fallback that stamped **S41** on all of them. Glory Park, in
Northamptonshire, reported "Section 41: 4"; its four priority species are on the Scottish and
NI lists and **none is on Section 41**. Every other fault this year lost or mis-chose facts.
This one manufactured them, and it is the only one that could have put a false statement in a
client report.

Also fixed: feeding guild counts split by Pantheon's inconsistent casing (larval predators
were 37 and 4; they are 41); and `display_status` labelling every priority listing "S41/BAP",
which the exported appendix printed against species with no English listing at all.

**Key species are now jurisdiction-aware.** `_classify` conferred the Priority tier for any
listing regardless of where the site was, so English sites gained key species on Scottish and
NI listings — including *Osmia bicornis*, the Red Mason Bee. Checked against practice first:
Section 41 requires a list of species of principal importance *in England*, reviewed English
EcIAs scope S41 and never cite the SBL, and JNCC's own UK BAP invertebrate list is published
with per-country Y/N columns. Rarity and threat are GB-wide and untouched; every designation
is still stored and displayed. Glory Park 12 → **8** key species — the number Wil said was
right at the start of the day. Bicester 42 → 31 and Derby 10 → 5 need checking against what
was issued.

**A mistake worth recording.** A diagnostic imported `seed_codex.SQS_DEFAULTS` as "Pantheon's
published rule" and reported 52% agreement and 408 bad merge incumbents. Both were artefacts:
`SQS_DEFAULTS` is the *gap-fill* table, scoring RDB3 at 16 on a different index's scale and
taking max-of-pairs where the rule is a function of rarity and threat together. Re-run against
`shared/sqs_derivation.py`: 85% agreement, and 8% of merge incumbents differ — so
incumbent-wins is safe. It also surfaced that **525 of 816 gap-filled scores don't follow the
published rule**, promoting D9 from tidy-up to correctness problem. Wil's own reading — that
the derived scores have no provenance and should be computed live — was the right one.

Nine patches, seven diagnostics, three Codex rebuilds, all verified.

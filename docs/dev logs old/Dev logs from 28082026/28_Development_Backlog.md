# Development Backlog

## Updated 5 September 2026 (Session 32)
## Companion: `24_Phase_Plan.md` (strategy), `10_Infrastructure_Issues.md` (faults)

Check this before starting a session. Grouped A–J, with a size and a trigger for each.

---

## The short list

1. **J2** — bridge collisions (rule decided, not applied) · ~1 day
2. **D9** — derive gap-filled SQS live · 0.5–1 day
3. **A1** — bulk curatorial editor · 0.5–1 day
4. **D2b** — external drive copy · 10 minutes
5. **G1** — `examen_data` tidy-up, rescoped · 0.5 day
6. **D7** — merge `main` → `stable` · 15 minutes

⚠️ **Also outstanding, not a code task:** Bicester Graven Hill and Derby key-species counts
moved substantially under jurisdiction filtering (42→31, 10→5). Check both against what was
issued to the client.

---

## A. Insect Collection

**A1. Bulk curatorial editor — HIGH.** 0.5–1 day. Six curatorial columns empty across all
2,549 specimens. Select many, set Preparation / Condition / Storage / Drawer, never touching
biological data.

**A2. Verify curatorial edit on existing specimens.** Small. May be closed by Session 29's
dialog work — test by editing and confirming save/reload.

**A3. `label_data` composition.** 0.5 day. Deferred.

**A4. `drawer_unit` → `drawer_number` rename.** 0.5 day. Column empty, no data risk.

**A5. `specimen_code`** — CLOSED, will not do.

---

## B. Data Entry

**B1.** ✅ DONE (Session 29).

**B2. Clicker count-mode.** 0.5 day. Keystroke increments Qty; foot-pedal compatible.

**B3. Repeat key for sex splits.** Small.

**B4. Reject `?` and `#N/A` as TVKs on load.** Trivial.

**B5. Species-name paste resolution.** 0.5 day. Pasted names store with no TVK and commit
with only a count as warning.

**B6. Row insert below the new-row marker.** Small. Committed but does not work.

---

## C. Import wizards

**C1.** ✅ FIXED (Session 30). 175 rows still doubled; cosmetic.

**C2. Re-enrich conservation from live Codex.** 0.5–1 day. **Raised in value by Session 32** —
workbooks bake in Codex data that now predates three corrections, not one.

**C3. Route wizards through `_get_preferred_common_name()`.** Small.

---

## D. Infrastructure

**D1.** ✅ DONE (Session 31).

**D2. Reconfigure the offline server.** Unscoped; documentation lost.

**D2b. External drive copy — HIGH, 10 minutes.** `data\` and
`C:\BiologicalSoftware_Backups\`. The only true off-machine copy available today.

**D3. Reconstruct `build_pantheon_db.py`.** ~1 day. Open since March.

**D3b. Rewrite `uksi_extractor.py`.** ~1 day. `uksi.db` is the specification.

**D4.** ✅ DONE (Session 30).

**D5. Sweep for never-executed code paths.** 0.5 day. **Seven found this year.** Two more
claimed by the September code review and unverified — see `37_Code_Review_Findings.md`.

**D6. Eyeball the future-dated commercial record.** Minutes.

**D7. Merge `main` → `stable`.** 15 min. Stale since June.

**D8. Laptop / second-machine access.** Unscoped. SQLite over a syncing folder from two
machines risks corruption. Needs a decision before it is attempted.

**D9. Derive gap-filled SQS live — HIGH, rescoped Session 32.** 0.5–1 day.
**525 of 816 gap-filled scores (64%) do not match Pantheon's published rule** — they came
from `seed_codex.SQS_DEFAULTS`, which scores RDB3 at 16 on a different index's scale and
takes max-of-pairs where the rule is a function of rarity *and* threat together.

Decision (Wil): the 4,971 Pantheon scores stay — they are a record of *what Pantheon
published*, which is what makes an SQI comparable. The gap-fill has no provenance and should
be computed on demand from `shared/sqs_derivation.py`. Touches `seed_codex.py`,
`CodexRepository.get_sqs`/`get_sqs_scores`. Removes Infrastructure 59 as a side effect.

---

## E. Documentation

**E1. Fill in Session 27.** The Data Entry build is reconstructed from code, not logged.

**E2. Reconcile `07_Codex_Design_Spec.md`.** §10 gives `PRIMARY KEY (tvk, status_track)`;
the live schema is `(tvk, status_track, status_detail)`. §3 says priority carries a uniform
"Priority" with the jurisdiction in `status_detail`; it now carries the jurisdiction in
**both** (deliberate — non-breaking). Contents figures still stale.

**E3. `23_Rebuild_Procedures.md`** documents a UKSI rebuild that cannot be performed, and
gives codex.db as 18 MB — it is **44.5 MB**.

**E4. `06_Software_Suite_Overview.md` predates Data Entry entirely.**

**E5. Delete `check_bridge_gap.py`** — superseded by `check_bridge_collisions.py`. It
re-derives the unmatched set from the pre-J1 logic and now reports every recovery as a
collision.

---

## F. Paused / closed

**Tabella** — development paused Aug 2026.

**Species status override** — will not build. Disagreement goes in the profile text.

---

## G. Examen

**Examen runs.** See `29_Examen_Revival_Assessment.md` §0 for the correction: the "must not
be run, reports zero key species" warning in five documents was wrong.

**G1. `examen_data` tidy-up — rescoped, no longer blocking.** 0.5 day. Not the 250-line strip
described. Three real items: `_classify_tier` duplicates `CodexRepository._classify` and has
drifted (so the two modes classify by different rules); the SQI arithmetic appears in four
places rather than calling `compute_sqi`; and the parallel enrichment paths cause
Infrastructure 62.

**G2, G4, G5** — ✅ DONE (Session 31).

**G3. Conservation tab** — ✅ DONE (Session 32). Was inventing Section 41; now reads
structured tracks. Priority jurisdictions and legal instruments counted under their own
names; bars rescaled.

**G6. Decide the fate of freeze / snapshots.** The case for stored state has weakened —
jurisdiction filtering now handles the main exclusion automatically. Reconsider.

**G7. Report renderers — Excel, then PDF, then Word.** 2–3 days. **Now the main remaining
build.** Excel first proves the pipeline.

**G8. Pantheon ecology has no editor.** Unscoped.

**G9. Views hardcode their own colour palettes.** 0.5 day. Six files.

**G10. Compartment analysis — v1.** 0.5 day. Maps to `sub_location`.

**G11. Key-species exclusion tickbox — rescoped.** Jurisdiction filtering (G17) removes the
main use case. What remains is the S41 research-only moths — and `pantheon.db` carries those
as a reporting category (**72 species**), already mapped in `CodexRepository`, so this may be
a filter rather than a tickbox.

**G12. Saproxylic SQI + IEC — v2.** ~3 days. Neither exists in the software. Needs the
605-species SQI list (Fowles 1999 / Alexander 2024) and the 180-species IEC list.

**G13. SQS derivation as an AnalysisMode.** 0.5 day. Related to D9.

**G14. Presentation items.** ~1 day. SQI at biotope and habitat level; NCS counts; species
names not codes; status-definitions footnote; vernacular fallback; Key and Rare Key
percentages; stenotopic count; SQI scale labelling.

**G15. Low-sample warning on the figure.** Small.

**G16. "Favourable (97 species, 19 required)".** Small.

**G17. Jurisdiction selector in the UI — NEW.** Small. The parameter exists on
`get_status_summary` / `get_statuses_batch` and defaults to England; there is no control.
**Needed before the tool is trusted on a Scottish or Welsh job.**

**G18. The two percentages — NEW.** Small. Project table shows key ÷ total (6.2%); Overview
card shows key ÷ species-in-Pantheon (8.0%). Same screen, same quantity.

**G19. Stray punctuation in the generated sentence — NEW.** Trivial. "recorded. across 4
visits", "conservation value..".

---

## H. Species profiles

**H1. Decide which store wins — HIGH, blocks H2–H4.** Two empty tables, different schemas,
neither aware of the other.

**H2. Three-way content model.** 0.5–1 day after H1.

**H3. Extract ~100 existing profiles from Word.** 0.5–1 day.

**H4. Scope, not a task.** Profiles only for species with a conservation status, or groups of
interest.

---

## I. Mapping tab

**I1. Adopt the Data Entry map widgets.** 0.5 day.

**I2. Move the map modules to `shared/`.** Small, do with I1 — two copies would drift.

**I3. Polygon grids** (hectad / tetrad / monad). 0.5 day.

**I4. Grid-square click → filtered records.** 0.5 day.

**I5. Atlas export.** 0.5 day.

**I6. Common-name search.** Small.

---

## J. Codex data integrity (NEW — Session 32)

**J1. Bridge synonym pass** — ✅ DONE. 1,153 species recovered; SQS 6,083 → 6,338.

**J2. The 1,847 bridge collisions — HIGH, NEXT.** ~1 day. UKSI has merged two Pantheon taxa
into one; each carries its own SQS and ecology, and `sqs_scores` is keyed on `tvk` alone so
one would silently overwrite the other.

**Rule decided: incumbent wins, union the ecology.** Evidence: only 18 of 835 genuine merges
disagree on SQS; merge incumbents differ from the published rule at 8% against 15% overall.
986 are spelling/gender variants and 26 subgenus reformattings — separate those first, they
are bookkeeping rather than merges.

Two for an entomologist: the *Hylaeus annularis* group; *Sigara striata* → *dorsalis*
(confirmed correct from NBN — a misapplied name).

**J3. Odonata under vernacular names in `pantheon.db`.** Small. "Azure Damselfly", "Banded
Demoiselle", "Black Darter" and others sit in the scientific-name column. Part of the 68 that
resolve by no route. Few enough to hand-map.

**J4. Unrouted designation codes.** 0.5 day. 1,519 rows across 16 codes. Most deliberate
(`NR-excludes` 732, `NS-excludes` 666, `WL` 76), but European Red List, bird breeding-season
RE/DD and some Global pre-94 codes fall through unmapped.

**J5. Rebuild-twice-and-compare check.** 0.5 day. Any difference means something is
order-dependent. Would have caught Infrastructure 57 in April, and converts the
version-stamping promise from an assumption into a tested fact.

---

## Not a task, but do not lose it

**The S41 research-only distinction is solved.** `pantheon.db.conservation_status` carries
72 species under *"Section 41 Priority Species - research only"*, already mapped by
`CodexRepository._apply_pantheon_row`. Butterfly Conservation's published list has 71. No
hardcoded list and no JNCC archaeology needed. Scope: invertebrates only, frozen at 2017.

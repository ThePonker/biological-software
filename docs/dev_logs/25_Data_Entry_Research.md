# Data Entry View — Research & Scoping

## Date: 11 June 2026 (Session 26)
## Purpose: Inform the design of an Observatum Data Entry View (Phase 3b) by examining what worked and what failed in the two dominant UK biological-recording packages — MapMate and Recorder 6 — plus why the recording community has been migrating away from both.

---

## 1. Why this research

Wil's workflow is desk/laptop typing-up, not in-field entry. The conservation/taxonomy columns Tabella auto-populates are *aids* (right-species confirmation, taxonomic sort, group context), not data to be captured. This reframes the target: a fast keyboard-driven grid that captures **species + what / where / when / who**, shows taxon/conservation **read-only alongside**, and writes straight to `observatum.db` against live Codex/UKSI — no frozen snapshot, no import round-trip.

MapMate and Recorder 6 are the reference implementations. They fail in opposite directions, and the gap between them is exactly where this view should sit.

---

## 2. MapMate — the fast one

MapMate (Access 97 backend, ~30 years old) is the tool prolific amateur recorders actually loved for *speed of entry*. Its data-entry design is worth copying closely.

### What worked — the speed mechanics

**Type-ahead matching on every field.** Type part of a name, press Enter, the program matches against the relevant table; multiple matches show a pick-list. This is the core loop and it is fast because it is keyboard-only — no reaching for the mouse.

**Field locking — the single most important idea.** Any field can be *locked* so its value carries unchanged to the next record. The documented best practice: complete and lock everything that repeats (site, date, recorder, method) *first*, then enter only the taxon and quantity per record. For a notebook of 40 records from one site on one date, that means 38 of them are essentially "taxon, quantity, Enter". This is the feature that makes MapMate feel instant, and it is the thing the Observatum view must replicate.

**Enter vs Tab distinction.** Enter validates the field (resolves dates, matches names) and advances; Tab advances *without* validating (leaves a raw value as-typed). Gives the user explicit control over when to pay the validation cost.

**Smart field parsing / shortcuts.** The date field accepts `now`, `today`, `yesterday`, `o/n` (overnight range), bare years (→ whole-year vague date), and ranges via `to` or `-`. Quantity accepts `0` (present, uncounted), sex shorthand (`1m`, `2f`, `2m:3f` → splits into two records), and DAFOR abundance codes. The site field has an inline create shortcut: `Sitename@GridRef` makes a new site and derives VC + admin area from the grid reference in one keystroke-run.

**Auto-derivation from grid reference.** Leave VC (or admin area) empty, press Enter, and MapMate offers the vice-county/area computed from the grid ref. Observatum already has the VC-lookup service to do this — it should wire into the grid-ref field the same way.

**Defaults / Restrictions as a scope filter.** The user sets working defaults (e.g. "Lepidoptera in Somerset"), which restricts pick-lists to relevant taxa and shrinks every match list. The current default scope is shown in the form's title bar so the user always knows what's filtered. A genuinely good idea — match lists over 140k UKSI taxa are unusable without scoping.

**`~name` escape hatch.** Prefix a search with `~` to search the *full* checklist even when defaults would exclude it — for the odd out-of-group record without reconfiguring. Small but thoughtful: scope for speed, with a one-character bypass for the exception.

**Voucher / status inline codes.** e.g. `!v` after quantity flags a voucher specimen. Lets metadata be captured without leaving the keyboard flow.

**Status line feedback.** A blue message line shows the last record entered and validation warnings — confirmation without a modal interrupting the flow.

### What didn't work — MapMate's failures

**Obsolescence and OS fragility.** Access 97 core; officially no longer recommended for new users; repeated breakage on Windows 8/10 (the analysis tree bug, the on-screen-keyboard conflict). BSBI now steers new recorders to the BSBI app / iRecord instead. *Lesson: don't build on a dead runtime — which Observatum (Python/Qt/SQLite) already avoids.*

**The sync model.** MapMate's peer-to-peer "sync" of records between users was a frequent source of confusion (records "disappearing" was usually a defaults/filter issue, but the sync compounded it). *Lesson: Observatum's single-user-writes-own-DB model is simpler and better; don't import this complexity.*

**Cramped, dated UI.** Functional but visually tight; the field-label-as-menu pattern (left-click a blue label for a context menu) is non-obvious. *Lesson: keep the speed mechanics, modernise the presentation.*

**Relational pre-requisites.** You must create at least one Site, Recorder, and Reference before your first record. Reasonable for a relational DB but a cold-start friction. *Lesson: allow inline creation (MapMate's own `@` shortcut does this well) so the first record isn't a wall.*

---

## 3. Recorder 6 — the comprehensive one

Recorder 6 (JNCC/Dorset Software, NBN data model) is the opposite: the professional-grade, maximally flexible, "correct" system. JNCC ceased support in March 2018 with no migration path offered.

### What worked

**Data model depth.** Built on the NBN data model — rich, GIS-linkable, handles specimens/collections (via extensions), exchange formats, verification workflow. The reason record centres and national schemes (Bryological/Lichen Society, Butterfly Conservation) committed to it and still can't easily leave.

**User-controlled validation timing.** A telling later fix: the import wizard used to auto-revalidate on every change, which "slowed down large imports"; they changed it so the user clicks to validate when ready, and can `Commit Matches` partway through a long manual-matching session. *Lesson: for bulk work, make validation an explicit user-triggered step, not a per-keystroke tax — directly relevant to how the Observatum grid validates.*

### What didn't work

**Weight and complexity.** Community's own words: "complex, extensive" data that recorders want to keep control of; a "10 year project to build our database"; everything maintained by unfunded volunteers. Powerful but heavy; the entry experience is forms-and-wizards, not rapid keyboard flow. *Lesson: comprehensiveness has a UX cost. The Observatum view should capture a deliberately thin record fast, not expose the full data model at entry time.*

**Abandonment risk.** Unsupported since 2018, no successor, no clean export. *Lesson — strategic: this is the argument **for** Wil owning his own tool on an open stack (SQLite he can read with any tool) rather than depending on someone else's abandoned package.*

---

## 4. Why the community moved away from both

- **MapMate**: Windows fragility + unfunded maintenance → BSBI recommends the BSBI app / iRecord for new recorders; some migrated databases to iRecord.
- **Recorder 6**: JNCC support ended 2018; heavy; volunteer-only maintenance.
- **The migration target** (iRecord/Indicia) is online, verification-oriented, and good for casual/survey records — but the **prolific specialist recorders** (inverts, fungi, lichens — exactly Wil's world) resisted, because their data is "complex, extensive, and important to them so they want to keep control of it." Several explicitly distrust online-only systems and poor rural broadband.
- Spreadsheets (Wil's current Tabella approach) are common but discouraged by schemes for "limited functionality and higher risk of errors."

**The gap this leaves** is precisely Observatum's opportunity: a *local, owned, fast* desktop entry tool for a serious specialist recorder — MapMate's speed and offline ownership, without its obsolescence; Recorder 6's data integrity, without its weight; spreadsheets' immediacy, without their error-proneness. No current product occupies that space well.

---

## 5. Design implications for the Observatum Data Entry View

Carried forward into the design discussion (next), not decided here.

| Principle | Source | Implication |
|---|---|---|
| **Field locking / sticky values** | MapMate's killer feature | Lock site/date/recorder/method; per-record entry collapses to taxon + qty. Non-negotiable for speed. |
| **Keyboard-only loop** | MapMate | Type-ahead + Enter-to-advance on every field; mouse optional. Observatum's QListWidget species popup (Session 25) is already the right primitive. |
| **Enter validates / Tab defers** | MapMate | Explicit control over when matching/validation runs. |
| **Smart date + grid parsing** | MapMate | `today`/`yesterday`/bare-year; grid-ref → VC auto-fill via existing vc_lookup_service. Reuse, don't rebuild. |
| **Scope filter with title-bar indicator + escape char** | MapMate Defaults | Optional working scope (group/VC) to shrink match lists; show it; allow a bypass. |
| **Inline create for site/recorder** | MapMate `@` shortcut | First record mustn't hit a cold-start wall. |
| **User-triggered validation for bulk** | Recorder 6 fix | Validate on demand, not per keystroke, when entering many rows. |
| **Thin record, live enrichment shown read-only** | Wil's reframing + R6 anti-pattern | Capture species + what/where/when/who; display taxon/conservation beside, never store stale copies. Writes direct to observatum.db. |
| **Embeddable widget + standalone launcher** | Wil's request | Build as a self-contained widget taking a DB connection; Observatum embeds it as a tab, a thin `__main__` opens it alone (Atrium pattern). Design constraint from line one. |
| **Open, owned, local** | R6/MapMate abandonment lesson | Reinforces the whole "evolve my own tool on SQLite/Python" strategy. |

---

## 6. Open questions for Wil (design discussion)

1. Did you use MapMate or Recorder 6 yourself? Firsthand "this annoyed me / this was great" outranks any forum thread.
2. The 40-records-from-one-notebook scenario: what do you type *first*, and what should be near-automatic (locked) by then?
3. Do you want a working-scope filter (MapMate Defaults style), or always full-checklist with fast search?
4. Standalone window: launch to a blank ready-to-type record, or to a session picker (which site/project first)?
5. Recording Scheme and Insect Collection — does the same grid serve all three record types (Personal / Commercial / Specimen) with a type switch, or is this Personal/Commercial observations only to start?

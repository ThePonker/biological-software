# Data Entry View — Design Spec

## Date: 11 June 2026 (Session 26)
## Status: Design agreed (paper). Build = Phase 3b, winter 2026.
## Companion: 25_Data_Entry_Research.md (MapMate / Recorder 6 study)

---

## 1. What it is

A fast, keyboard-driven observation-entry grid that writes directly to `observatum.db`. It replaces the Tabella Excel round-trip for desk/laptop typing-up. It is built as a self-contained widget that Observatum embeds as a tab **and** that a thin standalone launcher opens on its own.

It captures **observations only** — Personal and Commercial. Specimens are out of scope (Wil enters those directly via the Insect Collection tab). Conservation/taxonomy data is shown read-only as a confirmation aid, never captured.

The tool is a **writer into observatum.db**. Everything downstream — embargo, commercial export, iRecord upload, iRecord sync-back with verification/keys — is existing Observatum infrastructure that these records flow into unchanged. The iRecord round-trip is explicitly **out of scope** for this tool.

---

## 2. Why it exists (grounded in real data)

Inspection of a live workbook (218 records) showed:

- Wil reorders columns to put **Species, Sex, Qty** first — hand-building a fast entry loop the new tool should provide natively.
- **Date, Recorder, Determiner, Method, Stage, Certainty** are 100% filled and identical down a session — textbook sticky/locked fields.
- **VC is 0% filled** — never typed; must be derived from grid ref, not entered.
- **Conservation columns ~0–6% filled** — proof they are glance-aids, not captured data.
- **Certainty is always "Certain"** (for iRecord verification) — a fixed constant, not a per-record choice.

The central use case is **trap-sample processing**: load the job, work down a pitfall/flight-interception sample under the microscope, entering many species that share date/site/grid/parcel/trap/visit and differ only in species/sex/qty. A single trap can be 30–40 determinations. The design is optimised around this burst-entry pattern.

The strategic gap (from research): MapMate's entry speed without its dead runtime; Recorder 6's data integrity without its weight; spreadsheets' immediacy without their error-proneness. No current product occupies this space for a serious specialist recorder.

---

## 3. The entry model

### 3.1 Two zones

**Session header (sticky).** Set once at the start of a session; values ride every record until changed. Any field can be unlocked for a single record then re-locked (MapMate model).

| Field | Source / behaviour | Stored | → iRecord |
|---|---|---|---|
| Mode: Personal / Commercial | toggle; reveals project/client/embargo when Commercial | — | — |
| Date | smart parse: `today`, `yesterday`, bare year, ranges | yes | yes |
| Site Name | type-ahead from existing sites; inline-create | yes | yes |
| Grid Ref | drives VC derivation | yes | yes |
| VC | **auto-derived** from grid ref (vc_lookup_service); display-only, editable on exception | yes | yes |
| Recorder | type-ahead from existing; inline-create | yes | yes |
| Determiner | type-ahead; defaults to Recorder | yes | yes |
| Method | controlled vocab (existing DV_METHOD list — carries trap *type*) | yes | yes |
| Stage | controlled vocab; usual value Adult | yes | yes |
| **Sub-location / Parcel** | sticky; pick-from-existing-for-site; **internal only** | yes | **no** |
| **Trap Number** | sticky; **internal only** | yes | **no** |
| **Visit Number** | sticky; **internal only** | yes | **no** |
| Project / Client / Embargo | shown only in Commercial mode | yes | per existing commercial rules |

**Hot loop (per record).** Keyboard-only, the fast inner sequence:

```
Species → (confirm via read-only panel) → Sex → Qty (clicker count-mode) → Enter
```

- **Species**: type-ahead against UKSI; reuse the Session-25 QListWidget popup primitive (proven keyboard navigation).
- **Sex**: controlled vocab; single-letter shorthand where possible (`m`/`f`).
- **Qty**: clicker count-mode (§3.3).
- **Enter** commits the row, clears to a blank Species cell.
- **Repeat key**: clones the just-entered row (species + all sticky fields) and lands on Sex — for same-species sex-splits (3♂ then 2♀, common in spiders/Diptera/Hymenoptera). Four keystrokes for the second row.

**Fixed constant:** Certainty = "Certain" on every record, not shown in the flow (editable only via an advanced/edit path).

**Comment:** ordinary free-text field, pass-through to iRecord, no stripping logic. Genuine one-off notes only — survey structure lives in the structured fields above, not here.

### 3.2 Keyboard map (draft)

| Key | Action |
|---|---|
| Enter | validate field + advance / commit record |
| Tab | advance without validating |
| Repeat key (e.g. Ctrl+R or `"`) | clone last record → land on Sex |
| Clicker key (default `+` / Space) | increment Qty |
| Decrement key (default `-`) | decrement Qty (over-count fix) |
| Esc | cancel current field / popup |
| F-key or label-click | unlock a sticky field for one record |

Exact bindings finalised at build; all configurable.

### 3.3 Clicker count-mode

For counting many individuals under the scope without mental tallying.

- A configurable keystroke increments the current Qty; a second decrements (correction).
- Works identically from spacebar, an on-screen +/- button, or a **USB foot pedal** programmed to emit that keystroke — so it works with zero hardware, and a pedal is an optional nicer input.
- Large, glanceable on-screen counter so the total can be checked without leaving the eyepieces.
- Flow is **ID-first**: species and sex are set, then count-mode runs on Qty, then Enter commits. The live taxon panel shows the species being counted as confirmation.
- Pedal sends to the focused window only (not global capture) — fine in practice. Buy a pedal **programmable to a keystroke** (a 3-pedal model could map increment / decrement / commit).

### 3.4 Read-only confirmation panel

Beside the entry row, live from Codex/UKSI for the current species: scientific + common name, class/order/family, sort code, and conservation status across tracks. Captured: nothing. Purpose: confirm the right species is selected while entering/counting.

### 3.5 Running session list

Below the entry row, the records added this session for the current site/trap — so Wil can see what's already in (a known MapMate strength). Sortable; click a row to edit/correct it.

---

## 4. Schema prerequisite

Three new columns on the `observations` table, all internal (excluded from iRecord export), available to filtering and Examen analysis:

```
sub_location   TEXT    -- parcel / application area / red-line boundary
trap_number    TEXT    -- which physical trap
visit_number   TEXT    -- which visit / check
```

Per the project's schema-change rule: add to the live DB **and** run a per-table audit of `reset_database.py` (and any other CREATE TABLE for observations) so the columns exist in every definition. These three fields enable per-parcel / per-trap / per-visit data extraction and assemblage analysis — directly serving Examen ("run the assessment for Parcel 4 only" becomes a structured filter, not a free-text grep).

No other schema change. Comment, certainty, and the conservation/taxonomy display all use existing structures.

---

## 5. Architecture

**Widget-first.** The grid is a self-contained `QWidget` that takes a database connection (or path) as a constructor argument and has no dependency on Observatum's main-window internals. This is a design constraint from the first line of code.

Two entry points, one codebase:

1. **Embedded** — Observatum adds it as a tab (a "Data Entry" / "Quick Entry" tab) within the main window.
2. **Standalone** — a thin `__main__` + launcher (`launchers/run_entry.bat`) opens just the grid in its own window, following the Atrium pattern, so Wil doesn't have to open all of Observatum to type up a trap.

Shared concerns (species search, VC lookup, controlled vocabularies, the write path into observatum.db) come from existing services/repositories — the widget consumes them, doesn't reimplement them. The standalone launcher reuses `shared/db_config.py` for path resolution.

---

## 6. Explicitly out of scope

- **Specimens** — entered via the Insect Collection tab as now.
- **iRecord round-trip** — export, upload, sync-back, verification, keys: all existing Observatum infrastructure. Records from this tool flow into it unchanged.
- **Comment stripping** — comment is plain pass-through; no personal-convention logic baked in.
- **Per-parcel mapping / polygons** — a possible future (sub-location as a first-class mapped entity) but not now; the TEXT column covers analysis needs.
- **Tabella** — kept running in parallel during the transition; coexistence handled separately, not in this doc.

---

## 7. Build phasing (within Phase 3b)

| Step | Content |
|---|---|
| 0 | Schema prerequisite: 3 columns + reset-script audit |
| 1 | Widget shell + sticky header + write path to observatum.db |
| 2 | Hot loop: species type-ahead, sex, qty, Enter-to-commit, repeat key |
| 3 | Clicker count-mode + configurable keys |
| 4 | Read-only Codex/UKSI panel + running session list |
| 5 | Commercial mode (project/client/embargo) + VC auto-derive |
| 6 | Standalone launcher + Atrium entry |
| 7 | Field testing on a real trap sample; refine bindings |

---

## 8. Estimate

Originally pencilled at 2–3 days in the Phase Plan as a "MapMate-style grid". The agreed scope is larger — clicker count-mode, the repeat-key, the structured survey-axis fields, the read-only panel, the running list, and the embedded+standalone split. Revised rough estimate: **4–6 days**, winter. The schema prerequisite (step 0) is small and could be done ahead of the main build, even during field season, since it only adds columns.

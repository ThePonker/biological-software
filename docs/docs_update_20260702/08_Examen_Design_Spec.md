# Examen — Species Assessment Tool Design Spec (SUPERSEDED — reference only)

## Date: 24 March 2026

> **⚠️ Superseded.** This is the original **desktop** design. The desktop Examen was retired
> 16 April 2026 (archived at `_archive/Examen_desktop_20260416/`). It predates the 11-track Codex.
> Kept as a feature/layout reference only. The current design lives in `08_Examen_Web_Design_Spec.md`
> (web) and `24_Phase_Plan.md` → "Examen — desktop first" (the chosen rebuild path). Build fresh on
> current `shared/` + Codex; do not treat this as a foundation.

---

## What Examen Is

Examen is a standalone PySide6 application that replaces the online Pantheon website for invertebrate assemblage assessment. It provides three views in one window: a species reference database, a site analysis workflow for report-writing, and an archive of frozen assessment figures.

The name means both "examination" (what it does) and "swarm of bees" (who it serves).

---

## Why It Exists

The Pantheon website (Natural England / CEH) is:
- Manually operated — species lists entered by hand, results transcribed
- Clunky — lots of confusing, unused information in the interface
- Unfunded — Natural England is not maintaining it
- Stale — conservation data from 2017, missing many Hymenoptera and Diptera

Examen replaces this with a local tool that:
- Pulls species lists directly from Observatum or accepts pasted/imported lists
- Uses Codex (JNCC Dec 2023 + manual entries) for up-to-date conservation data
- Uses Pantheon's ecology tables (habitats, guilds, SATs) which have no alternative source
- Presents results clearly, without Pantheon's noise
- Freezes report figures so they're reproducible years later
- Exports at every level (species profiles, analysis reports, species appendices)
- Applies taxonomic sort order on all outputs

---

## Three Views

### View 1: Species Database

**Purpose**: Browse and edit species information — the reference library.

**Data sources**: codex.db (conservation), pantheon.db (ecology), uksi.db (taxonomy)

**Features**:
- Search by species name (UKSI autocomplete)
- Display: conservation status across all 8 Codex tracks, SQS score, source review for each status
- Display: Pantheon ecology — broad biotope, habitats, larval/adult guilds, SATs, fidelity scores, associations
- Manual entry editor: add/edit conservation statuses from published reviews not yet in JNCC
- Export species profile (PDF or CSV)

**Layout**: Search bar at top. Left panel: species list / search results. Right panel: full species profile with collapsible sections for each data category.

### View 2: Site Analysis

**Purpose**: The report-writing workflow. Load a species list, get your numbers.

**Data sources**: codex.db, pantheon.db, observatum.db (optional — for loading by site/project)

**Input modes**:
- **From Observatum**: Select a commercial project/site → pulls the species list automatically
- **Paste/Import**: Paste species names or import CSV/Excel with species column

**Computed metrics** (via PantheonAnalysisService):
- Key species count and percentage (three-tier: Rare/Scarce/Priority)
- SQI (Species Quality Index) — overall and per biotope/habitat/SAT
- Habitat breakdown with species counts
- SAT representation
- Guild composition (larval and adult)
- Full species list with conservation status, SQS, tier, biotope, habitat

**Mode comparison**: Toggle between Codex Full (enriched data) and Pantheon Only (strict comparison against what Pantheon website would show). Side-by-side comparison available.

**Taxonomic sort**: All species lists sorted by taxonomic_sort_key from UKSI.

**Exports**:
- Analysis summary report (Excel or PDF)
- Species appendix with status columns (the table that goes in your report)
- Raw data CSV

**Freeze**: When satisfied with the numbers, click Freeze → captures the full assessment (species list, all metrics, Codex version, mode used, date) into examen.db. The frozen figures never change.

### View 3: Assessment Archive

**Purpose**: Browse historical frozen assessments.

**Data source**: examen.db

**Features**:
- Browse by site, project, client, year
- View full details of any frozen assessment
- Compare two sites side-by-side (Jaccard similarity, metric comparison)
- Export historical data
- Note: live metrics (from current Codex) shown alongside frozen metrics for comparison

**Layout**: Table of all assessments with sort/filter. Click to expand detail panel.

---

## Data Flow

```
                   ┌─────────────┐
                   │  uksi.db    │ ← taxonomy, sort keys
                   └──────┬──────┘
                          │
┌──────────────┐   ┌──────┴──────┐   ┌───────────────┐
│ observatum.db│──→│   Examen    │←──│  pantheon.db   │ ← ecology
│ (commercial) │   │             │   │  (habitats,    │
└──────────────┘   │  3 views    │   │   guilds, SATs)│
                   │             │   └───────────────┘
                   │  Species DB │
                   │  Site Anal. │←──┌───────────────┐
                   │  Archive    │   │   codex.db     │ ← conservation
                   └──────┬──────┘   │  (statuses,    │
                          │          │   SQS, bridge)  │
                          ▼          └───────────────┘
                   ┌─────────────┐
                   │  examen.db  │ ← frozen assessments
                   └─────────────┘
```

---

## Existing Code (Carries Over)

| File | Purpose | Status |
|------|---------|--------|
| `Examen/examen_data.py` | Site/species queries from observatum.db | Working, needs expansion |
| `Examen/examen_ui.py` | Current basic UI (single table+detail) | To be restructured as 3-view tab bar |
| `Examen/snapshot_manager.py` | Freeze/retrieve logic | Working |
| `Observatum/src/repositories/codex_repository.py` | Codex data access (dual-mode) | Working |
| `Observatum/src/repositories/pantheon_repository.py` | Pantheon ecology access | Working |
| `Observatum/src/services/pantheon_analysis_service.py` | SQI, key species, compare | Working |

The analysis service and repositories are currently inside Observatum's `src/`. Examen imports them via the shared `PYTHONPATH`. If/when Examen needs to work independently of Observatum, these can be extracted to a shared library.

---

## File Structure (Target)

```
Examen/
├── __init__.py
├── __main__.py                    Entry point
├── examen_data.py                 Data queries (existing, expand)
├── examen_ui.py                   Main window with 3-view tab bar
├── species_database_view.py       View 1: browse/edit species
├── site_analysis_view.py          View 2: load list, compute, export, freeze
├── assessment_archive_view.py     View 3: browse frozen assessments
└── snapshot_manager.py            Freeze/retrieve logic (existing)
```

---

## Development Phases

**Note**: The three-view shell was built in Session 22. All views render and have basic functionality. The phases below cover wiring to live data sources and full feature implementation.


### Phase E1: Species Database View (~4-6 hrs)
- Species search with UKSI autocomplete
- Profile display (Codex statuses + Pantheon ecology)
- Manual entry editor dialog
- Species profile export

### Phase E2: Site Analysis View (~6-8 hrs)
- Load from Observatum (site/project picker) or paste/import
- Metric computation and display
- Mode comparison (Codex Full vs Pantheon Only)
- Export (report + species appendix)
- Freeze workflow

### Phase E3: Assessment Archive View (~3-4 hrs)
- Frozen assessment browser
- Detail panel
- Site comparison
- Historical export

---

## For Other Entomologists

Examen is designed to work with or without Observatum:
- **With Observatum**: load species lists from commercial observations by site/project
- **Without Observatum**: paste or import a species list directly (CSV, Excel, plain text)
- All exports are standalone — a colleague receiving an Excel report doesn't need any software

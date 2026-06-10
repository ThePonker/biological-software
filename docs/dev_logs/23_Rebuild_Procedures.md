# Biological Software ? Database Rebuild Procedures

## Date: 29 March 2026

---

## Overview

The suite uses 8 databases. Three have rebuild chains that must follow a specific order. This document explains when and how to rebuild each.

---

## Rebuild Chain Order

When multiple databases need rebuilding, follow this order:
```
UKSI (.mdb) ? uksi.db ? pantheon.db ? codex.db ? seed
```

Never rebuild Codex before UKSI or Pantheon ? it depends on both for TVK resolution and SQS scores.

---

## 1. UKSI Update (Taxonomy)

**When:** NHM publishes a new UK Species Inventory (every 2-3 years)

**Steps:**
1. Download new UKSI Access database (`.mdb`)
2. Update path in `scripts/uksi_extractor_v5.py` or add `UKSI_MDB` to `paths.py`
3. Run: `python scripts/uksi_extractor_v5.py`
4. This rebuilds `data/uksi.db` (~96 MB, ~122k taxa)
5. Then rebuild Codex (see below) ? TVK bridge needs regenerating

**Impact:**
- All apps using uksi.db see updated taxonomy immediately
- Species TVKs in observatum.db may become stale (records store TVKs at import time)
- A "taxonomy refresh" script for observatum.db does NOT exist yet

---

## 2. JNCC Conservation Designations Update

**When:** JNCC publishes a new spreadsheet (irregular ? last was Dec 2023)

**Steps:**
1. Download from https://hub.jncc.gov.uk/assets/478f7160-967b-4366-acdf-8941fd33850b
2. Save to `data/conservation-designations-YYYYMMDD/`
3. Update `JNCC_DIR` in `paths.py` to point to new folder
4. Run: `python scripts/build_codex_db.py`
5. Run: `python scripts/seed_codex.py`

**What's preserved:** manual_entries, reviews table, review imports ? all survive rebuild
**What's rebuilt:** designations, status_summary, tvk_bridge, sqs_scores

---

## 3. Pantheon Ecology Update

**When:** Natural England releases new NERC EIDC dataset (unlikely ? last was 2017 v3.7.4)

**Steps:**
1. Download from NERC EIDC (DOI: 10.5285/2a353d2d-c1b9-4bf7-8702-9e78910844bc)
2. Extract to data download directory
3. Run: `python build_pantheon_db.py`
4. Then rebuild Codex: `python scripts/build_codex_db.py` then `python scripts/seed_codex.py`

**Impact:** Ecology data updated (habitats, guilds, SATs). SQS scores re-imported into Codex.

---

## 4. Codex Review Import (Conservation)

**When:** A new species status review is published

**Steps (via Codex Manager GUI):**
1. Extract review data to CSV (species_name, status columns)
2. Open Codex Manager: `launchers/run_codex.bat`
3. Import Review tab ? browse CSV ? fill metadata ? Preview ? Import

**Steps (via CLI):**
```
python scripts/import_codex_review.py review.csv --name "..." --author "..." --group "..." --track gb_red_list
```

**What happens:** Entries added to manual_entries, status_summary rebuilt, review registered

---

## 5. What Does NOT Exist Yet

| Feature | Description | Priority |
|---------|-------------|----------|
| Taxonomy refresh | Update TVKs in observatum.db when UKSI changes | Medium |
| Rebuild-all script | Chain: UKSI ? Pantheon ? Codex in one command | Low |
| User-facing docs | Help page in the software explaining rebuilds | Low |

---

## Database Summary

| Database | Size | Rebuildable? | Rebuild trigger |
|----------|------|-------------|-----------------|
| observatum.db | ~113 MB | No (user data) | N/A ? backup regularly |
| uksi.db | 96 MB | Yes | New UKSI from NHM |
| pantheon.db | 22 MB | Yes | New NERC dataset |
| codex.db | 18 MB | Yes (preserves manual) | New JNCC or after UKSI/Pantheon rebuild |
| vc_lookup.db | 12 MB | Yes | New shapefile |
| examen.db | On demand | No (frozen assessments) | N/A ? backup with observatum |
| munia.db | ~varies | No (user data) | N/A ? backup regularly |
| gamification.db | ~0.2 MB | Recreated | Automatic |

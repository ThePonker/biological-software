# Biological Software — Session Handover

## Date: 6 May 2026 (Session 25 — Bug Fixes + Tabella Enhancement)

---

## Executive Summary

Field season bug-fix and enhancement session. Species search rewritten, specimen/observation editing functional, dates standardised, Atrium polished. Major new feature: Tabella pending records system scans active workbooks for un-imported entries and displays cross-workbook recording history with pending counts.

---

## What Was Accomplished

### Bug Fixes
- Species search: QCompleter → QListWidget popup (keyboard control)
- Specimen editing: site_name_local column, full edit chain
- Date standardisation: all ISO, settings-aware display, sort fixes
- Observation editing: new dialog, edit lock only on iRecord records
- CSV backup: always offered, includes recording_scheme
- Data: 8 Kent Deadwood 2027→2026, Ctrl+Enter shortcuts

### Tabella Pending Records (NEW)
- `refresh_records.py` scans `.xlsm` workbooks in Active Record Books folder
- VBA counts own workbook entries (file lock workaround)
- Displays `Personal: 3 (+2p)  Commercial: 5 (+1p)` format
- Generator updated for future workbooks
- 3 existing workbooks manually updated with new VBA

---

## Pending for Next Session (~1 hr)
- Excel sheet protection: lock auto-populated columns
- Active Record Books path configurable in Observatum Settings
- Update Tabella generator vba_source.py if sheet protection added

## Winter Projects
- Observatum Data Entry View (MapMate-style, replaces Excel for desk entry)
- Examen E5-E8
- Codex display integration, mapping polish, gamification

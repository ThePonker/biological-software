# Biological Software — Complete Development History

## Updated 2 July 2026 (through Session 26)

## Project Overview

**Biological Software** is a suite of Latin-themed tools for naturalist field recording and invertebrate survey reporting, built with Python/PySide6/SQLite, following a Victorian naturalist theme.

### The Software Suite

| Name | Purpose | Status |
|------|---------|--------|
| **Observatum** | Main biological recording app — observations, specimens, recording scheme | Active |
| **Examen** | Invertebrate assemblage assessment (Pantheon replacement) | Desktop retired 16 Apr 2026; desktop rebuild chosen first (winter), web = future layer |
| **Codex** | Conservation manager GUI + database pipeline | 11-track, biodiversity-wide, clean baseline |
| **Curator** | Insect collection organiser | Built |
| **Tabella** | Field data entry workbook generator (Excel+VBA) + runtime app | v2, pending-records live |
| **Munia** | Capacity planner | v2, MUNIA_DB registered |
| **Atrium** | Suite launcher (system tray) | Built (4 apps + 2 tools) |

---

### Session 24 (25–26 Mar 2026) — Import Pipeline, RS Integration & Multi-Bot Development

**Observatum fixes (17 items):** specimen enrichment root cause (`uksi_conn` → `uksi_model`); subfamily parent-chain lookup; import-notes combine on all 3 wizards; RS stats cache invalidation + refresh; RS export wired; VC lookup fix + recovery (94.5% → 99.2%); Species Match Report on all wizards; persistent Resolve Species button; stats refresh after import.

**Parallel bot:** Examen polish (manual entry editor, import list, appendix/site/historical export); Curator (Hemiptera sort, Coleoptera suborder grouping); Atrium system-tray launcher.

### Session 25 (28 Apr – May 2026) — Field-Season Fixes + Codex Widening

**Field fixes:**
- Species search: QCompleter → QListWidget popup (full keyboard control).
- Specimen editing: `site_name_local` column, edit chain end-to-end.
- Date standardisation: all 2,454 specimen dates → ISO; IC + RS sort fixes.
- Observation editing: new EditObservationDialog; edit lock only on `irecord_id`. **Follow-up fix:** `ObservationRepository.update()` signature mismatch resolved by direct SQL in `observation_detail_mixin.py`; mis-dated commercial records corrected.
- CSV backup always offered, includes recording_scheme.
- Atrium: tinted icons, pin toggle, taskbar, no console.
- Tabella pending records: `refresh_records.py` scans Active Record Books; VBA counts own entries; `Personal: 3 (+2p)` display.

**iRecord recovery (≈9 May):** sync audit closed clean (Commercial 1,178 / Personal 18,758 with irecord_id). `irecord_id`-nulling bug found and fixed in `wizard_import_mixin.py`; 295 new personal records imported, 180 IDs preserved. Tabella `refresh_records.py` rewritten to read TVK column + honour `--skip`. `mark_synced()` fixed (`synced_at` → `last_synced`). Tabella CSV `ParseCSVLine` VBA subroutine added for quoted multi-value fields.

**Codex 11-track widening (Apr):** rebuilt biodiversity-wide for conservation, invertebrate-only for SQS. 14,395 species / 11 tracks; designations 27,062, status_summary 23,123, sqs_scores 6,082. Cleanup: 109 zero-SQS + 6,231 non-invert collisions removed, 1,111 derived; build script patched. Regression 86%; Codex Manager + Tabella generation validated.

### Session 26 (June 2026) — Phase 0 Hygiene + Strategy + Data Entry Design

- **Phase 0 hygiene:** Git initialised (`main` + `stable`, `.gitignore`); WAL checkpoint on close; examen.db + munia.db added to backup-on-close; `MUNIA_DB` added to `paths.py`.
- **Data integrity:** three columns (`sub_location`, `trap_number`, `visit_number`) added to `observations` (Data Entry prerequisite); taxonomy refresh diagnostic — 30 records / 3 stale TVKs resolved, 0 remaining.
- **UKSI extractor v5:** English-only common names, sort_code/sort_order, preferred flag.
- **Strategy** (`24_Phase_Plan.md`): evolve-don't-rewrite; Examen desktop-first then web; frozen-report-as-record (no server storage); UKSI confirmed CC BY 4.0.
- **Design:** Data Entry View researched (`25`) + designed (`26`); Examen web spec rewritten around a no-storage core (`08_Examen_Web_Design_Spec.md`).

---

## Performance Metrics (from optimisation pass)

| Operation | Before | After |
|-----------|--------|-------|
| Total startup | 16.5s | 3.6s |
| Stats switching | 6.5s | 0.000s |
| Scheme stats | 2.6s | 0.026s |
| Column sort | 5+ sec | 0.018s |
| RS enrichment (79k rows) | Hung at 29% | Completes in seconds |

## Remaining Work (see `24_Phase_Plan.md` for the live plan)

| Category | Est. (focused days) | When |
|----------|-------|--------|
| Phase 1 — taxonomy refresh script, import-time Codex re-enrichment, rebuild-all chain, Tabella pending hour | ~2–3 | field-season-safe |
| Desktop Examen (personal) | 5–8 | winter, first |
| Data Entry View | 4–6 | winter, after Examen |
| Distributable Observatum | ~5–6 | winter / later |
| Web Examen | 10–15 | future, if reach justifies |

# 41 — Groundwork notes, 9 October 2026

Read-only research done during the D:\ refresh, so each build can start at the code.
Nothing in the suite or its databases was changed. Four parts follow, each with its own
sources, measurement queries, build checklist and open questions:

1. **Import wizards** — I7b repair plan for the scheme and specimen wizards; C4 merge design.
2. **Saproxylic SQI and IEC** — E7.
3. **Photos and geo** — A8 / A8b; I3b (F29) and I3c (F30).
4. **Checklist order and report contents** — drawer order (A1 open question); E3/E4/E6/E8.

*Caveat:* the code snapshot read was staged before the 9 Oct observation-import repair,
so Part 1 describes that wizard's pre-repair state in places; the fix pattern it proposes
for the other two wizards is the one now in the live observation wizard.

## Headline findings

**Imports (Part 1)**
- Scheme import: F33 confirmed (`wizard_import_mixin.py:345–355`); its update path always
  overwrites quantity / sensitive / sync_status / import_notes; a BOM file loses every
  iRecord ID (encoding order); "c.20" and "5+" become 1; Revalidate does nothing.
- Specimen import: no duplicate check (though `specimen_code` is UNIQUE); one bad row loses
  its 500-row batch silently; **every manual species pick (bulk resolution, the two search
  dialogs, revalidate) sets the TVK but never recomputes the sort key** — a hand-resolved
  specimen imports invisible to the sidebar or filed under the previous species.
- I7b realistically ~2.5 days, not 1. C4 realistically ~7 days (steps 1–5, ~4 days, give
  most of the value). The three species lookups behave differently — merging them needs
  decisions from you, not just code.

**Saproxylic (Part 2)**
- khepri.uk contradicts itself (605 species + IEC 2024 on its home page; 598/596 + IEC 2004
  on `/main`). Your Cobham 2024 report used 605 + 2024. **You choose the defaults.**
- Rankings: 241 sites, no licence or download — hold comparisons manually, don't scrape.
- **The IEC list is already in `pantheon.db`** (`fidelity_scores`, 180 rows, points 3/2/1);
  2 rows have a blank TVK (fault F26), so 178 usable until fixed.
- **The SQI cannot come from Codex alone:** Least Concern species are scored by their 1999
  distribution (Common 1 / Local 2 / other 4), which neither Codex nor Pantheon holds. A
  small `sap_list` table keyed from your copy of the 1999 paper fills that gap.
- Formula verified against the rankings (New Forest 2500/324 = 771.6). ~3 days to build.

**Photos and geo (Part 3)**
- **Do not use `grid_converter_service` for lat/long:** against OS's 40 published test
  points it is out by a median 35 m and up to 1.4 km. A plain-Python Helmert shift is within
  5 m (median 1.8 m) — enough; OSTN15 not needed.
- The import wizard converts the **corner** of the grid square, not its centre (up to 71 m
  for 6-figure refs) — decide centre or corner before recomputing the 3,332.
- VC at boundaries can be done in OS eastings/northings against the OSGB shapefile, no
  lat/long needed. Two more VC faults found: 10 km / 2 km refs take the VC of their SW 1 km
  square; coastal squares centred in the sea get no VC.
- Photos: Pillow does everything (3.14 wheels). **OneDrive risk:** reading any byte of a
  cloud-only file downloads it — a careless first scan would pull all 44 GB. The scanner
  links by filename and folder first and reads bytes only from local files.
- Estimates: photos ~3 days + ~2–2.5 for the inbox; geo ~1.5–2 days.

**Checklist order and reports (Part 4)**
- Only beetles and moths need a checklist file. Diptera (Chandler 2025), Hymenoptera and
  Heteroptera lists put genera alphabetically within family on purpose — UKSI is already
  right below family; just a family sequence (~100 lines) is needed.
- Moths: Agassiz, Beavan & Heckford data on the NHM Data Portal, CC BY-SA 4.0, ABH codes
  sort numerically. Beetles: no open electronic Duff 2018 — type genus order from your own
  copy family by family, or ask Andrew Duff. (Hook change needed: blank species = genus-only.)
- Reports: a 24-row section checklist mapped to what Examen already produces; the gaps are
  mostly methods (survey effort, limitations, species-by-visit, taxonomic coverage) plus
  E6, E8b, E7. 15 winter decisions listed. Read NE 2007 guidance p. 86 ("Suggested report
  format") from your own copy — the online text stops before it.

## Decisions waiting on you (collected)
See each part's "decisions" / "open questions" section: imports (species-lookup behaviour
before C4), saproxylic (list version defaults, thresholds, 1999 paper), photos (P1–P9:
library location, backup, stacked images, videos…), geo (G1–G4: centre vs corner…),
reports (15 winter decisions).

---


<!-- Part 1 -->
# Import wizards: I7b repair plan (scheme, specimen) and C4 merge design

*Groundwork, 9 Oct 2026. Read-only study of the snapshot `/mnt/user-data/uploads/Biological Software/`
(wizard files dated 9 Oct 00:57). Nothing has been run against observatum.db. The SQL in §1.4 was
checked for syntax and logic on an in-memory DB built from `scripts/reset_database.py`'s
CREATE statements (SQLite 3.45). It was not run against live data.*

**Snapshot caveats.**
1. **The observation import code here is from before the repair.** The import mixin still has the
   whole-record update (:628–672), and `_batch_insert_observations` returns 0 on failure (:285–287). It has no
   `backup_main_only`, `SYNC_UPDATE_FIELDS` or `_note_import_error`. The repair is uncommitted (handover `claude/29_…`).
   The worker is the F37 version (chunked, :904–931). Check names against the live file before copying them.
2. **The snapshot is missing some files that the 8 Oct dump (`_archive/_dump_20261008`) lists:** observation `__init__.py`
   and `wizard_species_mixin.py` (154; read here from the dump), the 2-line `species_match_report.py` shims,
   `src/utils/constants.py` and `views/dialogs/__init__.py`.
3. **Orphans:** 5 files in the dialogs root, 1,732 lines (`validation_worker` 502, `wizard_file_mixin` 239,
   `wizard_pages_mixin` 439, `wizard_species_mixin` 117, `wizard_validation_mixin` 435). They are in the 8 Oct
   dump but not in the snapshot. They are **old copies of the specimen wizard**: difflib gives 0.93/0.89/0.94/0.72
   against the specimen package and 0.13–0.57 against the others. Add the `.bak-` mixin from the handover.
   Archive them all (I8). Port nothing from them.

---

# PART 1 — I7b repair plan: scheme and specimen wizards

## 1.0 Shared pieces to build first (so the fixes import rather than copy)

Rule 2 in CLAUDE.md is "Import, don't copy". The three fixes below need the same five helpers. Put
them in **`shared/import_core.py`**: pure, no Qt, importable by `tests/` like `shared/sqs_derivation`.
This module is also the seed of C4 (Part 2).

```python
CHUNK = 900   # under SQLite's old 999-variable limit; the same as the F37 fix

def chunked_select(db, sql_with_ph, values) -> list      # loops CHUNK at a time; RAISES, never swallows
def table_columns(db, table) -> dict                     # PRAGMA table_info: name -> dflt_value (live schema)

def insert_rows(db, table, records, ref):                # ref(record) -> "row 17 Carabus nemoralis"
    cols = [c for c in table_columns(db, table) if c != "id" and any(c in r for r in records)]
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?'*len(cols))})"
    params = [tuple(r.get(c) for c in cols) for r in records]       # FIXED list, None -> NULL
    try:
        db.execute_main_many(sql, params); return len(params), []   # one transaction
    except Exception:                                               # rolled back -> retry row by row
        ok, fails = 0, []
        for rec, p in zip(records, params):
            try: db.execute_main_write(sql, p); ok += 1
            except Exception as e: fails.append((ref(rec), str(e)))
        return ok, fails                                            # never a silent 0

def taxonomy_for_tvks(db, tvks) -> dict  # tvk -> sort_key, superfamily, subfamily, order_name, family;
    # chunked; subfamily by the genus->subfamily / genus->tribe->subfamily UNION already at
    # specimen validation_worker.py:383-394, rewritten as `sp.tvk IN ({ph})`. RAISES.
def parse_quantity(text) -> (int|None, str|None)  # '12'->(12,None) 'c.20'->(20,'c.20') '5+'->(5,'5+') 'several'->(None,'several')
def read_table_file(path) -> (columns, rows, encoding, delimiter)
    # utf-8-sig, then cp1252, then latin-1 (it never fails, so it goes last), decoding the WHOLE file;
    # newline=''; sniff tab/comma; strip a stray '\ufeff' from columns[0]
```

The repaired observation mixin already has its own versions (row-by-row fallback, `_note_import_error`).
For I7b, leave observation alone. C4 moves it onto these helpers.

Time: **3 h**, including pytest for `parse_quantity`, `read_table_file` (tmp files with a BOM, cp1252,
tab, embedded newline) and `insert_rows` (in-memory DB from `reset_database.CREATE_RECORDING_SCHEME`
with a forced UNIQUE clash).

## 1.1 Scheme wizard (`Observatum/src/views/dialogs/scheme_import_wizard/`)

### S1. No backup before writing
- **Where:** `_do_import` (`wizard_import_mixin.py:83–185`) writes from :132 on with no backup. **Change:**
  do this after `rows_to_import` (:102), as the repaired observation import and `DataEntry/data_entry_widget.py:299` do:
  ```python
  from shared.backup_service import backup_main_only
  if not backup_main_only("pre-scheme-import"):
      QMessageBox.critical(self, "Backup failed", "No backup could be made, so nothing was imported.")
      return
  ```
- **Risk:** low. The DB copy takes a few seconds with the UI frozen, so set the status label first.

### S2. F33: the batch INSERT takes its columns from row 0
- **Where:** `wizard_import_mixin.py` `_batch_insert_records` :330–382.
  ```python
  first_data = {k: v for k, v in records[0].items() if v is not None}     # :345
  columns = list(first_data.keys())                                          # :346
  ...
  data = {k: v for k, v in record.items() if v is not None}                 # :353
  values = tuple(data.get(c) for c in columns)                               # :355
  ```
  A column that is empty in a batch's first row is dropped for all 500 rows in that batch. The batch
  fallback (:375–382) goes through `_insert_record`, which filters per row and so is correct. Only
  batches that succeeded were damaged. There is a second, hidden effect: a column that is *present* in
  row 0 gets NULL, not its schema default, in later rows that lack it (`basis_of_record` 'HumanObservation',
  `occurrence_status` 'present'). The defaults are therefore already applied inconsistently. Also, `return result if
  result else len(params_list)` (:363) would count a 0 rowcount as success.
- **Change:** replace the body with `insert_rows(self.db, "recording_scheme", records, ref)`. The column
  list then comes from `PRAGMA table_info`, which is fixed. Collect the failures (S3). Delete
  `_insert_record` (:311–328) or keep it unused. For the two default-bearing text columns, decide once:
  either pass `None` as "not supplied" or fill the default in `_row_to_record_dict`. Only the
  scheme/observation table models display them (`scheme_record_model.py:69–70`), so NULL is
  harmless. I recommend NULL, which states honestly that the column was not supplied.
- **Risk:** low. All 77 dict keys exist in `recording_scheme` (checked against `reset_database.py`).
  Columns the import never writes: `record_type, project_name, client, embargo_status, embargo_until,
  never_upload_to_irecord`. They take their defaults as before.

### S3. Batch failures are printed, not shown
- **Where:** `_insert_record` prints at :327, `_batch_insert_records` at :376, `_update_record` at :401.
  `_do_import` only counts `error_count` (:142, :161). The summary shows a number but no reason.
- **Change:** use the same pattern as the observation `_note_import_error`. Keep
  `self._import_errors = [(row_number, species, message)]`, fill it from `insert_rows`' failures and
  from the update path, show the first 20 on the summary page, and offer "Save error list…"
  (CSV beside the source file). Write the import's own report line into each row's `import_notes`
  only for rows that were written.
- **Risk:** none to data.

### S4. The update path rewrites every non-empty field (a milder F32)
- **Where:** `_update_record` :384–402. It runs only when "Update duplicates" is ticked (:91, :119).
  ```python
  update_data = {k: v for k, v in record_data.items()
                if k not in preserve_fields and v is not None}     # :389-390
  query = f"UPDATE recording_scheme SET {set_clauses} WHERE id = ?"   # :396
  ```
  It does not blank (None is skipped). But several values are never None, so they are always
  overwritten: `quantity` (`row.quantity or 1`, :260), `date_type` ('D'), `zero_abundance`, `sensitive`
  (NBN rows never supply it, so it is reset to 0), `sync_status` ('synced'), `source`, and
  `import_notes`. `import_notes` is replaced by "Duplicate found (ID: n)" (`validation_worker.py:1245`), which loses the
  original notes. Any local edit to species, site or recorder is overwritten from the file. There is no change detection,
  so every duplicate counts as "updated".
- **Change:** use the observation model. Add `SCHEME_UPDATE_FIELDS`: verification_status, verification_status_2,
  verifier, verified_on, automated_checks, species_name, species_tvk, common_name, taxon_rank,
  order_name, family, subfamily, superfamily, taxonomic_sort_key, determiner, comment, images,
  licence, last_edited_date. UPDATE only the fields in that set whose new value is non-empty **and**
  differs from the stored one. Return 'unchanged' when nothing differs. Append to `import_notes` rather than replace it.
  Do not reset `sensitive`, `quantity` or `date_type`. If the stored `irecord_id` is NULL and the
  duplicate was found by `record_key` (S5), set `irecord_id` as well. This repairs F33/BOM losses on re-import.
- **Risk:** medium. Ask Wil which fields a re-import should be allowed to change. With a narrow
  set, a corrected record in the source (e.g. a new grid ref) no longer flows through. That is the same trade-off
  as observations.

### S5. F35: duplicate checks fail silently, aren't chunked, and ignore the file itself
- **Where:** `validation_worker.py` `_batch_duplicate_check` :989–1042.
  ```python
  placeholders = ",".join(["?" for _ in irecord_ids])                       # :1003 one IN, unchunked
  ...
  except Exception:
      pass                                                                   # :1015-1016 (irecord)
  ...
  except Exception:
      pass                                                                   # :1039-1040 (nbn)
  ```
  `recording_scheme.irecord_id` is `INTEGER UNIQUE`, but `nbn_atlas_id` has no index at all
  (`reset_database.py:291–310`, index list :566–573). If the iRecord lookup fails, every batch then hits the
  UNIQUE constraint. With S2/S3 in place that becomes row-by-row and loud, but slow. A failed NBN lookup
  **re-imports the whole file**. Two rows of the same file with the same id are never compared:
  iRecord → the second fails UNIQUE; NBN → both are inserted.
- **Change:**
  ```python
  KEYS = {IRECORD: [("irecord_id", "irecord_id"), ("record_key", "record_key")],  # 2nd catches lost ids
          NBN_ATLAS: [("nbn_atlas_id", "nbn_atlas_id")], GENERIC_CSV: []}
  for df_col, db_col in KEYS[self.import_mode]:
      vals = <non-empty df[df_col] values of rows not yet duplicate>
      rows = chunked_select(self.db_manager,                                         # raises
               f"SELECT id, {db_col} FROM recording_scheme WHERE {db_col} IN ({{ph}})", vals)
      <map back as now>
      df.loc[<non-empty> & df.duplicated(df_col, keep="first"), "file_duplicate_of"] = <first row no.>
  ```
  In `run()` (:393), wrap the call. **On exception, emit a failure and stop**: add a `failed = Signal(str)`
  and have the wizard show it and stay on the validation page. Rows marked `file_duplicate_of` become
  WARNING "Same record as row N in this file". They are skipped at import unless the user ticks a box.
  GENERIC_CSV has no ids. Add a content-key warning (species_tvk+date+grid_ref+recorder), chunked
  the same way, as a warning only.
  **Optional (needs Wil's agreement, schema change):** `CREATE UNIQUE INDEX idx_scheme_nbn ON
  recording_scheme(nbn_atlas_id) WHERE nbn_atlas_id IS NOT NULL`. 8 Oct found no duplicate
  `nbn_atlas_id`, so it would apply cleanly. Add it to `reset_database.py` too.
- **Risk:** low for the code. Before the `record_key` fallback can be relied on, confirm with M4
  that iRecord `record_key` = 'iBRC' + ID.

### S6. F34: sort key and superfamily are computed but fail silently; subfamily is never computed; manual picks go stale
- **Where:** `validation_worker.py` `_enrich_sort_and_superfamily` :939–987 is batched, which is good:
  ```python
  except Exception:
      pass                                                                   # :975-976
  ```
  One failure loses a 500-TVK batch. Subfamily comes only from iRecord's `Subfamily` column (:463).
  NBN and generic rows never get one. Manual species picks (`wizard_validation_mixin.py:252–256`) set
  `species_tvk` but leave the sort key, superfamily, order and family belonging to the *old* TVK (or empty).
  "Revalidate" cannot fix this: `_revalidate_edited_rows` :299–343 runs a worker synchronously,
  then zips `worker.rows`, its *input*, back into the table (:324). The rebuilt rows the worker
  makes in `_build_import_rows` are discarded, so revalidation is a no-op.
- **Change:** recompute the taxonomy **at import time, from each row's final TVK**:
  `tax = taxonomy_for_tvks(self.uksi_model.db, tvks_of(rows_to_import))`, set on each row before
  `_row_to_record_dict`. Prefer UKSI over the file for subfamily, and fall back to the file's
  value. If the call raises, show "Taxonomy lookup failed: N rows would import without sort key"
  with Cancel / Import anyway. List rows that have a TVK but no key in the S3 error panel. Fix the revalidate no-op
  by connecting to the worker's `finished` list (or reading the return of `_build_import_rows`). Leave the
  validation-time enrichment as display only.
- **Risk:** low. The scheme's sort key is used only for export order (`recording_scheme_tab.py:659, :689`)
  and the subfamily column display.

### S7. BOM and encoding order lose every iRecord ID
- **Where:** `wizard_file_mixin.py` `_load_file_preview` :218–282.
  ```python
  encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']                    # :225
  ...
  lines = content.strip().split('\n')                                        # :242
  reader = csv.DictReader(lines)                                             # :243
  ```
  Plain `utf-8` decodes a BOM file without error, so the first header becomes `'\ufeffID'` (confirmed
  with `csv.DictReader`). Every `raw.get('ID')` (:450) is then '' and so `irecord_id` is None. `cp1252` is
  unreachable after `latin-1`. Splitting on '\n' turns an embedded CRLF in a quoted Comment into a lone
  '\r' (tested: `'a\r\nb'` → `'a\rb'`).
- **Change:** `self.columns, self.raw_rows, self._file_encoding, _ = read_table_file(self.file_path)`.
- **Risk:** low. Format detection (:284–) then sees the real `ID` column, which can only help.

### S8. Quantities: "c.20" becomes 1, and `individual_count` is never stored
- **Where:** `validation_worker.py`. iRecord :488, NBN :589 and generic :647 all do
  `"quantity": self._parse_int(...) or 1`. `_parse_int` (:1339–1346) is `int(float(str(value)))`, which
  turns 'c.20' or '5+' into None and so 1. The row builder repeats `or 1` (:1139). For NBN, `individualCount` goes
  into `quantity`, but the extractor never sets `individual_count`, so `_safe_int(row_data,
  "individual_count")` (:1140) is always None.
- **Change:** `q, raw = parse_quantity(text)`; `quantity = q if q is not None else 1`. When `raw` is
  set, store it in `organism_quantity` if that is empty, and add a note: "Count 'c.20' stored as 20". For NBN, also
  set `individual_count = q`.
- **Risk:** low. It changes figures only for rows whose counts were mangled.

### S9. Small issues in the same files
- `_do_import` :95–100 drops duplicates before the loop at :117–122 that counts them, so
  "Skipped duplicates" is always 0. Count them in the first loop.
- Exceptions in the species lookup are swallowed at :803–804 (cf./agg. retry). Record
  `species_lookup[name] = {"error": f"UKSI lookup error: {e}"}` as Step 2 already does (:740–741).
- `SchemeImportRow` (:155–296) declares ~20 fields twice (e.g. `irecord_id: str = ""` then
  `Optional[int] = None`). The last one wins. It is harmless but misleading, so clean it in C4.

## 1.2 Specimen wizard (`Observatum/src/views/dialogs/specimen_import_wizard/`)

There is **no update path** (insert only), so nothing like F32 exists here. The batch dict is a literal
with the same 26 keys every time (`specimen_import_wizard.py:364–391`), so nothing like F33 exists either.
The failures are elsewhere.

### P1. No backup
`specimen_import_wizard.py` `_do_import` :315–419. Same change as S1, label "pre-specimen-import",
placed after `rows_to_import` (:334).

### P2. One bad row loses its whole 500-row batch, silently
- **Where:** `_batch_insert_specimens` :421–463.
  ```python
  except Exception as e:
      print(f"[SpecimenImportWizard] Batch insert error: {e}")
      return 0                                                               # :461-463
  ```
  `specimen_code` is `TEXT UNIQUE` (`reset_database.py:256`). Re-importing a file, or a file that repeats a
  code, fails the whole batch. All 500 rows count as "errors", with the reason only on the console.
- **Change:** `inserted, fails = insert_rows(self.db, "specimens", insert_batch, ref)`, and send the failures
  to the summary's error panel as in S3.
- **Risk:** none.

### P3. No duplicate check at all
- **Where:** the worker pipeline `run()` :121–173 has no duplicate step. The wizard has no skip/update option.
- **Change:** add `_batch_duplicate_check`. Run `chunked_select("SELECT id, specimen_code FROM
  specimens WHERE specimen_code IN ({ph})", codes)`, which raises (stop validation loudly as in S5). Add
  within-file `df.duplicated("specimen_code")`. Such rows become ERROR "Code already in the collection (id N)"
  and are not imported. For rows without a code, warn only on species_tvk+date_collected+grid_ref+collector.
- **Risk:** low.

### P4. F35 #3 and F34: sort-key failures and every manual species pick leave the specimen invisible
- **Where (validation):** `validation_worker.py` :365–421 runs one UKSI query **per row** inside the apply loop:
  ```python
  sc = sc_result[0] if sc_result else None
  if sc:
      df.at[idx, "taxonomic_sort_key"] = compute_taxonomic_sort_key(sc[1] or '', sc[0] or 0)
  ...
  except Exception:
      pass                                                                   # :421-422
  ```
  An exception, or a TVK not present in `taxa`, leaves the key NULL with no warning. The second case is
  the likeliest: an **alias saved before the UKSI 2025 update** still carries the old `uksi_tvk`
  (:242). Rows with a NULL key are invisible in the Insect Collection sidebar (`WHERE taxonomic_sort_key IS
  NOT NULL`, the 244-specimen fault in `06_Faults.md`).
- **Where (manual paths, never covered):** these all set `species_tvk` and never recompute the key, superfamily,
  subfamily or taxon_group:
  - `wizard_species_mixin.py` `_apply_species_resolutions` :87–118 (bulk resolution, :97–101)
  - `wizard_validation_mixin.py` `_on_table_double_clicked` :284–312 (:297–305)
  - `wizard_validation_mixin.py` `_on_cell_double_clicked` :314– (:325–330)
  - `wizard_validation_mixin.py` `_revalidate_single_row` :369– (:381–385)

  A row that was "Species not found" and then resolved by hand has a key of None. One that was matched and
  then re-picked keeps the **old** species' key, so it is filed in the wrong place.
- **Change:** as S6, recompute at import time from the final TVK with `taxonomy_for_tvks` (batched),
  for every row, just before the record dict (:364). Then, **as a gate**: if any row to import has no
  `taxonomic_sort_key`, show "N specimens would not appear in the collection sidebar: [list]"
  with Cancel / Import anyway (and if you import anyway, run `scripts/backfill_sort_keys.py`). Remove the
  per-row block at :365–421, keeping only display-time taxonomy (or call the batched helper once in
  the worker). Import `ORDER_TO_GROUP` rather than keep the inline copy at :400–419. The observation worker
  has its own copy, and the C4 home for it should be `shared/import_core`.
- **Risk:** low. This is the most valuable fix in the specimen half.

### P5. Smaller items
- The fuzzy lookup is not guarded: `validation_worker.py:272` `results = self.uksi_model.search_species(name, limit=1)`.
  An exception escapes `run()`, `finished` is never emitted, and the wizard hangs on the validation page.
  Wrap it and record a per-name error, as the scheme does at :740.
- Encoding: `wizard_file_mixin.py:51, :59` accept utf-8-sig only, so a cp1252 file fails, though loudly.
  Use `read_table_file`.
- `specimens.sex` is never written. `ImportRow` (:69–97) has no sex and the mapping offers none. This is a feature
  gap rather than a fault: note it for A1.
- The specimen worker has no quantity, so the "c.20" problem does not apply here.

## 1.3 Observation wizard: what is left after the 9 Oct repair (for the record only)
- **F34 (obs):** `validation_worker.py:1046–1093` uses `self.uksi_conn`, which is never set. Per the sweep, nothing
  reads these fields for observations, so the cost is nil. In C4, swap it for `taxonomy_for_tvks`.
- **Personal duplicate check** :978–1016 runs one query per key inside `except: pass` (:1002–1003).
  The handover says "adds an unskipped duplicate (no overwrite)". Check whether the repair also made
  this lookup loud.
- **Lat/long derivation** :1027–1042 uses the local `_osgb36_to_wgs84` (:297), which has no Helmert step
  (F30, ~110 m). C4 must call `grid_converter_service` (I3c), not carry this forward.
- **Observatum key sequence:** `wizard_import_mixin.py:571–572` falls back to 0 on a DB error. It uses
  4-digit `:04d` (:577) against the model's 6-digit keys, and finds the "last key" by string sort.

## 1.4 Read-only measurement (run before any repair)

Open read-only: `sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)`. Every column
below exists in `reset_database.py` (`recording_scheme`: irecord_id, record_key, nbn_atlas_id,
occurrence_id, dataset_name, source, comment, verifier, latitude, determiner, site_name,
sample_comment, verification_status, taxonomic_sort_key, superfamily, subfamily, quantity,
organism_quantity, individual_count, created_at. `specimens`: taxonomic_sort_key, superfamily,
subfamily, species_tvk, import_notes, created_at). Run M1 first, because the live schema may differ.
There is no import-batch column, so a **session** is rows whose `created_at` is less than 5 minutes after the previous row.
A **block** is 500 consecutive ids within a session, which is the batch unit. A failed `executemany` rolls back
its AUTOINCREMENT, so ids stay contiguous.

```sql
-- M1  Live schema: is irecord_id UNIQUE, and does anything index nbn_atlas_id?
SELECT 'rs', name, "unique", origin FROM pragma_index_list('recording_scheme')
UNION ALL SELECT 'sp', name, "unique", origin FROM pragma_index_list('specimens');

-- M2  Import sessions in recording_scheme
WITH r AS (SELECT id, created_at,
             CASE WHEN LAG(created_at) OVER (ORDER BY id) IS NULL
                    OR (julianday(created_at) - julianday(LAG(created_at) OVER (ORDER BY id)))*1440 > 5
                  THEN 1 ELSE 0 END AS brk FROM recording_scheme),
     s AS (SELECT id, SUM(brk) OVER (ORDER BY id) AS sess FROM r)
SELECT s.sess, MIN(rs.created_at) started, COUNT(*) n, MIN(rs.id) first_id, MAX(rs.id) last_id,
       SUM(rs.record_key LIKE 'iBRC%') ibrc_rows, SUM(rs.irecord_id IS NOT NULL) with_irecord_id,
       SUM(rs.nbn_atlas_id IS NOT NULL) with_nbn_id, SUM(rs.latitude IS NOT NULL) with_lat,
       SUM(rs.comment IS NOT NULL) with_comment, SUM(rs.verifier IS NOT NULL) with_verifier,
       SUM(rs.taxonomic_sort_key IS NULL) no_sort_key
FROM s JOIN recording_scheme rs ON rs.id = s.id GROUP BY s.sess ORDER BY s.sess;

-- M3  F33 fingerprint: blocks in which a column is empty in EVERY row while the rest of the
--     session has it. est_values_lost = block rows x the session's rate in its other blocks.
WITH r AS (...same as M2...), s AS (...same as M2...),
b AS (SELECT s.sess, (s.id - MIN(s.id) OVER (PARTITION BY s.sess))/500 AS blk, rs.*
      FROM s JOIN recording_scheme rs ON rs.id = s.id),
c AS (SELECT sess, blk, 'comment' col, COUNT(*) n, SUM(comment IS NOT NULL) have FROM b GROUP BY sess, blk
      UNION ALL SELECT sess, blk, 'verifier', COUNT(*), SUM(verifier IS NOT NULL) FROM b GROUP BY sess, blk
      UNION ALL SELECT sess, blk, 'latitude', COUNT(*), SUM(latitude IS NOT NULL) FROM b GROUP BY sess, blk
      UNION ALL SELECT sess, blk, 'irecord_id', COUNT(*), SUM(irecord_id IS NOT NULL) FROM b GROUP BY sess, blk
      UNION ALL SELECT sess, blk, 'nbn_atlas_id', COUNT(*), SUM(nbn_atlas_id IS NOT NULL) FROM b GROUP BY sess, blk
      UNION ALL SELECT sess, blk, 'determiner', COUNT(*), SUM(determiner IS NOT NULL) FROM b GROUP BY sess, blk),
      -- add site_name, sample_comment, verification_status... the same way
t AS (SELECT sess, col, SUM(have) sess_have, SUM(n) sess_n FROM c GROUP BY sess, col)
SELECT c.sess, c.col, COUNT(*) empty_blocks, SUM(c.n) rows_in_empty_blocks,
       ROUND(1.0*t.sess_have/NULLIF(t.sess_n - SUM(c.n),0),3) session_rate,
       ROUND(SUM(c.n)*1.0*t.sess_have/NULLIF(t.sess_n - SUM(c.n),0)) est_values_lost
FROM c JOIN t ON t.sess=c.sess AND t.col=c.col
WHERE c.have = 0 AND c.n > 1 AND t.sess_have > 0
GROUP BY c.sess, c.col ORDER BY est_values_lost DESC;

-- M4  iRecord rows that lost their iRecord ID (F33, or the BOM fault when a whole session lacks it).
--     First confirm the key format (expect agree = checked):
SELECT COUNT(*) checked, SUM(CAST(substr(record_key,5) AS INTEGER) = irecord_id) agree
FROM recording_scheme WHERE record_key LIKE 'iBRC%' AND irecord_id IS NOT NULL;
SELECT substr(a.created_at,1,10) day, COUNT(*) lost_id,
       SUM(EXISTS(SELECT 1 FROM recording_scheme b
                  WHERE b.irecord_id = CAST(substr(a.record_key,5) AS INTEGER))) also_held_with_id
FROM recording_scheme a WHERE a.irecord_id IS NULL AND a.record_key LIKE 'iBRC%'
GROUP BY day ORDER BY day;          -- also_held_with_id > 0 = re-imported copies (dup check defeated)

-- M5  Duplicate keys
SELECT 'nbn_atlas_id' k, COUNT(*) keys_shared, SUM(c) rows_involved FROM
  (SELECT COUNT(*) c FROM recording_scheme WHERE nbn_atlas_id IS NOT NULL GROUP BY nbn_atlas_id HAVING c > 1)
UNION ALL SELECT 'dataset+occurrence_id', COUNT(*), SUM(c) FROM
  (SELECT COUNT(*) c FROM recording_scheme WHERE occurrence_id IS NOT NULL GROUP BY dataset_name, occurrence_id HAVING c > 1)
UNION ALL SELECT 'record_key', COUNT(*), SUM(c) FROM
  (SELECT COUNT(*) c FROM recording_scheme WHERE record_key IS NOT NULL GROUP BY record_key HAVING c > 1)
UNION ALL SELECT 'content', COUNT(*), SUM(c) FROM
  (SELECT COUNT(*) c FROM recording_scheme
   GROUP BY species_tvk, date, grid_ref, recorder, source, sex, stage HAVING c > 1);

-- M6  Taxonomy completeness, all three tables
SELECT 'recording_scheme' t, COUNT(*) n, SUM(taxonomic_sort_key IS NULL) no_key,
       SUM(taxonomic_sort_key IS NULL AND species_tvk IS NOT NULL) no_key_but_tvk,
       SUM(COALESCE(superfamily,'')='') no_superfamily, SUM(COALESCE(subfamily,'')='') no_subfamily
FROM recording_scheme
UNION ALL SELECT 'specimens', COUNT(*), SUM(taxonomic_sort_key IS NULL),
       SUM(taxonomic_sort_key IS NULL AND species_tvk IS NOT NULL),
       SUM(COALESCE(superfamily,'')=''), SUM(COALESCE(subfamily,'')='') FROM specimens
UNION ALL SELECT 'observations', COUNT(*), SUM(taxonomic_sort_key IS NULL),
       SUM(taxonomic_sort_key IS NULL AND species_tvk IS NOT NULL),
       SUM(COALESCE(superfamily,'')=''), SUM(COALESCE(subfamily,'')='') FROM observations;

-- M7  Invisible specimens, and the route they came in by (P4)
SELECT substr(created_at,1,10) day,
       CASE WHEN import_notes LIKE '%bulk lookup%' THEN 'bulk-resolved'
            WHEN import_notes LIKE 'Alias:%'      THEN 'alias'
            WHEN import_notes LIKE '%Fuzzy%'      THEN 'fuzzy'
            WHEN import_notes IS NULL            THEN 'no notes'
            ELSE 'other' END route,
       COUNT(*) n, SUM(COALESCE(species_tvk,'')='') no_tvk
FROM specimens WHERE taxonomic_sort_key IS NULL GROUP BY day, route ORDER BY day;

-- M8  Quantity (S8): text next to a fallback 1, and individual_count (expect 0)
SELECT SUM(quantity = 1 AND organism_quantity IS NOT NULL AND organism_quantity NOT IN ('1','1.0')) q1_text,
       SUM(individual_count IS NOT NULL) ind_count FROM recording_scheme;
```
In M3, write out the `r`/`s` CTEs in full as in M2. The complete, tested text of M1–M8 is in `scratchpad/tools/measure_imports.sql`. Already known from 8 Oct: no duplicate
`nbn_atlas_id`, and 2 specimens without a key (the A5 pair). M3/M4 are new and are the F33 numbers. "c.20" losses
on iRecord rows can't be measured from the DB: `quantity` was stored as 1 and the text was not kept. That needs a
re-read of the source files.

**Repair of existing damage (after the code fix, dry run first, backup, Wil's go-ahead):**
- lost `irecord_id` where M4 shows agreement and no collision: fill it from `record_key`;
- F33-dropped comment, verifier and lat/long: re-read the original files and fill only the NULL cells,
  matched on irecord_id/record_key/nbn_atlas_id;
- specimens: `scripts/backfill_sort_keys.py` (exists).

## 1.5 Build checklist (in order)

| # | Step | Est. |
|---|---|---|
| 0 | Run M1–M8 on the live DB, record the figures in `02`, add any new fault to `06` | 0.5 h |
| 1 | `shared/import_core.py` (chunked_select, table_columns, insert_rows, taxonomy_for_tvks, parse_quantity, read_table_file) and pytest | 3 h |
| 2 | Scheme S1 backup, S2 fixed columns, S3 error panel | 1.5 h |
| 3 | Scheme S5 duplicate checks: chunked, loud, within-file, `record_key` fallback | 1.5 h |
| 4 | Scheme S6 import-time taxonomy, the revalidate no-op, S7 reader, S8 quantity, S9 | 2 h |
| 5 | Scheme S4 targeted update (after Wil chooses the field set) | 1 h |
| 6 | Specimen P1, P2, P3 | 1.5 h |
| 7 | Specimen P4 import-time taxonomy and the sidebar gate; P5 | 1.5 h |
| 8 | Import every changed module; dry-run on a `conn.backup()` copy with real files (§2.6 list), before/after counts; `check_reference_figures.py` | 3 h |
| 9 | Repair scripts for existing damage (dry run → Wil → backup → apply) | 2 h |
| 10 | Docs: `06` F33–F35 status, `03` I7b → done, `02` figures | 0.5 h |
| | **Total** | **≈ 2.5 days** (the backlog's "~1 day" did not include the specimen manual paths or the scheme update path) |

---

# PART 2 — C4: merge the three wizards

## 2.1 Inventory (snapshot, plus files that exist only in the dump)

| Role | Observation | Scheme | Specimen |
|---|---|---|---|
| Wizard class / nav | `observation_import_wizard.py` 630 | `scheme_import_wizard.py` 424 | `specimen_import_wizard.py` 546 (also holds import) |
| Pages mixin | 933 | 779 | 459 |
| File mixin | 422 | 485 | 266 |
| Validation mixin | 548 | 425 | 569 |
| Import mixin | 708 | 422 | — (in wizard :315–463) |
| Species mixin | 154 (dump) | — | 127 |
| Validation worker | 1,271 | 1,355 | 567 |
| Table model | — (QTableWidget, `_populate_table_row`) | 172 | 146 |
| Dialogs | `UpdatePreviewDialog` (in import mixin) | `DuplicatePreviewDialog` (in import mixin) | `bulk_resolution_dialog.py` 504, `species_search_dialog.py` 217 |
| `__init__` / shim | 42 + 2 | 41 + 2 | 19 + 2 |
| **Total** | **≈ 4,710** | **≈ 4,105** | **≈ 3,420** |

That is ≈ 12,240 lines, plus 1,732 orphan lines, plus the shared `species_match_report_dialog.py` (451). The steps:
observation 7 (Mode, File, Map, Validate, Confirm, Import, Summary); scheme 7 (same names); specimen 5
(File, Map, Validate, Import options, Summary).

## 2.2 What is identical, what has drifted, what is genuinely per mode

Measured with `difflib.SequenceMatcher` on whitespace-stripped lines, per function (AST-extracted)
and per file. Ratio 1.00 = identical.

**Identical or nearly (≥ 0.90): merge mechanically.**
- obs↔scheme pages: `_create_import_page` 1.00, `_create_summary_page` 1.00, `_create_stat_card` 1.00,
  `_create_column_mapping_page` 0.97, ModeCard (`__init__` 0.98, `_update_style` 0.94,
  `_update_indicator` 0.94), `_create_file_selection_page` 0.92, `_create_validation_page` 0.91. The
  pages-mixin files overall are 0.70, with 599 shared lines.
- All three: `_init_vc_service` 1.00, `cancel` 1.00, `_go_back` 0.83–1.00.
- obs↔specimen: `_export_problems` 0.98, `_get_column_mapping` 1.00.
- scheme↔specimen table models: file 0.69. `rowCount`, `columnCount`, `headerData` and
  `set_theme_colors` 1.00; `data` 0.82; `flags` 0.84.

**Drifted (0.2–0.8): same job, different behaviour. Each needs a decision, not a merge.**
- `_batch_species_lookup` obs↔sch 0.38, obs↔spe 0.31, sch↔spe 0.31 (see 2.3)
- `_normalize_species_name` sch↔spe 0.83, obs↔either 0.21: obs uses `cf\.\s+` IGNORECASE; the others
  use `cf\.?\s+`, case-sensitive
- `_batch_vc_lookup` 0.33–0.41; `run` 0.59–0.69; `_find_vc_database` 0.65–0.71
- `_parse_date` 0.28–0.64 (scheme 49 lines, obs 16, specimen 9): three date parsers
- `_do_import` 0.37–0.66; `_combine_import_notes` obs↔sch 0.70 (obs adds `[Warning: …]` only for
  WARNING status; scheme adds `error_message` for any status)
- file loading: obs↔spe 0.73 (both use utf-8-sig and sniff the delimiter); scheme 0.21 (S7)
- validation mixins overall 0.17–0.22: cell edit, double-click, revalidate and filter are all
  different. Scheme's revalidate is a no-op (S6), and specimen's re-matches without taxonomy (P4).
- `_safe_get` obs↔sch 0.89; `_parse_int`/`_parse_float` obs↔sch 0.75

**Genuinely per mode (keep, as adapters):** the extractors (obs iRecord/personal; scheme iRecord/NBN/generic;
specimen mapping). The iRecord header names are written twice (obs :465–536, scheme :436–516), so make them one
`IRECORD_COLUMNS`. The rest: the row→record dicts (obs ≈90 keys plus commercial/embargo/`observatum_key`; scheme 77;
specimen 26); the duplicate strategy (obs iRecord ID|irecord_key plus F37/F38 twins, :884–1016, complexity 44;
obs personal species+date+grid; scheme irecord_id/nbn_atlas_id; specimen none); the update policy (obs sync
fields; scheme all non-None; specimen none). Only obs has the commercial/embargo confirmation page (158 vs 80 lines,
0.11) and `SYNC_LAST_SYNC`. Only specimen has bulk resolution and alias saving.

## 2.3 The species lookup, three times (radon cyclomatic complexity: obs 67, scheme 54, specimen 71)

| | Observation `validation_worker.py:635–827` | Scheme `:671–849` | Specimen `:213–429` |
|---|---|---|---|
| Names looked up | iRecord: only rows with no TVK; personal: all | all with a name (iRecord TVKs re-checked) | all |
| Saved aliases | yes, but the exact match then **overwrites** them (:678) | no | yes, with precedence (`remaining`, :252) |
| Exact batch `get_species_batch` | yes | yes | yes |
| Fuzzy `search_species(limit=1)` for the unmatched | **no** (only if `get_species_batch` is missing) | yes, warns "Matched to …" | yes, **unguarded** (:272) |
| cf./agg. retry | yes (sensu lato/aggregate SQL) | yes (same SQL, copied) | yes (same SQL, copied) |
| Lookup exception | swallowed → "Species not found" | Step 2: "UKSI lookup error"; Step 3 swallowed | Step 2 escapes `run()`; Step 3 swallowed |
| Applying fields | overwrite | **fill-if-empty** (keeps the file's order/family); notes "TVK normalized a→b" | overwrite |
| Fields | tvk, common, order, family, kingdom, group, rank | + phylum, class, genus | tvk, common, order, family (+ sort key, superfamily, subfamily, group inline) |
| `species_name` | kept | kept | **replaced by matched name** |
| Not found | ERROR (personal) / WARNING (sync) | ERROR (any mode) | ERROR |

`get_species_batch` (`models/uksi.py:626–691`) itself does one unchunked `IN` over every name and
swallows its exception (:689–690). If that fails, observation reports *every* species "not found", and
the other two fall back to one fuzzy query per name. Synonyms are reached only through
`search_species` (:249–330), so observation personal uploads never match on a synonym.

**Decisions Wil must make before merging (these are behaviour, not code):** fuzzy auto-accept or not
(observation never does it; the others do); whether to fill from the file or overwrite from UKSI;
whether `species_name` becomes the UKSI name (only specimen does this); whether aliases win over exact
matches; and whether "not found" in sync mode is a warning or an error.

## 2.4 Proposed architecture

```
shared/import_core/                 # pure, no Qt, under pytest (grows out of I7b's import_core.py)
  reader.py      read_table_file (encoding, BOM, delimiter, newline='')
  values.py      parse_date (one, from scheme's), parse_int/float, parse_quantity,
                 normalize_species_name (one regex), IRECORD_COLUMNS, ORDER_TO_GROUP
  species.py     SpeciesMatcher(uksi_db, aliases, policy).match(names) -> {name: Match}
                 Match = tvk, matched_name, taxonomy dict, route ('alias'|'exact'|'synonym'|
                 'fuzzy'|'agg'|'cf'), warning, note, error.  Policy = MatchPolicy(fuzzy, alias_wins,
                 fill_mode, rename, missing_is_error). Batched in chunks of 900; raises on DB error.
  taxonomy.py    taxonomy_for_tvks (sort key, superfamily, subfamily, order, family, group)
  geo.py         thin call into grid_converter_service + VC lookup (I3c: one converter)
  dedupe.py      KeyStrategy: IRecordKeys(id | irecord_key/record_key, F37/F38 twin rule),
                 NbnKeys(nbn_atlas_id, then dataset+occurrence_id), SpecimenCodeKeys,
                 ContentKeys(fields) ; within-file duplicates ; chunked_select (raises)
  writer.py      insert_rows (PRAGMA columns, executemany → row-by-row, failures returned),
                 update_fields(table, id, new, allowed, never_blank=True) -> 'updated'|'unchanged'
  pipeline.py    validate(raw_rows, adapter, mode, mapping, services) -> list[ImportRow]
                 run_import(rows, adapter, db, options) -> ImportResult(inserted, updated,
                 unchanged, skipped, failures)   # backup_main_only first; aborts if it fails
Observatum/src/views/dialogs/import_wizard/      # Qt only
  base_wizard.py      ImportWizardBase(QDialog): step stack/nav/progress/summary/error panel
  pages.py            mode cards, file, mapping, validation, import, summary (from obs/sch ≥0.9)
  validation_view.py  one QAbstractTableModel (scheme/specimen) + filter + edit + revalidate
                      (re-runs pipeline on edited rows and KEEPS its output)
  species_dialogs.py  SpeciesSearchDialog + BulkSpeciesResolutionDialog (from specimen) → all three
  worker.py           ValidationWorker(QThread) wrapping pipeline.validate; failed = Signal(str)
  adapters/observation.py  scheme.py  specimen.py
```

**The adapter contract** (one class per wizard, ~150–350 lines each):
```python
class ImportAdapter(Protocol):
    table: str                                   # 'observations' | 'recording_scheme' | 'specimens'
    modes: list[ModeSpec]                        # id, label, detect(columns)->score, extract(raw, mapping)->dict
    mapping_fields: list[FieldSpec]              # for the mapping page (generic/personal/specimen)
    def match_policy(self, mode) -> MatchPolicy
    def key_strategies(self, mode) -> list[KeyStrategy]
    def build_record(self, row: ImportRow, ctx) -> dict      # was _row_to_*_dict
    update_fields: frozenset | None              # None = insert only (specimen)
    extra_pages: list[PageSpec]                  # obs: commercial/embargo confirmation
    def after_import(self, result, ctx): ...     # obs: SYNC_LAST_SYNC; specimen: sidebar gate
    import_gate(rows) -> list[str]               # specimen: rows with no sort key
```
`ImportRow`: one dataclass with the common fields the views use as attributes (row_number, raw,
status, errors, warnings, notes, species_name, species_tvk, common_name, order_name, family,
date, grid_ref, site_name, is_duplicate, existing_id, match) plus `extra: dict` for each mode's columns.
That replaces three dataclasses of 30–80 attributes, one of which defines its fields twice.

## 2.5 Migration sequence (each step leaves all three wizards working)

0. **I7b first** (Part 1). Retire the orphans and the `.bak-` mixin to `_archive` (I8).
1. **Goldens.** `scripts/import_golden.py` (READ ONLY) runs each wizard's current worker synchronously under a
   `QCoreApplication` (as scheme revalidate already does) on each real file. It dumps status, tvk, matched name,
   warnings and duplicate id to CSV. Every later step re-runs it and diffs, and each difference must be intended.
2. **`values.py` and `reader.py`.** Switch all three to one reader, one date parser and one cf./agg.
   parser. Expected golden differences: BOM files (scheme), case-insensitive "CF." (scheme/specimen).
3. **`SpeciesMatcher`.** Port specimen first (most complex, and it has aliases and rename), then scheme, then
   observation, each with its own `MatchPolicy` reproducing today's behaviour. Goldens must not change.
   Only then change the policies to what Wil decided (2.3), one decision per commit.
4. **`taxonomy.py`, `geo.py`, `dedupe.py`, `writer.py`.** Observation drops `_osgb36_to_wgs84`
   (F30/I3c, so a golden change is expected: lat/long ~110 m), and drops its own insert/update helpers for `writer`.
5. **One `ValidationWorker` and `pipeline`** with the three adapters. Retire the three workers
   (≈3,190 lines) to `_archive`.
6. **Shared validation view and table model.** Observation moves from QTableWidget to the model.
   Bulk resolution and the species search dialog become available in all three.
7. **`ImportWizardBase` and `pages.py`.** The three wizard classes become thin subclasses. Retire the per-wizard
   mixins. Expected end state ≈ 4,000–4,500 lines in place of ≈ 12,240.

Each step: import every touched module ("compiling is not importing"), pytest, goldens, then one
real import into a `conn.backup()` copy per wizard, and `check_reference_figures.py`.

## 2.6 Test plan

**pytest (pure, no DB file; in-memory DB from `reset_database` CREATE strings plus a ~30-row
`taxa`/`common_names`/`synonyms` fixture):**
- `normalize_species_name` ("Anthocoris cf. confusus", "A. CF confusus", "Bombus lucorum agg[.]",
  "Bombus (Bombus) lucorum"); `parse_date` (the union of the three parsers' formats); `parse_quantity`
  ('12', '12.0', 'c.20', '5+', '>10', '', 'several', '0'); `read_table_file` (BOM, cp1252, tab, embedded CRLF)
- `SpeciesMatcher`: exact; case; alias vs exact under each `alias_wins`; synonym; fuzzy on/off; cf.;
  agg. → sensu lato; not found; a DB error raises
- `taxonomy_for_tvks`: sort key = `INSECT_ORDER_POSITION[order]*1e6 + sort_code` (imported, not
  restated); subfamily via genus and via tribe; unknown TVK → absent, not None-filled
- `dedupe`: chunking at 900/901/1801 ids; iRecord ID vs irecord_key/record_key; F37 shared external
  key (one id → match, two → no match); F38 twin (same key+species+date); within-file duplicates
- `insert_rows`: a fixed column list when row 0 has Nones (the F33 regression); one UNIQUE clash in 500 →
  499 inserted and 1 reported failure
- `update_fields`: never blanks; ignores fields outside `allowed`; 'unchanged' when equal

**Real files (dry runs into a backup copy, before/after counts):**
- the iRecord download of 8 Oct (20,656 records): re-import → 0 inserts; the same file with a BOM → identical (S7)
- NBN Atlas downloads with Darwin Core and with human-readable headers; re-import → 0 inserts
- a scheme CSV whose **first row has empty comment, verifier and lat/long** (F33); "c.20"/"5+" counts;
  cf./agg./alias/unknown names
- a specimen TSV export of 20 existing specimens → all flagged "code already in collection"; then
  20 new rows including one resolved by bulk lookup → all have `taxonomic_sort_key` and appear in the sidebar
- a file with >900 distinct ids (chunking)

## 2.7 Estimate and risks

| Phase | Days |
|---|---|
| Goldens harness and test files (2.5 step 1, 2.6 files) | 0.75 |
| values/reader + SpeciesMatcher + policies (steps 2–3) | 1.5 |
| taxonomy/geo/dedupe/writer (step 4) | 0.75 |
| Unified worker and pipeline (step 5) | 1 |
| Validation view, table model, dialogs (step 6) | 1 |
| Base wizard and pages (step 7) | 1 |
| Real-import testing and docs | 1 |
| **Total** | **≈ 7 days** (the backlog says 3–5. Steps 1–5 alone, about 4 days, deliver most of the value: one species matcher, one writer, one dedupe. The UI merge in steps 6–7 can wait.) |

**Risks**
- **Behaviour drift hidden as a merge.** The lookups disagree (2.3), so a naive merge changes which TVK records get.
  Guard against it with goldens, one policy per wizard first, then explicit decisions.
- **F37/F38 iRecord matching is the most valuable and most fragile code.** Move it whole into `IRecordKeys`,
  with tests. Re-check on a fresh iRecord download: expect 0 overwritten, as on 8 Oct.
- **Testability.** Workers import `src.*` at module level, and tests must not import views (`05_Rules`). Put all logic in `shared/import_core`.
- **The 9 Oct observation repair is uncommitted.** Commit it before C4, or it will be lost in the move.
- **Schema drift.** The sweep found `specimens.site_name_local` missing from reset's CREATE. `writer` reads `PRAGMA
  table_info`, but check the adapters' dicts against the live schema (M1).
- **F30 lat/long** (step 4) is an intended golden difference. Say so in the commit, together with I3c.
- **Performance.** `get_species_batch` uses an unchunked `LOWER(scientific_name) IN (...)`, which cannot use an index.
  Chunk it, and time a 30k-row NBN file.

---

# E7 groundwork: saproxylic SQI and IEC

9 October 2026. Read-only research. Nothing in the repository or databases has been
changed. This builds on `docs/39_Research_Notes.md` §4 (8 Oct) and does not repeat it.
Database figures come from the snapshot `data/codex.db` (v5.0, built 8 Oct) and
`data/pantheon.db` (Pantheon 3.7.4), opened `?mode=ro`.

---

## 0. What is new since §4 (summary)

1. **khepri.uk contradicts itself on which version it uses.** The home page says *"a list of
   605 saproxylic species"* and IEC grades *"taken from the latest revision (Alexander,
   2024)"*. `/main` says 598 species (596 after two adjustments) and cites the IEC as
   Alexander (2004). Wil's own Cobham report (Kent Downs annex 7n, Nov 2024) used **605 +
   Alexander 2024**. The backlog says 598 + the 2004 list. **Wil needs to choose.** Section 2
   suggests holding both versions.
2. **The IEC list is already in `pantheon.db`, under an open licence.** `fidelity_scores`
   holds `'revised index of ecology continuity score'` (180 rows, Alexander 2004) and
   `'index of ecology continuity score'` (188 rows, Harding & Rose 1986). The `score`
   column holds **points, not the grade**. I checked this against known species:
   *Limoniscus violaceus* = 3 (grade 1) and *Prionychus ater* = 1 (grade 3). The split is
   59 × 3, 42 × 2 and 79 × 1.
3. **Data fault: 2 of the 180 IEC rows have a blank TVK.** They join to a junk `species`
   row (`tvk = ''`, "Acalypta platychila", a lace bug). Across all indices, 20
   `fidelity_scores` rows have `tvk = ''`. Only 178 IEC species can be used as things
   stand. The missing two need naming from ENRR574 Appendix. Add this to `06_Faults.md`.
4. **The SQI cannot be derived from Codex alone.** khepri scores Least Concern species by
   their *original GB distribution*: Common 1, Local 2, others 4. **Codex has no
   Common/Local track.** Nor does Pantheon: its SQS has no value 2, and its 0/1/4/8/16/32
   ladder is a different scheme. The irreducible fact to hold is therefore a per-species
   "1999 base status" (Common / Local / other) for the roughly 598 species on the list.
5. **Codex coverage of modern IUCN statuses for saproxylic beetles is about 40%.** Of 677
   Pantheon "decaying wood" beetle species, only 273 have a `threat_iucn_2001` row. Several
   whole families have no modern review: Scolytinae, Nitidulidae, Elateridae, Curculionidae
   (part), Cryptophagidae, Ciidae, Latridiidae, Eucnemidae, Erotylidae and others. For
   those, the score must come from legacy statuses (1999-style). The Cobham report's
   table shows a score of **8**, which the khepri IUCN ladder (32/24/16/4/2/1) cannot
   produce. That suggests khepri itself is a hybrid: IUCN where reviewed, the 1999 score
   where not.
6. **The 1999 status→score table is still not confirmed.** I tried NRW 245, Petworth
   (Telfer 2020), Franchises Lodge, JNCC CSM 2008, Pantheon and ResearchGate (blocked).
   None states it. Wil's paper copy of *The Coleopterist* 8: 121–141 settles it.
7. **Rankings page:** 241 rows (manual count, ±1). Columns are Site · Region · spp. · SQS ·
   SQI · IEC · Survey Period, sorted by SQI and sortable client-side. Top row: *New Forest,
   South Hampshire | England: South | 324 | 2500 | 771.6 | 200 | < 2000*. Bottom row:
   *Melton Wood | 49 | 85 | 173.5 | 2*. The minimum in the table is 40 spp. There are
   per-site pages at `khepri.uk/dataset/<GUID>`, e.g. Epping Forest; these could not be
   fetched. There is still no licence, terms, contact or download. This sandbox's proxy
   refused curl (CONNECT 403), so I could not check whether the table is static HTML.
   **Do not scrape:** there is no licence, and it is someone else's curated database.
8. The formula checks out against the rankings: 2500 / 324 × 100 = 771.6 and
   2780 / 363 × 100 = 765.8. SQI is **rounded to one decimal**, and the denominator is
   **qualifying (list) species only**. That differs from Examen's Pantheon SQI, which
   divides by all species analysed and rounds to an integer.

---

## 1. Sources: what each confirms

| Claim | Source | Status |
|---|---|---|
| SQS ÷ qualifying spp × 100; 40-species minimum; complete list; equal attention to common species | NRW Evidence Report 245 §6.3 (Alexander 2017) | Confirmed, quoted |
| 1 (common) to 32 (rarest) on a geometric scale | NRW 245 §6.3 | Confirmed (scale only) |
| IUCN scheme: CE/CR/EN/RE 32; VU 24; NT+NR 24, NT 16; DD 2; LC by original distribution, Common 1 / Local 2 / others 4 | khepri.uk home page | Confirmed, quoted |
| 598 list, excluding *Pseudovadonia livida* | Telfer 2020 Petworth, Table 5 footnote | Confirmed |
| 596: *Anoplodera livida* in error; *Anaspis septentrionalis* sunk in *A. thoracica* | khepri.uk/main | Confirmed |
| 605 list; IEC from Alexander (2024) | khepri.uk home page; Heeney 2024 §3.3.7–8 | Confirmed (but contradicts /main) |
| Thresholds: SQI >500 national (Fowles 1999); 300+ best sites (Alexander) | NRW 245 §6.3 | Confirmed |
| SQI >590 international | Telfer 2020 §4.2.1, citing Fowles 1999 | Confirmed second-hand |
| IEC: 15–24 regional, 25–80 national, >80 European; post-1950 only | NRW 245 §6.4 | Confirmed. Note the **inclusive ranges**, not ">15" |
| IEC grade 1/2/3 = 3/2/1 points; 180 of 695 British native saproxylic beetles | Pantheon IEC (Revised) page | Confirmed |
| Pantheon *"does not apply any date filtering, so users should exclude pre-1950 records"* | Pantheon IEC (Revised) page | Confirmed |
| Fowles' own scoring spreadsheet *"Updated 24 Jan 2004"*, 597 spp | Franchises Lodge 2020, App. 1 | A third list count |
| 1999 table (Common 1 / Local 2 / Nb 4? / Na 8? / RDB3 16? / RDB1–2 32?) | not found online | **Unconfirmed** |
| Alexander 2024 IEC revision (BJENH 37: 33–45 per §4) | not found online | **Unconfirmed**: grade changes unknown |

The threshold wording matters for the verdict code. NRW 245 gives ranges ("15–24 regional,
25–80 national, in excess of 80 European"). Telfer gives ">15, >25, >80". The two disagree
at exactly 15 and 25. Make inclusivity a config flag (§5).

---

## 2. Where the data comes from

### 2.1 SQI membership and scores

**Membership is a fixed published list, not a Pantheon flag.** Pantheon's
`habitats.habitat = 'decaying wood'` gives 677 beetle species (772 Pantheon taxa). The
list is 598. Fowles excluded some groups and Pantheon's "decaying wood" is broader. Use
Pantheon only to *check coverage* and for the E8b "all saproxylic beetles" row, never to
decide what counts.

**Proposed table: `codex.db: sap_list`** (Codex owns status data; Examen reads it):

```
sap_list(
  list_version TEXT,   -- 'Fowles1999-598' | 'khepri-605'
  tvk          TEXT,   -- current UKSI TVK (through the existing bridge/remap)
  name_as_listed TEXT, -- as published, for audit
  base_status  TEXT,   -- 'Common' | 'Local' | 'Other'  (1999 GB distribution)
  score_1999   INTEGER,-- optional: the published score, if Wil transcribes it
  excluded     TEXT,   -- reason, e.g. 'in list in error (Telfer 2020)'
  PRIMARY KEY (list_version, tvk))
```

- `base_status` is the one fact Codex cannot supply. With it, every score can be **derived
  from Codex statuses** under khepri's published rule. That fits the backlog's licence
  stance, because khepri's scores are never shipped.
- `excluded` keeps *Pseudovadonia livida* as data. The *Anaspis septentrionalis* →
  *thoracica* merge happens through the TVK remap, so dedupe on current TVK.
- Licence: a list of names with a three-way distribution class is close to bare fact.
  It is still transcribed from a © journal paper. Hold it like the non-OGL reviews: a
  `reviews` row with `licence = 'internal reference only'`, used for Wil's own reports, and
  left out of any distributable bundle until Fowles agrees.
- Input: Wil's copy of the 1999 appendix, keyed as CSV
  (`name, base_status[, score_1999]`) and loaded by a new `scripts/load_sap_list.py` in
  the same pattern as `load_review.py`. About 598 rows is about two hours of keying.
  Alternatively, OCR the paper.

**Score rule, as a config table, not code** (`Examen/saproxylic_config.json`, §5). It
follows the Codex precedence already used by `derive_from_tracks`:

| Codex evidence (first match wins) | Score | `basis` label |
|---|---|---|
| `threat_iucn_2001` ∈ RE, CR, EN | 32 | IUCN |
| `threat_iucn_2001` = VU | 24 | IUCN |
| `threat_iucn_2001` = NT and `rarity_modern` = NR | 24 | IUCN |
| `threat_iucn_2001` = NT | 16 | IUCN |
| `threat_iucn_2001` = DD | 2 | IUCN (khepri's value, as published) |
| `threat_iucn_2001` = LC | Common 1 / Local 2 / Other 4 (from `base_status`) | IUCN + 1999 distribution |
| no modern row: `threat_iucn_legacy` RDB1 | 32 ⚠ | 1999 (provisional) |
| RDB2 | 32 or 24 ⚠ | 1999 (provisional) |
| RDB3 / RDBK / RDBI | 16 ⚠ | 1999 (provisional) |
| `rarity_legacy` Na | 8 ⚠ | 1999 (provisional) |
| `rarity_legacy` Nb / Notable | 4 ⚠ | 1999 (provisional) |
| otherwise: `base_status` Local 2 / Common 1 | 1–2 | 1999 |
| `score_1999` present and the rule gives nothing | `score_1999` | published |
| `threat_iucn_2001` ∈ NA, NE, EX, or not native | 0, with a warning | — |

⚠ = **must be confirmed from the 1999 paper before release**. Every species row carries
its `basis`, so a report can say "212 IUCN-scored, 41 on 1999 statuses".

Open point: is NT + NR = 24 keyed on the *modern* NR (`rarity_modern`)? khepri says
"Nationally Rare", which in current reviews is the hectad-based NR. Assume yes.

### 2.2 IEC

- **2004 list: read straight from `pantheon.db`.** It is OGL, DOI 10.5285/2a353d2d…, and
  can ship. Bridge `fidelity_scores.tvk` → UKSI through `tvk_bridge` (178/180 bridge).
  Repair the two blank-TVK rows with names from ENRR574.
- **Cleaner alternative:** copy it into `codex.db: iec_list(version, tvk, name_as_listed,
  grade, points)` at Codex build time, from pantheon.db, and patch the two blanks from a
  small `data/iec_fixes.csv`. That gives one place for the 2024 list too.
- **2024 list:** only if Wil gets Alexander (2024). Key it as `version = 'Alexander2024'`,
  © BENHS, internal use only. The config picks the default version and every output names
  it.
- The 1986 list (188) is also in pantheon.db and could be offered for comparison with old
  reports. Low priority.

### 2.3 Rankings

There is no licence, so do not ship or scrape. Two legitimate options:

1. **Manual comparison sites per project.** Wil types the 3–6 neighbour or famous sites he
   wants in a Petworth Table 8–style table (site, county, spp, SQI, IEC, period, source,
   date seen).
2. **A private snapshot** `data/sap_rankings_snapshot.csv` that Wil keys or copies himself.
   It lives outside the repo and the source bundle, carries a `snapshot_date`, and is
   loaded only if present. It gives "would rank 43rd of 241 (khepri, seen 09/10/2026)".

Best of all: ask Adrian Fowles for permission or an export (open question 1).

---

## 3. Read-only coverage queries

Run in DB Browser or `sqlite3` against `codex.db`, with Pantheon attached read-only:

```sql
ATTACH 'file:pantheon.db?mode=ro' AS pan;   -- sqlite3 CLI: open codex.db with -readonly
```

**Q1. IEC list size and bridging.** Snapshot result: 180 rows → 178 bridged, 2 blank TVK.
```sql
SELECT f.index_name, COUNT(*) AS n,
       SUM(f.tvk = '')                       AS blank_tvk,
       COUNT(b.uksi_tvk)                     AS bridged,
       SUM(b.uksi_tvk IS NOT NULL AND b.uksi_tvk <> f.tvk) AS rekeyed
FROM pan.fidelity_scores f
LEFT JOIN tvk_bridge b ON b.pantheon_tvk = f.tvk
WHERE f.index_name LIKE '%index of ecology continuity%'
GROUP BY f.index_name;
```

**Q2. IEC points split.** Snapshot result: 3 → 59, 2 → 42, 1 → 79.
```sql
SELECT score AS points, COUNT(*) FROM pan.fidelity_scores
WHERE index_name = 'revised index of ecology continuity score' GROUP BY score;
```

**Q3. IEC species and their Codex statuses.** Snapshot result: 93 of 179 have a modern
IUCN row.
```sql
SELECT s.species_name, f.score AS iec_points,
       MAX(CASE WHEN ss.status_track='threat_iucn_2001'   THEN ss.status_value END) AS iucn,
       MAX(CASE WHEN ss.status_track='rarity_modern'      THEN ss.status_value END) AS rarity,
       MAX(CASE WHEN ss.status_track='threat_iucn_legacy' THEN ss.status_value END) AS rdb,
       MAX(CASE WHEN ss.status_track='rarity_legacy'      THEN ss.status_value END) AS notable
FROM pan.fidelity_scores f
JOIN pan.species s ON s.tvk = f.tvk
LEFT JOIN tvk_bridge b ON b.pantheon_tvk = f.tvk
LEFT JOIN status_summary ss ON ss.tvk = COALESCE(b.uksi_tvk, f.tvk)
WHERE f.index_name = 'revised index of ecology continuity score'
GROUP BY f.tvk ORDER BY f.score DESC, s.species_name;
```

**Q4. Saproxylic beetle superset (Pantheon "decaying wood") and modern-status coverage by
family.** `pan.species` has no order column. The family list below is an **assumption**
(Coleoptera families present in Pantheon's decaying-wood set). If uksi.db is attached,
replace it with a join on `taxa`'s order. Snapshot result: 677 species, 273 with
`threat_iucn_2001`.
```sql
WITH sap AS (
  SELECT DISTINCT COALESCE(b.uksi_tvk, s.tvk) AS tvk, s.tvk AS pan_tvk, s.species_name, s.family
  FROM pan.species s
  JOIN pan.habitats h ON h.tvk = s.tvk AND h.habitat = 'decaying wood'
  LEFT JOIN tvk_bridge b ON b.pantheon_tvk = s.tvk
  WHERE s.family IN ('Cerambycidae','Elateridae' /* <- replace with the quoted 58-family list given under this query */))
SELECT family, COUNT(*) AS spp,
       SUM(tvk IN (SELECT tvk FROM status_summary WHERE status_track='threat_iucn_2001')) AS modern_iucn,
       SUM(tvk IN (SELECT tvk FROM status_summary WHERE status_track IN
                   ('threat_iucn_legacy','rarity_legacy'))) AS legacy_status
FROM sap GROUP BY family ORDER BY spp DESC;
```
Family list used (assumption): Aderidae Anobiidae Anthribidae Biphyllidae Bostrichidae Buprestidae Cantharidae Carabidae Cerambycidae Cerylonidae Chrysomelidae Ciidae Cleridae Colydiidae Corylophidae Cryptophagidae Cucujidae Curculionidae Dermestidae Elateridae Endomychidae Erotylidae Eucinetidae Eucnemidae Histeridae Laemophloeidae Lathridiidae Leiodidae Lucanidae Lycidae Lymexylidae Melandryidae Melyridae Mordellidae Mycetophagidae Nitidulidae Oedemeridae Phloiophilidae Platypodidae Ptiliidae Pyrochroidae Pythidae Rhizophagidae Salpingidae Scarabaeidae Scirtidae Scolytidae Scraptiidae Scydmaenidae Silvanidae Sphaeritidae Sphindidae Staphylinidae Tenebrionidae Tetratomidae Throscidae Trogidae Trogossitidae.
Snapshot families with no modern status: Scolytidae 0/59, Nitidulidae 0/25,
Curculionidae 0/24, Elateridae 0/23, Cryptophagidae 0/21, Ciidae 0/21, Lathridiidae 0/15,
Ptiliidae 0/14, Leiodidae 0/14, Scydmaenidae 0/9, Erotylidae 0/7, Eucnemidae 0/6. Staphylinidae
is 46/133.

**Q5. Score preview under the rule.** Skeleton; LC species need `base_status`, so before
`sap_list` exists they show as `LC?`.
```sql
-- reuse the "sap" CTE from Q4, then:
SELECT CASE
  WHEN iucn IN ('RE','CR','EN') THEN '32'
  WHEN iucn = 'VU' THEN '24'
  WHEN iucn = 'NT' AND rar = 'NR' THEN '24'
  WHEN iucn = 'NT' THEN '16'
  WHEN iucn = 'DD' THEN '2'
  WHEN iucn = 'LC' THEN 'LC? (1/2/4 by base status)'
  WHEN rdb IN ('RDB1','RDB2','RDB3','RDBK') THEN 'legacy '||rdb
  WHEN nb IN ('Na','Nb','Notable') THEN 'legacy '||nb
  ELSE 'Common/Local? (no status)' END AS bucket, COUNT(*)
FROM (SELECT sap.tvk,
        (SELECT status_value FROM status_summary WHERE tvk=sap.tvk AND status_track='threat_iucn_2001' LIMIT 1) iucn,
        (SELECT status_value FROM status_summary WHERE tvk=sap.tvk AND status_track='rarity_modern' LIMIT 1) rar,
        (SELECT status_value FROM status_summary WHERE tvk=sap.tvk AND status_track='threat_iucn_legacy' LIMIT 1) rdb,
        (SELECT status_value FROM status_summary WHERE tvk=sap.tvk AND status_track='rarity_legacy' LIMIT 1) nb
      FROM sap) GROUP BY bucket ORDER BY 2 DESC;
```
Caveat: `status_summary` can hold more than one row per track (the PK includes
`status_detail`). `LIMIT 1` is good enough for a preview. The real code must use
Codex's own precedence.

**Q6. Once `sap_list` exists:** names that did not resolve, and list species absent
from Pantheon.
```sql
SELECT list_version, COUNT(*), SUM(tvk IS NULL OR tvk = '') AS unresolved,
       SUM(tvk NOT IN (SELECT COALESCE(b.uksi_tvk, s.tvk) FROM pan.species s
                       LEFT JOIN tvk_bridge b ON b.pantheon_tvk = s.tvk)) AS not_in_pantheon
FROM sap_list GROUP BY list_version;
```

**Q7. Junk rows** (fault 3):
`SELECT index_name, COUNT(*) FROM pan.fidelity_scores WHERE tvk = '' GROUP BY 1;`
In the snapshot: 20 rows across 8 indices.

---

## 4. Computation module: `Examen/saproxylic.py` (pure, no Qt, no DB)

The DB reads go in a thin loader, `Examen/saproxylic_data.py`, which turns the site's
records plus `sap_list`, `iec_list` and Codex tracks into plain inputs. The calculator
never touches SQLite. This is the same split as `sqs_derivation`.

```python
@dataclass(frozen=True)
class SapInput:            # one species recorded at the site
    tvk: str; name: str; family: str
    first_year: int | None; last_year: int | None
    tracks: dict           # {status_track: status_value} from Codex
    base_status: str | None   # from sap_list; None = not on SQI list
    score_1999: int | None
    iec_points: int | None    # from iec_list; None = not an IEC species

@dataclass
class SpeciesScore:  tvk; name; family; status_label; sqi_score; basis; iec_points; counted_iec: bool
@dataclass
class SQIOutcome:    list_version; sqs; qualifying; sqi (1 dp) | None; calculable: bool;
                     verdict; by_basis: dict; warnings: list[str]
@dataclass
class IECOutcome:    version; total; by_grade: {1:(n,pts),2:(n,pts),3:(n,pts)};
                     excluded_pre_cutoff: list; verdict; warnings: list[str]

def score_species(tracks, base_status, score_1999, rules) -> tuple[int, str]
def compute_sqi(inputs, cfg) -> SQIOutcome
def compute_iec(inputs, cfg) -> IECOutcome
def verdict(value, bands, inclusive) -> str          # shared by SQI and IEC
def rank_against(sqi, snapshot_rows) -> tuple[int, int] | None   # (position, of_n)
def merge_surveys(*input_lists) -> list[SapInput]    # cumulative: union by tvk, widen years
```

The rules the calculator applies:

- **SQI.** Count species on the SQI list (`base_status` not None and not excluded), dedupe by
  current TVK, then SQI = round(SQS / qualifying × 100, 1). Below `min_species` (40),
  `calculable = False` and `sqi = None`. Report the *would-be* figure only in a warning
  ("36 qualifying; SQI not calculable; 40 required"), as NRW 245 does. Per
  `38_Report_Survey.md`: no number with an asterisk.
- **IEC.** Sum `iec_points` for species whose `last_year >= cutoff` (1950, configurable).
  Species seen only before the cutoff go into `excluded_pre_cutoff` and are listed in the
  report. Undated records: count them, but warn ("n undated records counted").
- **Cumulative.** `merge_surveys` unions several surveys or desk-study lists. The output
  says "minimum value; cumulative over 1988–2024". This is the Petworth model, and it
  differs from Examen's per-survey Pantheon analysis.
- **Warnings** cover: below 40; list version mismatch with the IEC version; species on the
  list with no score (no `base_status` and no status); provisional (1999-unconfirmed)
  scores used; a single-year scope when pooled data exist ("SQI expects a complete list");
  the blank-TVK IEC species.
- **SQI by habitat:** not meaningful. The index is site-level. Do not add it to E8's
  per-habitat display.

---

## 5. Configuration: `Examen/saproxylic_config.json`

This sits beside `sat_thresholds.json` and is loaded the same way as `_sat_thresholds()`
in `workbook_export.py` (here, then `<root>/Examen/`).

```json
{
  "_comment": "Saproxylic SQI (Fowles et al. 1999) and IEC (Alexander 2004/2024). Edit thresholds here; every output names the source of each.",
  "_updated": "2026-10-09",
  "sqi": {
    "list_version": "Fowles1999-598",
    "min_species": 40,
    "decimals": 1,
    "bands": [
      {"label": "International", "min": 590, "source": "Fowles et al. 1999"},
      {"label": "National",      "min": 500, "source": "Fowles et al. 1999"},
      {"label": "Among the best British sites", "min": 300, "source": "Alexander 2017 (NRW 245)", "enabled": true}
    ],
    "inclusive": false,
    "rules": [
      {"track": "threat_iucn_2001", "values": ["RE","CR","EN"], "score": 32, "basis": "IUCN"},
      {"track": "threat_iucn_2001", "values": ["VU"], "score": 24, "basis": "IUCN"},
      {"track": "threat_iucn_2001", "values": ["NT"], "and": {"rarity_modern": "NR"}, "score": 24, "basis": "IUCN"},
      {"track": "threat_iucn_2001", "values": ["NT"], "score": 16, "basis": "IUCN"},
      {"track": "threat_iucn_2001", "values": ["DD"], "score": 2,  "basis": "IUCN"},
      {"track": "threat_iucn_2001", "values": ["LC"], "by_base": {"Common":1,"Local":2,"Other":4}, "basis": "IUCN + 1999 distribution"},
      {"track": "threat_iucn_legacy", "values": ["RDB1","RDB2"], "score": 32, "basis": "1999", "provisional": true},
      {"track": "threat_iucn_legacy", "values": ["RDB3","RDBK","RDBI"], "score": 16, "basis": "1999", "provisional": true},
      {"track": "rarity_legacy", "values": ["Na"], "score": 8, "basis": "1999", "provisional": true},
      {"track": "rarity_legacy", "values": ["Nb","Notable"], "score": 4, "basis": "1999", "provisional": true},
      {"base": {"Local": 2, "Common": 1, "Other": 4}, "basis": "1999 distribution"}
    ],
    "exclusions": [{"name": "Pseudovadonia livida", "reason": "in published list in error (Telfer 2020)"}]
  },
  "iec": {
    "version": "Alexander2004",
    "post_year": 1950,
    "points": {"1": 3, "2": 2, "3": 1},
    "bands": [
      {"label": "International", "min": 80, "source": "Alexander 2004"},
      {"label": "National",      "min": 25, "source": "Alexander 2004"},
      {"label": "Regional",      "min": 15, "source": "Alexander 2004"}
    ],
    "inclusive": true,
    "_note": "NRW 245: 15-24 regional, 25-80 national, >80 European (inclusive lower bounds). Telfer 2020 writes >15/>25/>80."
  },
  "rankings": {"snapshot_path": "data/sap_rankings_snapshot.csv", "source": "khepri.uk/rankings (Fowles)"}
}
```

One edge case: with `inclusive: true`, an IEC of exactly 80 reads "National" under NRW
245 but "International" under a plain `>=` reading. Code the verdict as
`value > min` or `value >= min` from the flag, and test exactly 15, 25, 80, 500 and 590.

---

## 6. UI and reports

**Overview tab** (`overview_tab.py`): this view is Pantheon-centred. Do not crowd the hero
row. Add **one compact "Saproxylic" strip** under the tier frame, shown only when at
least one SQI- or IEC-listed species is present:
`Saproxylic SQI 488.0 (208 qualifying) · IEC 93 (national; 28×3 + 4×2 + 8×1)`.
Below 40 qualifying species it reads "SQI not calculable (36 of 40)". Use the existing ▲
low-sample pattern (E9) and `theme()` colours. E12 says the views hardcode palettes, so do
not add more.

**New detail tab "Saproxylic"** (`site_analysis_view.py:248`, after Assemblages), new file
`Examen/saproxylic_tab.py`:
1. A header card: SQI, IEC, verdicts with sources, list and IEC versions, scope (single
   survey or cumulative), and warnings.
2. The species table, after EMG2 Table 5: Family | Species | Status | SQI score | Basis |
   IEC grade | IEC pts | Years. Sortable, in taxonomic order by default via
   `in_taxonomic_order`.
3. The IEC contribution table, after Petworth Table 7: Grade | Species | Points |
   Contribution | Total.
4. A comparison table, after Petworth Table 8: this site, then manual comparison sites and,
   if present, the snapshot rank ("43rd of 241, khepri seen 09/10/2026").
5. A "Pool all years and desk-study records" toggle. It reuses the existing pool toggle,
   but IEC wants non-Commercial record types too (open question 4).

**Workbook** (`workbook_export.py`): add `_sheet_saproxylic(wb, sap, stamp)` after
`_sheet_assemblages`, only when the site has listed species. Content: the table as in item 2,
footer rows (SQS, qualifying species, SQI, IEC, species with status) and the contribution
table. Add stamp lines to `basis`: "Saproxylic SQI list: Fowles et al. 1999 (598 spp.),
scores derived from Codex statuses" and "IEC: Alexander 2004 via Pantheon (OGL)". Put the
two headline figures in the Summary sheet.

**Report model** (`report_model.py`): the footer and contribution rows do not fit
`_table()`. Add a `_saproxylic(ws)` reader and `rep["saproxylic"]`, so Word and PDF render
it. Do not add it to `SECTIONS`. Word and PDF then get the section and cannot drift (E3/E4
principle).

**Project table:** an optional SQI(sap) / IEC column pair, hidden by default.

---

## 7. Build checklist

| # | Step | Est. |
|---|---|---|
| 0 | **Wil:** confirm the 1999 score table from the paper; choose the 598 or 605 list and the 2004 or 2024 IEC; name the 2 blank-TVK IEC species | Wil, ~1 h |
| 1 | Key the SQI list CSV (name, base_status, score_1999) from the paper | Wil ~2 h, or OCR plus check |
| 2 | `scripts/load_sap_list.py` + `sap_list`/`iec_list` tables in `build_codex_db.py` (preserved across rebuilds like `manual_entries`; IEC copied from pantheon.db plus fixes CSV); `reviews` rows with licence | 0.5 day |
| 3 | `Examen/saproxylic.py` pure calculator + `saproxylic_config.json` | 0.5 day |
| 4 | `Examen/saproxylic_data.py` loader (records with years, Codex tracks via `get_statuses_batch`, list joins, pooling) | 0.5 day |
| 5 | Saproxylic tab + Overview strip | 0.5 day |
| 6 | Workbook sheet + report_model reader + Word/PDF rendering | 0.5 day |
| 7 | Comparison table (manual entry, stored in examen.db per project) + optional snapshot CSV | 0.25 day |
| 8 | Validate against the Cobham/Kent Deadwood figures and Petworth (SQI 569.2, IEC 87) | 0.25 day |
| | **Total** | **~3 days + Wil's keying**, which matches the backlog |

**Tests** (`tests/test_saproxylic.py`, pure, in the style of `test_pure_functions.py`):
- `score_species`: every rule row, including NT+NR → 24, NT alone → 16, DD → 2, LC × base
  1/2/4, legacy fallbacks flagged provisional, modern beating legacy, case and whitespace,
  NA/NE → 0 with a warning.
- `compute_sqi`: the New Forest identity (SQS 2500, n 324 → 771.6) and Windsor (2780/363 →
  765.8); n = 39 → not calculable; n = 40 → calculable; dedupe after the Anaspis synonymy;
  Pseudovadonia excluded; non-list species ignored in the denominator.
- `compute_iec`: 8×3 + 12×2 + 39×1 = 87 (Petworth); a 1949-only species excluded and
  listed; a 1949 + 1951 species counted; undated counted with a warning.
- `verdict`: 15, 25, 80, 500 and 590 under both inclusivity settings.
- `merge_surveys`: union, year widening, no double count.
- `rank_against`: ties, a value above the top, an empty snapshot.
- Loader smoke test against the real `data/` DBs (skipped if absent): IEC list = 180 rows,
  178 bridged until fixed.

---

## 8. Open questions for Wil

1. **Rankings and list:** will you ask Adrian Fowles for permission to hold the list and
   rankings, or for an export? That would remove the licence problem. Otherwise use
   manual comparison sites.
2. **Which versions are the default?** khepri's home page (605 + IEC 2024) or
   /main and Telfer (598 + IEC 2004)? Your 2024 Cobham report used 605 + 2024. Do you
   have Alexander (2024) and its grade changes?
3. **The 1999 table:** what are the exact scores for Nb, Na, RDB3, RDBK, RDB1 and RDB2? Was
   there an "Occasional" class? This settles the provisional rows.
4. **Cumulative scope:** IEC and the SQI are site-history measures. Should Examen pull
   non-Commercial record types (literature, desk study, other recorders) for a site? It
   reads only `record_type = 'Commercial'` today. Or should the user import a desk-study
   list for the site?
5. **SQI for non-beetles?** The SQI is Coleoptera only. Confirm there are no "saproxylic
   SQI" figures for Diptera etc., and keep Pantheon's A21x SATs for those.
6. **Families with no modern review** (Elateridae, Scolytinae, Nitidulidae…): are you
   content for them to score on Hyman & Parsons statuses (flagged "1999 basis")? Or do you
   know of newer reviews (e.g. an Elateroidea NECR) to load into Codex first?
7. **The 300 band:** show Alexander's "300+ among the best" as a third verdict, or only as
   a note? It is enabled in the config sketch.

---

## Sources

- khepri.uk, home page (605 list, IUCN scoring rule, IEC Alexander 2024): https://khepri.uk/
- khepri.uk/main (598/596, *Anoplodera livida*, *Anaspis septentrionalis*, 40 qualifying species): https://khepri.uk/main
- khepri.uk rankings (241 rows, columns, top and bottom rows): https://khepri.uk/rankings/
- khepri.uk per-site dataset page (example; not fetchable from here): https://khepri.uk/dataset/28960FE8-3087-40E6-8141-DCF573137A9D
- Old SQI page redirecting to khepri: https://yrefail.net/Coleoptera/sqi.htm
- BioInfo record for Fowles, *Saproxylic Quality Index* (web resource): https://www.bioinfo.org.uk/html/b156217.htm
- Pantheon, IEC (Revised): grades/points, 180 of 695, no date filtering: https://pantheon.brc.ac.uk/node/351 (also https://pantheon.brc.ac.uk/lexicon/iec-revised)
- Pantheon, Scoring systems (Pantheon SQS ladder; image table): https://pantheon.brc.ac.uk/content/scoring-systems
- Pantheon, Species Quality Indices lexicon: https://pantheon.brc.ac.uk/lexicon/species-quality-indices
- Alexander (2004) ENRR574: https://publications.naturalengland.org.uk/publication/133006 · file https://publications.naturalengland.org.uk/file/133007
- NRW Evidence Report 245, Wye Valley Woodlands SAC (2017), §6.3–6.4: https://www.naturalresourceswales.gov.uk/media/685547/report-245-saproxylic-invertebrate-survey-wye-valley-woodlands-sac-2017.pdf
- Telfer (2020), Petworth Park saproxylic survey (598, Pseudovadonia, 212 sites, Tables 5/7/8): https://cdn.buglife.org.uk/2022/01/Saproxylic-invertebrate-survey-of-Petworth-Park-2021-01-27.pdf
- Franchises Lodge scoping survey 2020 (597-species Fowles spreadsheet, 24 Jan 2004): https://cdn.buglife.org.uk/2022/01/Franchises-Lodge-saproxylic-invertebrate-scoping-survey-2020.pdf
- Heeney (2024), Cobham Woods etc., Kent Downs Annex 7n (605 + Alexander 2024; Table 4.4): https://kentdowns.org.uk/wp-content/uploads/2025/04/Annex-7n-Saproxylic-Invertebrates-assessment-of-the-North-Kent-Woods-and-Downs-NNR.pdf
- JNCC CSM Guidance for Terrestrial and Freshwater Invertebrates (2008), §5.4 (citation of Fowles et al. 1999): https://data.jncc.gov.uk/data/80873e1e-63eb-44a0-925c-b5edec5fa3fd/CSM-TerrestrialFreshwaterInvertebrates-2008.pdf
- Fowles, Alexander & Key (1999), *The Coleopterist* 8: 121–141 (ResearchGate record; not readable from here): https://www.researchgate.net/publication/285288635_The_Saproxylic_Quality_Index_Evaluating_wooded_habitats_for_the_conservation_of_dead-wood_Coleoptera
- Alexander (2002), Forthampton Oaks, BJENH 15: 63–64 (SQI below minimum, IEC 20 regional): https://archive.org/download/biostor-242303/biostor-242303.pdf
- Pantheon database (EIDC, OGL, DOI 10.5285/2a353d2d-c1b9-4bf7-8702-9e78910844bc): https://catalogue.ceh.ac.uk/id/2a353d2d-c1b9-4bf7-8702-9e78910844bc
- Code read: `scripts/build_codex_db.py` (schema, `DESIG_TO_TRACK`), `shared/services/pantheon_analysis_service.py`, `shared/repositories/{pantheon,codex}_repository.py`, `Examen/{examen_data,workbook_export,report_model,overview_tab,site_analysis_view}.py`, `Examen/sat_thresholds.json`, `tests/test_pure_functions.py`. Note: `shared/sqs_derivation.py` is imported but **missing from the snapshot**.

---

# 04 — Groundwork: Photos (A8, A8b) and Geo (I3b / F29, I3c / F30)

*Read-only research, 9 October 2026. Source: the snapshot at `/mnt/user-data/uploads/Biological Software/`.
That snapshot has no `observatum.db`, no `data/maps/`, and no `shared/species_rank.py` or
`Observatum/src/views/components/`. Wherever a figure below depends on those, it says "to measure".
Library versions are from PyPI JSON on 9 Oct 2026. Every converter figure is **measured** against
Ordnance Survey's 40 published OSTN15 test points (TP01–TP40), in scratch scripts. Nothing in the
project was changed.*

---

## Part B first: geo findings that change the plan

**B0.1 `grid_converter_service` / OSGridConverter is not a safe "one converter".** F30 and I3c
suggest switching the wizard to it because it "does apply the shift". It does, but its
grid→lat/long has a longitude error that grows with distance from the 2°W central meridian
(measured on the OS test points; the error is almost all in longitude, so the inverse
projection is at fault):

| Test point | Area | OSGridConverter error | Pure-Python Helmert error |
|---|---|---|---|
| TP04 SZ49 | Isle of Wight (near 2°W) | 1.1 m | 1.4 m |
| TP09 TQ30 | London | **32.9 m** | 1.7 m |
| TP14 TF62 | Norfolk | **72.1 m** | 2.7 m |
| TP07 TR39 | Kent | **216.6 m** | 1.9 m |
| TP01 SV91 | Scilly | **423.5 m** | 4.7 m |
| TP31 NF09 | Outer Hebrides | **1,439.6 m** | 4.9 m |
| all 40 | | median 35.3 m, max 1,440 m | median 1.8 m, max 4.9 m |

Its lat/long→grid direction is fine (1–5 m), so this matters for grid ref→lat/long only. The
snapshot has **no callers** of `grid_converter_service`. Its last release (0.1.3) was in July
2017, and `grid.py` has non-raw `'\d'` regex strings, which give a SyntaxWarning on 3.12+.
**Recommendation:** do not route I3c through it. Retire it to `_archive` once the shared
converter exists. Correct the F30 text.

**B0.2 The wizard converts the square's SW corner, not its centre.** `validation_worker.py:1033`
calls `parse_grid_ref`, which returns the SW corner, and then `_osgb36_to_wgs84(easting, northing)`.
For a 6-figure ref the corner is 71 m from the centre. Before recomputing anything, Wil needs to
decide which convention the stored lat/long follows (decision G2). The 20,702 iRecord records can
show what iRecord does (see the B4 script).

**B0.3 VC by point-in-polygon needs no datum transformation at all.** Grid refs are OSGB36
eastings/northings. If the test runs against the OSGB boundary (`vc_brc.shp`, said to be 56 MB;
check its `.prj` says British National Grid) in E/N, no lat/long is involved. Using
`vc_brc_wgs84.geojson` would bring in whatever transform made that file. If that transform skipped
the shift, the boundary is ~100 m out, the same problem F30 notes for Data Entry's overlay.

**B0.4 The 1 km lookup is centroid-based, and coarse refs inherit their SW square's VC.**
`create_vc_lookup_db.py` gives each square the VC whose polygon contains the square's **centroid**.
That causes two side-effects (to measure):
- coastal squares with the centroid in the sea get **no VC**, even when the record is on land;
- `get_1km_square("SP58")` (a 10 km ref) returns the SW 1 km square `SP5080`. A 10 km or 2 km
  ref is then silently given that corner square's VC.

From `vc_lookup.db` (read-only): 282,637 squares; **30,336 have a neighbour with a different
VC** (an upper bound on the boundary squares); 8,667 border a square with no VC (coast).
Confirmed: `SO5309` → 35 and `SO5306` → 35 (Highbury Wood, Cadora Woods; F29 says both are VC34).

**B0.5 Libraries the code imports today:** `OSGridConverter` (grid_converter_service only), and
`geopandas` + `shapely` (only in `scripts/create_vc_lookup_db.py`, in a try-block). No `pyproj`,
no `osgeo`. `pandas` is used by the import wizard. No Pillow or EXIF library is imported anywhere.
No `requirements.txt` was found.

---

## Part A — Photos (A8 link, A8b inbox)

### A1. Libraries (Python 3.14, Windows)

| Library | Latest (PyPI) | cp314 win_amd64 wheel | Status / use |
|---|---|---|---|
| **Pillow** | 12.3.0 (1 Jul 2026) | yes | Actively maintained. Reads EXIF and GPS, makes thumbnails. **The only image dependency needed.** |
| pillow-heif | 1.8.0 (22 Sep 2026) | yes | Optional HEIC/AVIF plugin (`register_heif_opener()`). Only needed if HEIC files exist. |
| ExifRead | 3.5.1 (Aug 2025) | pure Python | Maintained, read-only, no image decode. Redundant with Pillow. |
| piexif | 1.1.3 (**Jul 2019**) | pure Python | Unmaintained. **Avoid.** |
| ImageHash | 4.3.2 (Feb 2025) | pure Python, but pulls in numpy + scipy + PyWavelets (all have cp314 wheels) | Heavy for one feature. A dHash is ~15 lines on Pillow. |
| RapidFuzz | 3.14.6 | yes | Fast fuzzy matching. `difflib` (stdlib) is enough at 7,391 files. |

**EXIF with Pillow (verified on Pillow 12.3.0 with a synthetic JPEG):**
```python
from PIL import Image, ExifTags
def read_exif(path):
    with Image.open(path) as im:                       # lazy: reads headers, not pixels
        exif = im.getexif()
        sub  = exif.get_ifd(ExifTags.IFD.Exif)
        when = sub.get(ExifTags.Base.DateTimeOriginal) or exif.get(ExifTags.Base.DateTime)
        tz   = sub.get(ExifTags.Base.OffsetTimeOriginal)          # Pixel writes this
        gps  = exif.get_ifd(ExifTags.IFD.GPSInfo)
        lat = lon = None
        if gps.get(ExifTags.GPS.GPSLatitude) and gps.get(ExifTags.GPS.GPSLongitude):
            dms = lambda v: float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
            lat = dms(gps[ExifTags.GPS.GPSLatitude])  * (-1 if gps.get(ExifTags.GPS.GPSLatitudeRef)  == "S" else 1)
            lon = dms(gps[ExifTags.GPS.GPSLongitude]) * (-1 if gps.get(ExifTags.GPS.GPSLongitudeRef) == "W" else 1)
        return when, tz, lat, lon, im.size, exif.get(ExifTags.Base.Make), exif.get(ExifTags.Base.Model)
```
`DateTimeOriginal` is `"YYYY:MM:DD HH:MM:SS"` in local camera time. Store it as ISO. Use the
EXIF date, not the file mtime: OneDrive rewrites mtimes (`05_Rules.md`, "Prune by filename,
not mtime").

**Google Pixel:** by default it saves **JPEG, as Ultra HDR** (an ordinary JPEG plus a gain map
in metadata). Pillow reads the SDR base image. A DNG is written only if RAW is turned on. So
pillow-heif is probably not needed: check one Pixel 10 Pro file before adding it. GPS is present
only when location saving is on (A8b already says so).

**Thumbnails, two options:**
- *Pillow:* `im.draft("RGB", (400, 400))` makes libjpeg decode at 1/2, 1/4 or 1/8 scale (a
  4000×3000 JPEG decodes at 1000×750). Then `ImageOps.exif_transpose(im)` and
  `im.thumbnail((256, 256))`, saved as JPEG q≈80. Measured ~15 ms for a synthetic 12 MP image.
- *Qt-native:* `QImageReader(path)`, then `setAutoTransform(True)` (EXIF orientation) and
  `setScaledSize(QSize(w, h))`. Qt's JPEG plugin also decodes scaled, and this avoids converting
  PIL→QImage. Use it for display in the grid; use Pillow for EXIF and for writing cache files.
- **Cache:** outside OneDrive, under `%LOCALAPPDATA%\BiologicalSoftware\thumbs\<fp[:2]>\<fp>.jpg`,
  keyed by fingerprint. That is ~7,400 × ~15 KB ≈ 110 MB, and it can be regenerated, so no
  backup is needed. Add `THUMB_CACHE_DIR` to `paths.py`.

### A2. OneDrive Files On-Demand: reading a cloud-only file downloads it

With Files On-Demand, a file shown with the cloud icon is a placeholder. **Any read of its bytes
(EXIF, a hash, a thumbnail) makes Windows fetch the file.** OneDrive normally hydrates the whole
file, not a range: the Cloud Files API defines Partial, Progressive, Full and AlwaysFull hydration
policies, and which one OneDrive uses is not documented for this purpose. So a naive first scan
of `Media` could **download up to 44.3 GB** and fill the disk. `os.stat()`/`os.scandir()` do
**not** hydrate.

Detect the state on Windows from `os.stat(p).st_file_attributes`:
- `FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000`: cloud-only, a read will download it.
- `FILE_ATTRIBUTE_UNPINNED = 0x00100000`: online-only by user choice.
- `FILE_ATTRIBUTE_PINNED = 0x00080000`: "Always keep on this device".
- `FILE_ATTRIBUTE_OFFLINE = 0x00001000`.

Online-only shows as `-P +U +R`; locally available as `-P -U -R`; always-kept as `+P -U -R`.

**Scanner rule:** phase 1 walks with `os.scandir` (no hydration) and links by **filename and
folder only**. Bytes are read (EXIF, fingerprint, thumbnail) only for files without
`RECALL_ON_DATA_ACCESS`. Cloud-only files are counted and left "fingerprint pending", with a
"fetch N files (x GB)" button. Before any build, a read-only count script reports how much of
`Media` is local (decision P1).

### A3. Fingerprint: the options

| Method | Reads | 44 GB cost | Survives | Fails on |
|---|---|---|---|---|
| SHA-256 of whole file | all bytes | ~1.5–5 min from SSD/HDD if local; **44 GB download** if cloud-only | move, rename | any byte change (an EXIF edit, a rotate in Windows Photos) |
| **Fast partial: SHA-256(size ‖ first 64 KB ‖ last 64 KB)** | 128 KB per file, ~1 GB in all | seconds | move, rename | edits that keep the size, change neither end, and alter only the middle (negligible for JPEG: the EXIF header with its timestamps sits in the first 64 KB) |
| Perceptual (dHash/pHash, 64-bit) | decodes the image | minutes | re-save, resize, light crop, EXIF edit | is a *similarity*, not an identity. Stacks and burst shots collide by design |

**Recommendation:** `fp_fast` is the identity used for re-linking (indexed, with size). Compute
`sha256` only on request ("verify"). `dhash` is optional, used to suggest likely duplicates
between `Originals`/"Photos To Do" and the `Life` tree. Store it as a 16-hex string and compute
it in-house on Pillow (no numpy or scipy). **Stacked microscope images:** the stack sources
(Helicon or Zerene frames) are near-identical, so dHash would cluster them. Register only the
stacked outputs unless Wil decides otherwise (decision P3). Whole-file SHA-256 would catch
nothing that the fast fingerprint misses.

### A4. Parsing the filename conventions

Tested in a scratch script on these names: `Dolomedes plantarius - Fen Raft Spider 3`,
`… Ladybird 12 (1a)`, `Perostichus niger 6.vi.21`, `Lamia textor 14.VII.2023 2`,
`Aphodius sp 1.x.19`, `Zygaena filipendulae ssp. stephensi - …`, `IMG_20260614_102231`
(rejected as expected).

```python
ROMAN = {"i":1,"ii":2,"iii":3,"iv":4,"v":5,"vi":6,"vii":7,"viii":8,"ix":9,"x":10,"xi":11,"xii":12}
LIFE = re.compile(r"""^(?P<genus>[A-Z][a-z]+)\s+(?P<species>[a-z][a-z-]+)
    (?:\s+(?P<infra>(?:ssp\.|subsp\.|var\.|f\.)\s*[a-z-]+))?
    \s*-\s*(?P<common>.+?)\s*(?P<n>\d+)?\s*(?P<note>\([^)]*\))?\s*$""", re.X)
MICRO = re.compile(r"""^(?P<genus>[A-Z][a-z]+)\s+(?P<species>[a-z][a-z-]+|sp\.?)\s+
    (?P<d>\d{1,2})\.(?P<m>[ivxIVX]{1,4})\.(?P<y>\d{2}|\d{4})
    \s*(?P<note>\([^)]*\))?\s*(?P<n>\d+)?\s*$""", re.X)
```
- Match the stem (`Path.stem`). Compare suffixes case-insensitively (`.JPG`/`.jpg`/`.jpeg`).
- Map a 2-digit year to 20YY. Flag a year after the current one, and an invalid roman month
  (e.g. `iiii`), as a parse warning.
- **The folder is a second witness.** In `Life` the species folder carries the name. If folder
  and filename disagree, the photo goes to review. In `Microscope Photos` the Order or Family
  folder is a check on the matched taxon's order and family (the folder taxonomy is out of date,
  e.g. Lymantriidae, so a mismatch is only a soft warning).
- **Matching to UKSI, in order:** (1) exact current name → TVK; (2) `uksi.synonyms` → current
  TVK, **always to review** because of F25 (synonyms resolved at genus level, e.g. *Lamia
  sartor*); (3) fuzzy, with `difflib.get_close_matches(binomial, names_in_same_genus, n=3,
  cutoff=0.85)`, then over all names if the genus itself is unknown (e.g. `Perostichus`→
  *Pterostichus*), **always to review**; (4) the common name from the Life convention, as a
  tie-break only. Reuse `shared.species_rank.rank_matches` if it accepts a plain name (not in
  the snapshot; check).
- **Linking a microscope photo to a specimen:** the specimen's TVK and `date_collected` equal to
  the parsed date. Exactly 1 specimen gives `proposed`, high confidence (auto-confirm only if
  Wil agrees, decision P5). 0 or more than 1 go to review, with the candidates listed.

### A5. Schema (style of `scripts/reset_database.py`)

```sql
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Where (relative to a root registered in paths.py; forward slashes)
    root_key TEXT NOT NULL DEFAULT 'media',      -- 'media' = paths.PHOTOS_ROOT
    rel_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    media_type TEXT DEFAULT 'image',             -- image / video
    -- Identity
    file_size INTEGER,
    file_mtime TEXT,                             -- hint only (OneDrive rewrites mtimes)
    fp_fast TEXT,                                -- sha256(size|first64K|last64K); NULL = pending
    sha256 TEXT,                                 -- optional full hash
    dhash TEXT,                                  -- optional perceptual hash (16 hex)
    -- From the file
    width INTEGER,
    height INTEGER,
    taken_at TEXT,                               -- ISO, from EXIF DateTimeOriginal
    taken_tz TEXT,
    camera TEXT,
    gps_lat REAL,
    gps_lon REAL,
    -- From the name / folder
    parsed_name TEXT,                            -- binomial as written in the filename
    parsed_date TEXT,                            -- ISO, from D.month.YY
    parse_note TEXT,                             -- '(1a)', warnings
    -- Description
    photo_type TEXT,                             -- field / specimen / habitat / genitalia / other
    view TEXT,                                   -- dorsal / lateral / ventral / head / aedeagus...
    sex TEXT,
    stage TEXT,
    credit TEXT,
    licence TEXT,                                -- e.g. 'CC BY-NC 4.0', 'All rights reserved'
    caption TEXT,
    is_primary INTEGER DEFAULT 0,                -- shown first in a species account
    -- Housekeeping
    status TEXT DEFAULT 'present',               -- present / missing / ignored
    cloud_only INTEGER DEFAULT 0,
    last_seen_scan TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (root_key, rel_path)
);

CREATE TABLE IF NOT EXISTS photo_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_id INTEGER NOT NULL,
    species_tvk TEXT,                            -- always set when the species is known
    species_name TEXT,                           -- kept current by remap_record_tvks.py
    specimen_id INTEGER,
    observation_id INTEGER,
    link_status TEXT DEFAULT 'proposed',         -- proposed / confirmed / rejected
    match_method TEXT,                           -- exact / synonym / fuzzy / folder / date / manual / inbox
    confidence REAL,
    review_note TEXT,                            -- candidates, why it needs a look
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (photo_id) REFERENCES photos(id),
    FOREIGN KEY (specimen_id) REFERENCES specimens(id),
    FOREIGN KEY (observation_id) REFERENCES observations(id)
);

CREATE INDEX IF NOT EXISTS idx_photos_fp ON photos(file_size, fp_fast);
CREATE INDEX IF NOT EXISTS idx_photos_status ON photos(status);
CREATE INDEX IF NOT EXISTS idx_photo_links_photo ON photo_links(photo_id);
CREATE INDEX IF NOT EXISTS idx_photo_links_tvk ON photo_links(species_tvk);
CREATE INDEX IF NOT EXISTS idx_photo_links_specimen ON photo_links(specimen_id);
CREATE INDEX IF NOT EXISTS idx_photo_links_observation ON photo_links(observation_id);
CREATE INDEX IF NOT EXISTS idx_photo_links_status ON photo_links(link_status);
```
- **Migration** (`scripts/add_photo_tables.py`): the same `CREATE … IF NOT EXISTS` strings, so
  running it twice changes nothing. Dry run by default (prints the SQL and whether each table
  exists). `--apply` takes a `backup_service` copy first. Add the strings to `reset_database.py`
  so a rebuild has them. Do not change existing tables.
- **TVK upkeep:** add `"photo_links"` to the table tuple in `remap_record_tvks.py:84`. The loop
  checks columns first, so only `species_tvk`/`species_name` will be updated.
- Mark links "rejected" rather than deleting them, so the scanner does not re-propose them.
  `species_profiles.image_path` already exists, is unused, and can be retired in favour of
  `is_primary`.
- **`paths.py` additions** (append only; never rename or move the file):
  `PHOTOS_ROOT = Path(os.environ.get('BIOSOFT_PHOTOS') or Path.home()/'OneDrive'/'Documents'/'Media')`,
  `PHOTO_INBOX = PHOTOS_ROOT/'Inbox'`, `THUMB_CACHE_DIR`.

### A6. Scanner (`shared/photo_scan.py`, a pure function; the UI runs it in a QThread)

1. Walk `PHOTOS_ROOT/Photos/Life` and `…/Microscope Photos` (include/exclude list in one constant;
   `All Other Photos` and `Originals` are excluded from linking). `os.scandir` only, no reads.
2. For each file, look up `(root_key, rel_path)`:
   - **Known, same size:** set `last_seen_scan`; nothing else. (mtime is not trusted inside OneDrive.)
   - **Known, size changed:** re-read EXIF, recompute the fingerprint and thumbnail if local;
     keep the links.
   - **Unknown:** queue it as "new".
3. Paths in the DB not seen this scan become **candidates for "missing"**.
4. **Re-link:** for each new file that is local, compute `fp_fast` and look for a missing row
   with the same `(file_size, fp_fast)`. If there is one, **update that row's `rel_path`** (the
   links survive). If a new file is cloud-only, match a missing row by `(file_name, file_size)`
   as a provisional move, and confirm when it is fingerprinted.
5. Anything still missing is set `status='missing'`. **It is never deleted**, and is shown in
   review.
6. New rows: parse the name and folder (A4). Propose links. Read EXIF and make a thumbnail only
   if local.
7. Report counts: new, moved, missing, cloud-only pending, exact, synonym, fuzzy, unmatched.
   The first run is a **dry run that writes nothing** and prints these counts (house rule).

The first-run cost if everything is local is ~1 GB of reads plus 7,391 EXIF headers and thumbnails,
a few minutes. Later scans are a stat-walk of ~7,600 entries, seconds.

### A7. UI

- **Review list** (one dialog, Observatum Tools menu): tabs "Proposed (n)", "Unmatched (n)",
  "Missing (n)". Each row shows a thumbnail, the path, the parsed name, the proposed species and
  method, and candidate specimens. Actions: Confirm, Choose species… (existing ranked search),
  Choose specimen…, Reject, Ignore file. Multi-select with "confirm all exact".
- **Viewers:** one widget, `PhotoStrip(tvk=…, specimen_id=…, observation_id=…)`, in
  `Observatum/src/views/widgets/` or `shared/`, reused everywhere (house rule: import, don't copy).
  Clicking opens a viewer (scaled `QImageReader`, arrow keys, metadata, "Open in Explorer").
  - Species account: the primary photo first, then field photos and specimen photos.
  - `record_detail_dialog.py`: under the accounts panel on the right (`body` holds scroll +
    `_accounts_panel`). Shows the observation's photos, then the species' photos.
  - `add_specimen_dialog.py`: a "Photos" group with an **Add photo…** button, which links an
    existing registered file or one picked from disk (moved into the tree via A8b's mover).
  - `DataEntry/info_panel.py`: a fourth card in the readout row (`_build_workbook_card`,
    `_build_locations_card`) showing one thumbnail and "n photos". Lazy, so typing is not slowed.
- **Examen:** later, an optional "plate" of primary photos for key species in a report. Only
  where `licence`/`credit` are set, with the credit printed under each photo.

### A8b. Inbox

- `PHOTO_INBOX` folder. The screen is a `QListView` in IconMode with a model that loads
  thumbnails in a worker (QImageReader scaled). Show the date and a GPS marker. Group by day.
  Multi-select.
- **Pick the species** with the same ranked search as Data Entry and Add Specimen.
  `SpeciesSearch` (`Observatum/src/views/components/species_search.py`, used by
  `add_specimen_dialog.py:16`) is backed by `shared.species_rank.rank_matches`
  (`DataEntry/entry_grid.py:547`). Neither file is in the snapshot, so confirm both.
- **Move and rename, never delete:** destination
  `Life/<folders>/<Genus species>/<Genus species - Common name N>.jpg`. N is the next free
  number. Use the preferred common name from UKSI; if there is none, the name has no
  " - common" part. The folder path comes from the existing species folder if one exists;
  otherwise a "New species" folder under `Life/_Unsorted` (decision P6).
  `shutil.move` within one volume is a rename. Write the `photos` row (with `fp_fast` computed
  *before* the move) and a confirmed link with `match_method='inbox'`. Check for a name clash
  before moving. On any error, leave the file in the Inbox.
- **Optional observation:** date from `taken_at` (local time). Location from GPS: WGS84 lat/long
  → shared converter (B2) → E/N → grid ref at 6 or 8 figures (phone GPS is ~5–10 m, so 8-fig is
  defensible; decision P7). VC from B3. Otherwise one site and grid ref for the whole batch.
  Goes through the Data Entry staging and commit path (so the backup-before-commit and
  double-entry check apply), not straight into `observations`.

### Backups

`Media` (44.3 GB) is in OneDrive only. It is **not** in the `D:\` mirror, which copies only
`Biological Software` and `C:\BiologicalSoftware_Backups`. OneDrive is sync, not backup: a
deletion or a ransomware encryption syncs too. Its recycle bin and Files Restore cover about 30
days. Options:
1. A third robocopy line `/MIR` to `D:\BiologicalSoftware_Offsite\Media`. ~44 GB first run
   (~2–3 h by the measured 3.8 GB in 11 min), incremental afterwards. **It hydrates every
   cloud-only file**, so the PC needs ~45 GB free, or Media set to "Always keep on this device".
2. Leave photos out of the mirror but back up `observatum.db` (the links) as now. The links are
   cheap to rebuild by a re-scan **only if the files keep their names**.

`photos`/`photo_links` live in `observatum.db`, so they are already covered by every existing
layer. The thumbnail cache needs no backup.

### Decisions Wil makes first

- **P1** Where the library lives long term, and is it local? Run a read-only count of cloud-only
  files and GB first.
- **P2** Backup: add Media to the `D:\` mirror (option 1) or not.
- **P3** Stacks: register stacked outputs only, or the source frames too (and how to tell them
  apart: a folder or a filename pattern).
- **P4** Videos in scope? (192 files. Register as `media_type='video'` with no thumbnail, or skip.)
- **P5** Auto-confirm exact name plus a single date-matched specimen, or review everything the first time.
- **P6** The inbox destination when a species has no folder yet.
- **P7** Grid-ref precision from phone GPS (6 or 8 figures), and whether to create observations at all.
- **P8** Default credit and licence (e.g. "Wil Heeney / Flauna", "All rights reserved" or CC BY-NC).
- **P9** Photos of a species with no specimen or observation: link to the TVK only (yes, by design?).

### Build checklist (photos)

| # | Step | Est. |
|---|---|---|
| 1 | Read-only `check_media_library.py`: counts, extensions, cloud-only count and GB, parse hit rate, UKSI exact/synonym/fuzzy/none, specimen date matches | 0.5 day |
| 2 | Decisions P1–P9 | (Wil) |
| 3 | `paths.py` additions; `add_photo_tables.py` (dry run, backup, idempotent); `reset_database.py`; `remap_record_tvks.py` tuple | 0.25 day |
| 4 | `shared/photo_scan.py` (walk, parse, fingerprint, EXIF, re-link, missing) and unit tests (regexes, roman months, re-link by fp, cloud-only skip) | 0.75 day |
| 5 | Thumbnail cache, `PhotoStrip` widget and viewer | 0.5 day |
| 6 | Review dialog | 0.5 day |
| 7 | Placement in the species account, record detail, specimen dialog and info panel; Add photo… | 0.5 day |
| **A8 total** | | **~3 days** (backlog says ~2; step 1 and review are the extra) |
| 8 | A8b inbox grid, species pick, mover, card write | 1.5 days |
| 9 | A8b optional observation via staging (GPS → grid ref → VC) | 0.5–1 day (needs B2/B3) |
| 10 | Examen photo plate | later, 0.5 day |

---

## Part B — Geo (I3b / F29, I3c / F30)

### B1. Libraries

| | Latest | cp314 win_amd64 | Notes |
|---|---|---|---|
| **pyproj** | 3.8.0 (PROJ 9.8.1), Sep 2026 | yes | Without the grid, `EPSG:27700→4326` falls back to "OSGB36 to WGS 84 (6)", a 7-parameter Helmert with ±2 m stated accuracy. **Measured median 1.8 m, max 4.9 m**, identical to the pure-Python Helmert. With `uk_os_OSTN15_NTv2_OSGBtoETRS.tif` (download from cdn.proj.org, or `pyproj.network.set_network_enabled(True)`) it uses OSTN15, accurate to ~0.1 m. The grid download was blocked in this sandbox, so it was not measured here. |
| **shapely** | 2.2.0 (7 Oct 2026) | yes | Needs numpy. Fast `contains`, STRtree. Only needed at **build** time in the design below. |
| pyshp | 3.1.6 | pure Python | Reads `.shp`/`.dbf` with no GDAL. A lighter alternative to geopandas for the build script. |
| geopandas / pyogrio | 1.2.0 / 0.13.0 | yes | What `create_vc_lookup_db.py` uses now. Heavy, but it works. |
| OSGridConverter | 0.1.3 (2017) | py3 | **Inverse is wrong, up to 1.4 km** (B0.1). |

**Accuracy needed:** a 100 m square for VC, and maps. The OS says a Helmert transformation is
good to "about 3 metres", and that matched the measurement: max 4.9 m over all of GB including
Scilly and the Hebrides. OSTN15 is not needed for this suite. pyproj is optional, as a test oracle.

### B2. One converter: `shared/osgb.py` (pure Python, no dependencies)

```python
def gridref_to_en(ref) -> (e, n, precision_m) | None   # moved from VCLookupService.parse_grid_ref (verified correct)
def gridref_centre(ref) -> (e + p/2, n + p/2)
def en_to_gridref(e, n, digits=6) -> str
def osgb_en_to_wgs84(e, n) -> (lat, lon)        # inverse TM (Airy 1830) + Helmert OSGB36→WGS84
def wgs84_to_osgb_en(lat, lon) -> (e, n)        # Helmert WGS84→OSGB36 + forward TM
def gridref_to_wgs84(ref, at="centre") -> (lat, lon)
```
- **Helmert parameters** (OS guide; WGS84→OSGB36 is the same set with every sign flipped).
  OSGB36→WGS84: tx +446.448, ty −125.157, tz +542.060 m; s −20.4894 ppm; rx +0.1502″,
  ry +0.2470″, rz +0.8421″. Ellipsoids Airy 1830 (6377563.396 / 6356256.909) and GRS80/WGS84
  (6378137 / 6356752.3141). The TM constants are already in `osgb.py` and the wizard. The
  scratch implementation (inverse TM with the XIIA term and `abs()` in the meridional loop, then
  a cartesian Helmert, then an iterative geodetic) gave **median 1.8 m, max 4.9 m on TP01–TP40**.
- **Callers switch** to `from shared.osgb import …`: the wizard's `_osgb36_to_wgs84`
  (`validation_worker.py:297`, delete and import); `DataEntry/osgb.lonlat_to_en` (becomes a
  3-line shim, which fixes the ~110 m overlay shift); `VCLookupService.parse_grid_ref`,
  `get_1km_square`, `get_10km_square` (delegate); the scheme and specimen import workers if they
  convert (grep `latitude` in their `validation_worker.py`); A8b's GPS→grid ref.
  `grid_converter_service.py` and `grid_ref_service.to_coordinates()` go to `_archive`.
- **Tests** (`tests/test_osgb.py`, no DB): the 40 OS test points (copy the two OS test files
  into `tests/data/`), lat/long within 5 m both ways. Round trip E/N → lat/long → E/N within
  0.01 m. Grid-ref parsing for 2/4/6/8/10 figures, centre versus corner, invalid letters. The
  OS projection worked example (Airy lat/long → E 651409.903, N 313177.270 to 1 mm). If pyproj
  is installed, a cross-check: within 5 m of pyproj's Helmert pipeline on 1,000 random GB points.

### B3. VC at boundaries (I3b)

**Data, built once.** Add a table to `vc_lookup.db` with an extended
`create_vc_lookup_db.py --splits` (pyshp + shapely, OSGB shapefile, in E/N):
```sql
CREATE TABLE IF NOT EXISTS vc_split_squares (
    grid_1km TEXT NOT NULL,
    vc_number INTEGER NOT NULL,
    area_fraction REAL NOT NULL,       -- share of the 1 km square's LAND in this VC
    rings_json TEXT NOT NULL,          -- the VC polygon clipped to this square, E/N, [[outer],[hole]...]
    PRIMARY KEY (grid_1km, vc_number)
);
```
Rows go in for every square whose clipped area meets ≥2 VCs. The same build also catches
squares whose **centroid is in the sea** but which overlap 1 VC (to fix the coastal misses;
measure how many). Each clipped piece is small (tens of vertices), so the runtime test is
**pure-Python ray casting with no shapely or pyproj at runtime**. That was validated against
shapely in a scratch script: 0 mismatches in 5,000 points on a 2,200-vertex polygon with a hole.

**Runtime (in `VCLookupService`, keeping its API):**
1. Parse the ref → E/N/precision (shared).
2. Precision **≤ 100 m** (6 figures or finer) and the 1 km square is in `vc_split_squares`:
   test the **centre** of the ref's square against each piece. For a 100 m square, also test
   its 4 corners. If they all agree → that VC. If they disagree → **"on a boundary"**, with
   both VCs.
3. Precision = 1 km in a split square → "on a boundary: VC34 62% / VC35 38%". Whether to fill
   the majority VC with a flag or leave it blank is decision G1.
4. Precision 2 km or 10 km → check all 1 km squares inside it. If more than one VC → "on a
   boundary" (this also fixes B0.4's SW-corner inheritance).
5. Otherwise use the 1 km lookup as now.

Return the existing tuple plus a `boundary` flag/text, so Data Entry can show it in the
`_location_warning` line of `info_panel.py`. `get_vc_batch` gets the same logic.

**Expected tests:** `SO539092` → 34, `SO539069` → 34 (F29). A fine ref clearly inside each
side of one split square. `SO5309` (1 km) → on a boundary 34/35. A ref fully inside a VC →
unchanged. A coastal square whose centroid is offshore → its land VC.

### B4. Read-only measurement script (`scripts/check_vc_and_latlong.py`, "Nothing has been changed")

**Part 1 — VC disagreements:** for `observations`, `specimens` and `recording_scheme` (anything
with `grid_ref` + `vc_number`), compute the new VC (B3) and list:
(a) stored ≠ new, with ref, precision, source, country change E↔W (**those first**); (b) on a
boundary (coarse); (c) previously blank, now resolvable. Use the 125 iRecord disagreements in
F29 as the expected cross-check (iRecord computes from the precise position). Write a CSV for
Wil's judgement; change nothing.

**Part 2 — Identify the 3,332 (F30):** for each record with grid ref and lat/long, compute four
candidates: no-shift corner, no-shift centre, Helmert corner, Helmert centre. Label each record
by the nearest candidate within 2 m, else "other".
- Expect ~3,332 labelled *no-shift corner* (the wizard's maths), and the 20,702 iRecord records
  as *Helmert centre* or *corner*. **That settles G2 from data:** whichever convention iRecord
  uses is the one to adopt.
- Cross-tabulate by `source`/`dataset_name`/`import_notes`/`geodetic_datum`/`created_at` day. Note
  that the backfill measured **"Commercial 3,332 of 4,511 records with no vice-county"**: the
  same number. Check whether it is the same set (the wizard set neither VC nor the shift).
- Report the shift distribution (median and max, expected ~111 / 136 m) and 10 samples.

**Part 3 — Dry-run recompute:** for the *no-shift* set only, show old → new lat/long and the
distance. `--apply` (a later, separate step, after "proceed"): `backup_service` /
`conn.backup()` to `C:\BiologicalSoftware_Backups\reference\observatum_pre_latlong_fix_<ts>.db`,
then `UPDATE … SET latitude=?, longitude=?, geodetic_datum='WGS84' WHERE id=?` in one
transaction. Read back 5 rows, rerun Part 2 (no-shift count must be 0), then
`check_reference_figures.py` (expect no movement: VC, SQI and exports do not use lat/long).

### B5. Decisions

- **G1** A 1 km ref in a split square: fill the majority VC and flag it, or leave it blank and flag it?
- **G2** Stored lat/long = square centre or SW corner (let Part 2 show what iRecord does)?
- **G3** Do stored VCs that disagree get corrected one by one from the CSV, or not at all?
  Rule: stored VCs are not touched automatically.
- **G4** Is pyproj installed as a test-only dependency (an oracle), or are the OS test points enough?
  (Recommendation: test points only.)

### B6. Build checklist (geo)

| # | Step | Est. |
|---|---|---|
| 1 | `shared/osgb.py` + `tests/test_osgb.py` (OS TP01–TP40, round trips, parsing) | 2 h |
| 2 | Switch callers (wizard, `DataEntry/osgb.py` shim, VCLookupService delegation); archive `grid_converter_service`, `grid_ref_service.to_coordinates`; import-check every touched module; correct F30's note on OSGridConverter | 1.5 h |
| 3 | `check_vc_and_latlong.py` Part 2 (identify the 3,332, settle G2) and Part 3 dry run | 1.5 h |
| 4 | Apply the lat/long recompute after "proceed" (backup, apply, read back, reference check) | 0.5 h |
| 5 | Check the `.prj` of `vc_brc.shp`; extend `create_vc_lookup_db.py --splits` (pyshp + shapely, build-time) writing `vc_split_squares` into a **copy**; report split and coastal counts | 3 h |
| 6 | VCLookupService boundary logic (single and batch) + `boundary` flag; Data Entry warning text; tests (F29's two sites, coarse refs, coastal) | 3 h |
| 7 | `check_vc_and_latlong.py` Part 1 → CSV for Wil | 1 h |
| **Total** | | **~1.5–2 days** (backlog: I3b 0.5 day + I3c 1 h + a dry run; the extra comes from B0.1, B0.2 and B0.4) |

---

## Sources

- OS, *National Grid Transformation OSTN15* (OSTN15 ~0.1 m; Helmert "about 3 metres"):
  https://docs.os.uk/more-than-maps/a-guide-to-coordinate-systems-in-great-britain/from-one-coordinate-system-to-another-geodetic-transformations/national-grid-transformation-ostn15-etrs89-osgb36
- OS OSTN15/OSGM15 test files (TP01–TP40), as mirrored in grid-banger: https://github.com/thruston/grid-banger
  (`osgb/test/OSTN15_OSGM15_TestInput_OSGBtoETRS.txt`, `…TestOutput_OSGBtoETRS.txt`)
- convertbng (an OSTN15 implementation; background): https://pypi.org/project/convertbng/
- PROJ grid `uk_os_OSTN15_NTv2_OSGBtoETRS.tif`: https://cdn.proj.org/uk_os_OSTN15_NTv2_OSGBtoETRS.tif
- BRC Watsonian vice-county boundaries (latest edits 2 Nov 2020; GitHub repo): https://www.brc.ac.uk/node/269
  · https://github.com/BiologicalRecordsCentre/vice-counties · NBN mapping tools: https://nbn.org.uk/tools-and-resources/nbn-toolbox/for-mapping/
- PyPI JSON (versions and wheels, 9 Oct 2026): https://pypi.org/project/pillow/ · https://pypi.org/project/pillow-heif/ ·
  https://pypi.org/project/piexif/ · https://pypi.org/project/ExifRead/ · https://pypi.org/project/ImageHash/ ·
  https://pypi.org/project/pyproj/ · https://pypi.org/project/shapely/ · https://pypi.org/project/OSGridConverter/ ·
  https://pypi.org/project/pyshp/ · https://pypi.org/project/RapidFuzz/
- Pillow ExifTags (IFD, Base, GPS enums): https://Pillow.readthedocs.io/en/latest/_modules/PIL/ExifTags.html
- OneDrive file attributes (P/U/R states): https://www.techtarget.com/searchenterprisedesktop/blog/Windows-Enterprise-Desktop/OneDrive-File-Attributes-Uncovered
  · Microsoft forum on pinned/unpinned detection: https://techcommunity.microsoft.com/discussions/onedrivedeveloper/detect-file-attribute-for-files-on-demand-pinnedunpinned/159895
  · attribute constants: https://learn.microsoft.com/en-us/windows/win32/fileio/file-attribute-constants
- Cloud Files hydration policies: https://learn.microsoft.com/en-us/uwp/api/windows.storage.provider.storageproviderhydrationpolicy
- Ultra HDR JPEG (Pixel/Android 14): https://www.gsmarena.com/newscomm-59770.php
- Qt QImageReader (`setScaledSize`, `setAutoTransform`): https://doc.qt.io/qtforpython-6/PySide6/QtGui/QImageReader.html

---

# Groundwork 06: Checklist order for drawers, and report contents for winter

## 9 October 2026. Read-only research for backlog A1 (open question), E3, E4, E6, E7, E8, E8b

Local inputs read: `38_Report_Survey.md`, `08_Examen.md`, `03_Backlog.md` (A1, E3–E8b).
Every external claim has a URL in §C. **"Unverified"** means the page did not show the
detail and it has to be checked by opening the file.

---

# PART A: Systematic (checklist) order for "Drawer in hand"

## A0. The problem in one paragraph

UKSI's `sort_code` gives genera **alphabetically within a family**, and the extract has no
subfamily or tribe ranks. So Carabidae comes out *Abax, Acupalpus, Aepopsis…*. Duff's
order is *Cicindela, Cylindera, Brachinus, Omophron, Calosoma, Carabus, Cychrus, Leistus,
Nebria…*. (This is confirmed below from Duff 2008 itself. Note that **Brachinus and
Omophron come before Calosoma.**) The fix is to supply the order from outside UKSI as
`shared/checklists/<order>.csv` (`family,genus,species`, in checklist order).

**The finding that changes the scope:** only **Coleoptera and Lepidoptera** have a
checklist whose genus order differs from alphabetical. The current Diptera and
Hymenoptera checklists are alphabetical within family by design, and the Hemiptera list
on British Bugs is alphabetical too. For those orders UKSI's alphabetical order already
*is* checklist order below family level. Only the **family sequence** is missing, and that
is a list of about 100 lines that you can type yourself.

## A1. Coleoptera: sources compared

| Source | What it is | Order preserved? | Format | Licence / terms | Verdict |
|---|---|---|---|---|---|
| **Duff (ed.) 2018**, *Checklist of Beetles of the British Isles*, 3rd ed., Pemberley | The authority. Subfamilies, genera, species; subgenera treated consistently; higher taxa phylogenetic where possible | Yes: the whole sequence | Printed book. **No official electronic file found** on coleoptera.org.uk or colsoc.org | Copyright; no reuse terms published | Best content, but no file. You own it |
| **Duff (ed.) 2008**, 2008 edition (PDF, mirrored at zin.ru; originally hosted by *The Coleopterist*) | Full systematic list, suborder > superfamily > family > subfamily > tribe > genus > subgenus > species | **Yes.** Carabidae opens Cicindelinae: *Cicindela* (campestris, hybrida, maritima, sylvatica), *Cylindera*; Brachininae: *Brachinus*; Omophroninae: *Omophron*; Carabinae / Carabini: *Calosoma*, *Carabus*… | Text PDF, so it can be parsed | **"Copyright © A.G. Duff, 2008… All rights reserved. No part… may be reproduced, stored in a retrieval system…"** | Parseable, but the nomenclature is 10 years older than Duff 2018. Rights reserved |
| **ColSoc recording spreadsheet** (`ColSoc-Spreadsheet.xlsx`; older `.xls` also offered) | A recording proforma. Fields: family, species, common name, locality, grid ref, VC, dates, finder, recorder, determiner, obs type, voucher, plus optional stage, sex, method, habitat, image, notes | **Unverified.** Neither the spreadsheet page nor "How to record" mentions an embedded species list, dropdown or checklist numbers. It only says to follow Duff (2018) for nomenclature | xlsx | None stated | Probably no species list. Open it and look for a hidden lookup sheet. As Conservation Officer you can also ask whether ColSoc holds Duff 2018 electronically |
| **colsoc.org/checklist** | A book page for Duff 2018 with a buy link | n/a | No download | None stated | Not a source |
| **coleoptera.org.uk** (Beetles of Britain & Ireland) | Checklist page = book notice. The family page for Carabidae is a 23-image gallery in no particular order | No | HTML | None stated (BRC/JNCC/UKCEH logos) | Not a source |
| **ukbeetles.co.uk/classification** | Index by suborder > superfamily > family, plus a **downloadable checklist spreadsheet** "that includes the vast majority of the UK species… what we use to index our reference collection" | States it follows "a systematic list based on… the latest Palaearctic checklist, as well as Andrew Duff's 2018 Checklist". Whether it has subfamily/tribe columns is **unverified** | Spreadsheet (link not exposed to the fetcher; download it in a browser) | No licence; shared "in the hope that others might find it useful" | **Most practical file.** Built for exactly this use (ordering a reference collection). Mixes Palaearctic and Duff order |
| **Wikipedia** lists, e.g. *List of ground beetle (Carabidae) species recorded in Britain* | Organised by subfamily and tribe and cites Duff 2008. Genera run *Cicindela, Cylindera, Brachinus, Omophron, Calosoma, Carabus, Cychrus, Leistus, Nebria, Eurynebria, Pelophila, Notiophilus, Blethisa, Elaphrus, Loricera…* | Carabidae yes. The **Staphylinidae** list has no headings and only an implied subfamily order. Coverage across families is uneven | HTML tables | **CC BY-SA 4.0** (standard Wikipedia licence; not shown on the page itself) | The only openly licensed beetle order. Good for Carabidae; patchy elsewhere; 2008-based names |
| **UKSI** (NHM) | Wil's July 2025 and 2023 extracts: alphabetical within family | No | — | CC BY 4.0 | Confirms the problem. An old NBN forum thread (Raper) mentions work on a "weighting" column in the Organism table. If your extract has an `ORGANISM_MASTER` weight or sequence column, check it before anything else |

### Recommendation: Coleoptera

1. **First, 10 minutes:** open the ColSoc xlsx and the ukbeetles spreadsheet in Excel.
   - If either holds a full species list in Duff order, use it. Prefer ukbeetles, which
     is built for collection indexing.
   - Read its order straight into the CSV, as in §A5.
2. **Otherwise, the clean route:** use **genus-level order** taken from your own Duff 2018.
   - British beetles have roughly 1,100 genera, and the collection needs only the
     families it actually holds. Type `family,genus,` with the species left blank, one
     family at a time, as drawers come up.
   - Species stay alphabetical within each genus. Duff is close to that anyway, apart
     from subgenus blocks.
   - The hook needs one rule for this: a blank species means a genus-level row, so any
     species of that genus sorts by genus position and then alphabetically.
3. **Ask Andrew Duff (or Pemberley) for the electronic checklist.** As ColSoc Conservation
   Officer and organiser of a national scheme, you are well placed to ask. With a yes, you
   get the whole file under licence and with current names.
4. Use Duff 2008 or Wikipedia only as a **typing aid**, checked against Duff 2018.
   Duff 2008 is "all rights reserved". Wikipedia is CC BY-SA, but its names date from 2008.

**On rights (not legal advice):** a list arranged by an author's judgement can carry
copyright in its arrangement, and UK database right as well. Using that order privately to
arrange your own cabinet is low-risk. **Do not commit a transcribed Duff CSV to a public
repository or ship it in a distributed build** without permission. Keep it in
`shared/checklists/`, git-ignored, or mark it "personal use".

## A2. Lepidoptera: the best source of any order

**Agassiz, Beavan & Heckford (2013), *Checklist of the Lepidoptera of the British Isles***,
with its data on the **NHM Data Portal** (DOI 10.5519/0093915).

- **Licence: CC BY-SA 4.0.** Openly reusable with attribution and share-alike. Credit
  "Agassiz, Beavan & Heckford; NHM Data Portal".
- **Resources:**
  - `Agassiz Lepidoptera 20220628a.xlsx`: 7,166 records, updated 28 June 2022 by Les
    Evans-Hill and Chris Raper. **Use this one.**
  - The amended checklist of 19 February 2016: 6,750 records.
  - The 2014 first draft: 4,073 records.
- **Contents:** "current scientific names & codes", for translating between the old
  Bradley & Fletcher (B&F) codes and the new ABH codes.
  - ABH codes take the form family.species (for example 1.001, 70.258). Sorted
    numerically they *are* checklist order.
  - The exact column names are **unverified**, because the portal preview was down and API
    access is blocked here. Open the file to see them.
- **To CSV:** sort by ABH code (family number, then species number as an integer) and
  write `family,genus,species`. Better still, keep the ABH code as a fourth column, so the
  hook can sort on it directly and the drawer screen can print it. Lepidopterists use those
  numbers.

## A3. Diptera

**Chandler, *Checklist of Diptera of the British Isles***, Dipterists Forum, version 28
November 2025. File: `BRITISH ISLES CHECKLIST 2025_11.pdf`.

- **Updates:** published in *Dipterists Digest*, with the PDF replaced after each one.
- **Arrangement:**
  - Families are grouped by suborder, infraorder and superfamily (after McAlpine 1989),
    from Lower Diptera through Brachycera to Schizophora.
  - Subfamilies and tribes are given where agreed.
  - **Within families "valid taxa are listed alphabetically"**, except the Cecidomyiidae
    subfamilies, which are in phylogenetic order. In Syrphidae all genera are alphabetical
    and higher categories are left out.
  - There is no sequential numbering. The figures after each family are species counts.
- **Licence:** none stated. The site shows "© Dipterists Forum".
- **Route:** **UKSI alphabetical order is already correct within each family.** All you
  need is `diptera_families.csv`: family names in Chandler's sequence, about 110 lines,
  typed from the PDF's family list. A family sequence is a minimal fact-list; cite Chandler.
  - Optional refinement: Chandler places genera alphabetically *within* a subfamily, so
    true order is subfamily first. This matters only in large families with subfamilies
    (Tachinidae, Muscidae and others). Leave it until a Diptera drawer needs it.

## A4. Hymenoptera and Hemiptera

**Hymenoptera**

- **Broad (2014)**, *Checklist of British and Irish Hymenoptera: Introduction*,
  Biodiversity Data Journal 2: e1113, **CC BY 4.0**. Arrangement: **"Otherwise, the
  checklist is alphabetical."** A systematic order was considered and rejected for stated
  reasons. Superfamilies are grouped into sawflies, parasitoids and aculeates, following
  Sharkey (2007).
- **BWARS**, *List of all known species concepts* (November 2022). File:
  `20221110 species list.csv`.
  - Columns: `sf_name, f_name, g_name, descriptive, status, current_understanding`.
  - **Alphabetical** genera and species (*Andrena, Anthidium, Anthophora, Apis,
    Bombus…*), with synonyms included as rows.
  - Licence: none stated ("©BWARS 2020").
- **Route:** UKSI alphabetical order matches the checklist convention. Supply only a
  superfamily and family sequence, taken from the Broad 2014 table, which is downloadable as
  CSV and CC BY.

**Hemiptera**

- **British Bugs** (Bantock), systematic list for Heteroptera.
  - Columns: RS, current name, previous name, authority, common name, family, status.
  - It is grouped by recording scheme (shieldbugs, plant bugs, water bugs), with
    **families alphabetical and species alphabetical**, based on Nau (2006) plus revisions.
  - The site's *gallery* pages are systematic. Pentatomoidea, for example, runs
    Acanthosomatidae, Scutelleridae, Cydnidae, Thyreocoridae, Plataspidae, Pentatomidae.
  - No licence stated.
- **Route:** as for Diptera. Type a family sequence from the gallery pages or the Bantock
  & Botting field guide, and let UKSI order the rest. No downloadable systematic Hemiptera
  checklist was found.

## A5. Turning a source into the CSV

The method is the same whatever the source. Keep the scripts outside the downloads
directory, and run Python with `-I` on downloaded files.

1. **Get rows in source order.**
   - xlsx: `openpyxl` / `pandas.read_excel`, then forward-fill the family and genus
     columns where the sheet uses merged or heading rows.
   - PDF (Duff 2008, Chandler): `pdftotext -layout`, then a regex. Genus lines are
     UPPER-CASE plus an authority (`^([A-Z]{3,})\s+[A-Z(]`). Species lines are a lower-case
     epithet plus an authority. `Subfamily`, `Tribe` and subgenus `(Xxx)` lines are skipped
     but can be kept as optional columns.
2. **Reconcile names with UKSI.** Put each `genus species` through Codex's synonym
   resolver (the July 2025 UKSI synonyms, handover 27).
   - Write `family,genus,species` using **UKSI's current names**, so the hook matches on
     what the collection stores.
   - Log anything unmatched to `unmatched.txt`. Those taxa fall back to alphabetical
     order, which is the hook's current behaviour, so nothing breaks.
3. **Write the CSV** in row order, adding an optional `seq` (and `code` for ABH). The hook
   then keys on: order position, family position in the CSV, genus position, species
   position; with UKSI `sort_code` for anything absent.
4. **Stamp it:** add a header comment or companion `.txt` giving source, edition, date,
   licence, and match rate (e.g. "Duff 2018 genus order, transcribed WJH, 214 genera,
   personal use").

**Fit with Examen:** `examen_data.in_taxonomic_order` (order × 1,000,000 + UKSI
`sort_code`, item E19) could read the same CSVs. That would put appendices into Duff
order too, which is how Telfer and Wilson present them (`38` §4).

---

# PART B: What an invertebrate survey report should contain

## B1. What the standards require

**CIEEM, Guidelines for Ecological Report Writing (Dec 2017).** No later edition found.

- **Templates:** Appendix A covers the PEA report, Appendix B the EcIA report.
- **Proportionality:** apply the templates proportionately (2.6).
- **Front matter:** cover with title, date, author, client, unique reference and
  **version** (5.2); QA (3.13, 3.15); contents listing figures and tables (5.7–5.8);
  a one-page summary (5.3–5.4).
- **Methods:** desk study (contacts, data requested, search area, dates). Field survey:
  methods, **surveyors' names and qualifications**, **dates and times**, **weather**,
  guidance followed, **departures from it**, limitations (A7, 5.16–5.17).
- **Results:** use "the clearest format… with complete data to allow validation" (5.20).
  Long species lists go to an appendix, with the full dataset available on request (5.34).
  Metadata travels with raw data sent to records centres (5.22).
- **Data validity:** state for how long the data can be relied on (5.28). NBN data must
  not be reproduced without the provider's permission (3.11).
- **Confidentiality:** the title page may carry "confidential", with the reason stated
  (5.2).

**CIEEM, EcIA Guidelines v1.3 (Sept 2024).**

- **Importance:** state it within a **geographic frame**, from international down to
  local, district or parish (4.7–4.8).
- **What makes a feature important:** rich assemblages are a criterion (4.6). Use existing
  criteria where they exist (4.20). Distribution, abundance and trends are central (4.21).
- **Methods and limitations:** use standard methods and justify any departure (3.12).
  State the limitations — information, access, season (3.13).
- **Data sharing:** "CIEEM encourages all practitioners to share data… through… Local
  Record Centres" (1.14).

**CIEEM, EcIA Checklist (2019).**

- Limitations are identified and their implications explained (item 16).
- Methods follow published good practice, with deviations justified (18).
- Surveyors hold the competencies (19).
- Significance is given with its geographic scale (22).

**CIEEM, Advice Note on the Lifespan of Ecological Reports and Surveys (April 2019).**

| Age of data | What it means |
|---|---|
| Under 12 months | Likely valid |
| 12–18 months | Likely valid, with exceptions; flag where an update may be needed |
| 18 months – 3 years | An ecologist revisits the site and reviews validity |
| Over 3 years | Unlikely to be valid |

This is the source behind Examen's "two-year validity" stamp. **Consider quoting these
bands instead of the single figure.**

**BS 42020:2013** (as reproduced in a Milton Keynes Council evidence document):

- Competence (4.3.2); objective professional judgement with documented reasoning
  (4.4.1–4.4.3); proportionality (5.5).
- A brief **non-technical summary** (6.5.1).
- "**Survey data should be made available to local biological records centres**", unless
  the contract restricts it, and formatted for easy transfer (6.4.7).
- **Identify all relevant limitations** and state the significance of each (6.7.1–6.7.2).
- Data "not normally more than two/three years old" (6.2.1).

**CIEEM, Accessing and Using Biodiversity Data (2023).**

- Submit all relevant data to the LERC "unless the client has expressly refused
  permission". **Put this in your terms and conditions** (8.1).
- Some local planning authorities want data shared on completion or consent (4.8).
- iRecord is a verified route (4.7). NBN data does not replace LERC data (5.4).
- **Edit out sensitive records**, since reports end up on planning portals (7.2,
  footnote 12).
- Metadata travels with the data (9.4–9.5).

**Natural England NERR005, Drake, Lott, Alexander & Webb (2007).** Only §§1–3 could be
extracted. The PDF text stops at Chapter 3.

- Note the weather in the write-up (2.27).
- Seven visits, roughly monthly from April to October, is a "reasonably thorough"
  terrestrial benchmark (2.20). Single visits only in defined cases (2.19).
  Out-of-season results are poor (2.24).
- Standardise sampling units (2.6–2.7); surveyors' catches differ (2.9).
- Keep casual records in the overall evaluation (2.10).
- SAT condition thresholds apply only to lists from standard protocols (3.20).
- Compare across sites, management units or character areas, including SAT rankings
  (3.24, Fig. 1).
- Rarity indices / SQI (3.51–3.56); IEC (3.62); abundance (3.66+).
- **Table 17, "Suggested report format" (p. 86), and Tables 15–16 (client and surveyor
  responsibilities, project brief) could not be read here.** Open p. 84–86 of your own
  copy: it is the most directly relevant page in the literature, and I could not get its
  text.

**Pantheon** (BRC help pages).

- **Scoring:** SQI = ΣSQS ÷ species × 100. Treat any SQI from 15 or fewer species with
  caution. % representation: 10–20% suggests good quality, 21% or more a good proportion
  of characteristic species. % representation also needs caution where 10 or fewer
  species are coded to a category.
- **Bracketed statuses** are out of date.
- **Caveats on interpretation:**
  - A long list may mean a well-worked site rather than a rich one.
  - Taxonomic balance affects results.
  - A site important for one rare species may look poor on the indices.
  - "More work is required… to produce benchmarks and site ranking."
- **Reported condition** carries a confidence level: **high** for ISIS-compliant
  sampling, **medium** for semi-compliant, **low** for unstructured collecting or
  downloaded data.
- **Citation:** cite the version (3.7.6) and the access date, and read the disclaimer
  first.

**Saproxylic (Fowles 1999; Alexander 2004)** is already specified in `38` §3 and `39` §4.
Present SQI with its scoring species, IEC by grade, the national or county rank (khepri),
configurable thresholds, and the cumulative survey period.

**Practice survey (`38`)** gives the common shape:

- Bullet-point summary; introduction and site; legislation and policy.
- Methods, including the evaluation method and personnel.
- Results: totals, taxonomic summary, key species with accounts, Pantheon analysis,
  saproxylic analysis.
- Evaluation against SSSI and Local Wildlife Site guidelines.
- A hedged geographic value statement; mitigation; references.
- Annexes: status definitions, species lists, compartments, photos.

**Survey-only alternative:** where no sampling is done, the WSP/Cory DCO appendix (2025)
shows an IHP (invertebrate habitat potential) grading of 11 habitat elements, A to E, per
survey area. It reports a Pantheon version but no Pantheon outputs. This is the kind of
report Examen should *not* be needed for, but it is a format clients will ask for.

## B2. Section checklist, mapped to the software

Key: **HAVE** = Examen workbook / PDF / Word produces it now. **PART** = the data exists
and partial output exists. **NEW** = needs building. **PROSE** = author's text; the
software can only supply facts for it.

| # | Section | Tables / figures it needs | Source of requirement | Software |
|---|---|---|---|---|
| 1 | Cover and document control | Title, client, ref, version, date, author, QA, "confidential" flag | CIEEM RW 5.2, 3.13 | **PART**: stamp has run date and Codex version; no ref/version/QA block |
| 2 | Non-technical / executive summary | Bullets; headline metrics; value statement | CIEEM RW 5.3; BS 42020 6.5.1 | **PART**: Summary sheet metrics; bullets **NEW** (could draft from metrics) |
| 3 | Introduction, site, brief | Site location map; boundary on OS base | CIEEM RW A5 | **NEW** (Observatum vector map could export a site/compartment figure) |
| 4 | Legislation and policy | Legal and priority status table (WCA Sch.5, Habitats Regs, S41, LBAP) for species found | CIEEM RW A6; `38` §7 | **PART**: Codex has instrument-named designations, greyed by jurisdiction; no stand-alone legal table |
| 5 | Desk study | Records within *x* km: species, status, latest date, distance; data sources and dates | CIEEM RW A7.1; Data guidance 2023; Sea Link format (`38` §4) | **NEW**: needs LERC import; same shape as contributed records |
| 6 | Methods: field | **Survey effort table**: visit dates, times, weather, surveyors, methods per compartment, trap-days, sample units | CIEEM RW 5.16–5.17; NERR005 2.6, 2.20, 2.27 | **NEW, data largely exists** in Observatum (dates, method, sub_location, recorder); weather/times likely not captured |
| 7 | Methods: identification | Groups identified, groups not identified, experts used, keys, voucher/collection deposit | NERR005 ch. 6; CIEEM RW 5.17 | **NEW**: a taxonomic-coverage table (see 11) answers half |
| 8 | Methods: evaluation | Framework stated: Pantheon version, Codex version, SQS basis, jurisdiction, thresholds cited (Telfer / Kirby-Lambert; Fowles / Alexander) | `38` §9; Pantheon citation | **HAVE**: stamp and threshold notes (Summary sheet) |
| 9 | Limitations | Season coverage vs April–October benchmark; visits; weather; access; methods not used; unidentified groups; species Pantheon can't analyse; data age band | CIEEM RW/EcIA 3.13; BS 42020 6.7; NERR005 2.20–2.24; Pantheon caveats | **PART**: Pantheon coverage gap and low-sample ▲ exist; an auto-drafted facts list is **NEW** |
| 10 | Results: totals | Species, records, analysed by Pantheon, no-TVK | `38` §4 (H2 Table 7) | **HAVE** (appendix footer, Summary) |
| 11 | Results: taxonomic summary | Group / sub-group / taxa / with status / % (incl. "all saproxylic beetles") | EMG2 Table 2; backlog E8b | **NEW** (E8b, small) |
| 12 | Results: key species | Table with status *and source*; Rare Key first; accounts with site evidence | Telfer; `38` §5–6 | **HAVE** |
| 13 | Results: Pantheon habitats | Biotope > habitat > spp / % national pool / SQI / key spp named | EMG2 Table 4; New Forest Table 13 | **HAVE** (key spp named per habitat: check; E8) |
| 14 | Results: assemblages | SAT, count, threshold, PtT, condition **with confidence level** | Pantheon "reported condition"; H2 Table 8 | **PART**: confidence (high / medium / low by ISIS compliance) **NEW** |
| 15 | Results: compartments | Metrics × compartment (+Combined); SAT × compartment matrix, colour-coded | H2 Tables 7–8; Bicester 2025; NERR005 3.24 | **NEW** (E6) |
| 16 | Results: saproxylic | SQI (scoring spp), IEC by grade, species table with SQI/IEC scores, national/county rank, site comparison | EMG2 Table 5; Petworth Tables 7–8 | **NEW** (E7) |
| 17 | Results: phenology / visit matrix | Species × visit date; when target species were found | Barton Common; New Forest | **NEW**, cheap from own data |
| 18 | Evaluation | Value at a stated geographic scale; species, assemblage and taxonomic criteria; SSSI / LWS guideline comparison | EcIA 4.7–4.21; `38` §7 | **PROSE**, plus the "percentages not verdict" figures (**HAVE**); E16 verdict wording undecided |
| 19 | Impacts, mitigation, enhancement | Habitat features to retain or create, keyed to the SATs present | EcIA B10–B13 | **PROSE**; SAT-driven prompts possible later |
| 20 | Scoping-out | Taxon / species / reason (research-only, non-England, not analysable, casual / out-of-scope) | `38` §4, §9 | **PART**: greyed in the workbook; no explicit table (**NEW**, small) |
| 21 | Data sharing statement | Where records went (iRecord / LERC / scheme), when, embargo, sensitive species withheld | BS 42020 6.4.7; CIEEM data guidance 8.1, 7.2; EcIA 1.14 | **PART**: Observatum has an iRecord export and an embargo concept; no report sentence or sensitive-species flag |
| 22 | Data validity | Survey dates vs assessment date; CIEEM lifespan band | CIEEM 2019 note; BS 42020 6.2.1 | **HAVE** in part (two dates, "two-year" note); bands **NEW** (trivial) |
| 23 | References | Status reviews cited per designation; Pantheon / UKSI / JNCC attribution | CIEEM RW A11; licence conditions | **PART**: attribution and per-status `source` exist; generated reference list **NEW** |
| 24 | Appendices | Species list (taxonomic order; site / compartment columns; computed footer); status definitions; photos with date, coordinates, bearing | `38` §4–5, §8 | **HAVE** (list, definitions); compartment columns **NEW** (E6); photo annex **NEW** (Observatum holds the metadata) |

**The pattern:** Examen already covers the evaluation core, rows 8, 10, 12, 13 and
much of 24. The gaps are:

- the **methods and effort** layer (rows 6, 7, 9, 17), which mostly needs data you
  already hold;
- **structure** (rows 11, 15, 16, 20);
- **document furniture** (rows 1, 3, 5, 21, 23).

## B3. Winter decisions

**Scope of the generated report**

1. **What is the Word export: an appendix or the report?** If it is the analytical
   appendix, as now, rows 1–5 and 18–19 stay manual. If it is a draft report, it needs a
   template with the document-control block and placeholders for prose.
2. **E16, the SQI verdict wording.** Recommendation: drop the unsourced bands. Print
   Telfer's ~10% / >1% test and Kirby-Lambert's 5–10% / >10% as cited conventions, and add
   Pantheon's own "benchmarks… not yet produced" caveat.
3. **A geographic value statement:** either never generated (author's judgement, as BS 42020
   4.4 implies), or offered as a prompt with the evidence beside it. Recommendation: a
   prompt only.

**Methods and effort, which is where the standards press hardest**

4. **Survey effort table (row 6).** Decide the columns: date, start and end time, weather,
   surveyor, compartment, method, trap-days or sample count.
   - Check what Data Entry captures today. Weather and times are probably missing.
   - Decide whether to add a per-visit record (a "visit" table: date, times, weather,
     personnel), which Observatum doesn't hold yet.
5. **Limitations (row 9).** Decide whether Examen auto-drafts a factual list:
   - months covered against the April–October benchmark;
   - number of visits;
   - groups not identified;
   - species Pantheon could not analyse;
   - low-sample SQIs;
   - the data-age band.
6. **Reported condition confidence (row 14).** Decide how a survey declares its ISIS
   compliance (a project-level field: compliant, semi or none), so the condition column
   can carry high, medium or low.

**Structure**

7. **Order of build:** E6 compartments, then E8b taxonomic summary, then a scoping-out
   table, then E7 saproxylic (largest).
8. **Compartment model:** is `sub_location` alone enough, or do compartments need their
   own table with area, habitat and grid reference for the SAT matrix and the maps? Is the
   "Combined" column always shown?
9. **Phenology / visit matrix (row 17):** in the workbook only, or in Word as well?
   Recommendation: workbook plus an appendix option.

**Data and disclosure**

10. **Data-sharing sentence:** a standard paragraph generated from the project's iRecord
    status and embargo date. Also add a client opt-out clause to your terms and conditions
    (CIEEM data guidance 8.1).
11. **Sensitive species:** add a Codex flag for species whose locations should be blurred
    or withheld in public reports, with grid references reduced in the appendix.
12. **Desk study import (row 5):** worth building, reusing the contributed-records
    importer for LERC returns, or leave it manual?

**Presentation**

13. **Taxonomic order for appendices:** once `shared/checklists/` exists, decide whether
    Examen uses it too (recommendation: yes; one ordering rule across the suite).
14. **Validity statement:** quote the CIEEM 2019 bands rather than "two years".
15. **NERR005 Table 17:** read it from your copy (p. 86) and reconcile it with this
    checklist before settling the template.

---

# C. Sources

**Part A: checklists**

- ColSoc recording spreadsheet: https://www.colsoc.org/recording-spreadsheet
  (xlsx: https://www.colsoc.org/_files/ugd/78aa6f_0de566f8cd8b447792e451099f6be0c3.xlsx?dn=ColSoc-Spreadsheet.xlsx ;
  xls: https://www.colsoc.org/_files/ugd/78aa6f_28706b8d47d34d8493796b12b0354953.xls?dn=ColSoc-Spreadsheet.xls)
- ColSoc, how to record: https://www.colsoc.org/how-to-record
- ColSoc checklist page: https://colsoc.org/checklist
- ColSoc documents: https://www.colsoc.org/downloads (empty)
- Duff 2018, publisher: https://www.pemberleybooks.com/product/checklist-of-beetles-of-the-british-isles/34365/
- Beetles of Britain & Ireland, checklist: https://coleoptera.org.uk/node/8
- Beetles of Britain & Ireland, 2018 news: https://coleoptera.org.uk/node/22102
- Beetles of Britain & Ireland, Carabidae: https://coleoptera.org.uk/family/Carabidae
- Duff 2008 PDF: https://www.zin.ru/ANIMALIA/COLEOPTERA/pdf/checklist2008_a5.pdf
- UK Beetles classification and spreadsheet: https://www.ukbeetles.co.uk/classification
- Wikipedia, Carabidae: https://en.wikipedia.org/wiki/List_of_ground_beetle_(Carabidae)_species_recorded_in_Britain
- Wikipedia, Staphylinidae: https://en.wikipedia.org/wiki/List_of_rove_beetle_(Staphylinidae)_species_recorded_in_Britain
- Wikipedia, beetles of Great Britain: https://en.wikipedia.org/wiki/List_of_beetle_species_of_Great_Britain
- NBN forum, UKSI weighting: https://forums.nbn.org.uk/viewtopic.php?id=4871
- Indicia, UKSI import: https://indicia-docs.readthedocs.io/en/stable/administrating/warehouse/importing-uksi.html
- Agassiz et al., NHM data: https://data.nhm.ac.uk/dataset/checklist-of-the-lepidoptera-of-the-british-isles-data
  (2022 xlsx resource: https://data.nhm.ac.uk/dataset/checklist-of-the-lepidoptera-of-the-british-isles-data/resource/1ffc1315-0046-465d-9b88-0319c76c3806)
- Dipterists Forum checklist: https://dipterists.org.uk/node/23
  (PDF: https://dipterists.org.uk/sites/default/files/pdf/BRITISH%20ISLES%20CHECKLIST%202025_11.pdf)
- Broad 2014, Hymenoptera: https://bdj.pensoft.net/article_preview.php?id=1113
- BWARS information sheets: https://bwars.com/information_sheets
- BWARS checklist page: https://bwars.com/content/checklist-british-and-irish-aculeate-hymenoptera-0
- BWARS CSV: https://bwars.com/sites/default/files/diary_downloads/20221110%20species%20list.csv
- British Bugs, systematic lists: https://britishbugs.org.uk/systematic.html
- British Bugs, Heteroptera list: https://britishbugs.org.uk/systematic_het.html
- British Bugs, Pentatomoidea gallery: https://britishbugs.org.uk/gallery/heteroptera/Pentatomoidea/pentatomoidea.html
- British Bugs, recording: https://britishbugs.org.uk/recording.html

**Part B: report standards**

- CIEEM Report Writing 2017: https://cieem.net/wp-content/uploads/2019/02/Ecological-Report-Writing-Dec2017.pdf
- CIEEM EcIA v1.3, resource page: https://cieem.net/resource/guidelines-for-ecological-impact-assessment-ecia/
  (PDF: https://cieem.net/wp-content/uploads/2018/08/EcIA-Guidelines-v1.3-Sept-2024.pdf)
- CIEEM EcIA Checklist: https://cieem.net/wp-content/uploads/2019/11/EcIA-Checklist.pdf
- CIEEM lifespan note, resource page: https://cieem.net/resource/advice-note-on-the-lifespan-of-ecological-reports-and-surveys/
  (text: https://www.milton-keynes.gov.uk/sites/default/files/2022-03/M.26%20CIEEM%20Advice%20Note%20On%20the%20lifespan%20of%20ecological%20reports%20and%20surveys%20April%202019.pdf)
- CIEEM data guidance 2023: https://cieem.net/wp-content/uploads/2016/03/Accessing-and-Using-Biodiversity-Data-Guidance-in-the-UK-2023.pdf
- BS 42020 extract: https://www.milton-keynes.gov.uk/sites/default/files/2022-03/M.25%20BS-42020.pdf
  (standard: https://knowledge.bsigroup.com/products/biodiversity-code-of-practice-for-planning-and-development)
- NERR005: https://publications.naturalengland.org.uk/publication/36002
  (PDF: https://publications.naturalengland.org.uk/file/63016 ; RIN005: https://publications.naturalengland.org.uk/file/62026 ;
  CIEEM listing: https://cieem.net/resource/surveying-terrestrial-and-freshwater-invertebrates-for-conservation-evaluation/)
- Pantheon, how to use: https://pantheon.brc.ac.uk/node/440
- Pantheon, scoring systems: https://pantheon.brc.ac.uk/node/425
- Pantheon, reported condition: https://pantheon.brc.ac.uk/node/418
- WSP / Cory IHP report: https://nsip-documents.planninginspectorate.gov.uk/published-documents/EN010128-000890-Cory%20Environmental%20Holdings%20Limited%20(CEHL)%20-%206.3%20Environmental%20Statement%20-%20Appendix%207-8%20Terrestrial%20Invertebrates%20Survey%20Report.pdf
- Saproxylic thresholds and khepri: see `38_Report_Survey.md` §3 and `39_Research_Notes.md` §4

**Not read:**

- NERR005 chapters 4–8 (PDF text truncated).
- The ColSoc and ukbeetles spreadsheets and the NHM ABH xlsx (binary; no preview; API
  blocked by the proxy).
- Zenodo record 903354 (rate-limited, HTTP 429).
- BS 42020 full text (paywalled; the council extract was used).

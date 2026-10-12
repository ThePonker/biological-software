# Test files for the import wizards (tests 30, 31, 34, 35)

Four small made-up files. Every row has the site **TEST SITE – do not keep** and the
comment/notes **TEST – delete**, so they are easy to find if one gets in by mistake.
Open them straight from this folder; no editing needed.

| File | Wizard |
|---|---|
| `TEST_observation_import.csv` | Observation Data › + Import Data (Personal Upload) |
| `TEST_observation_vague_dates.csv` | Observation Data › + Import Data (Personal Upload) |
| `TEST_scheme_import.csv` | Recording Scheme › Import (Generic CSV) |
| `TEST_specimen_import.csv` | Insect Collection › Import |

Only test 35 needs a real import, and it can be deleted afterwards (steps below).
Everything else: **press Cancel before the Import button.**

Row numbers (all three wizards, since 12 Oct): the row of the file as a spreadsheet shows
it -- the heading line is row 1, so the first record is Row 2. Hover over the **Row** column
heading to see this said.

---

## Test 30 – Close spellings (all three wizards)

**Observation import**
1. Observation Data › **+ Import Data**. Pick **Personal Upload** › Next.
2. Browse to `TEST_observation_import.csv` › Next. The columns map themselves › Next.
3. A box asks "Unmatched Species Found … 2 unique species". Click **No** for now.
4. You should see:

   | Row | Species | Status | Message |
   |---|---|---|---|
   | 2 | Rutpela maculata | ✓ | |
   | 3 | Rhagium mordax | ✓ | |
   | 4 | Rutpela maculata | ⚠ | Close spelling: 'Rutpela maculta' matched to 'Rutpela maculata' |
   | 5 | Rhagium mordax | ⚠ | Close spelling: 'Rhagium mordx' matched to 'Rhagium mordax' |
   | 6 | Rutpla maculata | ✗ | Species not found in UKSI: Rutpla maculata — closest: Rutpela maculata, Russula maculata — confirm with Resolve Species |
   | 7 | Ab | ✗ | Species not found in UKSI: Ab — closest: Abia aenea, Abies alba, Abia nitens (+2 more) — confirm with Resolve Species |
   | 8 | Rutpela maculata | ✗ | Count of 0 — fix the count (test 34) |

5. Carry on to test 31 in the same window, or press **Cancel**.

**Scheme import**
1. Recording Scheme › **Import**. Pick **Generic CSV** › Next.
2. Browse to `TEST_scheme_import.csv` › Next. The columns map themselves › Next.
3. You should see (no question box here; a **Resolve Species...** button appears):

   | Row | Species | Status | Message |
   |---|---|---|---|
   | 2 | Rutpela maculata | ✓ | |
   | 3 | Rhagium mordax | ✓ | |
   | 4 | Rutpela maculata | ⚠ | Close spelling: 'Rutpela maculta' matched to 'Rutpela maculata' \| Imported as 'Rutpela maculta' (close spelling of 'Rutpela maculata') |
   | 5 | Rhagium mordax | ⚠ | Close spelling: 'Rhagium mordx' matched to 'Rhagium mordax' \| Imported as 'Rhagium mordx' (close spelling of 'Rhagium mordax') |
   | 6 | Rutpla maculata | ✗ | Species not found in UKSI: Rutpla maculata — closest: Rutpela maculata, Russula maculata — confirm with Resolve Species |
   | 7 | Ab | ✗ | Species not found in UKSI: Ab — closest: … — confirm with Resolve Species; Not a species-level record: Ab |
   | 8 | Rutpela maculata | ✓ | (count 0 – test 34) |

4. Carry on to test 31, or press **Cancel**.

**Specimen import**
1. Insect Collection › **Import**. Browse to `TEST_specimen_import.csv` › Next.
2. The columns map themselves › Next.
3. A box asks "Unmatched Species Found … 2". Click **No** for now.
4. Rows 2–3 ✓, rows 4–5 ⚠ "Close spelling: …" (as above), rows 6 (Rutpla maculata)
   and 7 (Ab) ✗ "Species not found in UKSI: … confirm with Resolve Species".
5. Carry on to test 31, or press **Cancel**.

## Test 31 – Species picked by hand

There are two ways to pick, and since 12 Oct both say the same, in all three wizards:

* **The pick list** (the "Resolve Unmatched Species" window, from **Resolve Species...** or
  from **Yes** on the question box): the message reads
  **File had 'Rutpla maculata'; picked by you as Rutpela maculata**.
* **Double-click the Species cell** (any of the three wizards): the message reads
  **File had 'Ab'; picked by you as Abax parallelepipedus**.

The import note kept with the record says the same: "Imported as 'Ab'; picked by you as
'Abax parallelepipedus'".

Steps (any of the three wizards, carrying on from test 30):
1. Click **Resolve Species...** (or Yes on the box).
2. On the left click **Rutpla maculata**. The search fills in and shows
   "Rutpela maculata (Cerambycidae) — close spelling". Click it › **Apply Match →**.
3. Click **Ab**. Type `Abax parallelepipedus` in the search, click the result › **Apply Match →**.
4. **Continue with Resolved Species**.
5. Both rows turn ⚠ with "File had '…'; picked by you as …".
6. To try the double-click, cancel and start again, then **double-click the Species cell**
   of the Rutpla or Ab row, choose the species in the search window › **Select Species**.
   The row turns ⚠ "File had 'Ab'; picked by you as Abax parallelepipedus" (the
   observation wizard too, since 12 Oct; it used to change the name and keep no note).
7. The specimen table shows ✓, ⚠ and ✗ in the Status column.
8. Press **Cancel**. Nothing is imported.

## Test 34 – Counts of 0

* **Observation import** (`TEST_observation_import.csv`): row 8 (count 0) is ✗
  "Count of 0 — fix the count" and is left out of the import. Press **Cancel**.
* **Scheme import** (`TEST_scheme_import.csv`): row 8 (count 0) is ✓ and would be stored
  with quantity 0. Press **Cancel**: scheme records cannot be deleted in the app, so
  please don't import this file. Storage was checked on a copy of the database instead:
  the row was saved with quantity 0 (and in the observation import the 0 row was not saved).

## Test 35 – Vague dates in an observation import (real import, then delete)

Uses *Geotrupes stercorarius*, which had no records in your database on 10 Oct.

1. Observation Data › **+ Import Data** › **Personal Upload** › Next.
2. Browse to `TEST_observation_vague_dates.csv` › Next › Next.
3. You should see:

   | Row | Date in file | Status | Message |
   |---|---|---|---|
   | 2 | 15/07/2024 | ✓ | |
   | 3 | 2021 | ⚠ | vague date: year only |
   | 4 | June 2021 | ⚠ | vague date: month only |
   | 5 | 01/06/2021 - 15/06/2021 | ⚠ | vague date: date range |

4. Next › **Import 4 Records** › finish.
5. Check: Observation Data › **Show Filters** › Location: type `TEST SITE` › Enter.
   Only the 4 test records are listed. **Columns** › tick **Date Type**. You should see
   2024-07-15 D, 2021-01-01 Y, 2021-06-01 O, 2021-06-01 DD.
6. Stats › **Species Lookup** › search *Geotrupes stercorarius*. The Phenology chart shows
   **one record, in July**. Nothing in June or January.
7. **Remove the test records:** back on Observation Data, with the Location filter still
   `TEST SITE` and only the 4 test records listed: **Select All** › **Delete Selected** ›
   Yes. (A backup is taken first.) Then **Clear Filters**, and untick Date Type in Columns
   if you don't want it.

Checked on a copy of the database (12 Oct): the four rows were stored as D / Y / O / DD and
the phenology chart gave July = 1, all other months 0.

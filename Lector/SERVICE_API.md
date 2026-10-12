# Lector service API (stage A, 12 Oct 2026)

`Lector/service.py` is the only module the desktop UI should import. It has no Qt.
Everything below is a method of `LectorService`.

```python
from Lector.service import LectorService, LectorError, NeedsUpdate, REVIEW_STATUSES, REVIEW_TAGS
svc = LectorService()          # data/lector.db, data/uksi.db, the real BHL client
```

Constructor (all optional): `db_path`, `uksi_db`, `client_factory` (a function returning a
BHL client; tests pass a fake), `export_dir` (default `data/lector_exports`),
`synonym_file` (default `data/lector_synonyms.txt`), `backup_dir` (default `data/_backups`).

## Rules for the UI

- **Threads.** Every method opens and closes its own SQLite connection, so any method can be
  called from a worker thread. Methods marked **NETWORK** can take minutes (BHL allows one
  request per second): call them in a `QThread`/worker. Run one NETWORK task at a time
  (they share one throttled client).
- **Progress.** NETWORK methods take `progress(stage, done, total, message)`: `stage` is
  `"search"` (names), `"text"` (page downloads) or `"count"`; `done`/`total` are ints for a
  progress bar; `message` is plain English. It is called from the worker thread: emit a Qt
  signal from it, don't touch widgets.
- **Cancel.** Pass `cancel=threading.Event()` (or any function returning True). It is checked
  before every request; the run stops within a second, is saved with status `cancelled`, and
  whatever was downloaded is kept. Running again carries on.
- **Errors.** `LectorError` carries a message to show as it is (no API key, not in UKSI, no
  names ticked, ...). `NeedsUpdate` (a `LectorError`) means lector.db was made by an older
  Lector: show `needs_update()`'s report, ask, then call `update_database()`.
- Dates/times are ISO strings (`2026-10-12T10:41:48`). Ids are ints.

## Settings and database

| Method | Returns |
|---|---|
| `settings_info()` | `{api_key_set, api_key_source, api_key_url, db_path, db_exists, db_needs_update, uksi_db_path, uksi_found, export_dir, synonym_file, docx_available, xlsx_available, pdf_method ('word'/'libreoffice'/None), request_interval}` |
| `needs_update()` | `None`, or a dry-run report `{before: {table: n}, after: {table: n}, searches_made: [{search_id, name, names, pages}], backup: None, applied: False}`. Changes nothing. |
| `update_database()` | Backs lector.db up with `conn.backup()` to `data/_backups/lector_pre_v2_<time>.db`, then updates in place. Same report with `backup` path and `applied: True`. |

## Taxa and names (UKSI, read-only, no network)

| Method | Returns |
|---|---|
| `resolve_taxon(text)` | `{found, typed, tvk, name, rank, family, genus, matched_as ('accepted'/'synonym'/'tvk'/None), alternatives: [{tvk, name, rank, family}]}`. An old name resolves to its current species (`matched_as='synonym'`). |
| `candidate_names(tvk, name=None)` | `[{name, origin ('accepted'/'uksi_synonym'/'user_added'), included, held_back_reason, conflict_name, conflict_tvk, source}]`, accepted name first. Held-back names have `included=False` and a reason such as *"Held back: epithet is current in Monochamus sutor (NHMSYS0020704741)"*. |
| `remember_name_choice(name, include, species=None, reason="")` | Appends `+ name @ species | reason` (or `-`) to `data/lector_synonyms.txt`; returns the line. `species=None` = every species. Use for "Remember my choices for these names in every search". |

```python
t = svc.resolve_taxon("lamia textor")      # {'found': True, 'tvk': 'NBNSYS0000011050', 'family': 'Cerambycidae', ...}
for c in svc.candidate_names(t["tvk"]):
    print(c["name"], c["included"], c["held_back_reason"])
```

## Saved searches

A search has: `search_id, name, target_tvk, target_name, kind ('species'/'family'/'list'),
status ('draft'/'active'), created, updated, notes`, plus

- `names`: `[{name, origin, included, held_back_reason, accepted_name, accepted_tvk, position}]`
- `filters`: `{from_year, to_year, journal_preset, include_words: [str], exclude_words: [str],
  max_pages (per name; 0/None = no cap), skip_index, skip_duplicates, recorded}`.
  Title words match whole words, English plurals allowed. `recorded=False` only on searches
  made from fetches before 12 Oct, whose filters were never stored: such a search can be
  counted but not fetched until its filters are set (any `update_search(filters=...)`).

| Method | Returns |
|---|---|
| `list_searches()` | `[search fields + {names_total, names_included, names_held_back: [str], journal_preset, years ('All years'/'1800-1950'/'Before 1950'/'From 1800'), filters_recorded, pages_held, pages_with_text, reviewed, records_extracted, runs, last_run: {run_id, started, finished, mode, status, found, kept, requests, failed} or None, found_last}]` |
| `dashboard()` | `{searches, pages_harvested, awaiting_review, records_extracted, activity: [{when, kind ('run'/'export'), text}], attention: [str]}` |
| `get_search(search_id)` | the search dict with `names` and `filters` |
| `create_search(target, name=None, kind='species', names=None, filters=None, status='draft', with_synonyms=True)` | new `search_id`. `target` = name, TVK or a `resolve_taxon()` result. Species: names default to `candidate_names()` (held-back ones stored unticked). Family: every UKSI species of the family (`target='Cerambycidae'`). List: `names=[...]` names/TVKs, each resolved. |
| `update_search(search_id, name=None, status=None, notes=None, filters=None, names=None)` | the updated search. `filters` = dict of keys to change; `names` = the full list (strings or dicts as above). |
| `duplicate_search(search_id, new_name=None)` | new `search_id` (a draft copy) |
| `default_filters()` | the filters a new search starts with (a copy) |
| `family_names(family)` | the names a family search uses: every UKSI species, accepted names, ticked |
| `journal_presets()` | `[{name, description, include_words, exclude_words, builtin}]` - "British periodicals", "Scottish titles", plus your own |
| `save_preset(name, include_words, exclude_words, description=None)` | - |

Choosing a preset in the UI: copy its words into the search's `include_words`/`exclude_words`
and set `journal_preset` to its name (later edits to a preset never change earlier runs).

```python
sid = svc.create_search("Lamia textor", name="Lamia textor - British literature",
                        filters={"include_words": ["Entomologist", "Naturalist", "Annals"],
                                 "exclude_words": ["Canadian"], "max_pages": 500})
svc.update_search(sid, filters={"to_year": 1950})
```

## Counting, preview and running (NETWORK)

| Method | Returns |
|---|---|
| `name_counts(names, refresh=False, progress=None, cancel=None)` | `{name: {found, source ('BHL'/'cache'), error}}` - pages BHL indexes for each name, before filters (one request per name not yet asked). |
| `preview(search_id, use_network=False, refresh=False, progress=None, cancel=None)` | `{found, within_filters, already_held, to_download, requests, est_seconds, requests_without_refresh, not_counted: [names], names, name_found}`. Without `use_network` it uses BHL's last answers only; names never asked are listed in `not_counted` (show "Refresh count"). |
| `preview_draft(names, filters=None, use_network=False, refresh=False, progress=None, cancel=None, count_all=True)` | as `preview()`, for names and filters not saved yet (the search builder): `names` = strings or `{name, included}`, `filters` = any filter keys (the rest default). Adds `name_found: {name: pages or None}` for every name, ticked or not (`count_all`), so a held-back name can be judged; only ticked names make the totals. NETWORK only with `use_network`. |
| `run_search(search_id, mode='fetch', refresh=True, progress=None, cancel=None)` | `{run_id, search_id, mode, status ('done'/'cancelled'/'failed'), message, found, kept, new, unchanged, withdrawn, text_fetched, failed, requests, names: [{name, found, kept, capped, source} or {name, error}]}` |

`mode='count'` asks BHL and records a count-only run; no pages are stored. `mode='fetch'`
stores the pages within the filters and downloads their text. A run **always applies the
search's current filters**: pages that no longer pass become *withdrawn* (kept in the
database with their notes, shown with `include_withdrawn=True`). `refresh=True` (default)
asks BHL again for every name, so newly scanned pages appear; `refresh=False` re-uses BHL's
last answer per name and costs no name requests (good after changing filters).

```python
stop = threading.Event()
def progress(stage, done, total, msg): worker.progress.emit(stage, done, total, msg)
result = svc.run_search(sid, progress=progress, cancel=stop)   # in the worker thread
# Cancel button: stop.set()
```

## History

| Method | Returns |
|---|---|
| `list_runs(search_id)` | newest first: `[{run_id, search_id, started, finished, mode, settings: {names, held_back, filters, refresh}, found, kept, requests, failed, status ('done'/'cancelled'/'failed'/'migrated'), message, new, unchanged, withdrawn}]` |
| `run_diff(search_id, run_a=None, run_b=None)` | default: the last two fetch runs; `None` if fewer than two. `{run_a, run_b, new: [page], withdrawn: [page + reason ('Now filtered out'/'No longer found on BHL')], unchanged: [page], settings_changed: [str]}`; page = `{page_id, citation, bhl_url, year, title, matched_names}` |
| `keep_page(search_id, page_id)` | keeps a withdrawn page in the search ("Keep anyway") |

## Review

Review state belongs to the page and the species (so it shows in every search of that
species). `REVIEW_STATUSES = ('unreviewed', 'relevant', 'not_relevant', 'record_extracted')`.
`REVIEW_TAGS = ('record', 'biology', 'mention', 'index')` - the mock-up's "What is this page?"
buttons (Not relevant is the status `not_relevant`).

| Method | Returns |
|---|---|
| `review_queue(search_id, status=None, order='year'/'journal', include_withdrawn=False)` | one item per page, other scans of the same text grouped inside it: `{page_id, citation, source, year, title, volume, page_label, authors, article_title, page_type, section ('main'/'index'/'no_match'), section_label, likely_index, index_reason, excerpts: [[line]], excerpt_runs: [[(text, bold)]], duplicate_group, copies: [{page_id, citation, bhl_url, year, title}], bhl_url, matched_names, review_status, review_tag, notes, state ('current'/'kept'/'withdrawn'), has_text, copyright_note, new_in_last_run}` |
| `page_detail(search_id, page_id)` | the page row (incl. full `ocr_text`) + `{citation, source, section, excerpts, text_runs: [(text, bold)], copyright_note}` |
| `set_review(search_id, page_id, status=None, tag=None, notes=None)` | `None` leaves a field unchanged; `tag=''` clears it |

`excerpt_runs` / `text_runs` are ready for a QTextEdit: bold the runs whose flag is True
(the searched names, found in any case, with accents, across line breaks and hyphenation).

## Export

| Method | Returns |
|---|---|
| `export(search_id, formats=('docx','xlsx'), order='year'/'journal', include_appendices=True, include_statuses=('unreviewed','relevant','record_extracted'), include_notes=True, out_dir=None)` | `{files: {'txt','csv','docx','xlsx','pdf': path}, messages: [str], counts: {pages, entries, duplicates_merged, index_pages, name_not_in_text}, date}` |
| `list_exports(search_id=None)` | `[{export_id, search_id, created, kind, path, pages}]` |

`formats` may hold `'txt'` (text bundle + index CSV), `'docx'` (Word dossier: summary, entries
with BHL links, authors and article titles where BHL gives them, "Same text also at", your
notes, appendices), `'xlsx'` (Excel index, made with the dossier), `'pdf'` (a PDF copy of the
dossier through Word + docx2pdf or LibreOffice). Missing packages never raise: `files` lacks
that format and `messages` says what to install.

```python
out = svc.export(sid, formats=("docx", "xlsx", "pdf"), order="journal")
for m in out["messages"]: print(m)            # e.g. 'PDF made with Microsoft Word.'
os.startfile(out["files"]["docx"])
```

## Added for the desktop window (stage B, 12 Oct 2026)

`preview_draft()`, `default_filters()`, `family_names()` and the `name_found` key of a
preview (Lector/previewing.py holds the preview for both `preview` and `preview_draft`,
so the builder and a saved search always agree). The window itself is `Lector/ui`
(`python -m Lector gui`); it calls nothing but the methods above.

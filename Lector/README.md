# Lector — BHL harvester

Finds every Biodiversity Heritage Library page on which a species name (and,
optionally, its UKSI synonyms) appears, downloads the page text with full
citation details, and stores it in `data/lector.db`.

## One-off setup

1. Get a free API key: https://www.biodiversitylibrary.org/getapikey.aspx
2. Save it (key only, one line) to `data\bhl_api_key.txt`.
   Alternatives: `BHL_API_KEY` environment variable, or `--key` on the command line.

Searching and the text export need no extra packages. The Word dossier needs
`python-docx`, and its Excel index needs `openpyxl`:

    pip install python-docx openpyxl

A PDF copy of the dossier (`--pdf`) uses Microsoft Word through `docx2pdf`
(`pip install docx2pdf`), or LibreOffice if installed. Without either, Lector
says so and the Word file is still written.

### Updating lector.db (12 Oct 2026)

Lector now keeps saved searches, runs and review notes (see `SERVICE_API.md`).
The first time the new version opens an older `lector.db` it shows what the
update would do and asks you to type YES; it backs the file up to
`data\_backups\lector_pre_v2_<time>.db` first. Nothing stored is changed or
removed. Or run `py -3.14 scripts\migrate_lector_v2.py` (dry run) and then
`--apply`. Each species already fetched becomes a saved search with one run.

Lector can sit anywhere (e.g. the desktop) - it finds the suite's `paths.py` by
itself. If it can't, put the full path of the `Biological Software` folder on
one line in `Lector\biosoft_root.txt`. Keep `run_lector.bat` next to the
`Lector` folder; when you move Lector into the suite root, move the .bat too.

## Commands

From the folder containing `Lector` (or replace `python -m Lector` with `run_lector.bat`):

| Command | What it does |
|---|---|
| `python -m Lector gui` | The Lector window: saved searches, new search with name checks and a preview, runs and what changed, reading list, exports. `launchers\run_lector_gui.bat` or Atrium's Lector tile. |
| `python -m Lector probe "Lamia textor"` | Raw BHL response for one name → `data\lector_exports\probe_*.json`. Run this first to confirm parsing. |
| `python -m Lector fetch species.txt --count-only` | Hit counts per name; downloads no pages. Use before big runs. |
| `python -m Lector fetch species.txt --synonyms` | Search names (+ UKSI synonyms), store pages, fetch text. |
| `python -m Lector status` | Pages and fetched text per species, year range. |
| `python -m Lector export --all` | One readable `.txt` per species (citation header per page) + index CSV. |
| `python -m Lector export --name "Lamia textor" --docx` | Word dossier + Excel index (see below). Add `--by-journal` to order by journal. |
| `python -m Lector export --name "Lamia textor" --pdf` | As `--docx`, plus a PDF copy (Word + docx2pdf, or LibreOffice). |
| `python -m Lector synonyms "Lamia textor"` | Which older names a `--synonyms` search would use, and which are held back and why. `--add NAME` / `--exclude NAME` change your list. |
| `python -m Lector forget --name "Lamia textor"` | Remove a species' page links and BHL answers so it is searched afresh. Page text is kept. Refuses if pages have review notes unless you add `--yes`. Rarely needed now (see `fetch`). |

## Input

- `.txt`: one scientific name or TVK per line; `#` lines ignored.
- `.csv`: a `tvk` column and/or a name column (`species`, `scientific_name`, `name`, `taxon`).

## fetch options

| Option | Effect |
|---|---|
| `--synonyms` | Also search UKSI synonyms of each species |
| `--from-year` / `--to-year` | Keep pages within a year range |
| `--max-pages N` | Cap per searched name (default 500; 0 = no cap). Earliest pages kept first |
| `--include-title WORD ...` | Keep only titles containing these whole words (e.g. `Entomologist Scottish`). English plurals count: `Naturalist` matches "Naturalists' Society" but not "naturalistes" |
| `--exclude-title WORD ...` | Drop titles containing these whole words (e.g. `catalogue index`) |
| `--skip-index` | Leave out pages BHL types as index or contents |
| `--count-only` | Report counts only |
| `--refresh` | Ask BHL again for names already searched (finds pages scanned since) |

Each species you fetch is a saved search named after it; the command's names
and filters become its settings. Every run applies the **current** filters:
BHL's answer for each name is kept, so changing a filter and fetching again
costs no name requests, and pages that no longer pass are marked withdrawn
(kept in the database with any notes, not deleted). Pages whose text failed to
download are retried on the next run. Ctrl+C is safe.

## Synonyms

UKSI gives some names as synonyms of the wrong species (e.g. *Lamia sartor* and
*L. sutor*, which are *Monochamus*; fault F25). With `--synonyms`, each synonym
is checked first and held back, with the reason shown, when its epithet is
current for another species of the same family, when UKSI also gives it for
another taxon, or when it is on an exclusion list: the suite's
`scripts\uksi_synonym_corrections.csv` or your own `data\lector_synonyms.txt`:

    - Lamia sartor                      never search this name
    - Lamia sutor @ Lamia textor        ...only for Lamia textor
    + Cerambyx textor @ Lamia textor    also search this name (also confirms a held-back one)

Text after `|` on a line is your reason. `python -m Lector synonyms` shows the
result and can add lines for you.

## Word dossier

`export --docx` writes `<species>_dossier.docx` and `<species>_dossier_index.xlsx`
to `data\lector_exports`:

- Front page: TVK, names searched, counts, and a reminder that excerpts are raw OCR.
- Summary table in date order (or by journal). Entry numbers link to the entries.
- One entry per page: up to three 5-line excerpts with the name in bold (found
  in any case, with or without accents, split over lines or hyphenated), a BHL
  link, authors and article title where BHL gives them, and any other scans of
  the same text merged in as "Same text also at" (same printed page, or the
  same text under another title; never two pages of one scanned volume).
- Pages from 1930 on carry a reminder to check BHL's rights statement.
- Appendix A: index and contents pages (BHL page type, or a layout test for
  pages BHL has not typed). Appendix B: pages where the name is not in the OCR
  text (plates, captions, misreadings).
- Pages marked `not_relevant` in `page_hits.review_status` are left out.

Page types, authors and article titles are stored from 12 Oct on. For pages
fetched earlier, `fetch` the species again with `--refresh` to fill them in.

## Notes

- Requests are throttled to one per second; text fetch is one request per page.
- BHL's name index both misses some mentions (OCR errors, abbreviated genera)
  and includes some false ones (homonyms). Treat output as a reading list.
- OCR text is unverified — check against the page image before using a record.
- Review state per page and species: `page_hits.review_status` (unreviewed /
  relevant / not_relevant / record_extracted), `review_tag` and `notes`.
- The desktop UI (to come) uses only `Lector/service.py`; see `SERVICE_API.md`.
- `data/` is git-ignored, so the key, database and exports stay out of the repo.

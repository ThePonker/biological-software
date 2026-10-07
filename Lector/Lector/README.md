# Lector — BHL harvester

Finds every Biodiversity Heritage Library page on which a species name (and,
optionally, its UKSI synonyms) appears, downloads the page text with full
citation details, and stores it in `data/lector.db`.

## One-off setup

1. Get a free API key: https://www.biodiversitylibrary.org/getapikey.aspx
2. Save it (key only, one line) to `data\bhl_api_key.txt`.
   Alternatives: `BHL_API_KEY` environment variable, or `--key` on the command line.

No extra packages needed (standard library only).

Lector can sit anywhere (e.g. the desktop) - it finds the suite's `paths.py` by
itself. If it can't, put the full path of the `Biological Software` folder on
one line in `Lector\biosoft_root.txt`. Keep `run_lector.bat` next to the
`Lector` folder; when you move Lector into the suite root, move the .bat too.

## Commands

From the folder containing `Lector` (or replace `python -m Lector` with `run_lector.bat`):

| Command | What it does |
|---|---|
| `python -m Lector probe "Lamia textor"` | Raw BHL response for one name → `data\lector_exports\probe_*.json`. Run this first to confirm parsing. |
| `python -m Lector fetch species.txt --count-only` | Hit counts per name; stores nothing. Use before big runs. |
| `python -m Lector fetch species.txt --synonyms` | Search names (+ UKSI synonyms), store pages, fetch text. |
| `python -m Lector status` | Pages and fetched text per species, year range. |
| `python -m Lector export --all` | One readable `.txt` per species (citation header per page) + index CSV. |

## Input

- `.txt`: one scientific name or TVK per line; `#` lines ignored.
- `.csv`: a `tvk` column and/or a name column (`species`, `scientific_name`, `name`, `taxon`).

## fetch options

| Option | Effect |
|---|---|
| `--synonyms` | Also search UKSI synonyms of each species |
| `--from-year` / `--to-year` | Keep pages within a year range |
| `--max-pages N` | Cap per searched name (default 500; 0 = no cap). Earliest pages kept first |
| `--include-title WORD ...` | Keep only titles containing these words (e.g. `Entomologist Scottish`) |
| `--exclude-title WORD ...` | Drop titles containing these words (e.g. `catalogue index`) |
| `--count-only` | Report counts only |
| `--refresh` | Re-search names already searched |

Runs are resumable: already-searched names are skipped, and pages whose text
failed to download are retried on the next run. Ctrl+C is safe.

## Notes

- Requests are throttled to one per second; text fetch is one request per page.
- BHL's name index both misses some mentions (OCR errors, abbreviated genera)
  and includes some false ones (homonyms). Treat output as a reading list.
- OCR text is unverified — check against the page image before using a record.
- `page_hits.review_status` (default `unreviewed`) is in place for a later review stage.
- `data/` is git-ignored, so the key, database and exports stay out of the repo.

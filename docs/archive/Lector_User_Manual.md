# Lector user manual

Lector, part of the Biological Software suite. Written 12 Oct 2026 for the code after
the Round 8 fixes (L1–L16) and the review that followed them, and checked against that
code.

Contents

1. What Lector is
2. Installing and first run
3. Ideas you need
4. The screens, step by step
5. Common jobs
6. The console
7. Files and data
8. Troubleshooting
9. Tests: automated and by hand
10. Glossary

---

## 1. What Lector is

Lector reads the Biodiversity Heritage Library (BHL) for you.

You give it a species. It:

1. looks the species up in UKSI and lists its older names (synonyms), checking each one;
2. asks BHL for every page that BHL's name index links to those names;
3. keeps the pages that pass your filters (years, journals, page limit);
4. downloads the text of each page (BHL's OCR text);
5. lets you read the pages, mark them and write notes;
6. exports a Word dossier with an Excel index (and a PDF or plain text if you want).

It keeps each search, with its names, filters and every run, so you can repeat it
exactly, or run it again later to catch pages BHL has scanned since.

**What Lector is not**

- It is not a records database. It does not put records into Observatum. You enter a
  record by hand and then mark the page "Record extracted". (The Extracted records
  screen is a placeholder for later.)
- It does not correct OCR text. The text is what BHL's scanner read. Names, dates and
  places can be wrong. Always check against the page image on BHL.
- It does not find pages BHL has not indexed. BHL's name index misses some mentions
  (OCR errors, abbreviated genera) and includes some false ones (homonyms). Treat the
  result as a reading list, not a complete bibliography.
- It does not decide copyright. It flags pages from 1930 on for you to check.

---

## 2. Installing and first run

### 2.1 What you need

| Item | Needed for | How to get it |
|---|---|---|
| Python 3.14 and the suite | Everything | Already on your PC (`py -3.14`) |
| `python-docx` | Word dossier (and so the PDF and the Excel index) | `py -3.14 -m pip install python-docx` |
| `openpyxl` | Excel index | `py -3.14 -m pip install openpyxl` |
| `docx2pdf` **and** Microsoft Word, or LibreOffice | PDF copy of the dossier | `py -3.14 -m pip install docx2pdf` (Word must be installed) |
| A BHL API key | Anything that talks to BHL | Free, see 2.2 |

Install the two main packages in one go:

```powershell
py -3.14 -m pip install python-docx openpyxl
```

Searching, reading and the plain text export need none of these packages. If one is
missing, Lector says which one and shows the install command. It never crashes for a
missing package.

### 2.2 The BHL API key

1. Go to https://www.biodiversitylibrary.org/getapikey.aspx and ask for a key. It is free.
2. Make a text file `data\bhl_api_key.txt` in the Biological Software folder.
3. Put the key in it, on one line, nothing else. Save.

Lector looks for the key in this order:

1. `--key` on a console command (fetch and probe only);
2. the `BHL_API_KEY` environment variable;
3. `data\bhl_api_key.txt`.

The foot of Lector's left-hand menu says "BHL API key: set" or "BHL API key: not set
(see README)", and shows the database path.

### 2.3 Opening Lector

Any of these opens the Lector window:

| Way | What to do |
|---|---|
| Atrium | Click the **Lector** tile (book icon). If Lector is already open, Atrium brings its window to the front instead of opening a second copy. |
| Launcher | Double-click `launchers\run_lector_gui.bat`. |
| PowerShell | In the Biological Software folder: `$env:PYTHONPATH = "$PWD;$PWD\Observatum"` then `py -3.14 -m Lector gui` |

The window title is "Lector — Biodiversity Heritage Library".

Atrium's Tools row also has a **Lector console** button. That opens the console mode
(type species one at a time) in its own window. See section 6.

### 2.4 The one-off database update

Lector's database is `data\lector.db`. The version of 12 Oct 2026 keeps saved
searches, runs and review notes, which the 7 Oct version did not. The first time the
new Lector opens an older `lector.db`:

1. A question box "Update lector.db" appears. It lists, table by table, what the update
   would change (a dry run: nothing has been changed yet) and the saved searches it
   would make from your earlier fetches.
2. Press **Yes** to update. Lector first copies the database to
   `data\_backups\lector_pre_v3_20261012_101500.db` (the date and time of the copy),
   then updates in place. A message gives the backup's path.
3. Press **No** and nothing is changed. Lector says it needs the update and closes.

The update only adds tables and columns. No stored page, text or note is changed or
removed. Each species you had fetched becomes one saved search with one run (shown as
"from an earlier Lector"). Its names are checked as a new search's are: a name the
checks hold back is stored unticked, with its reason, even if the old fetch searched it.

You can do the same from PowerShell instead (close Lector first):

```powershell
py -3.14 scripts\migrate_lector_v2.py
py -3.14 scripts\migrate_lector_v2.py --apply
```

The first line is a dry run and ends "DRY RUN - Nothing has been changed. Re-run with
--apply (Lector closed)." The second makes the backup and updates.

Your database was updated on 12 Oct (to version 2). The Round 8 Lector needs one more,
small update (version 3): it adds two columns to the runs (name searches and page texts
counted apart) and an empty `activity` table (for "Fetch missing text"). So you will see
the question once more. It lists only "activity: - -> 0" and makes no saved search.
Press **Yes**; the backup is `data\_backups\lector_pre_v3_<date>_<time>.db`. After that
you will not see it again.

### 2.5 The one-off name-choice fix

The 12 Oct update stored every name the old fetches had used as ticked, including
held-back synonyms (for Lamia textor: Lamia rosenmulleri, L. sartor, L. sutor,
L. titillator, which the 7 Oct `--synonyms` command had searched). Until you fix it,
Edit search shows each of them ticked, with its reason followed by "— ticked when
lector.db was updated, not by you: untick it unless you want it searched". The update
no longer does this, and a script unticks them in your database. Run it **before** you
edit and save those searches (a held-back name you save ticked counts as your choice):

```powershell
py -3.14 scripts\fix_lector_name_choices.py
py -3.14 scripts\fix_lector_name_choices.py --apply
```

1. Close Lector.
2. Run the first line (dry run). It lists exactly which names in which searches it would
   untick, with the reason for each, and how many pages were found only by those names.
   For Lamia textor it should read:

   ```text
   Lamia textor (search 1): untick 4 names the update ticked:
     Lamia rosenmulleri  -  Held back: on the suite corrections list (unverified; old Lamia combination resolved at genus level (F25))
     Lamia sartor  -  Held back: epithet is current in Monochamus sartor (NHMSYS0020704740); also on the suite corrections list
     Lamia sutor  -  Held back: epithet is current in Monochamus sutor (NHMSYS0020704741); also on the suite corrections list
     Lamia titillator  -  Held back: on the suite corrections list (Monochamus titillator (Nearctic), not Lamia textor (F25))
     Pages held that were found only by these names: N (kept now; the next run lists them under "No longer matched").

   DRY RUN - Nothing has been changed. Re-run with --apply (Lector closed).
   ```

   (The search number and N may differ on your PC.)
3. If the list is what you expect, run the second line. It backs `lector.db` up to
   `data\_backups\lector_pre_fix_names_<date>_<time>.db` first, prints the same list,
   then "Done. Backup: …".
4. Run the first line again. It now says "No ticked names to change: every search the
   update made matches the UKSI checks."
5. Open Lector, open the search, press **Edit search**. The held-back names are unticked,
   each with its reason.

The script only touches searches the update made, and in them only names the old fetch
used, that are still ticked, that the checks hold back today and that have no reason
stored. A held-back name you ticked yourself in Edit search and saved keeps its reason,
so it is left alone; so are names you added and every other search. Pages are not
touched: pages found only by the unticked names stay until the search is next run.

---

## 3. Ideas you need

### 3.1 Saved search

A saved search is one species (or a family, or a list) with:

- the **names** to send to BHL, each ticked or not;
- the **filters** (years, journals, page limit, skips);
- every **run**, each with a copy of the names and filters it used.

A search is a **draft** until it is first run, then **active**. Its species cannot
change; to search a species differently, duplicate the search or make a new one.

### 3.2 Names

BHL indexes names exactly as printed, so older names find older papers. For a species,
Lector offers:

| Name | Where from | Ticked at first? |
|---|---|---|
| The accepted name | UKSI | Yes |
| UKSI synonyms | UKSI (synonyms and names list) | Yes, unless held back |
| Names you add | You, in the window, or `+` lines in your list | Yes |

**Held back.** UKSI gives some names as synonyms of the wrong species. For example it
gives Lamia sartor and L. sutor under Lamia textor, but they are Monochamus. Lector
checks every synonym before using it and holds it back (unticked, with the reason
shown) when:

1. its epithet is current for another species of the same family ("Held back: epithet
   is current in Monochamus sutor (NHMSYS0020704741)");
2. UKSI also gives it for another taxon ("Held back: UKSI also gives this name for …");
3. it is itself the current name of another taxon;
4. it is on an exclusion list: the suite's `scripts\uksi_synonym_corrections.csv`
   ("Held back: on the suite corrections list (…)") or your own
   `data\lector_synonyms.txt` ("Held back: on your own list (…)").

For Lamia textor today Lector ticks Lamia textor and Cerambyx textor and holds back
Lamia rosenmulleri, L. sartor, L. sutor and L. titillator.

**Your ticks.** In a search you can tick a held-back name. It then shows its reason
followed by "— ticked by you". Your tick belongs to that search only.

**Your list, `data\lector_synonyms.txt`.** One change per line. `#` starts a comment.
The species after `@` can be a name or a TVK. Text after `|` is your reason.

```text
- Lamia sartor                      never search this name, for any species
- Lamia sutor @ Lamia textor        ...only when searching Lamia textor
+ Cerambyx textor @ Lamia textor    also search this name for Lamia textor
```

A `+` line adds a name, or confirms a name that checks 1–3 would hold back. It does
**not** override a name excluded by the suite corrections list; to use such a name in
one search, tick it in that search. You can edit the file in Notepad, or let Lector
add lines for you (the "Remember my choices" box in the search builder, or the
console's `synonyms --add` / `--exclude`).

**Family and list searches.** Type a family (for example Cerambycidae) and Lector
searches the accepted name of every UKSI species in it (88 for Cerambycidae), with no
synonyms. A list search is several species in one search; the service supports it but
the window does not make one yet.

### 3.3 Filters

Every run applies the search's **current** filters.

| Filter | What it does |
|---|---|
| From year / To year | Keep pages dated in this range. "Any" = no limit. A page with no year is left out when a year limit is set. |
| Journal preset | A ready-made list of title words. Choosing one copies its words into the search. |
| Title must contain one of | Keep only titles containing one of these whole words. English plurals count: "Naturalist" matches "Naturalists' Society" but not "naturalistes". |
| Leave out titles containing | Drop titles containing any of these whole words. |
| Page limit per name | At most this many pages per name, earliest first. Default 500. "No limit" = 0. |
| Skip index pages | Leave out pages BHL types as index, table of contents or list of illustrations. Off by default. |
| Skip duplicate scans | Keep one copy when several libraries scanned the same printed page (same title, volume and page number). On by default. |

**Built-in presets**

| Preset | Title must contain | Leave out |
|---|---|---|
| British periodicals | Entomologist, Naturalist, Zoologist, British, Transactions, Annals, Proceedings | Canadian, American, America, Australia, Australian, India, Indian, New Zealand, South African |
| Scottish titles | Scottish, Scotland, Glasgow, Edinburgh, Perthshire, Berwickshire, Dumfriesshire, Galloway, Aberdeen, Dundee, Inverness, Highland | — |

You can save your own words as a preset. A search keeps its own copy of the words, so
editing a preset later never changes what an earlier run did.

**How the screens describe the journals filter.** The Scope column on Saved searches
and the Journals line on a search's page use the same words for the stored filter:

| Stored filter | Shown as |
|---|---|
| A preset's words | The preset's name, e.g. "British periodicals" |
| No title words | "Any journal" |
| Your own title words | "Your title words (3)" (how many words) |
| Words to leave out, without a preset | ", 2 words left out" is added |
| Filters never recorded (a 7 Oct fetch) | "Filters not recorded" |

The years read "All years", "1800–1950", "From 1800" or "To 1950".

### 3.4 Runs

A run asks BHL, applies the filters, stores the pages and downloads their text.

| Kind | What it does |
|---|---|
| **Run** (fetch) | Stores the pages within the filters and downloads any text not yet held. |
| **Count only** | Asks BHL how many pages each name has and how many pass the filters. Stores no pages and downloads no text. Shown in the run list as "Count only", not numbered. |

**Look for newly scanned pages.** A tick box on the search's page, ticked by default.
Ticked, the run asks BHL again for every name (one request per name), so pages BHL has
scanned since appear. Unticked, the run reuses BHL's last answer for each name and only
re-applies the filters: no name requests at all. Untick it after you change a filter.

**Run numbers.** Runs are numbered within each search: Run 1, Run 2, Run 3.
Count-only runs take no number. The same number is used everywhere: the run list,
"What changed in run 2", "Compared with run 1", messages, Recent activity ("Run 2 of
“Lamia textor”: …") and the dossier's front page ("Run: 2, 2026-10-12").

**Requests.** BHL allows one request a second. A run counts every request it makes,
name searches and page-text downloads, and says so, for example
"19 BHL requests (3 name searches, 16 page texts)". Runs made before Round 8 kept only
the total ("8 BHL requests").

**New, unchanged, no longer matched.** Each run compares its pages with what the search
held before:

- **New**: pages this run added.
- **Unchanged**: pages held before and still within the filters.
- **No longer matched** (withdrawn): pages held before that this run does not keep.
  Each says why:
  - "Now filtered out (years, journals or index pages)";
  - "Duplicate scan: the same printed page is kept from another copy" (with "Skip
    duplicate scans" on, which it is by default, even when no other filter is set);
  - "Over the page limit per name";
  - "No longer found on BHL for the names searched".

  They are **kept** in the database with your notes, not deleted. They leave the
  reading list and the dossier. You can bring one back with "Keep anyway".

A name whose BHL search failed in a run never causes its pages to be withdrawn.
A cancelled run never withdraws a page unless every name had been looked up before you
cancelled (a cancel while it downloads text comes after that).

**Cancelled runs.** Cancel stops a run within about a second. Everything downloaded so
far is kept. Running again carries on where it stopped. The message reads, for example,
"Run 3 cancelled. Whatever was downloaded is kept; running again carries on from there."

**Fetch missing text.** Downloads the text of pages the search already holds
but has no text for, and nothing else: no name searches, no filters re-applied, no page
withdrawn. It works even on a search whose filters were never recorded.

### 3.5 Page types, duplicates, index pages

- **Page type.** BHL types some pages (Text, Index, Table of Contents, Illustration…).
  Lector stores it and shows it.
- **Duplicate scans.** Several libraries often scanned the same volume. Lector merges
  them twice: when choosing pages (same title, volume and printed page number, if "Skip
  duplicate scans" is on), and again when you read or export, by comparing the page
  text. Merged copies appear as "Same text also at" with their links. Two pages of one
  scanned volume are never merged (a repeated advertisement is not a copy).
- **Entries and pages.** One **entry** is one text, with any duplicate scans merged into
  it. So the reading list can show "79 entries (87 pages, duplicates merged)".
- **Index and contents pages.** A page BHL types as index or contents, or whose layout
  looks like one (most lines end in a page number), is marked "likely index". In the
  dossier these go in Appendix A.
- **Name not in the text.** BHL's index lists the page but the name is not in the OCR
  text (a plate, a caption, a misreading). These go in Appendix B.

Lector finds names in the text in any case, with any spacing or line breaks, with or
without accents, hyphenated across a line end, with the genus abbreviated ("L. textor")
or left out (the epithet alone, as in a list under the genus).

### 3.6 Rights check

Pages dated 1930 or later carry the note "May be in copyright - check the rights
statement on BHL before reproducing". This is a reminder only. Lector does not check.

### 3.7 BHL's one request a second

Lector waits one second between requests to be polite to BHL. A request that fails is
tried up to 4 times in all, waiting longer each time (each try counts as a request). Time estimates assume one second per
request: 3 names and 400 pages of text is about 7 minutes.

---

## 4. The screens, step by step

The window has a menu on the left: **Saved searches**, **Reading list**, **Extracted
records**, **Exports**. Clicking a menu item always goes to that screen, even when it
is already highlighted (for example "Saved searches" while you are inside a search).

Every screen you reach from another one (a search's page, New search and Edit search,
Reading list, Exports) has a **← Back** button at the top left. It goes back to where you
came from, or to Saved searches if Lector does not know. Going back never starts a run
again, and after **Save and run** Back skips the editor. The **Cancel** buttons of the
builder and of Exports go back the same way.

Long work (counts, runs, fetching text, exports) runs in the background. A line at the
bottom of the window shows what is happening, a progress bar and **Cancel**. Only one
such task runs at a time; if you start another, Lector asks you to wait or cancel.

If the window is small, each screen scrolls, and the row of buttons at the top right
scrolls sideways.

### 4.1 Saved searches (the dashboard)

**Top right:** a filter box and **New search**.

**Filter box.** It reads "Filter your searches…". Type and the list shrinks as you type
(no button to press). A search stays listed when every word you type is in its name,
species, TVK, Scope (journals) or years. The small × in the box clears it.

**Four cards:** Saved searches, Pages harvested, Awaiting review (pages not yet given a
status), Records extracted.

**The table.** One row per search, most recently changed first.

| Column | Shows |
|---|---|
| Search | The search name (click it to open the search), the species in italics, the TVK (or "Whole family from UKSI") and how many names are ticked |
| Scope | The journals filter and the years, worded as in 3.3 |
| Last run | Date of the last run, "(cancelled)" or "(failed)" if so, and how many runs (count-only runs included); or "Draft — not run" |
| Pages | Pages the search holds, and "of N found" in its last run |
| Reviewed | A bar and "x of y" pages given a status |
| (buttons) | See below |

Double-click a row to open the search.

**Row buttons.**

| Button | When | Does |
|---|---|---|
| **Edit** | Every row | Opens Edit search (names and filters) |
| **Run** | Draft searches | Opens the search's page and starts a run |
| **Run again** | Searches already run, with filters recorded | Opens the search's page and starts a run |
| **Set filters** | Searches whose first filters were never recorded (made from a 7 Oct fetch) | Opens Edit search so you can set them |
| **Review** | Searches holding pages | Opens the Reading list on this search |
| **More** | Every row | A menu, below |

**More menu.**

| Item | Does |
|---|---|
| Open (runs and changes) | The search's page |
| Edit names and filters | Edit search |
| Count only (no pages downloaded) | The search's page, starting a count-only run |
| Fetch missing text (N pages) | Downloads text for the N pages without it ("1 page" when one). Not in the menu when N is 0. |
| Duplicate as a new draft | Makes a copy named "… (copy)" and opens it in Edit search |
| Export a dossier | The Exports screen for this search |

**Recent activity** lists the last eight runs, fetches of missing text and exports,
newest first, each with its date and time, for example:

- "Run 4 of “Lamia textor”: 87 pages, 19 BHL requests (3 name searches, 16 page texts)"
  (" (cancelled)" or " (failed)" at the end when so);
- "Count only, Lamia textor: 1104 found, 87 within filters";
- "Fetched missing text, “Rutpela maculata”: 7 pages, 7 BHL requests";
- "Exported Lamia_textor_dossier.docx (79 pages)".

**Needs attention** lists, for each search:

- held-back names on an active search ("… held back (UKSI synonym checks); confirm them
  in the search to use them") — informational;
- "the filters of its first fetch were not recorded. Set the filters before running it
  again";
- "Emus hirtus: 494 pages still without text.", with a **Fetch now** link that fetches
  them (as **Fetch missing text** does).

If nothing needs attention it says so.

### 4.2 New search and Edit search (the builder)

Open with **New search** (empty) or **Edit** (an existing search). The screen has three
cards on the left, the Preview on the right, and the save buttons under the Preview.

**1. Species**

1. Type a species, a family or a TVK in "Species (UKSI)", for example `lamia textor`.
2. Press **Find** (or Enter).
3. Lector shows what it matched: name, TVK, rank, family. If you typed an older name it
   says "(you typed …, an older name)" and uses the current species. If the name is not
   in UKSI it says "… is not in UKSI — check the spelling."
4. "Search name" fills in with the species name. Change it if you like (for example
   "Lamia textor — British literature").

In Edit search the species is fixed (Find is greyed out).

**2. Names to search**

One row per name: a tick box, the name, where it came from ("accepted name", "UKSI
synonym", "added by you") and the number of BHL pages for it ("not counted yet" until
BHL has been asked). Held-back names have a pale warning background and their reason
underneath.

- Tick or untick a name to include it or not. A held-back name you tick shows
  "— ticked by you" after its reason. A held-back name that is ticked only because the
  12 Oct update ticked it shows "— ticked when lector.db was updated, not by you: untick
  it unless you want it searched" (until you run the fix in 2.5, or tick or untick it).
- To add a name (for example an original combination), type it in "Add a name…" and
  press **Add name** or Enter. Names you add have a **Remove** link.
- **Remember my choices for these names in every search of this species.** Tick this
  before saving to write your changes (ticks that differ from Lector's suggestion, and
  names you added) to `data\lector_synonyms.txt`, so the next search of this species
  starts with them. Each line is marked "chosen in Lector".

In Edit search, every name Lector would offer is listed, including held-back names with
their reasons, even for searches made by the 12 Oct update.

**3. Filters**

1. **From year**, **To year**: type a year, or leave "Any".
2. **Journal preset**: "Any journal" (no title words: every journal), "Your own title
   words" (the words you type below), or a preset. Choosing a preset fills in the title
   words; choosing "Any journal" clears the title words. Changing a word afterwards
   switches the box to "Your own title words", because the words are now your own
   (or to "Any journal" if you remove the last one).
3. **Page limit per name**: "No limit" or a number.
4. **Title must contain one of**: type a word in "Add word" and press Enter. Each word
   becomes a blue chip. Click a chip to remove it.
5. **Leave out titles containing**: the same, red chips.
6. **Skip index pages**, **Skip duplicate scans**: tick boxes. A ticked box, here and
   everywhere in Lector, shows a white tick on the blue square.
7. **Save words as a preset**: asks for a name and keeps the current words as a preset
   for other searches.

**Preview** (right)

| Line | Meaning |
|---|---|
| Found on BHL | Pages BHL lists for the ticked names (before filters) |
| Within filters | Pages that pass the filters, duplicates dropped |
| Already in database | Of those, pages whose text Lector already has |
| To download | Pages whose text a run would download |

Under it: the estimated time and number of requests, and any names "Not counted yet".
The preview updates as you change names or filters, using BHL's last answers (instant,
no requests). **Refresh count** asks BHL now (one request per name, in the background).

**Save buttons**

| Button | Does |
|---|---|
| **Save and run** | Saves, then opens the search's page and starts a run |
| **Save as draft** | Saves without running, back to Saved searches |
| **Cancel** | Back to where you came from; nothing saved |

You must have found a species and ticked at least one name, or Lector says so.

Saving filters on a search made from a 7 Oct fetch records them, so it can be run again.

### 4.3 A search's page

Opened from the search name, **Open**, **Run**, **Run again** or **Save and run**.

**Top:** the search name, then TVK · created date · draft or active. Buttons:

| Button | Does |
|---|---|
| **Edit search** | Edit search |
| **Duplicate** | Copy as a new draft, opened in Edit search |
| **Count only** | A count-only run (in the background) |
| **Run** / **Run again** | A full run (in the background) |

**Summary card:** Names (ticked, and how many held back), Years, Journals (worded as in
3.3), Page limit, Left out ("Duplicate scans", "Duplicate scans and index pages",
"Index pages" or "Nothing": the skips, which drop pages even with no years or journals
set), Pages held. Under it the tick box **Look for newly scanned pages (asks BHL again for
every name; untick to re-apply changed filters only)**. While a run goes, a line says
"Running… BHL allows one request a second; you can keep reading other pages, or press
Cancel below." When it ends, the line gives the result.

Result messages look like this:

- "Run 3 finished: 87 pages kept of 1,104 found — 6 new, 79 no longer matched, 19 BHL
  requests (3 name searches, 16 page texts)." If some texts failed: "N pages could not be
  downloaded: run again to retry them."
- "Counted: 1,104 pages found on BHL, 87 within the filters; 3 BHL requests (3 name
  searches, 0 page texts)."
- "Run 3 cancelled. Whatever was downloaded is kept; running again carries on from
  there." (one sentence, nothing after it)
- A failed run adds BHL's error in brackets.

**Runs card.** Every run, newest first:

- a fetch run: "Run 2 · 12 Oct 2026, 14:05", then "87 pages kept of 1,104 found ·
  6 new, 79 withdrawn", then the BHL requests (and "· N failed" if texts failed);
  "(cancelled)", "(failed)" or "(from an earlier Lector)" after the date when so;
- a count-only run: "Count only · date", then "N found · no pages downloaded · " and its
  BHL requests.

Click a run to see what changed in it.

**What changed card.**

- Heading "What changed in run 2" and "Compared with run 1".
- "Settings changed: …" (for example "to year: any → 1930", "added Cerambyx textor"), or
  "Same settings as the run before."
- Three tabs with counts: **New**, **No longer matched**, **Unchanged**. Each lists pages
  with their citation and year. A withdrawn page also says why (one of the four reasons
  in 3.4) and has a **Keep anyway** button; once kept it shows "Kept".
- Double-click a page to read it in the Reading list.
- **Review new pages** opens the Reading list at the first new page. **Export** opens
  Exports for this search.

The first run of a search has nothing to compare with; the card reads "Run 1 is the
first run of this search: N pages kept. Later runs are compared with it." A count-only
run has nothing to compare.

A search made from a 7 Oct fetch whose filters were never recorded cannot be run until
you set them: **Run again** says so and opens Edit search. **Count only** still works.

### 4.4 Reading list

Opened from **Review**, **Review new pages**, a double-click on a changed page, or the
left menu.

**Top:** a **← Back** button, then under the title one line with live numbers, for
example "Lamia textor · 79 entries (87 pages, duplicates merged) · 12 of 79 reviewed".
(With no duplicates it reads just "N entries".) At the top right:

| Box | Choices |
|---|---|
| Search | Every search holding pages |
| Show | Unreviewed (the first time), All pages, Relevant, Record extracted, Not relevant, No longer matched |
| Order | By year (grouped by decade), By journal (grouped by title) |

**Left pane: the list.** A find box ("Find in the list (journal, words, notes)") filters
as you type. Each row: a coloured dot for its status, the title, volume, page and year,
then its marks: status, tag, "likely index", "+2 scans" (duplicates merged into it),
"new" (new in the last run), "no longer matched".

**Middle pane: the page.**

- "PAGE 5 OF 79", the full citation, then: matched name, BHL page number, page type,
  section ("Likely index or contents page" or "Name not found in the page text") and
  "no longer matched by the filters" for a withdrawn page.
- A yellow note for pages from 1930 on (rights check) and a blue note for likely index
  pages, with why ("BHL page type" or "layout").
- The excerpts: up to three passages of about five lines around the name, with the name
  in bold.
- "Same text also at:" with links to the merged copies.
- **Open on BHL**: the page scan in your browser.
- **Show full page text** / **Show excerpts**: switch between the whole OCR text (names
  in bold) and the excerpts.
- **Previous** and **Next**.

If the page's text has not been downloaded yet, the middle pane says "The page text has
not been downloaded yet: use “Fetch missing text” (the search's More menu on Saved
searches, or Fetch now under Needs attention)." See 5.3.

**Right pane: Review.**

| Control | Does |
|---|---|
| **Relevant (1)**, **Not relevant (2)**, **Record extracted (3)**, **Unreviewed (4)** | Set the page's status. A button leaves you on the page; the key (1–4) also moves on to the next page. |
| What is this page? **Record**, **Biology**, **Mention**, **Index or list** | A tag, separate from the status. Click again to clear it. |
| **Notes** | An outlined text box under the label "Notes". Type; it saves itself after a short pause ("Saving…", then "Notes saved."). Notes are also saved when you change page or close Lector. |

**Keys** (when you are not typing in a box). The keys under the Review card read "Keys:
J next, K previous, 1–4 status and next page."

| Key | Does |
|---|---|
| J | Next page |
| K | Previous page |
| 1 | Relevant, then next page |
| 2 | Not relevant, then next page |
| 3 | Record extracted, then next page |
| 4 | Unreviewed, then next page |

Typing a digit or J or K in the Notes box or the find box types it; it never changes a
status or the page. Clicking in the page text (to scroll or copy) does not stop the
keys.

Review marks belong to the page and the species, so a page marked in one search of
Lamia textor shows the same mark in every search of Lamia textor.

"Not relevant" pages are left out of exports unless you tick them on the Exports screen.

### 4.5 Extracted records

A placeholder. It explains that taking records into Observatum is not built yet: enter
the record in Observatum by hand, then mark the page "Record extracted" (key 3). Those
pages are counted on Saved searches and kept in the dossier.

### 4.6 Exports

Title "Export a literature dossier".

**Left card: options.**

1. **Search**: which search to export (searches holding pages).
2. **Include pages marked as**: Relevant, Record extracted, Unreviewed (ticked) and Not
   relevant (not ticked).
3. **Order entries**: By year, or By journal, then year.
4. **Write**:
   - Word dossier (.docx) — ticked;
   - Excel index (.xlsx), made with the dossier — ticked;
   - PDF copy of the dossier — not ticked;
   - Plain text bundle and index (.txt, .csv) — not ticked.
   If a package is missing, that box is greyed out with "Needs python-docx: install once
   with  py -3.14 -m pip install python-docx" (or openpyxl). If PDF has no converter it
   says "Needs Microsoft Word (with docx2pdf) or LibreOffice".
5. **Options**: "Put index pages and pages without the name in appendices" (ticked),
   "Include my notes" (ticked).
6. "Saved to …" shows the folder (`data\lector_exports`).
7. Press **Create dossier**. It runs in the background. When done the card lists any
   messages (for example "PDF made with Microsoft Word.") and a link per file; click a
   link to open the file. **Cancel** goes back to where you came from.

**Right card: Preview.** The species, the number of entries, the first 12 rows (year,
source, status) and the first entry's excerpt with your note.

**Previous exports.** Every file made from this search, newest first, with its kind and
page count; "(file moved or deleted)" if it is gone. Double-click to open. **Open
folder** opens `data\lector_exports`.

**File names.** From the search name, spaces turned to underscores:

| File | Contents |
|---|---|
| `Lamia_textor_dossier.docx` | The Word dossier |
| `Lamia_textor_dossier_index.xlsx` | The Excel index |
| `Lamia_textor_dossier.pdf` | The PDF copy |
| `Lamia_textor.txt` and `Lamia_textor_index.csv` | The text bundle and its index |

Exporting the same search again overwrites these files (close them in Word and Excel
first). The console's `export` writes different names (`Lamia_textor_all_pages.txt`,
`Lamia_textor_all_pages_dossier.docx`…), so it never overwrites these (see 6.3).

**The Word dossier**

1. **Front page**: the species in italics; "Literature found in the Biodiversity
   Heritage Library"; TVK; names searched; date generated; pages (how many entries,
   duplicate scans merged, index pages, pages without the name); order; the saved
   search's name; the run it comes from ("Run: 3, 2026-10-12", the search's own run
   number); the statuses included; and a reminder that excerpts are uncorrected OCR.
2. **Summary**: a table in date (or journal) order: No., Year, Source, Type, BHL link.
   Each number links to its entry.
3. **Entries**: one per text. Heading "12. 1841 · source"; the excerpts with the name in
   bold; "View page on BHL"; page number, matched names and text source; "Same text also
   at:" for merged copies; the rights note for pages from 1930 on; "Your note:" with the
   tag and notes (if "Include my notes").
4. **Appendix A · Index and contents pages** and **Appendix B · Name not found in the
   page text**, each a table: Year, Source, Note, BHL (if "appendices" is ticked).
5. Footer: "Lector · species · page N".

**The Excel index.** Two sheets. **Index**: one row per page (merged copies included,
pointing to their entry), filters on, top row frozen. Columns: Entry, Year, Title, Volume, Page, Page type,
Section (Entries / Appendix A / Appendix B), Same text as entry, Matched names, Rights
check, BHL link, Page ID, Excerpt, Authors, Article title, Review, Notes, Citation.

**About**: the search, the saved search's name, the run ("2, 2026-10-12"), the statuses
included, the number of rows, and notes.

BHL gives authors and article titles only for article "parts", which are few and mostly
modern. When no exported page has an author, the Authors column is left out; the same
for Article title. The About sheet then has the note "Authors and article titles: none
given by BHL for these pages" (or "Authors: none given…" / "Article title: none given…"
when only one is left out). The text bundle's CSV does the same.

**The text bundle.** One `.txt` with every page in date order: a header with the
citation, BHL link, matched names, text source and your note, then the full OCR text.
The `_index.csv` lists the pages: page_id, year, title, volume, page, matched_names,
page_url, has_text, authors, article_title, citation (authors and article_title left
out when empty in every row).

**PDF.** Lector writes the Word file first, then converts it with Microsoft Word
(through `docx2pdf`) or, failing that, LibreOffice. If neither is there you get "PDF not
made: it needs Microsoft Word with the docx2pdf package (pip install docx2pdf) or
LibreOffice. The Word file is ready; you can also save it as PDF from Word."

---

## 5. Common jobs

### 5.1 Start a new species

1. Saved searches → **New search**.
2. Type the species, press **Find**. Check the match line.
3. Read the names. Leave held-back names unticked unless you know better. Add any
   original combination you know BHL prints (Add name).
4. Set the filters (5.4 for British journals).
5. Look at the Preview. If names say "not counted yet", press **Refresh count** and wait.
6. If "To download" is large, think about a page limit or tighter filters.
7. Press **Save and run**. Watch the bottom line. You can read other searches meanwhile.
8. When it finishes, press **Review new pages**.

### 5.2 Run again to catch new scans

1. Saved searches → **Run again** on the row (or open the search and press **Run
   again**).
2. Leave **Look for newly scanned pages** ticked.
3. When it ends, read the **New** tab of "What changed". Double-click a page to read it.

### 5.3 Fetch missing text

Pages without text show "The page text has not been downloaded yet…" in the Reading
list, and Needs attention says "<search>: N pages still without text."

1. Saved searches → **More** on the search's row → **Fetch missing text (N pages)**, or
   press **Fetch now** on the Needs attention line.
2. The bottom line shows "Fetching missing text for “<search>”: Downloading page text
   3 of 494", one page a second. **Cancel** stops it; what was fetched is kept.
3. When it ends, the status bar says "Text downloaded for N of M pages." (or "Cancelled.
   Text kept for the N pages downloaded; M still without text."), the Needs attention
   count drops and Recent activity records it.

This downloads text only. It does not search BHL for names, apply filters or withdraw
anything. A full run also fetches missing text, but does all of those too.

### 5.4 Narrow to British journals

1. Open the search → **Edit search**.
2. Journal preset → **British periodicals**. The title words fill in.
3. Add or remove words if you like (the preset box then reads "Your own title words").
4. Press **Save as draft** (this saves without running; an active search stays active).
   Open the search again, untick **Look for newly scanned pages** and press **Run
   again**. No name requests are needed: Lector re-applies the filters to
   BHL's last answers.
5. Check the **No longer matched** tab. If a British title was dropped (for example one
   whose name has none of the words), press **Keep anyway**, or add its word to the
   filter and run again.

### 5.5 Review quickly with the keyboard

1. Reading list, Show **Unreviewed**, Order **By year**.
2. Click the first page in the list (or in the page text; not in the Notes or find
   box).
3. Read the excerpt. Press **1** (relevant), **2** (not relevant), **3** (record
   extracted) or **4** (unreviewed). Lector marks the page and moves to the next.
4. **J** and **K** move without marking.
5. To write a note, click in the Notes box and type. Click back in the list before using
   the keys again.

### 5.6 Export a dossier and PDF

1. Saved searches → **More** → **Export a dossier** (or the left menu → Exports).
2. Check the statuses to include and the order.
3. Tick Word, Excel and PDF.
4. Press **Create dossier**. Wait for the links.
5. Click the Word or PDF link to open it.

If PDF says it needs a converter: `py -3.14 -m pip install docx2pdf` (Word must be
installed), then export again.

### 5.7 Change a held-back name decision

**For one search:**

1. Open the search → **Edit search**.
2. Tick the held-back name (it shows "— ticked by you") or untick a name.
3. **Save as draft** (or Save and run). The next run uses your choice.

**For every future search of the species:** do the above with **Remember my choices…**
ticked before saving. Or in the console:

```powershell
.\launchers\run_lector.bat synonyms "Lamia textor" --add "Cerambyx textor"
.\launchers\run_lector.bat synonyms "Lamia textor" --exclude "Lamia rosenmulleri" --reason "unverified"
```

To undo a remembered choice, open `data\lector_synonyms.txt` in Notepad and put `#` at
the start of its line. A `+` line cannot override the suite corrections list; to use
such a name, tick it in the search itself.

### 5.8 A search from 7 Oct with "Set filters"

1. Saved searches → **Set filters** on its row.
2. Set years and journals as you want them now, and **Save as draft**.
3. The row now shows **Run again**.

---

## 6. The console

The console does the same work without the window. It is older than the window: it
fetches into the saved search named after the species, and `status` and `export` work
by **species**, not by saved search (see the cautions below).

**How to run a command.** Open PowerShell in the Biological Software folder, then
either use the launcher:

```powershell
.\launchers\run_lector.bat status
```

or set the path once per PowerShell window and call Python:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\Observatum"
py -3.14 -m Lector status
```

Atrium's **Lector console** button opens the interactive mode (no command) in its own
window, which waits for Enter before closing.

### 6.1 Commands

| Command | Purpose | Example |
|---|---|---|
| *(none)* | Interactive: type a species, answer whether to search older names (for a species with no saved search yet), Lector fetches, writes `<Species>_all_pages.txt` and opens it. A species that already has a saved search is run with its own names and filters. Enter on an empty line finishes. | `.\launchers\run_lector.bat` |
| `gui` | Open the window | `py -3.14 -m Lector gui` |
| `probe NAME` | BHL's raw answer for one name, saved as `data\lector_exports\probe_Lamia_textor.json`; prints the first 10 pages parsed | `.\launchers\run_lector.bat probe "Lamia textor"` |
| `fetch FILE` | Run each species in the file: its saved search, or a new one with the command's names and filters; stores pages, fetches text | `.\launchers\run_lector.bat fetch species.txt --synonyms` |
| `status` | Per species: pages, pages with text, years (every page ever found, withdrawn ones too) | `.\launchers\run_lector.bat status` |
| `export` | Text bundle, or Word dossier and Excel index, per species, named `<Species>_all_pages…` | `.\launchers\run_lector.bat export --name "Lamia textor" --docx` |
| `synonyms NAME` | Which names a search would use, which are held back and why; change your list | `.\launchers\run_lector.bat synonyms "Lamia textor"` |
| `forget --name NAME` | Remove a species' page links and BHL answers so it is searched afresh (page text kept) | see cautions |

Add `-h` to any command for its help, for example `.\launchers\run_lector.bat fetch -h`.

### 6.2 Options

**fetch**

| Option | Effect |
|---|---|
| `FILE` | A `.txt` (one name or TVK per line; `#` lines ignored) or a `.csv` with a `tvk` column or a name column (`species`, `scientific_name`, `name`, `taxon`) |
| `--synonyms` | Also search the checked UKSI synonyms |
| `--from-year 1800` / `--to-year 1950` | Year range |
| `--max-pages 500` | Cap per name (default 500; 0 = no cap) |
| `--include-title Entomologist Scottish` | Keep only titles with one of these whole words |
| `--exclude-title catalogue index` | Drop titles with any of these whole words |
| `--skip-index` | Leave out index and contents pages |
| `--count-only` | Counts only; store no pages |
| `--refresh` | Ask BHL again for names already searched (finds new scans). Without it the last answer is reused. |
| `--replace-search` | For a species that already has a saved search: replace its names and filters with this command's. Without it the saved search's own names and filters are used |
| `--key KEY` | BHL API key for this command |

Ctrl+C stops a fetch safely; what was fetched is kept.

**export**

| Option | Effect |
|---|---|
| `--name "Lamia textor"` or `--all` | One species, or every species (one is required) |
| `--docx` | Word dossier and Excel index instead of text |
| `--by-journal` | With `--docx`: order by journal, then year |
| `--pdf` | Word dossier plus a PDF copy |
| `--out FOLDER` | Another output folder (default `data\lector_exports`) |

**synonyms**

| Option | Effect |
|---|---|
| `--add NAME …` | Also search these names (writes `+` lines) |
| `--exclude NAME …` | Never search these names (writes `-` lines) |
| `--all-species` | With `--exclude` (or `--add`): for every species, not just this one |
| `--reason "text"` | Your reason, kept in the list |

**forget**

| Option | Effect |
|---|---|
| `--name "Lamia textor"` | The species (required) |
| `--yes` | Go ahead even if pages have review statuses or notes |

**probe**: `--key KEY`.

### 6.3 Cautions

- **`fetch` and the interactive mode use the species' saved search as it is.** For a
  species that already has a saved search (named after it), they run it with its own
  names and filters, so your ticks and filters from the window are kept, and they print
  what they used:

  ```text
    Saved search “Lamia textor” kept as it is: its own names and filters are used, not this command's (--replace-search would replace them).
    Names: Lamia textor, Cerambyx textor
    - Lamia sartor: Held back: epithet is current in Monochamus sartor (…)
    Filters: British periodicals; All years; page limit none
  ```

  The command's own names and filters (`--synonyms`, `--include-title`, years, page
  limit) are used only for a species with no saved search yet, or with
  `fetch --replace-search`, which replaces the saved search's names and filters with the
  command's (your ticks included). `--count-only` and `--refresh` work either way. A
  search whose filters were never recorded is not run from the console: set its filters
  in the window, or use `--replace-search` with your filters.
- **`export` and `status` work on everything stored for the species**, every page ever
  linked to it, including pages a search has withdrawn. The window's Exports use only
  the pages the search holds now. So the console's files have their own names,
  `<Species>_all_pages.txt`, `<Species>_all_pages_index.csv`,
  `<Species>_all_pages_dossier.docx` and `<Species>_all_pages_dossier_index.xlsx`, and
  never overwrite the window's (`<Search>.txt`, `<Search>_dossier.docx`…).
- **`forget` removes page links, and with them review statuses and notes.** It refuses
  if any page has a status or note, unless you add `--yes`. Runs now re-apply changed
  filters by themselves, so you should not need it. Do not use it without asking first.

### 6.4 Scripts

| Script | What it does |
|---|---|
| `scripts\migrate_lector_v2.py` | The one-off database update (2.4). Dry run, then `--apply`. |
| `scripts\fix_lector_name_choices.py` | Unticks the held-back names the update ticked (2.5). Dry run, then `--apply`. |

Both back `lector.db` up to `data\_backups` before changing anything, and both say
"Nothing has been changed" on a dry run. Close Lector before `--apply`.

---

## 7. Files and data

All in the Biological Software folder. `data\` is not in git, so backups are its only
protection.

| Path | What it is |
|---|---|
| `data\lector.db` | Lector's database: saved searches, names, filters, runs, pages and their text, BHL's cached answers, review statuses, tags and notes, exports made |
| `data\_backups\lector_pre_v2_….db` | Copy taken before the 12 Oct update |
| `data\_backups\lector_pre_v3_….db` | Copy taken before the Round 8 update (2.4) |
| `data\_backups\lector_pre_fix_names_….db` | Copy taken by `fix_lector_name_choices.py --apply` |
| `data\lector_exports\` | Dossiers, indexes, PDFs, text bundles (the console's named `…_all_pages…`), `probe_*.json` |
| `data\bhl_api_key.txt` | Your BHL key |
| `data\lector_synonyms.txt` | Your synonym list (made the first time you remember a choice) |
| `data\uksi.db` | UKSI (read only, shared with the suite) |
| `scripts\uksi_synonym_corrections.csv` | The suite's corrections to UKSI synonyms (read only for Lector) |
| `Lector\biosoft_root.txt` | Optional: the full path of the Biological Software folder, if Lector cannot find it |
| `launchers\run_lector_gui.bat` | Opens the window |
| `launchers\run_lector.bat` | Runs a console command |

**The cache.** BHL's answer for each name (its page list) is kept in `lector.db`. That
is why a run with "Look for newly scanned pages" unticked needs no name requests, and
why the builder's preview is instant. Page text is kept too, so a page is downloaded
once, whatever searches use it.

**Safe to delete?** Nothing, without asking first. Exports can always be made again,
but the database holds your review work and is not in git.

**Data scripts.** Anything that changes `lector.db` outside the window is a script
that does a dry run by default, lists what it would change and says "Nothing has been
changed"; `--apply` backs up with `conn.backup()` into `data\_backups` and then writes.
Close Lector first.

---

## 8. Troubleshooting

| What you see | Why | What to do |
|---|---|---|
| Exports: a format greyed out, "Needs python-docx: install once with …" (or openpyxl) | Package missing | Run the command shown, e.g. `py -3.14 -m pip install python-docx`, then reopen Exports |
| "PDF not made: it needs Microsoft Word with the docx2pdf package … or LibreOffice" | No converter | `py -3.14 -m pip install docx2pdf` (needs Word), or open the .docx in Word and Save as PDF |
| "PDF not made: Word could not convert it (…)" | Word not installed, or busy | Close Word dialogs and retry; or use LibreOffice; or Save as PDF from Word |
| "No BHL API key found. Get a free key at …" when you run or count | No key | See 2.2. The menu foot then says "BHL API key: set" |
| A run is slow | One request a second | Expected. Read the estimate in the Preview first. You can keep reading while it runs |
| "BHL failed for …" in a run message, or a run marked "(failed)" | BHL slow, offline or refusing | Lector already tried each request 4 times. Run again later; nothing is lost. A name BHL could not answer uses its cached answer if it has one, and never causes withdrawals |
| "(cancelled)" on a run | You pressed Cancel, or closed Lector during the run | Run again; it carries on. Nothing downloaded is lost |
| "N pages could not be downloaded" | Text downloads failed | Run again, or **Fetch missing text** |
| Reading list: "The page text has not been downloaded yet…" | Page held, no text | **Fetch missing text** (5.3) |
| Reading list: "The searched name was not found in the page text" | OCR missed it, or a plate | Open on BHL and look at the image |
| "Wait for “…” to finish, or cancel it." | One background task at a time | Wait, or press Cancel at the bottom |
| "… was fetched before Lector kept each search's filters" | A 7 Oct search | Set its filters (5.8) |
| "This search has no names to search: tick at least one." | Every name unticked | Edit search, tick a name |
| "Tick at least one kind of page to include." | All statuses unticked in Exports | Tick one |
| Closing Lector during a run | | Lector asks "A run is still going. Stop it and close? Downloaded text is kept." **Stop and close** stops the run cleanly and closes; **Keep running** (the default, and what Esc does) goes back and the run carries on. The same for Fetch missing text |
| Window too small (laptop, 150 % scaling) | | Each screen scrolls; the top-right buttons scroll sideways. The window fits 1280 × 720 working space |
| Console: "Saved search “…” kept as it is" | The species has a saved search | Expected: its own names and filters are used. Add `--replace-search` to use the command's (6.3) |
| Console: "… was fetched before Lector kept filters, so it is not re-run here" | A 7 Oct search, filters never recorded | Set its filters in the window (5.8), or `fetch` with your filters and `--replace-search` |
| Console: "Database error: … is it open elsewhere or still syncing in OneDrive?" | lector.db locked | Close other copies of Lector; wait for OneDrive; retry |
| "Could not find the Biological Software folder (the one with paths.py)" | Lector moved outside the suite | Put the folder's full path on one line in `Lector\biosoft_root.txt` |
| "Lector could not open its database" at start | lector.db damaged or locked | Close other copies; check the file; ask before doing anything to it |

---

## 9. Tests

### 9.1 Automated tests

Run these in PowerShell, in the Biological Software folder. They use no network (BHL is
replaced by a stand-in) and only temporary databases, so they cannot change your data.
Install pytest once if needed: `py -3.14 -m pip install pytest`.

**Lector tests only:**

```powershell
py -3.14 -m pytest -q tests\test_lector_a.py tests\test_lector_ui.py tests\test_lector_r8.py tests\test_review_r8.py
```

**The whole suite:**

```powershell
py -3.14 -m pytest -q tests
```

**What the result means.** The last line reads like "71 passed, 2 skipped in 30.12s".

| Word | Meaning |
|---|---|
| passed | The test ran and everything it checks was right |
| skipped | The test did not run because something it needs is absent: e.g. LibreOffice not installed, or no un-updated `data\lector.db` to try the update on (yours is already updated). Not a fault |
| failed | Something it checks was wrong. Copy the whole output (from "FAILURES") and send it |
| error | The test could not even start (often a missing package). Send the output |

**What each file covers**

| File | Covers |
|---|---|
| `tests\test_lector_a.py` | The engine and service, no window: whole-word title filter with plurals; page types, authors and article titles read from BHL; excerpts with names in bold and index-page detection; year parsing; name matching (case, spacing, accents, hyphens); duplicate grouping; synonym hold-back; saved searches; runs re-applying filters and withdrawing without asking BHL; new scans found on refresh; progress, cancel and resume; worker thread and retry of failed texts; review list; dashboard, duplicate, presets; unrecorded filters block a run; Word, Excel and text exports; missing python-docx and missing PDF converter messages; PDF via LibreOffice; every console command; the database update (asks first, backup, nothing removed), including on a copy of a real old lector.db |
| `tests\test_lector_ui.py` | The window, offscreen: preview matches a saved search; every screen builds; making a search end to end; the builder needs a species and a ticked name; Cancel stops a run; runs show new and withdrawn; a search without recorded filters asks for them; review status, tag and notes kept; names bold, copies and copyright note shown; exports write files and explain missing packages; the update asks first; the window fits 1280 × 720; closing during a run; the Atrium tile, the Lector console button, the launcher |
| `tests\test_lector_r8.py` | The Round 8 fixes L1–L16: Back buttons and menu navigation, Edit on every row, Fetch missing text, filter box, held-back names and the name-choice fix script, tick marks, notes box, per-search run numbers, one-sentence cancel message, request counts, cancelled runs withdraw nothing, scope label, reading-list header, keys 1–4 moving on, empty Excel columns left out, the close-during-run question, the version 3 update |
| `tests\test_review_r8.py` | The review of Round 8: the console keeps a saved search's names and filters (and `--replace-search` replaces them), console export file names, "on your own list", keys working with the page text clicked, "Stop and close" when the run ends while the question is open, the fix script leaving a name you ticked, the dashboard filter matching "Any journal", and the Mapping tab's VC boundaries (Observatum) |
| `tests\test_tier2_apps_20261010.py` | (part of the suite) Atrium's tiles, including Lector, and the Lector console window |

### 9.2 Manual test checklist

Do one section per sitting. Each test says exactly what to do and what you should see.
Write **P** (pass) or **F** (fail) in the Result column and anything odd in Notes.
Tests marked **R8** check the Round 8 fixes.

Before you start: close Lector. Use the real searches (Emus hirtus, Rutpela maculata,
Lamia textor). Some tests make a test search; call it "TEST …" so you can spot it later
(there is no way to delete a saved search from the window yet).

#### A. Setup and opening

| # | Do this | You should see | Result | Notes |
|---|---|---|---|---|
| A1 | PowerShell in the Biological Software folder: `py -3.14 -m pip install python-docx openpyxl` | "Requirement already satisfied" or a successful install | | |
| A2 R8 | Atrium → click the **Lector** tile (the first time after Round 8) | The question "Update lector.db": "activity: - -> 0", no saved searches made, "A backup copy of lector.db is made first. Update now?" Press **Yes** | | |
| A2b | After the update | The Lector window, titled "Lector — Biodiversity Heritage Library", on Saved searches. A message with the backup path `…\data\_backups\lector_pre_v3_….db`. Next time: no question | | |
| A3 | Look at the foot of the left menu | "BHL API key: set" and the path of `lector.db` | | |
| A4 | Atrium → click the **Lector** tile again | The same Lector window comes to the front; no second window | | |
| A5 | Close Lector. Double-click `launchers\run_lector_gui.bat` | Lector opens as in A2; no black console window stays open | | |
| A6 | Close Lector. Atrium → Tools row → **Lector console** | A console window titled "Lector — BHL literature (Atrium)" asking "Species (or Enter to finish):" | | |
| A7 | In that window press Enter on the empty line | "Done. 0 requests." and the window waits for Enter, then closes | | |

#### B. Navigation and Back (R8)

| # | Do this | You should see | Result | Notes |
|---|---|---|---|---|
| B1 R8 | Saved searches → click **Lamia textor** | The search's page, with a **← Back** button at the top left | | |
| B2 R8 | Press **← Back** | Saved searches | | |
| B3 R8 | Open Lamia textor again. Click **Saved searches** in the left menu (already highlighted) | Saved searches | | |
| B4 R8 | Open Lamia textor → **Edit search** → **← Back** | Back on Lamia textor's page | | |
| B5 R8 | Open Lamia textor → **Review new pages** → **← Back** | Back on Lamia textor's page | | |
| B6 R8 | Open Lamia textor → **Export** → **← Back** | Back on Lamia textor's page | | |
| B7 R8 | Left menu → **Reading list**, then **Extracted records**, **Exports**, **Saved searches** | Each screen in turn; the clicked item is highlighted | | |

#### C. Saved searches dashboard

| # | Do this | You should see | Result | Notes |
|---|---|---|---|---|
| C1 | Look at the four cards | Saved searches 3 (or more), Pages harvested, Awaiting review, Records extracted, with figures | | |
| C2 | Look at the Lamia textor row | Name (link), *Lamia textor*, TVK and number of names; Scope; Last run date and number of runs; Pages "of N found"; Reviewed bar "x of y" | | |
| C3 R8 | Look at every row's buttons | Every row has **Edit**. Searches already run also have **Run again** (or **Set filters** if their filters were never recorded), and **Review** if they hold pages; drafts have **Edit** and **Run**; all have **More** | | |
| C4 R8 | Press **Edit** on Lamia textor | Edit search: Lamia textor | | |
| C5 | Back. Click **More** on Lamia textor | Open (runs and changes); Edit names and filters; Count only (no pages downloaded); Fetch missing text (N pages) if any; Duplicate as a new draft; Export a dossier | | |
| C6 R8 | Click **More** on Emus hirtus | "Fetch missing text (N pages)" with N matching Needs attention's "N pages still without text" | | |
| C7 R8 | Click **More** on a search with every page's text | No "Fetch missing text" item at all | | |
| C8 R8 | Look at the filter box | Grey text "Filter your searches…" | | |
| C9 R8 | Type `emus` | Only Emus hirtus is listed, as you type | | |
| C9b | Replace it with `any journal` | Only the searches whose Scope reads "Any journal" | | |
| C10 R8 | Click the small × in the box | Box empty, all searches listed | | |
| C11 R8 | Compare Emus hirtus's Scope column with its page's "Journals" line | The same words in both (e.g. both "Any journal", or both "Your title words (N)"); see 3.3 | | |
| C12 | Read **Recent activity** | Your recent runs and exports, newest first, with dates | | |
| C13 R8 | In Recent activity, find a Lamia textor run | "Run N of “Lamia textor”: …" with Lamia's own number (as in its Runs list), not a shared number | | |
| C14 R8 | Read **Needs attention** | Each "…: N pages still without text." line has a **Fetch now** link | | |
| C15 | Double-click the Rutpela maculata row (not on the name) | Rutpela maculata's page | | |
| C16 | Make the window narrow (drag its edge) | Rows and buttons still fit; the page scrolls rather than cutting off | | |

#### D. New search (builder)

| # | Do this | You should see | Result | Notes |
|---|---|---|---|---|
| D1 | **New search** | "New search", empty species box, names "Find a species first…", Preview dashes | | |
| D2 | Type `lamia  TEXTOR` and press **Find** | "Matched *Lamia textor* · NBNSYS0000011050 · species · Cerambycidae." Search name fills with "Lamia textor" | | |
| D3 | Look at the names | Lamia textor (accepted name) and Cerambyx textor (UKSI synonym) ticked; Lamia rosenmulleri, L. sartor, L. sutor, L. titillator unticked on a pale background, each with a "Held back: …" reason | | |
| D4 R8 | Look at the ticked boxes | Each ticked box shows a clear white tick on the coloured square | | |
| D5 | Tick **Lamia sartor** | Its reason now ends "— ticked by you"; Preview changes | | |
| D6 | Untick it again | Back to the held-back reason only | | |
| D7 | Type `Cerambyx textorius` in "Add a name…" and press **Add name** | A new row "added by you", ticked, with a **Remove** link | | |
| D8 | Press **Remove** on it | The row is gone | | |
| D9 | Look at the Preview | Four figures and an estimate "about … at one request per second (N requests)" | | |
| D10 | Press **Refresh count** | The bottom line shows "Counting names on BHL" with Cancel; afterwards each name shows "N pages" | | |
| D11 | Journal preset → **British periodicals** | Blue chips Entomologist … Proceedings; red chips Canadian … South African; Preview "Within filters" drops | | |
| D12 | Click the **Annals ×** chip | Annals removed; the preset box reads "Your own title words" | | |
| D12b R8 | Preset box → **Any journal** | The blue chips are cleared (red ones stay); Preview "Within filters" rises | | |
| D13 | Type `Annals` in the blue "Add word" box, Enter | Annals chip back; the preset box reads "Your own title words" | | |
| D14 | From year `1800`, To year `1950` | Preview updates | | |
| D15 | Page limit: type `100` | Preview updates | | |
| D16 R8 | Tick **Skip index pages** | A white tick shows; Preview may drop | | |
| D17 | **Save words as a preset** → name `TEST words` → OK | Preset box now reads "TEST words" | | |
| D18 | Search name: `TEST Lamia textor`. Press **Save as draft** | Saved searches, with a new row "TEST Lamia textor", "Draft — not run", buttons Edit, Run, More | | |
| D19 | **New search** → type `Cerambycidae` → **Find** | "Matched Cerambycidae · family · 88 UKSI species, accepted names only." 88 ticked names | | |
| D20 | Press **Cancel** | Back to Saved searches (where you came from); no new row | | |
| D21 | **New search** → type `Lamia nonsuchia` → **Find** | "“Lamia nonsuchia” is not in UKSI — check the spelling." | | |
| D22 | Press **Save and run** with no species found | "Type a species and press Find first." | | |
| D23 | Find Lamia textor, untick every name, press **Save as draft** | "Tick at least one name to search." Press Cancel | | |

#### E. Edit search and held-back names (R8)

| # | Do this | You should see | Result | Notes |
|---|---|---|---|---|
| E0 R8 | Before the fix: Lector → Lamia textor → **Edit search**, then **← Back** without saving | Lamia sartor, L. sutor… ticked, each reason ending "— ticked when lector.db was updated, not by you: untick it unless you want it searched" | | |
| E1 R8 | Close Lector. PowerShell: `py -3.14 scripts\fix_lector_name_choices.py` | "Lamia textor (search N): untick 4 names the update ticked:" then the four names with their reasons, the pages line, and "DRY RUN - Nothing has been changed. Re-run with --apply (Lector closed)." (as in 2.5) | | |
| E2 R8 | If the list is right: `py -3.14 scripts\fix_lector_name_choices.py --apply` | The same list, then "Done. Backup: …\data\_backups\lector_pre_fix_names_….db" | | |
| E3 R8 | Run the dry run again | "No ticked names to change: every search the update made matches the UKSI checks." and "DRY RUN - Nothing has been changed…" | | |
| E4 R8 | Open Lector → Lamia textor → **Edit search** | The four held-back names are listed, **unticked**, each with its reason; no "ticked by you" and no "ticked when lector.db was updated" | | |
| E5 R8 | Open Emus hirtus → **Edit search** | Every name Lector offers for Emus hirtus is listed, held-back ones unticked with reasons | | |
| E6 | In Lamia textor's Edit search, change nothing and press **← Back** | Lamia textor's page; nothing changed | | |
| E7 | Edit search → species box | The species box cannot be changed; Find is greyed out | | |

#### F. A search's page and runs

| # | Do this | You should see | Result | Notes |
|---|---|---|---|---|
| F1 | Open **Lamia textor** | Title, "NBNSYS0000011050 · created … · active"; Names, Years, Journals, Page limit, Left out, Pages held; "Look for newly scanned pages" ticked | | |
| F2 R8 | Read the Runs list | Fetch runs numbered Run 1, Run 2… for this search only; count-only runs unnumbered ("Count only") | | |
| F3 R8 | Read a run's request line | A run made now counts both, e.g. "19 BHL requests (3 name searches, 16 page texts)"; a run made before Round 8 shows only the total ("8 BHL requests") | | |
| F4 R8 | Click the newest run | "What changed in run N" and "Compared with run N-1", using the search's own numbers | | |
| F5 | Read the tabs | New (n), No longer matched (n), Unchanged (n); "Settings changed: …" or "Same settings as the run before." | | |
| F6 | **No longer matched** tab | Withdrawn pages, each with its reason ("Now filtered out (years, journals or index pages)", "Duplicate scan: …", "Over the page limit per name" or "No longer found on BHL for the names searched") and **Keep anyway** | | |
| F7 | Press **Keep anyway** on one | It shows "Kept" | | |
| F8 | Double-click a page in a tab | The Reading list opens on that page, Show = All pages | | |
| F9 | Open **TEST Lamia textor** (draft) | No runs; "No pages fetched yet. Press Run to fetch them."; the run button says **Run** | | |
| F10 | Press **Count only** | Bottom line "Counting “TEST Lamia textor”" with progress; then "Counted: N pages found on BHL, M within the filters; … BHL requests (… name searches, 0 page texts)."; a "Count only" entry in Runs, unnumbered | | |
| F11 | Untick **Look for newly scanned pages**. Press **Run** | It runs without name requests (BHL's last answers); finishes "Run 1 finished: … — N new, 0 no longer matched, M BHL requests (0 name searches, M page texts)." (M = 0 if Lamia textor's pages already have their text) | | |
| F12 | Press **Run again** (box still unticked) | "Run 2 finished: … 0 new, 0 no longer matched, 0 BHL requests (0 name searches, 0 page texts)." | | |
| F13 | **Duplicate** | Edit search for "TEST Lamia textor (copy)" | | |
| F14 | **← Back** to Saved searches, open Lamia textor, press **Export** | Exports with Lamia textor chosen | | |

#### G. Cancel and close (R8)

| # | Do this | You should see | Result | Notes |
|---|---|---|---|---|
| G1 | Open Emus hirtus. Leave "Look for newly scanned pages" ticked. **Run again**, then after 3 seconds **Cancel** (bottom right) | The bottom line says "…: stopping…", then disappears | | |
| G2 R8 | Read the message on the search's page | "Run N cancelled. Whatever was downloaded is kept; running again carries on from there." Nothing in brackets after it | | |
| G3 R8 | Read that run in the Runs list | "(cancelled)" after the date and "0 withdrawn" if you cancelled during the name searches (the bottom line said "Searching BHL for …"). If it was already downloading text, withdrawals are possible and correct (every name had been looked up) | | |
| G4 | Pages held on the dashboard | Unchanged by the cancelled run (no pages lost) | | |
| G5 R8 | Start **Run again** on Emus hirtus. While it runs, close the Lector window (×) | A question: "A run is still going. Stop it and close? Downloaded text is kept." with **Stop and close** (green) and **Keep running** (grey, outlined, the default) | | |
| G6 R8 | Press **Keep running** | The question closes; the run carries on | | |
| G7 R8 | Close the window again → **Stop and close** | The run stops and Lector closes within a few seconds | | |
| G7b R8 | Start **Fetch missing text** on Emus hirtus, close the window, press **Esc** | The question; Esc is "Keep running": the fetch carries on. Then press its **Cancel** | | |
| G8 | Reopen Lector, open Emus hirtus | The last run shows "(cancelled)"; nothing lost | | |

#### H. Fetch missing text (R8)

| # | Do this | You should see | Result | Notes |
|---|---|---|---|---|
| H1 R8 | Note Rutpela maculata's "pages still without text" in Needs attention. Press **Fetch now** on that line | The bottom line "Fetching missing text for “Rutpela maculata”: Downloading page text 1 of N" with progress and Cancel. No "Searching BHL for …" stage | | |
| H2 R8 | Let it finish | Status bar "Text downloaded for N of N pages."; the Needs attention line gone (or smaller if some failed); Recent activity "Fetched missing text, “Rutpela maculata”: N pages, N BHL requests" | | |
| H3 R8 | Open Rutpela maculata | No new run withdrew anything; Pages held unchanged | | |
| H4 R8 | Dashboard → Emus hirtus → **More** → **Fetch missing text (N pages)**; after 5 seconds press **Cancel** | Status bar "Cancelled. Text kept for the n pages downloaded; M still without text."; the count of pages without text has dropped by n; Recent activity ends "(cancelled)" | | |
| H5 R8 | If a search still shows **Set filters** (filters never recorded): **More** → **Fetch missing text** | It works there too | | |

#### I. Reading list

| # | Do this | You should see | Result | Notes |
|---|---|---|---|---|
| I1 R8 | Dashboard → **Review** on Lamia textor | Under the title: "Lamia textor · N entries (M pages, duplicates merged) · x of N reviewed" (79 and 87 on 12 Oct, if unchanged); a **← Back** button | | |
| I2 | Look at the three panes | List on the left grouped by decade; the page in the middle with the name in bold; Review on the right | | |
| I3 R8 | Look at the right pane | A label "Notes" above an outlined text box | | |
| I4 | Show → **All pages**; Order → **By journal** | List grouped by journal title | | |
| I5 | Type `Annals` in the find box | Only matching pages | | |
| I6 | Clear the find box. Click a page in the list. Press **J**, then **K** | Next page, then back | | |
| I6b | Click in the page text (middle), then press **J** | The next page: clicking the page text does not stop the keys | | |
| I7 R8 | Press **1** | The page is marked Relevant (green dot) and the next page is shown | | |
| I8 R8 | Press **K**, then **4** | Back to that page; it is Unreviewed again and the next page is shown | | |
| I9 R8 | Click in the Notes box, type `test 1234 jk` | The text appears in the box; the page does not change and no status changes | | |
| I10 R8 | Wait a second | "Notes saved." | | |
| I11 | Click another page, then come back | The note is still there | | |
| I12 | Delete the note text | "Notes saved." | | |
| I13 | Click **Biology**, then click it again | Tag set ("Biology" in the list row), then cleared | | |
| I14 | Click the **Record extracted (3)** button | Status set; the same page stays shown (only the keys move on) | | |
| I15 | Go back and set it to **Unreviewed (4)** | Restored | | |
| I16 | **Open on BHL** | Your browser opens the page scan | | |
| I17 | **Show full page text**, then **Show excerpts** | The whole OCR text with names bold; then the excerpts | | |
| I18 | Find a page with "+1 scan" | "Same text also at:" with a link | | |
| I19 | Find a page dated 1930 or later (if any) | A yellow note about the rights statement | | |
| I20 | Find a "likely index" page | A blue note "Probably an index or contents page (…)" | | |
| I21 | Show → **No longer matched** | Withdrawn pages, each saying "no longer matched by the filters" | | |
| I22 | Search box → **Emus hirtus**; open a page without text | "The page text has not been downloaded yet: use “Fetch missing text” (the search's More menu on Saved searches, or Fetch now under Needs attention)." | | |

#### J. Exports

| # | Do this | You should see | Result | Notes |
|---|---|---|---|---|
| J1 | Left menu → **Exports**, choose Lamia textor | Options with Word and Excel ticked; Preview with the species and entry count; "Saved to …\data\lector_exports" | | |
| J2 | Untick **Unreviewed** | Preview entry count drops | | |
| J3 | Tick it again. Tick **PDF** and **Plain text bundle**. **Create dossier** | Bottom line "Exporting"; then messages and links DOCX, XLSX, PDF, TXT, CSV | | |
| J4 | Click the DOCX link | Word opens the dossier: front page, Summary, Entries, Appendix A, Appendix B | | |
| J5 R8 | On the front page read "Run" | The search's own run number (e.g. "Run: 2, 2026-10-12"), matching the newest fetch run in the Runs list | | |
| J6 | Click an entry number in the Summary | Word jumps to that entry | | |
| J7 | Click "View page on BHL" in an entry | The page scan opens | | |
| J8 R8 | Open the XLSX | Sheet Index: no Authors or Article title columns (none given by BHL for Lamia's pages). Sheet About: a Note row "Authors and article titles: none given by BHL for these pages" | | |
| J9 R8 | Open the CSV | No authors or article_title columns | | |
| J10 | Open the PDF | A PDF copy of the dossier | | |
| J11 | Order → **By journal, then year**; untick appendices and notes; **Create dossier** | The dossier ends after the entries; no "Your note:" lines; entries by journal | | |
| J12 | Look at **Previous exports** | The files you made, newest first; double-click one opens it | | |
| J13 | **Open folder** | Explorer opens `data\lector_exports` | | |

#### K. Extracted records

| # | Do this | You should see | Result | Notes |
|---|---|---|---|---|
| K1 | Left menu → **Extracted records** | "Coming later" card explaining to mark pages "Record extracted" (key 3) | | |

#### L. Console (tests CO1–CO7)

Run in PowerShell, in the Biological Software folder, with Lector closed.

| # | Do this | You should see | Result | Notes |
|---|---|---|---|---|
| CO1 | `.\launchers\run_lector.bat status` | A table: Species, TVK, Pages, Text, Years for each species | | |
| CO2 | `.\launchers\run_lector.bat synonyms "Lamia textor"` | Lamia textor and its TVK; ✓ Lamia textor, ✓ Cerambyx textor; ✗ the four held-back names with reasons; "Your list: …lector_synonyms.txt" | | |
| CO3 | `.\launchers\run_lector.bat probe "Lamia textor"` | A "Status:" line, "Pages parsed: N", up to 10 pages listed, "Raw JSON written to: …probe_Lamia_textor.json" | | |
| CO1b R8 | Read the line above the table | "Every page ever found per species, withdrawn ones too (the window shows each saved search's own pages)." | | |
| CO4 R8 | `.\launchers\run_lector.bat export --name "Lamia textor" --out data\lector_exports\console_test` | "✓ Lamia textor: N pages → …\console_test\Lamia_textor_all_pages.txt" (every page ever linked to the species); `Lamia_textor_all_pages_index.csv` beside it | | |
| CO5 R8 | `.\launchers\run_lector.bat export --name "Lamia textor" --docx --out data\lector_exports\console_test` | "✓ Lamia textor: N entries (…), … index pages, …" and the Word and Excel paths, `Lamia_textor_all_pages_dossier.docx` and `…_all_pages_dossier_index.xlsx` | | |
| CO6 | `.\launchers\run_lector.bat fetch -h` | The fetch help listing every option | | |
| CO7 | `.\launchers\run_lector.bat nonsense` | An error "invalid choice" and the window pauses | | |
| CO8 R8 | Make `data\lector_exports\console_test\lamia.txt` holding one line `Lamia textor`. Run `.\launchers\run_lector.bat fetch data\lector_exports\console_test\lamia.txt --count-only --include-title Annals` | "Saved search “Lamia textor” kept as it is: …", then "Names: …" (the names ticked in the window), the held-back names with "- ", and "Filters: …" as the window shows them (not "Annals"); "0 requests" if BHL's answers are cached | | |
| CO9 R8 | Open Lector → Lamia textor | A new "Count only" entry in Runs; Names and Journals exactly as before CO8 | | |

(`forget` is not in this list on purpose: it removes review work. `fetch --replace-search`
is not either: it replaces a saved search's names and filters. See 6.3.)

#### M. Laptop size and scaling

| # | Do this | You should see | Result | Notes |
|---|---|---|---|---|
| M1 | Windows display scaling 150 % (or the laptop). Open Lector maximised | Every screen fits; nothing cut off; long screens scroll | | |
| M2 R8 | Saved searches at that size | The row buttons (Edit, Run again, Review, More) fit; Back buttons visible on the other screens | | |
| M3 | Reading list at that size | Three panes visible; the Review pane scrolls if needed | | |
| M4 | Builder at that size | The Preview and save buttons visible (scroll if needed) | | |

#### N. Automated tests

| # | Do this | You should see | Result | Notes |
|---|---|---|---|---|
| N1 | `py -3.14 -m pytest -q tests\test_lector_a.py tests\test_lector_ui.py tests\test_lector_r8.py tests\test_review_r8.py` | "… passed" (a couple skipped is fine), no "failed" | | |
| N2 | `py -3.14 -m pytest -q tests` | "… passed", no "failed" | | |

---

## 10. Glossary

| Word | Meaning |
|---|---|
| **BHL** | Biodiversity Heritage Library: a free online library of scanned natural-history literature, mostly old. Lector uses its API (version 3) |
| **API key** | A free code BHL gives you, which Lector sends with each request |
| **OCR** | Optical character recognition: the text a scanner read off the page image. Often has errors |
| **UKSI** | The UK Species Inventory: the suite's list of UK taxon names, TVKs and synonyms (`data\uksi.db`) |
| **TVK** | Taxon version key: UKSI's 16-character code for a name, e.g. NBNSYS0000011050 for Lamia textor |
| **Synonym** | Another name for the same species, usually older (e.g. Cerambyx textor) |
| **Held back** | A UKSI synonym Lector does not search unless you tick it, because a check suggests UKSI has it wrong, or because it is on the suite corrections list or your own list. The reason is shown |
| **Preset** | A saved list of journal title words (e.g. British periodicals) |
| **Part** | BHL's word for an article it has split out of a volume. Only parts carry authors and article titles; most old journals are not split |
| **Page type** | BHL's label for a page: Text, Index, Table of Contents, Illustration… |
| **Run** | One go of a search: ask BHL, filter, store pages, download text. Numbered within each search |
| **Count only** | A run that only counts pages and stores nothing |
| **Withdrawn / no longer matched** | A page the search held before that a later run no longer keeps. Kept in the database with its notes; can be kept anyway |
| **Kept** | A withdrawn page you chose to keep with "Keep anyway" |
| **Entry** | One text in the reading list or dossier, with duplicate scans merged into it |
| **Page** | One BHL page (one scan). Several pages can make one entry |
| **Duplicate scan** | Another library's scan of the same printed page, or the same text reissued under another title |
| **Index page** | An index, contents list or list of illustrations; goes in Appendix A |
| **Dossier** | The Word document Lector exports, with its Excel index |
| **Rights check** | The reminder on pages from 1930 on to check BHL's copyright statement |

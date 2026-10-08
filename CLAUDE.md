# Biological Software — instructions for Claude

Wil Heeney's desktop suite (Flauna) for invertebrate recording and assessment:
Observatum, Examen, Codex, Curator, Munia, Atrium, Lector, Data Entry.
Python / PySide6 / SQLite, Windows, inside OneDrive. One developer, real client
data, reports issued to Natural England and others. **Correctness of figures
matters more than speed.**

## Where things are

| Need | Look in |
|---|---|
| What exists, folder layout, databases, rebuild chains | `docs/01_Architecture.md` |
| Current figures (the only home for them) | `docs/02_Current_State.md` |
| What to do next — read the top before starting | `docs/03_Backlog.md` |
| Rules learned the hard way | `docs/05_Rules.md` (imported below) |
| Open faults in the area you are touching | `docs/06_Faults.md` |
| Codex / Examen / Data Entry detail | `docs/07`, `08`, `09` |
| Report layer spec (before E3 or E7) | `docs/38_Report_Survey.md` |

`paths.py` is the suite-wide path registry — **never delete, rename or move it**.
Every module does `import paths`.

## Running things

- Python is **`py -3.14`**. Not `python`, not another version.
- Run from the project root with `PYTHONPATH=<root>;<root>\Observatum`, as
  `run.bat` does. Observatum: `run.bat`.
- Scripts: `py -3.14 scripts\<name>.py`. Check scripts say "Nothing has been
  changed" / "READ ONLY" at the end.
- Shell is Windows PowerShell 5.1. Read the PowerShell section of `05_Rules.md`
  before writing any command (no `head`, no `<placeholder>`, quoting in `-c`).

## Safety — non-negotiable

An AI tool has deleted this software before. These rules exist because of that.

1. **Never delete anything.** No `rm`, `Remove-Item`, `del`, `os.remove`,
   `shutil.rmtree`, `unlink`, in any form, in scripts or commands. To retire a
   file, move it to `_archive\<what>_<YYYYMMDD>\` and say so.
2. **Never run** `git clean`, `git reset`, `git restore`, `git checkout -- …`,
   `git stash drop`, `git branch -D`, or any force push. Commit only when Wil
   asks; he pushes.
3. **Databases** (`data\*.db`) are not in git. Their only protection is the
   backup system:
   - Read with `sqlite3.connect(f"file:{path}?mode=ro", uri=True)`.
   - Anything that writes: **dry run first**, show the result, wait for
     "proceed", then back up with `conn.backup()` (never `shutil.copy2`) into
     `C:\BiologicalSoftware_Backups\reference\` with a name saying what it
     precedes. Wil closes the apps first.
   - **Never write to `codex.db` outside its build and import scripts**
     (`build_codex_db.py`, `load_review.py`, `import_status_review.py`,
     `withdraw_statuses.py`, `restore_dropped_statuses.py`, the `clear_*`
     scripts) or Codex Manager. No ad-hoc SQL against Codex.
   - A `DELETE` without `WHERE`, or anything that empties and refills a table,
     needs Wil's explicit agreement.
4. **No `.bak` files.** Git keeps the history of code. One-off data-changing
   scripts go in `scripts\_oneoff\` (git-ignored, archived later).
5. **Don't touch other chats' uncommitted work.** If `git status` shows changes
   you didn't make, leave them and mention them.
6. Confirm understanding before anything destructive or hard to reverse. When in
   doubt, ask.

## Working practice

- **Read the whole method before editing it**, and its imports. Never act on a
  grep hit alone. A filename search returns the 3-line shim and the real file;
  the real one is in `shared\`.
- **Prefer a direct edit** to a patch script. Small change: show the region,
  replace it. Larger: the whole file.
- **Compiling is not importing.** After an edit, import the module (or run the
  thing). After a data change, read the row back.
- **Diagnostic numbers before and after every change.** "It still launches" is
  not proof.
- Python 3.14 doesn't evaluate annotations: check that every name used only in
  an annotation is imported.
- `PRAGMA table_info` before writing a query. Name columns; don't index rows by
  guessed position.
- Any join between Pantheon and anything else goes through `codex.db.tvk_bridge`
  (`pantheon.db` is on 2017 TVKs).
- "Proceed" means continue with the plan as stated.

## The reference check — run it after any change that could move a figure

```
py -3.14 scripts\check_reference_figures.py
```

Compares Codex table counts and every survey's species / key species / SQI
(both bases) against the frozen values in `scripts\reference_figures.json`
(Glory Park SQI 117 matches its issued report). Read-only. Exit 0 = all match.

If a figure moves **on purpose** (a new review, a JNCC or UKSI update), update
`reference_figures.json` and `docs/02_Current_State.md` together, and say why in
the commit. If it moves and you didn't intend it, stop and report.

## Code conventions

1. Design system first
2. Import, don't copy — a rule written twice drifts (the dominant failure here)
3. Single source for constants
4. Files under 400 lines (new code)
5. Consistent patterns
6. No hardcoded colours — use `theme()`

Buttons: primary (Save/Add/Create) `#4a7c59`; navigate/view: tab theme;
cancel/close `#8b8178` outlined; delete `#a63d40` outlined (via `theme()`).

## Documentation

- One fact, one home. Figures live in `02`, work in `03`, faults in `06`, rules
  in `05`.
- Edit in place; no append files. Write what was measured, not what was
  inferred — if something has not been run, say so.
- End of session: update `02` if a figure moved, move backlog items in `03`, add
  faults/rules, a paragraph of history in `02`, then Wil commits.

## Full rules

@docs/05_Rules.md

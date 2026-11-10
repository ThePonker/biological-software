# Building the free-standing Lector

This makes a Lector that runs on a PC with no Python and no Biological Software suite, and an
installer for it. Nothing here has been run yet: it was written on a machine that could not
run PyInstaller or Inno Setup. The first real build may need a small fix (see "If the build
stops" below).

## What you get

- `Lector.exe` and its files, in a folder (PyInstaller "one-folder" build).
- `Lector_Setup_<date>.exe`, an installer for one user (Inno Setup). It installs to
  `AppData\Local\Programs\Lector`, adds a Start menu shortcut, and makes
  `Documents\Lector\data` for the data if that folder is not already there.
- UKSI is **not** included. Lector then searches BHL for the name as typed and says so.

## One-off set-up

1. Python 3.14 (`py -3.14`) is already on your PC.
2. Install Inno Setup 6 from https://jrsoftware.org/isdl.php (free). Skip this if you only want
   the folder, not the installer.

## Build

In PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\path\to\Biological Software\packaging\lector\build_lector.ps1"
```

Use the real path of your suite folder. The script:

1. makes a virtual environment in `%LOCALAPPDATA%\LectorBuild\venv` (outside OneDrive; it is
   reused next time);
2. installs PySide6, python-docx, openpyxl and PyInstaller into it;
3. runs PyInstaller on `lector.spec`. The program folder is
   `%LOCALAPPDATA%\LectorBuild\dist\Lector`;
4. if Inno Setup is installed, runs it on `lector.iss`. The installer is in
   `%LOCALAPPDATA%\LectorBuild\installer`.

It says what it is doing and stops with a message if a step fails. It deletes nothing and
writes nothing inside the suite.

## Try it before installing

Run `%LOCALAPPDATA%\LectorBuild\dist\Lector\Lector.exe`. It should open on the Saved searches
screen, make `Documents\Lector\data\lector.db`, and show the BHL key guide if you have no key
there. The suite's own `data\` folder is not used and not touched.

If your Documents folder is somewhere else, or you want a trial in another place, set the
`LECTOR_DATA_DIR` environment variable to a folder before you start it.

## What goes in, and why

- `lector_entry.py` is what starts the program (the same as `python -m Lector gui`).
- `lector.spec` lists the suite modules Lector uses (`shared\` and the theme in
  `Observatum\src`; several are imported inside functions, so they are named), and the data
  files it needs: `scripts\uksi_synonym_corrections.csv`, python-docx's document template.
- The suite's `paths.py` is left out on purpose. `Lector\config.py` makes a stand-in when it
  runs frozen, pointing at `Documents\Lector\data`.
- Qt parts Lector does not use (web view, 3D, QML...) are left out to keep the folder small.

## If the build stops

- *"Hidden import not found"* or a `ModuleNotFoundError` when you run `Lector.exe`: add the
  module's name to `SHARED` or `hidden` in `lector.spec`, and build again. PyInstaller prints
  the warnings in `%LOCALAPPDATA%\LectorBuild\build\lector\warn-lector.txt`.
- The window opens with no styling or a missing plug-in: PySide6 may need `--collect-all
  PySide6` style hooks; PyInstaller 6.x normally finds them by itself.
- A crash with no window: look in `Documents\Lector\data\logs` for `crash_lector_<month>.log`.
- Antivirus flags the new `.exe`: one-folder PyInstaller builds are sometimes flagged. Build on
  your own PC and, if needed, allow the folder.

## Checking the path logic without building

The tests in `tests\test_lector_round15b.py` check, with a pretend "frozen" program, that
Lector picks `Documents\Lector\data`, that `LECTOR_DATA_DIR` overrides it, and that the program
works with no `uksi.db`. They cannot check PyInstaller or Inno Setup themselves.

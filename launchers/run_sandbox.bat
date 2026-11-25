@echo off
rem Observatum on a SANDBOX copy of the data, never the live data (25 Nov 2026).
rem Make the copy first:  py -3.14 scripts\make_sandbox.py --apply
rem BIOSOFT_ROOT makes paths.py use <sandbox>\data; BIOSOFT_BACKUP_ROOT keeps backups there too.
cd /d "%~dp0\.."
if not exist "paths.py" (
    echo ERROR: paths.py is missing from the project root.
    pause
    exit /b 1
)
set "SANDBOX=C:\BiologicalSoftware_Sandbox"
if defined BIOSOFT_SANDBOX_DIR set "SANDBOX=%BIOSOFT_SANDBOX_DIR%"
if not exist "%SANDBOX%\data\observatum.db" (
    echo No sandbox found at %SANDBOX%\data. Make one first:
    echo     py -3.14 scripts\make_sandbox.py --apply
    pause
    exit /b 1
)
set "BIOSOFT_ROOT=%SANDBOX%"
set "BIOSOFT_SANDBOX=1"
rem no away-mode copy is ever made from a sandbox
set "BIOSOFT_NO_AWAY_COPY=1"
set "BIOSOFT_BACKUP_ROOT=%SANDBOX%\backups"
rem Photos: an empty sandbox library, so a commit in the sandbox never files your real photos.
set "BIOSOFT_MEDIA_ROOT=%SANDBOX%\Media"
set "PYTHONPATH=%CD%;%CD%\Observatum"
if not defined PYTHONPYCACHEPREFIX set "PYTHONPYCACHEPREFIX=%LOCALAPPDATA%\BiologicalSoftware\pycache"
echo SANDBOX: using the copy in %SANDBOX% (your live data is not touched).
py -3.14 -m src.main %*

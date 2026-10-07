@echo off
REM Standalone launcher for the DataEntry widget (development).
REM Auto-runs against the newest data\observatum_dev_*.db (see DataEntry\__main__.py),
REM so it never opens the live database by accident. Console kept visible on purpose
REM during development; switch to pythonw for a clean standalone window later.
cd /d "%~dp0.."
set PYTHONPATH=%CD%;%CD%\Observatum
py -3.14 -m DataEntry %*

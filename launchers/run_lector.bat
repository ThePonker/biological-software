@echo off
REM Lector -- BHL harvester. Usage: launchers\run_lector.bat probe "Lamia textor"
cd /d "%~dp0.."
set PYTHONPATH=%CD%;%CD%\Observatum
py -3.14 -m Lector %*

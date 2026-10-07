@echo off
REM Lector - BHL harvester. Keep this file next to the Lector folder.
REM Usage: run_lector.bat probe "Lamia textor"   /   run_lector.bat fetch species.txt --synonyms
cd /d "%~dp0"
set PYTHONPATH=%~dp0;%PYTHONPATH%
if "%~1"=="" (
    python -m Lector --help
    pause
    exit /b
)
python -m Lector %*

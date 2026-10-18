@echo off
cd /d "%~dp0\.."
if not exist "paths.py" (
    echo ERROR: paths.py is missing from the project root.
    pause
    exit /b 1
)
set "PYTHONPATH=%CD%;%CD%\Observatum"
py -3.14 -m shared.away_mode %*

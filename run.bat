@echo off
cd /d "%~dp0"
if not exist "paths.py" (
    echo ERROR: paths.py is missing from the project root.
    echo This file is required for all Biological Software tools.
    echo Restore from backup or contact the developer.
    pause
    exit /b 1
)
set "PYTHONPATH=%CD%;%CD%\Observatum"
py -3.14 -m src.main

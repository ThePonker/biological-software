@echo off
cd /d "%~dp0\.."
set PYTHONPATH=%CD%
echo.
echo ========================================
echo BIOLOGICAL SOFTWARE - RESET INSECT COLLECTION
echo ========================================
echo.
python scripts/reset_insect_collection.py %*
pause

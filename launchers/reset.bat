@echo off
cd /d "%~dp0\.."
set PYTHONPATH=%CD%
echo.
echo ========================================
echo BIOLOGICAL SOFTWARE - DATABASE RESET
echo ========================================
echo.
echo This will DELETE all data and create empty tables.
echo.
python scripts/reset_database.py %*
pause

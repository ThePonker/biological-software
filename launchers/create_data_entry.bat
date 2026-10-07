@echo off
cd /d "%~dp0\.."
set PYTHONPATH=%CD%;%CD%\Observatum
echo.
echo ========================================
echo TABELLA - CREATE FIELD ENTRY WORKBOOK
echo ========================================
echo.
py -3.14 -m Tabella.create_data_entry_workbook %*
pause

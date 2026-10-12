@echo off
REM Lector window (saved searches, reading list, exports). Console mode: run_lector.bat
cd /d "%~dp0\.."
set PYTHONPATH=%CD%;%CD%\Observatum
start "" pyw -3.14 -m Lector gui

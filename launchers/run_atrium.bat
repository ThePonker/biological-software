@echo off
cd /d "%~dp0\.."
set PYTHONPATH=%CD%;%CD%\Observatum
start "" pyw -3.14 -m Atrium

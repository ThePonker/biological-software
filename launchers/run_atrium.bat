@echo off
cd /d "%~dp0\.."
set PYTHONPATH=%CD%;%CD%\Observatum
if not defined PYTHONPYCACHEPREFIX set "PYTHONPYCACHEPREFIX=%LOCALAPPDATA%\BiologicalSoftware\pycache"
start "" pyw -3.14 -m Atrium

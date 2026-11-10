@echo off
title Examen
cd /d "%~dp0\.."
set PYTHONPATH=%CD%;%CD%\Observatum
if not defined PYTHONPYCACHEPREFIX set "PYTHONPYCACHEPREFIX=%LOCALAPPDATA%\BiologicalSoftware\pycache"
py -3.14 -m Examen
pause

@echo off
cd /d "%~dp0\.."
set PYTHONPATH=%CD%
if not defined PYTHONPYCACHEPREFIX set "PYTHONPYCACHEPREFIX=%LOCALAPPDATA%\BiologicalSoftware\pycache"
py -3.14 -m Curator

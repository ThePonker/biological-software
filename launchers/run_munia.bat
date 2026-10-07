@echo off
cd /d "%~dp0\.."
set PYTHONPATH=%CD%;%CD%\Observatum
py -3.14 -m Munia
pause

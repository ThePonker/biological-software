@echo off
REM Lector -- BHL harvester. Usage: launchers\run_lector.bat probe "Lamia textor"
cd /d "%~dp0.."
set PYTHONPATH=%CD%;%CD%\Observatum
py -3.14 -m Lector %*
set "RC=%ERRORLEVEL%"
REM Keep the window open if anything fails, so the message can be read.
if not "%RC%"=="0" pause
exit /b %RC%

@echo off
cd /d "%~dp0\.."
set PYTHONPATH=%CD%
echo.
echo ========================================
echo BIOLOGICAL SOFTWARE - RESET RECORDING SCHEME
echo ========================================
echo.
py -3.14 scripts/reset_recording_scheme.py %*
pause

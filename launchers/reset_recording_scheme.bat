@echo off
cd /d "%~dp0\.."
set PYTHONPATH=%CD%
echo.
echo ========================================
echo BIOLOGICAL SOFTWARE - RESET RECORDING SCHEME
echo ========================================
echo.
python scripts/reset_recording_scheme.py %*
pause

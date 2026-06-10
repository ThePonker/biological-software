@echo off
cd /d "%~dp0\.."
set PYTHONPATH=%CD%
echo.
echo ========================================
echo BIOLOGICAL SOFTWARE - RESET OBSERVATIONS
echo ========================================
echo.
python scripts/reset_observations.py %*
pause

@echo off
cd /d "%~dp0\.."
set PYTHONPATH=%CD%
echo.
echo ========================================
echo BIOLOGICAL SOFTWARE - RESET OBSERVATIONS
echo ========================================
echo.
py -3.14 scripts/reset_observations.py %*
pause

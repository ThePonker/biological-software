@echo off
cd /d "%~dp0\.."
set PYTHONPATH=%CD%
REM Observatum V2 - Mark iRecord Commercial Data
echo.
echo ========================================
echo OBSERVATUM V2 - MARK iRECORD COMMERCIAL
echo ========================================
echo.
py -3.14 scripts/mark_irecord_commercial.py %*
pause

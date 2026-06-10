@echo off
cd /d "%~dp0\.."
set PYTHONPATH=%CD%
python -m Curator

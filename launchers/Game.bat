@echo off
cd /d "%~dp0\.."
set PYTHONPATH=%CD%;%CD%\Observatum
python Observatum\src\features\gamification\game_launcher.py

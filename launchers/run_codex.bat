@echo off
title Codex Manager
cd /d "%~dp0\.."
set PYTHONPATH=%CD%;%CD%\Observatum
python -m Codex

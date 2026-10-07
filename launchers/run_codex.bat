@echo off
title Codex Manager
cd /d "%~dp0\.."
set PYTHONPATH=%CD%;%CD%\Observatum
py -3.14 -m Codex

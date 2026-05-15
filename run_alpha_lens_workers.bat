@echo off
REM Run the Alpha Lens background worker process from the repository root.
cd /d "%~dp0"
python backend/app.py --workers-only

@echo off
cd /d "%~dp0"
python -m app.gui
if errorlevel 1 pause

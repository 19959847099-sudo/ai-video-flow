@echo off
cd /d "%~dp0"
python -m app.preparation_gui
if errorlevel 1 pause

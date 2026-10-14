@echo off
cd /d "%~dp0"
uv run --locked --group gui -m cambridge_audio.gui
if errorlevel 1 pause

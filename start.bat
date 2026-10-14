@echo off
cd /d "%~dp0"
uv run --locked -m cambridge_audio %*
pause

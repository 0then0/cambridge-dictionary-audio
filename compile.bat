@echo off
cd /d "%~dp0"
uv sync --locked --group gui --group release
if errorlevel 1 exit /b 1
echo Build FFmpeg first in an MSYS2 UCRT64 shell: .venv/Scripts/python.exe scripts/build_ffmpeg.py
uv run --locked --group gui --group release python scripts\build_desktop.py
if errorlevel 1 exit /b 1
uv run --locked --group gui --group release python scripts\package_desktop.py

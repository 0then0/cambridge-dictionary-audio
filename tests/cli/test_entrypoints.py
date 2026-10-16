"""Exercise real process startup after moving the application into a package."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("entrypoint", [("-m", "cambridge_audio"), ("main.py",)])
@pytest.mark.parametrize("language, heading", [("en", "Options:"), ("ru", "Параметры:")])
def test_package_and_compatibility_launchers(entrypoint, language, heading):
    result = subprocess.run(
        [sys.executable, *entrypoint, "--lang", language, "--help"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert heading in result.stdout
    assert "--accent {us,uk,both}" in result.stdout

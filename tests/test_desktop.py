"""Source launches retain their environment and native macOS identity."""

import os
import plistlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cambridge_audio import desktop


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_other_platforms_do_not_create_a_bundle(tmp_path, monkeypatch, platform):
    monkeypatch.setattr(desktop.sys, "platform", platform)
    assert desktop.launch_macos_bundle(tmp_path) is None
    assert not list(tmp_path.iterdir())


def test_macos_bundle_preserves_environment_and_exit_status(tmp_path, monkeypatch):
    interpreter = tmp_path / "venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"interpreter")
    dependencies = tmp_path / "venv" / "lib" / "site-packages"
    monkeypatch.setattr(desktop.sys, "platform", "darwin")
    monkeypatch.setattr(desktop.sys, "executable", str(interpreter))
    monkeypatch.setattr(desktop.sys, "path", ["", str(dependencies)])
    monkeypatch.setattr(desktop.sys, "argv", ["gui.py", "-platform", "offscreen"])
    monkeypatch.setenv("CAMBRIDGE_TEST_ENV", "retained")
    run = Mock(return_value=SimpleNamespace(returncode=7))
    monkeypatch.setattr(desktop.subprocess, "run", run)

    assert desktop.launch_macos_bundle(tmp_path / "cache") == 7
    command = run.call_args.args[0]
    launcher = Path(command[0])
    assert launcher.is_symlink()
    assert launcher.samefile(interpreter)
    metadata = plistlib.loads((launcher.parent.parent / "Info.plist").read_bytes())
    assert metadata["CFBundleName"] == desktop.APPLICATION_NAME
    assert metadata["CFBundleExecutable"] == launcher.name
    assert command[1:] == ["-m", "cambridge_audio.gui", "-platform", "offscreen"]
    environment = run.call_args.kwargs["env"]
    assert environment["CAMBRIDGE_TEST_ENV"] == "retained"
    assert environment["PYTHONPATH"].split(os.pathsep) == [str(Path.cwd()), str(dependencies)]


def test_bundle_child_and_packaged_app_do_not_relaunch(tmp_path, monkeypatch):
    monkeypatch.setattr(desktop.sys, "platform", "darwin")
    monkeypatch.setattr(
        desktop.sys, "executable", str(tmp_path / "Audio.app" / "Contents" / "MacOS" / "Audio")
    )
    assert desktop.launch_macos_bundle(tmp_path / "cache") is None
    monkeypatch.setattr(desktop.sys, "executable", "/usr/bin/python3")
    monkeypatch.setattr(desktop.sys, "frozen", True, raising=False)
    assert desktop.launch_macos_bundle(tmp_path / "cache") is None
    assert not (tmp_path / "cache").exists()

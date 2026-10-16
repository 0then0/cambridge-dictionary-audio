"""Terminal preferences survive restart without sharing GUI state or session flags."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cambridge_audio.terminal import Options
from cambridge_audio.terminal import settings as terminal_settings
from cambridge_audio.terminal.settings import settings_path as platform_settings_path


def test_settings_roundtrip_preserves_unicode_and_only_persistent_preferences(
    tmp_path, isolated_terminal_settings
):
    options = Options(
        tmp_path / "Аудиозаписи",
        language="ru",
        accent="both",
        play=False,
        combine=False,
        translation="russian",
        timeout=3,
        overwrite=True,
        offline=True,
        dictionary_dir=tmp_path / "dictionary",
    )
    terminal_settings.save_settings(options, "cambridge-light")
    assert terminal_settings.load_settings() == {
        "directory": options.directory,
        "language": "ru",
        "accent": "both",
        "play": False,
        "combine": False,
        "translation": "russian",
        "theme": "cambridge-light",
    }
    assert "Аудиозаписи" in isolated_terminal_settings.read_text(encoding="utf-8")
    assert not options.directory.exists()


@pytest.mark.parametrize("content", [b"{", b"[]", b"null", b"123", b"\xff"])
def test_corrupt_settings_fall_back_to_defaults(isolated_terminal_settings, content):
    isolated_terminal_settings.parent.mkdir(parents=True)
    isolated_terminal_settings.write_bytes(content)
    assert terminal_settings.load_settings() == {}


def test_missing_settings_do_not_create_files(isolated_terminal_settings):
    assert terminal_settings.load_settings() == {}
    assert not isolated_terminal_settings.parent.exists()


def test_invalid_fields_are_ignored_independently(isolated_terminal_settings):
    isolated_terminal_settings.parent.mkdir(parents=True)
    isolated_terminal_settings.write_text(
        json.dumps(
            {
                "language": ["ru"],
                "accent": "both",
                "theme": "unknown",
                "play": "false",
                "combine": 1,
                "translation": "french",
                "directory": "relative",
                "overwrite": True,
            }
        ),
        encoding="utf-8",
    )
    assert terminal_settings.load_settings() == {"accent": "both"}


def test_failed_atomic_save_preserves_previous_settings_and_removes_temp_file(
    tmp_path, isolated_terminal_settings, monkeypatch
):
    options = Options(tmp_path)
    terminal_settings.save_settings(options, "cambridge-dark")
    previous = isolated_terminal_settings.read_bytes()
    monkeypatch.setattr(
        terminal_settings,
        "os",
        SimpleNamespace(replace=Mock(side_effect=PermissionError("read only"))),
    )
    with pytest.raises(PermissionError):
        terminal_settings.save_settings(options, "cambridge-light")
    assert isolated_terminal_settings.read_bytes() == previous
    assert list(isolated_terminal_settings.parent.iterdir()) == [isolated_terminal_settings]


@pytest.mark.parametrize("platform,root", [("win32", "roaming"), ("linux", "config")])
def test_platform_config_directory_respects_environment(tmp_path, monkeypatch, platform, root):
    monkeypatch.setattr(terminal_settings, "sys", SimpleNamespace(platform=platform))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    assert (
        platform_settings_path() == tmp_path / root / "cambridge-dictionary-audio/tui-settings.json"
    )

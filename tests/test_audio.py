from pathlib import Path
from unittest.mock import Mock

import pytest

from cambridge_audio import audio
from cambridge_audio.dictionary import AudioNotFoundError, CambridgeError


def test_phrase_requires_ffmpeg(monkeypatch, client, tmp_path):
    monkeypatch.setattr(audio, "ffmpeg_executable", lambda: None)
    with pytest.raises(CambridgeError, match="FFmpeg"):
        audio.combine_phrase(client, "hello world", "uk", tmp_path / "phrase.mp3")
    client.session.get.assert_not_called()


def test_missing_word_prevents_partial_phrase_and_cleans_temporary_files(monkeypatch, tmp_path):
    monkeypatch.setattr(audio.shutil, "which", lambda name: "ffmpeg")
    client = Mock()
    client.lookup.side_effect = [(), AudioNotFoundError("missing word")]
    paths = []

    def download(entries, accent, destination):
        paths.append(destination)
        destination.write_bytes(b"ID3first word")

    client.download.side_effect = download
    unrelated = tmp_path / "hello.mp3"
    unrelated.write_bytes(b"existing recording")
    with pytest.raises(AudioNotFoundError):
        audio.combine_phrase(client, "hello missing", "uk", tmp_path / "phrase.mp3")
    assert unrelated.read_bytes() == b"existing recording"
    assert not (tmp_path / "phrase.mp3").exists()
    assert paths and not paths[0].parent.exists()


def test_synthesis_publishes_audio_and_cleans_temporary_files(monkeypatch, tmp_path, mp3):
    monkeypatch.setattr(audio.shutil, "which", lambda name: "ffmpeg")
    client = Mock()
    paths = []

    def download(entries, accent, destination):
        paths.append(destination)
        destination.write_bytes(mp3)

    def run(command, **kwargs):
        assert command[0] == "ffmpeg"
        assert (paths[0].parent / "inputs.txt").read_text() == "file '0.mp3'\nfile '1.mp3'\n"
        Path(command[-1]).write_bytes(mp3)

    client.download.side_effect = download
    monkeypatch.setattr(audio.subprocess, "run", run)
    destination = tmp_path / "phrase.mp3"
    audio.combine_phrase(client, "hello world", "us", destination)
    assert destination.read_bytes() == mp3
    assert not paths[0].parent.exists()


@pytest.mark.parametrize("platform", ["win32", "darwin", "linux"])
def test_platform_playback_uses_absolute_path_without_shell(monkeypatch, platform, tmp_path):
    path = tmp_path / "folder with spaces" / "hello.us.mp3"
    monkeypatch.setattr(audio.sys, "platform", platform)
    opener = Mock()
    runner = Mock()
    monkeypatch.setattr(audio.os, "startfile", opener, raising=False)
    monkeypatch.setattr(audio.subprocess, "run", runner)
    monkeypatch.setattr(audio.shutil, "which", lambda name: name)
    audio.play_audio(path)
    if platform == "win32":
        opener.assert_called_once_with(str(path.resolve()))
        runner.assert_not_called()
    else:
        command = runner.call_args.args[0]
        assert command[0] == ("afplay" if platform == "darwin" else "ffplay")
        assert command[-1] == str(path.resolve())
        assert runner.call_args.kwargs == {"check": True}


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_terminal_player_stops_child_and_keeps_output_out_of_terminal(
    monkeypatch, platform, tmp_path
):
    import sys
    from threading import Event, Thread

    original_popen = audio.subprocess.Popen
    started = Event()
    stop = Event()
    children = []
    errors = []

    def launch(command, **kwargs):
        assert command[0] == ("afplay" if platform == "darwin" else "ffplay")
        assert kwargs["stdout"] == kwargs["stderr"] == audio.subprocess.DEVNULL
        child = original_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
        children.append(child)
        started.set()
        return child

    def play():
        try:
            audio.play_audio(tmp_path / "hello.us.mp3", stop=stop)
        except Exception as exc:
            errors.append(exc)

    monkeypatch.setattr(audio.sys, "platform", platform)
    monkeypatch.setattr(audio.shutil, "which", lambda name: name)
    monkeypatch.setattr(audio.subprocess, "Popen", launch)
    thread = Thread(target=play)
    thread.start()
    try:
        assert started.wait(5)
    finally:
        stop.set()
        thread.join(5)
    assert not thread.is_alive()
    assert not errors
    assert children[0].poll() is not None


def test_finder_launch_can_find_homebrew_ffmpeg(tmp_path, monkeypatch):
    monkeypatch.setattr(audio.sys, "platform", "darwin")
    monkeypatch.setattr(audio.shutil, "which", lambda name: None)
    monkeypatch.setattr(audio, "_MACOS_FFMPEG_DIRS", (tmp_path,))
    executable = tmp_path / "ffmpeg"
    executable.write_text("#!/bin/sh\n")
    executable.chmod(0o755)
    assert audio.ffmpeg_executable() == str(executable)
    executable.chmod(0o644)
    assert audio.ffmpeg_executable() is None


def test_ffmpeg_from_path_takes_priority_over_homebrew(tmp_path, monkeypatch):
    monkeypatch.setattr(audio.sys, "platform", "darwin")
    monkeypatch.setattr(audio.shutil, "which", lambda name: "/custom/bin/ffmpeg")
    monkeypatch.setattr(audio, "_MACOS_FFMPEG_DIRS", (tmp_path,))
    assert audio.ffmpeg_executable() == "/custom/bin/ffmpeg"


@pytest.mark.parametrize(
    "platform,filename", [("darwin", "ffmpeg"), ("linux", "ffmpeg"), ("win32", "ffmpeg.exe")]
)
def test_frozen_app_uses_its_ffmpeg_before_path(tmp_path, monkeypatch, platform, filename):
    monkeypatch.setattr(audio.sys, "platform", platform)
    monkeypatch.setattr(audio.sys, "frozen", True, raising=False)
    monkeypatch.setattr(audio.sys, "_MEIPASS", str(tmp_path), raising=False)
    tools = tmp_path / "tools"
    tools.mkdir()
    binary = tools / filename
    binary.write_bytes(b"binary")
    binary.chmod(0o755)
    monkeypatch.setattr(audio.shutil, "which", lambda name: "/external/ffmpeg")
    assert audio.ffmpeg_executable() == str(binary)


def test_python_cli_ignores_bundled_binary(tmp_path, monkeypatch):
    monkeypatch.setattr(audio.sys, "frozen", False, raising=False)
    monkeypatch.setattr(audio.sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(audio.shutil, "which", lambda name: "/external/ffmpeg")
    assert audio.ffmpeg_executable() == "/external/ffmpeg"

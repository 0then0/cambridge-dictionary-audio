"""Phrase synthesis and playback through system audio tools."""

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from .dictionary import CambridgeClient, CambridgeError, normalize_word, save_mp3
from .i18n import translate

_MACOS_FFMPEG_DIRS = (Path("/opt/homebrew/bin"), Path("/usr/local/bin"))


def ffmpeg_executable() -> str | None:
    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        bundled = root / "tools" / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
        if bundled.is_file() and os.access(bundled, os.X_OK):
            return str(bundled)
    executable = shutil.which("ffmpeg")
    if executable or sys.platform != "darwin":
        return executable
    # Finder launches do not inherit the shell's Homebrew PATH.
    for directory in _MACOS_FFMPEG_DIRS:
        candidate = directory / "ffmpeg"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def combine_phrase(
    client: CambridgeClient,
    phrase: str,
    accent: str,
    destination: Path,
    *,
    overwrite: bool = False,
    check_cancelled: Callable[[], None] | None = None,
) -> Path:
    words = normalize_word(phrase, client.language).split()
    if len(words) < 2:
        raise CambridgeError(
            translate("Combining requires a phrase with at least two words.", client.language)
        )
    ffmpeg = ffmpeg_executable()
    if ffmpeg is None:
        raise CambridgeError(
            translate("Install FFmpeg and add it to PATH to combine a phrase.", client.language)
        )
    if destination.exists() and not overwrite:
        raise FileExistsError(
            translate(
                "File already exists: {path}. Use --overwrite to replace it.",
                client.language,
                path=destination,
            )
        )
    with TemporaryDirectory(prefix="cambridge-audio-") as directory:
        temporary = Path(directory)
        for index, word in enumerate(words):
            if check_cancelled:
                check_cancelled()
            client.download(client.lookup(word), accent, temporary / f"{index}.mp3")
        manifest = temporary / "inputs.txt"
        manifest.write_text(
            "".join(f"file '{index}.mp3'\n" for index in range(len(words))), encoding="utf-8"
        )
        output = temporary / "combined.mp3"
        if check_cancelled:
            check_cancelled()
        try:
            subprocess.run(
                [
                    ffmpeg,
                    "-nostdin",
                    "-loglevel",
                    "error",
                    "-f",
                    "concat",
                    "-safe",
                    "1",
                    "-i",
                    str(manifest),
                    "-af",
                    "loudnorm",
                    "-c:a",
                    "libmp3lame",
                    str(output),
                ],
                check=True,
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                if sys.platform == "win32"
                else 0,
            )
        except subprocess.CalledProcessError as exc:
            raise CambridgeError(f"FFmpeg: {exc.stderr.decode(errors='replace').strip()}") from exc
        return save_mp3(
            output.read_bytes(), destination, overwrite=overwrite, language=client.language
        )


def play_audio(path: Path, language: str = "en", *, stop: Event | None = None) -> None:
    path = path.resolve()
    if sys.platform == "win32":
        os.startfile(str(path))
        return
    player = shutil.which("afplay" if sys.platform == "darwin" else "ffplay")
    if player is None:
        raise CambridgeError(
            translate(
                "Audio player not found: afplay (macOS) or ffplay (Linux) is required.", language
            )
        )
    command = [player, str(path)]
    if sys.platform != "darwin":
        command = [player, "-nodisp", "-autoexit", "-loglevel", "error", str(path)]
    if stop is not None:
        if stop.is_set():
            return
        # A terminal workspace owns its player so it can stop it on request or quit.
        # Keep child output away from the terminal's alternate screen.
        with subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ) as process:
            try:
                while not stop.is_set():
                    try:
                        code = process.wait(timeout=0.1)
                    except subprocess.TimeoutExpired:
                        continue
                    if code:
                        raise CambridgeError(
                            translate("Could not play {path}.", language, path=path)
                        )
                    return
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
        return
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise CambridgeError(translate("Could not play {path}.", language, path=path)) from exc

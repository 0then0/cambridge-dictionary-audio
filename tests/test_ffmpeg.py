"""Optional local integration test: real MP3 encoding, combining and probing."""

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from cambridge_audio.audio import combine_phrase


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg and ffprobe are required for the audio integration test",
)
def test_real_ffmpeg_combines_valid_mp3_without_losing_words(client, tmp_path):
    source = tmp_path / "source.mp3"
    subprocess.run(
        [
            shutil.which("ffmpeg"),
            "-nostdin",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.3",
            "-c:a",
            "libmp3lame",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    paths = []

    def download(entries, accent, destination):
        paths.append(destination)
        destination.write_bytes(source.read_bytes())

    client.lookup = Mock(return_value=())
    client.download = Mock(side_effect=download)
    destination = tmp_path / "nested folder" / "hello world.us.mp3"
    combine_phrase(client, "hello world", "us", destination)

    def probe(path: Path):
        result = subprocess.run(
            [
                shutil.which("ffprobe"),
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name:format=duration",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    original = probe(source)
    combined = probe(destination)
    assert combined["streams"][0]["codec_name"] == "mp3"
    duration = float(combined["format"]["duration"])
    assert 1.5 * float(original["format"]["duration"]) < duration
    assert duration < 2.5 * float(original["format"]["duration"])
    assert len(paths) == 2 and all(not path.parent.exists() for path in paths)

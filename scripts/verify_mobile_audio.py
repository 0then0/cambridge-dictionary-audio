"""Exercise the shared C codec with real MP3 decoding and frame-order assertions."""

import argparse
import ctypes
import json
import math
import struct
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def verify(library: Path, destination: Path):
    codec = ctypes.CDLL(str(library.resolve()))
    function = codec.cda_encode_phrase
    function.argtypes = [ctypes.POINTER(ctypes.c_float), ctypes.c_size_t, ctypes.c_char_p]
    function.restype = ctypes.c_int
    with TemporaryDirectory(prefix="cambridge-codec-") as temporary:
        folder = Path(temporary)
        decoded = []
        for index, frequency in enumerate((440, 880)):
            mp3 = folder / f"{index}.mp3"
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    f"sine=frequency={frequency}:duration=0.5",
                    "-c:a",
                    "libmp3lame",
                    str(mp3),
                ],
                check=True,
            )
            data = subprocess.check_output(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-i",
                    str(mp3),
                    "-f",
                    "f32le",
                    "-ar",
                    "44100",
                    "-ac",
                    "1",
                    "-",
                ]
            )
            decoded.extend(struct.unpack("<" + "f" * (len(data) // 4), data))
        pcm = (ctypes.c_float * len(decoded))(*decoded)
        destination.parent.mkdir(parents=True, exist_ok=True)
        assert function(pcm, len(decoded), str(destination).encode()) == 0
        info = json.loads(
            subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(destination)]
            )
        )
        assert info["streams"][0]["codec_name"] == "mp3"
        result = subprocess.check_output(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(destination),
                "-f",
                "f32le",
                "-ar",
                "44100",
                "-ac",
                "1",
                "-",
            ]
        )
        frames = struct.unpack("<" + "f" * (len(result) // 4), result)
        assert 0.95 < len(frames) / 44100 < 1.1
        # Compare spectral energy in the middle of each segment after MP3 delay.
        energies = []
        for start in (int(0.15 * 44100), int(0.65 * 44100)):
            window = frames[start : start + 4096]
            power = [
                sum(
                    value * math.cos(2 * math.pi * freq * i / 44100)
                    for i, value in enumerate(window)
                )
                ** 2
                + sum(
                    value * math.sin(2 * math.pi * freq * i / 44100)
                    for i, value in enumerate(window)
                )
                ** 2
                for freq in (440, 880)
            ]
            energies.append(power)
        assert energies[0][0] > energies[0][1] * 100
        assert energies[1][1] > energies[1][0] * 100
        assert max(map(abs, frames)) < 1
        report = {
            "codec": "mp3",
            "sample_rate": 44100,
            "frames": len(frames),
            "duration": len(frames) / 44100,
            "segment_order": [440, 880],
            "verified": "host C encoder and real MP3 decode; platform decoders separate",
        }
        destination.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    verify(args.library, args.destination)

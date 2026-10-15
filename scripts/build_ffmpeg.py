"""Build the audio-only LGPL FFmpeg executable and matching source distribution."""

import hashlib
import json
import os
import platform
import shutil
import struct
import subprocess
import sys
import tarfile
import urllib.request
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "packaging/ffmpeg-sources.json"


def download(source: dict, directory: Path) -> Path:
    name = source["url"].rsplit("/", 1)[-1]
    path = directory / name
    if not path.exists():
        with urllib.request.urlopen(source["url"], timeout=60) as response:
            data = response.read()
        path.write_bytes(data)
    if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError(f"Source checksum mismatch: {name}")
    return path


def configure_path(path: Path) -> str:
    if sys.platform == "win32":
        return subprocess.check_output(["cygpath", "-u", str(path)], text=True).strip()
    return str(path)


def configure_shell() -> str:
    if sys.platform == "win32":
        # Windows searches System32 before PATH and may otherwise launch WSL's bash.exe.
        return subprocess.check_output(["cygpath", "-w", "/usr/bin/bash"], text=True).strip()
    return "bash"


def verify(executable: Path):
    """Exercise exactly the concat/loudnorm/MP3 pipeline used by the application."""
    report = subprocess.check_output([str(executable), "-hide_banner", "-version"], text=True)
    license_text = subprocess.check_output([str(executable), "-hide_banner", "-L"], text=True)
    if "GNU Lesser General Public License" not in " ".join(license_text.split()):
        raise RuntimeError("The bundled FFmpeg must be LGPL, without GPL or nonfree components")
    if "--enable-gpl" in report or "--enable-nonfree" in report:
        raise RuntimeError("GPL/nonfree FFmpeg builds cannot be bundled")
    with TemporaryDirectory(prefix="cambridge-ffmpeg-test-") as directory:
        temporary = Path(directory)
        wav = temporary / "input.wav"
        with wave.open(str(wav), "wb") as stream:
            stream.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
            stream.writeframes(b"".join(struct.pack("<h", (i % 100) * 100) for i in range(4410)))
        first = temporary / "first.mp3"
        subprocess.run(
            [
                str(executable),
                "-nostdin",
                "-loglevel",
                "error",
                "-i",
                str(wav),
                "-c:a",
                "libmp3lame",
                str(first),
            ],
            check=True,
        )
        manifest = temporary / "inputs.txt"
        manifest.write_text("file 'first.mp3'\nfile 'first.mp3'\n", encoding="utf-8")
        result = temporary / "combined.mp3"
        subprocess.run(
            [
                str(executable),
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
                str(result),
            ],
            check=True,
        )
        if result.stat().st_size < 100:
            raise RuntimeError("Bundled FFmpeg produced empty audio")
        subprocess.run(
            [
                str(executable),
                "-nostdin",
                "-loglevel",
                "error",
                "-i",
                str(result),
                "-f",
                "null",
                "-",
            ],
            check=True,
        )
    return report


def main():
    pkg_config = shutil.which("pkg-config") or shutil.which("pkgconf")
    if not pkg_config:
        raise RuntimeError("Building LAME requires pkg-config (pkgconf)")
    sources = json.loads(MANIFEST.read_text(encoding="utf-8"))
    downloads = ROOT / "build/ffmpeg-downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    archives = {name: download(source, downloads) for name, source in sources.items()}
    workspace = ROOT / "build/ffmpeg-build"
    # This directory contains only generated third-party build files.
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    trees = {}
    for name, archive in archives.items():
        with tarfile.open(archive) as stream:
            stream.extractall(workspace, filter="data")
        trees[name] = workspace / f"{name}-{sources[name]['version']}"
    prefix = workspace / "prefix"
    prefix.mkdir()
    environment = os.environ.copy()
    environment["PKG_CONFIG"] = configure_path(Path(pkg_config))
    environment["CFLAGS"] = "-O2"
    environment["LC_ALL"] = "C"
    system = {"darwin": "macos", "win32": "windows", "linux": "linux"}[sys.platform]
    architecture = platform.machine().lower().replace("amd64", "x86_64")
    target = f"{system}-{architecture}"
    if sys.platform == "darwin":
        environment["MACOSX_DEPLOYMENT_TARGET"] = "14.0"
    commands = []

    def run(command, cwd):
        commands.append({"cwd": str(cwd.relative_to(workspace)), "argv": command})
        subprocess.run(command, cwd=cwd, env=environment, check=True)

    install_prefix = configure_path(prefix)
    shell = configure_shell()
    run(
        [
            shell,
            "./configure",
            f"--prefix={install_prefix}",
            "--disable-frontend",
            "--disable-decoder",
            "--disable-shared",
            "--enable-static",
            "--with-pic",
        ],
        trees["lame"],
    )
    jobs = str(min(8, os.cpu_count() or 2))
    run(["make", f"-j{jobs}"], trees["lame"])
    run(["make", "install"], trees["lame"])
    flags = [
        "--disable-everything",
        "--disable-autodetect",
        "--disable-gpl",
        "--disable-nonfree",
        "--disable-shared",
        "--enable-static",
        "--disable-doc",
        "--disable-debug",
        "--disable-network",
        "--disable-avdevice",
        "--disable-swscale",
        "--disable-x86asm",
        "--disable-ffplay",
        "--disable-ffprobe",
        "--enable-ffmpeg",
        "--enable-small",
        "--enable-libmp3lame",
        "--enable-protocol=file",
        "--enable-parser=mpegaudio",
        "--enable-decoder=mp3,mp3float,pcm_s16le",
        "--enable-demuxer=mp3,concat,wav",
        "--enable-muxer=mp3,wav,null",
        "--enable-encoder=libmp3lame,pcm_s16le",
        "--enable-filter=loudnorm,aresample,aformat,anull,atrim",
        f"--extra-cflags=-I{install_prefix}/include",
        f"--extra-ldflags=-L{install_prefix}/lib",
    ]
    if sys.platform == "win32":
        flags += [
            "--extra-ldexeflags=-static -static-libgcc",
            "--disable-pthreads",
            "--enable-w32threads",
        ]
    run([shell, "./configure", *flags], trees["ffmpeg"])
    run(["make", f"-j{jobs}"], trees["ffmpeg"])
    filename = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    output = ROOT / "build/bundled-ffmpeg"
    output.mkdir(parents=True, exist_ok=True)
    executable = output / filename
    shutil.copy2(trees["ffmpeg"] / filename, executable)
    version_report = verify(executable)
    (output / "VERSION.txt").write_text(version_report, encoding="utf-8")
    for name, tree in trees.items():
        for source in tree.glob("COPYING*"):
            shutil.copy2(source, output / f"{name}-{source.name}")
    (output / "NOTICE.txt").write_text(
        f"FFmpeg {sources['ffmpeg']['version']} and LAME {sources['lame']['version']}\n"
        "This executable uses LGPL components, without GPL or nonfree components.\n"
        "Corresponding sources and build parameters accompany the application release\n"
        "in ffmpeg-lame-sources-<platform>-<architecture>.tar.gz.\n"
        "FFmpeg: https://ffmpeg.org/\nLAME: https://lame.sourceforge.io/\n",
        encoding="utf-8",
    )
    recipe = {
        "target": target,
        "environment": {
            key: environment[key]
            for key in ("CFLAGS", "LC_ALL", "MACOSX_DEPLOYMENT_TARGET")
            if key in environment
        },
        "commands": commands,
    }
    (output / "BUILD.json").write_text(json.dumps(recipe, indent=2) + "\n", encoding="utf-8")
    # Keep original, unmodified source archives and the exact build recipe together.
    destination = ROOT / "dist/installers"
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(destination / f"ffmpeg-lame-sources-{target}.tar.gz", "w:gz") as stream:
        for archive in archives.values():
            stream.add(archive, arcname=f"build/ffmpeg-downloads/{archive.name}")
        stream.add(MANIFEST, arcname="packaging/ffmpeg-sources.json")
        stream.add(Path(__file__), arcname="scripts/build_ffmpeg.py")
        stream.add(ROOT / "packaging/ffmpeg-build.md", arcname="packaging/ffmpeg-build.md")
        stream.add(ROOT / "packaging/ffmpeg-build.md", arcname="README.md")
        for source in output.iterdir():
            if source.name != filename:
                stream.add(source, arcname=source.name)
    print(f"Bundled FFmpeg verified: {executable}", flush=True)


if __name__ == "__main__":
    main()

"""Validate versions, CLI distributions, native startup and release checksums."""

import argparse
import hashlib
import importlib.metadata
import os
import subprocess
import sys
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path
from tempfile import TemporaryDirectory

from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
GUI_PATHS = {"cambridge_audio/gui", "cambridge_audio/desktop.py"}
CLI_MODULES = {
    "__init__.py",
    "__main__.py",
    "audio.py",
    "cli.py",
    "dictionary.py",
    "errors.py",
    "i18n.py",
    "service.py",
    "library.py",
    "terminal/__init__.py",
    "terminal/app.py",
    "terminal/app.tcss",
    "terminal/dialogs.py",
    "terminal/messages.py",
    "terminal/rendering.py",
    "terminal/settings.py",
    "console.py",
    "translations.py",
    "wikdict.py",
    "anki.py",
}


def validate():
    version = importlib.metadata.version("cambridge-dictionary-audio")
    parsed = Version(version)
    if parsed.local is not None:
        raise ValueError("Local versions cannot be published to PyPI")
    if os.environ.get("GITHUB_REF_TYPE") == "tag":
        if os.environ["GITHUB_REF_NAME"] != f"v{version}":
            raise ValueError(f"The release tag must match project.version: v{version}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"version={version}\n")
            stream.write(f"prerelease={str(parsed.is_prerelease).lower()}\n")
    print(version)


def verify_python(directory: Path):
    wheels = list(directory.glob("*.whl"))
    sources = list(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise ValueError("Expected exactly one CLI wheel and one source distribution")
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
        modules = {
            name.removeprefix("cambridge_audio/")
            for name in names
            if name.startswith("cambridge_audio/") and not name.endswith("/")
        }
        if modules != CLI_MODULES:
            raise ValueError(f"Unexpected wheel modules: {modules}")
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        metadata = BytesParser().parsebytes(archive.read(metadata_name))
        if any("pyside" in value.lower() for value in metadata.get_all("Requires-Dist", [])):
            raise ValueError("Qt dependencies must not appear in the CLI distribution")
        if metadata.get_all("Provides-Extra"):
            raise ValueError("The CLI distribution must not expose a GUI extra")
        entries = archive.read(metadata_name.replace("METADATA", "entry_points.txt")).decode()
        if "cambridge-audio = cambridge_audio.cli:main" not in entries:
            raise ValueError("Missing CLI entry point")
        for name in ("LICENSE", "LICENSE-MIT", "NOTICE"):
            if not any(value.endswith(f"/licenses/{name}") for value in names):
                raise ValueError(f"Missing {name} in wheel")
    with tarfile.open(sources[0]) as archive:
        names = archive.getnames()
        relative = {"/".join(Path(name).parts[1:]) for name in names}
        if any(path == gui or path.startswith(gui + "/") for path in relative for gui in GUI_PATHS):
            raise ValueError("The source distribution must contain CLI code only")
        if any("assets/" in name for name in names):
            raise ValueError("GUI assets must not appear in the CLI source distribution")
    print("CLI wheel and sdist contents verified")


def smoke():
    name = "Cambridge Dictionary Audio"
    if sys.platform == "darwin":
        executable = ROOT / "dist/desktop" / f"{name}.app/Contents/MacOS" / name
    else:
        executable = (
            ROOT / "dist/desktop" / name / (name + (".exe" if sys.platform == "win32" else ""))
        )
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["PATH"] = ""
    with TemporaryDirectory(prefix="cambridge-frozen-check-") as directory:
        # An unrelated working directory catches resource paths that depend on cwd.
        subprocess.run(
            [str(executable), "--smoke-test"],
            cwd=directory,
            env=environment,
            check=True,
            timeout=60,
        )
    print("Frozen GUI startup, icons and bundled phrase synthesis verified")


def checksums(directory: Path):
    paths = sorted(p for p in directory.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt")
    if not paths:
        raise ValueError("No release artifacts found")
    lines = []
    for path in paths:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        lines.append(f"{digest.hexdigest()}  {path.name}")
    (directory / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("validate", "verify-python", "smoke", "checksums"))
    parser.add_argument("directory", nargs="?", type=Path)
    args = parser.parse_args()
    if args.command in {"verify-python", "checksums"} and args.directory is None:
        parser.error("directory is required")
    if args.command == "validate":
        validate()
    elif args.command == "verify-python":
        verify_python(args.directory)
    elif args.command == "smoke":
        smoke()
    else:
        checksums(args.directory)


if __name__ == "__main__":
    main()

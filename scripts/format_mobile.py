"""Pinned mobile formatters: check without writes, or explicitly format sources."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
TOOLS = ROOT / "build/format-tools"
CONFIG = json.loads((MOBILE / "formatters.json").read_text(encoding="utf-8"))
GENERATED = {
    MOBILE / "shared/src/commonMain/kotlin/org/cambridgeaudio/core/AnkiContract.kt",
    MOBILE / "androidApp/src/main/java/org/cambridgeaudio/app/Locales.kt",
    MOBILE / "iosApp/CambridgeAudio/Locales.swift",
}


def sources(language):
    if language == "kotlin":
        files = list(MOBILE.glob("*.gradle.kts"))
        for module in ("shared", "androidApp"):
            files.append(MOBILE / module / "build.gradle.kts")
            files.extend((MOBILE / module / "src").rglob("*.kt"))
            files.extend((MOBILE / module / "src").rglob("*.kts"))
    else:
        files = []
        for target in ("CambridgeAudio", "CambridgeAudioTests", "CambridgeAudioUITests"):
            files.extend((MOBILE / "iosApp" / target).rglob("*.swift"))
    return sorted(p for p in set(files) if p not in GENERATED and not p.is_symlink())


def download(tool, filename):
    TOOLS.mkdir(parents=True, exist_ok=True)
    path = TOOLS / filename
    if not path.exists():
        temporary = path.with_suffix(".download")
        try:
            print(f"Downloading {tool['url']}", flush=True)
            with urllib.request.urlopen(tool["url"], timeout=60) as response:
                with temporary.open("wb") as stream:
                    shutil.copyfileobj(response, stream)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != tool["sha256"]:
                raise ValueError(f"Formatter SHA-256 mismatch: {filename}")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    if hashlib.sha256(path.read_bytes()).hexdigest() != tool["sha256"]:
        raise ValueError(f"Cached formatter SHA-256 mismatch; remove {path}")
    return path


def swift_formatter():
    tool = CONFIG["swift-format"]
    archive = download(tool, f"swift-format-{tool['version']}.tar.gz")
    package = TOOLS / f"swift-format-{tool['version']}"
    if not package.exists():
        with tarfile.open(archive) as source:
            source.extractall(TOOLS, filter="data")
    lock = MOBILE / "swift-format.resolved"
    resolved = package / "Package.resolved"
    binary = package / ".build/release/swift-format"
    if not binary.exists() or not resolved.exists() or resolved.read_bytes() != lock.read_bytes():
        shutil.copyfile(lock, resolved)
        env = os.environ.copy()
        env["CLANG_MODULE_CACHE_PATH"] = str(TOOLS / "clang-cache")
        subprocess.run(
            [
                "swift",
                "build",
                "--package-path",
                str(package),
                "--cache-path",
                str(TOOLS / "swift-cache"),
                "--config-path",
                str(TOOLS / "swift-config"),
                "--security-path",
                str(TOOLS / "swift-security"),
                "--disable-sandbox",
                "--force-resolved-versions",
                "--configuration",
                "release",
                "--product",
                "swift-format",
                "--jobs",
                "2",
                "-Xswiftc",
                "-module-cache-path",
                "-Xswiftc",
                str(TOOLS / "swift-module-cache"),
            ],
            cwd=ROOT,
            env=env,
            check=True,
        )
    version = subprocess.check_output([str(binary), "--version"], text=True).strip()
    if version != tool["version"]:
        raise ValueError(f"Expected swift-format {tool['version']}, got {version}")
    return binary


def run(language, mode):
    files = sources(language)
    if not files:
        raise ValueError(f"No {language} sources found")
    if language == "kotlin":
        tool = CONFIG["ktfmt"]
        jar = download(tool, f"ktfmt-{tool['version']}.jar")
        command = ["java", "-jar", str(jar), f"--{tool['style']}-style", "--enable-editorconfig"]
        if mode == "check":
            command += ["--dry-run", "--set-exit-if-changed"]
    else:
        command = [str(swift_formatter())]
        command += ["lint", "--strict"] if mode == "check" else ["format", "--in-place"]
        command += ["--configuration", str(MOBILE / ".swift-format")]
    print(f"{mode}: {language}, {len(files)} files", flush=True)
    return subprocess.run(command + [str(p) for p in files], cwd=ROOT).returncode


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("mode", choices=["check", "format"])
    parser.add_argument("--language", choices=["all", "kotlin", "swift"], default="all")
    args = parser.parse_args()
    languages = ("kotlin", "swift") if args.language == "all" else (args.language,)
    codes = [run(language, args.mode) for language in languages]
    raise SystemExit(1 if any(codes) else 0)


if __name__ == "__main__":
    main()

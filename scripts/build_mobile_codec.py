"""Build pinned LGPL LAME for mobile. No binary wrapper or FFmpegKit dependency."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/mobile-codec"
SOURCE = json.loads((ROOT / "packaging/ffmpeg-sources.json").read_text())["lame"]


def run(args, *, cwd=None, env=None):
    subprocess.run([str(a) for a in args], cwd=cwd, env=env, check=True)


def source_tree():
    downloads = BUILD / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    archive = downloads / SOURCE["url"].rsplit("/", 1)[-1]
    if not archive.exists():
        old = ROOT / "build/ffmpeg-downloads" / archive.name
        if old.exists():
            shutil.copyfile(old, archive)
        else:
            with urllib.request.urlopen(SOURCE["url"], timeout=60) as response:
                archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SOURCE["sha256"]:
        raise ValueError("LAME source checksum mismatch")
    source = BUILD / "source" / f"lame-{SOURCE['version']}"
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as package:
            package.extractall(source.parent, filter="data")
    return source


def build(target, sdk):
    source = source_tree()
    prefix = BUILD / target
    work = BUILD / (target + "-work")
    work.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["CFLAGS"] = "-O2 -fPIC -fno-lto"
    args = [
        source / "configure",
        f"--prefix={prefix}",
        "--disable-shared",
        "--enable-static",
        "--disable-frontend",
        "--disable-decoder",
        "--disable-gtktest",
        "--disable-nasm",
    ]
    if target.startswith("android-"):
        abi = target.removeprefix("android-")
        triples = {
            "arm64-v8a": ("aarch64-linux-android", "aarch64-linux-android"),
            "armeabi-v7a": ("armv7a-linux-androideabi", "arm-linux-androideabi"),
            "x86_64": ("x86_64-linux-android", "x86_64-linux-android"),
        }
        triple, host = triples[abi]
        ndk = sdk / "ndk/28.2.13676358/toolchains/llvm/prebuilt/darwin-x86_64"
        if sys.platform != "darwin":
            ndk = sdk / "ndk/28.2.13676358/toolchains/llvm/prebuilt/linux-x86_64"
        env.update(
            CC=str(ndk / f"bin/{triple}28-clang"),
            AR=str(ndk / "bin/llvm-ar"),
            RANLIB=str(ndk / "bin/llvm-ranlib"),
        )
        args += [f"--host={host}"]
    elif target.startswith("ios-"):
        arch, sdkname = {
            "ios-arm64": ("arm64", "iphoneos"),
            "ios-simulator-arm64": ("arm64", "iphonesimulator"),
            "ios-simulator-x86_64": ("x86_64", "iphonesimulator"),
        }[target]
        sdkroot = subprocess.check_output(
            ["xcrun", "--sdk", sdkname, "--show-sdk-path"], text=True
        ).strip()
        env["CC"] = subprocess.check_output(
            ["xcrun", "--sdk", sdkname, "--find", "clang"], text=True
        ).strip()
        minimum = (
            "-mios-simulator-version-min=17.0"
            if "simulator" in target
            else "-miphoneos-version-min=17.0"
        )
        env["CFLAGS"] += f" -arch {arch} -isysroot {sdkroot} {minimum}"
        env["LDFLAGS"] = env["CFLAGS"]
        args += [f"--host={'aarch64' if arch == 'arm64' else arch}-apple-darwin"]
    elif target != "host":
        raise ValueError(f"Unknown target {target}")
    run(args, cwd=work, env=env)
    run(["make", "-j4"], cwd=work, env=env)
    run(["make", "install"], cwd=work, env=env)
    (prefix / "build-materials.json").write_text(
        json.dumps(
            {
                "source": SOURCE,
                "target": target,
                "configure": [str(a) for a in args],
                "cflags": env["CFLAGS"],
                "cc": env.get("CC", "cc"),
                "linkage": "static LGPL library; full application sources supplied for relinking",
            },
            indent=2,
        )
        + "\n"
    )
    return prefix


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument(
        "target",
        choices=[
            "host",
            "android-arm64-v8a",
            "android-armeabi-v7a",
            "android-x86_64",
            "ios-arm64",
            "ios-simulator-arm64",
            "ios-simulator-x86_64",
        ],
    )
    parser.add_argument(
        "--sdk",
        type=Path,
        default=Path(os.environ.get("ANDROID_HOME", ROOT / "build/mobile-tools/sdk")),
    )
    args = parser.parse_args()
    build(args.target, args.sdk.absolute())

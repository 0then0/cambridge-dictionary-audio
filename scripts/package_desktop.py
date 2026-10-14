"""Wrap a frozen GUI in native installers and portable archives."""

import importlib.metadata
import platform
import plistlib
import shlex
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
NAME = "Cambridge Dictionary Audio"
PACKAGE = "cambridge-dictionary-audio"
OUTPUT = ROOT / "dist/installers"


def run(*command):
    subprocess.run([str(value) for value in command], cwd=ROOT, check=True)


def archive(source: Path, destination: Path):
    with tarfile.open(destination, "w:gz") as stream:
        stream.add(source, arcname=source.name)


def reset_staging(path: Path):
    """Discard only generated staging files, including links from previous builds."""
    if path.is_symlink():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def macos(version: Version):
    architecture = platform.machine().lower()
    app = ROOT / "dist/desktop" / f"{NAME}.app"
    base = OUTPUT / f"{PACKAGE}-{version}-macos-{architecture}"
    numeric = ".".join(str(value) for value in (*version.release, 0, 0)[:3])
    package_root = ROOT / "build/macos-root"
    reset_staging(package_root)
    shutil.copytree(app, package_root / app.name, symlinks=True)
    components = ROOT / "build/macos-components.plist"
    run("pkgbuild", "--analyze", "--root", package_root, components)
    entries = plistlib.loads(components.read_bytes())
    for entry in entries:
        # Source launches also have cached app bundles; never relocate an install there.
        entry["BundleIsRelocatable"] = False
    components.write_bytes(plistlib.dumps(entries))
    run(
        "pkgbuild",
        "--root",
        package_root,
        "--component-plist",
        components,
        "--install-location",
        "/Applications",
        "--identifier",
        "org.cambridgeaudio.desktop",
        "--version",
        numeric,
        "--ownership",
        "recommended",
        str(base) + ".pkg",
    )
    staging = ROOT / "build/dmg"
    reset_staging(staging)
    shutil.copytree(app, staging / app.name, symlinks=True)
    applications = staging / "Applications"
    if not applications.is_symlink():
        applications.symlink_to("/Applications", target_is_directory=True)
    run(
        "hdiutil",
        "create",
        "-volname",
        NAME,
        "-srcfolder",
        staging,
        "-ov",
        "-format",
        "UDZO",
        str(base) + ".dmg",
    )
    archive(app, Path(str(base) + ".tar.gz"))


def windows(version: Version):
    compiler = shutil.which("iscc")
    if not compiler:
        for directory in ("C:/Program Files (x86)/Inno Setup 6", "C:/Program Files/Inno Setup 7"):
            candidate = Path(directory) / "ISCC.exe"
            if candidate.exists():
                compiler = str(candidate)
                break
    if not compiler:
        raise RuntimeError("Inno Setup compiler ISCC.exe was not found")
    source = ROOT / "dist/desktop" / NAME
    numeric = ".".join(str(value) for value in (*version.release, 0, 0, 0)[:4])
    run(
        compiler,
        f"/DAppVersion={version}",
        f"/DNumericVersion={numeric}",
        f"/DSourceDir={source}",
        f"/DOutputDir={OUTPUT}",
        ROOT / "packaging/windows.iss",
    )
    shutil.make_archive(
        str(OUTPUT / f"{PACKAGE}-{version}-windows-x86_64-portable"),
        "zip",
        source.parent,
        source.name,
    )


def linux_version(version: Version) -> str:
    value = ".".join(map(str, version.release))
    if version.pre:
        value += "~" + "".join(map(str, version.pre))
    if version.dev is not None:
        value += f"~dev{version.dev}"
    if version.post is not None:
        value += f"+post{version.post}"
    return value


def linux(version: Version):
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("Linux release packaging currently targets x86_64")
    payload = ROOT / "build/linux-root"
    reset_staging(payload)
    shutil.copytree(
        ROOT / "dist/desktop" / NAME, payload / "opt" / PACKAGE, symlinks=True, dirs_exist_ok=True
    )
    launcher = payload / "usr/bin/cambridge-audio-gui"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(f'#!/bin/sh\nexec "/opt/{PACKAGE}/{NAME}" "$@"\n', encoding="utf-8")
    launcher.chmod(0o755)
    for source, relative in (
        (ROOT / "packaging/linux.desktop", f"usr/share/applications/{PACKAGE}.desktop"),
        (ROOT / "assets/icon.svg", f"usr/share/icons/hicolor/scalable/apps/{PACKAGE}.svg"),
        (ROOT / "build/icon.png", f"usr/share/icons/hicolor/256x256/apps/{PACKAGE}.png"),
    ):
        destination = payload / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    control = payload / "DEBIAN/control"
    control.parent.mkdir(exist_ok=True)
    dependencies = (
        "libc6 (>= 2.34), libegl1, libopengl0, libgl1, libpulse0, libxkbcommon0, "
        "libxkbcommon-x11-0, libxcb1, libxcb-cursor0, libxcb-icccm4, libxcb-image0, "
        "libxcb-keysyms1, libxcb-render-util0, libxcb-xinerama0, libdbus-1-3"
    )
    size = sum(p.stat().st_size for p in payload.rglob("*") if p.is_file()) // 1024
    control.write_text(
        f"Package: {PACKAGE}\nVersion: {linux_version(version)}\nArchitecture: amd64\n"
        "Maintainer: 0then0 <0then0@users.noreply.github.com>\n"
        "Section: education\nPriority: optional\n"
        f"Homepage: https://github.com/0then0/{PACKAGE}\n"
        f"Depends: {dependencies}\nInstalled-Size: {size}\n"
        "Description: Cambridge Dictionary pronunciation downloader\n"
        " Download and listen to US and UK pronunciation recordings.\n",
        encoding="utf-8",
    )
    run(
        "dpkg-deb",
        "--build",
        "--root-owner-group",
        payload,
        OUTPUT / f"{PACKAGE}_{version}_amd64.deb",
    )
    control.unlink()
    control.parent.rmdir()
    rpmroot = ROOT / "build/rpm"
    for directory in ("BUILD", "BUILDROOT", "RPMS", "SOURCES", "SPECS", "SRPMS"):
        (rpmroot / directory).mkdir(parents=True, exist_ok=True)
    spec = rpmroot / "SPECS/desktop.spec"
    spec.write_text(
        f"""
Name: {PACKAGE}
Version: {linux_version(version)}
Release: 1
Summary: Cambridge Dictionary pronunciation downloader
License: Apache-2.0 AND MIT AND LGPL-2.1-or-later AND LGPL-3.0-only
URL: https://github.com/0then0/{PACKAGE}
BuildArch: x86_64
AutoReqProv: no
Requires: glibc >= 2.34
Requires: libEGL.so.1()(64bit), libOpenGL.so.0()(64bit), libGL.so.1()(64bit)
Requires: libpulse.so.0()(64bit), libxkbcommon.so.0()(64bit), libxkbcommon-x11.so.0()(64bit)
Requires: libxcb.so.1()(64bit), libxcb-cursor.so.0()(64bit), libdbus-1.so.3()(64bit)
Requires: libxcb-icccm.so.4()(64bit), libxcb-image.so.0()(64bit), libxcb-keysyms.so.1()(64bit)
Requires: libxcb-render-util.so.0()(64bit), libxcb-xinerama.so.0()(64bit)
%description
Download and listen to US and UK pronunciation recordings.
%install
mkdir -p %{{buildroot}}
cp -a {shlex.quote(str(payload))}/. "%{{buildroot}}/"
%files
/opt/{PACKAGE}
/usr/bin/cambridge-audio-gui
/usr/share/applications/{PACKAGE}.desktop
/usr/share/icons/hicolor/scalable/apps/{PACKAGE}.svg
/usr/share/icons/hicolor/256x256/apps/{PACKAGE}.png
""",
        encoding="utf-8",
    )
    run(
        "rpmbuild",
        "--define",
        f"_topdir {rpmroot}",
        "--define",
        "__os_install_post %{nil}",
        "-bb",
        spec,
    )
    for path in (rpmroot / "RPMS").rglob("*.rpm"):
        shutil.copy2(path, OUTPUT / path.name)
    archive(
        ROOT / "dist/desktop" / NAME, OUTPUT / f"{PACKAGE}-{version}-linux-x86_64-portable.tar.gz"
    )


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    version = Version(importlib.metadata.version(PACKAGE))
    {"darwin": macos, "win32": windows, "linux": linux}[sys.platform](version)


if __name__ == "__main__":
    main()

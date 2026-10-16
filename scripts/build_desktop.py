"""Build a native onedir GUI bundle with the locked release environment."""

import importlib.metadata
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
NAME = "Cambridge Dictionary Audio"


def run(*command):
    subprocess.run([str(value) for value in command], cwd=ROOT, check=True)


def render_icons():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    app = QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(str(ROOT / "assets/icon.svg"))
    if not renderer.isValid():
        raise RuntimeError("Invalid application SVG")
    iconset = ROOT / "build/icon.iconset"
    iconset.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 64, 128, 256, 512, 1024):
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        if size == 256:
            image.save(str(ROOT / "build/icon.png"))
        for logical, scale in ((size, 1), (size // 2, 2)):
            if logical in (16, 32, 128, 256, 512):
                suffix = "@2x" if scale == 2 else ""
                if not image.save(str(iconset / f"icon_{logical}x{logical}{suffix}.png")):
                    raise RuntimeError("Could not render application icon")
    del app
    if sys.platform == "darwin":
        run("iconutil", "-c", "icns", "-o", ROOT / "build/icon.icns", iconset)


def collect_licenses() -> Path:
    destination = ROOT / "build/third-party-licenses"
    destination.mkdir(parents=True, exist_ok=True)
    runtime = (
        "genanki",
        "cached-property",
        "chevron",
        "frozendict",
        "pyyaml",
        "beautifulsoup4",
        "soupsieve",
        "typing-extensions",
        "requests",
        "certifi",
        "charset-normalizer",
        "idna",
        "urllib3",
        "pyside6-essentials",
        "pyside6-addons",
        "shiboken6",
        "pyinstaller",
    )
    report = []
    for name in runtime:
        distribution = importlib.metadata.distribution(name)
        report.append(f"{name} {distribution.version}")
        for path in distribution.files or []:
            if path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE", "AUTHORS")):
                source = Path(distribution.locate_file(path))
                if source.is_file():
                    target = destination / name / str(path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    for source in (ROOT / "packaging/licenses").iterdir():
        shutil.copy2(source, destination / source.name)
    python_license = (
        Path(sys.base_prefix)
        / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/LICENSE.txt"
    )
    if python_license.exists():
        shutil.copy2(python_license, destination / "PYTHON-LICENSE.txt")
    qt_version = importlib.metadata.version("pyside6-essentials")
    report.extend(
        [
            "",
            f"Python {platform.python_version()}: https://www.python.org/downloads/source/",
            f"Qt/PySide6 {qt_version}: https://download.qt.io/official_releases/QtForPython/",
            "Qt sources: https://download.qt.io/official_releases/qt/"
            f"{qt_version.rsplit('.', 1)[0]}/{qt_version}/single/",
            "Qt/PySide6 are distributed under LGPLv3, "
            "with shared libraries kept separately replaceable.",
            "Third-party components bundled by Qt retain their own licenses:",
            "https://doc.qt.io/qt-6/licenses-used-in-qt.html",
            "FFmpeg: https://ffmpeg.org/legal.html",
        ]
    )
    (destination / "COMPONENTS.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    return destination


def main():
    version = Version(importlib.metadata.version("cambridge-dictionary-audio"))
    render_icons()
    licenses = collect_licenses()
    ffmpeg_root = ROOT / "build/bundled-ffmpeg"
    ffmpeg = ffmpeg_root / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    if not ffmpeg.is_file():
        raise RuntimeError("Build the bundled FFmpeg first: python scripts/build_ffmpeg.py")
    for path in ffmpeg_root.iterdir():
        if path != ffmpeg:
            target = licenses / "ffmpeg" / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    icon = ROOT / ("build/icon.icns" if sys.platform == "darwin" else "assets/icon.ico")
    if sys.platform == "linux":
        icon = ROOT / "build/icon.png"
    numeric = ".".join(str(value) for value in (*version.release, 0, 0)[:3])
    spec = f"""
from PyInstaller.utils.hooks import copy_metadata

a = Analysis([{str(ROOT / "scripts/desktop_entry.py")!r}],
    pathex=[{str(ROOT)!r}],
    datas=[*copy_metadata('cambridge-dictionary-audio'),
           ({str(ROOT / "assets")!r}, 'assets'),
           ({str(licenses)!r}, 'licenses/third-party'),
           *[({str(ROOT)!r} + '/' + name, 'licenses')
             for name in ('LICENSE', 'LICENSE-MIT', 'NOTICE')]],
    binaries=[({str(ffmpeg)!r}, 'tools')],
    hiddenimports=['PySide6.QtSvg'],
    excludes=['tkinter', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtPdf'],
    noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name={NAME!r},
          console=False, strip=False, upx=False, icon={str(icon)!r})
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name={NAME!r})
"""
    if sys.platform == "darwin":
        spec += f"""
bundle = BUNDLE(collection, name={NAME + ".app"!r}, icon={str(icon)!r},
    bundle_identifier='org.cambridgeaudio.desktop',
    info_plist={{'CFBundleName': {NAME!r}, 'CFBundleDisplayName': {NAME!r},
                'CFBundleShortVersionString': {numeric!r}, 'CFBundleVersion': {numeric!r},
                'LSMinimumSystemVersion': '14.0', 'NSHighResolutionCapable': True}})
"""
    spec_path = ROOT / "build/desktop.spec"
    spec_path.write_text(spec, encoding="utf-8")
    run(
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        ROOT / "dist/desktop",
        "--workpath",
        ROOT / "build/pyinstaller",
        spec_path,
    )


if __name__ == "__main__":
    main()

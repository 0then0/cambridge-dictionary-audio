"""Native application identity for GUI launches from a Python environment."""

import hashlib
import os
import plistlib
import subprocess
import sys
from pathlib import Path

APPLICATION_NAME = "Cambridge Dictionary Audio"


def launch_macos_bundle(cache_dir: Path) -> int | None:
    """Run source launches in an app bundle so Dock identifies the app, not Python.

    The bundle only links the current interpreter. PYTHONPATH preserves the
    caller's environment, including virtualenv dependencies, after relaunching.
    Packaged applications already have a bundle and need no wrapper.
    """
    if sys.platform != "darwin" or getattr(sys, "frozen", False):
        return None
    executable = Path(sys.executable)
    if executable.parent.name == "MacOS" and executable.parent.parent.parent.suffix == ".app":
        return None

    identity = hashlib.sha256(
        f"{Path(__file__).resolve().parent}:{executable}".encode()
    ).hexdigest()[:16]
    contents = cache_dir / identity / f"{APPLICATION_NAME}.app" / "Contents"
    binaries = contents / "MacOS"
    binaries.mkdir(parents=True, exist_ok=True)
    launcher = binaries / APPLICATION_NAME
    if launcher.is_symlink() and launcher.readlink() != executable:
        launcher.unlink()
    if not launcher.is_symlink():
        launcher.symlink_to(executable)
    (contents / "Info.plist").write_bytes(
        plistlib.dumps(
            {
                "CFBundleName": APPLICATION_NAME,
                "CFBundleDisplayName": APPLICATION_NAME,
                "CFBundleIdentifier": "org.cambridgeaudio.desktop",
                "CFBundleExecutable": APPLICATION_NAME,
                "CFBundlePackageType": "APPL",
            }
        )
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(str(Path(path).resolve()) for path in sys.path)
    return subprocess.run(
        [str(launcher), "-m", "cambridge_audio.gui", *sys.argv[1:]],
        env=environment,
        check=False,
    ).returncode

"""Xcode's PATH must not replace the selected build-script Python."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(os.name == "nt", reason="Apple build integration uses a POSIX shell")
def test_apple_build_uses_explicit_python_even_when_xcode_shadows_python3(tmp_path):
    root = tmp_path / "project with spaces"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(ROOT / "scripts/build_mobile_apple.sh", scripts / "build_mobile_apple.sh")
    (root / "mobile").mkdir()
    tools = root / "fake tools"
    tools.mkdir()
    programs = {
        root / "mobile/gradlew": "#!/bin/sh\nexit 0\n",
        tools / "python3": "#!/bin/sh\nexit 99\n",
        tools / "native python": (
            '#!/bin/sh\n[ "$1" = scripts/build_mobile_codec.py ] || exit 98\n'
            'mkdir -p "build/mobile-codec/$2/lib" "build/mobile-codec/$2/include/lame"\n'
            'printf native > "build/mobile-codec/$2/lib/libmp3lame.a"\n'
            'printf header > "build/mobile-codec/$2/include/lame/lame.h"\n'
        ),
        tools / "xcrun": '#!/bin/sh\ncp "$3" "$5"\n',
    }
    for path, content in programs.items():
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)
    env = os.environ | {
        "PATH": str(tools) + os.pathsep + os.environ["PATH"],
        "CDA_PYTHON": str(tools / "native python"),
        "ARCHS": "arm64",
        "PLATFORM_NAME": "iphonesimulator",
    }
    subprocess.run(["bash", str(scripts / "build_mobile_apple.sh")], env=env, check=True)
    output = root / "build/mobile-codec/ios-iphonesimulator"
    assert (output / "libmp3lame.a").read_bytes() == b"native"
    assert (output / "include/lame/lame.h").read_bytes() == b"header"

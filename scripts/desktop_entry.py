"""Frozen GUI entry point; smoke checks use disposable settings and no network."""

import struct
import subprocess
import sys
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import QSettings, QTimer

from cambridge_audio.audio import combine_phrase, ffmpeg_executable
from cambridge_audio.gui import MainWindow, create_application, main


def smoke_test() -> int:
    app = create_application([sys.argv[0]])
    with TemporaryDirectory(prefix="cambridge-smoke-") as directory:
        settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
        settings.setValue("output_dir", directory)
        window = MainWindow(settings)
        executable = ffmpeg_executable()
        expected = (
            Path(sys._MEIPASS) / "tools" / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
        )
        if executable is None or Path(executable) != expected:
            return 1
        if not window.combine_check.isEnabled():
            return 1
        sample = Path(directory) / "sample.wav"
        with wave.open(str(sample), "wb") as stream:
            stream.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
            stream.writeframes(b"".join(struct.pack("<h", (i % 100) * 100) for i in range(4410)))
        mp3 = Path(directory) / "sample.mp3"
        subprocess.run(
            [
                executable,
                "-nostdin",
                "-loglevel",
                "error",
                "-i",
                str(sample),
                "-c:a",
                "libmp3lame",
                str(mp3),
            ],
            check=True,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        class OfflineClient:
            language = "en"

            def lookup(self, word):
                return ()

            def download(self, entries, accent, destination):
                destination.write_bytes(mp3.read_bytes())

        result = combine_phrase(
            OfflineClient(), "good morning", "us", Path(directory) / "phrase.mp3"
        )
        if result.stat().st_size < 100:
            return 1
        if window.windowIcon().pixmap(128, 128).isNull():
            return 1
        if window.settings_button.icon().pixmap(22, 22).isNull():
            return 1
        window.show()
        QTimer.singleShot(150, window.close)
        return app.exec()


if __name__ == "__main__":
    raise SystemExit(smoke_test() if "--smoke-test" in sys.argv else main())

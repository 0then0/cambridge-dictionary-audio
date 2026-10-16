"""Exercise desktop behavior offscreen with isolated settings and mocked HTTP."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import Mock

import pytest

from tests.helpers import response

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6", reason="Install the gui group to run desktop tests")


from cambridge_audio.gui import app as gui  # noqa: E402
from cambridge_audio.gui import workers
from cambridge_audio.service import Recording  # noqa: E402
from tests.gui.helpers import wait_until


def test_close_during_download_cancels_between_requests(window, app, monkeypatch, client, html):
    from threading import Event

    entered, release = Event(), Event()

    def slow_response(*args, **kwargs):
        entered.set()
        release.wait(3)
        return response(html)

    client.session.get.side_effect = slow_response
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
    window.word_edit.setText("hello")
    window.start_download()
    wait_until(app, entered.is_set)
    try:
        window.close()
        assert not window.isVisible()
        assert window._worker.isInterruptionRequested()
    finally:
        release.set()
    wait_until(app, lambda: window._worker is None)
    assert client.session.get.call_count == 1
    assert not window.output_dir.exists()


def test_application_quit_joins_active_worker(window, app, monkeypatch, client, html):
    from threading import Event, Timer

    entered, release = Event(), Event()

    def slow_response(*args, **kwargs):
        entered.set()
        release.wait(3)
        return response(html)

    client.session.get.side_effect = slow_response
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
    window.word_edit.setText("hello")
    window.start_download()
    wait_until(app, entered.is_set)
    releaser = Timer(0.05, release.set)
    releaser.start()
    try:
        window.shutdown()
        assert not window._worker.isRunning()
        assert not window.isVisible()
    finally:
        release.set()
        releaser.join()
    wait_until(app, lambda: window._worker is None)
    assert client.session.get.call_count == 1


@pytest.mark.parametrize("order", ["dictionary-only", "dictionary-first", "download-first"])
def test_close_during_dictionary_installation_exits_event_loop(tmp_path, order):
    # A real event loop in a fresh process catches an application that stays
    # alive after hiding its window, unlike the processEvents-only GUI fixture.
    script = textwrap.dedent("""
        import sys
        from pathlib import Path
        from threading import Event
        from unittest.mock import patch

        from PySide6.QtCore import QSettings, QTimer
        from PySide6.QtWidgets import QMessageBox
        from cambridge_audio import gui, wikdict
        from cambridge_audio.gui import workers

        root, order = Path(sys.argv[1]), sys.argv[2]
        app = gui.create_application([])
        dictionary_entered, dictionary_release = Event(), Event()
        download_entered, download_release = Event(), Event()
        state = {"closed": False, "watchdog": False}

        def installer(*args, check_cancelled, **kwargs):
            dictionary_entered.set()
            assert dictionary_release.wait(5)
            check_cancelled()
            raise AssertionError("Closing must cancel installation")

        def download(*args, check_cancelled, **kwargs):
            download_entered.set()
            assert download_release.wait(5)
            check_cancelled()
            raise AssertionError("Closing must cancel download")

        def watchdog():
            state["watchdog"] = True
            dictionary_release.set()
            download_release.set()
            app.quit()

        def close_when_started():
            if not dictionary_entered.is_set() or (
                order != "dictionary-only" and not download_entered.is_set()
            ):
                QTimer.singleShot(10, close_when_started)
                return
            state["closed"] = True
            if order == "dictionary-first":
                window._dictionary_worker.finished.connect(download_release.set)
            elif order == "download-first":
                window._worker.finished.connect(dictionary_release.set)
            window.close()
            assert not window.isVisible()
            if order == "download-first":
                download_release.set()
            else:
                dictionary_release.set()

        settings = QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
        settings.setValue("output_dir", str(root / "audio"))
        with (
            patch.object(wikdict, "default_dictionary_dir", return_value=root / "dict"),
            patch.object(workers, "install_dictionary", installer),
            patch.object(workers, "download_recordings", download),
            patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes),
        ):
            window = gui.MainWindow(settings)
            window.show()
            window.install_wikdict()
            if order != "dictionary-only":
                window.word_edit.setText("hello")
                window.start_download()
            QTimer.singleShot(0, close_when_started)
            QTimer.singleShot(4000, watchdog)
            app.exec()
            assert state["closed"], "The close scenario did not run"
            assert not state["watchdog"], "Hidden application did not quit after workers finished"
            assert window._worker is None
            assert window._dictionary_worker is None
            assert not (root / "audio").exists()
            assert not (root / "dict").exists()
    """)
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), order],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_repeated_scrollbar_painting_exits_without_native_runtime_corruption():
    # A successful assertion inside the process is insufficient: broken Qt ABI
    # builds can corrupt singleton refcounts and abort only at interpreter exit.
    code = textwrap.dedent(
        """
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        from cambridge_audio.gui.theme import ScrollBar

        app = QApplication([])
        bar = ScrollBar(Qt.Orientation.Vertical)
        bar.resize(12, 300)
        bar.setRange(0, 100)
        bar.setPageStep(25)
        bar.show()
        app.processEvents()
        for index in range(2000):
            bar.setValue(index % 100)
            assert not bar.grab().isNull()
        bar.close()
        app.shutdown()
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("operation", ["download", "translation"])
def test_gui_worker_cancels_rate_limit_wait(app, tmp_path, monkeypatch, request_clock, operation):
    from threading import Event

    from cambridge_audio import dictionary
    from cambridge_audio.library import SavedRecording

    entered, release = Event(), Event()
    clients = []

    def create_client(**kwargs):
        client = dictionary.CambridgeClient(**kwargs)
        client.session.get = Mock(return_value=response("limited", status=429))
        clients.append(client)
        return client

    def waiting(seconds):
        entered.set()
        assert release.wait(5)
        request_clock.now += seconds

    monkeypatch.setattr(workers, "CambridgeClient", create_client)
    monkeypatch.setattr(dictionary, "sleep", waiting)
    if operation == "download":
        worker = gui.DownloadWorker(gui.DownloadRequest("hello", tmp_path, "us", "en"))
    else:
        record = Recording("hello", "us", tmp_path / "hello.mp3", "", "greeting")
        worker = gui.TranslationWorker(SavedRecording(record), "en")
    worker.start()
    try:
        wait_until(app, entered.is_set)
        worker.requestInterruption()
    finally:
        release.set()
        assert worker.wait(3000)
    app.processEvents()
    assert clients[0].session.get.call_count == 1
    assert not (tmp_path / "hello.mp3").exists()

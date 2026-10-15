"""Exercise desktop behavior offscreen with isolated settings and mocked HTTP."""

import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests
from conftest import response

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6", reason="Install the gui group to run desktop tests")

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtMultimedia import QAudioDevice  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QMessageBox  # noqa: E402

from cambridge_audio import gui  # noqa: E402
from cambridge_audio.service import Recording  # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = gui.create_application([])
    application.setQuitOnLastWindowClosed(False)
    yield application


@pytest.fixture
def window(app, tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("output_dir", str(tmp_path / "audio"))
    instance = gui.MainWindow(settings)
    instance.show()
    app.processEvents()
    yield instance
    for worker in (instance._worker, instance._translation_worker):
        if worker is not None:
            worker.requestInterruption()
            worker.wait(5000)
            app.processEvents()
    instance.close()
    app.processEvents()


def test_application_has_a_renderable_icon_and_display_name(app):
    assert app.applicationDisplayName() == "Cambridge Dictionary Audio"
    assert not app.windowIcon().pixmap(128, 128).isNull()


def wait_until(app, predicate, timeout=5):
    end = time.monotonic() + timeout
    while not predicate() and time.monotonic() < end:
        app.processEvents()
        QTest.qWait(10)
    assert predicate(), "GUI worker did not finish in time"


def test_enter_downloads_us_without_blocking_ui(window, app, monkeypatch, client, html, mp3):
    client.session.get.side_effect = [response(html), response(mp3)]
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
    window.word_edit.setText("hello")
    QTest.keyClick(window.word_edit, Qt.Key.Key_Return)
    assert window._worker is not None
    assert not window.download_button.isEnabled()
    assert window.preferences_dialog.theme_combo.isEnabled()
    wait_until(app, lambda: window._worker is None)
    assert (window.output_dir / "hello.us.mp3").read_bytes() == mp3
    assert window.result_title.text() == "hello"
    assert window.ipa_label.text() == "US /heˈloʊ/"
    assert window.status_label.text() == "Recording saved."
    assert window.play_button.isEnabled()


def test_network_error_keeps_ui_usable(window, app, monkeypatch, client):
    client.session.get.return_value = response("blocked", status=403)
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
    window.word_edit.setText("hello")
    window.start_download()
    wait_until(app, lambda: window._worker is None)
    assert "403" in window.status_label.text()
    assert window.status_label.property("severity") == "error"
    assert window.download_button.isEnabled()
    assert not window.play_button.isEnabled()


def test_timeout_has_a_friendly_russian_message(window, app, monkeypatch, client):
    client.session.get.side_effect = requests.Timeout("internal-network-detail")
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
    window.preferences_dialog.language_combo.setCurrentIndex(
        window.preferences_dialog.language_combo.findData("ru")
    )
    window.word_edit.setText("hello")
    window.start_download()
    wait_until(app, lambda: window._worker is None)
    assert "не ответил вовремя" in window.status_label.text()
    assert "internal-network-detail" not in window.status_label.text()
    assert window.download_button.isEnabled()


def test_partial_success_remains_playable(window, app, monkeypatch, client, html, mp3):
    client.session.get.side_effect = [response(html), response(mp3), response("failed", status=500)]
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
    window.accent_combo.setCurrentIndex(window.accent_combo.findData("both"))
    window.word_edit.setText("hello")
    window.start_download()
    wait_until(app, lambda: window._worker is None)
    assert len(window.recordings) == 1
    assert window.recordings[0].path.read_bytes() == mp3
    assert window.play_button.isEnabled()
    assert "500" in window.status_label.text()


def test_both_accents_remain_selectable_after_language_change(
    window, app, monkeypatch, client, html, mp3
):
    client.session.get.side_effect = [response(html), response(mp3), response(mp3)]
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
    window.accent_combo.setCurrentIndex(window.accent_combo.findData("both"))
    window.word_edit.setText("hello")
    window.start_download()
    wait_until(app, lambda: window._worker is None)
    assert len(window.recordings) == 2
    assert window.recording_combo.isVisible()
    window.recording_combo.setCurrentIndex(0)
    assert window.ipa_label.text() == "UK /heˈləʊ/"
    assert window.file_label.text() == "hello.uk.mp3"
    window.preferences_dialog.language_combo.setCurrentIndex(
        window.preferences_dialog.language_combo.findData("ru")
    )
    assert window.selected_recording().accent == "uk"
    assert window.recording_combo.currentText() == "Британское (UK)"
    assert window.status_label.text() == "Обе записи сохранены."


def test_existing_file_is_opened_without_network_or_overwrite(window, monkeypatch, mp3):
    window.output_dir.mkdir()
    destination = window.output_dir / "hello.us.mp3"
    destination.write_bytes(mp3)
    confirmation = Mock(
        side_effect=AssertionError("Opening saved audio must not ask to replace it")
    )
    monkeypatch.setattr(QMessageBox, "exec", confirmation)
    worker = Mock()
    monkeypatch.setattr(gui, "DownloadWorker", worker)
    window.word_edit.setText("hello")
    window.start_download()
    worker.assert_not_called()
    assert destination.read_bytes() == mp3
    assert window.selected_recording().path == destination
    assert window.play_button.isEnabled()
    confirmation.assert_not_called()


def test_confirmed_overwrite_downloads_new_file(window, app, monkeypatch, client, html, mp3):
    window.output_dir.mkdir()
    destination = window.output_dir / "hello.us.mp3"
    destination.write_bytes(b"old recording")
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
    client.session.get.side_effect = [response(html), response(mp3)]
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
    window.word_edit.setText("hello")
    window.start_download(force=True)
    wait_until(app, lambda: window._worker is None)
    assert destination.read_bytes() == mp3


def test_language_theme_and_folder_are_remembered(window, app, monkeypatch, tmp_path):
    window.preferences_dialog.language_combo.setCurrentIndex(
        window.preferences_dialog.language_combo.findData("ru")
    )
    assert window.download_button.text() == "Скачать"
    window.preferences_dialog.theme_combo.setCurrentIndex(
        window.preferences_dialog.theme_combo.findData("dark")
    )
    assert window.effective_theme == "dark"
    selected = tmp_path / "custom recordings"
    monkeypatch.setattr(gui.QFileDialog, "getExistingDirectory", lambda *args: str(selected))
    window.choose_folder()
    window.settings.sync()
    restored = gui.MainWindow(window.settings)
    assert restored.language == "ru"
    assert restored.theme == "dark"
    assert restored.output_dir == selected
    assert restored.download_button.text() == "Скачать"
    restored.preferences_dialog.theme_combo.setCurrentIndex(
        restored.preferences_dialog.theme_combo.findData("light")
    )
    assert restored.effective_theme == "light"
    restored.preferences_dialog.theme_combo.setCurrentIndex(
        restored.preferences_dialog.theme_combo.findData("system")
    )
    assert restored.theme == "system"
    restored.close()


def test_system_theme_tracks_color_scheme_changes(window, app, monkeypatch):
    monkeypatch.setattr(app.styleHints(), "colorScheme", lambda: Qt.ColorScheme.Dark)
    app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert window.effective_theme == "dark"
    window.preferences_dialog.theme_combo.setCurrentIndex(
        window.preferences_dialog.theme_combo.findData("light")
    )
    app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert window.effective_theme == "light"


def test_close_during_download_cancels_between_requests(window, app, monkeypatch, client, html):
    from threading import Event

    entered, release = Event(), Event()

    def slow_response(*args, **kwargs):
        entered.set()
        release.wait(3)
        return response(html)

    client.session.get.side_effect = slow_response
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
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
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
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
            patch.object(gui, "install_dictionary", installer),
            patch.object(gui, "download_recordings", download),
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
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_recording_reports_error_instead_of_launching_player(window, monkeypatch):
    record = Recording("hello", "us", window.output_dir / "missing.mp3", "", "")
    window._on_recording(record)
    play = Mock()
    monkeypatch.setattr(window.player, "play", play)
    window.toggle_playback()
    play.assert_not_called()
    assert "moved or deleted" in window.status_label.text()


def test_missing_audio_output_is_reported_without_losing_recording(window, monkeypatch, mp3):
    window.output_dir.mkdir()
    path = window.output_dir / "hello.us.mp3"
    path.write_bytes(mp3)
    window._on_recording(Recording("hello", "us", path, "", ""))
    monkeypatch.setattr(gui.QMediaDevices, "defaultAudioOutput", QAudioDevice)
    play = Mock()
    monkeypatch.setattr(window.player, "play", play)
    window.toggle_playback()
    play.assert_not_called()
    assert "Audio output is unavailable" in window.status_label.text()
    assert path.read_bytes() == mp3


def test_restart_restores_recording_and_details_without_network(window, app, monkeypatch, mp3):
    from cambridge_audio.library import save_metadata

    window.output_dir.mkdir()
    path = window.output_dir / "hello.us.mp3"
    path.write_bytes(mp3)
    save_metadata(Recording("hello", "us", path, "heˈloʊ", "a greeting"), ("привет",), "russian")
    client = Mock()
    monkeypatch.setattr(gui, "CambridgeClient", client)
    restored = gui.MainWindow(window.settings)
    try:
        assert restored.selected_recording().path == path
        assert restored.ipa_label.text() == "US /heˈloʊ/"
        assert restored.definition_label.text() == "a greeting"
        assert "Cambridge\nпривет" in restored.translation_label.text()
        assert restored.play_button.isEnabled()
        device = Mock()
        device.isNull.return_value = False
        monkeypatch.setattr(gui.QMediaDevices, "defaultAudioOutput", lambda: device)
        monkeypatch.setattr(restored.audio_output, "setDevice", Mock())
        play = Mock()
        monkeypatch.setattr(restored.player, "play", play)
        restored.toggle_playback()
        play.assert_called_once()
        assert Path(restored.player.source().toLocalFile()) == path.resolve()
        client.assert_not_called()
    finally:
        restored.close()


def test_folder_change_and_refresh_only_show_current_folder(window, monkeypatch, tmp_path, mp3):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "hello.us.mp3").write_bytes(mp3)
    (second / "world.uk.mp3").write_bytes(mp3)
    monkeypatch.setattr(gui.QFileDialog, "getExistingDirectory", lambda *args: str(first))
    window.choose_folder()
    assert window.selected_recording().word == "hello"
    monkeypatch.setattr(gui.QFileDialog, "getExistingDirectory", lambda *args: str(second))
    window.choose_folder()
    assert window.selected_recording().word == "world"
    assert window.library_combo.count() == 1
    (second / "world.uk.mp3").unlink()
    window.refresh_button.click()
    assert window.selected_recording() is None
    assert not window.play_button.isEnabled()


def test_both_accents_downloads_only_missing_recording(window, app, monkeypatch, client, html, mp3):
    window.output_dir.mkdir()
    existing = window.output_dir / "hello.us.mp3"
    existing.write_bytes(b"original audio")
    client.session.get.side_effect = [response(html), response(mp3)]
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
    window.accent_combo.setCurrentIndex(window.accent_combo.findData("both"))
    window.word_edit.setText("hello")
    window.download_button.click()
    wait_until(app, lambda: window._worker is None)
    assert existing.read_bytes() == b"original audio"
    assert (window.output_dir / "hello.uk.mp3").read_bytes() == mp3
    assert len(window.recordings) == 2
    assert window.library_combo.count() == 2


def test_new_download_details_survive_restart(window, app, monkeypatch, client, html, mp3):
    client.session.get.side_effect = [response(html), response(mp3)]
    client.translations = Mock(return_value=("привет",))
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
    window.translation_check.setChecked(True)
    window.word_edit.setText("hello")
    window.start_download()
    wait_until(app, lambda: window._worker is None)
    restored = gui.MainWindow(window.settings)
    try:
        assert restored.selected_recording().ipa == "heˈloʊ"
        assert restored.definition_label.text() == "used when meeting someone"
        assert "Cambridge\nпривет" in restored.translation_label.text()
        restored.word_edit.setText("hello")
        assert restored.download_button.text() == "Open saved"
        worker = Mock()
        monkeypatch.setattr(gui, "DownloadWorker", worker)
        restored.download_button.click()
        worker.assert_not_called()
        assert restored.selected_recording().word == "hello"
    finally:
        restored.close()


def test_download_again_button_requires_confirmation(window, monkeypatch, mp3):
    window.output_dir.mkdir()
    path = window.output_dir / "hello.us.mp3"
    path.write_bytes(mp3)
    window.refresh_library()
    confirmation = Mock(return_value=QMessageBox.StandardButton.No)
    monkeypatch.setattr(QMessageBox, "exec", confirmation)
    worker = Mock()
    monkeypatch.setattr(gui, "DownloadWorker", worker)
    window.redownload_button.click()
    confirmation.assert_called_once()
    worker.assert_not_called()
    assert path.read_bytes() == mp3


def test_metadata_failure_does_not_lose_downloaded_audio(
    window, app, monkeypatch, client, html, mp3
):
    client.session.get.side_effect = [response(html), response(mp3)]
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
    monkeypatch.setattr(gui, "save_metadata", Mock(side_effect=OSError("disk full")))
    window.word_edit.setText("hello")
    window.start_download()
    wait_until(app, lambda: window._worker is None)
    assert window.selected_recording().path.read_bytes() == mp3
    assert window.play_button.isEnabled()
    assert window.library_combo.count() == 1
    assert window.status_label.text() == "Audio saved. Details could not be saved: disk full"


def test_translation_checkbox_toggles_saved_translation_without_network(window, monkeypatch, mp3):
    from cambridge_audio.library import save_metadata

    window.output_dir.mkdir()
    path = window.output_dir / "hello.us.mp3"
    path.write_bytes(mp3)
    save_metadata(Recording("hello", "us", path, "heˈloʊ", "a greeting"), ("привет",), "russian")
    metadata = path.with_suffix(".json").read_bytes()
    client = Mock()
    monkeypatch.setattr(gui, "CambridgeClient", client)
    window.refresh_library()
    assert window.translation_label.isHidden()
    window.translation_check.click()
    assert window.translation_label.isVisible()
    assert "Cambridge\nпривет" in window.translation_label.text()
    assert window.settings.value("translation", type=bool)
    window.translation_check.click()
    assert window.translation_label.isHidden()
    window.preferences_dialog.language_combo.setCurrentIndex(
        window.preferences_dialog.language_combo.findData("ru")
    )
    assert window.translation_label.isHidden()
    window.refresh_library()
    assert window.translation_label.isHidden()
    window.translation_check.click()
    assert window.translation_label.isVisible()
    assert "Cambridge\nпривет" in window.translation_label.text()
    assert path.with_suffix(".json").read_bytes() == metadata
    client.assert_not_called()


def test_translation_checkbox_fetches_empty_cache_without_redownloading(
    window, app, monkeypatch, client, mp3
):
    from cambridge_audio.library import read_recording

    window.output_dir.mkdir()
    path = window.output_dir / "hello.us.mp3"
    path.write_bytes(mp3)
    client.translations = Mock(return_value=("привет",))
    client.download = Mock(side_effect=AssertionError("Audio must not be downloaded"))
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kw: client)
    window.refresh_library()
    window.translation_check.click()
    assert window.translation_label.isVisible()
    wait_until(app, lambda: window._translation_worker is None)
    assert "Cambridge\nпривет" in window.translation_label.text()
    assert read_recording(path).translation_language == "russian"
    assert path.read_bytes() == mp3
    window.translation_check.click()
    assert window.translation_label.isHidden()
    window.translation_check.click()
    assert "Cambridge\nпривет" in window.translation_label.text()
    client.translations.assert_called_once_with("hello", "russian")
    client.download.assert_not_called()


def test_settings_gear_opens_separate_window_and_changes_language(window):
    dialog = window.preferences_dialog
    assert not dialog.isVisible()
    assert dialog.isWindow()
    assert dialog.language_combo.window() is dialog
    window.settings_button.click()
    assert dialog.isVisible()
    assert not window.settings_button.icon().pixmap(22, 22).isNull()
    dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("ru"))
    assert window.settings_button.toolTip() == "Настройки"
    assert dialog.windowTitle() == "Настройки"
    assert dialog.color_labels["background"].text() == "Цвет фона"
    dialog.close_button.click()
    assert not dialog.isVisible()
    assert window.isVisible()
    window.settings_button.click()
    window.close()
    assert not dialog.isVisible()


def test_custom_colours_apply_and_survive_restart(window, app, monkeypatch):
    from PySide6.QtGui import QColor, QPalette

    from cambridge_audio.preferences import QColorDialog
    from cambridge_audio.theme import theme_colors

    dialog = window.preferences_dialog
    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData("light"))
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args: QColor("#112244"))
    dialog.color_buttons["background"].click()
    assert app.palette().color(QPalette.ColorRole.Window).name() == "#112244"
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args: QColor("#ffee33"))
    dialog.color_buttons["accent"].click()
    assert app.palette().color(QPalette.ColorRole.Highlight).name() == "#ffee33"
    assert app.palette().color(QPalette.ColorRole.HighlightedText).name() == "#000000"
    assert dialog.color_buttons["accent"].text() == "#FFEE33"
    colors = theme_colors("light", {"background": "#112244", "accent": "#ffee33"})
    icon = window.settings_button.icon().pixmap(24, 24).toImage()
    opaque = {
        icon.pixelColor(x, y).name()
        for x in range(icon.width())
        for y in range(icon.height())
        if icon.pixelColor(x, y).alpha() > 250
    }
    assert colors["muted"] in opaque
    window.settings.sync()
    restored = gui.MainWindow(window.settings)
    try:
        assert restored.preferences_dialog.color_buttons["background"].text() == "#112244"
        assert app.palette().color(QPalette.ColorRole.Highlight).name() == "#ffee33"
    finally:
        restored.close()


def test_colour_cancel_and_reset_preserve_other_settings(window, app, monkeypatch):
    from PySide6.QtGui import QColor, QPalette

    from cambridge_audio.preferences import QColorDialog
    from cambridge_audio.theme import COLORS

    dialog = window.preferences_dialog
    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData("light"))
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args: QColor())
    dialog.color_buttons["background"].click()
    assert not window.settings.contains("theme_colors/light/background")
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args: QColor("#aabbcc"))
    dialog.color_buttons["background"].click()
    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData("dark"))
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args: QColor("#998822"))
    dialog.color_buttons["accent"].click()
    dialog.reset_button.click()
    assert not window.settings.contains("theme_colors/dark/accent")
    assert window.settings.value("theme_colors/light/background") == "#aabbcc"
    assert app.palette().color(QPalette.ColorRole.Window).name() == COLORS["dark"]["background"]
    assert window.theme == "dark"
    assert window.language == "en"


def test_system_appearance_selects_custom_palette_and_updates_icons(window, app, monkeypatch):
    from PySide6.QtGui import QPalette

    window.settings.setValue("theme_colors/light/background", "#fff0dd")
    window.settings.setValue("theme_colors/dark/background", "#221133")
    monkeypatch.setattr(app.styleHints(), "colorScheme", lambda: Qt.ColorScheme.Dark)
    app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    dark_icon = window.settings_button.icon().cacheKey()
    assert app.palette().color(QPalette.ColorRole.Window).name() == "#221133"
    assert window.preferences_dialog.mode == "dark"
    monkeypatch.setattr(app.styleHints(), "colorScheme", lambda: Qt.ColorScheme.Light)
    app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Light)
    assert app.palette().color(QPalette.ColorRole.Window).name() == "#fff0dd"
    assert window.preferences_dialog.mode == "light"
    assert window.settings_button.icon().cacheKey() != dark_icon


@pytest.mark.parametrize("cached_language", ["french", None])
def test_gui_refetches_foreign_or_unknown_translation(
    window, app, monkeypatch, client, mp3, cached_language
):
    from cambridge_audio.library import read_recording, save_metadata

    window.output_dir.mkdir()
    path = window.output_dir / "hello.us.mp3"
    path.write_bytes(mp3)
    save_metadata(Recording("hello", "us", path, "", ""), ("bonjour",), cached_language)
    client.translations = Mock(return_value=("привет",))
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kw: client)
    window.refresh_library()
    window.translation_check.click()
    assert window.translation_label.text() != "bonjour"
    wait_until(app, lambda: window._translation_worker is None)
    assert "Cambridge\nпривет" in window.translation_label.text()
    assert read_recording(path).translation_language == "russian"
    client.translations.assert_called_once_with("hello", "russian")


def test_gui_translation_failure_can_be_retried_without_audio_download(
    window, app, monkeypatch, client, mp3
):
    from cambridge_audio.dictionary import CambridgeError

    window.output_dir.mkdir()
    path = window.output_dir / "hello.us.mp3"
    path.write_bytes(mp3)
    client.translations = Mock(side_effect=[CambridgeError("offline"), ("привет",)])
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kw: client)
    window.refresh_library()
    window.translation_check.click()
    wait_until(app, lambda: window._translation_worker is None)
    assert window.translation_label.text().startswith("Translation: offline")
    assert "not installed" in window.translation_label.text()
    app.processEvents()
    assert client.translations.call_count == 1
    window.translation_check.click()
    window.translation_check.click()
    wait_until(app, lambda: window._translation_worker is None)
    assert "Cambridge\nпривет" in window.translation_label.text()
    assert path.read_bytes() == mp3


@pytest.mark.parametrize("change", ["selection", "folder", "hide", "close"])
def test_gui_translation_finishes_safely_after_context_change(
    window, app, monkeypatch, client, mp3, tmp_path, change
):
    from threading import Event

    from cambridge_audio.library import read_recording

    window.output_dir.mkdir()
    first = window.output_dir / "hello.us.mp3"
    second = window.output_dir / "world.us.mp3"
    first.write_bytes(mp3)
    second.write_bytes(mp3)
    entered, release = Event(), Event()

    def fetch(word, language):
        if word == "hello":
            entered.set()
            assert release.wait(5)
            return ("привет",)
        return ("мир",)

    client.translations = Mock(side_effect=fetch)
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kw: client)
    # Prevent a test close from terminating the shared test QApplication.
    monkeypatch.setattr(app, "quit", Mock())
    window.refresh_library()
    window.translation_check.click()
    try:
        wait_until(app, entered.is_set)
        assert window.translation_label.text() == "Loading translation..."
        if change == "selection":
            window.library_combo.setCurrentIndex(window.library_combo.findData(str(second)))
        elif change == "folder":
            other = tmp_path / "other"
            other.mkdir()
            monkeypatch.setattr(gui.QFileDialog, "getExistingDirectory", lambda *a: str(other))
            window.choose_folder()
        elif change == "hide":
            window.translation_check.click()
        else:
            window.close()
            assert window._closing
            assert not window.isVisible()
    finally:
        release.set()
    wait_until(app, lambda: window._translation_worker is None)
    assert read_recording(first).translations == ("привет",)
    assert first.read_bytes() == mp3
    if change == "selection":
        assert window.selected_recording().word == "world"
        assert "Cambridge\nмир" in window.translation_label.text()
    elif change in ("folder", "hide"):
        assert window.translation_label.isHidden()
    else:
        app.quit.assert_called_once()


def test_gui_opens_aliases_and_recovers_reserved_names(window, mp3):
    window.output_dir.mkdir()
    target = window.output_dir / "hello.mp3"
    target.write_bytes(mp3)
    alias = window.output_dir / "hello.us.mp3"
    try:
        alias.symlink_to(target.name)
    except OSError:
        pytest.skip("Creating symlinks requires platform permission")
    (window.output_dir / "_con.us.mp3").write_bytes(mp3)
    window.refresh_library()
    assert window.selected_recording().word == "con"
    window.library_combo.setCurrentIndex(window.library_combo.findData(str(alias)))
    assert window.selected_recording().path == alias
    assert window.selected_recording().word == "hello"


@pytest.mark.parametrize("orientation", [Qt.Orientation.Vertical, Qt.Orientation.Horizontal])
def test_scrollbar_handle_expands_on_hover_without_resizing_layout(app, orientation):
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QScrollBar, QWidget

    from cambridge_audio.theme import apply_theme, theme_colors

    apply_theme(app, "dark")
    parent = QWidget()
    parent.resize(400, 400)
    bar = QScrollBar(orientation, parent)
    bar.setRange(0, 100)
    bar.setPageStep(25)
    if orientation == Qt.Orientation.Vertical:
        bar.setGeometry(20, 20, 12, 300)
    else:
        bar.setGeometry(20, 20, 300, 12)
    parent.show()
    QTest.mouseMove(parent, QPoint(350, 350))
    app.processEvents()
    color = theme_colors("dark")["scrollbar"]

    def thickness():
        image = bar.grab().toImage()
        # Sample through the middle of the handle, away from its rounded ends.
        return (
            sum(image.pixelColor(x, 20).name() == color for x in range(image.width()))
            if orientation == Qt.Orientation.Vertical
            else sum(image.pixelColor(20, y).name() == color for y in range(image.height()))
        )

    normal = thickness()
    size = bar.size()
    QTest.mouseMove(bar, QPoint(6, 20) if orientation == Qt.Orientation.Vertical else QPoint(20, 6))
    app.processEvents()
    # Hover may recolour the handle as well as change its width.
    hovered = bar.grab().toImage()
    # Count non-background pixels using the palette's two possible handle colours.
    colors = {color, theme_colors("dark")["scrollbar_hover"]}
    width = (
        sum(hovered.pixelColor(x, 20).name() in colors for x in range(hovered.width()))
        if orientation == Qt.Orientation.Vertical
        else sum(hovered.pixelColor(20, y).name() in colors for y in range(hovered.height()))
    )
    assert normal == 4
    assert width == 8
    assert bar.size() == size
    parent.close()


@pytest.mark.parametrize("answer", [QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes])
def test_gui_empty_recording_can_be_replaced_with_confirmation(
    window, app, monkeypatch, client, html, mp3, answer
):
    window.output_dir.mkdir()
    path = window.output_dir / "hello.us.mp3"
    path.touch()
    window.refresh_library()
    assert window.selected_recording() is None
    confirmation = Mock(return_value=answer)
    monkeypatch.setattr(QMessageBox, "exec", confirmation)
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kw: client)
    client.session.get.side_effect = [response(html), response(mp3)]
    window.word_edit.setText("hello")
    window.start_download()
    confirmation.assert_called_once()
    wait_until(app, lambda: window._worker is None)
    if answer == QMessageBox.StandardButton.Yes:
        assert path.read_bytes() == mp3
    else:
        assert path.read_bytes() == b""
        client.session.get.assert_not_called()


def test_gui_variant_selection_and_redownload_preserve_other_variants(
    window, app, monkeypatch, client, html
):
    from cambridge_audio.library import read_recording

    second = (
        html.replace("used when meeting someone", "a second meaning")
        .replace("hello-us.mp3", "hello-second.mp3")
        .replace("heˈloʊ", "different")
    )
    choices_html = html + second
    client.session.get.side_effect = [
        response(choices_html),
        response(b"ID3first"),
        response(choices_html),
        response(b"ID3second"),
        response(choices_html),
        response(b"ID3replaced"),
    ]
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
    selected_index = [0]
    monkeypatch.setattr(
        gui.QInputDialog, "getItem", lambda *args: (args[3][selected_index[0]], True)
    )
    window.word_edit.setText("hello")
    window.start_download()
    wait_until(app, lambda: window._worker is None)
    first = window.selected_recording()
    assert first.definition == "used when meeting someone"
    assert first.path.read_bytes() == b"ID3first"
    selected_index[0] = 1
    window.word_edit.clear()
    window.start_download(choose_variant=True)
    wait_until(app, lambda: window._worker is None)
    second_record = window.selected_recording()
    assert second_record.definition == "a second meaning"
    assert second_record.ipa == "different"
    assert second_record.path != first.path
    assert second_record.path.read_bytes() == b"ID3second"
    assert read_recording(second_record.path).recording == second_record
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Yes)
    window.redownload()
    wait_until(app, lambda: window._worker is None)
    assert second_record.path.read_bytes() == b"ID3replaced"
    assert first.path.read_bytes() == b"ID3first"
    assert window.library_combo.count() == 2


def test_gui_edit_while_translation_pending_survives_late_response(
    window, app, monkeypatch, client, mp3
):
    from threading import Event

    from cambridge_audio.library import read_recording, save_metadata
    from cambridge_audio.translations import cached_translation

    window.output_dir.mkdir()
    path = window.output_dir / "hello.us.mp3"
    path.write_bytes(mp3)
    save_metadata(Recording("hello", "us", path, "", "greeting", sense_id="greeting"))
    entered, release = Event(), Event()

    def translate(word, language):
        entered.set()
        assert release.wait(5)
        return ("automatic",)

    client.translations = Mock(side_effect=translate)
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
    monkeypatch.setattr(gui.QInputDialog, "getMultiLineText", lambda *args: ("personal", True))
    window.refresh_library()
    window.translation_check.setChecked(True)
    wait_until(app, entered.is_set)
    try:
        window.edit_selected_translation()
        window.translation_check.setChecked(False)
    finally:
        release.set()
    wait_until(app, lambda: window._translation_worker is None)
    result = cached_translation(read_recording(path), "russian")
    assert result.source == "User" and result.texts == ("personal",)
    assert window.translation_label.isHidden()
    window.translation_check.setChecked(True)
    assert "User\npersonal" in window.translation_label.text()
    client.translations.assert_called_once()


def test_gui_interface_language_change_keeps_foreign_edit_and_russian_response(
    window, app, monkeypatch, client, mp3
):
    from threading import Event

    from cambridge_audio.library import read_recording, save_metadata
    from cambridge_audio.translations import cached_translation, edit_translation

    window.output_dir.mkdir()
    path = window.output_dir / "hello.us.mp3"
    path.write_bytes(mp3)
    save_metadata(Recording("hello", "us", path, "", "greeting"))
    edit_translation(read_recording(path), "french", "bonjour personnel")
    entered, release = Event(), Event()

    def translate(word, language):
        assert language == "russian"
        entered.set()
        assert release.wait(5)
        return ("привет",)

    client.translations = Mock(side_effect=translate)
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
    window.refresh_library()
    window.translation_check.setChecked(True)
    wait_until(app, entered.is_set)
    try:
        window.preferences_dialog.language_combo.setCurrentIndex(
            window.preferences_dialog.language_combo.findData("ru")
        )
    finally:
        release.set()
    wait_until(app, lambda: window._translation_worker is None)
    saved = read_recording(path)
    assert window.language == "ru" and window.translation_language == "russian"
    assert window.translation_check.text() == "Показывать перевод на русский"
    assert "привет" in window.translation_label.text()
    assert "bonjour" not in window.translation_label.text()
    assert cached_translation(saved, "russian").texts == ("привет",)
    assert cached_translation(saved, "french").texts == ("bonjour personnel",)
    client.translations.assert_called_once_with("hello", "russian")


def test_gui_export_selected_and_all_and_reports_missing_mp3(window, monkeypatch, mp3, tmp_path):
    from cambridge_audio.library import save_metadata

    window.output_dir.mkdir()
    for accent in ("us", "uk"):
        path = window.output_dir / f"hello.{accent}.mp3"
        path.write_bytes(mp3)
        save_metadata(Recording("hello", accent, path, "", "greeting"))
    window.refresh_library()
    parent = tmp_path / "exports"
    parent.mkdir()
    monkeypatch.setattr(gui.QFileDialog, "getExistingDirectory", lambda *args: str(parent))
    scope = [0]

    def accept_export(dialog):
        dialog.setTextValue(dialog.comboBoxItems()[scope[0]])
        return gui.QInputDialog.DialogCode.Accepted

    monkeypatch.setattr(gui.QInputDialog, "exec", accept_export)
    window.export_collection()
    output = parent / "cambridge-anki"
    assert len(list((output / "media").iterdir())) == 1
    scope[0] = 1
    window.export_collection()
    assert len(list((output / "media").iterdir())) == 2
    original = (output / "collection.tsv").read_bytes()
    window.selected_recording().path.unlink()
    scope[0] = 0
    window.export_collection()
    assert window.status_label.property("severity") == "error"
    assert (output / "collection.tsv").read_bytes() == original


@pytest.mark.parametrize("language, theme, font_size", [("en", "light", 14), ("ru", "dark", 21)])
def test_short_combo_popups_show_every_row_without_scrolling(
    window, app, language, theme, font_size
):
    window.settings.setValue("language", language)
    window.settings.setValue("theme", theme)
    window._preferences_changed()
    window.preferences_dialog.show()
    for combo in (
        window.preferences_dialog.language_combo,
        window.preferences_dialog.theme_combo,
        window.accent_combo,
    ):
        font = combo.font()
        font.setPixelSize(font_size)
        combo.setFont(font)
        try:
            combo.showPopup()
            app.processEvents()
            view = combo.view()
            assert view.verticalScrollBar().maximum() == 0
            for row in range(combo.count()):
                rectangle = view.visualRect(view.model().index(row, 0))
                assert rectangle.top() >= 0
                assert rectangle.bottom() < view.viewport().height()
        finally:
            combo.hidePopup()


def test_long_combo_popup_keeps_scrolling_available(window, app):
    combo = gui.ComboBox(window)
    combo.addItems([f"Recording {index}" for index in range(100)])
    try:
        combo.showPopup()
        app.processEvents()
        assert combo.view().verticalScrollBar().maximum() > 0
        assert combo.view().height() < sum(combo.view().sizeHintForRow(i) for i in range(100))
    finally:
        combo.hidePopup()
        combo.close()


@pytest.mark.parametrize("language, title", [("en", "About"), ("ru", "О приложении")])
def test_settings_about_shows_installed_version_repository_and_licenses(
    window, app, monkeypatch, language, title
):
    from importlib.metadata import version

    window.settings.setValue("language", language)
    window._preferences_changed()
    about = Mock()
    monkeypatch.setattr(QMessageBox, "about", about)
    window.preferences_dialog.about_button.click()
    parent, actual_title, text = about.call_args.args
    assert parent is window.preferences_dialog
    assert actual_title == title
    assert window.preferences_dialog.about_button.text() == title
    assert app.applicationVersion() == version("cambridge-dictionary-audio")
    assert app.applicationVersion() in text
    assert "Cambridge Dictionary Audio" in text
    assert 'href="https://github.com/0then0/cambridge-dictionary-audio"' in text
    assert "Apache-2.0" in text and "MIT" in text
    assert ("own licenses" if language == "en" else "собственные лицензии") in text


@pytest.mark.parametrize("language,size", [("en", "20.9 MB"), ("ru", "20,9 МБ")])
def test_wikdict_install_confirmation_shows_megabytes(window, monkeypatch, language, size):
    window.language = language
    question = Mock(return_value=QMessageBox.StandardButton.No)
    monkeypatch.setattr(gui.QMessageBox, "question", question)
    window.install_wikdict()
    text = question.call_args.args[2]
    assert size in text
    assert gui.PACKAGE.version in text
    assert gui.PACKAGE.license_url in text
    assert window._dictionary_worker is None


@pytest.mark.parametrize("answer", [QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes])
def test_empty_new_word_does_not_replace_selected_library_record(
    window, app, monkeypatch, client, html, mp3, answer
):
    from cambridge_audio.library import read_recording, save_metadata

    window.output_dir.mkdir()
    original = window.output_dir / "hello.us.mp3"
    original.write_bytes(b"ID3original")
    save_metadata(Recording("hello", "us", original, "", "a greeting"))
    sidecar = original.with_suffix(".json").read_bytes()
    destination = window.output_dir / "world.us.mp3"
    destination.write_bytes(b"")
    window.refresh_library()
    assert window.selected_recording().word == "hello"
    window.word_edit.setText("world")
    client.session.get.side_effect = [response(html.replace("hello", "world")), response(mp3)]
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: answer)
    window.start_download()
    wait_until(app, lambda: window._worker is None)
    assert original.read_bytes() == b"ID3original"
    assert original.with_suffix(".json").read_bytes() == sidecar
    if answer == QMessageBox.StandardButton.Yes:
        assert destination.read_bytes() == mp3
        assert read_recording(destination).recording.word == "world"
    else:
        assert destination.read_bytes() == b""
        client.session.get.assert_not_called()


@pytest.mark.parametrize("language", ["en", "ru"])
def test_new_translation_displays_readable_senses_without_ids(
    window, app, monkeypatch, client, html, mp3, language
):
    from cambridge_audio.library import read_recording
    from cambridge_audio.translations import cached_translation

    bilingual = """<div class="entry-body__el"><span class="pos">exclamation</span>
    <div class="def-block"><div class="def ddef_d">a greeting</div>
    <div class="def-body"><span class="trans">привет</span></div></div>
    <div class="def-block"><div class="def ddef_d">answering the phone</div>
    <div class="def-body"><span class="trans">алло</span></div></div></div>"""
    client.session.get.side_effect = [response(html), response(mp3), response(bilingual)]
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
    window.language = language
    window._retranslate()
    window.translation_check.setChecked(True)
    window.word_edit.setText("hello")
    window.start_download()
    wait_until(app, lambda: window._worker is None and window._translation_worker is None)
    text = window.translation_label.text()
    assert "• привет" in text and "• алло" in text
    assert "a greeting" in text and "answering the phone" in text
    assert ("междометие" if language == "ru" else "exclamation") in text
    assert "unspecified sense" not in text
    result = cached_translation(read_recording(window.selected_recording().path), "russian")
    assert all(option.id not in text for option in result.options)
    monkeypatch.setattr(gui.QInputDialog, "getItem", lambda *args: (args[3][1], True))
    window.choose_translation_sense()
    assert "алло" in window.translation_label.text()
    assert "привет" not in window.translation_label.text()
    assert client.session.get.call_count == 3


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("orientation", [Qt.Orientation.Vertical, Qt.Orientation.Horizontal])
def test_adaptive_scrollbar_animates_hover_and_keeps_drag_target(app, mode, orientation):
    from PySide6.QtCore import QAbstractAnimation, QEvent, QPoint
    from PySide6.QtWidgets import QWidget

    from cambridge_audio.theme import ScrollBar, apply_theme, theme_colors

    apply_theme(app, mode)
    parent = QWidget()
    parent.resize(400, 400)
    bar = ScrollBar(orientation, parent)
    bar.setRange(0, 100)
    bar.setPageStep(25)
    vertical = orientation == Qt.Orientation.Vertical
    bar.setGeometry(20, 20, 12 if vertical else 300, 300 if vertical else 12)
    parent.show()
    QTest.mouseMove(parent, QPoint(350, 350))
    app.processEvents()
    dimensions = bar.size()

    def thickness(color):
        image = bar.grab().toImage()
        return (
            sum(image.pixelColor(x, 20).name() == color for x in range(image.width()))
            if vertical
            else sum(image.pixelColor(20, y).name() == color for y in range(image.height()))
        )

    assert thickness(theme_colors(mode)["scrollbar"]) == 4
    point = QPoint(6, 20) if vertical else QPoint(20, 6)
    QTest.mouseMove(bar, point)
    wait_until(app, lambda: bar._hover_animation.state() == QAbstractAnimation.State.Stopped)
    assert thickness(theme_colors(mode)["scrollbar_hover"]) == 8
    assert bar.size() == dimensions
    QTest.mousePress(bar, Qt.MouseButton.LeftButton, pos=point)
    assert bar.isSliderDown()
    app.sendEvent(bar, QEvent(QEvent.Type.Leave))
    assert bar._expansion == 1.0
    end = QPoint(6, 150) if vertical else QPoint(150, 6)
    QTest.mouseMove(bar, end)
    QTest.mouseRelease(bar, Qt.MouseButton.LeftButton, pos=end)
    assert bar.value() > 0
    assert bar.size() == dimensions
    parent.close()


def test_scroll_area_smooth_wheel_matches_qt_bounds_and_preserves_precise_input(app):
    from PySide6.QtCore import QAbstractAnimation, QPoint, QPointF
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QScrollArea, QWidget

    from cambridge_audio.theme import install_scrollbars

    def area(adaptive):
        widget = QScrollArea()
        widget.resize(400, 300)
        content = QWidget()
        content.setMinimumSize(800, 2000)
        widget.setWidget(content)
        if adaptive:
            install_scrollbars(widget)
        widget.show()
        return widget

    reference, animated = area(False), area(True)
    app.processEvents()
    native = reference.verticalScrollBar()
    bar = animated.verticalScrollBar()

    def wheel(widget, *, pixels=0, accepted=True):
        event = QWheelEvent(
            QPointF(100, 100),
            QPointF(widget.mapToGlobal(QPoint(100, 100))),
            QPoint(0, pixels),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate if pixels else Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        app.sendEvent(widget.viewport(), event)
        assert event.isAccepted() == accepted

    try:
        for _ in range(2):
            wheel(reference)
            wheel(animated)
        assert bar._scroll_animation.state() == QAbstractAnimation.State.Running
        assert bar.value() < native.value()
        wait_until(app, lambda: bar._scroll_animation.state() == QAbstractAnimation.State.Stopped)
        assert bar.value() == native.value() > 0
        wheel(reference, pixels=-15)
        wheel(animated, pixels=-15)
        assert bar._scroll_animation.state() == QAbstractAnimation.State.Stopped
        assert bar.value() == native.value()
        wheel(animated)
        QTest.keyClick(animated, Qt.Key.Key_PageDown)
        assert bar._scroll_animation.state() == QAbstractAnimation.State.Stopped
        bar.setValue(bar.maximum())
        wheel(animated, accepted=False)
        assert bar.value() == bar.maximum()
        assert bar._scroll_animation.state() == QAbstractAnimation.State.Stopped
    finally:
        reference.close()
        animated.close()


@pytest.mark.parametrize("exit_method", ["close", "shutdown"])
def test_window_geometry_survives_restart(window, app, exit_method):
    window.setGeometry(45, 50, 680, 560)
    app.processEvents()
    expected = window.geometry()
    settings_file = window.settings.fileName()
    getattr(window, exit_method)()
    settings = QSettings(settings_file, QSettings.Format.IniFormat)
    restored = gui.MainWindow(settings)
    try:
        restored.show()
        app.processEvents()
        assert restored.geometry() == expected
    finally:
        restored.close()


def test_maximized_window_restores_normal_size_after_restart(window, app):
    window.setGeometry(45, 50, 680, 560)
    app.processEvents()
    normal_size = window.size()
    window.showMaximized()
    app.processEvents()
    window.close()
    restored = gui.MainWindow(window.settings)
    try:
        restored.show()
        app.processEvents()
        assert restored.isMaximized()
        restored.showNormal()
        app.processEvents()
        assert restored.size() == normal_size
    finally:
        restored.close()


def test_offscreen_window_geometry_is_recovered_on_available_display(window, app):
    window.resize(680, 560)
    window.move(100000, 100000)
    app.processEvents()
    window.close()
    restored = gui.MainWindow(window.settings)
    try:
        restored.show()
        app.processEvents()
        assert any(
            screen.availableGeometry().contains(restored.geometry()) for screen in app.screens()
        )
    finally:
        restored.close()


@pytest.mark.parametrize("geometry", ["invalid setting", b"not a Qt geometry"])
def test_invalid_window_geometry_keeps_default_size(window, app, geometry):
    expected = window.size()
    window.close()
    window.settings.setValue("window/geometry", geometry)
    restored = gui.MainWindow(window.settings)
    try:
        restored.show()
        app.processEvents()
        assert restored.size() == expected
    finally:
        restored.close()


@pytest.mark.parametrize("state", ["missing", "installed", "damaged"])
@pytest.mark.parametrize("language", ["en", "ru"])
@pytest.mark.parametrize("accepted", [False, True])
def test_wikdict_checks_installed_package_and_downloads_only_after_confirmation(
    window, app, monkeypatch, wikdict_package, state, language, accepted
):
    from functools import partial

    from test_wikdict import download_session

    from cambridge_audio import wikdict

    spec, content = wikdict_package
    directory = window.output_dir.parent / "dictionary"
    directory.mkdir()
    window.dictionary_dir = directory
    window.language = language
    path = wikdict.package_path(directory, spec)
    if state != "missing":
        path.write_bytes(content if state == "installed" else b"damaged")
    before = path.read_bytes() if path.exists() else None
    monkeypatch.setattr(gui, "PACKAGE", spec)
    installer = Mock(
        wraps=partial(wikdict.install_dictionary, package=spec, session=download_session(content))
    )
    monkeypatch.setattr(gui, "install_dictionary", installer)
    question = Mock(
        return_value=QMessageBox.StandardButton.Yes if accepted else QMessageBox.StandardButton.No
    )
    monkeypatch.setattr(gui.QMessageBox, "question", question)
    window.install_wikdict()
    wait_until(app, lambda: window._dictionary_worker is None)
    text = question.call_args.args[2]
    expected = {
        ("missing", "en"): "Install the English–Russian",
        ("missing", "ru"): "Установить англо-русский",
        ("installed", "en"): "already installed and verified",
        ("installed", "ru"): "уже установлен и прошёл проверку",
        ("damaged", "en"): "is damaged",
        ("damaged", "ru"): "повреждён",
    }
    assert expected[state, language] in text
    assert spec.describe(language) in text
    assert spec.license_url in text
    assert question.call_args.args[-1] == QMessageBox.StandardButton.No
    if accepted:
        installer.assert_called_once()
        assert path.read_bytes() == content
    else:
        installer.assert_not_called()
        assert (path.read_bytes() if path.exists() else None) == before
    assert window.dictionary_button.isEnabled()


def test_repeated_wikdict_click_rechecks_disk_and_does_not_download_implicitly(
    window, app, monkeypatch, wikdict_package
):
    from functools import partial

    from test_wikdict import download_session

    from cambridge_audio import wikdict

    spec, content = wikdict_package
    window.dictionary_dir = window.output_dir.parent / "dictionary"
    monkeypatch.setattr(gui, "PACKAGE", spec)
    installer = Mock(
        wraps=partial(wikdict.install_dictionary, package=spec, session=download_session(content))
    )
    monkeypatch.setattr(gui, "install_dictionary", installer)
    question = Mock(return_value=QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(gui.QMessageBox, "question", question)
    window.install_wikdict()
    wait_until(app, lambda: window._dictionary_worker is None)
    installer.assert_called_once()
    question.return_value = QMessageBox.StandardButton.No
    window.install_wikdict()
    assert "already installed and verified" in question.call_args.args[2]
    assert installer.call_count == 1
    wikdict.package_path(window.dictionary_dir, spec).write_bytes(b"damaged externally")
    window.install_wikdict()
    assert "is damaged" in question.call_args.args[2]
    assert installer.call_count == 1
    assert window._dictionary_worker is None


def test_wikdict_read_error_does_not_offer_or_start_download(window, monkeypatch):
    question, installer = Mock(), Mock()
    monkeypatch.setattr(gui.QMessageBox, "question", question)
    monkeypatch.setattr(gui, "install_dictionary", installer)
    monkeypatch.setattr(gui, "validate_package", Mock(side_effect=PermissionError("read denied")))
    window.install_wikdict()
    assert "read denied" in window.status_label.text()
    question.assert_not_called()
    installer.assert_not_called()
    assert window.dictionary_button.isEnabled()


@pytest.mark.parametrize("language", ["en", "ru"])
def test_russian_translation_block_ignores_old_language_setting_and_preserves_cache(
    window, app, monkeypatch, client, mp3, language
):
    from cambridge_audio.library import read_recording, save_metadata
    from cambridge_audio.translations import cached_translation, edit_translation

    window.output_dir.mkdir()
    path = window.output_dir / "hello.us.mp3"
    path.write_bytes(mp3)
    save_metadata(Recording("hello", "us", path, "", "English definition"), ("bonjour",), "french")
    edit_translation(read_recording(path), "french", "mon texte")
    french_cache = read_recording(path).translation_cache
    window.settings.setValue("language", language)
    window.settings.setValue("translation_language", "french")
    client.translations = Mock(return_value=("привет",))
    monkeypatch.setattr(gui, "CambridgeClient", lambda **kwargs: client)
    restarted = gui.MainWindow(window.settings)
    try:
        restarted.show()
        app.processEvents()
        assert restarted.translation_language == "russian"
        assert not hasattr(restarted, "translation_language_edit")
        assert restarted.definition_label.text() == "English definition"
        assert (
            "не установлен" if language == "ru" else "not installed"
        ) in restarted.dictionary_status_label.text()
        assert read_recording(path).translation_cache == french_cache
        restarted.translation_check.setChecked(True)
        wait_until(app, lambda: restarted._translation_worker is None)
        assert "привет" in restarted.translation_label.text()
        saved = read_recording(path)
        assert cached_translation(saved, "french").texts == ("mon texte",)
        assert all(result in saved.translation_cache for result in french_cache)
        restarted.translation_check.setChecked(False)
        assert restarted.translation_label.isHidden()
        assert restarted.definition_label.text() == "English definition"
        client.translations.assert_called_once_with("hello", "russian")
    finally:
        restarted.close()


def test_russian_translation_block_keyboard_focus_follows_layout(window, app):
    window.accent_combo.setFocus()
    QTest.keyClick(window.accent_combo, Qt.Key.Key_Tab)
    if window.combine_check.isEnabled():
        assert window.combine_check.hasFocus()
        QTest.keyClick(window.combine_check, Qt.Key.Key_Tab)
    assert window.translation_check.hasFocus()
    QTest.keyClick(window.translation_check, Qt.Key.Key_Tab)
    assert window.dictionary_button.hasFocus()

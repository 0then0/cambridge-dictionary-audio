"""Exercise desktop behavior offscreen with isolated settings and mocked HTTP."""

import os
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
        assert restored.translation_label.text() == "привет"
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
        assert restored.translation_label.text() == "привет"
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
    assert window.translation_label.text() == "привет"
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
    assert window.translation_label.text() == "привет"
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
    assert window.translation_label.text() == "привет"
    assert read_recording(path).translation_language == "russian"
    assert path.read_bytes() == mp3
    window.translation_check.click()
    assert window.translation_label.isHidden()
    window.translation_check.click()
    assert window.translation_label.text() == "привет"
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
    assert window.translation_label.text() == "привет"
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
    assert window.translation_label.text() == "Translation: offline"
    app.processEvents()
    assert client.translations.call_count == 1
    window.translation_check.click()
    window.translation_check.click()
    wait_until(app, lambda: window._translation_worker is None)
    assert window.translation_label.text() == "привет"
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
        assert window.translation_label.text() == "мир"
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

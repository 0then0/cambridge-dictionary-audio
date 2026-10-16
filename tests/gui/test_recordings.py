"""Exercise desktop behavior offscreen with isolated settings and mocked HTTP."""

import os
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from tests.helpers import response

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6", reason="Install the gui group to run desktop tests")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtMultimedia import QAudioDevice  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QMessageBox  # noqa: E402

from cambridge_audio.gui import app as gui  # noqa: E402
from cambridge_audio.gui import workers
from cambridge_audio.service import Recording  # noqa: E402
from tests.gui.helpers import wait_until


def test_enter_downloads_us_without_blocking_ui(window, app, monkeypatch, client, html, mp3):
    client.session.get.side_effect = [response(html), response(mp3)]
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
    window.word_edit.setText("hello")
    window.start_download()
    wait_until(app, lambda: window._worker is None)
    assert "403" in window.status_label.text()
    assert window.status_label.property("severity") == "error"
    assert window.download_button.isEnabled()
    assert not window.play_button.isEnabled()


def test_timeout_has_a_friendly_russian_message(window, app, monkeypatch, client):
    client.session.get.side_effect = requests.Timeout("internal-network-detail")
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
    window.word_edit.setText("hello")
    window.start_download(force=True)
    wait_until(app, lambda: window._worker is None)
    assert destination.read_bytes() == mp3


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
    monkeypatch.setattr(workers, "CambridgeClient", client)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
    monkeypatch.setattr(workers, "save_metadata", Mock(side_effect=OSError("disk full")))
    window.word_edit.setText("hello")
    window.start_download()
    wait_until(app, lambda: window._worker is None)
    assert window.selected_recording().path.read_bytes() == mp3
    assert window.play_button.isEnabled()
    assert window.library_combo.count() == 1
    assert window.status_label.text() == "Audio saved. Details could not be saved: disk full"


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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kw: client)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
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

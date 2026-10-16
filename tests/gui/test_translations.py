"""Exercise desktop behavior offscreen with isolated settings and mocked HTTP."""

import os
from unittest.mock import Mock

import pytest

from tests.helpers import response

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6", reason="Install the gui group to run desktop tests")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QMessageBox  # noqa: E402

from cambridge_audio.gui import app as gui  # noqa: E402
from cambridge_audio.gui import workers
from cambridge_audio.service import Recording  # noqa: E402
from tests.gui.helpers import wait_until


def test_translation_checkbox_toggles_saved_translation_without_network(window, monkeypatch, mp3):
    from cambridge_audio.library import save_metadata

    window.output_dir.mkdir()
    path = window.output_dir / "hello.us.mp3"
    path.write_bytes(mp3)
    save_metadata(Recording("hello", "us", path, "heˈloʊ", "a greeting"), ("привет",), "russian")
    metadata = path.with_suffix(".json").read_bytes()
    client = Mock()
    monkeypatch.setattr(workers, "CambridgeClient", client)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kw: client)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kw: client)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kw: client)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kw: client)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
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


@pytest.mark.parametrize("state", ["missing", "installed", "damaged"])
@pytest.mark.parametrize("language", ["en", "ru"])
@pytest.mark.parametrize("accepted", [False, True])
def test_wikdict_checks_installed_package_and_downloads_only_after_confirmation(
    window, app, monkeypatch, wikdict_package, state, language, accepted
):
    from functools import partial

    from cambridge_audio import wikdict
    from tests.helpers import download_session

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
    monkeypatch.setattr(workers, "install_dictionary", installer)
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

    from cambridge_audio import wikdict
    from tests.helpers import download_session

    spec, content = wikdict_package
    window.dictionary_dir = window.output_dir.parent / "dictionary"
    monkeypatch.setattr(gui, "PACKAGE", spec)
    installer = Mock(
        wraps=partial(wikdict.install_dictionary, package=spec, session=download_session(content))
    )
    monkeypatch.setattr(workers, "install_dictionary", installer)
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
    monkeypatch.setattr(workers, "install_dictionary", installer)
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
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
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

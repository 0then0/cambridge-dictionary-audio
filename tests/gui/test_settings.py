"""Exercise desktop behavior offscreen with isolated settings and mocked HTTP."""

import os
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6", reason="Install the gui group to run desktop tests")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QMessageBox  # noqa: E402

from cambridge_audio.gui import app as gui  # noqa: E402


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


def test_colour_cancel_and_reset_preserve_other_settings(window, app, monkeypatch):
    from PySide6.QtGui import QColor, QPalette

    from cambridge_audio.gui.preferences import QColorDialog
    from cambridge_audio.gui.theme import COLORS

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

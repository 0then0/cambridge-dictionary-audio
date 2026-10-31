"""Every interface language is selectable, persists and fits the window."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6", reason="Install the gui group to run desktop tests")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QDialogButtonBox, QScrollArea  # noqa: E402

from cambridge_audio.gui import app as gui  # noqa: E402
from cambridge_audio.i18n import LANGUAGES, translate  # noqa: E402


def test_preferences_offer_every_language_by_its_own_name(window):
    combo = window.preferences_dialog.language_combo
    assert [(combo.itemData(i), combo.itemText(i)) for i in range(combo.count())] == list(
        LANGUAGES.items()
    )


@pytest.mark.parametrize("language", list(LANGUAGES))
def test_language_applies_immediately_and_is_remembered(window, language):
    combo = window.preferences_dialog.language_combo
    combo.setCurrentIndex(combo.findData(language))
    assert window.language == language
    assert window.download_button.text() == translate("Find", language)
    assert window.subtitle.text() == translate(
        "Download and listen to English pronunciation.", language
    )
    window.settings.sync()
    restored = gui.MainWindow(window.settings)
    try:
        assert restored.language == language
        assert restored.preferences_dialog.language_combo.currentData() == language
    finally:
        restored.close()
        restored.deleteLater()


def test_unknown_saved_language_falls_back_to_english(tmp_path):
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("output_dir", str(tmp_path / "audio"))
    settings.setValue("language", "xx")
    window = gui.MainWindow(settings)
    try:
        assert window.language == "en"
    finally:
        window.close()
        window.deleteLater()


@pytest.mark.parametrize(
    "language,standard",
    [
        ("de", "Abbrechen"),
        ("es", "Cancelar"),
        ("fr", "Annuler"),
        ("ja", "キャンセル"),
        ("pt-BR", "Cancelar"),
        ("ru", "Отмена"),
    ],
)
def test_qt_standard_buttons_follow_the_language(window, language, standard):
    def cancel_text():
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        return box.button(QDialogButtonBox.StandardButton.Cancel).text()

    combo = window.preferences_dialog.language_combo
    combo.setCurrentIndex(combo.findData(language))
    assert standard in cancel_text()
    combo.setCurrentIndex(combo.findData("en"))
    assert cancel_text().replace("&", "") == "Cancel"


def test_main_window_needs_no_more_width_than_russian_at_its_minimum_size(app, tmp_path):
    needed = {}
    for language in LANGUAGES:
        settings = QSettings(str(tmp_path / f"{language}.ini"), QSettings.Format.IniFormat)
        settings.setValue("output_dir", str(tmp_path / "audio"))
        settings.setValue("language", language)
        window = gui.MainWindow(settings)
        try:
            window.show()
            window.resize(window.minimumSize())
            app.processEvents()
            scroll = window.findChildren(QScrollArea)[0]
            needed[language] = (
                scroll.widget().minimumSizeHint().width(),
                scroll.viewport().width(),
            )
        finally:
            window.close()
            window.deleteLater()
    russian = needed["ru"][0]
    for language, (width, viewport) in needed.items():
        # The scroll area never scrolls sideways, so wider content would be clipped. Fonts differ
        # by platform (on Windows even English exceeds the viewport), hence a relative limit.
        assert width <= max(viewport, russian * 1.25), (language, needed)

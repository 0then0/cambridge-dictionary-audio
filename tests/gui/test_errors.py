"""Errors in all desktop operations have opt-in, plain-text diagnostics."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6", reason="Install the gui group to run desktop tests")

from cambridge_audio.dictionary import SelectionRequired, variants  # noqa: E402
from cambridge_audio.translations import TranslationOption, TranslationResult  # noqa: E402
from tests.core.test_errors import RAW_TIMEOUT  # noqa: E402
from tests.core.test_shared_audio import bank  # noqa: E402


@pytest.mark.parametrize("language", ["en", "ru"])
@pytest.mark.parametrize(
    "error",
    [
        RAW_TIMEOUT,
        PermissionError("/private/secret"),
        RuntimeError("<b>implementation failure</b>"),
    ],
)
def test_desktop_error_details_are_hidden_until_expanded(window, language, error):
    window.language = language
    window._retranslate()
    window._status("Error: {error}", severity="error", error=error)
    assert str(error) not in window.status_label.text()
    assert "https://" not in window.status_label.text()
    assert window.error_details_button.isVisible()
    layout = window.status_label.parentWidget().layout()
    assert layout.indexOf(window.error_summary_label) == layout.indexOf(window.status_label) + 1
    assert (
        layout.indexOf(window.error_details_button)
        == layout.indexOf(window.error_summary_label) + 1
    )
    assert (
        layout.indexOf(window.error_details_text) == layout.indexOf(window.error_details_button) + 1
    )
    assert not window.error_details_text.isVisible()
    window.error_details_button.click()
    assert window.error_details_text.isVisible()
    assert str(error) in window.error_details_text.toPlainText()
    window._status("Error: {error}", severity="error", error="a different internal error")
    assert not window.error_details_text.isVisible()
    assert str(error) not in window.error_details_text.toPlainText()
    window._status("Recording saved.")
    assert not window.error_details_button.isVisible()
    assert not window.error_details_text.toPlainText()


def test_preview_translation_fallback_keeps_translation_and_hides_raw_error(window):
    entries = bank()
    result = TranslationResult(
        "russian",
        entries[0].sense_id,
        "WikDict",
        (TranslationOption("personal", ("банк",), matched=True),),
        error=RAW_TIMEOUT,
    )
    window.translation_check.setChecked(True)
    window._preview_translations[entries[0].sense_id] = result
    window._selection_word = "bank"
    window._choose_variant(SelectionRequired(variants(entries), entries))
    text = window.translation_label.text()
    assert "банк" in text and "WikDict" in text
    assert "HTTPSConnectionPool" not in text
    assert "too long" in text
    assert "too long" in window.error_summary_label.text()
    assert window.error_summary_label.isVisible()
    assert window.error_details_button.isVisible()
    window.error_details_button.click()
    assert RAW_TIMEOUT in window.error_details_text.toPlainText()
    assert result.error == RAW_TIMEOUT  # Presentation does not rewrite cached diagnostics.
    window.translation_check.setChecked(False)
    assert not window.error_details_button.isVisible()

"""Inline selection and disposable playback must not mix collection meanings."""

import os
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6", reason="Install the gui group to run desktop tests")

from cambridge_audio.dictionary import SelectionRequired, dictionary_url, parse_entries, variants  # noqa: E402
from cambridge_audio.gui import workers  # noqa: E402
from cambridge_audio.library import scan_recordings  # noqa: E402
from tests.core.test_shared_audio import AUDIO, BANK  # noqa: E402
from tests.gui.helpers import wait_until  # noqa: E402
from tests.helpers import response  # noqa: E402


def test_inline_two_meanings_preview_then_save_reuses_one_audio(window, app, monkeypatch, client):
    client.session.get.side_effect = [response(BANK), response(AUDIO), response(BANK)]
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
    monkeypatch.setattr(window.player, "play", Mock())
    window.word_edit.setText("bank")
    window.download_button.click()
    wait_until(app, lambda: window._worker is None)
    assert window.meaning_list.isVisible()
    assert window.meaning_list.count() == 3  # POS heading, then two meanings.
    assert not scan_recordings(window.output_dir)
    assert not window.audio_combo.isVisible()
    assert window.definition_label.text() == "money"
    assert not window.edit_translation_button.isEnabled()
    window.toggle_playback()
    wait_until(app, lambda: window._worker is None)
    assert not scan_recordings(window.output_dir)
    window.save_button.click()
    wait_until(app, lambda: window._worker is None)
    assert not window.meaning_list.isVisible()
    assert not window.save_button.isVisible()
    assert not window._lookup_entries
    assert window.selected_recording().definition == "money"
    window.variant_button.click()
    wait_until(app, lambda: window._worker is None)
    assert window.meaning_list.isVisible()
    window.meaning_list.setCurrentRow(2)
    assert window.definition_label.text() == "river"
    assert not window.edit_translation_button.isEnabled()
    assert window._selected_saved() is None
    window.save_button.click()
    wait_until(app, lambda: window._worker is None)
    saved = scan_recordings(window.output_dir)
    assert len(saved) == 2
    assert len({s.recording.path for s in saved}) == 1
    assert client.session.get.call_count == 3  # Two lookups and one reusable preview.
    assert window.library_combo.count() == 2
    assert not window.meaning_list.isVisible()
    assert not window.save_button.isVisible()
    assert window.selected_recording().definition == "river"


def test_inline_audio_alternatives_keep_equal_ipa_and_update_selection(window):
    html = BANK.replace("</audio>", '</audio><audio><source src="/media/other.mp3"></audio>')
    entries = parse_entries(html, dictionary_url("bank"))
    window._selection_word = "bank"
    window._choose_variant(SelectionRequired(variants(entries), entries))
    assert window.audio_combo.count() == 2
    assert window.audio_combo.isVisible()
    one = window._current_choice()
    window.audio_combo.setCurrentIndex(1)
    two = window._current_choice()
    assert one.pronunciation.ipa == two.pronunciation.ipa
    assert one.pronunciation.url != two.pronunciation.url
    assert one.entry.sense_id == two.entry.sense_id


def test_theme_change_keeps_current_unsaved_meaning(window):
    entries = parse_entries(BANK, dictionary_url("bank"))
    window._selection_word = "bank"
    window._choose_variant(SelectionRequired(variants(entries), entries))
    window.meaning_list.setCurrentRow(2)
    window.settings.setValue("theme", "dark")
    window._preferences_changed()
    assert window.result_title.text() == "bank"
    assert window.definition_label.text() == "river"
    assert window.play_button.isEnabled()


@pytest.mark.parametrize("language,part", [("en", "noun"), ("ru", "существительное")])
def test_unsaved_meaning_translation_options_use_readable_gui_format(window, language, part):
    from cambridge_audio.translations import TranslationOption, TranslationResult

    entries = parse_entries(BANK, dictionary_url("bank"))
    result = TranslationResult(
        "russian",
        entries[0].sense_id,
        "Cambridge",
        (
            TranslationOption(
                "3f1b216547c4a33a95fd8793", ("банк",), "a financial institution", "noun"
            ),
            TranslationOption(
                "ede045b9d569d1678edb3af1", ("берег",), "land beside a river", "noun"
            ),
        ),
    )
    window.language = language
    window.translation_check.setChecked(True)
    window._selection_word = "bank"
    window._preview_translations[entries[0].sense_id] = result
    window._choose_variant(SelectionRequired(variants(entries), entries))

    text = window.translation_label.text()
    assert window.translation_label.isVisible()
    assert f"• банк · {part}\n  a financial institution" in text
    assert f"\n\n• берег · {part}\n  land beside a river" in text
    assert all(option.id not in text for option in result.options)
    assert text == result.format(language, show_ids=False)


def test_meaning_categories_are_distinct_and_not_selectable(window):
    from PySide6.QtCore import Qt

    entries = parse_entries(BANK, dictionary_url("bank"))
    window._choose_variant(SelectionRequired(variants(entries), entries))
    heading = window.meaning_list.item(0)
    category = window.meaning_list.itemWidget(heading)
    assert category.text() == "noun"
    assert category.objectName() == "meaning-category"
    assert category.font().bold()
    assert not heading.flags() & Qt.ItemFlag.ItemIsSelectable
    assert heading.sizeHint().height() >= category.sizeHint().height()


def test_failed_new_search_cannot_save_previous_word_meaning(window, app, monkeypatch, client):
    import requests

    client.session.get.side_effect = [requests.Timeout("timeout"), response(AUDIO)]
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
    entries = parse_entries(BANK, dictionary_url("bank"))
    window._selection_word = "bank"
    window._choose_variant(SelectionRequired(variants(entries), entries))
    window.word_edit.setText("lead")
    window.start_download(select_only=True)
    wait_until(app, lambda: window._worker is None)
    assert not window.meaning_list.isVisible()
    assert not window.save_button.isVisible()
    assert window._current_choice() is None
    window.save_choice()
    assert not scan_recordings(window.output_dir)
    assert client.session.get.call_count == 1

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
    assert window.edit_translation_button.isEnabled()
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
    assert window.edit_translation_button.isEnabled()
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


@pytest.mark.parametrize("language", ["en", "ru"])
def test_unsaved_unmatched_translation_hides_candidates_until_requested(window, language):
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
    assert window._t("No automatic translation match for this meaning.") in text
    assert "банк" not in text and "берег" not in text
    assert window.select_translation_button.isVisible()
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


@pytest.mark.parametrize("mode", ["automatic", "choose", "edit", "unresolved"])
def test_translation_is_resolved_before_save_and_keeps_the_preview(
    window, app, monkeypatch, client, mode
):
    from cambridge_audio.gui import app as gui
    from cambridge_audio.library import read_recording
    from cambridge_audio.translations import cached_translation
    from tests.helpers import BANK_BILINGUAL_HTML, BANK_FINANCIAL_DEFINITION

    definition = BANK_FINANCIAL_DEFINITION if mode == "automatic" else "a different definition"
    entries = parse_entries(BANK.replace(">money<", f">{definition}<"), dictionary_url("bank"))
    client.session.get.side_effect = [response(BANK_BILINGUAL_HTML), response(AUDIO)]
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kw: client)
    window.translation_check.setChecked(True)
    window._selection_word = "bank"
    window._choose_variant(SelectionRequired(variants(entries), entries))
    wait_until(app, lambda: window._translation_worker is None)
    assert not scan_recordings(window.output_dir)
    if mode == "automatic":
        assert "банк" in window.translation_label.text()
        assert "берег" not in window.translation_label.text()
        assert "занос" not in window.translation_label.text()
        assert not window.select_translation_button.isVisible()
    else:
        assert "банк" not in window.translation_label.text()
        assert window.select_translation_button.isVisible()
        assert window.save_button.isEnabled()
        if mode == "choose":

            def choose(dialog):
                assert "банк" in dialog.comboBoxItems()[0]
                dialog.setTextValue(dialog.comboBoxItems()[0])
                return gui.ChoiceDialog.DialogCode.Accepted

            monkeypatch.setattr(gui.ChoiceDialog, "exec", choose)
            window.select_translation_button.click()
        elif mode == "edit":
            monkeypatch.setattr(gui.QInputDialog, "getMultiLineText", lambda *a: ("мой банк", True))
            window.edit_translation_button.click()
    window.save_button.click()
    wait_until(app, lambda: window._worker is None and window._translation_worker is None)
    saved = read_recording(window.selected_recording().reference)
    result = cached_translation(saved, "russian")
    expected = () if mode == "unresolved" else ("мой банк",) if mode == "edit" else ("банк",)
    assert result.texts == expected
    assert len(scan_recordings(window.output_dir)) == 1
    assert client.session.get.call_count == 2  # One translation request and one MP3.
    if mode == "edit":
        assert result.source == "User"
    if mode == "choose":
        assert result.selected_id
    assert "берег" not in window.translation_label.text()


def test_personal_preview_survives_translation_arriving_after_edit(
    window, app, monkeypatch, client
):
    from threading import Event

    from cambridge_audio.gui import app as gui
    from cambridge_audio.translations import TranslationOption, cached_translation

    entered, release = Event(), Event()
    entries = parse_entries(BANK, dictionary_url("bank"))

    def fetch(*args):
        entered.set()
        assert release.wait(5)
        return (TranslationOption("dictionary", ("банк",), "money", "noun"),)

    client.translation_options = Mock(side_effect=fetch)
    client.session.get.return_value = response(AUDIO)
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kw: client)
    monkeypatch.setattr(gui.QInputDialog, "getMultiLineText", lambda *a: ("мой перевод", True))
    window.translation_check.setChecked(True)
    window._selection_word = "bank"
    window._choose_variant(SelectionRequired(variants(entries), entries))
    try:
        wait_until(app, entered.is_set)
        window.edit_translation_button.click()
        assert "мой перевод" in window.translation_label.text()
    finally:
        release.set()
    wait_until(app, lambda: window._translation_worker is None)
    assert "мой перевод" in window.translation_label.text()
    window.save_button.click()
    wait_until(app, lambda: window._worker is None)
    result = cached_translation(scan_recordings(window.output_dir)[0], "russian")
    assert result.source == "User" and result.texts == ("мой перевод",)
    client.translation_options.assert_called_once()


@pytest.mark.parametrize("mode,expected", [("edit", "мой банк"), ("choose", "банк")])
def test_hiding_translation_must_not_discard_personal_text_on_save(
    window, app, monkeypatch, client, mode, expected
):
    from cambridge_audio.gui import app as gui
    from cambridge_audio.gui import workers
    from cambridge_audio.translations import (
        TranslationOption,
        TranslationResult,
        cached_translation,
    )
    from tests.core.test_shared_audio import bank
    from tests.gui.helpers import wait_until

    entries = bank()
    window._preview_translations[entries[0].sense_id] = TranslationResult(
        "russian",
        entries[0].sense_id,
        "Cambridge",
        (TranslationOption("candidate", ("банк",), "unknown wording", "noun"),),
        alignment="unmatched",
    )
    client.session.get.return_value = response(AUDIO)
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kw: client)
    monkeypatch.setattr(gui.QInputDialog, "getMultiLineText", lambda *a: ("мой банк", True))
    window.translation_check.setChecked(True)
    window._selection_word = "bank"
    window._choose_variant(SelectionRequired(variants(entries), entries))
    if mode == "edit":
        window.edit_translation_button.click()
    else:
        monkeypatch.setattr(
            gui.ChoiceDialog, "exec", lambda dialog: gui.ChoiceDialog.DialogCode.Accepted
        )
        window.select_translation_button.click()
    assert expected in window.translation_label.text()
    window.translation_check.setChecked(False)
    window.save_button.click()
    wait_until(app, lambda: window._worker is None and window._translation_worker is None)
    records = scan_recordings(window.output_dir)
    assert len(records) == 1
    result = cached_translation(records[0], "russian")
    assert result is not None and result.texts == (expected,)
    assert not window.translation_label.isVisible()
    assert client.session.get.call_count == 1

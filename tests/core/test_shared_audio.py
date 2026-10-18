"""Collection meanings and audio remain independent across edits and restarts."""

import hashlib
import json
from dataclasses import replace
from unittest.mock import Mock

import pytest

from cambridge_audio import library
from cambridge_audio.dictionary import Pronunciation, dictionary_url, parse_entries, variants
from cambridge_audio.library import delete_recording, read_recording, scan_recordings, valid_audio
from cambridge_audio.service import download_recordings
from cambridge_audio.translations import cached_translation, edit_translation
from tests.helpers import response

BANK = """<div class="entry-body__el" id="bank-noun"><div class="pos-header">
<span class="hw">bank</span><span class="pos">noun</span>
<span class="us dpron-i"><span class="ipa">bæŋk</span>
<audio><source src="/media/bank.mp3"></audio></span></div>
<div class="def-block" data-wl-senseid="money"><div class="def ddef_d">money</div></div>
<div class="def-block" data-wl-senseid="river"><div class="def ddef_d">river</div></div></div>"""
AUDIO = b"ID3one URL always has the same content"


def bank():
    return parse_entries(BANK, dictionary_url("bank"))


def save(client, directory, choice, entries=None, **kwargs):
    return download_recordings(
        client, "bank", directory, entries=entries or bank(), variant_id=choice.id, **kwargs
    ).recordings[0]


def test_two_meanings_one_request_one_mp3_and_independent_translations(client, tmp_path):
    choices = variants(bank())
    client.session.get.return_value = response(AUDIO)
    first = save(client, tmp_path, choices[0])
    edit_translation(read_recording(first.reference), "russian", "банк")
    second = save(client, tmp_path, choices[1])
    assert first.path == second.path
    assert first.id != second.id
    assert first.reference != second.reference
    assert client.session.get.call_count == 1
    assert len(list(tmp_path.glob("*.mp3"))) == 1
    assert len(scan_recordings(tmp_path)) == 2
    assert cached_translation(read_recording(first.reference), "russian").texts == ("банк",)
    assert cached_translation(read_recording(second.reference), "russian") is None
    assert read_recording(first.path) is None  # MP3 alone cannot choose a meaning.


def test_restart_reuses_audio_and_local_ids_after_source_content_changes(client, tmp_path):
    choices = variants(bank())
    client.session.get.return_value = response(AUDIO)
    first = save(client, tmp_path, choices[0])
    edit_translation(read_recording(first.reference), "russian", "personal")
    changed = parse_entries(
        BANK.replace(">money<", ">financial institution<").replace(
            "</audio>", '</audio><audio><source src="/media/extra.mp3"></audio>'
        ),
        dictionary_url("bank"),
    )
    new_choice = next(v for v in variants(changed) if v.id == choices[0].id)
    assert new_choice.entry.entry_id == choices[0].entry.entry_id
    assert new_choice.entry.sense_id == choices[0].entry.sense_id
    client.session.get = Mock(side_effect=AssertionError("No audio request after restart"))
    updated = save(client, tmp_path, new_choice, changed)
    assert updated.id == first.id
    assert updated.definition == "financial institution"
    assert cached_translation(read_recording(updated.reference), "russian").texts == ("personal",)


@pytest.mark.parametrize("damage", [None, b"<html>error</html>", b"ID3silently changed bytes"])
def test_missing_or_damaged_managed_audio_is_restored(client, tmp_path, damage):
    choice = variants(bank())[0]
    client.session.get.return_value = response(AUDIO)
    record = save(client, tmp_path, choice)
    if damage is None:
        record.path.unlink()
    else:
        record.path.write_bytes(damage)
    assert not valid_audio(record)
    assert len(scan_recordings(tmp_path)) == 1
    restored = save(client, tmp_path, choice)
    assert restored.path.read_bytes() == AUDIO
    assert restored.id == record.id
    assert client.session.get.call_count == 2


def test_delete_one_shared_record_keeps_other_and_media(client, tmp_path):
    client.session.get.return_value = response(AUDIO)
    one, two = [save(client, tmp_path, choice) for choice in variants(bank())]
    delete_recording(one)
    assert not one.reference.exists()
    assert two.path.read_bytes() == AUDIO
    assert [s.recording.id for s in scan_recordings(tmp_path)] == [two.id]


def test_same_ipa_different_urls_not_deduplicated(client, tmp_path):
    entries = bank()
    other = Pronunciation("us", "https://dictionary.cambridge.org/media/other.mp3", "bæŋk")
    entries = (replace(entries[0], pronunciations=entries[0].pronunciations + (other,)),)
    choices = variants(entries)
    assert len(choices) == 2
    assert len({v.pronunciation.id for v in choices}) == 2
    client.session.get.side_effect = [response(AUDIO), response(b"ID3other recording")]
    records = [save(client, tmp_path, choice, entries) for choice in choices]
    assert records[0].path != records[1].path
    assert client.session.get.call_count == 2


def test_legacy_metadata_upgrades_atomically_preserving_local_export_ids(
    client, tmp_path, monkeypatch
):
    choice = variants(bank())[0]
    path = tmp_path / "bank--legacy.us.mp3"
    path.write_bytes(AUDIO)
    legacy_id = "c" * 24
    metadata = path.with_suffix(".json")
    old = dict(
        version=2,
        word="bank",
        ipa="bæŋk",
        definition="money",
        part_of_speech="noun",
        entry_id="old-entry",
        sense_id="old-sense",
        variant_id=legacy_id,
        audio_url=choice.pronunciation.url,
    )
    metadata.write_text(json.dumps(old))
    saved = edit_translation(read_recording(path), "russian", "my bank")
    before = metadata.read_bytes()
    original = library.os.replace
    monkeypatch.setattr(library.os, "replace", Mock(side_effect=OSError("disk full")))
    with pytest.raises(OSError):
        save(client, tmp_path, choice)
    assert metadata.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))
    monkeypatch.setattr(library.os, "replace", original)
    for _ in range(2):
        updated = save(client, tmp_path, choice)
        assert updated.id == legacy_id
        assert updated.sense_id == "old-sense"
        assert updated.source_sense_id == choice.entry.sense_id
        assert cached_translation(read_recording(updated.reference), "russian").texts == (
            "my bank",
        )
    assert saved.recording.id == updated.id
    client.session.get.assert_not_called()


def test_audio_source_does_not_depend_on_sense():
    one, two = variants(bank())
    assert one.id != two.id
    assert one.pronunciation.id == two.pronunciation.id
    assert hashlib.sha256(AUDIO).hexdigest()


def test_explicit_reassociation_of_fallback_keeps_collection_id_and_manual_translation(
    client, tmp_path
):
    from cambridge_audio.dictionary import SelectionRequired

    entries = parse_entries(BANK.replace(' data-wl-senseid="money"', ""), dictionary_url("bank"))
    choice = variants(entries)[0]
    client.session.get.return_value = response(AUDIO)
    record = save(client, tmp_path, choice, entries)
    edit_translation(read_recording(record.reference), "russian", "personal")
    changed = (replace(entries[0], definition="a rewritten meaning", sense_id="new-fallback"),)
    with pytest.raises(SelectionRequired) as required:
        download_recordings(client, "bank", tmp_path, entries=changed, target=record)
    assert required.value.target.id == record.id
    updated = download_recordings(
        client, "bank", tmp_path, entries=changed, target=record, variant_id=variants(changed)[0].id
    ).recordings[0]
    assert updated.id == record.id
    assert updated.definition == "a rewritten meaning"
    assert cached_translation(read_recording(updated.reference), "russian").texts == ("personal",)


def test_moving_collection_preserves_ids_and_audio(client, tmp_path):
    directory = tmp_path / "one"
    client.session.get.return_value = response(AUDIO)
    record = save(client, directory, variants(bank())[0])
    moved = tmp_path / "two"
    directory.rename(moved)
    restored = scan_recordings(moved)[0].recording
    assert restored.id == record.id
    assert restored.path.parent == moved
    assert valid_audio(restored)


def test_source_sense_ids_survive_block_reordering_without_block_ids():
    html = BANK.replace(' id="bank-noun"', "")
    other = html.replace('data-wl-senseid="money"', 'data-wl-senseid="tree"').replace(
        'data-wl-senseid="river"', 'data-wl-senseid="hill"'
    )
    old = parse_entries(html + other, dictionary_url("bank"))
    new = parse_entries(other + html, dictionary_url("bank"))
    assert {v.id for v in variants(old)} == {v.id for v in variants(new)}


def test_new_metadata_write_failure_leaves_no_unassociated_audio_and_can_retry(
    client, tmp_path, monkeypatch
):
    client.session.get.return_value = response(AUDIO)
    original = library.save_metadata
    monkeypatch.setattr(library, "save_metadata", Mock(side_effect=OSError("disk full")))
    with pytest.raises(OSError):
        save(client, tmp_path, variants(bank())[0])
    assert not list(tmp_path.glob("*.mp3"))
    monkeypatch.setattr(library, "save_metadata", original)
    record = save(client, tmp_path, variants(bank())[0])
    assert valid_audio(record)
    assert len(scan_recordings(tmp_path)) == 1


def test_legacy_sidecar_does_not_make_a_shared_mp3_unambiguous(client, tmp_path):
    choices = variants(bank())
    path = tmp_path / "bank.us.mp3"
    path.write_bytes(AUDIO)
    path.with_suffix(".json").write_text(
        json.dumps(
            {
                "version": 2,
                "word": "bank",
                "ipa": "bæŋk",
                "definition": "money",
                "part_of_speech": "noun",
                "sense_id": "old-money",
                "variant_id": "a" * 24,
                "audio_url": choices[0].pronunciation.url,
            }
        )
    )
    second = save(client, tmp_path, choices[1])
    assert second.path == path
    assert len(scan_recordings(tmp_path)) == 2
    assert read_recording(path) is None
    assert read_recording(path.with_suffix(".json")).recording.definition == "money"
    assert read_recording(second.reference).recording.definition == "river"
    client.session.get.assert_not_called()


def test_identical_fallback_definitions_remain_separate_ambiguous_choices():
    html = BANK.replace(' data-wl-senseid="money"', "").replace(' data-wl-senseid="river"', "")
    html = html.replace(">river<", ">money<")
    entries = parse_entries(html, dictionary_url("bank"))
    assert len(entries) == 2
    assert len(variants(entries)) == 2
    assert len({e.sense_id for e in entries}) == 2


@pytest.mark.parametrize("version", [1, 2])
def test_legacy_audio_reassociation_preserves_one_record_and_translations(
    client, tmp_path, version
):
    from cambridge_audio.anki import export_apkg

    original = tmp_path / "bank.us.mp3"
    original.write_bytes(AUDIO)
    identity = "c" * 24
    metadata = original.with_suffix(".json")
    metadata.write_text(
        json.dumps(
            {
                "version": version,
                "word": "bank",
                "ipa": "old",
                "definition": "money",
                "part_of_speech": "noun",
                "sense_id": "old-money",
                "variant_id": identity,
                "audio_url": bank()[0].pronunciations[0].url,
                "translations": ["мой банк"],
                "translation_language": "russian",
            }
        )
    )
    new_entry = replace(
        bank()[0],
        pronunciations=(
            Pronunciation("us", "https://dictionary.cambridge.org/media/new.mp3", "new"),
        ),
    )
    client.session.get.return_value = response(AUDIO)
    for _ in range(2):
        current = read_recording(metadata)
        updated = download_recordings(
            client,
            "bank",
            tmp_path,
            entries=(new_entry,),
            target=current.recording,
            variant_id=variants((new_entry,))[0].id,
        ).recordings[0]
        assert updated.reference == metadata
        assert updated.id == identity
        assert updated.path != original
        assert read_recording(metadata).translations == ("мой банк",)
        assert len(scan_recordings(tmp_path)) == 1
    assert original.read_bytes() == AUDIO
    assert client.session.get.call_count == 1
    assert export_apkg(scan_recordings(tmp_path), tmp_path / "export.apkg").is_file()


def test_legacy_reassociation_write_failure_preserves_original_and_retries(
    client, tmp_path, monkeypatch
):
    original = tmp_path / "bank.us.mp3"
    original.write_bytes(AUDIO)
    metadata = original.with_suffix(".json")
    metadata.write_text(
        json.dumps(
            {
                "version": 2,
                "word": "bank",
                "ipa": "old",
                "definition": "money",
                "variant_id": "c" * 24,
                "audio_url": bank()[0].pronunciations[0].url,
            }
        )
    )
    before = metadata.read_bytes()
    entry = replace(
        bank()[0],
        pronunciations=(
            Pronunciation("us", "https://dictionary.cambridge.org/media/new.mp3", "new"),
        ),
    )
    client.session.get.return_value = response(AUDIO)
    current = read_recording(metadata).recording
    with monkeypatch.context() as patch:
        patch.setattr(library.os, "replace", Mock(side_effect=OSError("disk full")))
        with pytest.raises(OSError):
            download_recordings(
                client,
                "bank",
                tmp_path,
                entries=(entry,),
                target=current,
                variant_id=variants((entry,))[0].id,
            )
    assert metadata.read_bytes() == before
    assert original.read_bytes() == AUDIO
    assert list(tmp_path.glob("*.mp3")) == [original]
    download_recordings(
        client,
        "bank",
        tmp_path,
        entries=(entry,),
        target=current,
        variant_id=variants((entry,))[0].id,
    )
    assert len(scan_recordings(tmp_path)) == 1
    assert read_recording(metadata).recording.id == current.id


def test_collection_reads_do_not_wait_for_audio_download(tmp_path):
    from threading import Event, Thread

    entered, release, read_done = Event(), Event(), Event()
    entry = bank()[0]
    client = Mock(language="en")
    failures = []

    def download(entries, accent, path, **kwargs):
        entered.set()
        if not release.wait(5):
            raise TimeoutError("test download was not released")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(AUDIO)
        return entries[0].pronunciations[0]

    client.download.side_effect = download

    def write():
        try:
            save(client, tmp_path, variants((entry,))[0], (entry,))
        except Exception as exc:
            failures.append(exc)

    def read():
        try:
            scan_recordings(tmp_path)
            read_recording(tmp_path / "missing.us.mp3")
            read_done.set()
        except Exception as exc:
            failures.append(exc)

    writer, reader = Thread(target=write), Thread(target=read)
    writer.start()
    try:
        assert entered.wait(3)
        reader.start()
        assert read_done.wait(1), "Collection reads blocked by network I/O"
    finally:
        release.set()
        writer.join(5)
        if reader.ident is not None:
            reader.join(5)
    assert not writer.is_alive() and not reader.is_alive()
    assert not failures
    assert len(scan_recordings(tmp_path)) == 1


def test_concurrent_meaning_saves_share_one_download(client, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    client.session.get.return_value = response(AUDIO)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(lambda choice: save(client, tmp_path, choice), variants(bank()))
        )
    assert results[0].path == results[1].path
    assert results[0].id != results[1].id
    assert len(scan_recordings(tmp_path)) == 2
    assert client.session.get.call_count == 1


def test_prepared_translation_is_saved_once_and_reused_for_another_accent(client, tmp_path):
    from cambridge_audio.translations import (
        TranslationOption,
        TranslationResult,
        cached_translation,
    )

    entries = bank()
    entries = (
        replace(
            entries[0],
            pronunciations=entries[0].pronunciations
            + (Pronunciation("uk", "https://dictionary.cambridge.org/media/bank-uk.mp3", "bæŋk"),),
        ),
    ) + entries[1:]
    prepared = TranslationResult(
        "russian",
        entries[0].sense_id,
        "User",
        (TranslationOption("confirmed", ("банк",), matched=True),),
    )
    client.session.get.return_value = response(AUDIO)
    client.translation_options = Mock(side_effect=AssertionError("Preview must be reused"))
    first = download_recordings(
        client,
        "bank",
        tmp_path,
        "us",
        entries=entries,
        sense_id=entries[0].sense_id,
        translation="russian",
        prepared_translation=prepared,
    )
    second = download_recordings(
        client,
        "bank",
        tmp_path,
        "uk",
        entries=entries,
        sense_id=entries[0].sense_id,
        translation="russian",
    )
    assert first.translations == second.translations == ("банк",)
    for record in (first.recordings[0], second.recordings[0]):
        result = cached_translation(read_recording(record.reference), "russian")
        assert result.source == "User" and result.texts == ("банк",)
    assert client.session.get.call_count == 2  # One file per accent, no translation requests.


def test_prepared_translation_cannot_leak_to_another_meaning(client, tmp_path):
    from cambridge_audio.translations import TranslationOption, TranslationResult

    entries = bank()
    prepared = TranslationResult(
        "russian",
        entries[0].sense_id,
        "User",
        (TranslationOption("money", ("банк",), matched=True),),
    )
    client.session.get.return_value = response(AUDIO)
    client.translation_options = Mock(return_value=())
    result = download_recordings(
        client,
        "bank",
        tmp_path,
        entries=entries,
        sense_id=entries[1].sense_id,
        translation="russian",
        prepared_translation=prepared,
    )
    assert not result.translations
    client.translation_options.assert_called_once()
    assert not any(
        t.source == "User" for t in read_recording(result.recordings[0].reference).translation_cache
    )


def test_personal_preview_for_new_accent_overrides_shared_automatic_translation(client, tmp_path):
    from cambridge_audio.translations import (
        TranslationOption,
        TranslationResult,
        persist_translation,
    )

    entries = bank()
    entries = (
        replace(
            entries[0],
            pronunciations=entries[0].pronunciations
            + (Pronunciation("uk", "https://dictionary.cambridge.org/media/uk.mp3", "bæŋk"),),
        ),
    )
    client.session.get.return_value = response(AUDIO)
    us = download_recordings(client, "bank", tmp_path, entries=entries).recordings[0]
    persist_translation(
        read_recording(us.reference),
        TranslationResult(
            "russian",
            us.sense_id,
            "Cambridge",
            (TranslationOption("auto", ("банк",), "money", "noun", matched=True),),
        ),
    )
    prepared = TranslationResult(
        "russian",
        entries[0].sense_id,
        "User",
        (TranslationOption("personal", ("мой банк",), matched=True),),
    )
    client.translation_options = Mock(side_effect=AssertionError("No new translation lookup"))
    uk = download_recordings(
        client,
        "bank",
        tmp_path,
        "uk",
        entries=entries,
        translation="russian",
        prepared_translation=prepared,
    ).recordings[0]
    for record in (us, uk):
        result = cached_translation(read_recording(record.reference), "russian")
        assert result.source == "User" and result.texts == ("мой банк",)


@pytest.mark.parametrize("prior_source", ["Cambridge", "User"])
def test_new_personal_preview_must_override_inherited_confirmed_source_choice(
    client, tmp_path, prior_source
):
    from cambridge_audio.translations import (
        TranslationOption,
        TranslationResult,
        persist_translation,
    )

    entries = bank()
    entries = (
        replace(
            entries[0],
            pronunciations=entries[0].pronunciations
            + (Pronunciation("uk", "https://dictionary.cambridge.org/media/uk.mp3", "bæŋk"),),
        ),
    )
    client.session.get.return_value = response(AUDIO)
    us = download_recordings(client, "bank", tmp_path, entries=entries).recordings[0]
    persist_translation(
        read_recording(us.reference),
        TranslationResult(
            "russian",
            us.sense_id,
            "Cambridge",
            (
                TranslationOption("money", ("банк",), "money", "noun"),
                TranslationOption("river", ("берег",), "river", "noun"),
            ),
            selected_id="money",
        ),
    )
    if prior_source == "User":
        edit_translation(read_recording(us.reference), "russian", "старый личный перевод")
    prepared = TranslationResult(
        "russian",
        entries[0].sense_id,
        "User",
        (TranslationOption("personal", ("мой банк",), matched=True),),
    )
    client.translation_options = Mock(side_effect=AssertionError("No lookup needed"))
    result = download_recordings(
        client,
        "bank",
        tmp_path,
        "uk",
        entries=entries,
        translation="russian",
        prepared_translation=prepared,
    )
    assert result.translations == ("мой банк",)


@pytest.mark.parametrize("late_action,expected", [("edit", "поздняя правка"), ("choose", "банк2")])
def test_prepared_translation_does_not_replace_a_choice_made_during_audio_download(
    client, tmp_path, monkeypatch, late_action, expected
):
    from cambridge_audio.translations import (
        TranslationOption,
        TranslationResult,
        persist_translation,
        select_translation,
    )

    entries = bank()
    entries = (
        replace(
            entries[0],
            pronunciations=entries[0].pronunciations
            + (Pronunciation("uk", "https://dictionary.cambridge.org/media/uk.mp3", "bæŋk"),),
        ),
    )
    client.session.get.return_value = response(AUDIO)
    us = download_recordings(client, "bank", tmp_path, entries=entries).recordings[0]
    persist_translation(
        read_recording(us.reference),
        TranslationResult(
            "russian",
            us.sense_id,
            "Cambridge",
            (
                TranslationOption("first", ("банк",), "money"),
                TranslationOption("second", ("банк2",), "money"),
            ),
            selected_id="first",
        ),
    )
    prepared = TranslationResult(
        "russian",
        entries[0].sense_id,
        "User",
        (TranslationOption("draft", ("черновик",), matched=True),),
    )
    download = client.download

    def change_during_download(*args, **kwargs):
        if late_action == "edit":
            edit_translation(read_recording(us.reference), "russian", expected)
        else:
            select_translation(read_recording(us.reference), "russian", "second")
        return download(*args, **kwargs)

    monkeypatch.setattr(client, "download", change_during_download)
    client.translation_options = Mock(side_effect=AssertionError("Must use the saved choice"))
    result = download_recordings(
        client,
        "bank",
        tmp_path,
        "uk",
        entries=entries,
        translation="russian",
        prepared_translation=prepared,
    )
    assert result.translations == (expected,)
    for saved in scan_recordings(tmp_path):
        assert cached_translation(saved, "russian").texts == (expected,)

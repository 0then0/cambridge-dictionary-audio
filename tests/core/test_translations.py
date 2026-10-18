from concurrent.futures import ThreadPoolExecutor
from functools import partial
from threading import Event
from unittest.mock import Mock

import pytest

from cambridge_audio import translations, wikdict
from cambridge_audio.dictionary import CambridgeBlockedError, CambridgeError
from cambridge_audio.library import read_recording, save_metadata
from cambridge_audio.service import Recording
from cambridge_audio.translations import (
    TranslationOption,
    TranslationResult,
    cached_translation,
    edit_translation,
    persist_translation,
    resolve_translation,
    select_translation,
)
from tests.helpers import download_session


def recording(tmp_path):
    path = tmp_path / "hello.us.mp3"
    path.write_bytes(b"ID3saved")
    record = Recording("hello", "us", path, "həˈləʊ", "a greeting", sense_id="greeting")
    save_metadata(record)
    return read_recording(path)


@pytest.mark.parametrize(
    "error", [None, CambridgeBlockedError("HTTP 403"), CambridgeError("offline")]
)
def test_cambridge_absent_or_unavailable_uses_local_fallback(
    tmp_path, wikdict_package, monkeypatch, error
):
    spec, content = wikdict_package
    directory = tmp_path / "dictionary"
    wikdict.install_dictionary(directory, package=spec, session=download_session(content))
    monkeypatch.setattr(translations, "lookup", partial(wikdict.lookup, package=spec))
    client = Mock()
    client.translation_options.side_effect = error
    client.translation_options.return_value = ()
    result = resolve_translation(client, recording(tmp_path), "russian", directory=directory)
    assert result.source == "WikDict"
    assert not result.texts  # Local gloss is not evidence for this Cambridge sense.
    assert result.alignment == "unmatched"
    assert "Cambridge match unverified" in result.display
    assert (str(error) in result.error) if error else not result.error


def test_installed_dictionary_and_saved_cache_are_offline(tmp_path, wikdict_package, monkeypatch):
    spec, content = wikdict_package
    directory = tmp_path / "dictionary"
    wikdict.install_dictionary(directory, package=spec, session=download_session(content))
    monkeypatch.setattr(translations, "lookup", partial(wikdict.lookup, package=spec))
    client = Mock()
    saved = recording(tmp_path)
    result = resolve_translation(client, saved, "russian", directory=directory, offline=True)
    saved = persist_translation(saved, result)
    client.translation_options.assert_not_called()
    monkeypatch.setattr(translations, "lookup", Mock(side_effect=AssertionError("cache hit")))
    assert resolve_translation(client, saved, "russian") == result
    client.translation_options.assert_not_called()


def test_edits_reset_restart_and_multiple_languages_sources(tmp_path):
    saved = recording(tmp_path)

    def result(language, source, text):
        return TranslationResult(
            language, "greeting", source, (TranslationOption(text, (text,), origin="fixture"),)
        )

    for value in (
        result("russian", "WikDict", "привет"),
        result("russian", "Cambridge", "здравствуйте"),
        result("french", "Cambridge", "bonjour"),
    ):
        saved = persist_translation(saved, value)
    saved = edit_translation(saved, "russian", "моя правка")
    saved = read_recording(saved.recording.path)
    assert cached_translation(saved, "russian").source == "User"
    client = Mock(side_effect=AssertionError("User edit precedes network"))
    assert resolve_translation(client, saved, "russian", refresh=True).texts == ("моя правка",)
    saved = persist_translation(saved, result("russian", "Cambridge", "обновлено"))
    assert cached_translation(saved, "russian").texts == ("моя правка",)
    saved = edit_translation(saved, "russian", None)
    assert cached_translation(saved, "russian").texts == ("обновлено",)
    assert cached_translation(saved, "french").texts == ("bonjour",)
    assert {t.source for t in saved.translation_cache if t.language == "russian"} == {
        "Cambridge",
        "WikDict",
    }
    save_metadata(saved.recording)  # A redownload does not erase caches.
    assert len(read_recording(saved.recording.path).translation_cache) == 3


def test_ambiguous_translation_requires_explicit_choice(tmp_path):
    saved = recording(tmp_path)
    result = TranslationResult(
        "russian",
        "greeting",
        "WikDict",
        (
            TranslationOption("one", ("привет",), "greeting"),
            TranslationOption("two", ("алло",), "on the phone"),
        ),
    )
    saved = persist_translation(saved, result)
    assert cached_translation(saved, "russian").texts == ()
    assert "on the phone" in cached_translation(saved, "russian").display
    saved = select_translation(saved, "russian", "two")
    assert cached_translation(read_recording(saved.recording.path), "russian").texts == ("алло",)


def test_late_response_preserves_edit_and_other_language(tmp_path):
    saved = recording(tmp_path)
    started, release = Event(), Event()

    def response():
        started.set()
        assert release.wait(5)
        return persist_translation(
            saved,
            TranslationResult(
                "russian", "greeting", "Cambridge", (TranslationOption("one", ("original",)),)
            ),
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(response)
        try:
            assert started.wait(5)
            edit_translation(saved, "russian", "personal")
            edit_translation(saved, "french", "bonjour")
        finally:
            release.set()
        current = future.result(5)
    assert cached_translation(current, "russian").texts == ("personal",)
    assert cached_translation(current, "french").texts == ("bonjour",)


def test_unknown_legacy_language_is_not_assumed_russian(tmp_path):
    saved = recording(tmp_path)
    save_metadata(saved.recording, ("bonjour",))
    saved = read_recording(saved.recording.path)
    assert saved.translations == ("bonjour",)
    assert cached_translation(saved, "russian") is None


def test_edit_is_scoped_to_sense_language_and_shared_between_accents(tmp_path):
    from dataclasses import replace

    first = recording(tmp_path)
    uk = replace(first.recording, accent="uk", path=tmp_path / "hello.uk.mp3")
    other = replace(first.recording, sense_id="other", path=tmp_path / "hello--other.us.mp3")
    for record in (uk, other):
        record.path.write_bytes(b"ID3saved")
        save_metadata(record)
    edit_translation(first, "russian", "personal")
    assert cached_translation(read_recording(uk.path), "russian").texts == ("personal",)
    assert cached_translation(read_recording(other.path), "russian") is None
    assert cached_translation(read_recording(uk.path), "french") is None
    edit_translation(first, "russian", None)
    assert cached_translation(read_recording(uk.path), "russian") is None


@pytest.mark.parametrize("accent", ["us", "uk"])
def test_new_pronunciation_inherits_sense_edits_and_reset_after_restart(tmp_path, accent):
    from dataclasses import replace

    original = recording(tmp_path)
    edit_translation(original, "russian", "personal")
    edit_translation(original, "french", "bonjour")
    new = replace(
        original.recording,
        accent=accent,
        path=tmp_path / f"hello--new.{accent}.mp3",
        variant_id="a" * 24,
    )
    new.path.write_bytes(b"ID3new")
    save_metadata(new)
    restarted = read_recording(new.path)
    client = Mock()
    assert resolve_translation(client, restarted, "russian").texts == ("personal",)
    assert cached_translation(restarted, "russian").source == "User"
    assert cached_translation(restarted, "french").texts == ("bonjour",)
    client.translation_options.assert_not_called()
    edit_translation(restarted, "russian", None)
    for path in (original.recording.path, new.path):
        saved = read_recording(path)
        assert cached_translation(saved, "russian") is None
        assert cached_translation(saved, "french").texts == ("bonjour",)


def test_legacy_edit_preserves_provenance_and_reset_after_redownload(tmp_path, client):
    from cambridge_audio.dictionary import Entry, Pronunciation
    from cambridge_audio.service import download_recordings
    from tests.helpers import response

    path = tmp_path / "hello.us.mp3"
    path.write_bytes(b"ID3old")
    old = Recording("hello", "us", path, "", "a greeting")
    save_metadata(old)
    automatic = TranslationResult(
        "russian", "", "Cambridge", (TranslationOption("original", ("dictionary",)),)
    )
    persist_translation(read_recording(path), automatic)
    edit_translation(read_recording(path), "russian", "personal")
    pronunciation = Pronunciation("us", "https://dictionary.cambridge.org/media/hello.mp3", "new")
    entry = Entry("hello", "a greeting", (pronunciation,), sense_id="greeting")
    client.session.get.return_value = response(b"ID3new")
    download_recordings(
        client,
        "hello",
        tmp_path,
        entries=(entry,),
        target=old,
        overwrite=True,
        on_recording=save_metadata,
        translation="russian",
    )
    restarted = read_recording(path)
    assert restarted.recording.sense_id == "greeting"
    assert cached_translation(restarted, "russian").source == "User"
    assert cached_translation(restarted, "russian").texts == ("personal",)
    assert client.session.get.call_count == 1
    edit_translation(restarted, "russian", None)
    assert cached_translation(read_recording(path), "russian").texts == ("dictionary",)
    assert path.read_bytes() == b"ID3new"


def test_changed_sense_cannot_reuse_flat_translation_or_delete_old_edit(tmp_path):
    from dataclasses import replace

    saved = recording(tmp_path)
    edit_translation(saved, "russian", "old personal")
    changed = replace(saved.recording, sense_id="other", definition="a different meaning")
    save_metadata(changed)
    current = read_recording(changed.path)
    assert cached_translation(current, "russian") is None
    client = Mock()
    client.translation_options.return_value = (TranslationOption("new", ("new dictionary",)),)
    resolved = resolve_translation(client, current, "russian")
    current = persist_translation(current, resolved)
    assert cached_translation(current, "russian").texts == ("new dictionary",)
    edit_translation(current, "russian", None)
    restarted = read_recording(changed.path)
    assert cached_translation(restarted, "russian").texts == ("new dictionary",)
    assert any(t.source == "User" and t.sense_id == "greeting" for t in restarted.translation_cache)


def test_lexical_alignment_requires_distinctive_evidence_and_rejects_conflicts():
    from cambridge_audio.translations import align_translation

    def aligned(definition, options, part="noun"):
        return align_translation(
            TranslationResult("russian", "s", "Cambridge", options), definition, part
        )

    definition = "a place where people can borrow money"
    finance = TranslationOption("f", ("банк",), "an organization to borrow money", "noun")
    # Two shared content words alone, a different POS, or negation are insufficient.
    for gloss, part in [
        ("a place to keep money", "noun"),
        ("a place where people can borrow money", "verb"),
        ("a place where people cannot borrow money", "noun"),
    ]:
        result = aligned(definition, (TranslationOption("x", ("wrong",), gloss, part),))
        assert not result.texts
        assert result.alignment == "unmatched"
    # Equally strong alternative translations are not silently resolved.
    one = TranslationOption("1", ("первый",), "a place to borrow money", "noun")
    two = TranslationOption("2", ("второй",), "a place to borrow money", "noun")
    assert not aligned(definition, (one, two)).texts
    # Exact corresponding definitions may contain several legitimate translations.
    a = TranslationOption("a", ("банк",), definition, "noun")
    b = TranslationOption("b", ("банковское учреждение",), definition, "noun")
    assert aligned(definition, (a, b, finance)).texts == ("банк", "банковское учреждение")


def test_old_unverified_cache_is_realigned_without_rewriting_personal_choices(tmp_path):
    from dataclasses import replace

    from tests.helpers import BANK_FINANCIAL_DEFINITION

    saved = recording(tmp_path)
    record = replace(saved.recording, definition=BANK_FINANCIAL_DEFINITION, part_of_speech="noun")
    save_metadata(record)
    options = (
        TranslationOption(
            "money",
            ("банк",),
            "an organization or place where you can borrow money, save money, etc",
            "noun",
        ),
        TranslationOption("river", ("берег",), "the land along the side of a river", "noun"),
    )
    saved = persist_translation(
        read_recording(record.path),
        TranslationResult("russian", record.sense_id, "Cambridge", options),
    )
    before = record.reference.read_bytes()
    result = cached_translation(saved, "russian")
    assert result.texts == ("банк",)
    assert record.reference.read_bytes() == before
    # A previously explicit selection is authoritative, even if a heuristic disagrees.
    selected = persist_translation(saved, replace(result, options=options, selected_id="river"))
    assert cached_translation(selected, "russian").texts == ("берег",)
    edit_translation(selected, "russian", "мой перевод")
    assert cached_translation(read_recording(record.path), "russian").texts == ("мой перевод",)


def test_explicit_source_choice_is_shared_between_accents_and_survives_late_lookup(tmp_path):
    from dataclasses import replace

    first = recording(tmp_path)
    uk = replace(first.recording, accent="uk", path=tmp_path / "hello.uk.mp3")
    uk.path.write_bytes(b"ID3saved")
    save_metadata(uk)
    result = TranslationResult(
        "russian",
        first.recording.sense_id,
        "Cambridge",
        (
            TranslationOption("one", ("привет",), "a greeting"),
            TranslationOption("two", ("алло",), "answering the phone"),
        ),
    )
    first = persist_translation(first, result)
    select_translation(first, "russian", "two")
    for record in (first.recording, uk):
        # A concurrent automatic refresh must not erase the confirmed choice.
        updated = persist_translation(read_recording(record.reference), result)
        assert cached_translation(updated, "russian").texts == ("алло",)


def test_unmatched_cambridge_can_use_a_matched_local_dictionary(tmp_path, monkeypatch):
    from dataclasses import replace

    saved = recording(tmp_path)
    client = Mock()
    client.translation_options.return_value = (
        TranslationOption("phone", ("алло",), "answering the phone", "noun"),
    )
    monkeypatch.setattr(
        translations,
        "lookup",
        Mock(
            return_value=(TranslationOption("local", ("привет",), "a greeting", "noun", "wikdict"),)
        ),
    )
    result = resolve_translation(client, saved, "russian")
    assert result.texts == ("привет",) and result.source == "WikDict"
    # A network failure is still recorded independently from a successful match.
    client.translation_options.side_effect = CambridgeError("offline")
    result = resolve_translation(client, saved, "russian")
    assert result.texts == ("привет",) and result.status == "network_error"
    assert result.alignment == "matched" and result.error == "offline"
    import json

    assert TranslationResult.from_dict(json.loads(json.dumps(result.to_dict()))) == result
    legacy = replace(result, alignment="").to_dict()
    legacy.pop("alignment")
    assert TranslationResult.from_dict(json.loads(json.dumps(legacy))).alignment == ""


def test_unmatched_cache_must_not_block_a_matching_installed_dictionary(tmp_path, monkeypatch):
    saved = recording(tmp_path)
    saved = persist_translation(
        saved,
        TranslationResult(
            "russian",
            "greeting",
            "Cambridge",
            (TranslationOption("phone", ("алло",), "answering the phone"),),
        ),
    )
    lookup = Mock(
        return_value=(TranslationOption("greet", ("привет",), "a greeting", origin="WikDict"),)
    )
    monkeypatch.setattr(translations, "lookup", lookup)
    result = resolve_translation(Mock(), saved, "russian", offline=True)
    assert result.texts == ("привет",)
    lookup.assert_called_once()


def test_explicit_wikdict_choice_must_beat_unmatched_cambridge_cache(tmp_path):
    saved = recording(tmp_path)
    saved = persist_translation(
        saved,
        TranslationResult(
            "russian",
            "greeting",
            "Cambridge",
            (TranslationOption("phone", ("алло",), "answering the phone"),),
        ),
    )
    saved = persist_translation(
        saved,
        TranslationResult(
            "russian",
            "greeting",
            "WikDict",
            (TranslationOption("greet", ("привет",), "a greeting", origin="WikDict"),),
        ),
    )
    selected = select_translation(saved, "russian", "greet")
    result = cached_translation(selected, "russian")
    assert result.texts == ("привет",)
    assert result.source == "WikDict"


def test_late_personal_cache_snapshot_cannot_replace_a_newer_edit(tmp_path):
    saved = edit_translation(recording(tmp_path), "russian", "old")
    snapshot = cached_translation(saved, "russian")
    edit_translation(saved, "russian", "new")
    saved = persist_translation(saved, snapshot)
    assert cached_translation(saved, "russian").texts == ("new",)


def test_most_recent_explicit_source_choice_wins_over_source_preference(tmp_path):
    saved = recording(tmp_path)
    for source, option_id, text in (("Cambridge", "phone", "алло"), ("WikDict", "greet", "привет")):
        saved = persist_translation(
            saved,
            TranslationResult(
                "russian",
                "greeting",
                source,
                (TranslationOption(option_id, (text,), "different wording"),),
                selected_id=option_id,
            ),
        )
    assert cached_translation(saved, "russian").texts == ("привет",)
    saved = select_translation(saved, "russian", "phone")
    assert cached_translation(saved, "russian").texts == ("алло",)


@pytest.mark.parametrize("part", ["verb", "phrasal verb"])
@pytest.mark.parametrize(
    "definition,gloss",
    [
        (
            "to pay money to use something for a short period",
            "to receive money for letting someone use something for a short period",
        ),
        (
            "to make someone pay money for using a thing",
            "to make someone receive money for using a thing",
        ),
        ("to give someone permission to borrow money", "to give someone permission to lend money"),
    ],
)
def test_action_direction_cannot_be_confirmed_by_shared_words(part, definition, gloss):
    from cambridge_audio.translations import align_translation

    result = align_translation(
        TranslationResult(
            "russian",
            "sense",
            "Cambridge",
            (TranslationOption("opposite", ("wrong",), gloss, part),),
        ),
        definition,
        part,
    )
    assert result.alignment == "unmatched" and not result.texts

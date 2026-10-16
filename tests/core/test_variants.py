"""Selection must keep sense, IPA and MP3 together across restarts and reordering."""

from dataclasses import replace

import pytest

from cambridge_audio.dictionary import (
    SelectionRequired,
    audio_filename,
    dictionary_url,
    parse_entries,
    variants,
)
from cambridge_audio.library import read_recording, save_metadata, scan_recordings
from cambridge_audio.service import download_recordings
from tests.helpers import response


@pytest.fixture
def multiple_html():
    return """
    <div class="entry-body__el" id="lead-metal"><div class="pos-header">
      <span class="hw">lead</span><span class="pos">noun</span>
      <span class="us"><span class="dpron-i"><span class="ipa">led</span>
      <audio><source src="/media/lead-metal.mp3"></audio></span></span></div>
      <div class="def-block" data-wl-senseid="metal"><div class="def ddef_d">a metal</div></div>
    </div>
    <div class="entry-body__el" id="lead-guide"><div class="pos-header">
      <span class="hw">lead</span><span class="pos">verb</span>
      <span class="us"><span class="dpron-i"><span class="ipa">liːd</span>
      <audio><source src="/media/lead-guide.mp3"></audio></span>
      <span class="dpron-i"><span class="ipa">lid</span>
      <audio><source src="/media/lead-guide-alt.mp3"></audio></span></span></div>
      <div class="def-block" data-wl-senseid="guide"><div class="def ddef_d">to guide</div></div>
      <div class="def-block" data-wl-senseid="first"><div class="def ddef_d">to be first</div></div>
    </div>"""


def test_choices_preserve_multiple_definitions_and_each_ipa(multiple_html):
    entries = parse_entries(multiple_html, dictionary_url("lead"))
    assert len(entries) == 3
    choices = variants(entries)
    assert len(choices) == 5
    assert {(v.entry.part_of_speech, v.entry.definition, v.pronunciation.ipa) for v in choices} == {
        ("noun", "a metal", "led"),
        ("verb", "to guide", "liːd"),
        ("verb", "to guide", "lid"),
        ("verb", "to be first", "liːd"),
        ("verb", "to be first", "lid"),
    }
    reordered = tuple(reversed(entries))
    assert {v.id for v in variants(reordered)} == {v.id for v in choices}


def test_ambiguity_does_not_download_and_selected_variants_never_collide(
    client, multiple_html, tmp_path
):
    client.session.get.return_value = response(multiple_html)
    with pytest.raises(SelectionRequired) as error:
        download_recordings(client, "lead", tmp_path)
    assert client.session.get.call_count == 1
    assert not list(tmp_path.iterdir())
    for choice in error.value.choices:
        audio = b"ID3" + choice.pronunciation.url.encode()
        client.session.get.return_value = response(audio)
        result = download_recordings(
            client,
            "lead",
            tmp_path,
            entries=error.value.entries,
            variant_id=choice.id,
            on_recording=save_metadata,
        )
        record = result.recordings[0]
        assert record.definition == choice.entry.definition
        assert record.part_of_speech == choice.entry.part_of_speech
        assert record.ipa == choice.pronunciation.ipa
        assert record.audio_url == choice.pronunciation.url
        assert record.path.read_bytes() == audio
        assert read_recording(record.reference).recording == record
    assert len(scan_recordings(tmp_path)) == 5
    before = {s.recording.path: s.recording.path.read_bytes() for s in scan_recordings(tmp_path)}
    selected = scan_recordings(tmp_path)[2].recording
    client.session.get.return_value = response(b"ID3replacement")
    count = client.session.get.call_count
    download_recordings(client, "lead", tmp_path, entries=error.value.entries, target=selected)
    assert client.session.get.call_count == count
    download_recordings(
        client,
        "lead",
        tmp_path,
        entries=error.value.entries,
        target=selected,
        overwrite=True,
        on_recording=save_metadata,
    )
    assert selected.path.read_bytes() == b"ID3replacement"
    assert all(p.read_bytes() == data for p, data in before.items() if p != selected.path)


def test_definition_from_entry_that_owns_the_audio(client, html, tmp_path):
    silent = (
        '<div class="entry-body__el"><div class="pos-header"></div>'
        '<div class="def ddef_d">wrong</div></div>'
    )
    client.session.get.side_effect = [response(silent + html), response(b"ID3audio")]
    result = download_recordings(client, "hello", tmp_path)
    assert result.recordings[0].definition == "used when meeting someone"


def test_portable_long_names_and_distinct_senses(multiple_html):
    name = audio_filename("a" * 300, "us", "b" * 24)
    assert len(name.encode()) < 150
    assert audio_filename("con", "us", "1234").startswith("_con--")
    entries = parse_entries(multiple_html, dictionary_url("lead"))
    one, two = entries[1:]
    assert one.sense_id != two.sense_id
    assert replace(one, pronunciations=tuple(reversed(one.pronunciations))).sense_id == one.sense_id


def test_single_remaining_variant_does_not_overwrite_different_saved_variant(
    client, html, tmp_path
):
    from cambridge_audio.service import Recording

    legacy_path = tmp_path / "hello.us.mp3"
    legacy_path.write_bytes(b"ID3previous")
    save_metadata(Recording("hello", "us", legacy_path, "old", "old sense", variant_id="a" * 24))
    client.session.get.side_effect = [response(html), response(b"ID3new")]
    result = download_recordings(
        client, "hello", tmp_path, overwrite=True, on_recording=save_metadata
    )
    assert result.recordings[0].path != legacy_path
    assert legacy_path.read_bytes() == b"ID3previous"
    assert result.recordings[0].path.read_bytes() == b"ID3new"

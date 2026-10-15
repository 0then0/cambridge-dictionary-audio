from unittest.mock import Mock

import pytest
import requests
from conftest import response

from cambridge_audio.dictionary import (
    BASE_URL,
    AudioNotFoundError,
    CambridgeError,
    audio_filename,
    dictionary_url,
    normalize_word,
    parse_entries,
    save_mp3,
)


def test_url_normalizes_phrase_and_encodes_apostrophe():
    assert dictionary_url("  Good   Morning ") == f"{BASE_URL}/us/dictionary/english/good-morning"
    assert dictionary_url("don't") == f"{BASE_URL}/us/dictionary/english/don%27t"


@pytest.mark.parametrize("word", ["", "../hello", "a/b", "a\\b", "https://example.com", "привет"])
def test_invalid_input(word):
    with pytest.raises(ValueError):
        normalize_word(word)


def test_current_markup_selects_mp3_and_correct_accent(html):
    (entry,) = parse_entries(html, dictionary_url("hello"))
    assert entry.word == "hello"
    assert entry.definition == "used when meeting someone"
    assert [(p.accent, p.url, p.ipa) for p in entry.pronunciations] == [
        ("us", f"{BASE_URL}/us/media/hello-us.mp3", "heˈloʊ"),
        ("uk", f"{BASE_URL}/us/media/hello-uk.mp3", "heˈləʊ"),
    ]


def test_parser_skips_incomplete_entries_and_untrusted_sources():
    html = f"""
    <div class="entry-body__el"></div>
    <div class="entry-body__el"><div class="dpos-h"><span class="uk">
      <audio><source src="https://other.example/hello.mp3">
      <source src="http://dictionary.cambridge.org/hello.mp3">
      <source src="//dictionary.cambridge.org/hello.mp3">
      <source src="{BASE_URL}/hello.mp3"></audio>
    </span></div></div>
    """
    (entry,) = parse_entries(html, dictionary_url("hello"))
    assert len(entry.pronunciations) == 1
    assert entry.pronunciations[0].url == f"{BASE_URL}/hello.mp3"
    assert entry.pronunciations[0].ipa == ""


def test_download_finds_audio_in_later_entry(client, html, mp3, tmp_path):
    silent = '<div class="entry-body__el"><div class="dpos-h"></div></div>'
    client.session.get.side_effect = [response(silent + html), response(mp3)]
    entries = client.lookup("hello")
    destination = tmp_path / "audio" / "hello.us.mp3"
    pronunciation = client.download(entries, "us", destination)
    assert pronunciation.accent == "us"
    assert destination.read_bytes() == mp3
    client.session.get.assert_called_with(f"{BASE_URL}/us/media/hello-us.mp3", timeout=15.0)


@pytest.mark.parametrize("status", [403, 429, 500])
def test_http_failure_does_not_create_file(client, html, tmp_path, status):
    client.session.get.return_value = response("error", status=status)
    with pytest.raises(CambridgeError, match=str(status)):
        client.download(parse_entries(html, dictionary_url("hello")), "uk", tmp_path / "x.mp3")
    assert list(tmp_path.iterdir()) == []


def test_timeout_is_reported(client):
    client.session.get.side_effect = requests.Timeout("timed out")
    with pytest.raises(CambridgeError, match="timed out"):
        client.lookup("hello")


@pytest.mark.parametrize(
    "result", [response("missing", status=404), response("<html>search</html>")]
)
def test_missing_entry(client, result):
    client.session.get.return_value = result
    with pytest.raises(AudioNotFoundError):
        client.lookup("nonexistent")


def test_missing_accent_does_not_fall_back_to_other_accent(client, html, tmp_path):
    entries = parse_entries(
        html.replace('class="uk dpron-i"', 'class="other"'), dictionary_url("hello")
    )
    with pytest.raises(AudioNotFoundError, match="UK"):
        client.download(entries, "uk", tmp_path / "hello.mp3")
    client.session.get.assert_not_called()


@pytest.mark.parametrize("content", [b"", b"<html>blocked</html>", b"not audio"])
def test_invalid_audio_preserves_existing_file_and_leaves_no_temporary(content, tmp_path, mp3):
    destination = tmp_path / "hello.mp3"
    destination.write_bytes(mp3)
    with pytest.raises(CambridgeError):
        save_mp3(content, destination, overwrite=True)
    assert destination.read_bytes() == mp3
    assert list(tmp_path.iterdir()) == [destination]


def test_explicit_overwrite_required(tmp_path, mp3):
    destination = tmp_path / "hello.mp3"
    destination.write_bytes(b"existing file")
    with pytest.raises(FileExistsError):
        save_mp3(mp3, destination)
    assert destination.read_bytes() == b"existing file"
    save_mp3(mp3, destination, overwrite=True)
    assert destination.read_bytes() == mp3
    assert list(tmp_path.iterdir()) == [destination]


def test_existing_file_rejected_before_audio_request(client, html, tmp_path):
    destination = tmp_path / "hello.mp3"
    destination.touch()
    with pytest.raises(FileExistsError):
        client.download(parse_entries(html, dictionary_url("hello")), "uk", destination)
    client.session.get.assert_not_called()


def test_write_failure_leaves_existing_file_intact(monkeypatch, tmp_path, mp3):
    destination = tmp_path / "hello.mp3"
    destination.write_bytes(b"original")
    monkeypatch.setattr(type(destination), "replace", Mock(side_effect=OSError("disk failure")))
    with pytest.raises(OSError):
        save_mp3(mp3, destination, overwrite=True)
    assert destination.read_bytes() == b"original"
    assert list(tmp_path.iterdir()) == [destination]


def test_translations_are_deduplicated(client):
    client.session.get.return_value = response("""
    <div class="entry-body__el"><div class="def-body">
    <span class="trans">привет</span><span class="trans">привет</span>
    <span class="trans">здравствуйте</span></div></div>""")
    assert client.translations("hello", "russian") == ("привет", "здравствуйте")
    client.session.get.assert_called_with(dictionary_url("hello", "english-russian"), timeout=15.0)


@pytest.mark.parametrize("word", ["con", "aux", "nul", "prn", "com1", "lpt9"])
def test_windows_device_names_get_portable_filenames(word):
    assert audio_filename(word, "us") == f"_{word}.us.mp3"
    assert audio_filename("hello", "us") == "hello.us.mp3"


def test_definition_preserves_internal_colon(html):
    entries = parse_entries(
        html.replace("used when meeting someone", "greeting: used when meeting someone:"),
        dictionary_url("hello"),
    )
    assert entries[0].definition == "greeting: used when meeting someone"


@pytest.mark.parametrize("failure", [OSError("disk full"), KeyboardInterrupt()])
@pytest.mark.parametrize("overwrite", [False, True])
def test_interrupted_write_never_publishes_partial_audio(
    monkeypatch, tmp_path, mp3, failure, overwrite
):
    from cambridge_audio import dictionary

    destination = tmp_path / "hello.us.mp3"
    if overwrite:
        destination.write_bytes(b"original")
    original = dictionary.NamedTemporaryFile

    def failing_stream(*args, **kwargs):
        stream = original(*args, **kwargs)

        def write(content):
            stream.file.write(content[:3])
            raise failure

        stream.write = write
        return stream

    monkeypatch.setattr(dictionary, "NamedTemporaryFile", failing_stream)
    with pytest.raises(type(failure)):
        save_mp3(mp3, destination, overwrite=overwrite)
    if overwrite:
        assert destination.read_bytes() == b"original"
    else:
        assert not destination.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_atomic_publish_preserves_concurrent_file(monkeypatch, tmp_path, mp3):
    from cambridge_audio import dictionary

    destination = tmp_path / "hello.us.mp3"
    if dictionary.os.name == "nt":
        original = type(destination).rename

        def publish(source, target):
            target.write_bytes(b"concurrent")
            return original(source, target)

        monkeypatch.setattr(type(destination), "rename", publish)
    else:
        original = dictionary.os.link

        def publish(source, target):
            target.write_bytes(b"concurrent")
            return original(source, target)

        monkeypatch.setattr(dictionary.os, "link", publish)
    with pytest.raises(FileExistsError):
        save_mp3(mp3, destination)
    assert destination.read_bytes() == b"concurrent"
    assert not list(tmp_path.glob("*.tmp"))


def test_bilingual_translation_matches_selected_part_and_definition(client):
    client.session.get.return_value = response("""
    <div class="entry-body__el"><span class="pos">noun</span>
    <div class="def-block"><div class="def ddef_d">a metal:</div>
    <div class="def-body"><span class="trans">свинец</span></div></div></div>
    <div class="entry-body__el"><span class="pos">verb</span>
    <div class="def-block"><div class="def ddef_d">to guide:</div>
    <div class="def-body"><span class="trans">вести</span></div></div></div>
    """)
    options = client.translation_options("lead", "russian", "to guide", "verb")
    assert len(options) == 1
    assert options[0].texts == ("вести",)
    assert options[0].matched and options[0].part_of_speech == "verb"
    assert "english-russian/lead" in options[0].origin
    # English and bilingual definitions can differ. Keep a known matching part
    # of speech, without claiming an exact match or including unrelated nouns.
    options = client.translation_options("lead", "russian", "to show the way", "verb")
    assert len(options) == 1 and options[0].texts == ("вести",)
    assert options[0].definition == "to guide" and not options[0].matched
    client.session.get.return_value = response("""
    <div class="entry-body__el"><div class="def-body"><span class="trans">one</span></div>
    <div class="def-body"><span class="trans">two</span></div></div>
    """)
    options = client.translation_options("lead", "russian", "to guide", "verb")
    assert len(options) == 2 and not any(o.matched for o in options)


def test_blocking_page_is_not_reported_as_absent_translation(client):
    from cambridge_audio.dictionary import CambridgeBlockedError

    client.session.get.return_value = response("<html>Access Denied CAPTCHA</html>")
    with pytest.raises(CambridgeBlockedError):
        client.translation_options("hello", "russian")

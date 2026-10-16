from unittest.mock import Mock

import pytest
import requests

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
from tests.helpers import response


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
    assert client.session.get.call_count == 1
    client.session.get.return_value = response("""
    <div class="entry-body__el"><div class="def-body"><span class="trans">one</span></div>
    <div class="def-body"><span class="trans">two</span></div></div>
    """)
    # A different page exercises missing POS/gloss metadata; successful pages
    # already fetched by this client are intentionally reused.
    options = client.translation_options("unknown", "russian", "to guide", "verb")
    assert len(options) == 2 and not any(o.matched for o in options)


def test_blocking_page_is_not_reported_as_absent_translation(client):
    from cambridge_audio.dictionary import CambridgeBlockedError

    client.session.get.return_value = response("<html>Access Denied CAPTCHA</html>")
    with pytest.raises(CambridgeBlockedError):
        client.translation_options("hello", "russian")


@pytest.mark.parametrize(
    "retry_after,delay",
    [
        ("5", 5),
        ("Thu, 01 Jan 1970 00:16:45 GMT", 5),
        ("0", 1),
        ("Thu, 01 Jan 1970 00:00:00 GMT", 1),
        (None, 2),
        ("invalid", 2),
        ("-5", 2),
        ("nan", 2),
        ("1.5", 2),
    ],
)
def test_rate_limit_retries_after_server_delay_or_backoff(
    client, html, request_clock, retry_after, delay
):
    limited = response("slow down", status=429)
    if retry_after is not None:
        limited.headers["Retry-After"] = retry_after
    limited.close = Mock(wraps=limited.close)
    times = []
    replies = iter((limited, response(html)))

    def get(*args, **kwargs):
        times.append(request_clock.now)
        return next(replies)

    client.session.get.side_effect = get
    assert client.lookup("hello")[0].word == "hello"
    assert times == [1000, 1000 + delay]
    limited.close.assert_called_once()


def test_rate_limit_has_bounded_exponential_retries(client, request_clock):
    from cambridge_audio.dictionary import CambridgeBlockedError

    times = []

    def get(*args, **kwargs):
        times.append(request_clock.now)
        return response("limited", status=429)

    client.session.get.side_effect = get
    with pytest.raises(CambridgeBlockedError, match="429"):
        client.lookup("hello")
    assert times == [1000, 1002, 1006]


@pytest.mark.parametrize("status", [403, 500])
def test_other_http_failures_are_not_retried(client, status):
    client.session.get.return_value = response("error", status=status)
    with pytest.raises(CambridgeError, match=str(status)):
        client.lookup("hello")
    assert client.session.get.call_count == 1


def test_request_spacing_and_server_cooldown_are_shared_between_clients(
    client, html, request_clock
):
    from cambridge_audio.dictionary import CambridgeClient

    client.session.get.return_value = response(html)
    client.lookup("hello")
    with CambridgeClient() as other:
        # End this operation after a 429 so the next client must honor its delay.
        other.session.get = Mock(return_value=response("limited", status=429))
        other.session.get.return_value.headers["Retry-After"] = "60"
        with pytest.raises(CambridgeError, match="60 seconds"):
            other.lookup("world")
        assert request_clock.now == 1001
        assert other.session.get.call_count == 1
    client.session.get.reset_mock()
    with pytest.raises(CambridgeError, match="60 seconds"):
        client.lookup("world")
    client.session.get.assert_not_called()
    # Cached pages remain usable during a server cooldown.
    assert client.lookup("hello")[0].word == "hello"
    request_clock.now += 60
    client.lookup("world")
    assert client.session.get.call_count == 1


@pytest.mark.parametrize("retry_after", ["31", "9" * 400])
def test_long_retry_after_does_not_block_or_retry_early(client, request_clock, retry_after):
    client.language = "ru"
    limited = response("limited", status=429)
    limited.headers["Retry-After"] = retry_after
    client.session.get.return_value = limited
    with pytest.raises(CambridgeError, match="Повторите через"):
        client.lookup("hello")
    assert client.session.get.call_count == 1
    assert request_clock.now == 1000


@pytest.mark.parametrize("rate_limited", [False, True])
def test_spacing_and_retry_waits_can_be_cancelled(client, html, request_clock, rate_limited):
    from cambridge_audio.service import DownloadCancelled

    def check():
        if request_clock.now >= 1000.1:
            raise DownloadCancelled("cancelled")

    if rate_limited:
        client.session.get.return_value = response("limited", status=429)
    else:
        client.session.get.return_value = response(html)
        client.lookup("hello")
    client.check_cancelled = check
    with pytest.raises(DownloadCancelled):
        client.lookup("world")
    assert client.session.get.call_count == 1
    assert request_clock.now == pytest.approx(1000.1)


def test_successful_pages_are_reused_but_explicit_audio_redownload_is_fresh(
    client, html, mp3, tmp_path
):
    client.session.get.side_effect = [response(html), response(mp3), response(mp3 + b"new")]
    entries = client.lookup("hello")
    assert client.lookup("  HELLO ") == entries
    path = tmp_path / "hello.mp3"
    client.download(entries, "us", path)
    client.download(client.lookup("hello"), "us", path, overwrite=True)
    assert path.read_bytes() == mp3 + b"new"
    assert client.session.get.call_count == 3


@pytest.mark.parametrize(
    "status,content",
    [
        (403, "denied"),
        (404, "missing"),
        (500, "error"),
        (200, "captcha"),
        (200, "<html>search</html>"),
    ],
)
def test_failed_pages_are_not_cached(client, html, status, content):
    client.session.get.side_effect = [response(content, status=status), response(html)]
    with pytest.raises(CambridgeError):
        client.lookup("hello")
    assert client.lookup("hello")[0].word == "hello"
    assert client.session.get.call_count == 2


def test_page_cache_is_bounded(client, html):
    client.session.get.return_value = response(html)
    for index in range(65):
        client.lookup("word " + "a" * (index + 1))
    client.lookup("word a")
    assert client.session.get.call_count == 66


def test_concurrent_clients_space_requests_without_blocking_inflight_response(
    client, html, request_clock
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from cambridge_audio.dictionary import CambridgeClient

    entered, release = Event(), Event()
    times = []

    def first_get(*args, **kwargs):
        times.append(request_clock.now)
        entered.set()
        assert release.wait(5)
        return response(html)

    def second_get(*args, **kwargs):
        times.append(request_clock.now)
        release.set()
        return response(html)

    client.session.get.side_effect = first_get
    with ThreadPoolExecutor(max_workers=1) as executor, CambridgeClient() as other:
        other.session.get = Mock(side_effect=second_get)
        first = executor.submit(client.lookup, "hello")
        try:
            assert entered.wait(5)
            other.lookup("world")
            assert first.result(timeout=5)[0].word == "hello"
        finally:
            release.set()
    assert times == [1000, 1001]

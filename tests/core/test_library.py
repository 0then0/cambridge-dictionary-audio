import pytest

from cambridge_audio import library
from cambridge_audio.service import Recording


def test_scan_legacy_files_is_sorted_and_ignores_unrelated_files(tmp_path):
    for name in ("hello.us.mp3", "hello.uk.mp3", "Good morning.us.mp3", "notes.mp3", "hello.json"):
        (tmp_path / name).write_bytes(b"audio")
    (tmp_path / "folder.us.mp3").mkdir()
    records = library.scan_recordings(tmp_path)
    assert [(r.recording.word, r.recording.accent) for r in records] == [
        ("Good morning", "us"),
        ("hello", "uk"),
        ("hello", "us"),
    ]
    assert all(r.recording.ipa == "" for r in records)
    assert library.scan_recordings(tmp_path / "missing") == []


def test_metadata_roundtrip_preserves_phrase_details_and_translations(tmp_path):
    path = tmp_path / "good morning.us.mp3"
    path.write_bytes(b"audio")
    record = Recording("good morning", "us", path, "ɡʊd", "a greeting", combined=True)
    library.save_metadata(record, ("доброе утро",))
    saved = library.read_recording(path)
    assert saved.recording == record
    assert saved.translations == ("доброе утро",)


@pytest.mark.parametrize("content", ["{invalid", "[]", '{"version":1,"word":"other"}', "\udcff"])
def test_bad_metadata_does_not_hide_audio(tmp_path, content):
    path = tmp_path / "hello.us.mp3"
    path.write_bytes(b"audio")
    path.with_suffix(".json").write_bytes(content.encode("utf-8", errors="surrogateescape"))
    saved = library.read_recording(path)
    assert saved.recording.word == "hello"
    assert saved.recording.ipa == ""


def test_metadata_restores_windows_reserved_word(tmp_path):
    path = tmp_path / "_con.us.mp3"
    path.write_bytes(b"audio")
    record = Recording("con", "us", path, "", "")
    library.save_metadata(record)
    assert library.read_recording(path).recording.word == "con"


def test_failed_metadata_replace_keeps_previous_details(tmp_path, monkeypatch):
    path = tmp_path / "hello.us.mp3"
    path.write_bytes(b"audio")
    record = Recording("hello", "us", path, "", "old")
    library.save_metadata(record)
    previous = path.with_suffix(".json").read_bytes()

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(library.os, "replace", fail)
    with pytest.raises(OSError):
        library.save_metadata(Recording("hello", "us", path, "", "new"))
    assert path.with_suffix(".json").read_bytes() == previous
    assert not list(tmp_path.glob("*.tmp"))


def test_empty_files_are_not_saved_recordings(tmp_path):
    (tmp_path / "hello.us.mp3").touch()
    assert library.scan_recordings(tmp_path) == []


@pytest.mark.parametrize(
    "word",
    [
        "con",
        "prn",
        "aux",
        "nul",
        *[f"com{i}" for i in range(1, 10)],
        *[f"lpt{i}" for i in range(1, 10)],
    ],
)
def test_reserved_word_restored_without_metadata(tmp_path, word):
    from cambridge_audio.dictionary import audio_filename, normalize_word

    path = tmp_path / audio_filename(word, "us")
    path.write_bytes(b"ID3saved")
    assert normalize_word(library.read_recording(path).recording.word) == word


def test_unrelated_underscore_is_not_removed(tmp_path):
    path = tmp_path / "_hello.us.mp3"
    path.write_bytes(b"ID3saved")
    assert library.read_recording(path).recording.word == "_hello"


def test_aliases_retain_distinct_names_and_sidecars(tmp_path):
    target = tmp_path / "hello.mp3"
    target.write_bytes(b"ID3saved")
    for accent in ("us", "uk"):
        path = tmp_path / f"hello.{accent}.mp3"
        try:
            path.symlink_to(target.name)
        except OSError:
            pytest.skip("Creating symlinks requires platform permission")
    records = library.scan_recordings(tmp_path)
    assert {r.recording.path.name for r in records} == {"hello.us.mp3", "hello.uk.mp3"}
    for saved in records:
        library.save_metadata(saved.recording, ("привет",), "russian")
        assert library.read_recording(saved.recording.path).translation_language == "russian"
    assert not target.with_suffix(".json").exists()
    assert target.read_bytes() == b"ID3saved"


def test_language_roundtrip_and_legacy_unknown_language(tmp_path):
    path = tmp_path / "hello.us.mp3"
    path.write_bytes(b"ID3saved")
    record = Recording("hello", "us", path, "", "")
    library.save_metadata(record, ("bonjour",), "french")
    assert library.read_recording(path).translation_language == "french"
    library.save_metadata(record, ("привет",))
    assert library.read_recording(path).translation_language is None


def test_metadata_replace_waits_for_active_reader(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FutureTimeoutError
    from threading import Event

    path = tmp_path / "hello.us.mp3"
    path.write_bytes(b"ID3saved")
    record = Recording("hello", "us", path, "", "old")
    library.save_metadata(record)
    reading, release, staged = Event(), Event(), Event()
    original_read = type(path).read_text
    original_replace = library.os.replace
    original_dump = library.json.dump

    def read(path, *args, **kwargs):
        reading.set()
        try:
            assert release.wait(5)
            return original_read(path, *args, **kwargs)
        finally:
            reading.clear()

    def dump(*args, **kwargs):
        original_dump(*args, **kwargs)
        staged.set()

    def replace(source, destination):
        if reading.is_set():
            raise PermissionError("Windows sharing violation: reader is active")
        return original_replace(source, destination)

    monkeypatch.setattr(type(path), "read_text", read)
    monkeypatch.setattr(library.json, "dump", dump)
    monkeypatch.setattr(library.os, "replace", replace)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reader = pool.submit(library.read_recording, path)
        writer = None
        try:
            assert reading.wait(5)
            writer = pool.submit(library.save_metadata, Recording("hello", "us", path, "", "new"))
            with pytest.raises(FutureTimeoutError):
                writer.result(timeout=0.05)
        finally:
            release.set()
        assert reader.result(timeout=5).recording.definition == "old"
        writer.result(timeout=5)
    assert library.read_recording(path).recording.definition == "new"
    assert path.read_bytes() == b"ID3saved"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("language", [None, "french"])
def test_metadata_only_update_preserves_legacy_translation_and_original_language(
    tmp_path, language
):
    import json

    path = tmp_path / "hello.us.mp3"
    path.write_bytes(b"ID3saved")
    path.with_suffix(".json").write_text(
        json.dumps(
            {
                "version": 1,
                "word": "hello",
                "ipa": "",
                "definition": "greeting",
                "translations": ["bonjour"],
                "translation_language": language,
            }
        )
    )
    record = library.read_recording(path).recording
    library.save_metadata(record, translation_language="russian")
    saved = library.read_recording(path)
    assert saved.translations == ("bonjour",)
    assert saved.translation_language == language

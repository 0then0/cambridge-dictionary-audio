import csv
import io
from pathlib import Path
from unittest.mock import Mock

import pytest

from cambridge_audio import anki, cli
from cambridge_audio.anki import export_anki
from cambridge_audio.library import read_recording, save_metadata, scan_recordings
from cambridge_audio.service import Recording
from cambridge_audio.translations import edit_translation


def collection(tmp_path):
    directory = tmp_path / "audio"
    directory.mkdir()
    for accent in ("us", "uk"):
        path = directory / f"hello.{accent}.mp3"
        path.write_bytes(b"ID3original" + accent.encode())
        save_metadata(
            Recording("hello", accent, path, "həˈləʊ", 'say "hello"\t<greeting>\n&amp; привет'),
            ("привет",),
            "russian",
        )
    return scan_recordings(directory)


def rows(path):
    return list(
        csv.reader(
            io.StringIO("\n".join(path.read_text(encoding="utf-8").splitlines()[3:])),
            delimiter="\t",
        )
    )


def test_tsv_audio_escaping_unicode_ids_and_repeat_export(tmp_path):
    records = collection(tmp_path)
    originals = {
        p: p.read_bytes()
        for s in records
        for p in (s.recording.path, s.recording.path.with_suffix(".json"))
    }
    path = export_anki(records, tmp_path / "export")
    content = path.read_text(encoding="utf-8")
    assert content.startswith("#separator:Tab\n#html:true\n#columns:ID\tWord")
    values = rows(path)
    assert len(values) == 2
    assert len({row[0] for row in values}) == 2
    for row in values:
        assert len(row) == 9
        assert "&quot;hello&quot;\t&lt;greeting&gt;<br>&amp;amp; привет" in row[3]
        assert row[4] == "привет"
        assert row[7].startswith("[sound:")
        media = row[7][7:-1]
        assert "/" not in media and "\\" not in media
        assert (path.parent / "media" / media).read_bytes().startswith(b"ID3original")
    assert "collection.media" in (path.parent / "IMPORT.txt").read_text(encoding="utf-8")
    assert "CC BY-SA 4.0" in (path.parent / "SOURCES.txt").read_text(encoding="utf-8")
    assert export_anki(records, path.parent).read_text(encoding="utf-8") == content
    assert all(p.read_bytes() == data for p, data in originals.items())


def test_missing_invalid_unreadable_audio_and_unknown_destination_are_failures(
    tmp_path, monkeypatch
):
    records = collection(tmp_path)
    destination = tmp_path / "export"
    path = export_anki(records, destination)
    original = path.read_bytes()
    records[0].recording.path.unlink()
    with pytest.raises(ValueError, match="Cannot export"):
        export_anki(records, destination)
    assert path.read_bytes() == original
    records[0].recording.path.write_bytes(b"<html>not mp3</html>")
    with pytest.raises(ValueError, match="invalid MP3"):
        export_anki(records, tmp_path / "new-export")
    personal = tmp_path / "personal"
    personal.mkdir()
    (personal / "notes.txt").write_text("untouched")
    with pytest.raises(FileExistsError):
        export_anki(records, personal)
    assert (personal / "notes.txt").read_text(encoding="utf-8") == "untouched"
    assert not (tmp_path / "new-export").exists()


def test_copy_failure_keeps_previous_export_and_originals(tmp_path, monkeypatch):
    records = collection(tmp_path)
    path = export_anki(records, tmp_path / "export")
    before = path.read_bytes()
    monkeypatch.setattr(anki.shutil, "copyfile", Mock(side_effect=PermissionError("denied")))
    with pytest.raises(PermissionError):
        export_anki(records, path.parent)
    assert path.read_bytes() == before
    assert all(s.recording.path.is_file() for s in records)
    assert not list(tmp_path.glob(".cambridge-anki-*"))


def test_cli_selected_export_does_not_create_network_client(tmp_path, monkeypatch):
    records = collection(tmp_path)
    selected = records[0]
    monkeypatch.setattr(cli, "CambridgeClient", Mock(side_effect=AssertionError("offline export")))
    args = [
        "--recording",
        str(selected.recording.path),
        "--export-anki",
        str(tmp_path / "export"),
        "--export-format",
        "tsv",
    ]
    assert cli.main(args) == 0
    assert len(rows(tmp_path / "export/collection.tsv")) == 1
    selected = edit_translation(selected, "russian", "пользовательский")
    assert cli.main(args) == 0
    assert rows(tmp_path / "export/collection.tsv")[0][4] == "пользовательский"
    selected.recording.path.unlink()
    assert cli.main(args) == 1


def test_legacy_symlink_keeps_original_and_exports_flat_media(tmp_path):
    target = tmp_path / "original.mp3"
    target.write_bytes(b"ID3original")
    alias = tmp_path / "hello.us.mp3"
    try:
        alias.symlink_to(target.name)
    except OSError:
        pytest.skip("Symlinks require platform permission")
    saved = read_recording(alias)
    export_anki([saved], tmp_path / "export")
    assert alias.is_symlink()
    assert target.read_bytes() == b"ID3original"
    assert not target.with_suffix(".json").exists()


def test_failed_publish_rolls_back_previous_export(tmp_path, monkeypatch):
    records = collection(tmp_path)
    path = export_anki(records, tmp_path / "export")
    before = path.read_bytes()
    original = anki.os.replace

    def fail(source, destination):
        if Path(source).name == "export" and Path(source).parent.name.startswith(
            ".cambridge-anki-"
        ):
            raise OSError("publish failed")
        return original(source, destination)

    monkeypatch.setattr(anki.os, "replace", fail)
    with pytest.raises(OSError, match="publish failed"):
        export_anki(records, path.parent)
    assert path.read_bytes() == before


def test_repeat_export_refuses_unrelated_media_files(tmp_path):
    records = collection(tmp_path)
    path = export_anki(records, tmp_path / "export")
    unrelated = path.parent / "media/personal.mp3"
    unrelated.write_bytes(b"ID3personal")
    with pytest.raises(FileExistsError, match="unrelated"):
        export_anki(records, path.parent)
    assert unrelated.read_bytes() == b"ID3personal"


def test_unsafe_metadata_id_is_hashed_for_flat_media(tmp_path):
    from dataclasses import replace

    from cambridge_audio.library import SavedRecording

    records = collection(tmp_path)
    record = replace(records[0].recording, variant_id="../../private")
    path = export_anki([SavedRecording(record)], tmp_path / "export")
    assert len(list((path.parent / "media").glob("*.mp3"))) == 1
    assert "/" not in record.id and "\\" not in record.id

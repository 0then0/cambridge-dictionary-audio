"""Transfer acceptance and hostile/corrupt archive regression cases."""

import json
import os
from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

import pytest

from cambridge_audio import bundle
from cambridge_audio.bundle import apply_import, export_bundle, preview_import
from cambridge_audio.dictionary import variants
from cambridge_audio.library import read_recording, save_metadata, scan_recordings
from cambridge_audio.translations import cached_translation, edit_translation
from tests.core.test_shared_audio import AUDIO, bank, save
from tests.helpers import response


def collection(client, directory):
    directory.mkdir()
    client.session.get.return_value = response(AUDIO)
    records = [save(client, directory, choice) for choice in variants(bank())]
    edit_translation(read_recording(records[0].reference), "russian", "my bank")
    metadata = records[0].reference
    data = json.loads(metadata.read_bytes())
    data["unknown_future_field"] = {"retain": [1, "text"]}
    data["translation_cache"][0]["opaque"] = {"author": "me"}
    data["translation_cache"][0]["options"][0]["future_option"] = True
    metadata.write_text(json.dumps(data))
    (directory / ".anki-mapping.json").write_text(
        json.dumps(
            {
                "version": 1,
                "notes": {records[0].id: {"guid": "oldGUID", "model": {"id": 42}}},
                "last_export": 1700000000,
            }
        )
    )
    return records


def test_transfer_flushes_writable_descriptors_as_required_on_windows(
    client, tmp_path, monkeypatch
):
    records = collection(client, tmp_path / "source")
    native_fsync = bundle.os.fsync

    def windows_fsync(descriptor):
        # Windows _commit rejects read-only handles. A zero-byte write exercises
        # the same access restriction on POSIX without changing the file contents.
        os.write(descriptor, b"")
        native_fsync(descriptor)

    monkeypatch.setattr(bundle.os, "fsync", windows_fsync)
    archive = export_bundle(tmp_path / "source", tmp_path / "backup.cda")
    target = tmp_path / "target"
    apply_import(preview_import(archive, target))
    restored = scan_recordings(target)
    assert {s.recording.id for s in restored} == {r.id for r in records}
    assert all(bundle.valid_audio(s.recording) for s in restored)


def test_file_transfer_round_trip_idempotence_and_unknown_data(client, tmp_path):
    records = collection(client, tmp_path / "desktop")
    expected = {r.id for r in records}
    source = tmp_path / "transfer.cda"
    export_bundle(tmp_path / "desktop", source)
    for name in ("android-storage", "ios-storage", "returned-desktop"):
        target = tmp_path / name
        preview = preview_import(source, target)
        assert set(preview.added) == expected and not preview.conflicts
        apply_import(preview)
        current = sorted(scan_recordings(target), key=lambda s: s.recording.id != records[0].id)
        assert {s.recording.id for s in current} == expected
        assert len({s.recording.path for s in current}) == 1
        assert cached_translation(current[0], "russian").texts == ("my bank",)
        assert json.loads(current[0].recording.reference.read_bytes())["unknown_future_field"] == {
            "retain": [1, "text"]
        }
        again = preview_import(source, target)
        assert set(again.unchanged) == expected and not again.conflicts
        before = {p.name: p.read_bytes() for p in target.iterdir()}
        assert apply_import(again) is None
        assert before == {p.name: p.read_bytes() for p in target.iterdir()}
        export_bundle(target, source, replace=True)
    # These are Python storage operations, not emulator/device validation.
    assert (
        json.loads((target / ".anki-mapping.json").read_bytes())["notes"][records[0].id]["guid"]
        == "oldGUID"
    )


def test_conflicts_require_choice_and_stale_preview_cannot_overwrite_edit(client, tmp_path):
    records = collection(client, tmp_path / "source")
    archive = export_bundle(tmp_path / "source", tmp_path / "bundle.cda")
    target = tmp_path / "target"
    apply_import(preview_import(archive, target))
    local = next(s for s in scan_recordings(target) if s.recording.id == records[0].id)
    edit_translation(local, "russian", "new edit")
    preview = preview_import(archive, target)
    assert preview.conflicts == (records[0].id,)
    original = local.recording.reference.read_bytes()
    with pytest.raises(ValueError, match="Resolve"):
        apply_import(preview)
    assert local.recording.reference.read_bytes() == original
    apply_import(preview, {records[0].id: "existing"})
    assert local.recording.reference.read_bytes() == original
    preview = preview_import(archive, target)
    edit_translation(local, "russian", "even newer")
    with pytest.raises(ValueError, match="changed"):
        apply_import(preview, {records[0].id: "incoming"})
    preview = preview_import(archive, target)
    backup = apply_import(preview, {records[0].id: "incoming"})
    assert cached_translation(
        next(s for s in scan_recordings(backup) if s.recording.id == records[0].id), "russian"
    ).texts == ("even newer",)
    assert cached_translation(
        next(s for s in scan_recordings(target) if s.recording.id == records[0].id), "russian"
    ).texts == ("my bank",)


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize("changed_audio", [False, True])
def test_replacing_native_record_does_not_resurrect_old_media(
    client, tmp_path, shared, changed_audio
):
    target = tmp_path / "target"
    target.mkdir()
    client.session.get.return_value = response(AUDIO)
    choices = variants(bank())
    records = [save(client, target, choices[0])]
    if shared:
        records.append(save(client, target, choices[1]))
    original_audio = records[0].path
    # A genuinely independent MP3-only entry must survive cleanup.
    standalone = target / "hello.us.mp3"
    standalone.write_bytes(b"ID3standalone independent")
    expected_ids = {s.recording.id for s in scan_recordings(target)}
    incoming = tmp_path / "incoming"
    archive = export_bundle(target, tmp_path / "bundle.cda")
    apply_import(preview_import(archive, incoming))
    imported = next(s for s in scan_recordings(incoming) if s.recording.id == records[0].id)
    edit_translation(imported, "russian", "incoming edit")
    if changed_audio:
        imported.recording.path.write_bytes(b"ID3new source recording")
        for saved in scan_recordings(incoming):
            if saved.recording.path == imported.recording.path:
                save_metadata(
                    replace(saved.recording, audio_sha256=bundle._sha(b"ID3new source recording"))
                )
    export_bundle(incoming, archive, replace=True)
    preview = preview_import(archive, target)
    backup = apply_import(preview, {i: "incoming" for i in preview.conflicts})
    current = scan_recordings(target)
    assert len(current) == len(expected_ids)
    assert {s.recording.id for s in current} == expected_ids
    assert cached_translation(
        next(s for s in current if s.recording.id == records[0].id), "russian"
    ).texts == ("incoming edit",)
    assert standalone.read_bytes() == b"ID3standalone independent"
    assert original_audio.exists() == (shared and not changed_audio)
    assert (backup / original_audio.name).read_bytes() == AUDIO
    again = preview_import(archive, target)
    assert not again.added and not again.conflicts
    assert apply_import(again) is None


@pytest.mark.parametrize("damage", [None, b"corrupt"])
@pytest.mark.parametrize("portable", [False, True])
def test_backup_restores_missing_or_corrupt_local_media(client, tmp_path, damage, portable):
    records = collection(client, tmp_path / "source")
    archive = export_bundle(tmp_path / "source", tmp_path / "backup.cda")
    target = tmp_path / "source"
    if portable:
        target = tmp_path / "target"
        apply_import(preview_import(archive, target))
    current = scan_recordings(target)
    audio = current[0].recording.path
    if damage is None:
        audio.unlink()
    else:
        audio.write_bytes(damage)
    preview = preview_import(archive, target)
    assert set(preview.conflicts) == {r.id for r in records}
    # Keeping a broken local version is still an explicit, non-destructive choice.
    assert apply_import(preview, {i: "existing" for i in preview.conflicts}) is None
    backup = apply_import(preview, {i: "incoming" for i in preview.conflicts})
    restored = scan_recordings(target)
    assert {s.recording.id for s in restored} == {r.id for r in records}
    assert len(restored) == len(records)
    assert all(bundle.valid_audio(s.recording) for s in restored)
    if damage is None:
        assert not (backup / audio.name).exists()
    else:
        assert (backup / audio.name).read_bytes() == damage
    assert not preview_import(archive, target).conflicts


def test_unrelated_missing_media_does_not_block_import(client, tmp_path):
    records = collection(client, tmp_path / "source")
    archive = export_bundle(tmp_path / "source", tmp_path / "backup.cda")
    target = tmp_path / "target"
    target.mkdir()
    client.session.get.return_value = response(AUDIO)
    local = save(client, target, variants(bank())[0])
    local.path.unlink()
    metadata = local.reference.read_bytes()
    preview = preview_import(archive, target)
    assert set(preview.added) == {r.id for r in records}
    apply_import(preview)
    assert local.reference.read_bytes() == metadata
    assert not local.path.exists()
    assert len(scan_recordings(target)) == len(records) + 1


def test_import_never_overwrites_unowned_file_or_changes_original_on_publish_failure(
    client, tmp_path, monkeypatch
):
    target = tmp_path / "target"
    target.mkdir()
    client.session.get.return_value = response(AUDIO)
    record = save(client, target, variants(bank())[0])
    archive = export_bundle(target, tmp_path / "backup.cda")
    edit_translation(read_recording(record.reference), "russian", "local edit")
    unrelated = target / f"audio-{bundle._sha(AUDIO)}.us.mp3"
    unrelated.write_bytes(b"ID3independent content")
    before = {p.name: p.read_bytes() for p in target.iterdir()}
    with pytest.raises(ValueError, match="Conflicting local audio"):
        apply_import(preview_import(archive, target), {record.id: "incoming"})
    assert before == {p.name: p.read_bytes() for p in target.iterdir()}
    unrelated.unlink()
    before = {p.name: p.read_bytes() for p in target.iterdir()}
    original_replace = bundle.os.replace

    def fail_publication(source, destination):
        if Path(source).name == "collection":
            raise OSError("disk full during publication")
        return original_replace(source, destination)

    monkeypatch.setattr(bundle.os, "replace", fail_publication)
    with pytest.raises(OSError, match="disk full"):
        apply_import(preview_import(archive, target), {record.id: "incoming"})
    assert before == {p.name: p.read_bytes() for p in target.iterdir()}


@pytest.mark.parametrize(
    "kind",
    [
        "traversal",
        "absolute",
        "backslash",
        "duplicate",
        "checksum",
        "future",
        "missing",
        "symlink",
        "size",
    ],
)
def test_hostile_or_corrupt_bundles_leave_collection_intact(client, tmp_path, kind):
    collection(client, tmp_path / "source")
    archive = export_bundle(tmp_path / "source", tmp_path / "bundle.cda")
    target = tmp_path / "target"
    apply_import(preview_import(archive, target))
    before = {p.name: p.read_bytes() for p in target.iterdir()}
    with ZipFile(archive) as z:
        files = {n: z.read(n) for n in z.namelist()}
    manifest = json.loads(files["manifest.json"])
    if kind in {"traversal", "absolute", "backslash"}:
        files[
            {"traversal": "../outside", "absolute": "/outside", "backslash": "collection\\outside"}[
                kind
            ]
        ] = b"x"
    elif kind == "checksum":
        files[next(n for n in files if n.endswith(".mp3"))] = b"ID3changed"
    elif kind == "future":
        manifest["version"] = 999
    elif kind == "missing":
        files.pop(next(n for n in files if n.endswith(".mp3")))
    elif kind == "size":
        manifest["files"][next(iter(manifest["files"]))]["size"] = 999999999
    files["manifest.json"] = json.dumps(manifest).encode()
    with ZipFile(archive, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
        if kind == "duplicate":
            with pytest.warns(UserWarning):
                z.writestr("manifest.json", files["manifest.json"])
        if kind == "symlink":
            from zipfile import ZipInfo

            info = ZipInfo("collection/link")
            info.external_attr = 0o120777 << 16
            z.writestr(info, "../../outside")
    with pytest.raises(ValueError):
        preview_import(archive, target)
    assert before == {p.name: p.read_bytes() for p in target.iterdir()}


def test_failed_publication_rolls_back_and_keeps_original(client, tmp_path, monkeypatch):
    collection(client, tmp_path / "source")
    archive = export_bundle(tmp_path / "source", tmp_path / "bundle.cda")
    target = tmp_path / "target"
    target.mkdir()
    (target / "unrelated.txt").write_text("retain me")
    preview = preview_import(archive, target)
    original = os.replace

    def fail(source, dest):
        if Path(source).name == "collection":
            raise OSError("disk full / interrupted rename")
        return original(source, dest)

    monkeypatch.setattr(bundle.os, "replace", fail)
    with pytest.raises(OSError, match="disk full"):
        apply_import(preview)
    assert (target / "unrelated.txt").read_text() == "retain me"
    assert not scan_recordings(target)


def test_recover_directory_swap_after_process_interruption(tmp_path):
    target = tmp_path / "collection"
    backup = tmp_path / (".collection.backup-" + "a" * 32)
    backup.mkdir()
    (backup / "precious").write_text("retained")
    (tmp_path / ".collection.import.json").write_text(
        json.dumps({"version": 1, "backup": backup.name})
    )
    assert scan_recordings(target) == []
    assert (target / "precious").read_text() == "retained"


def test_external_symlink_rejected_internal_legacy_alias_supported(tmp_path):
    target = tmp_path / "collection"
    target.mkdir()
    outside = tmp_path / "private.us.mp3"
    outside.write_bytes(AUDIO)
    link = target / "alias.us.mp3"
    link.symlink_to(outside)
    with pytest.raises(ValueError, match="External"):
        export_bundle(target, tmp_path / "bundle.cda")
    link.unlink()
    (target / "bank.us.mp3").write_bytes(AUDIO)
    link.symlink_to("bank.us.mp3")
    export_bundle(target, tmp_path / "bundle.cda")
    destination = tmp_path / "imported"
    apply_import(preview_import(tmp_path / "bundle.cda", destination))
    assert len(scan_recordings(destination)) == 2
    assert len(list(destination.glob("*.mp3"))) == 1


def test_metadata_edit_preserves_unknown_fields_and_foreign_cache(client, tmp_path):
    records = collection(client, tmp_path / "source")
    saved = read_recording(records[0].reference)
    save_metadata(replace(saved.recording, definition="updated"))
    data = json.loads(records[0].reference.read_bytes())
    assert data["unknown_future_field"] == {"retain": [1, "text"]}
    assert data["translation_cache"][0]["opaque"] == {"author": "me"}
    assert data["translation_cache"][0]["options"][0]["future_option"] is True


def test_import_refuses_metadata_symlink_without_modifying_original(client, tmp_path):
    records = collection(client, tmp_path / "source")
    archive = export_bundle(tmp_path / "source", tmp_path / "bundle.cda")
    target = tmp_path / "target"
    target.mkdir()
    original = records[0].reference
    before = original.read_bytes()
    (target / original.name).symlink_to(original)
    with pytest.raises(ValueError, match="metadata symlinks"):
        preview_import(archive, target)
    assert original.read_bytes() == before

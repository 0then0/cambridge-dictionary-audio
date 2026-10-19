"""Versioned collection transfer, bounded ZIP validation and transactional import.

Bundle layout is specified in docs/mobile/storage.md. No network or Qt dependency.
"""

import hashlib
import json
import os
import re
import shutil
import stat
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile, TemporaryDirectory
from uuid import uuid4
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from .anki import MAPPING_FILE, SOURCES
from .dictionary import is_mp3
from .library import _METADATA_LOCK, read_recording, scan_recordings, valid_audio

FORMAT = "cambridge-dictionary-audio-collection"
VERSION = 1
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024 * 1024
MAX_FILES = 100_000
MAX_MANIFEST = 8 * 1024 * 1024


def _json(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def _sha(content):
    return hashlib.sha256(content).hexdigest()


def _safe_name(value):
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or "\0" in value
        or PurePosixPath(value).is_absolute()
        or any(p in {"", ".", ".."} for p in value.split("/"))
    ):
        raise ValueError(f"Unsafe archive path: {value!r}")
    return value


def _read_json(content):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(content, object_pairs_hook=unique)


def _mapping(data):
    if (
        not isinstance(data, dict)
        or data.get("version") != 1
        or not isinstance(data.get("notes"), dict)
        or not isinstance(data.get("last_export", 0), int)
    ):
        raise ValueError("Unsupported Anki identity mapping.")
    for identity, note in data["notes"].items():
        if (
            not re.fullmatch(r"[a-f0-9]{24}", identity)
            or not isinstance(note, dict)
            or not isinstance(note.get("guid"), str)
            or not isinstance(note.get("model"), dict)
        ):
            raise ValueError("Invalid adopted Anki identity.")
    return data


def _document(saved):
    """Snapshot a readable legacy entry without modifying the original."""
    record = saved.recording
    sidecar = record.reference.with_suffix(".json")
    previous = {}
    if sidecar.exists():
        previous = _read_json(sidecar.read_bytes())
        if not isinstance(previous, dict) or previous.get("version") not in {1, 2, 3}:
            raise ValueError(f"Unsupported or corrupt metadata: {sidecar}")
    data = previous | asdict(record)
    data.pop("path", None)
    data.pop("metadata_path", None)
    # Freeze MP3-only and v1 identities before moving to another platform.
    data.update(
        version=3,
        variant_id=record.id,
        audio_file=f"audio-{_sha(record.path.read_bytes())}.{record.accent}.mp3",
        audio_sha256=_sha(record.path.read_bytes()),
        separate_metadata=True,
    )
    data.setdefault("translations", list(saved.translations))
    data.setdefault("translation_language", saved.translation_language)
    data.setdefault("translation_cache", [t.to_dict() for t in saved.translation_cache])
    # Upgrade a v1 flat cache to the exact association already used by Python.
    if previous.get("version") == 1:
        data["translation_cache"] = [t.to_dict() for t in saved.translation_cache]
    return data


def export_bundle(directory: Path, destination: Path) -> Path:
    """Export all entries; refuse external symlinks and unverifiable media."""
    directory, destination = Path(directory).absolute(), Path(destination).absolute()
    if directory.is_symlink() or destination.is_symlink():
        raise ValueError("Collection and bundle destination must not be symbolic links.")
    if destination.resolve().is_relative_to(directory.resolve()):
        raise ValueError("Save the backup outside the collection directory.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with _METADATA_LOCK:
        recover_import(directory)
        files, records, seen = {}, [], set()
        # Never silently omit corrupt/future sidecars or unknown-language data.
        for path in directory.glob("*.json"):
            if path.name.startswith("."):
                continue
            if not path.resolve().is_relative_to(directory.resolve()):
                raise ValueError(f"External metadata symlink: {path.name}")
            data = _read_json(path.read_bytes())
            if not isinstance(data, dict) or data.get("version") not in {1, 2, 3}:
                raise ValueError(f"Unsupported or corrupt metadata: {path.name}")
        for saved in scan_recordings(directory):
            record = saved.recording
            if not record.path.resolve().is_relative_to(directory.resolve()):
                raise ValueError(f"External audio symlink: {record.path.name}")
            if not valid_audio(record):
                raise ValueError(f"Missing or corrupt MP3: {record.path.name}")
            if record.id in seen:
                raise ValueError(f"Duplicate permanent collection ID: {record.id}")
            seen.add(record.id)
            document = _document(saved)
            name = f"collection/{record.id}.{record.accent}.json"
            files[name] = _json(document)
            files["collection/" + document["audio_file"]] = record.path.read_bytes()
            records.append({"id": record.id, "metadata": name})
        mapping_path = directory / MAPPING_FILE
        if mapping_path.exists():
            if mapping_path.is_symlink():
                raise ValueError("Anki mapping must not be a symbolic link.")
            files["collection/" + MAPPING_FILE] = _json(
                _mapping(_read_json(mapping_path.read_bytes()))
            )
        files["SOURCES.txt"] = SOURCES.encode()
        manifest = {
            "format": FORMAT,
            "version": VERSION,
            "storage_version": 3,
            "records": records,
            "files": {n: {"sha256": _sha(b), "size": len(b)} for n, b in files.items()},
        }
        if len(files) > MAX_FILES or sum(map(len, files.values())) > MAX_TOTAL:
            raise ValueError("Collection exceeds supported bundle limits.")
        temporary = None
        try:
            with NamedTemporaryFile(dir=destination.parent, suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
            with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", _json(manifest))
                for name, content in files.items():
                    if len(content) > MAX_FILE:
                        raise ValueError(f"File exceeds bundle limit: {name}")
                    archive.writestr(name, content)
            # Validate our output before replacing even an existing backup.
            _load_bundle(temporary)
            with temporary.open("rb") as stream:
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
    return destination


def _load_bundle(source):
    try:
        with ZipFile(source) as archive:
            members = archive.infolist()
            names = [m.filename for m in members]
            if len(names) > MAX_FILES or len(set(names)) != len(names):
                raise ValueError("Too many or duplicate archive members.")
            folded = [n.casefold() for n in names]
            if len(set(folded)) != len(names):
                raise ValueError("Archive paths collide on case-insensitive filesystems.")
            total = 0
            for member in members:
                _safe_name(member.filename)
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode) or member.is_dir() or member.flag_bits & 1:
                    raise ValueError("Links, directory and encrypted ZIP members are unsupported.")
                if member.file_size > (
                    MAX_MANIFEST if member.filename == "manifest.json" else MAX_FILE
                ):
                    raise ValueError("Archive member is too large.")
                total += member.file_size
            if total > MAX_TOTAL:
                raise ValueError("Archive exceeds total size limit.")
            manifest = _read_json(archive.read("manifest.json"))
            if (
                not isinstance(manifest, dict)
                or manifest.get("format") != FORMAT
                or manifest.get("version") != VERSION
                or manifest.get("storage_version") != 3
                or not isinstance(manifest.get("files"), dict)
                or not isinstance(manifest.get("records"), list)
            ):
                raise ValueError("Unsupported collection bundle version.")
            if set(names) != {"manifest.json", *manifest["files"]}:
                raise ValueError("Archive does not match its manifest.")
            files = {}
            for name, expected in manifest["files"].items():
                if not isinstance(expected, dict):
                    raise ValueError("Invalid checksum manifest.")
                content = archive.read(name)
                if len(content) != expected.get("size") or _sha(content) != expected.get("sha256"):
                    raise ValueError(f"Size / SHA-256 mismatch: {name}")
                files[name] = content
    except (BadZipFile, KeyError, TypeError, UnicodeError) as exc:
        raise ValueError(f"Unreadable collection bundle: {exc}") from exc
    records, referenced = {}, set()
    for item in manifest["records"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid collection record reference.")
        identity, name = item.get("id"), item.get("metadata")
        if not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{24}", identity):
            raise ValueError("Invalid permanent collection ID.")
        if identity in records or name not in files:
            raise ValueError("Duplicate identity or missing metadata.")
        data = _read_json(files[name])
        if not isinstance(data, dict) or data.get("version") != 3:
            raise ValueError("Unsupported metadata schema in bundle.")
        accent = data.get("accent")
        if (
            accent not in {"us", "uk"}
            or name != f"collection/{identity}.{accent}.json"
            or data.get("variant_id") != identity
            or not all(isinstance(data.get(k), str) for k in ("word", "ipa", "definition"))
        ):
            raise ValueError("Inconsistent metadata identity / fields.")
        audio = _safe_name(data.get("audio_file"))
        if "/" in audio or not audio.endswith(f".{accent}.mp3"):
            raise ValueError("Invalid portable audio reference.")
        audio_name = "collection/" + audio
        content = files.get(audio_name, b"")
        if not is_mp3(content) or _sha(content) != data.get("audio_sha256"):
            raise ValueError("Missing or corrupt referenced audio.")
        records[identity] = data
        referenced.update((name, audio_name))
    allowed = referenced | {"collection/" + MAPPING_FILE, "SOURCES.txt"}
    if set(files) - allowed:
        raise ValueError("Bundle contains unreferenced collection data.")
    mapping = (
        _mapping(_read_json(files["collection/" + MAPPING_FILE]))
        if "collection/" + MAPPING_FILE in files
        else {"version": 1, "notes": {}}
    )
    return files, records, mapping


def _revision(directory):
    state = {}
    if directory.exists():
        for path in directory.iterdir():
            if path.suffix.lower() in {".json", ".mp3"}:
                # Include raw bytes and link targets: a preview becomes stale on any edit.
                state[path.name] = _sha(path.read_bytes()) if path.is_file() else "missing"
                if path.is_symlink():
                    state[path.name] += ":" + os.readlink(path)
    return _sha(_json(state))


def _canonical(data):
    return {k: v for k, v in data.items() if k not in {"audio_file", "separate_metadata"}}


@dataclass(frozen=True)
class ImportPreview:
    source: Path
    directory: Path
    bundle_sha256: str
    revision: str
    added: tuple[str, ...]
    unchanged: tuple[str, ...]
    conflicts: tuple[str, ...]


def preview_import(source: Path, directory: Path) -> ImportPreview:
    source, directory = Path(source).absolute(), Path(directory).absolute()
    if directory.is_symlink():
        raise ValueError("Collection directory must not be a symbolic link.")
    with _METADATA_LOCK:
        recover_import(directory)
        # A copied absolute metadata symlink could otherwise resolve back into
        # the live collection while validating or editing staging.
        if any(path.is_symlink() for path in directory.glob("*.json")):
            raise ValueError("Materialize metadata symlinks before importing into this folder.")
        if (directory / MAPPING_FILE).is_symlink():
            raise ValueError("Anki mapping must not be a symbolic link.")
        _, incoming, mapping = _load_bundle(source)
        local = {s.recording.id: s for s in scan_recordings(directory)}
        existing_mapping = directory / MAPPING_FILE
        current_mapping = (
            _mapping(_read_json(existing_mapping.read_bytes()))
            if existing_mapping.exists()
            else {"notes": {}}
        )
        added, unchanged, conflicts = [], [], []
        for identity, data in incoming.items():
            mapping_conflict = (
                identity in mapping["notes"]
                and identity in current_mapping["notes"]
                and mapping["notes"][identity] != current_mapping["notes"][identity]
            )
            if identity not in local:
                added.append(identity)
            elif (
                valid_audio(local[identity].recording)
                and _canonical(data) == _canonical(_document(local[identity]))
                and not mapping_conflict
            ):
                unchanged.append(identity)
            else:
                conflicts.append(identity)
        if set(mapping["notes"]) - set(incoming):
            # A full mapping may include deleted notes. Retain it, but require a choice
            # for conflicting orphan identities as well.
            for identity in set(mapping["notes"]) & set(current_mapping["notes"]) - set(incoming):
                if mapping["notes"][identity] != current_mapping["notes"][identity]:
                    conflicts.append(identity)
        return ImportPreview(
            source,
            directory,
            _sha(source.read_bytes()),
            _revision(directory),
            tuple(added),
            tuple(unchanged),
            tuple(conflicts),
        )


def _journal_path(directory):
    return directory.parent / f".{directory.name}.import.json"


def _atomic_json(path, data):
    with NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(_json(data))
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def recover_import(directory: Path) -> None:
    """Recover the only unsafe crash window: old directory moved, new not yet moved."""
    directory = Path(directory).absolute()
    journal = _journal_path(directory)
    if not journal.exists():
        return
    if journal.is_symlink():
        raise ValueError("Import journal must not be a symbolic link.")
    state = _read_json(journal.read_bytes())
    backup_name = state.get("backup", "")
    if not re.fullmatch(re.escape(f".{directory.name}.backup-") + r"[0-9a-f]{32}", backup_name):
        raise ValueError("Invalid import recovery journal.")
    backup = directory.parent / backup_name
    if backup.is_symlink():
        raise ValueError("Import backup must not be a symbolic link.")
    if not directory.exists() and backup.is_dir():
        os.replace(backup, directory)
    journal.unlink()


def apply_import(preview: ImportPreview, decisions: dict[str, str] | None = None) -> Path | None:
    """Apply a reviewed preview; return the retained backup, or None for a no-op.

    Every conflict needs an explicit 'existing' or 'incoming' choice. There is no
    device-clock last-writer policy. Reject stale previews before any mutation.
    """
    decisions = decisions or {}
    if any(decisions.get(i) not in {"existing", "incoming"} for i in preview.conflicts):
        raise ValueError("Resolve every conflicting ID before importing.")
    directory = preview.directory
    with _METADATA_LOCK:
        if (
            _sha(preview.source.read_bytes()) != preview.bundle_sha256
            or _revision(directory) != preview.revision
        ):
            raise ValueError("Collection or bundle changed; preview the import again.")
        files, incoming, mapping = _load_bundle(preview.source)
        selected = set(preview.added) | {i for i in preview.conflicts if decisions[i] == "incoming"}
        existing_mapping_path = directory / MAPPING_FILE
        current_mapping = (
            _mapping(_read_json(existing_mapping_path.read_bytes()))
            if existing_mapping_path.exists()
            else {"version": 1, "notes": {}}
        )
        notes = dict(current_mapping["notes"])
        for identity, mapped in mapping["notes"].items():
            if identity not in preview.conflicts or decisions[identity] == "incoming":
                notes[identity] = mapped
        merged_mapping = (
            mapping
            | current_mapping
            | {
                "version": 1,
                "notes": notes,
                "last_export": max(
                    mapping.get("last_export", 0), current_mapping.get("last_export", 0)
                ),
            }
        )
        if not selected and merged_mapping == current_mapping:
            return None
        directory.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=f".{directory.name}.staging-", dir=directory.parent) as temp:
            staging = Path(temp) / "collection"
            if directory.exists():
                shutil.copytree(directory, staging, symlinks=True)
            else:
                staging.mkdir()
            local = {s.recording.id: s for s in scan_recordings(staging)}
            replacing = selected & incoming.keys()
            for identity in replacing:
                data = incoming[identity]
                old = local.get(identity)
                metadata = (
                    old.recording.reference.with_suffix(".json")
                    if old
                    else staging / f"{identity}.{data['accent']}.json"
                )
                audio_path = staging / data["audio_file"]
                content = files["collection/" + data["audio_file"]]
                if audio_path.is_symlink():
                    raise ValueError(f"Conflicting local audio path: {audio_path.name}")
                if audio_path.exists() and audio_path.read_bytes() != content:
                    owners = [s for s in local.values() if s.recording.path == audio_path]
                    # Repair a managed blob only when every owner expects these exact bytes.
                    if not owners or any(
                        s.recording.audio_sha256 != data["audio_sha256"] for s in owners
                    ):
                        raise ValueError(f"Conflicting local audio path: {audio_path.name}")
                if metadata.is_symlink() or (not old and metadata.exists()):
                    raise ValueError(f"Conflicting local metadata path: {metadata.name}")
                audio_path.write_bytes(content)
                metadata.write_bytes(_json(data))
                saved = read_recording(metadata)
                if (
                    saved is None
                    or saved.recording.id != identity
                    or not valid_audio(saved.recording)
                ):
                    raise ValueError("Staged entry failed validation.")
            referenced = {
                s.recording.path for identity, s in local.items() if identity not in replacing
            } | {staging / incoming[identity]["audio_file"] for identity in replacing}
            # Only retire media owned by replaced entries. Unrelated MP3-only files stay intact.
            for identity in replacing & local.keys():
                old_audio = local[identity].recording.path
                if old_audio not in referenced:
                    old_audio.unlink(missing_ok=True)
            _atomic_json(staging / MAPPING_FILE, merged_mapping)
            # Flush every staged regular file. Never dereference copied symlinks.
            for path in staging.iterdir():
                if path.is_file() and not path.is_symlink():
                    with path.open("rb") as stream:
                        os.fsync(stream.fileno())
            backup = directory.parent / f".{directory.name}.backup-{uuid4().hex}"
            had_previous = directory.exists()
            journal = _journal_path(directory)
            _atomic_json(journal, {"version": 1, "backup": backup.name})
            try:
                if had_previous:
                    os.replace(directory, backup)
                os.replace(staging, directory)
            except BaseException:
                if had_previous and backup.exists() and not directory.exists():
                    os.replace(backup, directory)
                raise
            finally:
                if directory.exists():
                    journal.unlink(missing_ok=True)
            return backup if had_previous else None

"""Local recordings and optional metadata stored beside each MP3."""

import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

from .dictionary import audio_filename, is_mp3, stable_id
from .service import Recording
from .translations import TranslationOption, TranslationResult

# Windows cannot replace a file while another thread holds a normal read handle.
_METADATA_LOCK = RLock()


@dataclass(frozen=True)
class SavedRecording:
    recording: Recording
    translations: tuple[str, ...] = ()
    translation_language: str | None = None
    translation_cache: tuple[TranslationResult, ...] = ()


def read_recording(path: Path) -> SavedRecording | None:
    with _METADATA_LOCK:
        return _read_recording(path)


def _read_recording(path: Path) -> SavedRecording | None:
    path = Path(path)
    metadata = path if path.suffix.lower() == ".json" else path.with_suffix(".json")
    explicit_metadata = path.suffix.lower() == ".json"
    if explicit_metadata:
        path = path.with_suffix(".mp3")
    stem, separator, accent = path.stem.rpartition(".")
    if (
        (not path.is_file() and not metadata.is_file())
        or path.suffix.lower() != ".mp3"
        or not separator
    ):
        return None
    if not stem or accent not in {"us", "uk"}:
        return None
    if not explicit_metadata:
        # A shared MP3 alone does not select a meaning. Accept it only when unambiguous.
        related = []
        for candidate in path.parent.glob("*.json"):
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(data, dict) and (
                    (data.get("version") == 3 and data.get("audio_file") == path.name)
                    or (data.get("version") in {1, 2} and candidate == metadata)
                ):
                    related.append(candidate)
            except (OSError, ValueError):
                continue
        if related:
            return read_recording(related[0]) if len(related) == 1 else None
    if not metadata.exists():
        try:
            if path.stat().st_size == 0:
                return None
        except OSError:
            return None
    # Resolve the directory, preserving the name and sidecar of a symlink alias.
    path = path.parent.resolve() / path.name
    if stem.startswith("_") and audio_filename(stem[1:], accent) == path.name:
        stem = stem[1:]
    record = Recording(stem, accent, path, "", "")
    try:
        with _METADATA_LOCK:
            content = metadata.read_text(encoding="utf-8")
        data = json.loads(content)
        if not isinstance(data, dict) or data.get("version") not in {1, 2, 3}:
            return SavedRecording(record)
        if data["version"] == 3:
            audio_file = data.get("audio_file")
            if (
                not isinstance(audio_file, str)
                or Path(audio_file).name != audio_file
                or "\\" in audio_file
                or not audio_file.endswith(f".{accent}.mp3")
            ):
                return None
            path = path.parent / audio_file
        word = data.get("word")
        if not isinstance(word, str) or (
            data["version"] == 1
            and path.name not in {audio_filename(word, accent), f"{word}.{accent}.mp3"}
        ):
            return SavedRecording(record)
        if not all(isinstance(data.get(key), str) for key in ("ipa", "definition")):
            return SavedRecording(record)
        translations = data.get("translations", [])
        if not isinstance(translations, list) or not all(isinstance(t, str) for t in translations):
            translations = []
        record = Recording(
            word,
            accent,
            path,
            data["ipa"],
            data["definition"],
            data.get("combined") is True,
            *(
                data.get(key, "") if isinstance(data.get(key, ""), str) else ""
                for key in (
                    "part_of_speech",
                    "entry_id",
                    "sense_id",
                    "variant_id",
                    "source_url",
                    "audio_url",
                    "lemma",
                )
            ),
            metadata.resolve() if data.get("separate_metadata") is True else None,
            data.get("source_entry_id", ""),
            data.get("source_sense_id", ""),
            data.get("audio_sha256", ""),
        )
        language = data.get("translation_language")
        if not isinstance(language, str) or not language.strip():
            language = None
        cache = data.get("translation_cache", [])
        if not isinstance(cache, list):
            cache = []
        cache = tuple(
            t
            for item in cache
            if isinstance(item, dict) and (t := TranslationResult.from_dict(item)) is not None
        )
        if data["version"] == 1 and translations and language:
            cache = (
                TranslationResult(
                    language,
                    record.sense_id,
                    "Cambridge",
                    (
                        TranslationOption(
                            stable_id(*translations),
                            tuple(translations),
                            origin="Legacy JSON cache; sense association unverified",
                        ),
                    ),
                ),
            )
        return SavedRecording(record, tuple(translations), language, cache)
    except (OSError, ValueError, TypeError):
        return SavedRecording(record)


def scan_recordings(directory: Path) -> list[SavedRecording]:
    if not directory.exists():
        return []
    records, referenced = [], set()
    for path in directory.glob("*.json"):
        try:
            with _METADATA_LOCK:
                data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("version") in {1, 2, 3}:
            saved = read_recording(path)
            if saved:
                records.append(saved)
                referenced.add(saved.recording.path)
    for path in directory.glob("*.mp3"):
        if (
            path.parent.resolve() / path.name not in referenced
            and (saved := read_recording(path))
            and saved.recording.path not in referenced
        ):
            # An old sidecar can now point to replacement audio. Its former MP3
            # stays on disk, but must not add the same collection entry twice.
            records.append(saved)
            referenced.add(saved.recording.path)
    return sorted(
        records, key=lambda saved: (saved.recording.word.casefold(), saved.recording.accent)
    )


def save_metadata(
    record: Recording,
    translations: tuple[str, ...] = (),
    translation_language: str | None = None,
    *,
    translation_cache: tuple[TranslationResult, ...] | None = None,
) -> None:
    with _METADATA_LOCK:
        destination = record.reference.with_suffix(".json")
        # Serialize read/merge/write as well as publication: late metadata updates must
        # preserve translations and Windows readers must close before os.replace.
        previous = {}
        try:
            previous = json.loads(destination.read_bytes())
            if not isinstance(previous, dict) or previous.get("version") not in {1, 2, 3}:
                raise FileExistsError(f"Unrecognized metadata: {destination}")
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            raise FileExistsError(f"Unreadable metadata: {destination}") from exc
        if previous and previous.get("version") not in {1, 2, 3}:
            raise FileExistsError(f"Unrecognized metadata: {destination}")
        previous_saved = read_recording(record.reference)
        if previous_saved and previous_saved.recording.id != record.id:
            # A legacy unassociated file may acquire a source identity on explicit save.
            if previous_saved.recording.variant_id:
                raise FileExistsError(
                    f"Metadata belongs to another collection record: {destination}"
                )
        if translation_cache is None:
            provided_translations = bool(translations)
            if not provided_translations:
                # A metadata-only save must retain legacy translations too, including
                # an unknown language. Never relabel an old value with today's option.
                old_texts = previous.get("translations", [])
                if isinstance(old_texts, list) and all(isinstance(t, str) for t in old_texts):
                    translations = tuple(old_texts)
                    translation_language = previous.get("translation_language")
            cache = previous_saved.translation_cache if previous_saved else ()
            # Upgrade a legacy association only when its recorded meaning agrees.
            # A changed meaning retains its old cache, but cannot use it as a fallback.
            if (
                previous_saved
                and previous_saved.recording.word == record.word
                and not previous_saved.recording.sense_id
                and record.sense_id
                and record.definition
                and previous_saved.recording.definition.casefold() == record.definition.casefold()
                and (
                    not previous_saved.recording.part_of_speech
                    or previous_saved.recording.part_of_speech == record.part_of_speech
                )
            ):
                cache = tuple(
                    replace(t, sense_id=record.sense_id) if not t.sense_id else t for t in cache
                )
            if record.sense_id and (
                previous_saved is None or previous_saved.recording.sense_id != record.sense_id
            ):
                # A newly saved accent/pronunciation shares resolved sense translations.
                for related in scan_recordings(record.path.parent):
                    if (
                        related.recording.word != record.word
                        or related.recording.meaning_key != record.meaning_key
                    ):
                        continue
                    for result in related.translation_cache:
                        if (
                            (result.source == "User" or result.selected_id or result.texts)
                            and result.sense_id == related.recording.sense_id
                            and not any(
                                t.source == result.source
                                and t.language == result.language
                                and t.sense_id == record.sense_id
                                for t in cache
                            )
                        ):
                            cache += (replace(result, sense_id=record.sense_id),)
            if provided_translations and translation_language:
                result = TranslationResult(
                    translation_language,
                    record.sense_id,
                    "Cambridge",
                    (
                        TranslationOption(
                            stable_id(*translations), tuple(translations), origin=record.source_url
                        ),
                    ),
                )
                # Compatibility callers must never overwrite detailed source provenance.
                if not any(
                    (t.language, t.source, t.sense_id)
                    == (result.language, result.source, result.sense_id)
                    for t in cache
                ):
                    cache += (result,)
        else:
            cache = translation_cache
            from .translations import cached_translation

            translation_language = (
                cache[-1].language if cache else previous.get("translation_language")
            )
            active = cached_translation(
                SavedRecording(record, translation_cache=cache), translation_language
            )
            translations = active.texts if active else ()
        data = asdict(record)
        data.pop("path")
        data.pop("metadata_path")
        data.update(
            version=3,
            audio_file=record.path.name,
            separate_metadata=record.metadata_path is not None,
            translations=translations,
            translation_language=translation_language,
            translation_cache=[t.to_dict() for t in cache],
        )
        temporary = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=destination.parent, suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def valid_audio(record: Recording) -> bool:
    """Check the signature and, for managed files, the saved content checksum."""
    import hashlib

    try:
        content = record.path.read_bytes()
        return is_mp3(content) and (
            not record.audio_sha256 or hashlib.sha256(content).hexdigest() == record.audio_sha256
        )
    except OSError:
        return False


def delete_recording(record: Recording) -> None:
    """Remove one meaning; retain media referenced by another meaning or symlink."""
    with _METADATA_LOCK:
        others = [
            s.recording
            for s in scan_recordings(record.path.parent)
            if s.recording.reference != record.reference
        ]
        record.reference.with_suffix(".json").unlink(missing_ok=True)
        if not any(r.path.resolve() == record.path.resolve() for r in others):
            record.path.unlink(missing_ok=True)

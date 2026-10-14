"""Local recordings and optional metadata stored beside each MP3."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from .dictionary import audio_filename
from .service import Recording


@dataclass(frozen=True)
class SavedRecording:
    recording: Recording
    translations: tuple[str, ...] = ()
    translation_language: str | None = None


def read_recording(path: Path) -> SavedRecording | None:
    stem, separator, accent = path.stem.rpartition(".")
    if not path.is_file() or path.suffix.lower() != ".mp3" or not separator:
        return None
    if not stem or accent not in {"us", "uk"}:
        return None
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
        data = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1:
            return SavedRecording(record)
        word = data.get("word")
        if not isinstance(word, str) or audio_filename(word, accent) != path.name:
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
        )
        language = data.get("translation_language")
        if not isinstance(language, str) or not language.strip():
            language = None
        return SavedRecording(record, tuple(translations), language)
    except (OSError, ValueError):
        return SavedRecording(record)


def scan_recordings(directory: Path) -> list[SavedRecording]:
    if not directory.exists():
        return []
    records = [saved for path in directory.iterdir() if (saved := read_recording(path))]
    return sorted(
        records, key=lambda saved: (saved.recording.word.casefold(), saved.recording.accent)
    )


def save_metadata(
    record: Recording, translations: tuple[str, ...] = (), translation_language: str | None = None
) -> None:
    destination = record.path.with_suffix(".json")
    data = {
        "version": 1,
        "word": record.word,
        "ipa": record.ipa,
        "definition": record.definition,
        "combined": record.combined,
        "translations": translations,
        "translation_language": translation_language,
    }
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent, suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

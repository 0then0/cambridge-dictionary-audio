"""Download orchestration shared by the CLI and desktop interface."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .audio import combine_phrase
from .dictionary import (
    AudioNotFoundError,
    CambridgeClient,
    CambridgeError,
    audio_filename,
    normalize_word,
)


class DownloadCancelled(CambridgeError):
    """A caller cancelled work between network requests."""


@dataclass(frozen=True)
class Recording:
    word: str
    accent: str
    path: Path
    ipa: str
    definition: str
    combined: bool = False


@dataclass(frozen=True)
class DownloadResult:
    recordings: tuple[Recording, ...]
    translations: tuple[str, ...] = ()
    translation_error: str = ""


def download_recordings(
    client: CambridgeClient,
    word: str,
    output_dir: Path,
    accent: str = "us",
    *,
    overwrite: bool = False,
    combine: bool = False,
    translation: str | None = None,
    on_recording: Callable[[Recording], None] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> DownloadResult:
    word = normalize_word(word, client.language)
    if accent not in {"us", "uk", "both"}:
        raise ValueError("Accent must be us, uk or both.")
    if check_cancelled:
        check_cancelled()
    entries = ()
    try:
        entries = client.lookup(word)
    except AudioNotFoundError:
        if not combine or len(word.split()) < 2:
            raise
    recordings = []
    for region in ("uk", "us") if accent == "both" else (accent,):
        if check_cancelled:
            check_cancelled()
        destination = output_dir.resolve() / audio_filename(word, region)
        combined = False
        ipa = ""
        try:
            pronunciation = client.download(entries, region, destination, overwrite=overwrite)
            ipa = pronunciation.ipa
        except AudioNotFoundError:
            if not combine or len(word.split()) < 2:
                raise
            combine_phrase(
                client,
                word,
                region,
                destination,
                overwrite=overwrite,
                check_cancelled=check_cancelled,
            )
            combined = True
        recording = Recording(
            word,
            region,
            destination,
            ipa,
            entries[0].definition if entries else "",
            combined,
        )
        recordings.append(recording)
        if on_recording:
            on_recording(recording)
    translations = ()
    translation_error = ""
    if translation:
        if check_cancelled:
            check_cancelled()
        try:
            translations = client.translations(word, translation)
        except (CambridgeError, ValueError) as exc:
            translation_error = str(exc)
    return DownloadResult(tuple(recordings), translations, translation_error)

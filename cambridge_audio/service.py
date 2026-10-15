"""Download orchestration shared by the CLI and desktop interface."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .audio import combine_phrase
from .dictionary import (
    AudioNotFoundError,
    CambridgeClient,
    CambridgeError,
    Entry,
    SelectionRequired,
    audio_filename,
    normalize_word,
    stable_id,
    variants,
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
    part_of_speech: str = ""
    entry_id: str = ""
    sense_id: str = ""
    variant_id: str = ""
    source_url: str = ""
    audio_url: str = ""
    lemma: str = ""

    @property
    def id(self):
        if self.variant_id:
            return (
                self.variant_id
                if re.fullmatch(r"[0-9a-f]{24}", self.variant_id)
                else stable_id("variant", self.variant_id)
            )
        return stable_id(
            "legacy",
            self.word.casefold(),
            self.accent,
            "combined" if self.combined else "recording",
        )

    @property
    def label(self):
        return (
            f"{self.word} · {self.accent.upper()} · {self.part_of_speech} · "
            f"{self.definition[:70]} · /{self.ipa}/"
        )


@dataclass(frozen=True)
class DownloadResult:
    recordings: tuple[Recording, ...]
    translations: tuple[str, ...] = ()
    translation_error: str = ""
    translation_results: tuple = ()


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
    variant_id: str | None = None,
    entries: tuple[Entry, ...] | None = None,
    target: Recording | None = None,
    dictionary_dir: Path | None = None,
    offline_translation: bool = False,
) -> DownloadResult:
    word = normalize_word(word, client.language)
    if accent not in {"us", "uk", "both"}:
        raise ValueError("Accent must be us, uk or both.")
    if target and (target.word != word or target.accent != accent):
        raise ValueError("The selected recording does not match the requested word and accent.")
    if check_cancelled:
        check_cancelled()
    if entries is None:
        entries = ()
        try:
            entries = client.lookup(word)
        except AudioNotFoundError:
            if not combine or len(word.split()) < 2:
                raise
    choices = variants(entries, accent)
    chosen = None
    wanted = target.variant_id if target else variant_id
    if wanted:
        chosen = next((v for v in choices if v.id == wanted), None)
        if chosen is None:
            raise ValueError(
                "The selected pronunciation is no longer available. Choose a variant again."
            )
    elif any(
        sum(v.pronunciation.accent == region for v in choices) > 1
        for region in (("uk", "us") if accent == "both" else (accent,))
    ):
        raise SelectionRequired(choices, entries)
    recordings = []
    regions = (
        (chosen.pronunciation.accent,)
        if chosen
        else ("uk", "us")
        if accent == "both"
        else (accent,)
    )
    for region in regions:
        if check_cancelled:
            check_cancelled()
        choice = chosen or next((v for v in choices if v.pronunciation.accent == region), None)
        entry = choice.entry if choice else None
        multiple = len(variants(entries, region)) > 1
        destination = (
            target.path
            if target
            else output_dir.resolve()
            / audio_filename(word, region, choice.id if choice and (multiple or variant_id) else "")
        )
        if choice and not target and destination.exists():
            from .library import read_recording

            existing = read_recording(destination)
            if (
                existing
                and existing.recording.variant_id
                and existing.recording.variant_id != choice.id
            ):
                destination = output_dir.resolve() / audio_filename(word, region, choice.id)
        combined = False
        ipa = ""
        try:
            selected_entries = (
                (Entry(entry.word, entry.definition, (choice.pronunciation,)),)
                if choice
                else entries
            )
            pronunciation = client.download(
                selected_entries, region, destination, overwrite=overwrite
            )
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
            entry.definition if entry else "",
            combined,
            entry.part_of_speech if entry else "",
            entry.entry_id if entry else "",
            entry.sense_id if entry else "",
            choice.id if choice else "",
            entry.source_url if entry else "",
            choice.pronunciation.url if choice else "",
            entry.lemma if entry else "",
        )
        recordings.append(recording)
        if on_recording:
            on_recording(recording)
    translations = ()
    translation_error = ""
    results = []
    if translation:
        from .library import SavedRecording, read_recording
        from .translations import persist_translation, resolve_translation

        for recording in recordings:
            if check_cancelled:
                check_cancelled()
            saved = read_recording(recording.path) or SavedRecording(recording)
            # The recording's fresh source identity takes precedence over absent legacy metadata.
            if saved.recording.sense_id != recording.sense_id:
                saved = SavedRecording(recording)
            result = resolve_translation(
                client, saved, translation, directory=dictionary_dir, offline=offline_translation
            )
            results.append(result)
            try:
                persist_translation(saved, result)
            except OSError:
                pass  # The caller reports metadata write errors; MP3 remains usable.
        translations = results[0].texts if results else ()
        translation_error = "\n".join(dict.fromkeys(r.error for r in results if r.error))
    return DownloadResult(tuple(recordings), translations, translation_error, tuple(results))

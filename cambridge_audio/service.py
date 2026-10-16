"""Download orchestration shared by the CLI and desktop interface."""

import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock

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

# Serialize media writers without blocking collection reads during network I/O.
_DOWNLOAD_LOCK = Lock()


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
    metadata_path: Path | None = None
    source_entry_id: str = ""
    source_sense_id: str = ""
    audio_sha256: str = ""

    @property
    def reference(self) -> Path:
        if self.metadata_path:
            return self.metadata_path
        sidecar = self.path.with_suffix(".json")
        return sidecar if sidecar.is_file() else self.path

    @property
    def meaning_key(self) -> str:
        return self.source_sense_id or self.sense_id or self.id

    @property
    def audio_id(self) -> str:
        return (
            stable_id("cambridge-audio", self.accent, self.audio_url) if self.audio_url else self.id
        )

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
    sense_id: str | None = None,
    audio_id: str | None = None,
    select_only: bool = False,
    audio_cache_dir: Path | None = None,
) -> DownloadResult:
    from hashlib import sha256
    from uuid import uuid4

    from .library import _METADATA_LOCK, save_metadata, scan_recordings, valid_audio

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
    if select_only and choices:
        raise SelectionRequired(choices, entries, client.language)
    with _METADATA_LOCK:
        saved_records = scan_recordings(output_dir)
    if target:
        matches = [
            v
            for v in choices
            if (
                (target.source_sense_id and v.entry.sense_id == target.source_sense_id)
                or v.id == target.variant_id
                or target.variant_id in v.entry.legacy_ids
                or (
                    not target.source_sense_id
                    and v.entry.definition == target.definition
                    and v.entry.part_of_speech == target.part_of_speech
                )
            )
            and v.pronunciation.url == target.audio_url
        ]
        if variant_id or sense_id:
            # An explicit choice is a user-authorized reassociation of this saved record.
            pass
        elif len(matches) != 1 and target.audio_url:
            selection = SelectionRequired(choices, entries, client.language)
            selection.target = target
            raise selection
        elif len(matches) == 1:
            choices = tuple(matches)
    if variant_id:
        choices = tuple(v for v in choices if v.id == variant_id)
    if sense_id:
        choices = tuple(v for v in choices if v.entry.sense_id == sense_id)
    if audio_id:
        choices = tuple(v for v in choices if v.pronunciation.id == audio_id)
    if (variant_id or sense_id or audio_id) and not choices:
        raise ValueError("The selected meaning/audio is no longer available. Choose again.")
    regions = ("uk", "us") if accent == "both" else (accent,)
    if any(sum(v.pronunciation.accent == region for v in choices) > 1 for region in regions):
        raise SelectionRequired(choices, entries, client.language)
    recordings = []
    for region in regions:
        if check_cancelled:
            check_cancelled()
        choice = next((v for v in choices if v.pronunciation.accent == region), None)
        if choice is None and choices and (variant_id or audio_id):
            continue
        entry = choice.entry if choice else None
        with _DOWNLOAD_LOCK:
            saved_records = scan_recordings(output_dir)
            matches = [
                s.recording
                for s in saved_records
                if choice
                and s.recording.word == word
                and s.recording.accent == region
                and s.recording.audio_url == choice.pronunciation.url
                and (
                    s.recording.source_sense_id == entry.sense_id
                    or s.recording.variant_id == choice.id
                    or s.recording.variant_id in entry.legacy_ids
                    or (
                        not s.recording.source_sense_id
                        and s.recording.definition == entry.definition
                        and s.recording.part_of_speech == entry.part_of_speech
                    )
                )
            ]
            if len(matches) > 1 and target is None:
                raise ValueError("Several saved records match; select the saved record explicitly.")
            existing = target or (matches[0] if matches else None)
            if existing is None and overwrite:
                # Explicit replacement may adopt an MP3-only or unassociated v1 file.
                existing = next(
                    (
                        s.recording
                        for s in saved_records
                        if s.recording.path.name == audio_filename(word, region)
                        and not s.recording.variant_id
                        and not s.recording.audio_url
                    ),
                    None,
                )
            shared = next(
                (
                    s.recording
                    for s in saved_records
                    if choice
                    and s.recording.accent == region
                    and s.recording.audio_url == choice.pronunciation.url
                    and valid_audio(s.recording)
                ),
                None,
            )
            local_id = existing.id if existing else uuid4().hex[:24]
            reuse_target_path = existing and (
                not choice
                or not existing.audio_url
                or existing.audio_url == choice.pronunciation.url
            )
            destination = (
                existing.path
                if reuse_target_path
                else shared.path
                if shared
                else (
                    output_dir.resolve()
                    / audio_filename(
                        word,
                        region,
                        choice.pronunciation.id
                        if choice and len(variants(entries, region)) > 1
                        else "",
                    )
                )
            )
            managed = existing if reuse_target_path else shared
            occupied = any(s.recording.path == destination for s in saved_records)
            # Protect other saved variants and nonconventional, unassociated files.
            if (
                destination.exists()
                and managed is None
                and not (
                    overwrite and not occupied and destination.name == audio_filename(word, region)
                )
            ):
                destination = output_dir.resolve() / audio_filename(
                    word, region, choice.pronunciation.id if choice else local_id
                )
                if destination.exists():
                    raise FileExistsError(f"Unassociated audio file: {destination}")
            created_media = not destination.exists()
            combined, ipa = False, ""
            reusable = managed is not None and valid_audio(managed) and not overwrite
            if not reusable:
                try:
                    selected_entries = (
                        (replace(entry, pronunciations=(choice.pronunciation,)),)
                        if choice
                        else entries
                    )
                    cached_path = (
                        audio_cache_dir / f"{choice.pronunciation.id}.mp3"
                        if audio_cache_dir and choice
                        else None
                    )
                    from .dictionary import is_mp3, save_mp3

                    if (
                        cached_path
                        and cached_path.is_file()
                        and is_mp3(cached_path.read_bytes())
                        and not overwrite
                    ):
                        save_mp3(
                            cached_path.read_bytes(),
                            destination,
                            overwrite=destination.exists() and managed is not None,
                        )
                        ipa = choice.pronunciation.ipa
                    else:
                        pronunciation = client.download(
                            selected_entries,
                            region,
                            destination,
                            overwrite=destination.exists() and (managed is not None or overwrite),
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
                        overwrite=destination.exists() and (managed is not None or overwrite),
                        check_cancelled=check_cancelled,
                    )
                    combined = True
            else:
                combined = managed.combined
            if choice:
                ipa = choice.pronunciation.ipa
            record = Recording(
                word,
                region,
                destination,
                ipa,
                entry.definition if entry else "",
                combined,
                entry.part_of_speech if entry else "",
                existing.entry_id if existing else entry.entry_id if entry else "",
                existing.sense_id
                if existing and existing.sense_id
                else entry.sense_id
                if entry
                else "",
                existing.variant_id if existing else local_id,
                entry.source_url if entry else "",
                choice.pronunciation.url if choice else "",
                entry.lemma if entry else "",
                existing.reference.with_suffix(".json")
                if existing
                else output_dir.resolve()
                / audio_filename(word, region, local_id).replace(".mp3", ".json"),
                entry.entry_id if entry else "",
                entry.sense_id if entry else "",
                sha256(destination.read_bytes()).hexdigest(),
            )
            # Keep all legacy local/export IDs, including the computed v1 ID.
            if existing and not existing.variant_id:
                record = replace(record, variant_id=existing.id)
            with _METADATA_LOCK:
                try:
                    save_metadata(record)
                except OSError:
                    # Roll back only the new file owned by this failed save. Existing
                    # recordings and shared media must survive a metadata write error.
                    if (
                        created_media
                        and sha256(destination.read_bytes()).hexdigest() == record.audio_sha256
                    ):
                        destination.unlink(missing_ok=True)
                    raise
                # A deliberate replacement updates checksums of all references to that file.
                if not reusable:
                    for saved in saved_records:
                        other = saved.recording
                        if other.path == destination and other.reference != record.reference:
                            save_metadata(replace(other, audio_sha256=record.audio_sha256))
        recordings.append(record)
        if on_recording:
            on_recording(record)
    translations, translation_error, results = (), "", []
    if translation:
        from .library import read_recording
        from .translations import persist_translation, resolve_translation

        for record in recordings:
            if check_cancelled:
                check_cancelled()
            saved = read_recording(record.reference)
            result = resolve_translation(
                client, saved, translation, directory=dictionary_dir, offline=offline_translation
            )
            results.append(result)
            persist_translation(saved, result)
        translations = results[0].texts if results else ()
        translation_error = "\n".join(dict.fromkeys(r.error for r in results if r.error))
    return DownloadResult(tuple(recordings), translations, translation_error, tuple(results))


def preview_recording(client, choice, directory: Path, *, collection_dir: Path | None = None):
    """Download to a disposable preview cache; do not add a collection record."""
    from .library import scan_recordings, valid_audio

    if collection_dir:
        shared = next(
            (
                s.recording
                for s in scan_recordings(collection_dir)
                if s.recording.audio_url == choice.pronunciation.url
                and s.recording.accent == choice.pronunciation.accent
                and valid_audio(s.recording)
            ),
            None,
        )
        if shared:
            return shared.path
    destination = directory / f"{choice.pronunciation.id}.mp3"
    from .dictionary import is_mp3

    if not destination.exists() or not is_mp3(destination.read_bytes()):
        client.download(
            (replace(choice.entry, pronunciations=(choice.pronunciation,)),),
            choice.pronunciation.accent,
            destination,
            overwrite=destination.exists(),
        )
    return destination

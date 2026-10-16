"""Background download, translation and dictionary installation tasks."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ..dictionary import (
    CambridgeClient,
    SelectionRequired,
)
from ..errors import diagnostic_details
from ..i18n import translate
from ..library import SavedRecording, read_recording, save_metadata
from ..service import DownloadCancelled, Recording, download_recordings, preview_recording
from ..translations import (
    persist_translation,
    resolve_translation,
)
from ..wikdict import (
    install_dictionary,
)


@dataclass(frozen=True)
class DownloadRequest:
    word: str
    output_dir: Path
    accent: str
    language: str
    translation: bool = False
    combine: bool = False
    overwrite: bool = False
    variant_id: str | None = None
    entries: tuple | None = None
    target: Recording | None = None
    translation_language: str = "russian"
    dictionary_dir: Path | None = None
    select_only: bool = False
    preview_choice: object = None
    preview_dir: Path | None = None
    sense_id: str | None = None


class DownloadWorker(QThread):
    recording = Signal(object)
    completed = Signal(object)
    failed = Signal(str)
    selection = Signal(object)
    previewed = Signal(object)

    def __init__(self, request: DownloadRequest, parent=None):
        super().__init__(parent)
        self.request = request
        self.metadata_error = ""

    def _save_metadata(self, record, translations=()):
        try:
            save_metadata(
                record,
                translations,
                self.request.translation_language if self.request.translation else None,
            )
        except OSError as exc:
            self.metadata_error = diagnostic_details(exc)

    def _recording_saved(self, record):
        self._save_metadata(record)
        self.recording.emit(record)

    def _check_cancelled(self):
        if self.isInterruptionRequested():
            raise DownloadCancelled(translate("Download cancelled.", self.request.language))

    def run(self):
        request = self.request
        try:
            with CambridgeClient(
                language=request.language, check_cancelled=self._check_cancelled
            ) as client:
                if request.preview_choice is not None:
                    path = preview_recording(
                        client,
                        request.preview_choice,
                        request.preview_dir,
                        collection_dir=request.output_dir,
                    )
                    self.previewed.emit(path)
                    return
                result = download_recordings(
                    client,
                    request.word,
                    request.output_dir,
                    request.accent,
                    overwrite=request.overwrite,
                    combine=request.combine,
                    translation=request.translation_language if request.translation else None,
                    variant_id=request.variant_id,
                    sense_id=request.sense_id,
                    entries=request.entries,
                    target=request.target,
                    dictionary_dir=request.dictionary_dir,
                    on_recording=self._recording_saved,
                    check_cancelled=self._check_cancelled,
                    select_only=request.select_only,
                    audio_cache_dir=request.preview_dir,
                )
            for record in result.recordings:
                self._save_metadata(
                    record, () if result.translation_results else result.translations
                )
            for record, translation in zip(
                result.recordings, result.translation_results, strict=False
            ):
                persist_translation(read_recording(record.reference), translation)
            self.completed.emit(result)
        except SelectionRequired as exc:
            self.selection.emit(exc)
        except Exception as exc:
            # Keep the UI usable even when a dependency raises an unexpected error.
            self.failed.emit(diagnostic_details(exc))


class TranslationWorker(QThread):
    completed = Signal(object, object, str)

    def __init__(self, saved: SavedRecording, language: str, parent=None):
        super().__init__(parent)
        self.saved = saved
        self.language = language
        self.target_language = parent.translation_language if parent else "russian"
        self.dictionary_dir = parent.dictionary_dir if parent else None

    def _check_cancelled(self):
        if self.isInterruptionRequested():
            raise DownloadCancelled(translate("Download cancelled.", self.language))

    def run(self):
        try:
            with CambridgeClient(
                language=self.language, check_cancelled=self._check_cancelled
            ) as client:
                result = resolve_translation(
                    client, self.saved, self.target_language, directory=self.dictionary_dir
                )
            self.completed.emit(self.saved, result, "")
        except Exception as exc:
            self.completed.emit(self.saved, (), diagnostic_details(exc))


class DictionaryWorker(QThread):
    completed = Signal(str)
    failed = Signal(str)
    progress = Signal(int, int)

    def __init__(self, directory, parent=None):
        super().__init__(parent)
        self.directory = directory

    def run(self):
        try:

            def cancelled():
                if self.isInterruptionRequested():
                    raise DownloadCancelled("Dictionary installation cancelled.")

            path = install_dictionary(
                self.directory, progress=self.progress.emit, check_cancelled=cancelled
            )
            self.completed.emit(str(path))
        except Exception as exc:
            self.failed.emit(diagnostic_details(exc))

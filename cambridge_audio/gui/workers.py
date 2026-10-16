"""Background download, translation and dictionary installation tasks."""

import errno
from dataclasses import dataclass
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal

from ..dictionary import (
    AudioNotFoundError,
    CambridgeClient,
    SelectionRequired,
)
from ..i18n import translate
from ..library import SavedRecording, read_recording, save_metadata
from ..service import DownloadCancelled, Recording, download_recordings
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


class DownloadWorker(QThread):
    recording = Signal(object)
    completed = Signal(object)
    failed = Signal(str)
    selection = Signal(object)

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
            self.metadata_error = str(exc)

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
                result = download_recordings(
                    client,
                    request.word,
                    request.output_dir,
                    request.accent,
                    overwrite=request.overwrite,
                    combine=request.combine,
                    translation=request.translation_language if request.translation else None,
                    variant_id=request.variant_id,
                    entries=request.entries,
                    target=request.target,
                    dictionary_dir=request.dictionary_dir,
                    on_recording=self._recording_saved,
                    check_cancelled=self._check_cancelled,
                )
            for record in result.recordings:
                self._save_metadata(
                    record, () if result.translation_results else result.translations
                )
            for record, translation in zip(
                result.recordings, result.translation_results, strict=False
            ):
                persist_translation(read_recording(record.path), translation)
            self.completed.emit(result)
        except SelectionRequired as exc:
            self.selection.emit(exc)
        except Exception as exc:
            # Keep the UI usable even when a dependency raises an unexpected error.
            self.failed.emit(self._error_message(exc))

    def _error_message(self, error: Exception) -> str:
        cause = error.__cause__ or error
        values = {}
        if isinstance(cause, requests.Timeout):
            message = "Cambridge took too long to respond. Please try again."
        elif isinstance(cause, requests.HTTPError) and cause.response is not None:
            message = "Cambridge could not provide the recording (HTTP {status}). Try again later."
            values["status"] = cause.response.status_code
        elif isinstance(cause, requests.RequestException):
            message = (
                "Could not connect to Cambridge. Check your internet connection and try again."
            )
        elif isinstance(error, AudioNotFoundError):
            message = "No recording was found for '{word}' with this pronunciation."
            values["word"] = self.request.word
        elif isinstance(error, FileExistsError):
            message = (
                "A recording appeared in this folder. "
                "Download again to choose whether to replace it."
            )
        elif isinstance(error, PermissionError):
            message = (
                "Cannot save in this folder. Choose another folder or close apps using the file."
            )
        elif isinstance(error, OSError) and error.errno == errno.ENOSPC:
            message = "Not enough free space in the selected folder."
        else:
            return str(error) or type(error).__name__
        return translate(message, self.request.language, **values)


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
            self.completed.emit(self.saved, (), str(exc) or type(exc).__name__)


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
            self.failed.emit(str(exc))

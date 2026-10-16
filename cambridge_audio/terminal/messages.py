"""Worker results delivered to the terminal application."""

from textual.message import Message

from ..library import SavedRecording
from ..translations import (
    TranslationResult,
)


class VariantSelection(Message):
    def __init__(self, word, selection):
        super().__init__()
        self.word, self.selection = word, selection


class DictionaryFinished(Message):
    def __init__(self, error=""):
        super().__init__()
        self.error = error


class DownloadUpdate(Message):
    def __init__(self, saved: SavedRecording):
        super().__init__()
        self.saved = saved


class DownloadFinished(Message):
    def __init__(self, error: str = "", warning: str = "", translation_error: str = ""):
        super().__init__()
        self.error = error
        self.warning = warning
        self.translation_error = translation_error


class TranslationFinished(Message):
    def __init__(
        self,
        saved: SavedRecording,
        translations: tuple[str, ...] = (),
        error: str = "",
        language: str = "russian",
        result: TranslationResult | None = None,
    ):
        super().__init__()
        self.saved = saved
        self.language = language
        self.translations = translations
        self.result = result
        self.error = error


class PlaybackFinished(Message):
    def __init__(self, error: str = ""):
        super().__init__()
        self.error = error

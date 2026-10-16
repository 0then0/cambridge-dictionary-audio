"""User-facing error summaries; original diagnostics stay separate from UI text."""

import errno
import re

from .i18n import translate


def diagnostic_details(error: Exception | str) -> str:
    if not isinstance(error, BaseException):
        return str(error)
    parts, seen = [], set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        parts.append(f"{type(error).__name__}: {error}")
        error = error.__cause__ or error.__context__
    return "\n\n".join(parts)


def friendly_error(error: Exception | str, language: str = "en", *, context="operation") -> str:
    """Classify live exceptions and serialized/cached errors without exposing raw text."""
    details = diagnostic_details(error).casefold()
    if any(token in details for token in ("timeout", "timed out", "не ответил вовремя")):
        message = "The service took too long to respond. Please try again."
    elif re.search(r"\bhttp(?:error)?[\s:()]*429\b", details) or any(
        token in details for token in ("rate limit", "слишком много запросов")
    ):
        message = "The service is receiving too many requests. Please try again later."
    elif re.search(r"\bhttp(?:error)?[\s:()]*403\b", details) or any(
        token in details for token in ("captcha", "blocked", "блокир")
    ):
        message = "The dictionary temporarily refused access. Please try again later."
    elif any(
        token in details
        for token in (
            "connection",
            "httpsconnectionpool",
            "ssl",
            "requestexception",
            "ошибка запроса",
        )
    ):
        message = "Could not connect to the service. Check your internet connection and try again."
    elif (isinstance(error, OSError) and error.errno == errno.ENOSPC) or any(
        token in details for token in ("disk full", "no space", "free space", "недостаточно места")
    ):
        message = "Not enough free space. Free some space and try again."
    elif any(token in details for token in ("permission", "denied", "отказано", "нет доступа")):
        message = "Cannot access the file or folder. Check permissions or choose another folder."
    elif re.search(r"\bhttp(?:error)?[\s:()]*404\b", details) or any(
        token in details for token in ("not found", "filenotfound", "no recording", "не найден")
    ):
        message = {
            "translation": "No translation found.",
            "playback": "The audio file is unavailable. Save the recording again.",
        }.get(context, "The requested item could not be found. Check your selection and try again.")
    elif re.search(r"\bhttp(?:error)?[\s:()]*5\d\d\b|\b5\d\d server error", details):
        message = "The service is temporarily unavailable. Please try again later."
    elif any(
        token in details
        for token in ("checksum", "sha-256", "corrupt", "damaged", "invalid mp3", "поврежд")
    ):
        message = "The file is damaged or incomplete. Download it again."
    elif any(
        token in details
        for token in ("fileexists", "already exists", "unrelated", "unassociated", "уже существует")
    ):
        message = "The destination is already in use. Choose another file or folder."
    elif any(token in details for token in ("cancelled", "отменён", "отменен")):
        message = "Download cancelled."
    elif any(token in details for token in ("enter an english word", "введите английское слово")):
        message = "Enter an English word or phrase without URLs or path separators."
    elif "choose a translation" in details:
        message = "Choose a translation sense before exporting."
    elif "no recordings selected" in details:
        message = "No recordings selected for export."
    elif "audio output is unavailable" in details or "аудиовыход недоступен" in details:
        message = "Audio output is unavailable. Check your system sound settings."
    elif "moved or deleted" in details or "перемещена или удалена" in details:
        message = "The recording was moved or deleted. Download it again."
    elif context == "translation" and any(
        token in details for token in ("not installed", "не установлен")
    ):
        message = "The offline dictionary is not installed. Install WikDict or try again online."
    else:
        message = {
            "translation": "Could not load the translation. Please try again.",
            "metadata": "Audio is saved, but its details could not be saved. Please try again.",
            "export": (
                "Could not export the collection. Check the selected recordings and destination."
            ),
            "library": "Could not read the collection. Check the folder and try again.",
            "playback": "Could not play the recording. Check your audio settings and try again.",
            "settings": "Could not save settings. Check the settings folder permissions.",
        }.get(context, "Could not complete the operation. Please try again.")
    summary = translate(message, language)
    if context == "metadata" and not message.startswith("Audio is saved"):
        summary = (
            translate(
                "Audio is saved, but its details could not be saved. Please try again.", language
            )
            + " "
            + summary
        )
    return summary

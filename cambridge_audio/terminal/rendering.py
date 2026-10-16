"""Readable terminal translations and recording paths."""

from dataclasses import replace
from pathlib import Path

from rich.text import Text

from ..errors import friendly_error
from ..i18n import translate
from ..translations import (
    TranslationResult,
)


def translation_context(option, language: str) -> str:
    return " · ".join(filter(None, (translate(option.part_of_speech, language), option.definition)))


def render_translation(result: TranslationResult, language: str) -> Text:
    """Present source senses without exposing storage IDs or empty gloss placeholders."""
    t = lambda message: translate(message, language)  # noqa: E731
    if result.error:
        result = replace(
            result, error=friendly_error(result.error, language, context="translation")
        )
    if not result.options:
        return Text(result.format(language))
    text = Text()
    text.append(t("Translation"), style="bold")
    text.append(" · " + t(result.source), style="dim")
    text.append("\n", style="none")
    selected = next((o for o in result.options if o.id == result.selected_id), None)
    options = (selected,) if selected else result.options
    ambiguous = len(options) > 1
    for index, option in enumerate(options, start=1):
        if index > 1:
            text.append("\n", style="none")
        if ambiguous:
            text.append(f"{index}. ", style="bold")
        text.append("; ".join(option.texts), style="none")
        if option.part_of_speech:
            text.append(" · " + t(option.part_of_speech), style="dim")
        if option.definition:
            text.append("\n" + ("   " if ambiguous else "") + option.definition, style="dim")
    if ambiguous:
        text.append("\n\n" + t("Ctrl+T: choose a meaning or edit the translation."), style="dim")
    if not all(option.matched for option in options):
        text.append(
            ("\n" if ambiguous else "\n\n") + t("Sense match with Cambridge is unverified."),
            style="dim",
        )
    if result.error:
        text.append(
            "\n\n" + "; ".join(t(part) for part in result.error.split("; ")), style="italic"
        )
    return text


def display_path(path: Path) -> str:
    for base, prefix in ((Path.cwd(), "."), (Path.home(), "~")):
        try:
            return str(Path(prefix) / path.relative_to(base))
        except ValueError:
            pass
    return str(path)

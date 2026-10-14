"""Readable terminal output with a plain fallback for pipes and older terminals."""

import os
import sys
from contextlib import nullcontext

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .i18n import translate


def is_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get("TERM") != "dumb"


class Output:
    def __init__(self, language: str, *, plain: bool = False):
        self.language = language
        self.pretty = is_terminal() and not plain
        self.console = Console(highlight=False)

    def message(self, message: str, *, style: str = "") -> None:
        if self.pretty:
            self.console.print(Text(message, style=style))
        else:
            print(message)

    def working(self):
        if self.pretty:
            return self.console.status(translate("Downloading...", self.language), spinner="dots")
        return nullcontext()

    def details(self, word: str, definition: str, translations: tuple[str, ...]) -> None:
        content = "\n\n".join(value for value in (definition, "\n".join(translations)) if value)
        if self.pretty and content:
            self.console.print(
                Panel(Text(content), title=Text(word), border_style="cyan", padding=1)
            )
        elif content:
            print("\n".join(value for value in (definition, "\n".join(translations)) if value))

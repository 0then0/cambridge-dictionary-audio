"""Terminal settings, selection, help and confirmation dialogs."""

from dataclasses import replace
from importlib.metadata import version
from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Link, Select, Static

from ..i18n import translate
from .settings import Options


class Dialog(ModalScreen):
    BINDINGS = [("escape", "close", "Close")]

    def action_close(self) -> None:
        self.dismiss(None)


class ErrorDetails(Dialog):
    def __init__(self, language, details):
        super().__init__()
        self.language, self.details = language, details

    def compose(self):
        with VerticalScroll(classes="dialog"):
            yield Label(translate("Technical details", self.language), classes="dialog-title")
            yield Static(Text(self.details), id="diagnostic-text")
            yield Button(translate("Close", self.language), id="close-errors")

    @on(Button.Pressed, "#close-errors")
    def close_details(self):
        self.dismiss(None)


class Settings(Dialog):
    def __init__(self, options: Options, theme: str):
        super().__init__()
        self.options = options
        self.current_theme = theme

    def compose(self) -> ComposeResult:
        t = lambda message: translate(message, self.options.language)  # noqa: E731
        with VerticalScroll(classes="dialog"):
            yield Label(t("Settings"), classes="dialog-title")
            yield Label(t("Language"))
            yield Select(
                [("English", "en"), ("Русский", "ru")],
                value=self.options.language,
                allow_blank=False,
                id="language",
            )
            yield Label(t("Appearance"))
            yield Select(
                [(t("Dark"), "cambridge-dark"), (t("Light"), "cambridge-light")],
                value=self.current_theme,
                allow_blank=False,
                id="theme",
            )
            yield Label(t("Pronunciation"))
            yield Select(
                [(t("American (US)"), "us"), (t("British (UK)"), "uk"), (t("Both"), "both")],
                value=self.options.accent,
                allow_blank=False,
                id="accent",
            )
            yield Label(t("Save to"))
            yield Input(str(self.options.directory), id="directory")
            yield Checkbox(
                t("Show Russian translation"), bool(self.options.translation), id="translation"
            )
            yield Checkbox(t("Autoplay"), self.options.play, id="autoplay")
            yield Checkbox(
                t("Combine words if the phrase has no recording"),
                self.options.combine,
                id="combine",
            )
            yield Static(
                t("Settings are saved for future launches. CLI flags override saved values."),
                classes="muted",
            )
            yield Static("", id="settings-error")
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("Apply"), variant="primary", id="apply")
                yield Button(t("Cancel"), id="dismiss")

    @on(Button.Pressed)
    def apply_settings(self, event: Button.Pressed) -> None:
        if event.button.id != "apply":
            self.dismiss(None)
            return
        directory = self.query_one("#directory", Input).value.strip()
        if not directory:
            self.query_one("#settings-error", Static).update(
                translate("Choose a download folder", self.options.language)
            )
            return
        options = replace(
            self.options,
            directory=Path(directory).expanduser().resolve(),
            language=str(self.query_one("#language", Select).value),
            accent=str(self.query_one("#accent", Select).value),
            translation="russian" if self.query_one("#translation", Checkbox).value else None,
            play=self.query_one("#autoplay", Checkbox).value,
            combine=self.query_one("#combine", Checkbox).value,
        )
        self.dismiss((options, str(self.query_one("#theme", Select).value)))


class ConfirmReplace(Dialog):
    def __init__(self, language: str, word: str):
        super().__init__()
        self.language = language
        self.word = word

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(translate("Replace recordings?", self.language), classes="dialog-title")
            yield Static(
                Text(translate("Replace saved audio for '{word}'?", self.language, word=self.word))
            )
            with Horizontal(classes="dialog-buttons"):
                yield Button(translate("Keep existing", self.language), id="keep")
                yield Button(translate("Replace", self.language), variant="warning", id="replace")

    @on(Button.Pressed)
    def answer(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "replace")


class ChooseOption(Dialog):
    def __init__(self, language, title, choices, *, text=None, note=""):
        super().__init__()
        self.language, self.title, self.choices = language, title, choices
        self.text, self.note = text, note

    def compose(self):
        t = lambda message: translate(message, self.language)  # noqa: E731
        with VerticalScroll(classes="dialog"):
            yield Label(t(self.title), classes="dialog-title")
            if self.note:
                yield Static(Text(self.note))
            if self.choices:
                yield Select(
                    [(Text(label), value) for label, value in self.choices],
                    value=self.choices[0][1],
                    allow_blank=False,
                    id="choice",
                )
            if self.text is not None:
                yield Input(self.text, id="value")
            with Horizontal(classes="dialog-buttons"):
                yield Button(t("Apply"), variant="primary", id="accept")
                yield Button(t("Cancel"), id="cancel")

    @on(Button.Pressed)
    def answer(self, event):
        if event.button.id != "accept":
            self.dismiss(None)
        else:
            value = self.query_one("#choice", Select).value if self.choices else ""
            text = self.query_one("#value", Input).value if self.text is not None else None
            self.dismiss((value, text))


class About(Dialog):
    def __init__(self, language: str):
        super().__init__()
        self.language = language

    def compose(self) -> ComposeResult:
        t = lambda message: translate(message, self.language)  # noqa: E731
        with VerticalScroll(classes="dialog"):
            yield Label(t("About"), classes="dialog-title")
            yield Static(Text("Cambridge Dictionary Audio", style="bold"))
            yield Static(
                translate(
                    "Version {version}",
                    self.language,
                    version=version("cambridge-dictionary-audio"),
                ),
                id="about-version",
            )
            yield Static(t("Download and listen to English pronunciation."), classes="help-note")
            yield Link(
                "github.com/0then0/cambridge-dictionary-audio",
                url="https://github.com/0then0/cambridge-dictionary-audio",
                tooltip=t("Source code on GitHub"),
                id="about-repository",
            )
            yield Static(
                t("Application code: Apache-2.0; inherited code: MIT."), classes="help-note"
            )
            yield Static(
                t("Dictionary content and recordings retain their own licenses."),
                classes="help-note",
            )
            yield Button(t("Close"), id="close-about")

    @on(Button.Pressed, "#close-about")
    def close_about(self) -> None:
        self.dismiss(None)


class Help(Dialog):
    def __init__(self, language: str):
        super().__init__()
        self.language = language

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="dialog"):
            yield Label(translate("Keyboard shortcuts", self.language), classes="dialog-title")
            yield Static(
                translate(
                    "Enter in search: download or open saved audio\n"
                    "Enter in library: play selected recording\n"
                    "Tab / Shift+Tab: move between controls\n"
                    "Up / Down: navigate saved recordings\n"
                    "Ctrl+L: focus search\nCtrl+P: play / stop selected recording\n"
                    "Ctrl+R: refresh library\nCtrl+S: settings\n"
                    "Ctrl+O: choose meaning\nCtrl+T: edit / choose / reset translation\n"
                    "Ctrl+D: install WikDict\nCtrl+E: export to Anki\n"
                    "Ctrl+C: cancel download / stop playback, or quit when idle\nCtrl+Q: quit\n"
                    "F1: this help\nEsc: close a dialog",
                    self.language,
                )
            )
            yield Static(
                translate(
                    "Existing audio opens offline. Download again asks before replacing it.\n"
                    "Phrase synthesis needs FFmpeg; Linux playback needs ffplay.",
                    self.language,
                ),
                classes="help-note",
            )
            yield Static(translate("F2: About", self.language), classes="help-note")
            yield Static(
                translate(
                    "Any keyboard layout: F3 search; F4 play / stop; F5 refresh; "
                    "F6 settings; F7 export; F8 translation; F9 WikDict; "
                    "F10 meaning; F11 cancel; F12 quit. "
                    "Ctrl shortcuts also accept Russian and Ukrainian key positions.",
                    self.language,
                ),
                classes="help-note",
            )
            with Horizontal(classes="dialog-buttons"):
                yield Button(translate("About", self.language), id="help-about")
                yield Button(translate("Close", self.language), id="close-help")

    @on(Button.Pressed, "#close-help")
    def close_help(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#help-about")
    def open_about(self) -> None:
        self.app.action_about()

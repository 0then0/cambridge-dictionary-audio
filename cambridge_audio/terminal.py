"""Keyboard-friendly terminal workspace, independent of the desktop GUI."""

from dataclasses import dataclass, replace
from importlib.metadata import version
from pathlib import Path
from threading import Event

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widgets import Button, Checkbox, DataTable, Footer, Input, Label, Link, Select, Static
from textual.worker import Worker, WorkerState

from .anki import export_anki
from .audio import play_audio
from .dictionary import (
    CambridgeClient,
    CambridgeError,
    SelectionRequired,
    audio_filename,
    normalize_word,
)
from .i18n import translate
from .library import SavedRecording, read_recording, save_metadata, scan_recordings
from .service import DownloadCancelled, download_recordings
from .translations import (
    TranslationResult,
    cached_translation,
    edit_translation,
    persist_translation,
    resolve_translation,
    select_translation,
)
from .wikdict import PACKAGE, install_dictionary


def translation_context(option, language: str) -> str:
    return " · ".join(filter(None, (translate(option.part_of_speech, language), option.definition)))


def render_translation(result: TranslationResult, language: str) -> Text:
    """Present source senses without exposing storage IDs or empty gloss placeholders."""
    t = lambda message: translate(message, language)  # noqa: E731
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


@dataclass(frozen=True)
class Options:
    directory: Path
    language: str = "en"
    accent: str = "us"
    play: bool = True
    combine: bool = True
    translation: str | None = None
    timeout: float = 15.0
    overwrite: bool = False
    dictionary_dir: Path | None = None
    offline: bool = False


class Dialog(ModalScreen):
    BINDINGS = [("escape", "close", "Close")]

    def action_close(self) -> None:
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
                t("Settings apply to this session. Use CLI flags for future launches."),
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


class VariantSelection(Message):
    def __init__(self, word, selection):
        super().__init__()
        self.word, self.selection = word, selection


class DictionaryFinished(Message):
    def __init__(self, error=""):
        super().__init__()
        self.error = error


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
                    "Ctrl+O: choose pronunciation\nCtrl+T: edit / choose / reset translation\n"
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
                    "F10 pronunciation; F11 cancel; F12 quit. "
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


class CambridgeApp(App[None]):
    TITLE = "Cambridge Dictionary Audio"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding("ctrl+l", "search", "Search", priority=True),
        Binding("ctrl+p", "play", "Play", priority=True),
        Binding("ctrl+r", "refresh", "Refresh", priority=True),
        Binding("ctrl+s", "settings", "Settings", priority=True),
        Binding("ctrl+e", "export", "Export to Anki", priority=True),
        Binding("ctrl+t", "edit_translation", "Edit translation", priority=True),
        Binding("ctrl+d", "dictionary", "Install WikDict", priority=True),
        Binding("ctrl+o", "variants", "Choose pronunciation", priority=True),
        Binding("f1", "help", "Help", priority=True),
        Binding("f2", "about", "About", priority=True),
        Binding("ctrl+c", "cancel", "Cancel", priority=True, show=False),
        Binding("ctrl+q", "quit", "Quit", priority=True),
    ]
    # Terminals report logical characters, not physical scan codes. Accept the
    # Cyrillic keys at the same positions and offer F-keys for every layout.
    BINDINGS += [
        Binding(keys, action, label, priority=True, show=False)
        for keys, action, label in (
            ("ctrl+д,f3", "search", "Search"),
            ("ctrl+з,f4", "play", "Play"),
            ("ctrl+к,f5", "refresh", "Refresh"),
            ("ctrl+ы,ctrl+і,f6", "settings", "Settings"),
            ("ctrl+у,f7", "export", "Export to Anki"),
            ("ctrl+е,f8", "edit_translation", "Edit translation"),
            ("ctrl+в,f9", "dictionary", "Install WikDict"),
            ("ctrl+щ,f10", "variants", "Choose pronunciation"),
            ("ctrl+с,f11", "cancel", "Cancel"),
            ("ctrl+й,f12", "quit", "Quit"),
        )
    ]
    CSS = """
    Screen { background: $background; }
    #brand { height: 3; padding: 1 2 0 2; text-style: bold; color: $text; }
    #context { height: 2; padding: 0 2; color: $text-muted;
               text-overflow: ellipsis; text-wrap: nowrap; }
    #search-bar { height: 3; margin: 0 2 1 2; }
    #query { width: 1fr; }
    #download { margin-left: 1; min-width: 14; }
    #workspace { height: 1fr; margin: 0 2; }
    #library-pane { width: 38%; min-width: 24; border: round $panel; }
    #detail-pane { width: 1fr; margin-left: 1; border: round $panel; }
    #library-pane, #detail-pane { border-title-color: $text-muted; }
    Input { border: round $panel; }
    Input:focus { border: round $primary; }
    Button { border: round $panel; }
    Button.-primary { border: round $primary; }
    Button:focus { border: round $accent; }
    #recordings { height: 1fr; background: $background; }
    DataTable > .datatable--header { background: $panel; color: $text-muted; }
    DataTable > .datatable--cursor { background: $primary; color: #ffffff; }
    #empty { padding: 1 2; color: $text-muted; height: auto; }
    #detail-scroll { height: 1fr; padding: 1 2; }
    #word { height: auto; color: $text; text-style: bold; margin-bottom: 1; }
    #pronunciation { height: auto; color: $accent; margin-bottom: 1; }
    #definition, #translation { height: auto; margin-bottom: 1; }
    #file { height: auto; color: $text-muted; }
    #detail-actions { height: 3; margin: 0 1 1 1; }
    #play { min-width: 10; margin-right: 1; }
    #again { min-width: 16; }
    #show-translation { height: 1; margin: 0 2 1 2; }
    #status { height: auto; max-height: 4; min-height: 2; margin: 0 2; padding: 1 0 0 0; }
    #status.error { color: $error; }
    #status.warning { color: $warning; }
    Footer { background: $panel; }
    .narrow #workspace { layout: vertical; }
    .narrow #library-pane { width: 100%; height: 35%; min-width: 0; }
    .narrow #detail-pane { width: 100%; height: 1fr; margin: 1 0 0 0; }
    .narrow #detail-scroll { padding: 0 1; }
    .short #brand { height: 2; padding-top: 0; }
    .short #context { height: 1; }
    .short #search-bar { margin-bottom: 0; }
    .short #status { min-height: 1; padding-top: 0; }
    ModalScreen { align: center middle; background: $background 70%; }
    .dialog { width: 64; max-width: 95%; height: auto; max-height: 90%;
              padding: 1 2; border: round $primary; background: $surface; }
    .dialog Label { height: auto; margin-top: 1; }
    .dialog .dialog-title { margin-top: 0; text-style: bold; color: $accent; }
    .dialog Input, .dialog Select { width: 100%; }
    .dialog Checkbox { height: auto; width: 100%; margin-top: 1; }
    .muted { color: $text-muted; height: auto; margin-top: 1; }
    .help-note { color: $text-muted; height: auto; margin: 1 0; }
    .dialog-buttons { height: 3; margin-top: 1; }
    .dialog-buttons Button { margin-right: 1; }
    #settings-error { height: auto; color: $error; }
    """

    def __init__(self, options: Options):
        super().__init__()
        self.register_theme(
            Theme(
                name="cambridge-dark",
                primary="#af3448",
                accent="#e38494",
                foreground="#eff2f6",
                background="#171b22",
                surface="#202630",
                panel="#2d3542",
                error="#f09aaa",
                dark=True,
            )
        )
        self.register_theme(
            Theme(
                name="cambridge-light",
                primary="#af3448",
                accent="#af3448",
                foreground="#1d2733",
                background="#f5f6f8",
                surface="#ffffff",
                panel="#e8ecf0",
                error="#a82b3e",
                dark=False,
            )
        )
        self.theme = "cambridge-dark"
        self.options = replace(
            options,
            directory=options.directory.expanduser().resolve(),
            translation="russian" if options.translation else None,
        )
        self.saved: list[SavedRecording] = []
        self.selected: SavedRecording | None = None
        self.busy = False
        self.playing = False
        self.cancel_download = Event()
        self.stop_playback = Event()
        self.quit_pending = False
        self.warning = ""
        self.dictionary_busy = False
        self.translation_pending: SavedRecording | None = None
        self.translation_errors: dict[tuple[Path, str], str] = {}

    def t(self, message: str, **values) -> str:
        return translate(message, self.options.language, **values)

    def compose(self) -> ComposeResult:
        yield Static(
            f"Cambridge Dictionary Audio  {version('cambridge-dictionary-audio')}", id="brand"
        )
        yield Static("", id="context")
        with Horizontal(id="search-bar"):
            yield Input(placeholder=self.t("For example: hello or good morning"), id="query")
            yield Button(self.t("Download"), variant="primary", id="download")
        with Horizontal(id="workspace"):
            with Vertical(id="library-pane"):
                yield DataTable(id="recordings", cursor_type="row", show_row_labels=False)
                yield Static("", id="empty")
            with Vertical(id="detail-pane"):
                with VerticalScroll(id="detail-scroll"):
                    yield Static("", id="word")
                    yield Static("", id="pronunciation")
                    yield Static("", id="definition")
                    yield Static("", id="translation")
                    yield Static("", id="file")
                yield Checkbox(
                    self.t("Show Russian translation"),
                    bool(self.options.translation),
                    id="show-translation",
                    compact=True,
                )
                with Horizontal(id="detail-actions"):
                    yield Button(self.t("Play"), id="play", disabled=True)
                    yield Button(self.t("Download again"), id="again", disabled=True)
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.localize()
        self.action_refresh()
        self.action_search()

    def on_resize(self, event) -> None:
        root = self.screen_stack[0]
        root.set_class(event.size.width < 76, "narrow")
        root.set_class(event.size.height < 28, "short")

    def _set_button_label(self, key: str, message: str) -> None:
        button = self.screen_stack[0].query_one(f"#{key}", Button)
        text = self.t(message)
        if button.label.plain != text:
            button.label = text
            # Textual's Button.label repaints without recalculating its auto width.
            button.refresh(layout=True)

    def localize(self) -> None:
        for key, label in (("download", "Download"), ("play", "Play"), ("again", "Download again")):
            self._set_button_label(key, label)
        self.screen_stack[0].query_one("#query", Input).placeholder = self.t(
            "For example: hello or good morning"
        )
        self.screen_stack[0].query_one("#show-translation", Checkbox).label = self.t(
            "Show Russian translation"
        )
        self.screen_stack[0].query_one("#library-pane").border_title = self.t("Saved recordings")
        self.screen_stack[0].query_one("#detail-pane").border_title = self.t("Recording")
        # Update descriptions in place: App.bind appends non-priority duplicates.
        labels = {binding.action: binding.description for binding in self.BINDINGS}
        for key, bindings in self._bindings.key_to_bindings.items():
            self._bindings.key_to_bindings[key] = [
                replace(binding, description=self.t(labels[binding.action]))
                if binding.action in labels
                else binding
                for binding in bindings
            ]
        self.refresh_bindings()
        self.screen_stack[0].query_one("#context", Static).update(
            Text(f"{self.options.accent.upper()}  ·  {display_path(self.options.directory)}")
        )
        table = self.screen_stack[0].query_one("#recordings", DataTable)
        table.clear(columns=True)
        table.add_columns(self.t("Word or phrase"), self.t("Accent"), self.t("Dictionary entry"))
        self.render_library()
        self.show_recording(self.selected)

    def status(self, message: str, *, error: bool = False, warning: bool = False) -> None:
        widget = self.screen_stack[0].query_one("#status", Static)
        widget.set_class(error, "error")
        widget.set_class(warning, "warning")
        widget.update(Text(message))

    def action_search(self) -> None:
        self.screen_stack[0].query_one("#query", Input).focus()

    def action_refresh(self) -> None:
        try:
            self.saved = scan_recordings(self.options.directory)
        except OSError as exc:
            self.status(self.t("Could not read saved recordings: {error}", error=exc), error=True)
            return
        self.render_library()
        if self.selected:
            current = next(
                (s for s in self.saved if s.recording.path == self.selected.recording.path), None
            )
            self.show_recording(current)
        if not self.busy:
            self.status(self.t("Ready · {count} saved recordings", count=len(self.saved)))

    def render_library(self) -> None:
        query = self.screen_stack[0].query_one("#query", Input).value.strip().casefold()
        table = self.screen_stack[0].query_one("#recordings", DataTable)
        selected_path = str(self.selected.recording.path) if self.selected else None
        table.clear()
        matches = [s for s in self.saved if query in s.recording.word.casefold()]
        preferred = "us" if self.options.accent == "both" else self.options.accent
        selected_row = next(
            (i for i, s in enumerate(matches) if s.recording.accent == preferred), 0
        )
        for index, saved in enumerate(matches):
            record = saved.recording
            table.add_row(
                Text(record.word),
                record.accent.upper(),
                Text(f"{record.part_of_speech} · {record.definition[:50]} · /{record.ipa}/"),
                key=str(record.path),
            )
            if str(record.path) == selected_path:
                selected_row = index
        if matches:
            table.move_cursor(row=selected_row)
        self.screen_stack[0].query_one("#empty", Static).display = not matches
        self.screen_stack[0].query_one("#empty", Static).update(
            self.t("No matching recordings" if self.saved else "No saved recordings")
        )

    @on(Input.Changed, "#query")
    def filter_library(self) -> None:
        self.render_library()

    @on(DataTable.RowHighlighted)
    def highlight(self, event: DataTable.RowHighlighted) -> None:
        if not self.screen_stack or not self.screen_stack[0].query("#word"):
            return
        saved = next((s for s in self.saved if str(s.recording.path) == event.row_key.value), None)
        if saved:
            self.show_recording(saved)

    @on(DataTable.RowSelected)
    def select_recording(self, event: DataTable.RowSelected) -> None:
        if not self.screen_stack or not self.screen_stack[0].query("#word"):
            return
        saved = next((s for s in self.saved if str(s.recording.path) == event.row_key.value), None)
        if saved:
            self.show_recording(saved)
            self.action_play()

    def show_recording(self, saved: SavedRecording | None) -> None:
        self.selected = saved
        values = {
            "word": self.t("No recording yet"),
            "pronunciation": "",
            "definition": self.t("Download a word or phrase to listen to it here."),
            "translation": "",
            "file": "",
        }
        if saved:
            record = saved.recording
            values = {
                "word": record.word,
                "pronunciation": f"{record.accent.upper()}  "
                + (
                    self.t("Combined from individual words")
                    if record.combined
                    else f"/{record.ipa}/"
                    if record.ipa
                    else ""
                ),
                "definition": (f"{record.part_of_speech} · " if record.part_of_speech else "")
                + record.definition
                or self.t("Details are unavailable for this saved recording."),
                "translation": "\n".join(saved.translations),
                "file": display_path(record.path),
            }
        for key, value in values.items():
            self.screen_stack[0].query_one(f"#{key}", Static).update(Text(value))
        self.update_translation()
        self.update_controls()

    @on(Checkbox.Changed, "#show-translation")
    def toggle_translation(self) -> None:
        if not self.screen_stack or not self.screen_stack[0].query("#show-translation"):
            return
        enabled = self.screen_stack[0].query_one("#show-translation", Checkbox).value
        self.options = replace(self.options, translation="russian" if enabled else None)
        if self.selected and enabled:
            self.translation_errors.pop(
                (self.selected.recording.path, self.options.translation or "russian"), None
            )
        self.update_translation()

    def update_translation(self) -> None:
        widget = self.screen_stack[0].query_one("#translation", Static)
        widget.display = (
            self.selected is not None
            and self.screen_stack[0].query_one("#show-translation", Checkbox).value
        )
        if not widget.display:
            return
        saved = self.selected
        if not saved.recording.path.is_file():
            widget.update(Text(self.t("The recording was moved or deleted. Download it again.")))
            return
        language = self.options.translation or "russian"
        key = (saved.recording.path, language)
        saved = read_recording(saved.recording.path) or saved
        result = cached_translation(saved, language)
        if result:
            widget.update(render_translation(result, self.options.language))
        elif key in self.translation_errors:
            widget.update(Text(self.translation_errors[key]))
        else:
            widget.update(Text(self.t("Loading translation...")))
            if not self.busy and self.translation_pending is None and not self.quit_pending:
                self.translation_pending = saved
                self.fetch_translation(saved, self.options)

    @work(thread=True, group="translation", exit_on_error=False)
    def fetch_translation(self, saved: SavedRecording, options: Options) -> None:
        try:
            with CambridgeClient(options.timeout, language=options.language) as client:
                result = resolve_translation(
                    client,
                    saved,
                    options.translation or "russian",
                    directory=options.dictionary_dir,
                    offline=options.offline,
                )
            self.post_message(
                TranslationFinished(
                    saved, result.texts, language=options.translation or "russian", result=result
                )
            )
        except (CambridgeError, OSError, ValueError) as exc:
            self.post_message(
                TranslationFinished(
                    saved, error=str(exc), language=options.translation or "russian"
                )
            )

    def on_translation_finished(self, message: TranslationFinished) -> None:
        self.translation_pending = None
        record = message.saved.recording
        if message.error or not message.result or not message.result.options:
            self.translation_errors[(record.path, message.language)] = (
                self.t(
                    "Translation: {error}",
                    error=message.error or (message.result.error if message.result else ""),
                )
                if message.error or (message.result and message.result.error)
                else self.t("No translation found. Toggle off and on to retry.")
            )
        else:
            # Update both accents without changing the selected row or touching MP3s.
            paths = {
                s.recording.path
                for s in self.saved
                if s.recording.word == record.word
                and s.recording.sense_id == record.sense_id
                and s.recording.path.parent == record.path.parent
            }
            paths.add(record.path)
            for path in paths:
                current = read_recording(path)
                if current is None:
                    continue
                updated = current
                try:
                    updated = persist_translation(current, message.result) or current
                except OSError as exc:
                    self.status(
                        self.t("Audio saved. Details could not be saved: {error}", error=exc),
                        warning=True,
                    )
                self.saved = [updated if s.recording.path == path else s for s in self.saved]
                if self.selected and self.selected.recording.path == path:
                    self.selected = updated
        self.update_translation()
        if self.quit_pending and not self.busy and not self.playing and not self.dictionary_busy:
            self.exit()

    def update_controls(self) -> None:
        self.screen_stack[0].query_one("#download", Button).disabled = self.busy
        self.screen_stack[0].query_one("#download", Button).loading = self.busy
        self.screen_stack[0].query_one("#query", Input).disabled = self.busy
        self.screen_stack[0].query_one("#again", Button).disabled = (
            self.busy or self.selected is None
        )
        self.screen_stack[0].query_one("#play", Button).disabled = (
            self.selected is None and not self.playing
        )
        self._set_button_label("play", "Stop" if self.playing else "Play")

    @on(Input.Submitted, "#query")
    @on(Button.Pressed, "#download")
    def submit(self) -> None:
        if self.busy:
            return
        try:
            word = normalize_word(
                self.screen_stack[0].query_one("#query", Input).value, self.options.language
            )
            regions = ("uk", "us") if self.options.accent == "both" else (self.options.accent,)
            existing = [
                read_recording(self.options.directory / audio_filename(word, accent))
                for accent in regions
            ]
        except (OSError, ValueError) as exc:
            self.status(self.t("Error: {error}", error=exc), error=True)
            return
        if not self.options.overwrite:
            for index, region in enumerate(regions):
                if existing[index] is None:
                    existing[index] = next(
                        (
                            current
                            for item in self.saved
                            if item.recording.word == word
                            and item.recording.accent == region
                            and (current := read_recording(item.recording.path)) is not None
                        ),
                        None,
                    )
        missing = [region for region, saved in zip(regions, existing, strict=True) if saved is None]
        if not missing and not self.options.overwrite:
            saved = next(saved for saved in reversed(existing) if saved is not None)
            self.show_recording(saved)
            table = self.screen_stack[0].query_one("#recordings", DataTable)
            key = str(saved.recording.path)
            if key in table.rows:
                table.move_cursor(row=table.get_row_index(key))
            self.status(self.t("Opened saved recording."))
            self.warning = ""
            if self.options.play:
                self.action_play()
        elif (self.options.overwrite and any(existing)) or any(
            saved is None and (self.options.directory / audio_filename(word, region)).exists()
            for region, saved in zip(regions, existing, strict=True)
        ):
            self.confirm_replace(word, self.options.accent)
        else:
            accent = "both" if len(missing) == 2 else missing[0]
            self.start_download(word, accent)

    @on(Button.Pressed, "#again")
    def download_again(self) -> None:
        if self.selected and not self.busy:
            self.confirm_replace(
                self.selected.recording.word,
                self.selected.recording.accent,
                target=self.selected.recording,
            )

    def confirm_replace(
        self, word: str, accent: str, *, target=None, variant_id=None, entries=None
    ) -> None:
        def answer(confirmed):
            if confirmed:
                self.start_download(
                    word,
                    accent,
                    overwrite=True,
                    target=target,
                    variant_id=variant_id,
                    entries=entries,
                )

        self.push_screen(ConfirmReplace(self.options.language, word), answer)

    def start_download(
        self,
        word: str,
        accent: str,
        *,
        overwrite: bool = False,
        variant_id=None,
        entries=None,
        target=None,
    ) -> None:
        self.busy = True
        self.warning = ""
        self.cancel_download.clear()
        self.update_controls()
        self.status(self.t("Downloading '{word}' · Ctrl+C to cancel", word=word))
        self.download(word, accent, self.options, overwrite, variant_id, entries, target)

    @work(thread=True, group="download", exit_on_error=False)
    def download(
        self,
        word: str,
        accent: str,
        options: Options,
        overwrite: bool,
        variant_id=None,
        entries=None,
        target=None,
    ) -> None:
        warnings = []

        def cancelled():
            if self.cancel_download.is_set():
                raise DownloadCancelled(translate("Download cancelled.", options.language))

        def store(record, translations=()):
            try:
                save_metadata(record, translations, options.translation)
            except OSError as exc:
                warnings.append(
                    translate(
                        "Audio saved. Details could not be saved: {error}",
                        options.language,
                        error=exc,
                    )
                )
            self.post_message(
                DownloadUpdate(SavedRecording(record, translations, options.translation))
            )

        try:
            with CambridgeClient(options.timeout, language=options.language) as client:
                result = download_recordings(
                    client,
                    word,
                    options.directory,
                    accent,
                    overwrite=overwrite,
                    combine=options.combine,
                    translation=options.translation,
                    on_recording=store,
                    variant_id=variant_id,
                    entries=entries,
                    target=target,
                    dictionary_dir=options.dictionary_dir,
                    offline_translation=options.offline,
                    check_cancelled=cancelled,
                )
            for i, record in enumerate(result.recordings):
                store(record, () if result.translation_results else result.translations)
                if result.translation_results:
                    current = read_recording(record.path)
                    if current:
                        updated = persist_translation(current, result.translation_results[i])
                        if updated:
                            self.post_message(DownloadUpdate(updated))
            if result.translation_error:
                warnings.append(
                    translate(
                        "Translation: {error}", options.language, error=result.translation_error
                    )
                )
            self.post_message(
                DownloadFinished(
                    warning="\n".join(dict.fromkeys(warnings)),
                    translation_error=result.translation_error,
                )
            )
        except SelectionRequired as exc:
            self.post_message(VariantSelection(word, exc))
        except (CambridgeError, OSError, ValueError) as exc:
            self.post_message(DownloadFinished(str(exc), "\n".join(dict.fromkeys(warnings))))

    def on_variant_selection(self, message: VariantSelection):
        self.busy = False
        self.update_controls()
        if self.quit_pending:
            if self.translation_pending is None and not self.playing and not self.dictionary_busy:
                self.exit()
            return
        selection = message.selection

        def choose(answer):
            if answer is None:
                self.status(self.t("Download cancelled."))
                return
            choice = next(v for v in selection.choices if v.id == answer[0])
            path = self.options.directory / audio_filename(
                message.word, choice.pronunciation.accent, choice.id
            )
            if path.exists():
                self.confirm_replace(
                    message.word,
                    choice.pronunciation.accent,
                    variant_id=choice.id,
                    entries=selection.entries,
                )
            else:
                self.start_download(
                    message.word,
                    choice.pronunciation.accent,
                    variant_id=choice.id,
                    entries=selection.entries,
                )

        self.push_screen(
            ChooseOption(
                self.options.language,
                "Choose pronunciation",
                [(v.label, v.id) for v in selection.choices],
            ),
            choose,
        )

    def action_variants(self):
        if self.busy or self.quit_pending or isinstance(self.screen, ModalScreen):
            return
        try:
            word = normalize_word(
                self.screen_stack[0].query_one("#query", Input).value
                or (self.selected.recording.word if self.selected else "")
            )
            self.start_download(word, self.options.accent)
        except ValueError as exc:
            self.status(str(exc), error=True)

    def action_edit_translation(self):
        if not self.selected or self.quit_pending or isinstance(self.screen, ModalScreen):
            return
        saved = self.selected
        language = self.options.translation or "russian"
        result = cached_translation(read_recording(saved.recording.path) or saved, language)
        choices = [(self.t("Edit translation"), "edit"), (self.t("Reset translation"), "reset")]
        if result:
            choices += [
                (
                    "; ".join(o.texts)
                    + (
                        f" ({context})"
                        if (context := translation_context(o, self.options.language))
                        else ""
                    ),
                    o.id,
                )
                for o in result.options
            ]

        def apply(answer):
            if answer is None:
                return
            try:
                mode, text = answer
                if mode in {"edit", "reset"}:
                    updated = edit_translation(saved, language, text if mode == "edit" else None)
                else:
                    updated = select_translation(
                        read_recording(saved.recording.path), language, mode
                    )
                self.saved = [
                    updated if s.recording.path == saved.recording.path else s for s in self.saved
                ]
                if self.selected and self.selected.recording.path == saved.recording.path:
                    self.show_recording(updated)
            except (OSError, ValueError) as exc:
                self.status(str(exc), error=True)

        self.push_screen(
            ChooseOption(
                self.options.language,
                "Edit translation",
                choices,
                text="; ".join(result.texts) if result else "",
            ),
            apply,
        )

    def action_export(self):
        if self.quit_pending or isinstance(self.screen, ModalScreen):
            return
        saved = self.selected

        def apply(answer):
            if answer is None:
                return
            try:
                scope, path = answer
                records = (
                    [read_recording(saved.recording.path)]
                    if scope == "selected" and saved
                    else scan_recordings(self.options.directory)
                    if scope == "all"
                    else []
                )
                if not all(records):
                    raise ValueError("Selected MP3 is missing or unreadable.")
                output = export_anki(
                    records, Path(path).expanduser(), language=self.options.translation or "russian"
                )
                self.status(self.t("Anki export saved: {path}", path=output))
            except (OSError, ValueError) as exc:
                self.status(str(exc), error=True)

        self.push_screen(
            ChooseOption(
                self.options.language,
                "Export to Anki",
                [(self.t("Selected recording"), "selected"), (self.t("Whole collection"), "all")],
                text=str(self.options.directory / "cambridge-anki"),
            ),
            apply,
        )

    def action_dictionary(self):
        if self.dictionary_busy or self.quit_pending or isinstance(self.screen, ModalScreen):
            return

        def apply(answer):
            if answer is not None:
                self.dictionary_busy = True
                self.install_wikdict()
                self.status(PACKAGE.describe(self.options.language))

        self.push_screen(
            ChooseOption(
                self.options.language,
                "Install WikDict",
                [],
                note=PACKAGE.describe(self.options.language) + "\n" + PACKAGE.license_url,
            ),
            apply,
        )

    @work(thread=True, group="dictionary", exit_on_error=False)
    def install_wikdict(self):
        try:

            def cancelled():
                if self.quit_pending:
                    raise DownloadCancelled("Dictionary installation cancelled.")

            install_dictionary(self.options.dictionary_dir, check_cancelled=cancelled)
            self.post_message(DictionaryFinished())
        except Exception as exc:
            self.post_message(DictionaryFinished(str(exc)))

    def on_dictionary_finished(self, message):
        self.dictionary_busy = False
        self.translation_errors.clear()
        self.status(message.error or self.t("WikDict installed."), error=bool(message.error))
        self.update_translation()
        if (
            self.quit_pending
            and not self.busy
            and not self.playing
            and self.translation_pending is None
        ):
            self.exit()

    def on_download_update(self, message: DownloadUpdate) -> None:
        self.saved = [s for s in self.saved if s.recording.path != message.saved.recording.path]
        self.saved.append(message.saved)
        self.saved.sort(key=lambda s: (s.recording.word.casefold(), s.recording.accent))
        self.show_recording(message.saved)
        self.render_library()

    def on_download_finished(self, message: DownloadFinished) -> None:
        self.busy = False
        self.update_controls()
        self.action_search()
        self.warning = message.warning
        if message.translation_error and self.selected:
            self.translation_errors[
                (self.selected.recording.path, self.options.translation or "russian")
            ] = self.t("Translation: {error}", error=message.translation_error)
        self.update_translation()
        if (
            self.quit_pending
            and not self.playing
            and self.translation_pending is None
            and not self.dictionary_busy
        ):
            self.exit()
            return
        if message.error:
            self.status(self.t("Error: {error}", error=message.error), error=True)
        elif message.warning:
            self.status(message.warning, warning=True)
        else:
            self.status(self.t("Recording saved."))
            if self.options.play and not self.quit_pending:
                self.action_play()

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.ERROR:
            error = self.t("Unexpected error: {error}", error=event.worker.error)
            if event.worker.group == "download":
                self.on_download_finished(DownloadFinished(error))
            elif event.worker.group == "playback":
                self.on_playback_finished(PlaybackFinished(error))
            elif event.worker.group == "translation" and self.translation_pending:
                self.on_translation_finished(
                    TranslationFinished(self.translation_pending, error=error)
                )

    @on(Button.Pressed, "#play")
    def action_play(self) -> None:
        if self.playing:
            self.stop_playback.set()
            return
        if not self.selected or self.quit_pending:
            return
        if not self.selected.recording.path.is_file():
            self.status(
                self.t("The recording was moved or deleted. Download it again."), error=True
            )
            return
        self.playing = True
        self.stop_playback.clear()
        self.update_controls()
        self.status(self.t("Playing '{word}'", word=self.selected.recording.word))
        self.play(self.selected.recording.path, self.options.language)

    @work(thread=True, group="playback", exit_on_error=False)
    def play(self, path: Path, language: str) -> None:
        try:
            play_audio(path, language, stop=self.stop_playback)
            self.post_message(PlaybackFinished())
        except (CambridgeError, OSError) as exc:
            self.post_message(PlaybackFinished(str(exc)))

    def on_playback_finished(self, message: PlaybackFinished) -> None:
        self.playing = False
        self.update_controls()
        if (
            self.quit_pending
            and not self.busy
            and self.translation_pending is None
            and not self.dictionary_busy
        ):
            self.exit()
        elif message.error:
            self.status(self.t("Playback: {error}", error=message.error), error=True)
        elif not self.busy:
            self.status(
                self.warning or self.t("Opened saved recording."), warning=bool(self.warning)
            )

    def action_settings(self) -> None:
        if self.busy or self.quit_pending or isinstance(self.screen, ModalScreen):
            return

        def apply_settings(result):
            if result:
                old_translation = self.options.translation
                self.options, self.theme = result
                if self.options.translation != old_translation:
                    self.screen_stack[0].query_one("#show-translation", Checkbox).value = bool(
                        self.options.translation
                    )
                self.selected = None
                self.localize()
                self.action_refresh()

        self.push_screen(Settings(self.options, self.theme), apply_settings)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        if action == "about":
            return not self.quit_pending and (
                not isinstance(self.screen, ModalScreen) or isinstance(self.screen, Help)
            )
        return not (
            isinstance(self.screen, ModalScreen)
            and action
            in {
                "search",
                "play",
                "refresh",
                "settings",
                "export",
                "dictionary",
                "edit_translation",
                "variants",
            }
        )

    def action_help(self) -> None:
        if not isinstance(self.screen, ModalScreen):
            self.push_screen(Help(self.options.language))

    def action_about(self) -> None:
        if self.check_action("about", ()):
            self.push_screen(About(self.options.language))

    def action_cancel(self) -> None:
        if self.busy:
            self.cancel_download.set()
            self.status(self.t("Cancelling after the current request..."))
        elif self.playing:
            self.stop_playback.set()
        else:
            self.action_quit()

    def action_quit(self) -> None:
        if (
            self.busy
            or self.playing
            or self.translation_pending is not None
            or self.dictionary_busy
        ):
            self.quit_pending = True
            self.cancel_download.set()
            self.stop_playback.set()
            self.status(self.t("Finishing the current operation before closing..."))
        else:
            self.exit()

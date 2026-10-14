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
from textual.widgets import Button, Checkbox, DataTable, Footer, Input, Label, Select, Static
from textual.worker import Worker, WorkerState

from .audio import play_audio
from .dictionary import CambridgeClient, CambridgeError, audio_filename, normalize_word
from .i18n import translate
from .library import SavedRecording, read_recording, save_metadata, scan_recordings
from .service import DownloadCancelled, download_recordings


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
            yield Label(t("Translation language (Russian if empty)"))
            yield Input(self.options.translation or "", placeholder="russian", id="translation")
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
            translation=self.query_one("#translation", Input).value.strip() or None,
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
            yield Button(translate("Close", self.language), id="close-help")

    @on(Button.Pressed)
    def close_help(self) -> None:
        self.dismiss(None)


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
    ):
        super().__init__()
        self.saved = saved
        self.language = language
        self.translations = translations
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
        Binding("f1", "help", "Help", priority=True),
        Binding("ctrl+c", "cancel", "Cancel", priority=True, show=False),
        Binding("ctrl+q", "quit", "Quit", priority=True),
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
        self.options = replace(options, directory=options.directory.expanduser().resolve())
        self.saved: list[SavedRecording] = []
        self.selected: SavedRecording | None = None
        self.busy = False
        self.playing = False
        self.cancel_download = Event()
        self.stop_playback = Event()
        self.quit_pending = False
        self.warning = ""
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
                    self.t("Show translation"),
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
        self.screen.set_class(event.size.width < 76, "narrow")
        self.screen.set_class(event.size.height < 28, "short")

    def localize(self) -> None:
        for key, label in (("download", "Download"), ("play", "Play"), ("again", "Download again")):
            self.query_one(f"#{key}", Button).label = self.t(label)
        self.query_one("#query", Input).placeholder = self.t("For example: hello or good morning")
        self.query_one("#show-translation", Checkbox).label = self.t("Show translation")
        self.query_one("#library-pane").border_title = self.t("Saved recordings")
        self.query_one("#detail-pane").border_title = self.t("Recording")
        for key, action, label in (
            ("ctrl+l", "search", "Search"),
            ("ctrl+p", "play", "Play"),
            ("ctrl+r", "refresh", "Refresh"),
            ("ctrl+s", "settings", "Settings"),
            ("f1", "help", "Help"),
            ("ctrl+q", "quit", "Quit"),
        ):
            self.bind(key, action, description=self.t(label))
        self.refresh_bindings()
        self.query_one("#context", Static).update(
            Text(f"{self.options.accent.upper()}  ·  {display_path(self.options.directory)}")
        )
        table = self.query_one("#recordings", DataTable)
        table.clear(columns=True)
        table.add_columns(self.t("Word or phrase"), self.t("Accent"))
        self.render_library()
        self.show_recording(self.selected)

    def status(self, message: str, *, error: bool = False, warning: bool = False) -> None:
        widget = self.query_one("#status", Static)
        widget.set_class(error, "error")
        widget.set_class(warning, "warning")
        widget.update(Text(message))

    def action_search(self) -> None:
        self.query_one("#query", Input).focus()

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
        query = self.query_one("#query", Input).value.strip().casefold()
        table = self.query_one("#recordings", DataTable)
        selected_path = str(self.selected.recording.path) if self.selected else None
        table.clear()
        matches = [s for s in self.saved if query in s.recording.word.casefold()]
        preferred = "us" if self.options.accent == "both" else self.options.accent
        selected_row = next(
            (i for i, s in enumerate(matches) if s.recording.accent == preferred), 0
        )
        for index, saved in enumerate(matches):
            record = saved.recording
            table.add_row(Text(record.word), record.accent.upper(), key=str(record.path))
            if str(record.path) == selected_path:
                selected_row = index
        if matches:
            table.move_cursor(row=selected_row)
        self.query_one("#empty", Static).display = not matches
        self.query_one("#empty", Static).update(
            self.t("No matching recordings" if self.saved else "No saved recordings")
        )

    @on(Input.Changed, "#query")
    def filter_library(self) -> None:
        self.render_library()

    @on(DataTable.RowHighlighted)
    def highlight(self, event: DataTable.RowHighlighted) -> None:
        saved = next((s for s in self.saved if str(s.recording.path) == event.row_key.value), None)
        if saved:
            self.show_recording(saved)

    @on(DataTable.RowSelected)
    def select_recording(self, event: DataTable.RowSelected) -> None:
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
                "definition": record.definition
                or self.t("Details are unavailable for this saved recording."),
                "translation": "\n".join(saved.translations),
                "file": display_path(record.path),
            }
        for key, value in values.items():
            self.query_one(f"#{key}", Static).update(Text(value))
        self.update_translation()
        self.update_controls()

    @on(Checkbox.Changed, "#show-translation")
    def toggle_translation(self) -> None:
        if self.selected and self.query_one("#show-translation", Checkbox).value:
            self.translation_errors.pop(
                (self.selected.recording.path, self.options.translation or "russian"), None
            )
        self.update_translation()

    def update_translation(self) -> None:
        widget = self.query_one("#translation", Static)
        widget.display = (
            self.selected is not None and self.query_one("#show-translation", Checkbox).value
        )
        if not widget.display:
            return
        saved = self.selected
        if not saved.recording.path.is_file():
            widget.update(Text(self.t("The recording was moved or deleted. Download it again.")))
            return
        language = self.options.translation or "russian"
        key = (saved.recording.path, language)
        if saved.translations and saved.translation_language == language:
            widget.update(Text("\n".join(saved.translations)))
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
                translations = client.translations(
                    saved.recording.word, options.translation or "russian"
                )
            self.post_message(
                TranslationFinished(saved, translations, language=options.translation or "russian")
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
        if message.error or not message.translations:
            self.translation_errors[(record.path, message.language)] = (
                self.t("Translation: {error}", error=message.error)
                if message.error
                else self.t("No translation found. Toggle off and on to retry.")
            )
        else:
            # Update both accents without changing the selected row or touching MP3s.
            paths = {
                s.recording.path
                for s in self.saved
                if s.recording.word == record.word and s.recording.path.parent == record.path.parent
            }
            paths.add(record.path)
            for path in paths:
                current = read_recording(path)
                if current is None:
                    continue
                updated = SavedRecording(current.recording, message.translations, message.language)
                try:
                    save_metadata(
                        updated.recording, updated.translations, updated.translation_language
                    )
                except OSError as exc:
                    self.status(
                        self.t("Audio saved. Details could not be saved: {error}", error=exc),
                        warning=True,
                    )
                self.saved = [updated if s.recording.path == path else s for s in self.saved]
                if self.selected and self.selected.recording.path == path:
                    self.selected = updated
        self.update_translation()
        if self.quit_pending and not self.busy and not self.playing:
            self.exit()

    def update_controls(self) -> None:
        self.query_one("#download", Button).disabled = self.busy
        self.query_one("#download", Button).loading = self.busy
        self.query_one("#query", Input).disabled = self.busy
        self.query_one("#again", Button).disabled = self.busy or self.selected is None
        self.query_one("#play", Button).disabled = self.selected is None and not self.playing
        self.query_one("#play", Button).label = self.t("Stop" if self.playing else "Play")

    @on(Input.Submitted, "#query")
    @on(Button.Pressed, "#download")
    def submit(self) -> None:
        if self.busy:
            return
        try:
            word = normalize_word(self.query_one("#query", Input).value, self.options.language)
            regions = ("uk", "us") if self.options.accent == "both" else (self.options.accent,)
            existing = [
                read_recording(self.options.directory / audio_filename(word, accent))
                for accent in regions
            ]
        except (OSError, ValueError) as exc:
            self.status(self.t("Error: {error}", error=exc), error=True)
            return
        missing = [region for region, saved in zip(regions, existing, strict=True) if saved is None]
        if not missing and not self.options.overwrite:
            saved = next(saved for saved in reversed(existing) if saved is not None)
            self.show_recording(saved)
            table = self.query_one("#recordings", DataTable)
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
            self.confirm_replace(self.selected.recording.word, self.selected.recording.accent)

    def confirm_replace(self, word: str, accent: str) -> None:
        def answer(confirmed):
            if confirmed:
                self.start_download(word, accent, overwrite=True)

        self.push_screen(ConfirmReplace(self.options.language, word), answer)

    def start_download(self, word: str, accent: str, *, overwrite: bool = False) -> None:
        self.busy = True
        self.warning = ""
        self.cancel_download.clear()
        self.update_controls()
        self.status(self.t("Downloading '{word}' · Ctrl+C to cancel", word=word))
        self.download(word, accent, self.options, overwrite)

    @work(thread=True, group="download", exit_on_error=False)
    def download(self, word: str, accent: str, options: Options, overwrite: bool) -> None:
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
                    check_cancelled=cancelled,
                )
            for record in result.recordings:
                store(record, result.translations)
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
        except (CambridgeError, OSError, ValueError) as exc:
            self.post_message(DownloadFinished(str(exc), "\n".join(dict.fromkeys(warnings))))

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
        if self.quit_pending and not self.playing and self.translation_pending is None:
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
        if self.quit_pending and not self.busy and self.translation_pending is None:
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
                    self.query_one("#show-translation", Checkbox).value = bool(
                        self.options.translation
                    )
                self.selected = None
                self.localize()
                self.action_refresh()

        self.push_screen(Settings(self.options, self.theme), apply_settings)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        return not (
            isinstance(self.screen, ModalScreen)
            and action in {"search", "play", "refresh", "settings"}
        )

    def action_help(self) -> None:
        if not isinstance(self.screen, ModalScreen):
            self.push_screen(Help(self.options.language))

    def action_cancel(self) -> None:
        if self.busy:
            self.cancel_download.set()
            self.status(self.t("Cancelling after the current request..."))
        elif self.playing:
            self.stop_playback.set()
        else:
            self.action_quit()

    def action_quit(self) -> None:
        if self.busy or self.playing or self.translation_pending is not None:
            self.quit_pending = True
            self.cancel_download.set()
            self.stop_playback.set()
            self.status(self.t("Finishing the current operation before closing..."))
        else:
            self.exit()

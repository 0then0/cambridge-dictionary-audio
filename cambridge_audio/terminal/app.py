"""Terminal workspace, actions and background task coordination."""

from dataclasses import replace
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widgets import Button, Checkbox, DataTable, Footer, Input, OptionList, Select, Static
from textual.widgets.option_list import Option
from textual.worker import Worker, WorkerState

from ..anki import export_anki, export_apkg
from ..audio import play_audio
from ..dictionary import (
    CambridgeClient,
    CambridgeError,
    SelectionRequired,
    audio_filename,
    normalize_word,
    variants,
)
from ..errors import diagnostic_details, friendly_error
from ..i18n import translate
from ..library import SavedRecording, read_recording, save_metadata, scan_recordings
from ..service import DownloadCancelled, Recording, download_recordings, preview_recording
from ..translations import (
    cached_translation,
    edit_translation,
    persist_translation,
    resolve_translation,
    select_translation,
)
from ..wikdict import PACKAGE, install_dictionary
from .dialogs import About, ChooseOption, ConfirmReplace, ErrorDetails, Help, Settings
from .messages import (
    DictionaryFinished,
    DownloadFinished,
    DownloadUpdate,
    PlaybackFinished,
    TranslationFinished,
    VariantSelection,
)
from .rendering import display_path, render_translation, translation_context
from .settings import Options, save_settings


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
        Binding("ctrl+o", "variants", "Choose meaning", priority=True),
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
            ("ctrl+щ,f10", "variants", "Choose meaning"),
            ("ctrl+с,f11", "cancel", "Cancel"),
            ("ctrl+й,f12", "quit", "Quit"),
        )
    ]
    CSS_PATH = "app.tcss"

    def __init__(self, options: Options, *, theme: str = "cambridge-dark"):
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
        self.theme = theme
        self.options = replace(
            options,
            directory=options.directory.expanduser().resolve(),
            translation="russian" if options.translation else None,
        )
        self._lookup_entries = ()
        self._lookup_word = ""
        self._audio_choices = ()
        self._preview_cache = TemporaryDirectory(prefix="cambridge-preview-")
        self._preview_translations = {}
        self.saved: list[SavedRecording] = []
        self.selected: SavedRecording | None = None
        self.busy = False
        self.playing = False
        self.cancel_download = Event()
        self.stop_playback = Event()
        self.quit_pending = False
        self.warning = ""
        self._error_details = {}
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
            yield Button(self.t("Find"), variant="primary", id="download")
        with Horizontal(id="workspace"):
            with Vertical(id="library-pane"):
                yield DataTable(id="recordings", cursor_type="row", show_row_labels=False)
                yield Static("", id="empty")
            with Vertical(id="detail-pane"):
                with VerticalScroll(id="detail-scroll"):
                    yield Static("", id="word")
                    yield Static("", id="pronunciation")
                    yield Select(
                        [("US", "us"), ("UK", "uk")],
                        value="us" if self.options.accent == "both" else self.options.accent,
                        allow_blank=False,
                        id="result-accent",
                    )
                    yield OptionList(id="meanings")
                    yield Select([], allow_blank=True, id="other-audio")
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
                    yield Button(self.t("Save meaning"), id="save-meaning")
                    yield Button(self.t("Download again"), id="again", disabled=True)
        yield Static("", id="status")
        yield Static("", id="error-summary")
        yield Button(self.t("Technical details"), id="error-details")
        yield Footer()

    def on_mount(self) -> None:
        for key in ("meanings", "other-audio", "result-accent", "save-meaning"):
            self.query_one(f"#{key}").display = False
        self.query_one("#error-details").display = False
        self.query_one("#error-summary").display = False
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
        self._set_button_label("error-details", "Technical details")
        for key, label in (("download", "Find"), ("play", "Play"), ("again", "Download again")):
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

    def status(
        self, message: str, *, error: bool = False, warning: bool = False, context="operation"
    ) -> None:
        widget = self.screen_stack[0].query_one("#status", Static)
        widget.set_class(error, "error")
        widget.set_class(warning, "warning")
        if error or warning:
            self._set_error_details("Operation", message)
            if "Details could not" in str(message) or "сведения" in str(message):
                context = "metadata"
            message = friendly_error(message, self.options.language, context=context)
        else:
            self._set_error_details("Operation", "")
        widget.update(Text(message))

    def _set_error_details(self, section, error):
        if error:
            self._error_details[section] = diagnostic_details(error)
        else:
            self._error_details.pop(section, None)
        summaries = [
            self.t(key) + ": " + friendly_error(value, self.options.language, context="translation")
            for key, value in self._error_details.items()
            if key != "Operation"
        ]
        summary = self.screen_stack[0].query_one("#error-summary", Static)
        summary.update(Text("\n".join(summaries)))
        summary.display = bool(summaries)
        self.screen_stack[0].query_one("#error-details").display = bool(self._error_details)

    @on(Button.Pressed, "#error-details")
    def show_error_details(self):
        if self._error_details and not isinstance(self.screen, ModalScreen):
            self.push_screen(
                ErrorDetails(
                    self.options.language,
                    "\n\n".join(
                        self.t(key) + "\n" + value for key, value in self._error_details.items()
                    ),
                )
            )

    def action_search(self) -> None:
        self.screen_stack[0].query_one("#query", Input).focus()

    def action_refresh(self) -> None:
        try:
            self.saved = scan_recordings(self.options.directory)
        except OSError as exc:
            self.status(exc, error=True, context="library")
            return
        self.render_library()
        if self.selected:
            current = next(
                (
                    s
                    for s in self.saved
                    if s.recording.reference == self.selected.recording.reference
                ),
                None,
            )
            self.show_recording(current)
        if not self.busy:
            self.status(self.t("Ready · {count} saved recordings", count=len(self.saved)))

    def render_library(self) -> None:
        query = self.screen_stack[0].query_one("#query", Input).value.strip().casefold()
        table = self.screen_stack[0].query_one("#recordings", DataTable)
        selected_path = str(self.selected.recording.reference) if self.selected else None
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
                key=str(record.reference),
            )
            if str(record.reference) == selected_path:
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
        if event.data_table.id != "recordings":
            return
        if not self.screen_stack or not self.screen_stack[0].query("#word"):
            return
        saved = next(
            (s for s in self.saved if str(s.recording.reference) == event.row_key.value), None
        )
        if saved and not self._lookup_entries:
            self.show_recording(saved)

    @on(DataTable.RowSelected)
    def select_recording(self, event: DataTable.RowSelected) -> None:
        if not self.screen_stack or not self.screen_stack[0].query("#word"):
            return
        saved = next(
            (s for s in self.saved if str(s.recording.reference) == event.row_key.value), None
        )
        if saved:
            self._lookup_entries = ()
            self._audio_choices = ()
            for key in ("meanings", "other-audio", "result-accent", "save-meaning"):
                self.query_one(f"#{key}").display = False
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
                "file": self.t("Already saved"),
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
        changed = bool(self.options.translation) != enabled
        self.options = replace(self.options, translation="russian" if enabled else None)
        if self.selected and enabled:
            self.translation_errors.pop(
                (self.selected.recording.reference, self.options.translation or "russian"), None
            )
        self.update_translation()
        if changed:
            self.save_preferences()

    def update_translation(self) -> None:
        if self._lookup_entries:
            self.show_choice()
            return
        widget = self.screen_stack[0].query_one("#translation", Static)
        widget.display = (
            self.selected is not None
            and self.screen_stack[0].query_one("#show-translation", Checkbox).value
        )
        if not widget.display:
            self._set_error_details("Translation", "")
            return
        saved = self.selected
        if not saved.recording.path.is_file():
            widget.update(Text(self.t("The recording was moved or deleted. Download it again.")))
            return
        language = self.options.translation or "russian"
        key = (saved.recording.reference, language)
        saved = read_recording(saved.recording.reference) or saved
        result = cached_translation(saved, language)
        if result:
            self._set_error_details("Translation", result.error)
            widget.update(render_translation(result, self.options.language))
        elif key in self.translation_errors:
            raw = self.translation_errors[key]
            self._set_error_details("Translation", raw)
            widget.update(Text(friendly_error(raw, self.options.language, context="translation")))
        else:
            self._set_error_details("Translation", "")
            widget.update(Text(self.t("Loading translation...")))
            if not self.busy and self.translation_pending is None and not self.quit_pending:
                self.translation_pending = saved
                self.fetch_translation(saved, self.options)

    @work(thread=True, group="translation", exit_on_error=False)
    def fetch_translation(self, saved: SavedRecording, options: Options) -> None:
        def cancelled():
            if self.quit_pending:
                raise DownloadCancelled(translate("Download cancelled.", options.language))

        try:
            with CambridgeClient(
                options.timeout, language=options.language, check_cancelled=cancelled
            ) as client:
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
                    saved, error=diagnostic_details(exc), language=options.translation or "russian"
                )
            )

    def on_translation_finished(self, message: TranslationFinished) -> None:
        self.translation_pending = None
        record = message.saved.recording
        if record.path.parent == Path(self._preview_cache.name):
            if message.error and not message.result:
                from ..translations import TranslationResult

                message.result = TranslationResult(
                    message.language,
                    record.sense_id,
                    "Cambridge",
                    error=message.error,
                    status="error",
                )
            if message.result:
                self._preview_translations[record.sense_id] = message.result
            if self._lookup_entries:
                self.show_choice()
            return
        if message.error or not message.result or not message.result.options:
            self.translation_errors[(record.reference, message.language)] = (
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
                s.recording.reference
                for s in self.saved
                if s.recording.word == record.word
                and s.recording.sense_id == record.sense_id
                and s.recording.path.parent == record.path.parent
            }
            paths.add(record.reference)
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
                self.saved = [updated if s.recording.reference == path else s for s in self.saved]
                if self.selected and self.selected.recording.reference == path:
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
            self.selected is None and not self.playing and not self._audio_choices
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
                            and (current := read_recording(item.recording.reference)) is not None
                        ),
                        None,
                    )
        missing = [region for region, saved in zip(regions, existing, strict=True) if saved is None]
        if not missing and not self.options.overwrite:
            saved = next(saved for saved in reversed(existing) if saved is not None)
            self.show_recording(saved)
            table = self.screen_stack[0].query_one("#recordings", DataTable)
            key = str(saved.recording.reference)
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
            self.start_download(word, accent, select_only=True)

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
        select_only=False,
    ) -> None:
        self.busy = True
        self.warning = ""
        self.cancel_download.clear()
        self.update_controls()
        self.status(self.t("Downloading '{word}' · Ctrl+C to cancel", word=word))
        self.download(
            word, accent, self.options, overwrite, variant_id, entries, target, select_only
        )

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
        select_only=False,
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
            with CambridgeClient(
                options.timeout, language=options.language, check_cancelled=cancelled
            ) as client:
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
                    select_only=select_only,
                    audio_cache_dir=Path(self._preview_cache.name),
                )
            for i, record in enumerate(result.recordings):
                store(record, () if result.translation_results else result.translations)
                if result.translation_results:
                    current = read_recording(record.reference)
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
            self.post_message(
                DownloadFinished(diagnostic_details(exc), "\n".join(dict.fromkeys(warnings)))
            )

    def on_variant_selection(self, message: VariantSelection):
        self.busy = False
        self.update_controls()
        if self.quit_pending:
            if self.translation_pending is None and not self.playing and not self.dictionary_busy:
                self.exit()
            return
        self._lookup_target = getattr(message.selection, "target", None)
        self._lookup_entries = message.selection.entries
        self._lookup_word = message.word
        accents = {v.pronunciation.accent for v in message.selection.choices}
        if len(accents) == 1:
            self.query_one("#result-accent", Select).value = next(iter(accents))
        listing = self.query_one("#meanings", OptionList)
        listing.clear_options()
        seen, first = set(), None
        for entry in sorted(self._lookup_entries, key=lambda e: e.part_of_speech):
            if entry.sense_id in seen or not entry.pronunciations:
                continue
            seen.add(entry.sense_id)
            listing.add_option(
                Option(
                    Text(f"{self.t(entry.part_of_speech)} · {entry.definition}"), id=entry.sense_id
                )
            )
            if first is None:
                first = entry.sense_id
        for key in ("meanings", "result-accent", "save-meaning"):
            self.query_one(f"#{key}").display = True
        if first:
            listing.highlighted = 0
            self._show_meaning(first)
        self.status(self.t("Choose a meaning, listen, then save."))
        listing.focus()

    @on(OptionList.OptionHighlighted, "#meanings")
    def highlight_meaning(self, event):
        self._show_meaning(event.option.id)

    @on(Select.Changed, "#result-accent")
    def result_accent_changed(self):
        listing = self.query_one("#meanings", OptionList)
        if self._lookup_entries and listing.highlighted is not None:
            self._show_meaning(listing.get_option_at_index(listing.highlighted).id)

    def _show_meaning(self, sense_id):
        entry = next((e for e in self._lookup_entries if e.sense_id == sense_id), None)
        if not entry:
            return
        self._audio_choices = variants((entry,), self.query_one("#result-accent", Select).value)
        selector = self.query_one("#other-audio", Select)
        selector.set_options(
            [
                (f"{self.t('Other pronunciation')} {i + 1} · /{v.pronunciation.ipa}/", v.id)
                for i, v in enumerate(self._audio_choices)
            ]
        )
        selector.display = len(self._audio_choices) > 1
        selector.value = self._audio_choices[0].id if self._audio_choices else Select.NULL
        self.show_choice()

    def current_choice(self):
        identity = self.query_one("#other-audio", Select).value
        return next((v for v in self._audio_choices if v.id == identity), None)

    @on(Select.Changed, "#other-audio")
    def show_choice(self):
        choice = self.current_choice()
        if not choice:
            self._set_error_details("Translation", "")
            self.query_one("#save-meaning", Button).disabled = True
            self.query_one("#play", Button).disabled = True
            return
        if getattr(self, "_displayed_choice", None) != choice.id and self.playing:
            self.stop_playback.set()
        self._displayed_choice = choice.id
        entry, audio = choice.entry, choice.pronunciation
        for key, value in (
            ("word", entry.word),
            ("pronunciation", f"{audio.accent.upper()} /{audio.ipa}/"),
            ("definition", entry.definition),
            ("file", ""),
        ):
            self.query_one(f"#{key}", Static).update(Text(value))
        existing = next(
            (
                s
                for s in self.saved
                if (
                    s.recording.source_sense_id == entry.sense_id
                    or s.recording.variant_id in entry.legacy_ids
                )
                and s.recording.audio_url == audio.url
            ),
            None,
        )
        self._set_button_label("save-meaning", "Already saved" if existing else "Save meaning")
        self.query_one("#save-meaning", Button).disabled = self.busy
        self.query_one("#play", Button).disabled = self.busy
        widget = self.query_one("#translation", Static)
        widget.display = bool(self.options.translation)
        result = (
            cached_translation(existing, self.options.translation or "russian")
            if existing
            else None
        )
        result = result or self._preview_translations.get(entry.sense_id)
        self._set_error_details(
            "Translation", result.error if result and self.options.translation else ""
        )
        widget.update(render_translation(result, self.options.language) if result else "")
        if self.options.translation and not result and self.translation_pending is None:
            preview = Recording(
                entry.word,
                audio.accent,
                Path(self._preview_cache.name) / "preview.us.mp3",
                audio.ipa,
                entry.definition,
                part_of_speech=entry.part_of_speech,
                sense_id=entry.sense_id,
                source_url=entry.source_url,
                lemma=entry.lemma,
            )
            self.translation_pending = SavedRecording(preview)
            self.fetch_translation(self.translation_pending, self.options)

    @on(Button.Pressed, "#save-meaning")
    def save_meaning(self):
        choice = self.current_choice()
        if choice and not self.busy:
            self.start_download(
                self._lookup_word,
                choice.pronunciation.accent,
                variant_id=choice.id,
                entries=self._lookup_entries,
                target=getattr(self, "_lookup_target", None),
            )

    def action_variants(self):
        if self.busy or self.quit_pending or isinstance(self.screen, ModalScreen):
            return
        try:
            word = normalize_word(
                self.screen_stack[0].query_one("#query", Input).value
                or (self.selected.recording.word if self.selected else "")
            )
            self.start_download(word, self.options.accent, select_only=True)
        except ValueError as exc:
            self.status(exc, error=True)

    def action_edit_translation(self):
        if not self.selected or self.quit_pending or isinstance(self.screen, ModalScreen):
            return
        saved = self.selected
        if self._lookup_entries and (choice := self.current_choice()):
            saved = next(
                (
                    s
                    for s in self.saved
                    if s.recording.source_sense_id == choice.entry.sense_id
                    and s.recording.audio_url == choice.pronunciation.url
                ),
                None,
            )
            if saved is None:
                return
        language = self.options.translation or "russian"
        result = cached_translation(read_recording(saved.recording.reference) or saved, language)
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
                        read_recording(saved.recording.reference), language, mode
                    )
                self.saved = [
                    updated if s.recording.reference == saved.recording.reference else s
                    for s in self.saved
                ]
                if self.selected and self.selected.recording.reference == saved.recording.reference:
                    self.show_recording(updated)
            except (OSError, ValueError) as exc:
                self.status(exc, error=True)

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
        if self._lookup_entries and (choice := self.current_choice()):
            saved = next(
                (
                    s
                    for s in self.saved
                    if s.recording.source_sense_id == choice.entry.sense_id
                    and s.recording.audio_url == choice.pronunciation.url
                ),
                None,
            )

        def apply(answer):
            if answer is None:
                return
            try:
                scope, path = answer
                records = (
                    [read_recording(saved.recording.reference)]
                    if scope == "selected" and saved
                    else scan_recordings(self.options.directory)
                    if scope == "all"
                    else []
                )
                if not all(records):
                    raise ValueError("Selected MP3 is missing or unreadable.")
                destination = Path(path).expanduser()
                exporter = export_anki if destination.suffix.lower() == ".tsv" else export_apkg
                if exporter is export_anki:
                    destination = destination.with_suffix("")
                output = exporter(
                    records, destination, language=self.options.translation or "russian"
                )
                self.status(self.t("Anki export saved: {path}", path=output))
            except (OSError, ValueError) as exc:
                self.status(exc, error=True, context="export")

        self.push_screen(
            ChooseOption(
                self.options.language,
                "Export to Anki",
                [(self.t("Selected recording"), "selected"), (self.t("Whole collection"), "all")],
                text=str(self.options.directory / "cambridge-anki.apkg"),
                note=self.t("Use .apkg for a ready deck, or .tsv for a text export folder."),
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
            self.post_message(DictionaryFinished(diagnostic_details(exc)))

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
        self.saved = [
            s for s in self.saved if s.recording.reference != message.saved.recording.reference
        ]
        self.saved.append(message.saved)
        self.saved.sort(key=lambda s: (s.recording.word.casefold(), s.recording.accent))
        self.show_recording(message.saved)
        self.render_library()
        if self._lookup_entries:
            self.show_choice()

    def on_download_finished(self, message: DownloadFinished) -> None:
        self.busy = False
        self.update_controls()
        self.action_search()
        self.warning = message.warning
        if message.translation_error and self.selected:
            self.translation_errors[
                (self.selected.recording.reference, self.options.translation or "russian")
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
            error = diagnostic_details(event.worker.error)
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
        if self._lookup_entries and self.current_choice() and not self.quit_pending:
            self.playing = True
            self.stop_playback.clear()
            self.update_controls()
            self.play_preview(self.current_choice(), self.options)
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
    def play_preview(self, choice, options):
        try:
            with CambridgeClient(options.timeout, language=options.language) as client:
                path = preview_recording(
                    client, choice, Path(self._preview_cache.name), collection_dir=options.directory
                )
            if not self.stop_playback.is_set():
                play_audio(path, options.language, stop=self.stop_playback)
            self.post_message(PlaybackFinished())
        except (CambridgeError, OSError) as exc:
            self.post_message(PlaybackFinished(diagnostic_details(exc)))

    @work(thread=True, group="playback", exit_on_error=False)
    def play(self, path: Path, language: str) -> None:
        try:
            play_audio(path, language, stop=self.stop_playback)
            self.post_message(PlaybackFinished())
        except (CambridgeError, OSError) as exc:
            self.post_message(PlaybackFinished(diagnostic_details(exc)))

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
            self.status(message.error, error=True, context="playback")
        elif not self.busy:
            self.status(
                self.warning or self.t("Opened saved recording."), warning=bool(self.warning)
            )

    def save_preferences(self) -> None:
        try:
            save_settings(self.options, self.theme)
        except OSError as exc:
            self.status(exc, error=True, context="settings")

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
                self.save_preferences()

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

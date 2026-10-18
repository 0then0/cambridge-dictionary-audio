"""Small desktop interface. Run with: uv run --group gui -m cambridge_audio.gui."""

import sys
from dataclasses import replace
from html import escape
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from PySide6.QtCore import (
        QByteArray,
        QSettings,
        QSize,
        QStandardPaths,
        Qt,
        QUrl,
        Slot,
    )
    from PySide6.QtGui import QDesktopServices, QIcon
    from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QInputDialog,
        QLabel,
        QLineEdit,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError as exc:
    if exc.name == "PySide6":
        raise SystemExit(
            "Install the GUI with: uv run --group gui -m cambridge_audio.gui"
        ) from None
    raise

from ..anki import export_anki, export_apkg
from ..audio import ffmpeg_executable
from ..desktop import APPLICATION_NAME, launch_macos_bundle
from ..dictionary import (
    audio_filename,
    normalize_word,
    variants,
)
from ..errors import diagnostic_details, friendly_error
from ..i18n import translate
from ..library import SavedRecording, read_recording, scan_recordings
from ..service import DownloadResult, Recording
from ..translations import (
    TranslationResult,
    cached_translation,
    edit_translation,
    persist_translation,
    select_translation,
)
from ..wikdict import (
    PACKAGE,
    DictionaryCorrupt,
    DictionaryMissing,
    package_path,
    validate_package,
)
from .dialogs import ChoiceDialog
from .preferences import PreferencesDialog
from .theme import (
    ComboBox,
    ContentList,
    apply_theme,
    install_scrollbars,
    stored_colors,
    theme_colors,
    themed_icon,
)
from .workers import DictionaryWorker, DownloadRequest, DownloadWorker, TranslationWorker


def label(text="", *, name="", wrap=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(wrap)
    if name:
        widget.setObjectName(name)
    return widget


def set_choices(combo: QComboBox, choices: list[tuple[str, str]], selected: str):
    blocked = combo.blockSignals(True)
    try:
        combo.clear()
        for text, value in choices:
            combo.addItem(text, value)
        combo.setCurrentIndex(max(0, combo.findData(selected)))
    finally:
        combo.blockSignals(blocked)


def default_output_dir() -> Path:
    downloads = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    return (
        Path(downloads) if downloads else Path.home() / "Downloads"
    ) / "Cambridge Dictionary Audio"


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None):
        super().__init__()
        self.settings = (
            settings
            if settings is not None
            else QSettings("CambridgeDictionaryAudio", "CambridgeDictionaryAudio")
        )
        self.language = self._choice("language", {"en", "ru"}, "en")
        self.theme = self._choice("theme", {"system", "light", "dark"}, "system")
        self.accent = self._choice("accent", {"us", "uk", "both"}, "us")
        self.output_dir = Path(str(self.settings.value("output_dir", str(default_output_dir()))))
        self.recordings: list[Recording] = []
        self._accent_record: Recording | None = None
        self.translations: tuple[str, ...] = ()
        self._worker: DownloadWorker | None = None
        self._translation_worker: TranslationWorker | None = None
        self._translation_errors: dict[tuple[Path, str], str] = {}
        self._translation_attempts: set[tuple[Path, str]] = set()
        self._closing = False
        self._dictionary_worker = None
        self._pending_selection = None
        self._lookup_entries = ()
        self._preview_cache = TemporaryDirectory(prefix="cambridge-preview-")
        self._preview_translations = {}
        self._rendering_choices = False
        self.translation_language = "russian"
        self.dictionary_dir = None
        self._status_message = "Ready to download."
        self._status_values = {}
        self._status_severity = ""
        self._error_details = {}
        self.setWindowTitle(APPLICATION_NAME)
        self.setMinimumSize(620, 520)
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(
                max(620, min(760, available.width() - 48)),
                max(520, min(760, available.height() - 64)),
            )
        else:
            self.resize(760, 760)
        self._build_ui()
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.8)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio_output)
        self.player.playbackStateChanged.connect(self._playback_changed)
        self.player.errorOccurred.connect(self._playback_error)
        self._connect_ui()
        self._retranslate()
        app = QApplication.instance()
        app.styleHints().colorSchemeChanged.connect(self._system_theme_changed)
        app.aboutToQuit.connect(self.shutdown)
        self._apply_theme()
        self._set_busy(False)
        geometry = self.settings.value("window/geometry")
        if isinstance(geometry, (QByteArray, bytes)):
            # Qt also moves geometry from a disconnected display onto an available screen.
            self.restoreGeometry(geometry)
        self.refresh_library()
        self.word_edit.setFocus()

    def _choice(self, key, allowed, default):
        value = str(self.settings.value(key, default))
        return value if value in allowed else default

    def _t(self, message, **values):
        return translate(message, self.language, **values)

    def _build_ui(self):
        scroll = QScrollArea()
        install_scrollbars(scroll)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCentralWidget(scroll)
        page = QWidget()
        page.setObjectName("page")
        scroll.setWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        header = QHBoxLayout()
        header.setSpacing(12)
        icon = label()
        icon.setPixmap(self.windowIcon().pixmap(44, 44))
        icon.setFixedSize(44, 44)
        header.addWidget(icon)
        brand = QVBoxLayout()
        brand.setSpacing(4)
        brand.addWidget(label("Cambridge Dictionary Audio", name="heading"))
        self.subtitle = label(name="muted", wrap=True)
        brand.addWidget(self.subtitle)
        header.addLayout(brand, 1)
        self.settings_button = QPushButton()
        self.settings_button.setObjectName("settingsButton")
        self.settings_button.setFixedSize(40, 40)
        self.settings_button.setIconSize(QSize(22, 22))
        header.addWidget(self.settings_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)
        self.preferences_dialog = PreferencesDialog(self.settings, self)

        form = QFrame()
        form.setObjectName("panel")
        grid = QGridLayout(form)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        self.word_label = label()
        self.word_edit = QLineEdit()
        self.clear_action = self.word_edit.addAction(
            QIcon(str(Path(__file__).resolve().parents[2] / "assets" / "ui" / "clear.svg")),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        self.clear_action.setVisible(False)
        self.clear_action.triggered.connect(self.word_edit.clear)
        self.word_label.setBuddy(self.word_edit)
        self.download_button = QPushButton()
        self.download_button.setObjectName("downloadButton")
        self.download_button.setMinimumWidth(130)
        grid.addWidget(self.word_label, 0, 0, 1, 2)
        entry_row = QHBoxLayout()
        entry_row.setSpacing(12)
        entry_row.addWidget(self.word_edit, 1)
        entry_row.addWidget(self.download_button)
        grid.addLayout(entry_row, 1, 0, 1, 2)
        self.accent_label = label()
        self.accent_combo = ComboBox()
        self.accent_label.setBuddy(self.accent_combo)
        self.combine_check = QCheckBox()
        ffmpeg_available = bool(ffmpeg_executable())
        self.combine_check.setChecked(
            ffmpeg_available and self.settings.value("combine", False, type=bool)
        )
        self.combine_check.setEnabled(ffmpeg_available)
        self.translation_check = QCheckBox()
        self.translation_check.setChecked(self.settings.value("translation", False, type=bool))
        grid.addWidget(self.accent_label, 2, 0)
        grid.addWidget(self.accent_combo, 3, 0, 1, 2)
        grid.addWidget(self.combine_check, 4, 0, 1, 2)
        self.dictionary_button = QPushButton(self._t("Install WikDict"))
        self.dictionary_status_label = label(name="muted", wrap=True)
        grid.addWidget(self.translation_check, 5, 0)
        grid.addWidget(self.dictionary_button, 5, 1)
        grid.addWidget(self.dictionary_status_label, 6, 0, 1, 2)
        grid.setRowMinimumHeight(2, 28)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addWidget(form)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        layout.addWidget(self.progress)
        self.status_label = label(name="status", wrap=True)
        layout.addWidget(self.status_label)
        self.error_summary_label = label(wrap=True)
        self.error_summary_label.hide()
        layout.addWidget(self.error_summary_label)
        self.error_details_button = QPushButton(self._t("Technical details"))
        self.error_details_button.setCheckable(True)
        self.error_details_button.hide()
        self.error_details_text = QPlainTextEdit()
        self.error_details_text.setReadOnly(True)
        self.error_details_text.setMaximumHeight(180)
        self.error_details_text.setAccessibleName(self._t("Technical details"))
        self.error_details_text.hide()
        self.error_details_button.toggled.connect(self.error_details_text.setVisible)
        layout.addWidget(self.error_details_button)
        layout.addWidget(self.error_details_text)

        destination = QVBoxLayout()
        destination.setSpacing(8)
        self.folder_label = label()
        destination.addWidget(self.folder_label)
        destination_row = QHBoxLayout()
        destination_row.setSpacing(8)
        self.folder_edit = QLineEdit(str(self.output_dir))
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setCursorPosition(0)
        self.folder_label.setBuddy(self.folder_edit)
        self.choose_button = QPushButton()
        self.open_button = QPushButton()
        destination_row.addWidget(self.folder_edit, 1)
        destination_row.addWidget(self.choose_button)
        destination_row.addWidget(self.open_button)
        destination.addLayout(destination_row)
        layout.addLayout(destination)

        library_row = QHBoxLayout()
        self.library_label = label()
        self.library_combo = ComboBox()
        self.library_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.library_combo.setMinimumContentsLength(10)
        self.library_label.setBuddy(self.library_combo)
        self.refresh_button = QPushButton()
        library_row.addWidget(self.library_label)
        library_row.addWidget(self.library_combo, 1)
        library_row.addWidget(self.refresh_button)
        layout.addLayout(library_row)

        result = QFrame()
        result.setObjectName("panel")
        result_layout = QVBoxLayout(result)
        result_layout.setContentsMargins(16, 16, 16, 16)
        result_layout.setSpacing(8)
        self.result_title = label(name="word", wrap=True)
        self.ipa_label = label(name="muted", wrap=True)
        self.definition_label = label(wrap=True)
        self.definition_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.translation_label = label(wrap=True)
        self.translation_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.file_label = label(name="muted", wrap=True)
        for widget in (
            self.result_title,
            self.ipa_label,
            self.definition_label,
            self.translation_label,
            self.file_label,
        ):
            result_layout.addWidget(widget)
        self.meaning_list = ContentList()
        self.meaning_list.setWordWrap(True)
        self.meaning_list.setSpacing(4)
        self.meaning_list.hide()
        result_layout.insertWidget(2, self.meaning_list)
        self.audio_combo = ComboBox()
        self.audio_combo.hide()
        result_layout.insertWidget(3, self.audio_combo)
        self.save_button = QPushButton(self._t("Save meaning"))
        self.save_button.hide()
        player_row = QHBoxLayout()
        player_row.setSpacing(12)
        self.play_button = QPushButton()
        self.play_button.setMinimumWidth(100)
        self.recording_combo = ComboBox()
        player_row.addWidget(self.play_button)
        player_row.addWidget(self.accent_combo)
        player_row.addWidget(self.save_button)
        self.accent_label.hide()
        player_row.addWidget(self.recording_combo)
        player_row.addStretch()
        self.redownload_button = QPushButton()
        player_row.addWidget(self.redownload_button)
        result_layout.addLayout(player_row)
        result_layout.removeWidget(self.result_title)
        result_layout.removeWidget(self.ipa_label)
        result_header = QHBoxLayout()
        word_details = QVBoxLayout()
        word_details.addWidget(self.result_title)
        word_details.addWidget(self.ipa_label)
        result_header.addLayout(word_details, 1)
        result_header.addWidget(self.accent_combo)
        result_header.addWidget(self.play_button)
        result_layout.insertLayout(0, result_header)
        translation_actions = QHBoxLayout()
        self.edit_translation_button = QPushButton(self._t("Edit translation"))
        self.reset_translation_button = QPushButton(self._t("Reset translation"))
        self.select_translation_button = QPushButton(self._t("Find translation"))
        self.select_translation_button.hide()
        for button in (
            self.edit_translation_button,
            self.reset_translation_button,
            self.select_translation_button,
        ):
            translation_actions.addWidget(button)
        result_layout.insertLayout(
            result_layout.indexOf(self.translation_label) + 1, translation_actions
        )
        layout.addWidget(result)
        export_actions = QHBoxLayout()
        self.variant_button = QPushButton(self._t("Choose another pronunciation"))
        self.export_button = QPushButton(self._t("Export to Anki"))
        export_actions.addWidget(self.variant_button)
        export_actions.addWidget(self.export_button)
        layout.addLayout(export_actions)
        layout.addStretch()

    def _connect_ui(self):
        self.word_edit.returnPressed.connect(lambda: self.start_download(select_only=True))
        self.word_edit.textChanged.connect(self._input_changed)
        self.download_button.clicked.connect(lambda: self.start_download(select_only=True))
        self.choose_button.clicked.connect(self.choose_folder)
        self.open_button.clicked.connect(self.open_folder)
        self.refresh_button.clicked.connect(self.refresh_library)
        self.library_combo.currentIndexChanged.connect(self._library_selected)
        self.redownload_button.clicked.connect(self.redownload)
        self.play_button.clicked.connect(self.toggle_playback)
        self.recording_combo.currentIndexChanged.connect(self._recording_selected)
        self.settings_button.clicked.connect(self.open_settings)
        self.preferences_dialog.changed.connect(self._preferences_changed)
        self.preferences_dialog.about_requested.connect(self.show_about)
        self.accent_combo.currentIndexChanged.connect(self._accent_changed)
        self.translation_check.toggled.connect(self._translation_changed)
        self.dictionary_button.clicked.connect(self.install_wikdict)
        self.edit_translation_button.clicked.connect(self.edit_selected_translation)
        self.reset_translation_button.clicked.connect(self.reset_selected_translation)
        self.select_translation_button.clicked.connect(self.choose_translation_sense)
        self.export_button.clicked.connect(self.export_collection)
        self.variant_button.clicked.connect(lambda: self.start_download(choose_variant=True))
        self.meaning_list.currentRowChanged.connect(self._meaning_selected)
        self.audio_combo.currentIndexChanged.connect(self._show_choice)
        self.save_button.clicked.connect(self.save_choice)
        self.combine_check.toggled.connect(lambda value: self.settings.setValue("combine", value))

    def _retranslate(self):
        self.error_details_button.setText(self._t("Technical details"))
        self.error_details_text.setAccessibleName(self._t("Technical details"))
        self.subtitle.setText(self._t("Download and listen to English pronunciation."))
        self.settings_button.setToolTip(self._t("Settings"))
        self.settings_button.setAccessibleName(self._t("Settings"))
        self.preferences_dialog.retranslate(self.language)
        self.word_label.setText(self._t("Word or phrase"))
        self.word_edit.setPlaceholderText(self._t("For example: hello or good morning"))
        self.word_edit.setAccessibleName(self._t("Word or phrase"))
        self.clear_action.setText(self._t("Clear word"))
        self.accent_label.setText(self._t("Pronunciation"))
        self.accent_combo.setAccessibleName(self._t("Pronunciation"))
        self.folder_label.setText(self._t("Save to"))
        self.folder_edit.setAccessibleName(self._t("Save to"))
        self.choose_button.setText(self._t("Choose..."))
        self.open_button.setText(self._t("Open folder"))
        self.library_label.setText(self._t("Saved recordings"))
        self.library_combo.setAccessibleName(self._t("Saved recordings"))
        self.refresh_button.setText(self._t("Refresh"))
        self.redownload_button.setText(self._t("Download again"))
        if self.library_combo.count() == 1 and self.library_combo.currentData() is None:
            self.library_combo.setItemText(0, self._t("No saved recordings"))
        self.translation_check.setText(self._t("Show Russian translation"))
        self.dictionary_button.setToolTip(
            self._t(
                "WikDict is a free English–Russian dictionary.\n"
                "Install it for offline translations and as a fallback\n"
                "when Cambridge has no translation or is unavailable."
            )
        )
        self._update_dictionary_status()
        for button, title in (
            (self.dictionary_button, "Install WikDict"),
            (self.edit_translation_button, "Edit translation"),
            (self.reset_translation_button, "Reset translation"),
            (self.select_translation_button, "Find translation"),
            (self.variant_button, "Choose meaning"),
            (self.export_button, "Export to Anki"),
        ):
            button.setText(self._t(title))
        self.variant_button.setToolTip(
            self._t("Choose the English meaning of the word in Cambridge.")
        )
        self.select_translation_button.setToolTip(
            self._t("Choose which translation matches the selected English meaning.")
        )
        self.combine_check.setText(self._t("Combine words if the phrase has no recording"))
        self.combine_check.setToolTip(
            self._t("Combining requires FFmpeg. The result is not a recording of the whole phrase.")
        )
        set_choices(
            self.accent_combo,
            [
                (self._t(key), value)
                for key, value in (
                    ("American (US)", "us"),
                    ("British (UK)", "uk"),
                    ("Both", "both"),
                )
            ],
            self.accent,
        )
        self.recording_combo.setAccessibleName(self._t("Recording to play"))
        self.meaning_list.setAccessibleName(self._t("Choose meaning"))
        self.audio_combo.setAccessibleName(self._t("Other pronunciation"))
        self._refresh_recordings()
        if self._lookup_entries:
            self._show_choice()
        self._refresh_status()
        self._update_download_label()
        self._playback_changed()

    @Slot()
    def _preferences_changed(self):
        self.language = self._choice("language", {"en", "ru"}, "en")
        self.theme = self._choice("theme", {"system", "light", "dark"}, "system")
        self._retranslate()
        self._apply_theme()

    @Slot()
    def open_settings(self):
        self.preferences_dialog.show()
        self.preferences_dialog.raise_()
        self.preferences_dialog.activateWindow()

    @Slot()
    def show_about(self):
        repository = "https://github.com/0then0/cambridge-dictionary-audio"
        app_version = QApplication.instance().applicationVersion()
        link_color = self.palette().windowText().color().name()
        text = (
            f"<h3>{APPLICATION_NAME}</h3>"
            f"<p>{escape(self._t('Version {version}', version=app_version))}</p>"
            f"<p>{escape(self._t('Download and listen to English pronunciation.'))}</p>"
            f'<p><a href="{repository}" style="color: {link_color}">'
            f"{escape(self._t('Source code on GitHub'))}</a></p>"
            f"<p>{escape(self._t('Application code: Apache-2.0; inherited code: MIT.'))}</p>"
            "<p>"
            + escape(self._t("Dictionary content and recordings retain their own licenses."))
            + "</p>"
        )
        QMessageBox.about(self.preferences_dialog, self._t("About"), text)

    @Slot()
    def _accent_changed(self):
        self.accent = self.accent_combo.currentData()
        self.settings.setValue("accent", self.accent)
        if self._lookup_entries:
            self._meaning_selected()
        elif (record := self.selected_recording() or self._accent_record) and self.accent in {
            "us",
            "uk",
        }:
            if self._worker is None:
                saved = [
                    item
                    for item in scan_recordings(self.output_dir)
                    if item.recording.word == record.word
                    and item.recording.accent == self.accent
                    and (
                        item.recording.meaning_key == record.meaning_key
                        or (
                            item.recording.definition == record.definition
                            and item.recording.part_of_speech == record.part_of_speech
                        )
                    )
                ]
                if saved:
                    self._open_saved(saved)
                    self._status("Opened saved recording.")
                else:
                    self.player.stop()
                    self.player.setSource(QUrl())
                    self._accent_record = record
                    self.recordings.clear()
                    self.translations = ()
                    self._refresh_recordings()
                    self._launch_download(
                        DownloadRequest(
                            record.word,
                            self.output_dir,
                            self.accent,
                            self.language,
                            self.translation_check.isChecked(),
                            translation_language=self.translation_language,
                            dictionary_dir=self.dictionary_dir,
                            sense_id=record.source_sense_id or None,
                            select_only=not bool(record.source_sense_id),
                        )
                    )
        self._update_download_label()

    @Slot(bool)
    def _translation_changed(self, checked):
        self.settings.setValue("translation", checked)
        if checked and (record := self.selected_recording()):
            self._translation_errors.pop((record.reference, self.translation_language), None)
            self._translation_attempts.discard((record.reference, self.translation_language))
        if self._lookup_entries:
            self._show_choice()
        else:
            self._update_translation()

    def _update_translation(self):
        if self._lookup_entries:
            self._show_choice()
            return
        self.select_translation_button.hide()
        record = self.selected_recording()
        visible = self.translation_check.isChecked() and record is not None
        self.translation_label.setVisible(visible)
        if record is None:
            self._set_error_details("Translation", "")
            self.translations = ()
            self.translation_label.clear()
            return
        saved = read_recording(record.reference)
        if saved is None:
            self.translation_label.setText(
                self._t("The recording was moved or deleted. Download it again.")
            )
            return
        result = cached_translation(saved, self.translation_language)
        self.translations = result.texts if result else ()
        self.translation_label.setText(self._format_translation(result))
        if not visible:
            return
        key = (record.reference, self.translation_language)
        if result and (
            result.texts
            or key in self._translation_attempts
            or not package_path(self.dictionary_dir, PACKAGE).is_file()
        ):
            return
        elif key in self._translation_errors:
            raw = self._translation_errors[(record.reference, self.translation_language)]
            self._set_error_details("Translation", raw)
            self.translation_label.setText(
                friendly_error(raw, self.language, context="translation")
            )
        else:
            self.translation_label.setText(self._t("Loading translation..."))
            if self._translation_worker is None and self._worker is None and not self._closing:
                self._translation_attempts.add(key)
                worker = TranslationWorker(saved, self.language, self)
                self._translation_worker = worker
                worker.completed.connect(self._translation_completed)
                worker.finished.connect(self._translation_finished)
                worker.finished.connect(worker.deleteLater)
                worker.start()

    @Slot(object, object, str)
    def _translation_completed(self, saved, translations, error):
        language = (
            self._translation_worker.target_language
            if self._translation_worker
            else self.translation_language
        )
        record = saved.recording
        result = translations if isinstance(translations, TranslationResult) else None
        if error or result is None or not result.options:
            self._translation_errors[(record.reference, language)] = (
                self._t("Translation: {error}", error=error or (result.error if result else ""))
                if error or (result and result.error)
                else self._t("No translation found. Toggle off and on to retry.")
            )
        else:
            try:
                for item in scan_recordings(record.path.parent):
                    if (
                        item.recording.word == record.word
                        and item.recording.sense_id == record.sense_id
                    ):
                        persist_translation(item, result)
            except OSError as exc:
                self._translation_errors[(record.reference, language)] = str(exc)
        self._update_translation()

    def _selected_saved(self):
        if self._lookup_entries and (choice := self._current_choice()):
            return next(
                (
                    s
                    for s in scan_recordings(self.output_dir)
                    if s.recording.source_sense_id == choice.entry.sense_id
                    and s.recording.audio_url == choice.pronunciation.url
                ),
                None,
            )
        record = self.selected_recording()
        return read_recording(record.reference) if record else None

    def edit_selected_translation(self):
        if self._worker is not None:
            return
        saved = self._selected_saved()
        choice = self._current_choice() if self._lookup_entries else None
        if not saved and not choice:
            return
        result = (
            cached_translation(saved, self.translation_language)
            if saved
            else self._preview_translations.get(choice.entry.sense_id)
        )
        text, accepted = QInputDialog.getMultiLineText(
            self,
            self._t("Edit translation"),
            self._t("Translation"),
            "\n".join(result.texts) if result else "",
        )
        if accepted:
            try:
                if saved:
                    edit_translation(saved, self.translation_language, text)
                elif text.strip():
                    from ..dictionary import stable_id
                    from ..translations import TranslationOption

                    self._preview_translations[choice.entry.sense_id] = TranslationResult(
                        self.translation_language,
                        choice.entry.sense_id,
                        "User",
                        (TranslationOption(stable_id(text), (text.strip(),), matched=True),),
                    )
                self._update_translation()
            except (OSError, ValueError) as exc:
                self._status("Error: {error}", severity="error", error=exc)

    def reset_selected_translation(self):
        if self._worker is not None:
            return
        saved = self._selected_saved()
        if not saved and self._lookup_entries and (choice := self._current_choice()):
            self._preview_translations.pop(choice.entry.sense_id, None)
            self._show_choice()
        if saved:
            try:
                edit_translation(saved, self.translation_language, None)
                self._update_translation()
            except OSError as exc:
                self._status("Error: {error}", severity="error", error=exc)

    def choose_translation_sense(self):
        if self._worker is not None:
            return
        saved = self._selected_saved()
        choice = self._current_choice() if self._lookup_entries else None
        result = (
            cached_translation(saved, self.translation_language)
            if saved
            else self._preview_translations.get(choice.entry.sense_id)
            if choice
            else None
        )
        if not result or not result.options:
            return
        options = [o.label_for(self.language) for o in result.options]
        dialog = ChoiceDialog(
            self,
            self._t("Find translation"),
            self._t("Choose which translation matches the selected English meaning."),
            options,
        )
        dialog.setOkButtonText(self._t("OK"))
        dialog.setCancelButtonText(self._t("Cancel"))
        if dialog.exec() == ChoiceDialog.DialogCode.Accepted:
            text = dialog.textValue()
            try:
                option_id = result.options[options.index(text)].id
                if saved:
                    select_translation(saved, self.translation_language, option_id)
                else:
                    self._preview_translations[choice.entry.sense_id] = replace(
                        result, selected_id=option_id
                    )
                self._update_translation()
            except (OSError, ValueError) as exc:
                self._status("Error: {error}", severity="error", error=exc)

    def _update_dictionary_status(self):
        details = ""
        try:
            validate_package(package_path(self.dictionary_dir, PACKAGE), PACKAGE)
        except DictionaryMissing:
            message = "Offline dictionary: not installed."
        except DictionaryCorrupt as exc:
            message = "Offline dictionary: damaged."
            details = exc
        except OSError as exc:
            message = "Offline dictionary: unavailable."
            details = exc
        else:
            message = "Offline dictionary: ready."
        self._set_error_details("Offline dictionary", details)
        self.dictionary_status_label.setText(self._t(message))

    def install_wikdict(self):
        if self._dictionary_worker or self._closing:
            return
        title = self._t("Install WikDict")
        try:
            validate_package(package_path(self.dictionary_dir, PACKAGE), PACKAGE)
        except DictionaryMissing:
            self.dictionary_status_label.setText(self._t("Offline dictionary: not installed."))
            message = self._t("Install the English–Russian WikDict package?")
        except DictionaryCorrupt:
            self.dictionary_status_label.setText(self._t("Offline dictionary: damaged."))
            title = self._t("Reinstall WikDict")
            message = self._t("The installed WikDict package is damaged. Download it again?")
        except OSError as exc:
            self.dictionary_status_label.setText(self._t("Offline dictionary: unavailable."))
            self._status("Error: {error}", severity="error", error=exc)
            return
        else:
            self.dictionary_status_label.setText(self._t("Offline dictionary: ready."))
            title = self._t("Reinstall WikDict")
            message = self._t("WikDict is already installed and verified. Download it again?")
        if (
            QMessageBox.question(
                self,
                title,
                message + "\n\n" + PACKAGE.describe(self.language) + "\n" + PACKAGE.license_url,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        worker = DictionaryWorker(self.dictionary_dir, self)
        self._dictionary_worker = worker
        self.dictionary_button.setEnabled(False)
        worker.progress.connect(
            lambda done, total: self._status(
                "WikDict: {done} / {total} bytes", done=done, total=total
            )
        )
        worker.completed.connect(lambda path: self._status("WikDict installed: {path}", path=path))
        worker.failed.connect(
            lambda error: self._status("Error: {error}", severity="error", error=error)
        )
        worker.finished.connect(self._dictionary_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _dictionary_finished(self):
        if self._dictionary_worker:
            self._dictionary_worker.wait()
        self._dictionary_worker = None
        self.dictionary_button.setEnabled(True)
        self._update_dictionary_status()
        self._translation_errors.clear()
        self._translation_attempts.clear()
        if self._closing:
            if self._worker is None and self._translation_worker is None:
                self.close()
                QApplication.instance().quit()
        else:
            self._update_translation()

    def export_collection(self):
        choices = [self._t("Selected recording"), self._t("Whole collection")]
        dialog = ChoiceDialog(self, self._t("Export to Anki"), self._t("Export"), choices)
        dialog.setOkButtonText(self._t("Export"))
        dialog.setCancelButtonText(self._t("Cancel"))
        if dialog.exec() != ChoiceDialog.DialogCode.Accepted:
            return
        scope = dialog.textValue()
        records = (
            [self._selected_saved()] if scope == choices[0] else scan_recordings(self.output_dir)
        )
        if not records or not all(records):
            self._status("No recordings selected for export.", severity="error")
            return
        path, chosen_filter = QFileDialog.getSaveFileName(
            self,
            self._t("Export to Anki"),
            str(self.output_dir / "cambridge-anki.apkg"),
            "Anki (*.apkg);;TSV (*.tsv)",
        )
        if not path:
            return
        try:
            if chosen_filter.startswith("TSV"):
                output = export_anki(
                    records, Path(path).with_suffix(""), language=self.translation_language
                )
            else:
                output = export_apkg(records, Path(path), language=self.translation_language)
            self._status("Anki export saved: {path}", path=output)
        except (OSError, ValueError) as exc:
            self._status("Export: {error}", severity="error", error=exc)

    def _translation_finished(self):
        if self._translation_worker is not None:
            self._translation_worker.wait()
        self._translation_worker = None
        if self._closing:
            if self._worker is None and self._dictionary_worker is None:
                self.close()
                QApplication.instance().quit()
        else:
            if self._lookup_entries:
                self._show_choice()
            else:
                self._update_translation()

    def _apply_theme(self, *, update_scheme=True):
        custom = stored_colors(self.settings)
        self.effective_theme = apply_theme(
            QApplication.instance(), self.theme, custom_colors=custom, update_scheme=update_scheme
        )
        colors = theme_colors(self.effective_theme, custom[self.effective_theme])
        self.clear_action.setIcon(themed_icon("clear", colors["muted"]))
        self.settings_button.setIcon(themed_icon("settings", colors["muted"]))
        self.preferences_dialog.update_colors(self.effective_theme)

    @Slot()
    def _system_theme_changed(self):
        self._apply_theme(update_scheme=False)

    def _refresh_status(self):
        message = self._t(self._status_message, **self._status_values)
        if self._status_severity == "error":
            raw = self._status_values.get("error", self._status_message)
            context = next(
                (
                    context
                    for marker, context in (
                        ("Details could not", "metadata"),
                        ("Translation", "translation"),
                        ("read saved", "library"),
                        ("Playback", "playback"),
                        ("Export", "export"),
                    )
                    if marker in self._status_message
                ),
                "operation",
            )
            message = friendly_error(raw, self.language, context=context)
        self.status_label.setText(message)
        self.status_label.setProperty("severity", self._status_severity)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _status(self, message, *, severity="", **values):
        self._status_message, self._status_values, self._status_severity = message, values, severity
        raw = values.get("error", self._t(message, **values)) if severity == "error" else ""
        self._set_error_details("Operation", raw)
        self._refresh_status()

    def _set_error_details(self, section, error):
        details = diagnostic_details(error) if error else ""
        previous = self._error_details.copy()
        if details:
            self._error_details[section] = details
        else:
            self._error_details.pop(section, None)
        if previous != self._error_details:
            self.error_details_button.setChecked(False)
            self.error_details_text.hide()
        summaries = [
            self._t(key)
            + ": "
            + friendly_error(
                value, self.language, context="translation" if key == "Translation" else "operation"
            )
            for key, value in self._error_details.items()
            if key != "Operation"
        ]
        self.error_summary_label.setText("\n".join(summaries))
        self.error_summary_label.setVisible(bool(summaries))
        self.error_details_button.setVisible(bool(self._error_details))
        self.error_details_text.setPlainText(
            "\n\n".join(self._t(key) + "\n" + value for key, value in self._error_details.items())
        )

    def _format_translation(self, result):
        self.select_translation_button.setVisible(
            bool(
                self.translation_check.isChecked()
                and result
                and result.options
                and not result.texts
            )
        )
        self._set_error_details(
            "Translation", result.error if result and self.translation_check.isChecked() else ""
        )
        if result and result.error:
            result = replace(
                result, error=friendly_error(result.error, self.language, context="translation")
            )
        return result.format(self.language, show_ids=False) if result else ""

    @Slot()
    def _input_changed(self):
        self.clear_action.setVisible(bool(self.word_edit.text()))
        self.download_button.setEnabled(
            bool(self.word_edit.text().strip()) and self._worker is None
        )
        self._update_download_label()

    def _update_download_label(self):
        existing = False
        try:
            word = normalize_word(self.word_edit.text(), self.language)
            accents = ("us", "uk") if self.accent == "both" else (self.accent,)
            existing = all((self.output_dir / audio_filename(word, a)).is_file() for a in accents)
        except ValueError:
            pass
        self.download_button.setText(
            self._t("Downloading..." if self._worker else "Open saved" if existing else "Find")
        )

    def _set_busy(self, busy):
        for widget in (
            self.word_edit,
            self.accent_combo,
            self.choose_button,
            self.preferences_dialog.language_combo,
            self.library_combo,
            self.refresh_button,
            self.meaning_list,
            self.audio_combo,
        ):
            widget.setEnabled(not busy)
        self.combine_check.setEnabled(not busy and bool(ffmpeg_executable()))
        self.progress.setVisible(busy)
        self._update_download_label()
        self.download_button.setEnabled(not busy and bool(self.word_edit.text().strip()))
        self.save_button.setEnabled(not busy)
        self.play_button.setEnabled(not busy and bool(self.recordings or self._current_choice()))
        self.redownload_button.setEnabled(not busy and bool(self.recordings))
        self.library_combo.setEnabled(not busy and bool(self.library_combo.currentData()))

    @Slot()
    def start_download(self, *, force=False, choose_variant=False, select_only=False):
        if self._worker is not None:
            return
        if choose_variant and not self.word_edit.text().strip() and self.selected_recording():
            self.word_edit.setText(self.selected_recording().word)
        try:
            word = normalize_word(self.word_edit.text(), self.language)
        except ValueError as exc:
            self._status("Error: {error}", severity="error", error=exc)
            self.word_edit.setFocus()
            return
        accents = ("us", "uk") if self.accent == "both" else (self.accent,)
        target = self.selected_recording() if force else None
        existing = [self.output_dir / audio_filename(word, accent) for accent in accents]
        existing = [path for path in existing if path.is_file()]
        saved = [item for path in existing if (item := read_recording(path))]
        # Empty files are not cache hits, but replacing them still requires consent.
        force = force or len(saved) != len(existing)
        if not force and not choose_variant:
            saved = [
                item
                for item in scan_recordings(self.output_dir)
                if item.recording.word == word and item.recording.accent in accents
            ]
            existing = [item.recording.path for item in saved]
        if saved and not force and not choose_variant:
            self._open_saved(saved)
            if all(a in {s.recording.accent for s in saved} for a in accents):
                self._status("Opened saved recording.")
                return
        if target:
            existing = [target.path]
        missing = [a for a in accents if a not in {s.recording.accent for s in saved}]
        overwrite = False
        if existing and force:
            confirmation = QMessageBox(self)
            confirmation.setIcon(QMessageBox.Icon.Question)
            confirmation.setWindowTitle(self._t("Replace recordings?"))
            confirmation.setTextFormat(Qt.TextFormat.PlainText)
            message = (
                "The recording already exists:\n{files}\n\nReplace it?"
                if len(existing) == 1
                else "These files already exist:\n{files}\n\nReplace them?"
            )
            confirmation.setText(self._t(message, files="\n".join(p.name for p in existing)))
            confirmation.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            confirmation.button(QMessageBox.StandardButton.Yes).setText(self._t("Replace"))
            confirmation.button(QMessageBox.StandardButton.No).setText(self._t("Keep existing"))
            confirmation.setDefaultButton(QMessageBox.StandardButton.No)
            answer = confirmation.exec()
            if answer != QMessageBox.StandardButton.Yes:
                return
            overwrite = True
        self._clear_lookup()
        self._accent_record = None
        self.player.stop()
        self.player.setSource(QUrl())
        if force or not saved:
            self.recordings.clear()
            self.translations = ()
        self._refresh_recordings()
        request = DownloadRequest(
            word,
            self.output_dir,
            self.accent if force or len(missing) != 1 else missing[0],
            self.language,
            self.translation_check.isChecked(),
            self.combine_check.isChecked(),
            overwrite,
            target=target,
            translation_language=self.translation_language,
            dictionary_dir=self.dictionary_dir,
            select_only=not force and (select_only or choose_variant),
        )
        self._launch_download(request)

    def _launch_download(self, request):
        worker = DownloadWorker(request, self)
        self._worker = worker
        self._selection_word = request.word
        worker.recording.connect(self._on_recording)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.selection.connect(self._selection_required)
        worker.previewed.connect(self._play_preview)
        worker.finished.connect(self._finished)
        worker.finished.connect(worker.deleteLater)
        self._set_busy(True)
        self._status("Downloading...")
        worker.start()

    def _selection_required(self, selection):
        self._pending_selection = selection

    def _choose_variant(self, selection):
        self._lookup_target = getattr(selection, "target", None)
        self._lookup_entries = selection.entries
        self._rendering_choices = True
        self.meaning_list.clear()
        grouped = {}
        for entry in selection.entries:
            if entry.pronunciations:
                grouped.setdefault(entry.part_of_speech, []).append(entry)
        self._meanings = []
        first = -1
        for part, entries in grouped.items():
            heading = QListWidgetItem(self._t(part) or self._t("Meaning"))
            heading.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.meaning_list.addItem(heading)
            category = label(heading.text(), name="meaning-category")
            self.meaning_list.setItemWidget(heading, category)
            category.ensurePolished()
            heading.setSizeHint(category.sizeHint())
            for entry in entries:
                if any(e.sense_id == entry.sense_id for e in self._meanings):
                    continue
                self._meanings.append(entry)
                item = QListWidgetItem(entry.definition)
                item.setToolTip(entry.definition)
                item.setData(Qt.ItemDataRole.UserRole, entry)
                self.meaning_list.addItem(item)
                if first < 0:
                    first = self.meaning_list.count() - 1
        self._rendering_choices = False
        self.meaning_list.setVisible(True)
        self.save_button.setVisible(True)
        self.meaning_list.setCurrentRow(first)
        self._meaning_selected()
        self._status("Choose a meaning, listen, then save.")

    def _meaning_selected(self, *args):
        if self._rendering_choices:
            return
        item = self.meaning_list.currentItem()
        entry = item.data(Qt.ItemDataRole.UserRole) if item else None
        if entry is None:
            return
        accent = "us" if self.accent == "both" else self.accent
        choices = variants((entry,), accent)
        self._audio_choices = choices
        set_choices(
            self.audio_combo,
            [
                (f"{self._t('Other pronunciation')} {i + 1} · /{v.pronunciation.ipa}/", v.id)
                for i, v in enumerate(choices)
            ],
            "",
        )
        self.audio_combo.setVisible(len(choices) > 1)
        self._show_choice()

    def _current_choice(self):
        return next(
            (
                v
                for v in getattr(self, "_audio_choices", ())
                if v.id == self.audio_combo.currentData()
            ),
            None,
        )

    def _show_choice(self, *args):
        self.select_translation_button.hide()
        choice = self._current_choice()
        if not choice:
            self._set_error_details("Translation", "")
            self.save_button.setEnabled(False)
            self.play_button.setEnabled(False)
            return
        entry, audio = choice.entry, choice.pronunciation
        self.result_title.setText(entry.word)
        self.ipa_label.setText(f"{audio.accent.upper()} /{audio.ipa}/")
        self.ipa_label.show()
        self.definition_label.setText(entry.definition)
        self.file_label.hide()
        existing = next(
            (
                s
                for s in scan_recordings(self.output_dir)
                if (
                    s.recording.source_sense_id == entry.sense_id
                    or s.recording.variant_id in entry.legacy_ids
                )
                and s.recording.audio_url == audio.url
            ),
            None,
        )
        self.save_button.setText(self._t("Already saved" if existing else "Save meaning"))
        self.save_button.setEnabled(self._worker is None)
        self.play_button.setEnabled(self._worker is None)
        self.redownload_button.setEnabled(False)
        self.translation_label.setText("")
        self._set_error_details("Translation", "")
        self.translation_label.setVisible(self.translation_check.isChecked())
        self.edit_translation_button.setEnabled(self._worker is None)
        self.select_translation_button.setEnabled(self._worker is None)
        result = cached_translation(existing, self.translation_language) if existing else None
        result = result or self._preview_translations.get(entry.sense_id)
        self.reset_translation_button.setEnabled(self._worker is None and bool(existing or result))
        if result:
            self.translation_label.setText(self._format_translation(result))
            item = self.meaning_list.currentItem()
            if item:
                item.setText(
                    entry.definition + ("\n" + "; ".join(result.texts) if result.texts else "")
                )
        elif self.translation_check.isChecked() and self._translation_worker is None:
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
            self.translation_label.setText(self._t("Loading translation..."))
            worker = TranslationWorker(SavedRecording(preview), self.language, self)
            self._translation_worker = worker
            worker.completed.connect(self._preview_translation_completed)
            worker.finished.connect(self._translation_finished)
            worker.finished.connect(worker.deleteLater)
            worker.start()

    def _preview_translation_completed(self, saved, result, error):
        if error and not isinstance(result, TranslationResult):
            result = TranslationResult(
                self.translation_language,
                saved.recording.sense_id,
                "Cambridge",
                error=error,
                status="error",
            )
        if isinstance(result, TranslationResult):
            current = self._preview_translations.get(saved.recording.sense_id)
            if not current or (current.source != "User" and not current.selected_id):
                self._preview_translations[saved.recording.sense_id] = result

    def save_choice(self):
        choice = self._current_choice()
        if choice and self._worker is None:
            self._launch_download(
                DownloadRequest(
                    self._selection_word,
                    self.output_dir,
                    choice.pronunciation.accent,
                    self.language,
                    self.translation_check.isChecked(),
                    variant_id=choice.id,
                    entries=self._lookup_entries,
                    prepared_translation=self._preview_translations.get(choice.entry.sense_id),
                    target=getattr(self, "_lookup_target", None),
                    preview_dir=Path(self._preview_cache.name),
                    dictionary_dir=self.dictionary_dir,
                )
            )

    def _play_preview(self, path):
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()

    @Slot(object)
    def _on_recording(self, recording: Recording):
        self.recordings = [r for r in self.recordings if r.id != recording.id]
        self.recordings.append(recording)
        self._refresh_recordings(selected=len(self.recordings) - 1)

    @Slot(object)
    def _on_completed(self, result: DownloadResult):
        if self._worker.request.variant_id and result.recordings:
            self._clear_lookup()
        self.translations = result.translations or self.translations
        self._refresh_recordings()
        self.refresh_library(select=False)
        if self._worker.metadata_error:
            self._status(
                "Audio saved. Details could not be saved: {error}",
                severity="error",
                error=self._worker.metadata_error,
            )
        elif result.translation_error:
            language = self._worker.request.translation_language
            for record in result.recordings:
                self._translation_errors[(record.reference, language)] = self._t(
                    "Translation: {error}", error=result.translation_error
                )
            self._status(
                "Audio saved. Translation unavailable: {error}",
                severity="error",
                error=result.translation_error,
            )
        else:
            self._status(
                "Recording saved." if len(result.recordings) == 1 else "Both recordings saved."
            )

    @Slot(str)
    def _on_failed(self, error):
        self.refresh_library(select=False)
        self._status("Error: {error}", severity="error", error=error)

    @Slot()
    def _finished(self):
        if self._worker is not None:
            self._worker.wait()
        self._worker = None
        self._set_busy(False)
        if self._pending_selection is not None and not self._closing:
            selection, self._pending_selection = self._pending_selection, None
            self._choose_variant(selection)
            return
        if self._closing:
            if self._translation_worker is None and self._dictionary_worker is None:
                self.close()
                QApplication.instance().quit()
        else:
            if self._lookup_entries:
                self._show_choice()
            else:
                self._update_translation()
            self.word_edit.setFocus()
            self.word_edit.selectAll()

    def _refresh_recordings(self, selected=None):
        if selected is None:
            selected = max(0, self.recording_combo.currentIndex())
        choices = [
            (
                record.label
                if record.part_of_speech
                or sum(r.accent == record.accent for r in self.recordings) > 1
                else self._t("American (US)" if record.accent == "us" else "British (UK)"),
                str(i),
            )
            for i, record in enumerate(self.recordings)
        ]
        set_choices(self.recording_combo, choices, str(selected))
        self.recording_combo.setVisible(len(self.recordings) > 1)
        self._recording_selected()

    @Slot()
    def _recording_selected(self):
        record = self.selected_recording()
        if hasattr(self, "player") and (
            record is None or self.player.source() != QUrl.fromLocalFile(str(record.path.resolve()))
        ):
            self.player.stop()
        self.result_title.setText(record.word if record else self._t("No recording yet"))
        self.ipa_label.setText(
            self._t("Combined from individual words")
            if record and record.combined
            else f"{record.accent.upper()}" + (f" /{record.ipa}/" if record.ipa else "")
            if record
            else ""
        )
        self.ipa_label.setVisible(record is not None)
        self.definition_label.setText(
            (f"{record.part_of_speech} · " if record.part_of_speech else "") + record.definition
            or self._t("Details are unavailable for this saved recording.")
            if record
            else self._t("Download a word or phrase to listen to it here.")
        )
        self._update_translation()
        self.file_label.setText(self._t("Already saved") if record else "")
        self.file_label.setToolTip(str(record.path) if record else "")
        self.file_label.setVisible(record is not None)
        self.play_button.setEnabled(record is not None and self._worker is None)
        self.redownload_button.setEnabled(record is not None and self._worker is None)
        if record is not None:
            self._accent_record = record
            if self.accent != "both":
                self.accent_combo.blockSignals(True)
                self.accent_combo.setCurrentIndex(self.accent_combo.findData(record.accent))
                self.accent_combo.blockSignals(False)
                self.accent = record.accent
                self.settings.setValue("accent", self.accent)
            index = self.library_combo.findData(str(record.reference))
            if index >= 0:
                self.library_combo.blockSignals(True)
                self.library_combo.setCurrentIndex(index)
                self.library_combo.blockSignals(False)

    def _clear_lookup(self):
        self._lookup_entries = ()
        self._audio_choices = ()
        self._pending_selection = None
        self.meaning_list.clear()
        self.meaning_list.hide()
        self.audio_combo.hide()
        self.save_button.hide()

    def _open_saved(self, saved):
        self._clear_lookup()
        self._accent_record = None
        self.player.stop()
        self.recordings = [item.recording for item in saved]
        self.translations = next(
            (
                item.translations
                for item in saved
                if item.translations and item.translation_language == self.translation_language
            ),
            (),
        )
        self._refresh_recordings(selected=0)

    def refresh_library(self, *, select=True):
        previous = self.library_combo.currentData()
        if not select and (record := self.selected_recording()) is not None:
            previous = str(record.reference)
        try:
            self._library = scan_recordings(self.output_dir)
        except OSError as exc:
            self._library = []
            self._status("Could not read saved recordings: {error}", severity="error", error=exc)
        self.library_combo.blockSignals(True)
        self.library_combo.clear()
        for item in self._library:
            record = item.recording
            self.library_combo.addItem(record.label, str(record.reference))
        if not self._library:
            self.library_combo.addItem(self._t("No saved recordings"), None)
        index = self.library_combo.findData(previous) if previous else 0
        self.library_combo.setCurrentIndex(max(0, index))
        self.library_combo.blockSignals(False)
        self.library_combo.setEnabled(bool(self._library) and self._worker is None)
        if select:
            self._library_selected()
        self._update_download_label()

    @Slot()
    def _library_selected(self):
        path = self.library_combo.currentData()
        saved = read_recording(Path(path)) if path else None
        self._open_saved([saved] if saved else [])
        if saved:
            self._status("Opened saved recording.")

    @Slot()
    def redownload(self):
        record = self.selected_recording()
        if record is not None:
            self.word_edit.setText(record.word)
            self.accent_combo.blockSignals(True)
            self.accent_combo.setCurrentIndex(self.accent_combo.findData(record.accent))
            self.accent_combo.blockSignals(False)
            self.accent = record.accent
            self.start_download(force=True)

    def selected_recording(self) -> Recording | None:
        index = self.recording_combo.currentIndex()
        return self.recordings[index] if 0 <= index < len(self.recordings) else None

    @Slot()
    def toggle_playback(self):
        if self.meaning_list.isVisible() and self._current_choice() and self._worker is None:
            if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self.player.stop()
            else:
                self._launch_download(
                    DownloadRequest(
                        self._selection_word,
                        self.output_dir,
                        self._current_choice().pronunciation.accent,
                        self.language,
                        preview_choice=self._current_choice(),
                        preview_dir=Path(self._preview_cache.name),
                    )
                )
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
            return
        record = self.selected_recording()
        if record is None:
            return
        if not record.path.is_file():
            self._status("The recording was moved or deleted. Download it again.", severity="error")
            return
        device = QMediaDevices.defaultAudioOutput()
        if device.isNull():
            self._status(
                "Audio output is unavailable. Check your system sound settings.",
                severity="error",
            )
            return
        self.audio_output.setDevice(device)
        if self._status_message in {
            "Audio output is unavailable. Check your system sound settings.",
            "The recording was moved or deleted. Download it again.",
        }:
            self._status("Recording saved.")
        self.player.setSource(QUrl.fromLocalFile(str(record.path.resolve())))
        self.player.play()

    @Slot()
    def _playback_changed(self):
        playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.play_button.setText(self._t("Stop" if playing else "Play"))

    def _playback_error(self, error, message):
        if error != QMediaPlayer.Error.NoError:
            self._status("Playback: {error}", severity="error", error=message)

    @Slot()
    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, self._t("Choose a download folder"), str(self.output_dir)
        )
        if path:
            self.output_dir = Path(path)
            self.folder_edit.setText(path)
            self.folder_edit.setCursorPosition(0)
            self.settings.setValue("output_dir", path)
            self.refresh_library()

    @Slot()
    def open_folder(self):
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_dir.resolve()))):
                self._status("Could not open the folder.", severity="error")
        except OSError as exc:
            self._status("Error: {error}", severity="error", error=exc)

    @Slot()
    def shutdown(self):
        """Also protect active workers when the OS menu quits the whole application."""
        self.preferences_dialog.hide()
        self.player.stop()
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.sync()
        self.hide()
        for worker in (self._worker, self._translation_worker, self._dictionary_worker):
            if worker is not None and worker.isRunning():
                worker.requestInterruption()
                worker.wait()

    def closeEvent(self, event):
        self.preferences_dialog.hide()
        self.player.stop()
        self.settings.setValue("window/geometry", self.saveGeometry())
        self.settings.sync()
        workers = [
            w
            for w in (self._worker, self._translation_worker, self._dictionary_worker)
            if w is not None and w.isRunning()
        ]
        if workers:
            QApplication.instance().setQuitOnLastWindowClosed(False)
            self._closing = True
            for worker in workers:
                worker.requestInterruption()
            self.hide()
            event.ignore()
            return
        event.accept()


def create_application(argv: list[str] | None = None) -> QApplication:
    QApplication.setApplicationName(APPLICATION_NAME)
    QApplication.setOrganizationName("CambridgeDictionaryAudio")
    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationDisplayName(APPLICATION_NAME)
    app.setApplicationVersion(version("cambridge-dictionary-audio"))
    app.setDesktopFileName("cambridge-dictionary-audio")
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parents[2] / "assets" / "icon.svg")))
    app.setStyle("Fusion")
    font = app.font()
    font.setPixelSize(14)
    app.setFont(font)
    return app


def main() -> int:
    QApplication.setApplicationName(APPLICATION_NAME)
    QApplication.setOrganizationName("CambridgeDictionaryAudio")
    if sys.platform == "darwin":
        result = launch_macos_bundle(
            Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation))
        )
        if result is not None:
            return result
    app = create_application()
    window = MainWindow()
    window.show()
    return app.exec()

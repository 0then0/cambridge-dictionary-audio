"""Small desktop interface. Run with: uv run --group gui -m cambridge_audio.gui."""

import sys
from html import escape
from importlib.metadata import version
from pathlib import Path

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
        QListView,
        QMainWindow,
        QMessageBox,
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

from ..anki import export_anki
from ..audio import ffmpeg_executable
from ..desktop import APPLICATION_NAME, launch_macos_bundle
from ..dictionary import (
    audio_filename,
    normalize_word,
)
from ..i18n import translate
from ..library import read_recording, scan_recordings
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
from .preferences import PreferencesDialog
from .theme import (
    ComboBox,
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
        self.translations: tuple[str, ...] = ()
        self._worker: DownloadWorker | None = None
        self._translation_worker: TranslationWorker | None = None
        self._translation_errors: dict[tuple[Path, str], str] = {}
        self._closing = False
        self._dictionary_worker = None
        self._pending_selection = None
        self.translation_language = "russian"
        self.dictionary_dir = None
        self._status_message = "Ready to download."
        self._status_values = {}
        self._status_severity = ""
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
        player_row = QHBoxLayout()
        player_row.setSpacing(12)
        self.play_button = QPushButton()
        self.play_button.setMinimumWidth(100)
        self.recording_combo = ComboBox()
        player_row.addWidget(self.play_button)
        player_row.addWidget(self.recording_combo)
        player_row.addStretch()
        self.redownload_button = QPushButton()
        player_row.addWidget(self.redownload_button)
        result_layout.addLayout(player_row)
        translation_actions = QHBoxLayout()
        self.edit_translation_button = QPushButton(self._t("Edit translation"))
        self.reset_translation_button = QPushButton(self._t("Reset translation"))
        self.select_translation_button = QPushButton(self._t("Choose translation sense"))
        for button in (
            self.edit_translation_button,
            self.reset_translation_button,
            self.select_translation_button,
        ):
            translation_actions.addWidget(button)
        result_layout.addLayout(translation_actions)
        layout.addWidget(result)
        export_actions = QHBoxLayout()
        self.variant_button = QPushButton(self._t("Choose another pronunciation"))
        self.export_button = QPushButton(self._t("Export to Anki"))
        export_actions.addWidget(self.variant_button)
        export_actions.addWidget(self.export_button)
        layout.addLayout(export_actions)
        layout.addStretch()

    def _connect_ui(self):
        self.word_edit.returnPressed.connect(self.start_download)
        self.word_edit.textChanged.connect(self._input_changed)
        self.download_button.clicked.connect(self.start_download)
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
        self.combine_check.toggled.connect(lambda value: self.settings.setValue("combine", value))

    def _retranslate(self):
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
            (self.select_translation_button, "Choose translation sense"),
            (self.variant_button, "Choose another pronunciation"),
            (self.export_button, "Export to Anki"),
        ):
            button.setText(self._t(title))
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
        self._refresh_recordings()
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
        self._update_download_label()

    @Slot(bool)
    def _translation_changed(self, checked):
        self.settings.setValue("translation", checked)
        if checked and (record := self.selected_recording()):
            self._translation_errors.pop((record.path, self.translation_language), None)
        self._update_translation()

    def _update_translation(self):
        record = self.selected_recording()
        visible = self.translation_check.isChecked() and record is not None
        self.translation_label.setVisible(visible)
        if record is None:
            self.translations = ()
            self.translation_label.clear()
            return
        saved = read_recording(record.path)
        if saved is None:
            self.translation_label.setText(
                self._t("The recording was moved or deleted. Download it again.")
            )
            return
        result = cached_translation(saved, self.translation_language)
        self.translations = result.texts if result else ()
        self.translation_label.setText(
            result.format(self.language, show_ids=False) if result else ""
        )
        if not visible:
            return
        if result:
            return
        elif (record.path, self.translation_language) in self._translation_errors:
            self.translation_label.setText(
                self._translation_errors[(record.path, self.translation_language)]
            )
        else:
            self.translation_label.setText(self._t("Loading translation..."))
            if self._translation_worker is None and self._worker is None and not self._closing:
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
            self._translation_errors[(record.path, language)] = (
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
                self._translation_errors[(record.path, language)] = str(exc)
        self._update_translation()

    def _selected_saved(self):
        record = self.selected_recording()
        return read_recording(record.path) if record else None

    def edit_selected_translation(self):
        saved = self._selected_saved()
        if not saved:
            return
        result = cached_translation(saved, self.translation_language)
        text, accepted = QInputDialog.getMultiLineText(
            self,
            self._t("Edit translation"),
            self._t("Translation"),
            "\n".join(result.texts) if result else "",
        )
        if accepted:
            try:
                edit_translation(saved, self.translation_language, text)
                self._update_translation()
            except (OSError, ValueError) as exc:
                self._status("Error: {error}", severity="error", error=str(exc))

    def reset_selected_translation(self):
        saved = self._selected_saved()
        if saved:
            try:
                edit_translation(saved, self.translation_language, None)
                self._update_translation()
            except OSError as exc:
                self._status("Error: {error}", severity="error", error=str(exc))

    def choose_translation_sense(self):
        saved = self._selected_saved()
        result = cached_translation(saved, self.translation_language) if saved else None
        if not result or not result.options:
            return
        options = [o.label_for(self.language) for o in result.options]
        text, accepted = QInputDialog.getItem(
            self, self._t("Choose translation sense"), self._t("Source senses"), options, 0, False
        )
        if accepted:
            try:
                select_translation(
                    saved, self.translation_language, result.options[options.index(text)].id
                )
                self._update_translation()
            except (OSError, ValueError) as exc:
                self._status("Error: {error}", severity="error", error=str(exc))

    def _update_dictionary_status(self):
        try:
            validate_package(package_path(self.dictionary_dir, PACKAGE), PACKAGE)
        except DictionaryMissing:
            message = "Offline dictionary: not installed."
        except DictionaryCorrupt:
            message = "Offline dictionary: damaged."
        except OSError:
            message = "Offline dictionary: unavailable."
        else:
            message = "Offline dictionary: ready."
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
            self._status("Error: {error}", severity="error", error=str(exc))
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
        if self._closing:
            if self._worker is None and self._translation_worker is None:
                self.close()
                QApplication.instance().quit()
        else:
            self._update_translation()

    def export_collection(self):
        choices = [self._t("Selected recording"), self._t("Whole collection")]
        dialog = QInputDialog(self)
        dialog.setWindowTitle(self._t("Export to Anki"))
        dialog.setLabelText(self._t("Export"))
        dialog.setComboBoxItems(choices)
        dialog.setComboBoxEditable(False)
        dialog.setOption(QInputDialog.InputDialogOption.UseListViewForComboBoxItems)
        list_view = dialog.findChild(QListView)
        if list_view is not None:
            install_scrollbars(list_view)
            rows_height = sum(list_view.sizeHintForRow(row) for row in range(len(choices)))
            list_view.setMinimumSize(420, max(160, rows_height + 2 * list_view.frameWidth()))
        dialog.setOkButtonText(self._t("Export"))
        dialog.setCancelButtonText(self._t("Cancel"))
        if dialog.exec() != QInputDialog.DialogCode.Accepted:
            return
        scope = dialog.textValue()
        parent = QFileDialog.getExistingDirectory(
            self, self._t("Choose export parent folder"), str(self.output_dir)
        )
        if not parent:
            return
        try:
            if scope == choices[0] and (selected := self.selected_recording()) is not None:
                if self._selected_saved() is None:
                    raise FileNotFoundError(f"Missing or unreadable MP3: {selected.path}")
            records = (
                [self._selected_saved()]
                if scope == choices[0] and self._selected_saved()
                else scan_recordings(self.output_dir)
                if scope == choices[1]
                else []
            )
            path = export_anki(
                records, Path(parent) / "cambridge-anki", language=self.translation_language
            )
            self._status("Anki export saved: {path}", path=str(path))
        except (OSError, ValueError) as exc:
            self._status("Error: {error}", severity="error", error=str(exc))

    @Slot()
    def _translation_finished(self):
        if self._translation_worker is not None:
            self._translation_worker.wait()
        self._translation_worker = None
        if self._closing:
            if self._worker is None and self._dictionary_worker is None:
                self.close()
                QApplication.instance().quit()
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
        self.status_label.setText(self._t(self._status_message, **self._status_values))
        self.status_label.setProperty("severity", self._status_severity)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _status(self, message, *, severity="", **values):
        self._status_message, self._status_values, self._status_severity = message, values, severity
        self._refresh_status()

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
            self._t("Downloading..." if self._worker else "Open saved" if existing else "Download")
        )

    def _set_busy(self, busy):
        for widget in (
            self.word_edit,
            self.accent_combo,
            self.choose_button,
            self.preferences_dialog.language_combo,
            self.library_combo,
            self.refresh_button,
        ):
            widget.setEnabled(not busy)
        self.combine_check.setEnabled(not busy and bool(ffmpeg_executable()))
        self.progress.setVisible(busy)
        self._update_download_label()
        self.download_button.setEnabled(not busy and bool(self.word_edit.text().strip()))
        self.play_button.setEnabled(not busy and bool(self.recordings))
        self.redownload_button.setEnabled(not busy and bool(self.recordings))
        self.library_combo.setEnabled(not busy and bool(self.library_combo.currentData()))

    @Slot()
    def start_download(self, *, force=False, choose_variant=False):
        if self._worker is not None:
            return
        if choose_variant and not self.word_edit.text().strip() and self.selected_recording():
            self.word_edit.setText(self.selected_recording().word)
        try:
            word = normalize_word(self.word_edit.text(), self.language)
        except ValueError as exc:
            self._status("Error: {error}", severity="error", error=str(exc))
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
        worker.finished.connect(self._finished)
        worker.finished.connect(worker.deleteLater)
        self._set_busy(True)
        self._status("Downloading...")
        worker.start()

    def _selection_required(self, selection):
        self._pending_selection = selection

    def _choose_variant(self, selection):
        labels = [v.label + f" [{v.id[:8]}]" for v in selection.choices]
        text, accepted = QInputDialog.getItem(
            self, self._t("Choose pronunciation"), self._t("Dictionary entry"), labels, 0, False
        )
        if not accepted:
            self._status("Download cancelled.")
            return
        choice = selection.choices[labels.index(text)]
        path = self.output_dir / audio_filename(
            self._selection_word, choice.pronunciation.accent, choice.id
        )
        overwrite = False
        if path.exists():
            if (
                QMessageBox.question(
                    self,
                    self._t("Replace recordings?"),
                    str(path),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
            overwrite = True
        self._launch_download(
            DownloadRequest(
                self._selection_word,
                self.output_dir,
                choice.pronunciation.accent,
                self.language,
                self.translation_check.isChecked(),
                self.combine_check.isChecked(),
                overwrite,
                variant_id=choice.id,
                entries=selection.entries,
                translation_language=self.translation_language,
                dictionary_dir=self.dictionary_dir,
            )
        )

    @Slot(object)
    def _on_recording(self, recording: Recording):
        self.recordings.append(recording)
        self._refresh_recordings(selected=len(self.recordings) - 1)

    @Slot(object)
    def _on_completed(self, result: DownloadResult):
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
                self._translation_errors[(record.path, language)] = self._t(
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
        self.file_label.setText(record.path.name if record else "")
        self.file_label.setVisible(record is not None)
        self.play_button.setEnabled(record is not None and self._worker is None)
        self.redownload_button.setEnabled(record is not None and self._worker is None)
        if record is not None:
            index = self.library_combo.findData(str(record.path))
            if index >= 0:
                self.library_combo.blockSignals(True)
                self.library_combo.setCurrentIndex(index)
                self.library_combo.blockSignals(False)

    def _open_saved(self, saved):
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
            previous = str(record.path)
        try:
            self._library = scan_recordings(self.output_dir)
        except OSError as exc:
            self._library = []
            self._status(
                "Could not read saved recordings: {error}", severity="error", error=str(exc)
            )
        self.library_combo.blockSignals(True)
        self.library_combo.clear()
        for item in self._library:
            record = item.recording
            self.library_combo.addItem(record.label, str(record.path))
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
            self.accent_combo.setCurrentIndex(self.accent_combo.findData(record.accent))
            self.start_download(force=True)

    def selected_recording(self) -> Recording | None:
        index = self.recording_combo.currentIndex()
        return self.recordings[index] if 0 <= index < len(self.recordings) else None

    @Slot()
    def toggle_playback(self):
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
            self._status("Error: {error}", severity="error", error=str(exc))

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

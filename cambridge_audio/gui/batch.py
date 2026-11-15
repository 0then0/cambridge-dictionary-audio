"""Batch word-list dialog: sequential search, explicit choice, then one confirmed save."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
)

from ..batch import (
    ERROR,
    EXISTING,
    FAILED,
    FOUND,
    MAX_BATCH_QUERIES,
    MISSING,
    PENDING,
    SAVED,
    SEARCHING,
    BatchInput,
    BatchRow,
    SaveSettings,
    accent_regions,
    item_key,
    options,
    parse_batch,
    pending_items,
    retry_lookups,
    selectable,
    selected_items,
)
from ..errors import friendly_error
from ..i18n import translate
from ..library import scan_recordings
from ..service import saved_choice_matches
from .theme import ComboBox, install_scrollbars
from .workers import BatchLookupWorker, BatchSaveWorker, DownloadRequest, DownloadWorker

ACCENT_NAMES = {"us": "American (US)", "uk": "British (UK)"}


def _label(text="", *, name="", wrap=True):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(wrap)
    if name:
        widget.setObjectName(name)
    return widget


def _names(values, limit=5):
    values = list(values)
    return ", ".join(values[:limit]) + (" …" if len(values) > limit else "")


class BatchDialog(QDialog):
    """Modal while open, so the main window cannot change the same collection."""

    library_changed = Signal()

    def __init__(
        self,
        parent=None,
        *,
        output_dir: Path,
        accent: str,
        language: str,
        translation_language: str | None = None,
        dictionary_dir: Path | None = None,
        preview_dir: Path | None = None,
        play=None,
    ):
        super().__init__(parent)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        # Captured once: later main-window changes cannot redirect this batch.
        self.output_dir = Path(output_dir)
        self.language = language
        self.translation_language = translation_language
        self.dictionary_dir = dictionary_dir
        self.preview_dir = preview_dir
        self._play = play
        self.accent = accent if accent in {"us", "uk", "both"} else "us"
        self._input = BatchInput()
        self._rows: list[BatchRow] = []
        self._generation = 0
        self._worker = None
        self._phase = ""
        self._progress = (0, 0)
        self._close_requested = False
        self._cancelled = False
        self._changed_library = False
        self._attempted_save = False
        self._rendering = False
        self._shown_query = ""
        self._saved = []
        self._status_text, self._status_error = "", False
        self._build_ui()
        self._connect_ui()
        self._retranslate()
        self._rescan()
        self._input_changed()
        available = self.screen().availableGeometry()
        self.resize(min(880, available.width() - 40), min(760, available.height() - 64))

    def _t(self, message, **values):
        return translate(message, self.language, **values)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        self.input_label = _label(wrap=False)
        self.input_edit = QPlainTextEdit()
        self.input_edit.setTabChangesFocus(True)
        self.input_edit.setMaximumHeight(104)
        self.input_label.setBuddy(self.input_edit)
        install_scrollbars(self.input_edit)
        self.input_summary = _label(name="status")
        layout.addWidget(self.input_label)
        layout.addWidget(self.input_edit)
        layout.addWidget(self.input_summary)
        controls = QHBoxLayout()
        controls.setSpacing(12)
        self.accent_label = _label(wrap=False)
        self.accent_combo = ComboBox()
        self.accent_label.setBuddy(self.accent_combo)
        self.search_button = QPushButton()
        self.search_button.setObjectName("downloadButton")
        self.cancel_button = QPushButton()
        controls.addWidget(self.accent_label)
        controls.addWidget(self.accent_combo)
        controls.addStretch()
        controls.addWidget(self.search_button)
        controls.addWidget(self.cancel_button)
        layout.addLayout(controls)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(3)
        layout.addWidget(self.progress)
        self.status_label = _label(name="status")
        layout.addWidget(self.status_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.query_list = QListWidget()
        self.query_list.setWordWrap(True)
        self.query_list.setSpacing(2)
        install_scrollbars(self.query_list)
        splitter.addWidget(self.query_list)
        panel = QFrame()
        panel.setObjectName("panel")
        details = QVBoxLayout(panel)
        details.setContentsMargins(12, 12, 12, 12)
        details.setSpacing(8)
        self.result_title = _label()
        font = self.result_title.font()
        font.setBold(True)
        self.result_title.setFont(font)
        details.addWidget(self.result_title)
        self.meaning_list = QListWidget()
        self.meaning_list.setWordWrap(True)
        self.meaning_list.setSpacing(2)
        self.meaning_list.setMinimumHeight(150)
        install_scrollbars(self.meaning_list)
        details.addWidget(self.meaning_list, 1)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        self.region_labels, self.region_combos, self.play_buttons = {}, {}, {}
        for row, region in enumerate(("us", "uk")):
            name = _label(wrap=False)
            combo = ComboBox()
            play = QPushButton()
            name.setBuddy(combo)
            grid.addWidget(name, row, 0)
            grid.addWidget(combo, row, 1)
            grid.addWidget(play, row, 2)
            self.region_labels[region] = name
            self.region_combos[region] = combo
            self.play_buttons[region] = play
        grid.setColumnStretch(1, 1)
        details.addLayout(grid)
        self.error_label = _label()
        self.error_label.setObjectName("status")
        self.error_label.setProperty("severity", "error")
        details.addWidget(self.error_label)
        self.details_button = QPushButton()
        self.details_button.setCheckable(True)
        self.details_text = QPlainTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(120)
        self.details_text.hide()
        self.details_button.toggled.connect(self.details_text.setVisible)
        details.addWidget(self.details_button, 0, Qt.AlignmentFlag.AlignLeft)
        details.addWidget(self.details_text)
        splitter.addWidget(panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)

        self.selection_label = _label(wrap=False)
        self.selection_list = QListWidget()
        self.selection_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.selection_list.setMaximumHeight(96)
        self.selection_list.setWordWrap(True)
        self.selection_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.selection_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        install_scrollbars(self.selection_list)
        self.selection_label.setBuddy(self.selection_list)
        layout.addWidget(self.selection_label)
        layout.addWidget(self.selection_list)
        self.summary_label = _label()
        self.retry_label = _label(name="muted")
        layout.addWidget(self.summary_label)
        layout.addWidget(self.retry_label)
        actions = QHBoxLayout()
        actions.addStretch()
        self.save_button = QPushButton()
        self.save_button.setObjectName("downloadButton")
        self.close_button = QPushButton()
        actions.addWidget(self.save_button)
        actions.addWidget(self.close_button)
        layout.addLayout(actions)

    def _connect_ui(self):
        self.input_edit.textChanged.connect(self._input_changed)
        self.accent_combo.currentIndexChanged.connect(self._accent_changed)
        self.search_button.clicked.connect(self.start_search)
        self.cancel_button.clicked.connect(self.cancel)
        self.save_button.clicked.connect(self.start_save)
        self.close_button.clicked.connect(self.close)
        self.query_list.currentRowChanged.connect(self._show_row)
        self.meaning_list.currentRowChanged.connect(self._show_meaning)
        self.meaning_list.itemChanged.connect(self._meaning_checked)
        for region in ("us", "uk"):
            self.region_combos[region].activated.connect(
                lambda _index, region=region: self._pronunciation_chosen(region)
            )
            self.play_buttons[region].clicked.connect(
                lambda _checked=False, region=region: self.preview(region)
            )

    def _retranslate(self):
        self.setWindowTitle(self._t("Add a word list"))
        self.input_label.setText(self._t("Words and phrases, one per line"))
        self.input_edit.setAccessibleName(self._t("Words and phrases, one per line"))
        self.input_edit.setPlaceholderText(self._t("For example:\nhello\nlead\ngood morning"))
        self.accent_label.setText(self._t("Pronunciation"))
        self.accent_combo.setAccessibleName(self._t("Pronunciation"))
        blocked = self.accent_combo.blockSignals(True)
        self.accent_combo.clear()
        for key, value in (
            ("American (US)", "us"),
            ("British (UK)", "uk"),
            ("Both", "both"),
        ):
            self.accent_combo.addItem(self._t(key), value)
        self.accent_combo.setCurrentIndex(max(0, self.accent_combo.findData(self.accent)))
        self.accent_combo.blockSignals(blocked)
        self.cancel_button.setText(self._t("Cancel"))
        self.close_button.setText(self._t("Close"))
        self.query_list.setAccessibleName(self._t("Search results"))
        self.meaning_list.setAccessibleName(self._t("Choose meanings to save"))
        self.selection_label.setText(self._t("Selected for saving"))
        self.selection_list.setAccessibleName(self._t("Selected for saving"))
        self.details_button.setText(self._t("Technical details"))
        self.details_text.setAccessibleName(self._t("Technical details"))
        for region in ("us", "uk"):
            self.region_labels[region].setText(self._t(ACCENT_NAMES[region]))
            self.region_combos[region].setAccessibleName(self._t(ACCENT_NAMES[region]))
            self.play_buttons[region].setText(self._t("Play"))
            self.play_buttons[region].setToolTip(
                self._t("Listen without saving to the collection.")
            )
        self._status(self._t("Paste words or phrases, one per line, then search."))

    # State ---------------------------------------------------------------

    @property
    def regions(self):
        return accent_regions(self.accent)

    def busy(self):
        return self._worker is not None

    def _row(self, query):
        return next((row for row in self._rows if row.query == query), None)

    def _current_row(self):
        index = self.query_list.currentRow()
        return self._rows[index] if 0 <= index < len(self._rows) else None

    def _current_entry(self):
        item = self.meaning_list.currentItem()
        row = self._current_row()
        return row.entry(item.data(Qt.ItemDataRole.UserRole)) if item and row else None

    def _rescan(self):
        try:
            self._saved = scan_recordings(self.output_dir)
        except OSError:
            self._saved = []

    def _saved_regions(self, row, entry):
        """Accents of this meaning already in the collection before this batch saved them."""
        return [
            region
            for region in self.regions
            if any(
                saved_choice_matches(s.recording, row.query, variant)
                and row.outcomes.get(item_key(row.query, variant), ("", ""))[0] != SAVED
                for variant in options(entry, region)
                for s in self._saved
            )
        ]

    def _status(self, text, *, error=False):
        self._status_text, self._status_error = text, error
        self.status_label.setText(text)
        self.status_label.setProperty("severity", "error" if error else "")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _invalidate(self):
        """Discard results of operations started for an earlier list or accent."""
        self._generation += 1

    def _input_changed(self):
        if self.busy():
            return
        self._invalidate()
        self._input = parse_batch(self.input_edit.toPlainText(), self.language)
        previous = {row.query: row for row in self._rows}
        # Unchanged queries keep their results; removed ones disappear with their choices.
        self._rows = [previous.get(query) or BatchRow(query) for query in self._input.queries]
        if self._input.over_limit:
            self._rows = []
        self._render_rows()
        self._update_summary()

    def _accent_changed(self):
        if self.busy():
            return
        self._invalidate()
        self.accent = self.accent_combo.currentData()
        for row in self._rows:
            if row.status == FOUND:
                row.reset_selection(self.regions)
        self._render_rows()

    # Rendering -----------------------------------------------------------

    def _row_text(self, row):
        if row.status == PENDING:
            state = self._t("Waiting")
        elif row.status == SEARCHING:
            state = self._t("Searching...")
        elif row.status == MISSING:
            state = self._t("No result")
        elif row.status == ERROR:
            state = self._t(
                "Search failed: {error}", error=friendly_error(row.details, self.language)
            )
        elif not any(selectable(e, self.regions) for e in row.meanings()):
            state = self._t("No recording for the selected pronunciation")
        elif row.unresolved():
            state = self._t("Choose a pronunciation")
        elif row.selection:
            state = self._t("Found · selected: {count}", count=len(row.selection))
        else:
            state = self._t("Choose meanings: {count}", count=len(row.meanings()))
        outcomes = [outcome for outcome, _ in row.outcomes.values()]
        parts = [state]
        if outcomes.count(SAVED):
            parts.append(self._t("saved: {count}", count=outcomes.count(SAVED)))
        if outcomes.count(EXISTING):
            parts.append(self._t("already in collection: {count}", count=outcomes.count(EXISTING)))
        if outcomes.count(FAILED):
            parts.append(self._t("failed: {count}", count=outcomes.count(FAILED)))
        return row.query + "\n" + " · ".join(parts)

    def _render_rows(self):
        current = self.query_list.currentRow()
        self._rendering = True
        self.query_list.clear()
        for row in self._rows:
            item = QListWidgetItem(self._row_text(row))
            item.setToolTip(item.text())
            self.query_list.addItem(item)
        self._rendering = False
        if self._rows:
            self.query_list.setCurrentRow(min(max(current, 0), len(self._rows) - 1))
        self._show_row()
        self._update_selection()
        self._update_actions()

    def _refresh_row(self, row):
        index = self._rows.index(row)
        item = self.query_list.item(index)
        if item is not None:
            item.setText(self._row_text(row))
            item.setToolTip(item.text())
        if index == self.query_list.currentRow():
            self._show_row()
        self._update_selection()
        self._update_actions()

    def _row_locked(self, row, entry):
        return any(
            row.outcomes.get(item_key(row.query, v), ("", ""))[0] in {SAVED, EXISTING}
            for region in self.regions
            for v in options(entry, region)
        )

    def _meaning_text(self, row, entry):
        parts = []
        for region in self.regions:
            choices = options(entry, region)
            if not choices:
                parts.append(self._t("{accent}: not available", accent=region.upper()))
            else:
                ipa = ", ".join(dict.fromkeys(f"/{v.pronunciation.ipa}/" for v in choices))
                parts.append(f"{region.upper()} {ipa}")
        saved = self._saved_regions(row, entry)
        if saved:
            parts.append(
                self._t("Already saved: {accents}", accents=", ".join(r.upper() for r in saved))
            )
        for region in self.regions:
            for variant in options(entry, region):
                outcome = row.outcomes.get(item_key(row.query, variant), ("", ""))[0]
                if outcome == SAVED:
                    parts.append(self._t("{accent}: saved", accent=region.upper()))
                elif outcome == FAILED:
                    parts.append(self._t("{accent}: failed", accent=region.upper()))
        heading = " · ".join(p for p in (self._t(entry.part_of_speech), entry.definition) if p)
        return heading + "\n" + " · ".join(parts)

    def _show_row(self, *args):
        if self._rendering:
            return
        row = self._current_row()
        previous = self.meaning_list.currentRow()
        same = row is not None and row.query == self._shown_query
        self._shown_query = row.query if row else ""
        self._rendering = True
        self.meaning_list.clear()
        if row is not None:
            self.result_title.setText(row.query)
            for entry in row.meanings():
                item = QListWidgetItem(self._meaning_text(row, entry))
                item.setData(Qt.ItemDataRole.UserRole, entry.sense_id)
                item.setToolTip(entry.definition)
                flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                if (
                    selectable(entry, self.regions)
                    and not self.busy()
                    and not self._row_locked(row, entry)
                ):
                    flags |= Qt.ItemFlag.ItemIsUserCheckable
                item.setFlags(flags)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if entry.sense_id in row.selection
                    else Qt.CheckState.Unchecked
                )
                self.meaning_list.addItem(item)
        else:
            self.result_title.setText("")
        self._rendering = False
        if self.meaning_list.count():
            # Re-rendering the same query keeps the meaning the user is working on.
            keep = same and 0 <= previous < self.meaning_list.count()
            self.meaning_list.setCurrentRow(previous if keep else 0)
        self._show_meaning()
        self._show_errors(row)

    def _show_errors(self, row):
        summaries, details = [], []
        if row is not None and row.status == MISSING:
            summaries.append(self._t("No dictionary entry found for '{word}'.", word=row.query))
            details.append(row.details)
        elif row is not None and row.status == ERROR:
            summaries.append(friendly_error(row.details, self.language))
            details.append(row.details)
        if row is not None:
            for outcome, problem in row.outcomes.values():
                if not problem:
                    continue
                if outcome == FAILED:
                    summaries.append(
                        self._t(
                            "Saving failed: {error}", error=friendly_error(problem, self.language)
                        )
                    )
                else:
                    summaries.append(
                        self._t(
                            "Audio saved. Translation unavailable: {error}",
                            error=friendly_error(problem, self.language, context="translation"),
                        )
                    )
                details.append(problem)
        text = "\n".join(dict.fromkeys(summaries))
        self.error_label.setText(text)
        self.error_label.setVisible(bool(text))
        self.details_text.setPlainText("\n\n".join(dict.fromkeys(details)))
        self.details_button.setVisible(bool(details))
        if not details:
            self.details_button.setChecked(False)

    def _show_meaning(self, *args):
        if self._rendering:
            return
        row, entry = self._current_row(), self._current_entry()
        for region in ("us", "uk"):
            combo, play, name = (
                self.region_combos[region],
                self.play_buttons[region],
                self.region_labels[region],
            )
            visible = entry is not None and region in self.regions
            for widget in (combo, play, name):
                widget.setVisible(visible)
            if not visible:
                continue
            choices = options(entry, region)
            chosen = row.selection.get(entry.sense_id, {}).get(region, "")
            blocked = combo.blockSignals(True)
            combo.clear()
            if not choices:
                combo.addItem(self._t("{accent}: not available", accent=region.upper()), "")
            elif len(choices) > 1 and not chosen:
                combo.addItem(self._t("Choose a pronunciation"), "")
            for number, variant in enumerate(choices, 1):
                text = f"/{variant.pronunciation.ipa}/" if variant.pronunciation.ipa else ""
                if len(choices) > 1:
                    text = f"{number}. {text}".strip()
                combo.addItem(text or self._t("Recording"), variant.id)
            combo.setCurrentIndex(max(0, combo.findData(chosen)) if chosen else 0)
            combo.blockSignals(blocked)
            combo.setEnabled(
                len(choices) > 1 and not self.busy() and not self._row_locked(row, entry)
            )
            play.setEnabled(bool(combo.currentData()) and not self.busy())

    def _update_selection(self):
        self.selection_list.clear()
        count = 0
        for row in self._rows:
            if row.status != FOUND:
                continue
            for sense_id, chosen in row.selection.items():
                entry = row.entry(sense_id)
                if entry is None:
                    continue
                accents = []
                for region in self.regions:
                    variant_id = chosen.get(region)
                    if region not in chosen:
                        accents.append(self._t("{accent}: not available", accent=region.upper()))
                    elif not variant_id:
                        accents.append(f"{region.upper()}: " + self._t("Choose a pronunciation"))
                    else:
                        variant = next(v for v in options(entry, region) if v.id == variant_id)
                        accents.append(f"{region.upper()} /{variant.pronunciation.ipa}/")
                        count += 1
                text = " · ".join(
                    p
                    for p in (
                        row.query,
                        self._t(entry.part_of_speech),
                        entry.definition,
                        ", ".join(accents),
                    )
                    if p
                )
                self.selection_list.addItem(text)
        self.selection_label.setText(self._t("Selected for saving: {count}", count=count))

    def _update_summary(self):
        if self._input.over_limit:
            text = self._t(
                "The list has {count} different queries; the limit is {limit}. "
                "Split it into smaller lists.",
                count=len(self._input.queries),
                limit=MAX_BATCH_QUERIES,
            )
        else:
            text = self._t("Queries: {count}", count=len(self._input.queries))
            if self._input.duplicates:
                text += "\n" + self._t(
                    "Repeated lines merged: {items}",
                    items=_names(f"{q} (+{n})" for q, n in self._input.duplicates),
                )
        if self._input.invalid:
            text += "\n" + self._t(
                "Invalid lines (fix or remove them): {items}",
                items=_names(f"{n}: {line}" for n, line in self._input.invalid),
            )
        self.input_summary.setText(text)
        self.input_summary.setProperty(
            "severity", "error" if self._input.invalid or self._input.over_limit else ""
        )
        self.input_summary.style().unpolish(self.input_summary)
        self.input_summary.style().polish(self.input_summary)
        self._update_actions()

    def _update_actions(self):
        busy = self.busy()
        lookups = retry_lookups(self._rows)
        items = pending_items(self._rows)
        unresolved = sum(row.unresolved() for row in self._rows if row.status == FOUND)
        failed_searches = [self._rows[i].query for i in lookups if self._rows[i].status == ERROR]
        failed_items = [
            item
            for item in items
            if self._row(item.query).outcomes.get(item.key, ("", ""))[0] == FAILED
        ]
        self.input_edit.setReadOnly(busy)
        self.accent_combo.setEnabled(not busy)
        self.cancel_button.setEnabled(busy and not self._close_requested)
        self.search_button.setEnabled(not busy and self._input.ready and bool(lookups))
        self.search_button.setText(
            self._t("Retry search ({count})", count=len(lookups))
            if failed_searches
            else self._t("Search")
        )
        self.save_button.setEnabled(not busy and bool(items) and not unresolved)
        self.save_button.setText(
            self._t("Retry saving ({count})", count=len(items))
            if failed_items
            else self._t("Save {count} recordings", count=len(items))
        )
        if unresolved and not busy:
            self.save_button.setToolTip(
                self._t("Choose a pronunciation for each selected meaning.")
            )
        else:
            self.save_button.setToolTip("")
        retry = []
        if failed_searches:
            retry.append(self._t("Retry search: {items}", items=_names(failed_searches)))
        if failed_items:
            retry.append(
                self._t(
                    "Retry saving: {items}",
                    items=_names(
                        f"{i.query} ({self._t(i.variant.entry.part_of_speech) or '-'}, "
                        f"{i.variant.pronunciation.accent.upper()})"
                        for i in failed_items
                    ),
                )
            )
        if retry:
            retry.append(self._t("Completed searches and saved recordings are not repeated."))
        self.retry_label.setText("\n".join(retry))
        self.retry_label.setVisible(bool(retry))
        self.progress.setVisible(busy)
        done, total = self._progress
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)
        self._update_outcomes()

    def _update_outcomes(self):
        if not self._attempted_save:
            self.summary_label.hide()
            return
        outcomes = [o for row in self._rows for o, _ in row.outcomes.values()]
        # Skipped: no result, failed search or nothing selected; never unsaved choices.
        chosen = {item.query for item in selected_items(self._rows)}
        skipped = sum(1 for row in self._rows if row.query not in chosen and not row.outcomes)
        translations = sum(
            1
            for row in self._rows
            for o, problem in row.outcomes.values()
            if o == SAVED and problem
        )
        text = self._t(
            "Saved: {saved} · already in collection: {existing} · skipped queries: {skipped} · "
            "failed: {failed}",
            saved=outcomes.count(SAVED),
            existing=outcomes.count(EXISTING),
            skipped=skipped,
            failed=outcomes.count(FAILED),
        )
        if translations:
            text += "\n" + self._t(
                "Audio saved; translation unavailable for {count} recordings.", count=translations
            )
        self.summary_label.setText(text)
        self.summary_label.show()

    # User actions ----------------------------------------------------------

    def _meaning_checked(self, item):
        if self._rendering or self.busy():
            return
        row = self._current_row()
        if row is None:
            return
        row.select(
            item.data(Qt.ItemDataRole.UserRole),
            self.regions,
            item.checkState() == Qt.CheckState.Checked,
        )
        # The toggled meaning becomes the one whose pronunciations are shown.
        self.meaning_list.setCurrentItem(item)
        self._update_row_in_place(row)

    def _pronunciation_chosen(self, region):
        row, entry = self._current_row(), self._current_entry()
        variant_id = self.region_combos[region].currentData()
        if row is None or entry is None or not variant_id or self.busy():
            return
        # Choosing a recording is an explicit selection of its meaning.
        row.select(entry.sense_id, self.regions)
        row.choose(entry.sense_id, region, variant_id)
        self._update_row_in_place(row)

    def _update_row_in_place(self, row):
        """Refresh the visible row without recreating list items.

        Called from the list's and combo boxes' own signal handlers: deleting the
        item being clicked there would make Qt reset the current meaning.
        """
        index = self._rows.index(row)
        item = self.query_list.item(index)
        if item is not None:
            item.setText(self._row_text(row))
            item.setToolTip(item.text())
        self._rendering = True
        try:
            for number in range(self.meaning_list.count()):
                meaning = self.meaning_list.item(number)
                entry = row.entry(meaning.data(Qt.ItemDataRole.UserRole))
                if entry is None:
                    continue
                meaning.setText(self._meaning_text(row, entry))
                meaning.setCheckState(
                    Qt.CheckState.Checked
                    if entry.sense_id in row.selection
                    else Qt.CheckState.Unchecked
                )
        finally:
            self._rendering = False
        self._show_meaning()
        self._update_selection()
        self._update_actions()

    def start_search(self):
        if self.busy() or not self._input.ready:
            return
        indexes = retry_lookups(self._rows)
        if not indexes:
            return
        self._invalidate()
        for index in indexes:
            self._rows[index].status, self._rows[index].details = PENDING, ""
        queries = tuple(self._rows[i].query for i in indexes)
        worker = BatchLookupWorker(self._generation, queries, self.language, self)
        worker.searching.connect(self._searching)
        worker.looked_up.connect(self._looked_up)
        self._start(worker, "search", len(queries))
        self._status(self._t("Searching {done} of {total}...", done=1, total=len(queries)))

    def _searching(self, generation, query):
        row = self._row(query)
        if generation != self._generation or row is None:
            return
        row.status = SEARCHING
        done, total = self._progress
        self._status(self._t("Searching {done} of {total}...", done=done + 1, total=total))
        self._refresh_row(row)

    def _looked_up(self, generation, query, status, entries, details):
        row = self._row(query)
        if generation != self._generation or row is None:
            return
        row.status, row.entries, row.details = status, tuple(entries or ()), details
        row.outcomes.clear()
        if status == FOUND:
            row.reset_selection(self.regions)
        done, total = self._progress
        self._progress = (done + 1, total)
        self._refresh_row(row)

    def start_save(self):
        if self.busy():
            return
        items = pending_items(self._rows)
        if not items or any(row.unresolved() for row in self._rows if row.status == FOUND):
            return
        self._invalidate()
        self._attempted_save = True
        # Freeze destination and options for the whole operation.
        settings = SaveSettings(
            self.output_dir,
            self.language,
            self.translation_language,
            self.dictionary_dir,
            self.preview_dir,
        )
        worker = BatchSaveWorker(self._generation, items, settings, self)
        worker.saving.connect(self._saving)
        worker.saved.connect(self._item_saved)
        self._start(worker, "save", len(items))
        self._status(self._t("Saving {done} of {total}...", done=1, total=len(items)))

    def _saving(self, generation, key):
        if generation != self._generation:
            return
        done, total = self._progress
        self._status(self._t("Saving {done} of {total}...", done=done + 1, total=total))

    def _item_saved(self, generation, key, outcome, details):
        if generation != self._generation:
            return
        row = self._row(key.rpartition(":")[0])
        if row is None:
            return
        row.outcomes[key] = (outcome, details)
        if outcome == SAVED:
            self._changed_library = True
        done, total = self._progress
        self._progress = (done + 1, total)
        self._rescan()
        self._refresh_row(row)

    def preview(self, region):
        row, entry = self._current_row(), self._current_entry()
        variant_id = self.region_combos[region].currentData()
        if self.busy() or row is None or entry is None or not variant_id:
            return
        variant = next(v for v in options(entry, region) if v.id == variant_id)
        worker = DownloadWorker(
            DownloadRequest(
                row.query,
                self.output_dir,
                region,
                self.language,
                preview_choice=variant,
                preview_dir=self.preview_dir,
            ),
            self,
        )
        generation = self._generation
        worker.previewed.connect(lambda path: self._previewed(generation, path))
        worker.failed.connect(lambda error: self._preview_failed(generation, error))
        self._start(worker, "preview", 0)

    def _previewed(self, generation, path):
        if generation == self._generation and not self._close_requested and self._play:
            self._play(path)

    def _preview_failed(self, generation, error):
        if generation == self._generation:
            self._status(
                self._t(
                    "Playback: {error}",
                    error=friendly_error(error, self.language, context="playback"),
                ),
                error=True,
            )

    def _start(self, worker, phase, total):
        self._worker, self._phase, self._progress = worker, phase, (0, total)
        worker.finished.connect(self._finished)
        worker.finished.connect(worker.deleteLater)
        self._render_rows()
        worker.start()

    def cancel(self):
        if self._worker is not None:
            self._cancelled = True
            self._worker.requestInterruption()
            self._status(self._t("Stopping after the current request..."))
            self._update_actions()

    def _finished(self):
        worker, phase = self._worker, self._phase
        if worker is not None:
            worker.wait()
        # QThread forgets an interruption request once it has finished.
        cancelled, self._cancelled = self._cancelled, False
        self._worker, self._phase = None, ""
        for row in self._rows:
            if row.status == SEARCHING:
                row.status = PENDING
        if phase in {"search", "save"}:
            self._rescan()
        if phase == "save" and self._changed_library:
            self._changed_library = False
            self.library_changed.emit()
        if self._close_requested:
            self.close()
            return
        self._render_rows()
        if cancelled:
            self._status(self._t("Cancelled. Finished results are kept."))
        elif phase == "search":
            errors = sum(row.status == ERROR for row in self._rows)
            self._status(
                self._t("Search finished with errors: {count}. Retry is available.", count=errors)
                if errors
                else self._t("Search finished. Choose meanings, listen, then save."),
                error=bool(errors),
            )
        elif phase == "save":
            failed = sum(o == FAILED for row in self._rows for o, _ in row.outcomes.values())
            self._status(
                self._t("Saving finished with errors: {count}. Retry is available.", count=failed)
                if failed
                else self._t("Saving finished."),
                error=bool(failed),
            )
        elif phase == "preview" and not self._status_error:
            self._status(self._t("Search finished. Choose meanings, listen, then save."))

    # Closing ---------------------------------------------------------------

    def reject(self):
        self.close()

    def closeEvent(self, event):
        if self._worker is not None:
            # Keep the modal dialog until the bounded request ends: the main window
            # must not start competing work on the same collection meanwhile.
            self._close_requested = self._cancelled = True
            self._worker.requestInterruption()
            self._status(self._t("Stopping after the current request. The window closes then."))
            self._update_actions()
            event.ignore()
            return
        self._invalidate()
        if self._changed_library:
            self.library_changed.emit()
            self._changed_library = False
        event.accept()

    def shutdown(self):
        """Application quit: stop new work and join the current request."""
        self._invalidate()
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            worker.wait()

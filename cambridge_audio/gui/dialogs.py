"""Choice dialogs with explicit, wrapping lists on every platform."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from ..anki import normalize_anki_tag
from ..i18n import translate
from ..library import SavedRecording
from .theme import ContentList, install_scrollbars


class ChoiceDialog(QDialog):
    def __init__(self, parent, title, prompt, choices):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._choices = list(choices)
        layout = QVBoxLayout(self)
        label = QLabel(prompt)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        layout.addWidget(label)
        self.list_view = ContentList(self)
        self.list_view.setSpacing(4)
        self.list_view.addItems(self._choices)
        self.list_view.setCurrentRow(0)
        self.list_view.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.list_view)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        available = self.screen().availableGeometry()
        self.resize(min(680, available.width() - 40), self.sizeHint().height())

    def comboBoxItems(self):
        return self._choices.copy()

    def textValue(self):
        item = self.list_view.currentItem()
        return item.text() if item else ""

    def setTextValue(self, text):
        matches = self.list_view.findItems(text, Qt.MatchFlag.MatchExactly)
        if matches:
            self.list_view.setCurrentItem(matches[0])

    def setOkButtonText(self, text):
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(text)

    def setCancelButtonText(self, text):
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(text)


class ExportSelectionDialog(QDialog):
    def __init__(self, parent, records: list[SavedRecording], language: str):
        super().__init__(parent)
        self.language = language
        self._selected_ids: set[str] = set()
        self.tag = ""
        self.setWindowTitle(self._t("Export to Anki"))

        layout = QVBoxLayout(self)
        self.filter_edit = QLineEdit()
        self.filter_edit.setClearButtonEnabled(True)
        filter_label = QLabel(self._t("Filter by word or phrase"))
        filter_label.setBuddy(self.filter_edit)
        layout.addWidget(filter_label)
        layout.addWidget(self.filter_edit)

        self.recordings_list = QListWidget()
        self.recordings_list.setAccessibleName(self._t("Saved recordings"))
        self.empty_label = QLabel(self._t("No matching recordings"))
        layout.addWidget(self.empty_label)
        layout.addWidget(self.recordings_list, 2)

        selection_header = QHBoxLayout()
        self.selection_label = QLabel()
        self.selection_label.setWordWrap(True)
        self.clear_button = QPushButton(self._t("Clear selection"))
        selection_header.addWidget(self.selection_label, 1)
        selection_header.addWidget(self.clear_button)
        layout.addLayout(selection_header)

        self.selection_list = QListWidget()
        self.selection_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.selection_label.setBuddy(self.selection_list)
        layout.addWidget(self.selection_list, 1)
        for view in (self.recordings_list, self.selection_list):
            view.setWordWrap(True)
            view.setTextElideMode(Qt.TextElideMode.ElideNone)
            view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            view.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
            view.setSpacing(4)
            install_scrollbars(view)

        tag_row = QHBoxLayout()
        self.tag_edit = QLineEdit()
        self.tag_edit.setClearButtonEnabled(True)
        tag_label = QLabel(self._t("Anki tag (optional)"))
        tag_label.setBuddy(self.tag_edit)
        tag_row.addWidget(tag_label)
        tag_row.addWidget(self.tag_edit, 1)
        layout.addLayout(tag_row)
        self.tag_error = QLabel()
        self.tag_error.setWordWrap(True)
        self.tag_error.setObjectName("status")
        self.tag_error.setProperty("severity", "error")
        self.tag_error.hide()
        self.tag_edit.textChanged.connect(self.tag_error.hide)
        layout.addWidget(self.tag_error)

        self._rows: dict[str, tuple[str, str]] = {}
        for saved in records:
            record = saved.recording
            heading = " · ".join(
                part
                for part in (
                    record.word,
                    record.part_of_speech,
                    record.accent.upper(),
                    f"/{record.ipa}/" if record.ipa else "",
                )
                if part
            )
            text = f"{heading}\n{record.definition}" if record.definition else heading
            self._rows[record.id] = (" ".join(record.word.casefold().split()), text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self._t("Cancel"))
        self.export_button = buttons.addButton(
            self._t("Export"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.filter_edit.textChanged.connect(self._filter)
        self.recordings_list.itemChanged.connect(self._item_changed)
        self.clear_button.clicked.connect(self._clear_selection)
        self._filter("")
        self._update_selection()
        self.filter_edit.setFocus()
        available = self.screen().availableGeometry()
        self.resize(min(700, available.width() - 40), min(600, available.height() - 64))

    def _t(self, message, **values):
        return translate(message, self.language, **values)

    @property
    def selected_ids(self) -> frozenset[str]:
        return frozenset(self._selected_ids)

    def accept(self):
        if not self._selected_ids:
            return
        try:
            self.tag = normalize_anki_tag(self.tag_edit.text())
        except ValueError as exc:
            self.tag_error.setText(self._t(str(exc)))
            self.tag_error.show()
            self.tag_edit.setFocus()
            return
        super().accept()

    def _filter(self, text):
        query = " ".join(text.casefold().split())
        self.recordings_list.clear()
        for identity, (word, label) in self._rows.items():
            if query in word:
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, identity)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if identity in self._selected_ids
                    else Qt.CheckState.Unchecked
                )
                item.setToolTip(label)
                self.recordings_list.addItem(item)
        self.empty_label.setVisible(not self.recordings_list.count())

    def _item_changed(self, item):
        identity = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            self._selected_ids.add(identity)
        else:
            self._selected_ids.discard(identity)
        self._update_selection()

    def _clear_selection(self):
        self._selected_ids.clear()
        self._filter(self.filter_edit.text())
        self._update_selection()

    def _update_selection(self):
        self.selection_list.clear()
        for identity, (_, label) in self._rows.items():
            if identity in self._selected_ids:
                preview = QListWidgetItem(label, self.selection_list)
                preview.setToolTip(label)
        self.selection_label.setText(
            self._t("Selected for export: {count}", count=len(self._selected_ids))
        )
        self.clear_button.setEnabled(bool(self._selected_ids))
        self.export_button.setEnabled(bool(self._selected_ids))

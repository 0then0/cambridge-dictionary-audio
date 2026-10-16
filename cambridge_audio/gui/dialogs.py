"""Choice dialogs with explicit, wrapping lists on every platform."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from .theme import ContentList


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

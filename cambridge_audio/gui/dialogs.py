"""Choice dialogs with readable, wrapping rows instead of native combo popups."""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QInputDialog, QListView

from .theme import fit_list_height, install_scrollbars


class ChoiceDialog(QInputDialog):
    def __init__(self, parent, title, prompt, choices):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setLabelText(prompt)
        self.setComboBoxItems(choices)
        self.setComboBoxEditable(False)
        self.setOption(QInputDialog.InputDialogOption.UseListViewForComboBoxItems)
        self.list_view = self.findChild(QListView)
        self._sizing_list = False
        self.list_view.viewport().installEventFilter(self)
        view = self.list_view
        view.setWordWrap(True)
        view.setTextElideMode(Qt.TextElideMode.ElideNone)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setSpacing(4)
        install_scrollbars(view)
        available = self.screen().availableGeometry()
        self.resize(min(680, available.width() - 40), self.sizeHint().height())
        self.setTextValue(choices[0] if choices else "")

    def _size_list(self):
        if self._sizing_list:
            return
        self._sizing_list = True
        try:
            limit = max(80, self.screen().availableGeometry().height() // 2)
            fit_list_height(self.list_view, limit)
        finally:
            self._sizing_list = False

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize and watched is self.list_view.viewport():
            self._size_list()
        return super().eventFilter(watched, event)

    def showEvent(self, event):
        super().showEvent(event)
        self._size_list()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._size_list()

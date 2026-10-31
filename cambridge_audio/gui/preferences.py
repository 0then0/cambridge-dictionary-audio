"""Small settings window with immediate, persistent appearance changes."""

from PySide6.QtCore import QSettings, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ..i18n import LANGUAGES, translate
from .theme import ComboBox, stored_colors, theme_colors


class PreferencesDialog(QDialog):
    changed = Signal()
    about_requested = Signal()

    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.language = str(settings.value("language", "en"))
        self.mode = "light"
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        self.language_combo = ComboBox()
        self.theme_combo = ComboBox()
        self.language_label = QLabel()
        self.theme_label = QLabel()
        self.language_label.setBuddy(self.language_combo)
        self.theme_label.setBuddy(self.theme_combo)
        form.addRow(self.language_label, self.language_combo)
        form.addRow(self.theme_label, self.theme_combo)
        layout.addLayout(form)
        self.colors_label = QLabel()
        self.colors_label.setObjectName("heading")
        layout.addWidget(self.colors_label)
        self.explanation = QLabel()
        self.explanation.setObjectName("muted")
        self.explanation.setWordWrap(True)
        layout.addWidget(self.explanation)
        colors = QFormLayout()
        colors.setHorizontalSpacing(16)
        colors.setVerticalSpacing(12)
        self.color_labels = {}
        self.color_buttons = {}
        for token in ("background", "accent"):
            button = QPushButton()
            label = QLabel()
            label.setBuddy(button)
            colors.addRow(label, button)
            button.clicked.connect(lambda checked=False, key=token: self.choose_color(key))
            self.color_labels[token] = label
            self.color_buttons[token] = button
        layout.addLayout(colors)
        self.reset_button = QPushButton()
        self.reset_button.clicked.connect(self.reset_colors)
        layout.addWidget(self.reset_button)
        actions = QHBoxLayout()
        self.about_button = QPushButton()
        self.about_button.clicked.connect(self.about_requested.emit)
        actions.addWidget(self.about_button)
        actions.addStretch()
        self.close_button = QPushButton()
        self.close_button.clicked.connect(self.accept)
        actions.addWidget(self.close_button)
        layout.addLayout(actions)
        self.retranslate(self.language)
        self.update_colors(self.mode)
        self.language_combo.currentIndexChanged.connect(self._language_changed)
        self.theme_combo.currentIndexChanged.connect(self._theme_changed)

    def _t(self, message, **values):
        return translate(message, self.language, **values)

    def retranslate(self, language):
        self.language = language
        self.setWindowTitle(self._t("Settings"))
        self.language_label.setText(self._t("Language"))
        self.theme_label.setText(self._t("Appearance"))
        self.explanation.setText(
            self._t(
                "Changes apply immediately. System uses the palette matching your OS appearance."
            )
        )
        self.color_labels["background"].setText(self._t("Background colour"))
        self.color_labels["accent"].setText(self._t("Accent colour"))
        self.reset_button.setText(self._t("Restore default colours"))
        self.about_button.setText(self._t("About"))
        self.close_button.setText(self._t("Close"))
        for combo, choices, selected in (
            (self.language_combo, [(name, code) for code, name in LANGUAGES.items()], language),
            (
                self.theme_combo,
                [
                    (self._t(text), key)
                    for text, key in (("System", "system"), ("Light", "light"), ("Dark", "dark"))
                ],
                str(self.settings.value("theme", "system")),
            ),
        ):
            combo.blockSignals(True)
            combo.clear()
            for text, key in choices:
                combo.addItem(text, key)
            combo.setCurrentIndex(max(0, combo.findData(selected)))
            combo.blockSignals(False)
        self.language_combo.setAccessibleName(self._t("Language"))
        self.theme_combo.setAccessibleName(self._t("Appearance"))
        self.update_colors(self.mode)

    def update_colors(self, mode):
        self.mode = mode
        self.colors_label.setText(self._t("Colours: {theme}", theme=self._t(mode.title())))
        colors = theme_colors(mode, stored_colors(self.settings)[mode])
        for token, button in self.color_buttons.items():
            color = colors[token]
            swatch = QPixmap(16, 16)
            swatch.fill(QColor(color))
            painter = QPainter(swatch)
            painter.setPen(QPen(QColor(colors["text"])))
            painter.drawRect(0, 0, 15, 15)
            painter.end()
            button.setIcon(QIcon(swatch))
            button.setText(color.upper())
            message = "Background colour" if token == "background" else "Accent colour"
            button.setAccessibleName(f"{self._t(message)}: {color.upper()}")

    def choose_color(self, token):
        mode = self.mode
        colors = theme_colors(mode, stored_colors(self.settings)[mode])
        title = self._t("Background colour" if token == "background" else "Accent colour")
        color = QColorDialog.getColor(QColor(colors[token]), self, title)
        if color.isValid():
            self.settings.setValue(f"theme_colors/{mode}/{token}", color.name())
            self.changed.emit()

    def reset_colors(self):
        self.settings.remove(f"theme_colors/{self.mode}")
        self.changed.emit()

    def _language_changed(self):
        self.settings.setValue("language", self.language_combo.currentData())
        self.changed.emit()

    def _theme_changed(self):
        self.settings.setValue("theme", self.theme_combo.currentData())
        self.changed.emit()

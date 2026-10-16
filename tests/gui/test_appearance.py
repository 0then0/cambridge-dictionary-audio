"""Exercise desktop behavior offscreen with isolated settings and mocked HTTP."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6", reason="Install the gui group to run desktop tests")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from cambridge_audio.gui import app as gui  # noqa: E402
from tests.gui.helpers import wait_until


def test_application_has_a_renderable_icon_and_display_name(app):
    assert app.applicationDisplayName() == "Cambridge Dictionary Audio"
    assert not app.windowIcon().pixmap(128, 128).isNull()


def test_system_theme_tracks_color_scheme_changes(window, app, monkeypatch):
    monkeypatch.setattr(app.styleHints(), "colorScheme", lambda: Qt.ColorScheme.Dark)
    app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert window.effective_theme == "dark"
    window.preferences_dialog.theme_combo.setCurrentIndex(
        window.preferences_dialog.theme_combo.findData("light")
    )
    app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert window.effective_theme == "light"


def test_custom_colours_apply_and_survive_restart(window, app, monkeypatch):
    from PySide6.QtGui import QColor, QPalette

    from cambridge_audio.gui.preferences import QColorDialog
    from cambridge_audio.gui.theme import theme_colors

    dialog = window.preferences_dialog
    dialog.theme_combo.setCurrentIndex(dialog.theme_combo.findData("light"))
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args: QColor("#112244"))
    dialog.color_buttons["background"].click()
    assert app.palette().color(QPalette.ColorRole.Window).name() == "#112244"
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args: QColor("#ffee33"))
    dialog.color_buttons["accent"].click()
    assert app.palette().color(QPalette.ColorRole.Highlight).name() == "#ffee33"
    assert app.palette().color(QPalette.ColorRole.HighlightedText).name() == "#000000"
    assert dialog.color_buttons["accent"].text() == "#FFEE33"
    colors = theme_colors("light", {"background": "#112244", "accent": "#ffee33"})
    icon = window.settings_button.icon().pixmap(24, 24).toImage()
    opaque = {
        icon.pixelColor(x, y).name()
        for x in range(icon.width())
        for y in range(icon.height())
        if icon.pixelColor(x, y).alpha() > 250
    }
    assert colors["muted"] in opaque
    window.settings.sync()
    restored = gui.MainWindow(window.settings)
    try:
        assert restored.preferences_dialog.color_buttons["background"].text() == "#112244"
        assert app.palette().color(QPalette.ColorRole.Highlight).name() == "#ffee33"
    finally:
        restored.close()


def test_system_appearance_selects_custom_palette_and_updates_icons(window, app, monkeypatch):
    from PySide6.QtGui import QPalette

    window.settings.setValue("theme_colors/light/background", "#fff0dd")
    window.settings.setValue("theme_colors/dark/background", "#221133")
    monkeypatch.setattr(app.styleHints(), "colorScheme", lambda: Qt.ColorScheme.Dark)
    app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    dark_icon = window.settings_button.icon().cacheKey()
    assert app.palette().color(QPalette.ColorRole.Window).name() == "#221133"
    assert window.preferences_dialog.mode == "dark"
    monkeypatch.setattr(app.styleHints(), "colorScheme", lambda: Qt.ColorScheme.Light)
    app.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Light)
    assert app.palette().color(QPalette.ColorRole.Window).name() == "#fff0dd"
    assert window.preferences_dialog.mode == "light"
    assert window.settings_button.icon().cacheKey() != dark_icon


@pytest.mark.parametrize("orientation", [Qt.Orientation.Vertical, Qt.Orientation.Horizontal])
def test_scrollbar_handle_expands_on_hover_without_resizing_layout(app, orientation):
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QScrollBar, QWidget

    from cambridge_audio.gui.theme import apply_theme, theme_colors

    apply_theme(app, "dark")
    parent = QWidget()
    parent.resize(400, 400)
    bar = QScrollBar(orientation, parent)
    bar.setRange(0, 100)
    bar.setPageStep(25)
    if orientation == Qt.Orientation.Vertical:
        bar.setGeometry(20, 20, 12, 300)
    else:
        bar.setGeometry(20, 20, 300, 12)
    parent.show()
    QTest.mouseMove(parent, QPoint(350, 350))
    app.processEvents()
    color = theme_colors("dark")["scrollbar"]

    def thickness():
        image = bar.grab().toImage()
        # Sample through the middle of the handle, away from its rounded ends.
        return (
            sum(image.pixelColor(x, 20).name() == color for x in range(image.width()))
            if orientation == Qt.Orientation.Vertical
            else sum(image.pixelColor(20, y).name() == color for y in range(image.height()))
        )

    normal = thickness()
    size = bar.size()
    QTest.mouseMove(bar, QPoint(6, 20) if orientation == Qt.Orientation.Vertical else QPoint(20, 6))
    app.processEvents()
    # Hover may recolour the handle as well as change its width.
    hovered = bar.grab().toImage()
    # Count non-background pixels using the palette's two possible handle colours.
    colors = {color, theme_colors("dark")["scrollbar_hover"]}
    width = (
        sum(hovered.pixelColor(x, 20).name() in colors for x in range(hovered.width()))
        if orientation == Qt.Orientation.Vertical
        else sum(hovered.pixelColor(20, y).name() in colors for y in range(hovered.height()))
    )
    assert normal == 4
    assert width == 8
    assert bar.size() == size
    parent.close()


@pytest.mark.parametrize("language, theme, font_size", [("en", "light", 14), ("ru", "dark", 21)])
def test_short_combo_popups_show_every_row_without_scrolling(
    window, app, language, theme, font_size
):
    window.settings.setValue("language", language)
    window.settings.setValue("theme", theme)
    window._preferences_changed()
    window.preferences_dialog.show()
    for combo in (
        window.preferences_dialog.language_combo,
        window.preferences_dialog.theme_combo,
        window.accent_combo,
    ):
        font = combo.font()
        font.setPixelSize(font_size)
        combo.setFont(font)
        try:
            combo.showPopup()
            app.processEvents()
            view = combo.view()
            assert view.verticalScrollBar().maximum() == 0
            for row in range(combo.count()):
                rectangle = view.visualRect(view.model().index(row, 0))
                assert rectangle.top() >= 0
                assert rectangle.bottom() < view.viewport().height()
        finally:
            combo.hidePopup()


def test_long_combo_popup_keeps_scrolling_available(window, app):
    combo = gui.ComboBox(window)
    combo.addItems([f"Recording {index}" for index in range(100)])
    try:
        combo.showPopup()
        app.processEvents()
        assert combo.view().verticalScrollBar().maximum() > 0
        assert combo.view().height() < sum(combo.view().sizeHintForRow(i) for i in range(100))
    finally:
        combo.hidePopup()
        combo.close()


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("orientation", [Qt.Orientation.Vertical, Qt.Orientation.Horizontal])
def test_adaptive_scrollbar_animates_hover_and_keeps_drag_target(app, mode, orientation):
    from PySide6.QtCore import QAbstractAnimation, QPoint
    from PySide6.QtWidgets import QWidget

    from cambridge_audio.gui.theme import ScrollBar, apply_theme, theme_colors

    apply_theme(app, mode)
    parent = QWidget()
    parent.resize(400, 400)
    bar = ScrollBar(orientation, parent)
    bar.setRange(0, 100)
    bar.setPageStep(25)
    vertical = orientation == Qt.Orientation.Vertical
    bar.setGeometry(20, 20, 12 if vertical else 300, 300 if vertical else 12)
    parent.show()
    QTest.mouseMove(parent, QPoint(350, 350))
    app.processEvents()
    dimensions = bar.size()

    def thickness(color):
        image = bar.grab().toImage()
        return (
            sum(image.pixelColor(x, 20).name() == color for x in range(image.width()))
            if vertical
            else sum(image.pixelColor(20, y).name() == color for y in range(image.height()))
        )

    assert thickness(theme_colors(mode)["scrollbar"]) == 4
    point = QPoint(6, 20) if vertical else QPoint(20, 6)
    QTest.mouseMove(bar, point)
    wait_until(app, lambda: bar._hover_animation.state() == QAbstractAnimation.State.Stopped)
    assert thickness(theme_colors(mode)["scrollbar_hover"]) == 8
    assert bar.size() == dimensions
    QTest.mousePress(bar, Qt.MouseButton.LeftButton, pos=point)
    assert bar.isSliderDown()
    app.sendEvent(bar, QEvent(QEvent.Type.Leave))
    assert bar._expansion == 1.0
    end = QPoint(6, 150) if vertical else QPoint(150, 6)
    QTest.mouseMove(bar, end)
    QTest.mouseRelease(bar, Qt.MouseButton.LeftButton, pos=end)
    assert bar.value() > 0
    assert bar.size() == dimensions
    parent.close()


def test_scroll_area_smooth_wheel_matches_qt_bounds_and_preserves_precise_input(app):
    from PySide6.QtCore import QAbstractAnimation, QPoint, QPointF
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QScrollArea, QWidget

    from cambridge_audio.gui.theme import install_scrollbars

    def area(adaptive):
        widget = QScrollArea()
        widget.resize(400, 300)
        content = QWidget()
        content.setMinimumSize(800, 2000)
        widget.setWidget(content)
        if adaptive:
            install_scrollbars(widget)
        widget.show()
        return widget

    reference, animated = area(False), area(True)
    app.processEvents()
    native = reference.verticalScrollBar()
    bar = animated.verticalScrollBar()

    def wheel(widget, *, pixels=0, accepted=True):
        event = QWheelEvent(
            QPointF(100, 100),
            QPointF(widget.mapToGlobal(QPoint(100, 100))),
            QPoint(0, pixels),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate if pixels else Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        app.sendEvent(widget.viewport(), event)
        assert event.isAccepted() == accepted

    try:
        for _ in range(2):
            wheel(reference)
            wheel(animated)
        assert bar._scroll_animation.state() == QAbstractAnimation.State.Running
        assert bar.value() < native.value()
        wait_until(app, lambda: bar._scroll_animation.state() == QAbstractAnimation.State.Stopped)
        assert bar.value() == native.value() > 0
        wheel(reference, pixels=-15)
        wheel(animated, pixels=-15)
        assert bar._scroll_animation.state() == QAbstractAnimation.State.Stopped
        assert bar.value() == native.value()
        wheel(animated)
        QTest.keyClick(animated, Qt.Key.Key_PageDown)
        assert bar._scroll_animation.state() == QAbstractAnimation.State.Stopped
        bar.setValue(bar.maximum())
        wheel(animated, accepted=False)
        assert bar.value() == bar.maximum()
        assert bar._scroll_animation.state() == QAbstractAnimation.State.Stopped
    finally:
        reference.close()
        animated.close()

"""Short choice lists show every complete row; long lists remain bounded."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QAbstractItemView, QProxyStyle, QStyle  # noqa: E402

from cambridge_audio.gui.dialogs import ChoiceDialog  # noqa: E402
from cambridge_audio.gui.theme import ComboBox, ContentList  # noqa: E402


@pytest.mark.parametrize("long", [False, True])
def test_two_dialog_choices_fit_without_scrolling(window, app, long):
    text = "кот, кошка · существительное · a small animal with fur, four legs, and a tail "
    choices = [text * (3 if long else 1), "животное семейства кошачьих · a large wild cat"]
    dialog = ChoiceDialog(window, "Уточнить перевод", "Выберите перевод", choices)
    dialog.show()
    app.processEvents()
    try:
        view = dialog.list_view
        assert view.verticalScrollBar().maximum() == 0, {
            "view": view.size(),
            "viewport": view.viewport().size(),
            "scroll_mode": view.verticalScrollMode(),
            "rows": [
                view.visualRect(view.model().index(i, 0)) for i in range(view.model().rowCount())
            ],
        }
        assert view.horizontalScrollBar().maximum() == 0
        for row in range(2):
            rect = view.visualRect(view.model().index(row, 0))
            assert view.viewport().rect().contains(rect)
        if long:
            assert (
                view.visualRect(view.model().index(0, 0)).height() > view.fontMetrics().height() * 2
            )
        dialog.resize(440, dialog.height())
        app.processEvents()
        assert view.verticalScrollBar().maximum() == 0
        assert view.viewport().rect().contains(view.visualRect(view.model().index(1, 0)))
    finally:
        dialog.close()


def test_large_choice_dialog_is_bounded_and_scrollable(window, app):
    dialog = ChoiceDialog(window, "Choose", "Meaning", [f"meaning {i}" for i in range(100)])
    dialog.show()
    app.processEvents()
    try:
        assert dialog.list_view.height() <= dialog.screen().availableGeometry().height() // 2
        assert dialog.list_view.verticalScrollBar().maximum() > 0
    finally:
        dialog.close()


def test_inline_meanings_fit_two_wrapped_rows(window, app):
    view = ContentList(window)
    view.setSpacing(4)
    view.addItems(
        ["noun", "an organization where people can invest or borrow money " * 3, "river bank"]
    )
    view.resize(440, 120)
    view.show()
    app.processEvents()
    try:
        assert view.verticalScrollBar().maximum() == 0
        assert view.viewport().rect().contains(view.visualItemRect(view.item(2)))
        view.addItems(["another meaning"] * 50)
        app.processEvents()
        assert view.height() <= 360
        assert view.verticalScrollBar().maximum() > 0
    finally:
        view.close()


def test_short_combo_popup_fits_all_rows(window, app):
    combo = ComboBox(window)
    combo.addItems(["Американское (US)", "Британское (UK)"])
    combo.show()
    combo.showPopup()
    app.processEvents()
    try:
        assert combo.view().verticalScrollBar().maximum() == 0
        assert combo.view().horizontalScrollBar().maximum() == 0
    finally:
        combo.hidePopup()
        combo.close()


def test_choice_list_includes_viewport_margins_in_its_height(window, app):
    dialog = ChoiceDialog(window, "Choose", "Meaning", ["first meaning", "second meaning"])
    dialog.list_view.setViewportMargins(0, 6, 0, 8)
    dialog.show()
    app.processEvents()
    try:
        view = dialog.list_view
        assert view.verticalScrollBar().maximum() == 0
        assert view.viewport().rect().contains(view.visualRect(view.model().index(1, 0)))
    finally:
        dialog.close()


class ItemScrollStyle(QProxyStyle):
    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ItemView_ScrollMode:
            return QAbstractItemView.ScrollMode.ScrollPerItem.value
        return super().styleHint(hint, option, widget, returnData)


def test_short_wrapped_list_fits_with_native_item_scroll_default(window, app):
    dialog = ChoiceDialog(window, "Choose", "Meaning", ["long definition " * 18, "short meaning"])
    style = ItemScrollStyle("Windows")
    style.setParent(dialog)
    view = dialog.list_view
    view.setStyle(style)
    view.resetVerticalScrollMode()
    assert view.verticalScrollMode() == QAbstractItemView.ScrollMode.ScrollPerItem
    dialog.show()
    app.processEvents()
    try:
        assert view.verticalScrollBar().maximum() == 0
        assert view.viewport().rect().contains(view.visualRect(view.model().index(1, 0)))
    finally:
        dialog.close()

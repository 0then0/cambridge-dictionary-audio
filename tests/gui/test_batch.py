"""Batch word lists in the desktop app: offscreen, mocked HTTP, real worker threads."""

import os
import threading
from threading import Event
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6", reason="Install the gui group to run desktop tests")

from PySide6.QtCore import Qt  # noqa: E402

from cambridge_audio.batch import ERROR, FOUND, MISSING, PENDING  # noqa: E402
from cambridge_audio.dictionary import dictionary_url  # noqa: E402
from cambridge_audio.gui import workers  # noqa: E402
from cambridge_audio.library import scan_recordings  # noqa: E402
from tests.conftest import HTML  # noqa: E402
from tests.core.test_batch import LEAD, router  # noqa: E402
from tests.core.test_shared_audio import BANK  # noqa: E402
from tests.gui.helpers import wait_until  # noqa: E402

PAGES = {
    dictionary_url("lead"): LEAD,
    dictionary_url("hello"): HTML,
    dictionary_url("bank"): BANK,
    dictionary_url("good morning"): HTML.replace("hello", "gm").replace(">gm<", ">good morning<"),
}


@pytest.fixture
def mocked(monkeypatch, client):
    monkeypatch.setattr(workers, "CambridgeClient", lambda **kwargs: client)
    return client


def open_dialog(window, app):
    window.batch_button.click()
    dialog = window._batch_dialog
    assert dialog is not None and dialog.isVisible() and dialog.isModal()
    app.processEvents()
    return dialog


def close_dialog(window, app, dialog):
    dialog.close()
    wait_until(app, lambda: window._batch_dialog is None)


def check(dialog, query, definition, checked=True):
    dialog.query_list.setCurrentRow([r.query for r in dialog._rows].index(query))
    for index in range(dialog.meaning_list.count()):
        item = dialog.meaning_list.item(index)
        if definition in item.text():
            dialog.meaning_list.setCurrentRow(index)
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            return item
    raise AssertionError(definition)


def search(dialog, app, text):
    dialog.input_edit.setPlainText(text)
    dialog.search_button.click()
    wait_until(app, lambda: not dialog.busy())


def test_full_list_search_choose_preview_save_and_retry(window, app, mocked, monkeypatch):
    calls = router(mocked, PAGES)
    played = Mock()
    monkeypatch.setattr(window.player, "play", played)
    window.accent = "both"
    dialog = open_dialog(window, app)
    assert dialog.accent_combo.currentData() == "both"
    search(dialog, app, "hello\nlead\nLead\ngood morning\nzzqx\n")
    assert "lead (+1)" in dialog.input_summary.text()
    statuses = {r.query: r.status for r in dialog._rows}
    assert statuses == {
        "hello": FOUND,
        "lead": FOUND,
        "good morning": FOUND,
        "zzqx": MISSING,
    }
    assert len(calls) == 4
    assert "No result" in dialog.query_list.item(3).text()
    # Only unambiguous single-meaning words are preselected; lead needs choices.
    lead = dialog._row("lead")
    assert lead.selection == {}
    assert dialog.save_button.text() == "Save 4 recordings"
    dialog.query_list.setCurrentRow(1)
    assert "UK: not available" in dialog.meaning_list.item(0).text()
    assert dialog.error_label.isHidden()

    check(dialog, "lead", "a metal")
    check(dialog, "lead", "to guide")
    assert dialog._row("lead").unresolved() == 1
    assert not dialog.save_button.isEnabled()
    combo = dialog.region_combos["us"]
    assert combo.isEnabled() and combo.currentData() == ""
    assert not dialog.play_buttons["us"].isEnabled()
    combo.setCurrentIndex(2)
    combo.activated.emit(2)
    assert dialog._row("lead").unresolved() == 0
    assert "lead · verb · to guide · US /lid/, UK: not available" in [
        dialog.selection_list.item(i).text() for i in range(dialog.selection_list.count())
    ]

    # Listening uses a disposable preview and does not add a record.
    dialog.play_buttons["us"].click()
    wait_until(app, lambda: not dialog.busy())
    played.assert_called_once()
    assert not scan_recordings(window.output_dir)

    assert dialog.save_button.text() == "Save 6 recordings"
    router(mocked, PAGES, fail=("hello-uk.mp3",), calls=calls)
    dialog.save_button.click()
    wait_until(app, lambda: not dialog.busy())
    assert "Saved: 5" in dialog.summary_label.text()
    assert "failed: 1" in dialog.summary_label.text()
    assert "skipped queries: 1" in dialog.summary_label.text()
    assert dialog.save_button.text() == "Retry saving (1)"
    assert "Retry saving: hello (-, UK)" in dialog.retry_label.text()
    assert len(scan_recordings(window.output_dir)) == 5
    assert window.library_combo.count() == 5
    dialog.query_list.setCurrentRow(0)
    assert "Could not connect" in dialog.error_label.text()
    assert dialog.details_button.isVisible()
    assert "UK: failed" in dialog.meaning_list.item(0).text()

    calls.clear()
    router(mocked, PAGES, calls=calls)
    dialog.save_button.click()
    wait_until(app, lambda: not dialog.busy())
    assert calls == ["https://dictionary.cambridge.org/us/media/hello-uk.mp3"]
    assert "Saved: 6" in dialog.summary_label.text()
    assert not dialog.save_button.isEnabled()
    assert dialog.retry_label.isHidden()
    close_dialog(window, app, dialog)
    assert len(scan_recordings(window.output_dir)) == 6


def test_network_error_is_retried_without_repeating_successful_searches(window, app, mocked):
    calls = router(mocked, PAGES, fail=("english/lead",))
    dialog = open_dialog(window, app)
    search(dialog, app, "hello\nlead")
    assert [r.status for r in dialog._rows] == [FOUND, ERROR]
    assert "Search failed" in dialog.query_list.item(1).text()
    assert dialog.search_button.text() == "Retry search (1)"
    assert "Retry search: lead" in dialog.retry_label.text()
    dialog.query_list.setCurrentRow(1)
    assert "Could not connect" in dialog.error_label.text()
    assert "ConnectionError" in dialog.details_text.toPlainText()
    calls.clear()
    router(mocked, PAGES, calls=calls)
    dialog.search_button.click()
    wait_until(app, lambda: not dialog.busy())
    assert calls == [dictionary_url("lead")]
    assert [r.status for r in dialog._rows] == [FOUND, FOUND]
    close_dialog(window, app, dialog)


def test_invalid_and_oversized_lists_cannot_be_searched(window, app, mocked):
    dialog = open_dialog(window, app)
    dialog.input_edit.setPlainText("hello\nhttp://example.com")
    assert not dialog.search_button.isEnabled()
    assert "2: http://example.com" in dialog.input_summary.text()
    dialog.input_edit.setPlainText("\n".join(f"w{i}" for i in range(101)))
    assert not dialog.search_button.isEnabled()
    assert "101" in dialog.input_summary.text() and "100" in dialog.input_summary.text()
    assert dialog._rows == []
    close_dialog(window, app, dialog)


def test_changed_list_or_accent_invalidates_results_and_choices(window, app, mocked):
    router(mocked, PAGES)
    dialog = open_dialog(window, app)
    search(dialog, app, "hello\nbank")
    check(dialog, "bank", "river")
    generation = dialog._generation
    dialog.input_edit.setPlainText("bank\nlead")
    assert dialog._generation > generation
    assert [r.query for r in dialog._rows] == ["bank", "lead"]
    assert dialog._row("bank").selection  # Unchanged query keeps its result.
    assert dialog._row("lead").status == PENDING
    # A late result of the previous list is ignored.
    dialog._looked_up(generation, "bank", MISSING, (), "late")
    dialog._item_saved(generation, "bank:x", "saved", "")
    assert dialog._row("bank").status == FOUND and not dialog._row("bank").outcomes
    dialog.accent_combo.setCurrentIndex(dialog.accent_combo.findData("uk"))
    assert dialog._row("bank").selection == {}
    assert not dialog.save_button.isEnabled()
    close_dialog(window, app, dialog)


def test_cancel_search_keeps_finished_rows_and_gui_responsive(window, app, mocked):
    entered, release = Event(), Event()
    calls = router(mocked, PAGES)
    get = mocked.session.get.side_effect
    threads = []

    def slow(url, timeout=None):
        if "english/lead" in url:
            entered.set()
            release.wait(5)
        return get(url, timeout)

    mocked.session.get.side_effect = slow
    dialog = open_dialog(window, app)
    original = dialog._refresh_row

    def record_thread(row):
        threads.append(threading.current_thread())
        original(row)

    dialog._refresh_row = record_thread
    dialog.input_edit.setPlainText("hello\nlead\nbank")
    dialog.search_button.click()
    wait_until(app, entered.is_set)
    # The event loop keeps running while the worker waits for the network.
    wait_until(app, lambda: dialog._row("hello").status == FOUND)
    assert dialog.cancel_button.isEnabled()
    assert dialog.input_edit.isReadOnly() and not dialog.save_button.isEnabled()
    dialog.cancel_button.click()
    release.set()
    wait_until(app, lambda: not dialog.busy())
    assert dialog._row("hello").status == FOUND
    assert dialog._row("bank").status == PENDING
    assert dictionary_url("bank") not in calls
    assert "Cancelled" in dialog.status_label.text()
    assert threads and all(t is threading.main_thread() for t in threads)
    dialog.search_button.click()  # Continue with unfinished rows only.
    wait_until(app, lambda: not dialog.busy())
    assert calls.count(dictionary_url("hello")) == 1
    assert dialog._row("bank").status == FOUND
    close_dialog(window, app, dialog)


def test_cancel_and_close_during_save_keep_published_records(window, app, mocked):
    entered, release = Event(), Event()
    calls = router(mocked, PAGES)
    get = mocked.session.get.side_effect

    def slow(url, timeout=None):
        if url.endswith("hello-uk.mp3"):
            entered.set()
            release.wait(5)
        return get(url, timeout)

    dialog = open_dialog(window, app)
    dialog.accent_combo.setCurrentIndex(dialog.accent_combo.findData("both"))
    search(dialog, app, "hello\nbank")
    check(dialog, "bank", "money")
    mocked.session.get.side_effect = slow
    dialog.save_button.click()
    wait_until(app, entered.is_set)
    dialog.close()  # Closing while saving cancels and waits; it stays modal meanwhile.
    assert dialog.isVisible() and window._batch_dialog is dialog
    assert not dialog.cancel_button.isEnabled()
    assert "closes" in dialog.status_label.text()
    release.set()
    wait_until(app, lambda: window._batch_dialog is None)
    records = scan_recordings(window.output_dir)
    # The running item completes; the next one (bank) is never started.
    assert sorted((r.recording.word, r.recording.accent) for r in records) == [
        ("hello", "uk"),
        ("hello", "us"),
    ]
    assert not any("bank.mp3" in url for url in calls)
    assert window.library_combo.count() == 2


def test_main_window_entry_is_unavailable_during_other_work(window, app, mocked):
    window._set_busy(True)
    assert not window.batch_button.isEnabled()
    window._set_busy(False)
    window._translation_worker = object()
    window.open_batch()
    assert window._batch_dialog is None
    window._translation_worker = None
    dialog = open_dialog(window, app)
    window.open_batch()
    assert window._batch_dialog is dialog
    close_dialog(window, app, dialog)


def test_application_quit_joins_batch_worker(window, app, mocked):
    from threading import Timer

    entered, release = Event(), Event()
    router(mocked, PAGES)
    get = mocked.session.get.side_effect

    def slow(url, timeout=None):
        entered.set()
        release.wait(5)
        return get(url, timeout)

    mocked.session.get.side_effect = slow
    dialog = open_dialog(window, app)
    dialog.input_edit.setPlainText("hello\nlead")
    dialog.search_button.click()
    wait_until(app, entered.is_set)
    worker = dialog._worker
    releaser = Timer(0.05, release.set)
    releaser.start()
    try:
        window.shutdown()
        assert not worker.isRunning()
    finally:
        release.set()
        releaser.join()
    app.processEvents()
    assert mocked.session.get.call_count == 1
    close_dialog(window, app, dialog)


def test_dialog_texts_follow_interface_language(window, app, mocked):
    window.language = "ru"
    dialog = open_dialog(window, app)
    assert dialog.windowTitle() == "Добавить список слов"
    for button in (dialog.search_button, dialog.save_button, dialog.close_button):
        assert button.text() and "{" not in button.text()
    close_dialog(window, app, dialog)


def test_single_word_flow_is_unchanged(window, app, mocked):
    router(mocked, PAGES)
    window.word_edit.setText("hello")
    window.download_button.click()
    wait_until(app, lambda: window._worker is None)
    assert window.meaning_list.isVisible()
    window.save_button.click()
    wait_until(app, lambda: window._worker is None)
    assert [r.recording.word for r in scan_recordings(window.output_dir)] == ["hello"]
    assert window.batch_button.isEnabled()


def test_clicking_a_meaning_checkbox_keeps_that_meaning_current(window, app, mocked):
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest

    router(mocked, PAGES)
    dialog = open_dialog(window, app)
    search(dialog, app, "lead")
    dialog.resize(900, 900)
    app.processEvents()
    view = dialog.meaning_list
    rect = view.visualItemRect(view.item(1))
    # Click the check indicator of "to guide", which has two US recordings.
    QTest.mouseClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(rect.left() + 10, rect.center().y()),
    )
    app.processEvents()
    lead = dialog._row("lead")
    guide = next(e for e in lead.meanings() if e.definition == "to guide")
    assert view.item(1).checkState() == Qt.CheckState.Checked
    assert lead.selection == {guide.sense_id: {"us": ""}}
    assert view.currentRow() == 1
    combo = dialog.region_combos["us"]
    assert combo.isEnabled() and combo.count() == 3  # Placeholder and two recordings.
    combo.setCurrentIndex(2)
    combo.activated.emit(2)
    assert lead.selection[guide.sense_id]["us"] == combo.currentData()
    assert view.currentRow() == 1 and not lead.unresolved()
    close_dialog(window, app, dialog)

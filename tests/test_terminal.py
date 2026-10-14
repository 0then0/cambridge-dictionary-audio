"""Exercise the actual terminal UI without a network, player or display server."""

import asyncio
import time
from contextlib import suppress
from threading import Event
from unittest.mock import Mock

import pytest
from conftest import response
from textual.widgets import Button, Checkbox, DataTable, Input, Select, Static
from textual.worker import WorkerCancelled, WorkerFailed

from cambridge_audio import terminal
from cambridge_audio.library import read_recording, save_metadata
from cambridge_audio.service import Recording
from cambridge_audio.terminal import CambridgeApp, Options, Settings


def saved(directory, word="hello", accent="us"):
    record = Recording(word, accent, directory / f"{word}.{accent}.mp3", "heˈloʊ", "A greeting")
    record.path.write_bytes(b"ID3saved")
    save_metadata(record, ("привет",), "russian")
    return record


async def finish_download(app, pilot):
    await app.workers.wait_for_complete()
    await pilot.pause()


async def wait_for_ui(pilot, predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        await pilot.pause(0.01)
    assert predicate(), "Terminal UI did not reach the expected state"


@pytest.mark.parametrize("size", [(110, 34), (80, 24), (60, 30)])
def test_saved_library_keyboard_playback_filter_and_translation(tmp_path, monkeypatch, size):
    record = saved(tmp_path)
    saved(tmp_path, "world", "uk")
    player = Mock()
    monkeypatch.setattr(terminal, "play_audio", player)
    client = Mock(side_effect=AssertionError("Saved audio must open offline"))
    monkeypatch.setattr(terminal, "CambridgeClient", client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            assert app.query_one("#recordings", DataTable).row_count == 2
            assert app.query_one("#detail-scroll").size.height >= 3
            await wait_for_ui(pilot, lambda: app.selected is not None)
            assert not app.query_one("#translation", Static).display
            app.query_one("#show-translation", Checkbox).value = True
            await wait_for_ui(pilot, lambda: app.query_one("#translation", Static).display)
            app.query_one("#query", Input).value = "HELLO"
            await pilot.press("enter")
            await pilot.pause()
            assert app.selected.recording.path == record.path
            assert app.query_one("#recordings", DataTable).row_count == 1
            assert not app.busy
            await pilot.press("ctrl+p")
            await finish_download(app, pilot)
            player.assert_called_once_with(record.path, "en", stop=app.stop_playback)
            client.assert_not_called()
            await pilot.press("f1")
            await pilot.pause()
            assert isinstance(app.screen, terminal.Help)
            await pilot.press("escape")
            assert not isinstance(app.screen, terminal.Help)

    asyncio.run(scenario())


def test_download_metadata_survives_restart(tmp_path, monkeypatch, client, html, mp3):
    client.session.get.side_effect = [response(html), response(mp3)]
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *a, **kw: client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test() as pilot:
            app.query_one("#query", Input).value = "hello"
            await pilot.press("enter")
            await finish_download(app, pilot)
            assert not app.busy
            assert app.selected.recording.ipa == "heˈloʊ"
            assert "used when meeting" in app.selected.recording.definition
            assert app.query_one("#recordings", DataTable).row_count == 1
        second = CambridgeApp(Options(tmp_path, play=False))
        async with second.run_test() as pilot:
            await pilot.pause()
            assert second.selected.recording.ipa == "heˈloʊ"
            second.query_one("#query", Input).value = "hello"
            await pilot.press("enter")
            assert not second.busy
        assert client.session.get.call_count == 2

    asyncio.run(scenario())


def test_both_downloads_only_missing_accent(tmp_path, monkeypatch, client, html, mp3):
    existing = saved(tmp_path)
    client.session.get.side_effect = [response(html), response(mp3)]
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *a, **kw: client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, accent="both", play=False))
        async with app.run_test() as pilot:
            app.query_one("#query", Input).value = "hello"
            await pilot.press("enter")
            await finish_download(app, pilot)
            assert existing.path.read_bytes() == b"ID3saved"
            assert (tmp_path / "hello.uk.mp3").read_bytes() == mp3
            assert read_recording(existing.path).translations == ("привет",)
        assert client.session.get.call_count == 2

    asyncio.run(scenario())


def test_partial_failure_keeps_audio_and_metadata(tmp_path, monkeypatch, client, html, mp3):
    client.session.get.side_effect = [
        response(html),
        response(mp3),
        response("blocked", status=429),
    ]
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *a, **kw: client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, accent="both", play=False))
        async with app.run_test() as pilot:
            app.query_one("#query", Input).value = "hello"
            await pilot.press("enter")
            await finish_download(app, pilot)
            assert not app.busy
            assert app.query_one("#status", Static).has_class("error")
            assert read_recording(tmp_path / "hello.uk.mp3").recording.ipa == "heˈləʊ"
            assert not (tmp_path / "hello.us.mp3").exists()

    asyncio.run(scenario())


def test_replacement_requires_confirmation_even_with_overwrite_flag(
    tmp_path, monkeypatch, client, html, mp3
):
    record = saved(tmp_path)
    client.session.get.side_effect = [response(html), response(mp3)]
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *a, **kw: client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False, overwrite=True))
        async with app.run_test() as pilot:
            app.query_one("#query", Input).value = "hello"
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, terminal.ConfirmReplace)
            await pilot.click("#keep")
            assert record.path.read_bytes() == b"ID3saved"
            client.session.get.assert_not_called()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.click("#replace")
            await finish_download(app, pilot)
            assert record.path.read_bytes() == mp3

    asyncio.run(scenario())


def test_settings_switch_language_theme_and_folder_and_escape_discards(tmp_path):
    saved(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    saved(other, "world")

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test(size=(110, 45)) as pilot:
            await pilot.press("ctrl+s")
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, Settings)
            screen.query_one("#language", Select).value = "ru"
            screen.query_one("#theme", Select).value = "cambridge-light"
            screen.query_one("#directory", Input).value = str(other)
            screen.query_one("#translation", Input).value = "russian"
            screen.query_one("#apply", Button).press()
            await wait_for_ui(
                pilot,
                lambda: app.selected is not None and app.selected.recording.word == "world",
            )
            assert app.options.language == "ru"
            assert app.options.translation == "russian"
            assert app.theme == "cambridge-light"
            assert app.options.directory == other
            assert app.query_one("#download", Button).label.plain == "Скачать"
            assert app.selected.recording.word == "world"
            await pilot.press("ctrl+s")
            await pilot.pause()
            app.screen.query_one("#accent", Select).value = "both"
            await pilot.press("escape")
            assert app.options.accent == "us"

    asyncio.run(scenario())


@pytest.mark.parametrize("quit_requested", [False, True])
def test_cancel_waits_for_request_and_retains_already_saved_file(
    tmp_path, monkeypatch, client, html, mp3, quit_requested
):
    started = Event()
    proceed = Event()

    def get(*args, **kwargs):
        call = client.session.get.call_count
        if call == 1:
            return response(html)
        if call == 2:
            started.set()
            assert proceed.wait(10)
            return response(mp3)
        raise AssertionError("Cancelled request must not download the second accent")

    client.session.get.side_effect = get
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *a, **kw: client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False, accent="both"))
        async with app.run_test() as pilot:
            try:
                app.query_one("#query", Input).value = "hello"
                await pilot.press("enter")
                assert await asyncio.to_thread(started.wait, 5)
                assert app.busy
                await pilot.press("ctrl+q" if quit_requested else "ctrl+c")
                assert app.cancel_download.is_set()
                assert app.busy  # Don't tear down while the MP3 save is in progress.
                proceed.set()
                await finish_download(app, pilot)
                assert not app.busy
                assert (tmp_path / "hello.uk.mp3").read_bytes() == mp3
                assert not (tmp_path / "hello.us.mp3").exists()
            finally:
                proceed.set()

    asyncio.run(scenario())


@pytest.mark.parametrize("key", ["ctrl+p", "ctrl+q"])
def test_playback_can_be_stopped_or_closed_without_waiting_for_audio(tmp_path, monkeypatch, key):
    saved(tmp_path)
    started = Event()

    def play(path, language, *, stop):
        started.set()
        assert stop.wait(5)

    monkeypatch.setattr(terminal, "play_audio", play)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test() as pilot:
            try:
                await pilot.pause()
                await pilot.press("ctrl+p")
                assert await asyncio.to_thread(started.wait, 5)
                assert app.playing
                assert app.query_one("#play", Button).label.plain == "Stop"
                await pilot.press(key)
                await finish_download(app, pilot)
                assert not app.playing
            finally:
                app.stop_playback.set()

    asyncio.run(scenario())


def test_unexpected_worker_error_does_not_leave_controls_locked(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal, "CambridgeClient", Mock(side_effect=RuntimeError("bad client")))

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test() as pilot:
            app.start_download("hello", "us")
            worker = next(iter(app.workers))
            with pytest.raises(WorkerFailed, match="bad client"):
                await worker.wait()
            await pilot.pause()
            assert not app.busy
            assert not app.query_one("#download", Button).disabled
            assert app.query_one("#status", Static).has_class("error")

    asyncio.run(scenario())


@pytest.mark.parametrize("translation_language", [None, "french"])
def test_translation_checkbox_fetches_missing_details_and_caches_both_accents(
    tmp_path, monkeypatch, client, translation_language
):
    first = saved(tmp_path)
    second = saved(tmp_path, accent="uk")
    for record in (first, second):
        save_metadata(record)  # Reproduce a normal download without --translation.
    client.translations = Mock(return_value=("bonjour" if translation_language else "привет",))
    client.download = Mock(side_effect=AssertionError("MP3 must not be downloaded again"))
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *a, **kw: client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False, translation=translation_language))
        async with app.run_test() as pilot:
            await pilot.pause()
            checkbox = app.query_one("#show-translation", Checkbox)
            if not checkbox.value:
                await pilot.click("#show-translation")  # Exercise a real click, not just .value.
            await finish_download(app, pilot)
            expected = client.translations.return_value
            assert app.selected.translations == expected
            assert app.query_one("#translation", Static).display
            assert app.query_one("#translation", Static).render().plain == expected[0]
            await pilot.click("#show-translation")
            assert not app.query_one("#translation", Static).display
            await pilot.click("#show-translation")
            assert app.query_one("#translation", Static).display
            client.translations.assert_called_once_with("hello", translation_language or "russian")
            for record in (first, second):
                assert record.path.read_bytes() == b"ID3saved"
                assert read_recording(record.path).translations == expected
        restored = CambridgeApp(Options(tmp_path, play=False, translation=translation_language))
        async with restored.run_test() as pilot:
            if not restored.query_one("#show-translation", Checkbox).value:
                await pilot.click("#show-translation")
            assert restored.selected.translations == expected
            client.translations.assert_called_once()
        client.download.assert_not_called()

    asyncio.run(scenario())


@pytest.mark.parametrize("result", [(), terminal.CambridgeError("HTTP 429")])
def test_translation_failure_is_visible_and_toggle_retries(tmp_path, monkeypatch, client, result):
    record = saved(tmp_path)
    save_metadata(record)
    client.translations = Mock(side_effect=[result, ("привет",)])
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *a, **kw: client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False, language="ru"))
        async with app.run_test() as pilot:
            await pilot.click("#show-translation")
            await finish_download(app, pilot)
            widget = app.query_one("#translation", Static)
            assert widget.display
            assert (
                "429" in widget.render().plain
                if isinstance(result, Exception)
                else ("Перевод не найден" in widget.render().plain)
            )
            app.show_recording(app.selected)
            await pilot.pause()
            assert client.translations.call_count == 1  # No automatic retry loop.
            await pilot.click("#show-translation")
            assert not widget.display
            await pilot.click("#show-translation")
            await finish_download(app, pilot)
            assert widget.render().plain == "привет"
            assert client.translations.call_count == 2
            assert record.path.read_bytes() == b"ID3saved"

    asyncio.run(scenario())


def test_changing_selection_or_hiding_translation_during_request_does_not_show_stale_result(
    tmp_path, monkeypatch, client
):
    record = saved(tmp_path)
    save_metadata(record)
    other = saved(tmp_path, "world")
    started = Event()
    proceed = Event()

    def translations(word, language):
        started.set()
        assert proceed.wait(5)
        return ("привет",)

    client.translations = Mock(side_effect=translations)
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *a, **kw: client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test() as pilot:
            try:
                await pilot.click("#show-translation")
                assert await asyncio.to_thread(started.wait, 5)
                assert (
                    app.query_one("#translation", Static).render().plain == "Loading translation..."
                )
                app.show_recording(read_recording(other.path))
                await pilot.click("#show-translation")
                proceed.set()
                await finish_download(app, pilot)
                assert app.selected.recording.path == other.path
                assert not app.query_one("#translation", Static).display
                assert read_recording(record.path).translations == ("привет",)
                client.translations.assert_called_once()
            finally:
                proceed.set()

    asyncio.run(scenario())


def test_quit_during_translation_waits_for_request_and_keeps_audio(tmp_path, monkeypatch, client):
    record = saved(tmp_path)
    save_metadata(record)
    started = Event()
    proceed = Event()

    def translations(word, language):
        started.set()
        assert proceed.wait(5)
        return ("привет",)

    client.translations = Mock(side_effect=translations)
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *a, **kw: client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test() as pilot:
            try:
                await pilot.click("#show-translation")
                assert await asyncio.to_thread(started.wait, 5)
                await pilot.press("ctrl+q")
                assert app.quit_pending
                assert app.translation_pending is not None
                proceed.set()
                # Textual may cancel the worker's async wrapper during shutdown,
                # after the request result and metadata have already been processed.
                with suppress(WorkerCancelled):
                    await finish_download(app, pilot)
                assert app.translation_pending is None
                assert record.path.read_bytes() == b"ID3saved"
                assert read_recording(record.path).translations == ("привет",)
            finally:
                proceed.set()

    asyncio.run(scenario())


def test_search_and_library_enter_keep_cursor_details_and_playback_in_sync(tmp_path, monkeypatch):
    us = saved(tmp_path)
    saved(tmp_path, accent="uk")
    player = Mock()
    monkeypatch.setattr(terminal, "play_audio", player)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test() as pilot:
            table = app.query_one("#recordings", DataTable)
            table.move_cursor(row=0)
            await pilot.pause()
            assert app.selected.recording.accent == "uk"
            query = app.query_one("#query", Input)
            query.value = "hello"
            query.focus()
            await pilot.press("enter")
            await pilot.pause()
            assert app.selected.recording.accent == "us"
            assert table.get_row_at(table.cursor_row)[1] == "US"
            table.focus()
            await pilot.press("enter")
            await finish_download(app, pilot)
            assert player.call_args.args[0] == us.path

    asyncio.run(scenario())


def test_alias_translation_is_cached_once_and_both_accents_start(tmp_path, monkeypatch, client):
    target = tmp_path / "hello.mp3"
    target.write_bytes(b"ID3saved")
    for accent in ("us", "uk"):
        try:
            (tmp_path / f"hello.{accent}.mp3").symlink_to(target.name)
        except OSError:
            pytest.skip("Creating symlinks requires platform permission")
    client.translations = Mock(return_value=("привет",))
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *a, **kw: client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False, translation="russian"))
        async with app.run_test() as pilot:
            await finish_download(app, pilot)
            assert app.query_one("#recordings", DataTable).row_count == 2
            assert app.query_one("#translation", Static).render().plain == "привет"
            await pilot.pause()
            client.translations.assert_called_once_with("hello", "russian")

    asyncio.run(scenario())


def test_changing_translation_language_refetches_and_survives_restart(
    tmp_path, monkeypatch, client
):
    record = saved(tmp_path)
    client.translations = Mock(return_value=("bonjour",))
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *a, **kw: client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False, translation="russian"))
        async with app.run_test() as pilot:
            await pilot.press("ctrl+s")
            app.screen.query_one("#translation", Input).value = "french"
            app.screen.query_one("#apply", Button).press()
            await pilot.pause()
            await finish_download(app, pilot)
            assert app.query_one("#translation", Static).render().plain == "bonjour"
            assert read_recording(record.path).translation_language == "french"
        restored = CambridgeApp(Options(tmp_path, play=False, translation="french"))
        async with restored.run_test() as pilot:
            await finish_download(restored, pilot)
            assert restored.query_one("#translation", Static).render().plain == "bonjour"
            client.translations.assert_called_once_with("hello", "french")

    asyncio.run(scenario())


def test_empty_recording_is_not_opened_and_requires_replace_confirmation(tmp_path, monkeypatch):
    path = tmp_path / "hello.us.mp3"
    path.touch()
    confirm = Mock()
    monkeypatch.setattr(CambridgeApp, "confirm_replace", confirm)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test() as pilot:
            assert app.query_one("#recordings", DataTable).row_count == 0
            app.query_one("#query", Input).value = "hello"
            await pilot.press("enter")
            confirm.assert_called_once_with("hello", "us")
            assert app.selected is None
            assert path.read_bytes() == b""

    asyncio.run(scenario())

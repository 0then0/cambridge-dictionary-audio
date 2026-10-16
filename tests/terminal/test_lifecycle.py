"""Exercise the actual terminal UI without a network, player or display server."""

import asyncio
from threading import Event
from unittest.mock import Mock

import pytest
from textual.widgets import Button, DataTable, Input

from cambridge_audio.terminal import CambridgeApp, Options
from cambridge_audio.terminal import app as terminal
from tests.helpers import response
from tests.terminal.helpers import finish_download, saved


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
                app.start_download("hello", "both")
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


@pytest.mark.parametrize("quit_requested", [False, True])
def test_cancel_or_quit_interrupts_rate_limit_backoff(
    tmp_path, monkeypatch, request_clock, quit_requested
):
    from cambridge_audio import dictionary

    entered, release = Event(), Event()
    clients = []

    def create_client(*args, **kwargs):
        client = dictionary.CambridgeClient(*args, **kwargs)
        client.session.get = Mock(return_value=response("limited", status=429))
        clients.append(client)
        return client

    def waiting(seconds):
        entered.set()
        assert release.wait(5)
        request_clock.now += seconds

    monkeypatch.setattr(terminal, "CambridgeClient", create_client)
    monkeypatch.setattr(dictionary, "sleep", waiting)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test() as pilot:
            try:
                app.query_one("#query", Input).value = "hello"
                await pilot.press("enter")
                assert await asyncio.to_thread(entered.wait, 5)
                await pilot.press("ctrl+q" if quit_requested else "ctrl+c")
                assert app.cancel_download.is_set()
                release.set()
                await finish_download(app, pilot)
                assert not app.busy
            finally:
                release.set()
        assert clients[0].session.get.call_count == 1
        assert not (tmp_path / "hello.us.mp3").exists()

    asyncio.run(scenario())

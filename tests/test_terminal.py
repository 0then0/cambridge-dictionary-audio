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
def test_button_labels_fit_after_language_and_playback_changes(tmp_path, monkeypatch, size):
    saved(tmp_path)

    def player(path, language, *, stop):
        assert stop.wait(5), "Playback was not stopped"

    monkeypatch.setattr(terminal, "play_audio", player)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test(size=size) as pilot:
            await wait_for_ui(pilot, lambda: app.selected is not None)
            assert not app.query("#logo")

            async def check_labels(expected):
                await pilot.pause()
                for key, text in expected.items():
                    button = app.query_one(f"#{key}", Button)
                    assert button.label.plain == text
                    painted = "\n".join(
                        strip.text for strip in button.render_lines(button.region.reset_offset)
                    )
                    assert text in painted

            await check_labels({"play": "Play", "again": "Download again"})
            await pilot.press("ctrl+s")
            app.screen.query_one("#language", Select).value = "ru"
            app.screen.query_one("#apply", Button).press()
            await wait_for_ui(pilot, lambda: not isinstance(app.screen, Settings))
            await check_labels(
                {"download": "Скачать", "play": "Слушать", "again": "Скачать заново"}
            )
            await pilot.press("ctrl+p")
            await wait_for_ui(pilot, lambda: app.playing)
            await check_labels({"play": "Стоп"})
            await pilot.press("ctrl+p")
            await wait_for_ui(pilot, lambda: not app.playing)
            await check_labels({"play": "Слушать"})
            await pilot.press("ctrl+s")
            app.screen.query_one("#language", Select).value = "en"
            app.screen.query_one("#apply", Button).press()
            await wait_for_ui(pilot, lambda: not isinstance(app.screen, Settings))
            await check_labels({"download": "Download", "play": "Play", "again": "Download again"})

    asyncio.run(scenario())


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
            screen.query_one("#translation", Checkbox).value = True
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


@pytest.mark.parametrize("translation_language", [None, "russian"])
def test_translation_checkbox_fetches_missing_details_and_caches_both_accents(
    tmp_path, monkeypatch, client, translation_language
):
    first = saved(tmp_path)
    second = saved(tmp_path, accent="uk")
    for record in (first, second):
        save_metadata(
            record, translation_cache=()
        )  # Reproduce a normal download without --translation.
    client.translations = Mock(return_value=("привет",))
    client.download = Mock(side_effect=AssertionError("MP3 must not be downloaded again"))
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *a, **kw: client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False, translation=translation_language))
        async with app.run_test() as pilot:
            await wait_for_ui(pilot, lambda: app.selected is not None)
            checkbox = app.query_one("#show-translation", Checkbox)
            if not checkbox.value:
                await pilot.click("#show-translation")  # Exercise a real click, not just .value.
            await finish_download(app, pilot)
            expected = client.translations.return_value
            assert app.selected.translations == expected
            assert app.query_one("#translation", Static).display
            assert (
                f"Cambridge\n{expected[0]}" in app.query_one("#translation", Static).render().plain
            )
            await pilot.click("#show-translation")
            await wait_for_ui(
                pilot,
                lambda: not checkbox.value and not app.query_one("#translation", Static).display,
            )
            await pilot.click("#show-translation")
            await wait_for_ui(
                pilot, lambda: checkbox.value and app.query_one("#translation", Static).display
            )
            client.translations.assert_called_once_with("hello", translation_language or "russian")
            for record in (first, second):
                assert record.path.read_bytes() == b"ID3saved"
                assert read_recording(record.path).translations == expected
        restored = CambridgeApp(Options(tmp_path, play=False, translation=translation_language))
        async with restored.run_test() as pilot:
            await wait_for_ui(pilot, lambda: restored.selected is not None)
            if not restored.query_one("#show-translation", Checkbox).value:
                await pilot.click("#show-translation")
            assert restored.selected.translations == expected
            client.translations.assert_called_once()
        client.download.assert_not_called()

    asyncio.run(scenario())


@pytest.mark.parametrize("result", [(), terminal.CambridgeError("HTTP 429")])
def test_translation_failure_is_visible_and_toggle_retries(tmp_path, monkeypatch, client, result):
    record = saved(tmp_path)
    save_metadata(record, translation_cache=())
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
                else ("not installed" in widget.render().plain)
            )
            app.show_recording(app.selected)
            await pilot.pause()
            assert client.translations.call_count == 1  # No automatic retry loop.
            await pilot.click("#show-translation")
            assert not widget.display
            await pilot.click("#show-translation")
            await finish_download(app, pilot)
            assert "Cambridge\nпривет" in widget.render().plain
            assert client.translations.call_count == 2
            assert record.path.read_bytes() == b"ID3saved"

    asyncio.run(scenario())


def test_changing_selection_or_hiding_translation_during_request_does_not_show_stale_result(
    tmp_path, monkeypatch, client
):
    record = saved(tmp_path)
    save_metadata(record, translation_cache=())
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
    save_metadata(record, translation_cache=())
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
            assert "Cambridge\nпривет" in app.query_one("#translation", Static).render().plain
            await pilot.pause()
            client.translations.assert_called_once_with("hello", "russian")

    asyncio.run(scenario())


def test_settings_toggle_russian_translation_preserves_foreign_edits(tmp_path, monkeypatch):
    from cambridge_audio.translations import cached_translation, edit_translation

    record = saved(tmp_path)
    edit_translation(read_recording(record.path), "french", "salut personnel")
    original = record.path.with_suffix(".json").read_bytes()
    client = Mock(side_effect=AssertionError("cached Russian translation"))
    monkeypatch.setattr(terminal, "CambridgeClient", client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test() as pilot:
            await pilot.press("ctrl+s")
            assert not app.screen.query_one("#translation", Checkbox).value
            assert not app.screen.query("Input#translation")
            app.screen.query_one("#translation", Checkbox).value = True
            app.screen.query_one("#apply", Button).press()
            await wait_for_ui(
                pilot,
                lambda: (
                    not isinstance(app.screen, Settings)
                    and "привет" in app.query_one("#translation", Static).render().plain
                ),
            )
            assert app.options.translation == "russian"
            assert "Cambridge\nпривет" in app.query_one("#translation", Static).render().plain
            await pilot.press("ctrl+s")
            assert app.screen.query_one("#translation", Checkbox).value
            app.screen.query_one("#translation", Checkbox).value = False
            app.screen.query_one("#apply", Button).press()
            await wait_for_ui(pilot, lambda: not isinstance(app.screen, Settings))
            assert app.options.translation is None
            assert not app.query_one("#translation", Static).display
        restarted = CambridgeApp(Options(tmp_path, play=False, translation="russian"))
        async with restarted.run_test() as pilot:
            assert "Cambridge\nпривет" in restarted.query_one("#translation", Static).render().plain
        assert cached_translation(read_recording(record.path), "french").texts == (
            "salut personnel",
        )
        assert record.path.with_suffix(".json").read_bytes() == original
        client.assert_not_called()

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


def test_tui_pronunciation_choice_saves_matching_variant(tmp_path, monkeypatch, client, html):
    other = (
        html.replace("used when meeting someone", "a different sense")
        .replace("hello-us.mp3", "other-us.mp3")
        .replace("heˈloʊ", "other-ipa")
    )
    client.session.get.side_effect = [response(html + other), response(b"ID3selected")]
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *a, **kwargs: client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test() as pilot:
            app.query_one("#query", Input).value = "hello"
            app.submit()
            await wait_for_ui(
                pilot,
                lambda: (
                    isinstance(app.screen, terminal.ChooseOption)
                    and bool(app.screen.query("#choice"))
                    and bool(app.screen.query("#accept"))
                    and app.screen.query_one("#accept", Button).is_mounted
                ),
            )
            selector = app.screen.query_one("#choice", Select)
            selected_id = app.screen.choices[1][1]
            selector.value = selected_id
            app.screen.query_one("#accept", Button).press()
            await wait_for_ui(pilot, lambda: not app.busy and app.selected is not None)
            record = app.selected.recording
            assert record.definition == "a different sense"
            assert record.ipa == "other-ipa"
            assert record.variant_id == selected_id
            assert record.path.read_bytes() == b"ID3selected"
            assert read_recording(record.path).recording == record
            assert client.session.get.call_count == 2
            await finish_download(app, pilot)

    asyncio.run(scenario())


def test_tui_edit_reset_and_export_collection(tmp_path, monkeypatch):
    first = saved(tmp_path)
    saved(tmp_path, "world", "uk")
    monkeypatch.setattr(terminal, "CambridgeClient", Mock(side_effect=AssertionError("offline")))

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test() as pilot:
            app.show_recording(read_recording(first.path))
            app.action_edit_translation()
            await wait_for_ui(
                pilot,
                lambda: (
                    isinstance(app.screen, terminal.ChooseOption)
                    and bool(app.screen.query("#value"))
                ),
            )
            app.screen.query_one("#value", Input).value = "personal"
            app.screen.query_one("#accept", Button).press()
            await wait_for_ui(pilot, lambda: not isinstance(app.screen, terminal.ChooseOption))
            from cambridge_audio.translations import cached_translation

            assert cached_translation(read_recording(first.path), "russian").texts == ("personal",)
            app.action_edit_translation()
            await pilot.pause()
            app.screen.query_one("#choice", Select).value = "reset"
            app.screen.query_one("#accept", Button).press()
            await wait_for_ui(pilot, lambda: not isinstance(app.screen, terminal.ChooseOption))
            assert cached_translation(read_recording(first.path), "russian").texts == ("привет",)
            app.action_export()
            await pilot.pause()
            app.screen.query_one("#choice", Select).value = "all"
            destination = tmp_path / "export"
            app.screen.query_one("#value", Input).value = str(destination)
            app.screen.query_one("#accept", Button).press()
            await wait_for_ui(pilot, lambda: (destination / "collection.tsv").exists())
            assert len(list((destination / "media").iterdir())) == 2
            assert first.path.read_bytes() == b"ID3saved"

    asyncio.run(scenario())


@pytest.mark.parametrize("language,size", [("en", (110, 34)), ("ru", (60, 30))])
def test_translation_senses_are_readable_and_selection_keeps_internal_ids(
    tmp_path, monkeypatch, language, size
):
    from cambridge_audio.translations import (
        TranslationOption,
        TranslationResult,
        persist_translation,
    )

    record = saved(tmp_path)
    result = TranslationResult(
        "russian",
        record.sense_id,
        "Cambridge",
        (
            TranslationOption(
                "775e305f512eae1a051b5251",
                ("привет! здравствуй(те)!",),
                part_of_speech="exclamation",
            ),
            TranslationOption("38183dda1906f89bec3a6e3d", ("алло!",), part_of_speech="exclamation"),
        ),
    )
    persist_translation(read_recording(record.path), result)
    monkeypatch.setattr(terminal, "CambridgeClient", Mock(side_effect=AssertionError("cached")))

    async def scenario():
        app = CambridgeApp(Options(tmp_path, language=language, play=False, translation="russian"))
        async with app.run_test(size=size) as pilot:
            widget = app.query_one("#translation", Static)
            text = widget.render()
            assert "1. привет! здравствуй(те)!" in text.plain
            assert "2. алло!" in text.plain
            assert "Ctrl+T" in text.plain
            assert "unspecified sense" not in text.plain
            for option in result.options:
                assert option.id not in text.plain
            assert ("междометие" if language == "ru" else "exclamation") in text.plain
            assert any(getattr(span.style, "dim", False) for span in text.spans)
            await pilot.press("ctrl+t")
            await wait_for_ui(
                pilot,
                lambda: (
                    isinstance(app.screen, terminal.ChooseOption)
                    and bool(app.screen.query("#choice"))
                ),
            )
            assert {o.id for o in result.options} <= {value for _, value in app.screen.choices}
            assert all("unspecified sense" not in label for label, _ in app.screen.choices)
            app.screen.query_one("#choice", Select).value = result.options[1].id
            app.screen.query_one("#accept", Button).press()
            await wait_for_ui(pilot, lambda: not isinstance(app.screen, terminal.ChooseOption))
            text = app.query_one("#translation", Static).render().plain
            assert "алло!" in text and "привет!" not in text
            assert "Ctrl+T" not in text
            assert (
                read_recording(record.path).translation_cache[-1].selected_id
                == result.options[1].id
            )

    asyncio.run(scenario())


@pytest.mark.parametrize("language,size", [("en", (110, 34)), ("ru", (60, 30))])
def test_about_keyboard_help_link_and_return_to_library(tmp_path, monkeypatch, language, size):
    from importlib.metadata import version

    from textual.widgets import Link

    record = saved(tmp_path)
    monkeypatch.setattr(terminal, "CambridgeClient", Mock(side_effect=AssertionError("offline")))

    async def scenario():
        app = CambridgeApp(Options(tmp_path, language=language, play=False))
        open_url = Mock()
        monkeypatch.setattr(app, "open_url", open_url)
        async with app.run_test(size=size) as pilot:
            await pilot.press("f2")
            await wait_for_ui(
                pilot,
                lambda: (
                    isinstance(app.screen, terminal.About)
                    and bool(app.screen.query("#about-version"))
                ),
            )
            assert (
                version("cambridge-dictionary-audio")
                in app.screen.query_one("#about-version", Static).render().plain
            )
            assert ("Версия" if language == "ru" else "Version") in app.screen.query_one(
                "#about-version", Static
            ).render().plain
            link = app.screen.query_one("#about-repository", Link)
            assert link.url == "https://github.com/0then0/cambridge-dictionary-audio"
            link.focus()
            await pilot.press("enter")
            open_url.assert_called_once_with(link.url)
            stack_size = len(app.screen_stack)
            await pilot.press("f2")
            assert len(app.screen_stack) == stack_size
            await pilot.press("escape")
            assert not isinstance(app.screen, terminal.About)
            assert app.selected.recording.path == record.path
            await pilot.press("f1")
            await wait_for_ui(
                pilot,
                lambda: (
                    isinstance(app.screen, terminal.Help) and bool(app.screen.query("#help-about"))
                ),
            )
            app.screen.query_one("#help-about", Button).press()
            await wait_for_ui(pilot, lambda: isinstance(app.screen, terminal.About))
            await pilot.press("escape")
            assert isinstance(app.screen, terminal.Help)
            await pilot.press("escape")
            assert not isinstance(app.screen, terminal.Dialog)
            assert app.selected.recording.path == record.path

    asyncio.run(scenario())


@pytest.mark.parametrize("language", ["en", "ru"])
def test_shortcuts_with_cyrillic_layout_and_function_keys(tmp_path, monkeypatch, language):
    saved(tmp_path)
    monkeypatch.setattr(terminal, "CambridgeClient", Mock(side_effect=AssertionError("offline")))

    async def scenario():
        app = CambridgeApp(Options(tmp_path, language=language, play=False))
        async with app.run_test() as pilot:
            commands = [
                ("ctrl+д", "f3", "search"),
                ("ctrl+з", "f4", "play"),
                ("ctrl+к", "f5", "refresh"),
                ("ctrl+ы", "f6", "settings"),
                ("ctrl+у", "f7", "export"),
                ("ctrl+е", "f8", "edit_translation"),
                ("ctrl+в", "f9", "dictionary"),
                ("ctrl+щ", "f10", "variants"),
                ("ctrl+с", "f11", "cancel"),
                ("ctrl+й", "f12", "quit"),
            ]
            # Repeated localization must preserve priority and not duplicate bindings.
            before = sum(map(len, app._bindings.key_to_bindings.values()))
            app.localize()
            app.localize()
            assert sum(map(len, app._bindings.key_to_bindings.values())) == before
            query = app.query_one("#query", Input)
            query.focus()
            await pilot.press(*"привет")
            assert query.value == "привет"
            handlers = {}
            for cyrillic, function, action in commands:
                handler = Mock()
                handlers[action] = handler

                def record_action(callback=handler):
                    callback()

                monkeypatch.setattr(app, "action_" + action, record_action)
                latin = next(b.key for b in app.BINDINGS if b.action == action)
                for key in (latin, cyrillic, function):
                    query.focus()
                    await pilot.press(key)
                    assert query.value == "привет"
                assert handler.call_count == 3, action
            await pilot.press("ctrl+і")  # Ukrainian position of S.
            assert handlers["settings"].call_count == 4

    asyncio.run(scenario())


def test_cyrillic_shortcut_respects_modal_input(tmp_path, monkeypatch):
    saved(tmp_path)
    monkeypatch.setattr(terminal, "CambridgeClient", Mock(side_effect=AssertionError("offline")))

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test() as pilot:
            await pilot.press("ctrl+ы")
            await wait_for_ui(pilot, lambda: isinstance(app.screen, Settings))
            screen = app.screen
            await pilot.press("ctrl+д", "f3", "f9")
            assert app.screen is screen
            await pilot.press("escape")
            assert not isinstance(app.screen, terminal.Dialog)
            app.query_one("#recordings", DataTable).focus()
            await pilot.press("ctrl+д")
            assert app.focused is app.query_one("#query", Input)

    asyncio.run(scenario())


@pytest.mark.parametrize("language,size", [("en", "20.9 MB"), ("ru", "20,9 МБ")])
def test_tui_dictionary_confirmation_shows_megabytes(tmp_path, monkeypatch, language, size):
    monkeypatch.setattr(terminal, "CambridgeClient", Mock(side_effect=AssertionError("offline")))

    async def scenario():
        app = CambridgeApp(Options(tmp_path, language=language, play=False))
        async with app.run_test() as pilot:
            await pilot.press("ctrl+в")
            await wait_for_ui(pilot, lambda: isinstance(app.screen, terminal.ChooseOption))
            assert size in app.screen.note
            assert terminal.PACKAGE.license_url in app.screen.note
            await pilot.press("escape")
            assert not app.dictionary_busy

    asyncio.run(scenario())


def test_both_downloads_missing_accent_beside_saved_variant(
    tmp_path, monkeypatch, client, html, mp3
):
    from dataclasses import replace

    original = saved(tmp_path)
    variant_path = tmp_path / "hello--saved.us.mp3"
    original.path.rename(variant_path)
    original.path.with_suffix(".json").rename(variant_path.with_suffix(".json"))
    variant = replace(original, path=variant_path, variant_id="a" * 24)
    save_metadata(variant)
    before = variant_path.read_bytes()
    client.session.get.side_effect = [response(html), response(mp3)]
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *a, **kw: client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, accent="both", play=False))
        async with app.run_test() as pilot:
            app.query_one("#query", Input).value = "hello"
            await pilot.press("enter")
            await finish_download(app, pilot)
            assert variant_path.read_bytes() == before
            assert (tmp_path / "hello.uk.mp3").read_bytes() == mp3
            assert not (tmp_path / "hello.us.mp3").exists()
            assert client.session.get.call_count == 2

    asyncio.run(scenario())


def test_russian_help_includes_translated_new_shortcuts(tmp_path):
    async def scenario():
        app = CambridgeApp(Options(tmp_path, language="ru", play=False))
        async with app.run_test() as pilot:
            await pilot.press("f1")
            text = "\n".join(getattr(w.render(), "plain", "") for w in app.screen.query(Static))
            assert "Enter в поиске" in text
            assert "Ctrl+O: выбрать произношение" in text
            assert "Ctrl+E: экспорт в Anki" in text
            assert "Enter in search" not in text

    asyncio.run(scenario())

"""Exercise the actual terminal UI without a network, player or display server."""

import asyncio
from contextlib import suppress
from threading import Event
from unittest.mock import Mock

import pytest
from textual.widgets import Button, Checkbox, DataTable, Input, Select, Static
from textual.worker import WorkerCancelled

from cambridge_audio.library import read_recording, save_metadata
from cambridge_audio.terminal import CambridgeApp, Options
from cambridge_audio.terminal import app as terminal
from tests.terminal.helpers import finish_download, saved, wait_for_ui


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

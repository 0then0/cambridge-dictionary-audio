"""Exercise the actual terminal UI without a network, player or display server."""

import asyncio
from unittest.mock import Mock

import pytest
from textual.widgets import Button, DataTable, Input, Select, Static
from textual.worker import WorkerFailed

from cambridge_audio.library import read_recording, save_metadata
from cambridge_audio.terminal import CambridgeApp, Options
from cambridge_audio.terminal import app as terminal
from tests.helpers import response
from tests.terminal.helpers import finish_download, saved, wait_for_ui


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
    ] + [response("blocked", status=429) for _ in range(3)]
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
    assert client.session.get.call_count == 5


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

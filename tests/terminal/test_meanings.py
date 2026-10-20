"""Exercise inline meaning, accent and audio controls in the real Textual app."""

import asyncio
from unittest.mock import Mock

import pytest
from textual.widgets import Input, OptionList, Select, Static

from cambridge_audio.library import scan_recordings
from cambridge_audio.terminal import CambridgeApp, Options
from cambridge_audio.terminal import app as terminal
from tests.core.test_shared_audio import AUDIO, BANK
from tests.helpers import response
from tests.terminal.helpers import finish_download, wait_for_ui


def test_inline_meanings_preview_and_shared_audio(tmp_path, monkeypatch, client):
    client.session.get.side_effect = [response(BANK), response(AUDIO)]
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *args, **kwargs: client)
    player = Mock()
    monkeypatch.setattr(terminal, "play_audio", player)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test(size=(110, 40)) as pilot:
            app.query_one("#query", Input).value = "bank"
            app.submit()
            await finish_download(app, pilot)
            listing = app.query_one("#meanings", OptionList)
            assert listing.display and listing.option_count == 2
            assert not app.query_one("#other-audio").display
            assert app.query_one("#definition", Static).render().plain == "money"
            assert not scan_recordings(tmp_path)
            app.action_play()
            await finish_download(app, pilot)
            player.assert_called_once()
            assert not scan_recordings(tmp_path)
            app.save_meaning()
            await finish_download(app, pilot)
            listing.highlighted = 1
            await wait_for_ui(
                pilot, lambda: app.query_one("#definition", Static).render().plain == "river"
            )
            assert app.query_one("#definition", Static).render().plain == "river"
            app.save_meaning()
            await finish_download(app, pilot)
            records = scan_recordings(tmp_path)
            assert len(records) == 2
            assert len({s.recording.path for s in records}) == 1
            assert client.session.get.call_count == 2
            app.query_one("#result-accent", Select).value = "uk"
            await pilot.pause()
            assert app.current_choice() is None
            assert app.query_one("#save-meaning").disabled

    asyncio.run(scenario())


@pytest.mark.parametrize("hide", [False, True])
def test_unsaved_meaning_translation_can_be_chosen_and_saved_once(
    tmp_path, monkeypatch, client, hide
):
    from textual.widgets import Button

    from cambridge_audio.translations import cached_translation
    from tests.helpers import BANK_BILINGUAL_HTML
    from tests.terminal.helpers import wait_for_ui

    client.session.get.side_effect = [
        response(BANK),
        response(BANK_BILINGUAL_HTML),
        response(AUDIO),
    ]
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *a, **kw: client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False, translation="russian"))
        async with app.run_test(size=(110, 40)) as pilot:
            app.query_one("#query", Input).value = "bank"
            app.submit()
            await finish_download(app, pilot)
            await wait_for_ui(pilot, lambda: bool(app._preview_translations))
            assert not scan_recordings(tmp_path)
            assert "банк" not in app.query_one("#translation", Static).render().plain
            await pilot.press("ctrl+t")
            await wait_for_ui(pilot, lambda: isinstance(app.screen, terminal.ChooseOption))
            choices = app.screen.choices
            selected = next(value for label, value in choices if label.startswith("банк"))
            app.screen.query_one("#choice", Select).value = selected
            app.screen.query_one("#accept", Button).press()
            await wait_for_ui(pilot, lambda: not isinstance(app.screen, terminal.ChooseOption))
            assert "банк" in app.query_one("#translation", Static).render().plain
            if hide:
                from textual.widgets import Checkbox

                app.query_one("#show-translation", Checkbox).value = False
                await pilot.pause()
            app.save_meaning()
            await finish_download(app, pilot)
            records = scan_recordings(tmp_path)
            assert len(records) == 1
            assert cached_translation(records[0], "russian").texts == ("банк",)
            assert client.session.get.call_count == 3

    asyncio.run(scenario())


def test_preview_translation_arriving_in_edit_dialog_is_shown_after_cancel(
    tmp_path, monkeypatch, client
):
    from threading import Event

    from cambridge_audio.translations import TranslationOption
    from tests.terminal.helpers import wait_for_ui

    entered, release = Event(), Event()

    def fetch(*args):
        entered.set()
        assert release.wait(5)
        return (TranslationOption("money", ("банк",), "money", "noun"),)

    client.translation_options = Mock(side_effect=fetch)
    client.session.get.return_value = response(BANK)
    monkeypatch.setattr(terminal, "CambridgeClient", lambda *a, **kw: client)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False, translation="russian"))
        async with app.run_test(size=(110, 40)) as pilot:
            try:
                app.query_one("#query", Input).value = "bank"
                app.submit()
                await wait_for_ui(pilot, entered.is_set)
                await pilot.press("ctrl+t")
                await wait_for_ui(pilot, lambda: isinstance(app.screen, terminal.ChooseOption))
                release.set()
                await wait_for_ui(pilot, lambda: app.translation_pending is None)
                assert isinstance(app.screen, terminal.ChooseOption)
                await pilot.press("escape")
                await wait_for_ui(pilot, lambda: not isinstance(app.screen, terminal.ChooseOption))
                assert "банк" in app.query_one("#translation", Static).render().plain
                assert not scan_recordings(tmp_path)
            finally:
                release.set()

    asyncio.run(scenario())

"""Exercise inline meaning, accent and audio controls in the real Textual app."""

import asyncio
from unittest.mock import Mock

from textual.widgets import Input, OptionList, Select, Static

from cambridge_audio.library import scan_recordings
from cambridge_audio.terminal import CambridgeApp, Options
from cambridge_audio.terminal import app as terminal
from tests.core.test_shared_audio import AUDIO, BANK
from tests.helpers import response
from tests.terminal.helpers import finish_download


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
            await pilot.pause()
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

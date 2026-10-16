"""Raw terminal diagnostics are opened explicitly and never interpreted as markup."""

import asyncio

import pytest
from textual.widgets import Button, Static

from cambridge_audio.terminal import CambridgeApp, Options
from cambridge_audio.terminal.dialogs import ErrorDetails
from tests.core.test_errors import RAW_TIMEOUT
from tests.terminal.helpers import saved


@pytest.mark.parametrize("language", ["en", "ru"])
def test_terminal_error_details_are_available_and_close_back_to_workspace(tmp_path, language):
    async def scenario():
        app = CambridgeApp(Options(tmp_path, language=language, play=False))
        async with app.run_test(size=(110, 40)) as pilot:
            app.status(RAW_TIMEOUT, error=True)
            assert RAW_TIMEOUT not in app.query_one("#status", Static).render().plain
            assert "HTTPSConnectionPool" not in app.query_one("#status", Static).render().plain
            assert app.query_one("#error-details", Button).display
            assert not isinstance(app.screen, ErrorDetails)
            app.query_one("#error-details", Button).press()
            await pilot.pause()
            assert isinstance(app.screen, ErrorDetails)
            assert RAW_TIMEOUT in app.screen.query_one("#diagnostic-text", Static).render().plain
            await pilot.press("escape")
            assert not isinstance(app.screen, ErrorDetails)
            app.status("Ready")
            assert not app.query_one("#error-details").display

    asyncio.run(scenario())


def test_terminal_cached_translation_error_keeps_translation_and_opt_in_details(tmp_path):
    from cambridge_audio.library import read_recording
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
        (TranslationOption("known", ("привет",), matched=True),),
        error=RAW_TIMEOUT,
    )
    persist_translation(read_recording(record.reference), result)

    async def scenario():
        app = CambridgeApp(Options(tmp_path, translation="russian", play=False))
        async with app.run_test() as pilot:
            await pilot.pause()
            text = app.query_one("#translation", Static).render().plain
            assert "привет" in text
            assert "too long" in text
            assert "HTTPSConnectionPool" not in text
            assert RAW_TIMEOUT in app._error_details["Translation"]
            assert "too long" in app.query_one("#error-summary", Static).render().plain
            assert app.query_one("#error-summary").display
            assert app.query_one("#error-details").display

    asyncio.run(scenario())

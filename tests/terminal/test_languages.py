"""The terminal workspace offers every interface language and fits its buttons."""

import asyncio

import pytest
from textual.widgets import Button, Select

from cambridge_audio.i18n import LANGUAGES, translate
from cambridge_audio.terminal import CambridgeApp, Options, Settings
from cambridge_audio.terminal import settings as terminal_settings
from tests.terminal.helpers import saved, wait_for_ui


@pytest.mark.parametrize("size", [(110, 34), (80, 24), (60, 30)])
@pytest.mark.parametrize("language", list(LANGUAGES))
def test_button_labels_are_fully_painted_in_every_language(tmp_path, language, size):
    saved(tmp_path)
    labels = {
        "download": translate("Find", language),
        "play": translate("Play", language),
        "again": translate("Download again", language),
    }

    async def scenario():
        app = CambridgeApp(Options(tmp_path, language=language, play=False))
        async with app.run_test(size=size) as pilot:
            await wait_for_ui(pilot, lambda: app.selected is not None)
            await pilot.pause()
            for key, text in labels.items():
                button = app.query_one(f"#{key}", Button)
                assert button.label.plain == text
                painted = "\n".join(
                    strip.text for strip in button.render_lines(button.region.reset_offset)
                )
                assert text in painted, (language, size, key, painted)

    asyncio.run(scenario())


@pytest.mark.parametrize("language", [code for code in LANGUAGES if code != "en"])
def test_settings_list_every_language_and_remember_the_choice(
    tmp_path, isolated_terminal_settings, language
):
    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test(size=(110, 45)) as pilot:
            await pilot.press("ctrl+s")
            await wait_for_ui(pilot, lambda: isinstance(app.screen, Settings))
            select = app.screen.query_one("#language", Select)
            offered = [value for _, value in select._options if value is not Select.BLANK]
            assert offered == list(LANGUAGES)
            select.value = language
            app.screen.query_one("#apply", Button).press()
            await wait_for_ui(pilot, isolated_terminal_settings.exists)
            assert app.options.language == language
            assert terminal_settings.load_settings()["language"] == language

    asyncio.run(scenario())

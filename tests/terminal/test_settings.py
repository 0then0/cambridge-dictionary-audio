"""Exercise the actual terminal UI without a network, player or display server."""

import asyncio
from unittest.mock import Mock

import pytest
from textual.widgets import Button, Checkbox, Input, Select, Static

from cambridge_audio.library import read_recording
from cambridge_audio.terminal import CambridgeApp, Options, Settings
from cambridge_audio.terminal import app as terminal
from tests.terminal.helpers import saved, wait_for_ui


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


def test_settings_apply_is_saved_and_cancel_preserves_previous_file(
    tmp_path, isolated_terminal_settings, monkeypatch
):
    from cambridge_audio.terminal import settings as terminal_settings

    monkeypatch.setattr(terminal, "CambridgeClient", Mock(side_effect=AssertionError("offline")))

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test(size=(110, 45)) as pilot:
            await pilot.press("ctrl+s")
            await wait_for_ui(pilot, lambda: isinstance(app.screen, Settings))
            screen = app.screen
            screen.query_one("#language", Select).value = "ru"
            screen.query_one("#theme", Select).value = "cambridge-light"
            screen.query_one("#accent", Select).value = "both"
            screen.query_one("#combine", Checkbox).value = False
            screen.query_one("#apply", Button).press()
            await wait_for_ui(pilot, isolated_terminal_settings.exists)
            assert terminal_settings.load_settings() == {
                "directory": tmp_path,
                "language": "ru",
                "accent": "both",
                "play": False,
                "combine": False,
                "translation": None,
                "theme": "cambridge-light",
            }
            previous = isolated_terminal_settings.read_bytes()
            await pilot.press("ctrl+s")
            await wait_for_ui(pilot, lambda: isinstance(app.screen, Settings))
            app.screen.query_one("#accent", Select).value = "uk"
            await pilot.press("escape")
            await wait_for_ui(pilot, lambda: not isinstance(app.screen, Settings))
            assert isolated_terminal_settings.read_bytes() == previous

        # This is the same reconstruction performed by the CLI on the next launch.
        restored = terminal_settings.load_settings()
        theme = restored.pop("theme")
        second = CambridgeApp(Options(**restored), theme=theme)
        async with second.run_test() as pilot:
            assert second.options.language == "ru"
            assert second.options.accent == "both"
            assert second.theme == "cambridge-light"
            assert second.query_one("#download", Button).label.plain == "Скачать"

    asyncio.run(scenario())


def test_main_translation_toggle_is_persisted(tmp_path, monkeypatch):
    from cambridge_audio.terminal import settings as terminal_settings

    saved(tmp_path)
    monkeypatch.setattr(terminal, "CambridgeClient", Mock(side_effect=AssertionError("offline")))

    async def scenario():
        app = CambridgeApp(Options(tmp_path, play=False))
        async with app.run_test() as pilot:
            await wait_for_ui(pilot, lambda: app.selected is not None)
            toggle = app.query_one("#show-translation", Checkbox)
            toggle.value = True
            await wait_for_ui(
                pilot, lambda: terminal_settings.load_settings().get("translation") == "russian"
            )
            toggle.value = False
            await wait_for_ui(
                pilot,
                lambda: terminal_settings.load_settings().get("translation", "missing") is None,
            )

    asyncio.run(scenario())


def test_startup_does_not_persist_command_line_values(tmp_path, isolated_terminal_settings):
    async def scenario():
        app = CambridgeApp(Options(tmp_path, language="ru", translation="russian"))
        async with app.run_test() as pilot:
            await pilot.pause()
            assert not isolated_terminal_settings.exists()

    asyncio.run(scenario())


def test_settings_save_error_is_visible_without_closing_app(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal, "save_settings", Mock(side_effect=PermissionError("read only")))

    async def scenario():
        app = CambridgeApp(Options(tmp_path, language="ru"))
        async with app.run_test() as pilot:
            await pilot.press("ctrl+s")
            await wait_for_ui(pilot, lambda: isinstance(app.screen, Settings))
            app.screen.query_one("#accent", Select).value = "both"
            app.screen.query_one("#apply", Button).press()
            await wait_for_ui(
                pilot,
                lambda: "Не удалось сохранить" in app.query_one("#status", Static).render().plain,
            )
            assert app.options.accent == "both"
            assert app.query_one("#status", Static).has_class("error")

    asyncio.run(scenario())

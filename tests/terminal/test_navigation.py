"""Exercise the actual terminal UI without a network, player or display server."""

import asyncio
from unittest.mock import Mock

import pytest
from textual.widgets import Button, DataTable, Input, Static

from cambridge_audio.terminal import CambridgeApp, Options, Settings
from cambridge_audio.terminal import app as terminal
from cambridge_audio.terminal.dialogs import Dialog
from tests.terminal.helpers import saved, wait_for_ui


@pytest.mark.parametrize("dialog_key", ["ctrl+s", "f1", "f2"])
def test_resize_with_modal_updates_main_layout_and_keeps_buttons_visible(
    tmp_path, monkeypatch, dialog_key
):
    record = saved(tmp_path)
    monkeypatch.setattr(
        terminal, "CambridgeClient", Mock(side_effect=AssertionError("Saved audio is offline"))
    )

    async def scenario():
        app = CambridgeApp(Options(tmp_path, language="ru", play=False))
        async with app.run_test(size=(110, 34)) as pilot:
            await wait_for_ui(pilot, lambda: app.selected is not None)
            root = app.screen_stack[0]
            for size in ((60, 24), (110, 34)):
                await pilot.press(dialog_key)
                await wait_for_ui(pilot, lambda: isinstance(app.screen, Dialog))
                dialog = app.screen
                await pilot.resize_terminal(*size)
                assert app.screen is dialog
                await pilot.press("escape")
                await wait_for_ui(pilot, lambda: app.screen is root)
                await pilot.pause()
                assert root.has_class("narrow") == (size[0] < 76)
                assert root.has_class("short") == (size[1] < 28)
                library = root.query_one("#library-pane").region
                detail = root.query_one("#detail-pane").region
                if size[0] < 76:
                    assert detail.y > library.y
                else:
                    assert detail.x > library.x
                actions = root.query_one("#detail-actions").content_region
                for key in ("play", "again"):
                    button = root.query_one(f"#{key}", Button)
                    assert button.region.intersection(actions) == button.region
                    assert button.label.plain in "\n".join(
                        strip.text for strip in button.render_lines(button.region.reset_offset)
                    )
                assert app.selected.recording.path == record.path

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
            assert not isinstance(app.screen, Dialog)
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
            assert not isinstance(app.screen, Dialog)
            app.query_one("#recordings", DataTable).focus()
            await pilot.press("ctrl+д")
            assert app.focused is app.query_one("#query", Input)

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

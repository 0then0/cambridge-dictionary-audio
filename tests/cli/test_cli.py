from pathlib import Path
from unittest.mock import Mock

import pytest

from cambridge_audio import cli, service
from cambridge_audio.dictionary import CambridgeError
from tests.helpers import response


def test_cli_downloads_both_accents(monkeypatch, client, html, mp3, tmp_path, capsys):
    client.session.get.side_effect = [response(html), response(mp3), response(mp3)]
    monkeypatch.setattr(cli, "CambridgeClient", lambda timeout, **kwargs: client)
    assert cli.main(["hello", "--accent", "both", "--output-dir", str(tmp_path)]) == 0
    assert (tmp_path / "hello.uk.mp3").read_bytes() == mp3
    assert (tmp_path / "hello.us.mp3").read_bytes() == mp3
    assert "US:" in capsys.readouterr().out


def test_cli_error_has_nonzero_exit(monkeypatch, client, tmp_path, capsys):
    client.session.get.return_value = response("blocked", status=403)
    monkeypatch.setattr(cli, "CambridgeClient", lambda timeout, **kwargs: client)
    assert cli.main(["hello", "--output-dir", str(tmp_path)]) == 1
    assert "403" in capsys.readouterr().err


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "inf", "text"])
def test_cli_rejects_invalid_timeout(timeout):
    with pytest.raises(SystemExit) as error:
        cli.main(["hello", f"--timeout={timeout}"])
    assert error.value.code == 2


def test_interactive_commands_do_not_recurse_or_delete_unrelated_files(
    monkeypatch, client, html, mp3, tmp_path
):
    unrelated = tmp_path / "my-recording.mp3"
    unrelated.write_bytes(b"personal recording")
    client.session.get.side_effect = [response(html), response(mp3)]
    monkeypatch.setattr(cli, "CambridgeClient", lambda timeout, **kwargs: client)
    inputs = iter([""] * 1100 + ["/m", "hello", "/r", "/q"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))
    monkeypatch.setattr(cli, "play_audio", Mock())
    assert cli.main(["--no-play", "--translation", "", "--output-dir", str(tmp_path)]) == 0
    assert unrelated.read_bytes() == b"personal recording"
    assert not (tmp_path / "hello.us.mp3").exists()


def test_playback_failure_keeps_successful_download(monkeypatch, client, html, mp3, tmp_path):
    client.session.get.side_effect = [response(html), response(mp3)]
    monkeypatch.setattr(cli, "CambridgeClient", lambda timeout, **kwargs: client)
    monkeypatch.setattr(cli, "play_audio", Mock(side_effect=CambridgeError("no player")))
    assert cli.main(["hello", "--play", "--output-dir", str(tmp_path)]) == 0
    assert (tmp_path / "hello.us.mp3").read_bytes() == mp3


def test_network_failure_does_not_trigger_phrase_synthesis(monkeypatch, client, tmp_path):
    client.session.get.return_value = response("blocked", status=429)
    fallback = Mock()
    monkeypatch.setattr(cli, "CambridgeClient", lambda timeout, **kwargs: client)
    monkeypatch.setattr(service, "combine_phrase", fallback)
    assert cli.main(["missing phrase", "--combine", "--output-dir", str(tmp_path)]) == 1
    fallback.assert_not_called()


def test_default_us_english_and_definition_without_trailing_colon(
    monkeypatch, client, html, mp3, tmp_path, capsys
):
    client.session.get.side_effect = [
        response(html.replace("used when meeting someone", "used when meeting someone:")),
        response(mp3),
    ]
    monkeypatch.setattr(cli, "CambridgeClient", lambda timeout, **kwargs: client)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["hello"]) == 0
    assert (tmp_path / "downloads" / "hello.us.mp3").read_bytes() == mp3
    assert not (tmp_path / "downloads" / "hello.uk.mp3").exists()
    assert not (tmp_path / "hello.us.mp3").exists()
    output = capsys.readouterr().out
    assert "Saved:" in output
    assert "used when meeting someone\n" in output
    assert "someone:" not in output
    assert client.session.get.call_count == 2  # No implicit translation request.


@pytest.mark.parametrize("language, heading", [("en", "Options:"), ("ru", "Параметры:")])
def test_help_uses_requested_language(language, heading, capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(["--help", "--lang", language])
    assert error.value.code == 0
    assert heading in capsys.readouterr().out


def test_russian_messages_and_independent_translation_language(
    monkeypatch, client, html, mp3, tmp_path, capsys
):
    languages = []

    def create_client(timeout, *, language):
        client.language = language
        languages.append(language)
        return client

    client.session.get.side_effect = [response(html), response(mp3)]
    monkeypatch.setattr(cli, "CambridgeClient", create_client)
    assert cli.main(["hello", "--lang", "ru", "--output-dir", str(tmp_path)]) == 0
    assert "Сохранено:" in capsys.readouterr().out
    assert client.session.get.call_count == 2
    client.session.get.side_effect = [response("missing", status=404)]
    assert cli.main(["missing", "--lang", "ru"]) == 1
    assert "Ошибка: Словарная статья не найдена" in capsys.readouterr().err
    assert languages == ["ru", "ru"]


def test_terminal_launch_passes_cli_options_without_opening_http_client(monkeypatch, tmp_path):
    from cambridge_audio import terminal

    application = Mock()
    client = Mock(side_effect=AssertionError("TUI creates clients only when downloading"))
    monkeypatch.setattr(cli, "is_terminal", lambda: True)
    monkeypatch.setattr(cli, "CambridgeClient", client)
    monkeypatch.setattr(terminal, "CambridgeApp", application)
    assert (
        cli.main(["--lang", "ru", "--accent", "both", "--no-play", "--output-dir", str(tmp_path)])
        == 0
    )
    options = application.call_args.args[0]
    assert options.language == "ru"
    assert options.accent == "both"
    assert options.directory == tmp_path
    assert not options.play
    application.return_value.run.assert_called_once()
    client.assert_not_called()


def test_explicit_tui_requires_terminal(monkeypatch, capsys):
    monkeypatch.setattr(cli, "is_terminal", lambda: False)
    with pytest.raises(SystemExit) as error:
        cli.main(["--tui"])
    assert error.value.code == 2
    assert "requires a terminal" in capsys.readouterr().err


def test_cli_variants_list_and_explicit_selection(monkeypatch, client, html, tmp_path, capsys):
    from cambridge_audio.dictionary import dictionary_url, parse_entries, variants
    from cambridge_audio.library import read_recording

    other = (
        html.replace("used when meeting someone", "a second meaning")
        .replace("hello-us.mp3", "other.mp3")
        .replace("heˈloʊ", "second")
    )
    entries = parse_entries(html + other, dictionary_url("hello"))
    selected = variants(entries)[1]
    monkeypatch.setattr(cli, "CambridgeClient", lambda *args, **kwargs: client)
    client.session.get.return_value = response(html + other)
    assert cli.main(["hello", "--list-variants", "--output-dir", str(tmp_path)]) == 0
    assert selected.id in capsys.readouterr().out
    assert not list(tmp_path.iterdir())
    assert cli.main(["hello", "--output-dir", str(tmp_path)]) == 1
    assert "Choose a dictionary entry" in capsys.readouterr().err
    client.session.get.side_effect = [response(html + other), response(b"ID3selected")]
    assert cli.main(["hello", "--variant", selected.id, "--output-dir", str(tmp_path)]) == 0
    path = next(tmp_path.glob("*.mp3"))
    record = read_recording(path).recording
    assert record.definition == "a second meaning" and record.ipa == "second"


def test_cli_download_fallback_retains_wikdict_provenance(monkeypatch, client, html, tmp_path):
    from cambridge_audio import translations
    from cambridge_audio.library import read_recording
    from cambridge_audio.translations import TranslationOption, cached_translation

    client.session.get.side_effect = [response(html), response(b"ID3audio")]
    client.translations = Mock(return_value=())
    monkeypatch.setattr(
        translations,
        "lookup",
        lambda *args: (
            TranslationOption("one", ("привет",), "greeting", origin="WikDict fixture"),
        ),
    )
    monkeypatch.setattr(cli, "CambridgeClient", lambda *args, **kwargs: client)
    assert cli.main(["hello", "--translation", "russian", "--output-dir", str(tmp_path)]) == 0
    saved = read_recording(tmp_path / "hello.us.mp3")
    assert cached_translation(saved, "russian").source == "WikDict"
    assert {t.source for t in saved.translation_cache} == {"WikDict"}


@pytest.mark.parametrize("value", ["russian", "ru", "русский", " RUSSIAN "])
@pytest.mark.parametrize("interface_language", ["en", "ru"])
def test_cli_accepts_only_russian_translation_aliases(
    monkeypatch, client, html, mp3, tmp_path, value, interface_language
):
    client.translations = Mock(return_value=("привет",))
    client.session.get.side_effect = [response(html), response(mp3)]
    monkeypatch.setattr(cli, "CambridgeClient", lambda *args, **kwargs: client)
    assert (
        cli.main(
            [
                "hello",
                "--lang",
                interface_language,
                "--translation",
                value,
                "--output-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    client.translations.assert_called_once_with("hello", "russian")


@pytest.mark.parametrize("value", ["french", "english", "banana", "chinese-simplified"])
@pytest.mark.parametrize("interface_language", ["en", "ru"])
def test_cli_rejects_other_translation_languages_before_io(
    monkeypatch, tmp_path, capsys, value, interface_language
):
    client = Mock(side_effect=AssertionError("reject before network"))
    monkeypatch.setattr(cli, "CambridgeClient", client)
    with pytest.raises(SystemExit) as error:
        cli.main(
            [
                "hello",
                "--lang",
                interface_language,
                "--translation",
                value,
                "--output-dir",
                str(tmp_path / "audio"),
            ]
        )
    assert error.value.code == 2
    message = capsys.readouterr().err
    assert (
        "только перевод на русский" if interface_language == "ru" else "Only Russian translation"
    ) in message
    assert not (tmp_path / "audio").exists()
    client.assert_not_called()


@pytest.mark.parametrize("explicit", [False, True])
def test_tui_restores_preferences_and_explicit_flags_override_without_rewriting(
    tmp_path, monkeypatch, isolated_terminal_settings, explicit
):
    from cambridge_audio import terminal
    from cambridge_audio.terminal import settings as terminal_settings

    saved = terminal.Options(
        tmp_path / "saved",
        language="ru",
        accent="both",
        play=False,
        combine=False,
        translation="russian",
        overwrite=True,
        offline=True,
    )
    terminal_settings.save_settings(saved, "cambridge-light")
    previous = isolated_terminal_settings.read_bytes()
    application = Mock()
    monkeypatch.setattr(cli, "is_terminal", lambda: True)
    monkeypatch.setattr(terminal, "CambridgeApp", application)
    flags = (
        ["--lang=en", "--accent=us", "--play", "--combine", "--output-dir", str(tmp_path)]
        if explicit
        else []
    )
    assert cli.main(flags) == 0
    options = application.call_args.args[0]
    assert options.directory == (tmp_path if explicit else saved.directory)
    assert options.language == ("en" if explicit else "ru")
    assert options.accent == ("us" if explicit else "both")
    assert options.play is explicit
    assert options.combine is explicit
    assert options.translation == "russian"
    assert not options.overwrite and not options.offline
    assert application.call_args.kwargs["theme"] == "cambridge-light"
    assert isolated_terminal_settings.read_bytes() == previous


def test_tui_negative_flags_override_saved_enabled_preferences(tmp_path, monkeypatch):
    from cambridge_audio import terminal
    from cambridge_audio.terminal import settings as terminal_settings

    terminal_settings.save_settings(terminal.Options(tmp_path), "cambridge-dark")
    application = Mock()
    monkeypatch.setattr(cli, "is_terminal", lambda: True)
    monkeypatch.setattr(terminal, "CambridgeApp", application)
    assert cli.main(["--no-play", "--no-combine"]) == 0
    options = application.call_args.args[0]
    assert not options.play and not options.combine


@pytest.mark.parametrize("plain", [False, True])
def test_saved_tui_preferences_do_not_change_other_cli_modes(tmp_path, monkeypatch, client, plain):
    from cambridge_audio import terminal
    from cambridge_audio.terminal import settings as terminal_settings

    terminal_settings.save_settings(
        terminal.Options(tmp_path / "saved", language="ru", accent="both", play=False),
        "cambridge-light",
    )
    captured = []
    monkeypatch.setattr(cli, "is_terminal", lambda: True)
    monkeypatch.setattr(cli, "CambridgeClient", lambda *a, **kw: client)
    monkeypatch.setattr(cli, "interactive", lambda client, args: captured.append(args) or 0)
    monkeypatch.setattr(
        cli, "download_word", lambda client, word, args, files: captured.append(args)
    )
    assert cli.main(["--plain"] if plain else ["hello"]) == 0
    args = captured[0]
    assert args.lang == "en" and args.accent == "us"
    assert args.output_dir == Path.cwd() / "downloads"
    assert args.play is plain and args.combine is plain

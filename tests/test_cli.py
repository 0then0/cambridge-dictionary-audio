from unittest.mock import Mock

import pytest
from conftest import response

from cambridge_audio import cli, service
from cambridge_audio.dictionary import CambridgeError


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

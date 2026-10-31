"""--lang selects any supported interface language in help and messages."""

import pytest

from cambridge_audio import cli
from cambridge_audio.i18n import translate


@pytest.mark.parametrize("language", ["es", "de", "fr", "ja", "pt-BR"])
def test_help_and_errors_use_the_selected_language(language, tmp_path, capsys):
    with pytest.raises(SystemExit) as stop:
        cli.main(["--lang", language, "--help"])
    assert stop.value.code == 0
    help_text = capsys.readouterr().out
    assert translate("Show this help message and exit.", language) in help_text
    assert translate("Options", language) + ":" in help_text.replace(" :", ":")
    with pytest.raises(SystemExit) as stop:
        cli.main(["--lang", language, "--replace-bundle", "--output-dir", str(tmp_path)])
    assert stop.value.code == 2
    assert translate("usage: ", language).strip() in capsys.readouterr().err


@pytest.mark.parametrize("value,expected", [("pt-br", "pt-BR"), ("PT-BR", "pt-BR"), ("JA", "ja")])
def test_language_codes_are_case_insensitive(value, expected):
    assert cli.interface_language(value) == expected


def test_unknown_language_is_rejected_with_the_choices(capsys):
    with pytest.raises(SystemExit) as stop:
        cli.main(["--lang", "pt", "--help"])
    assert stop.value.code == 2
    assert "pt-BR" in capsys.readouterr().err


@pytest.mark.parametrize("columns", [60, 80])
def test_japanese_help_wraps_by_display_width(monkeypatch, capsys, columns):
    import unicodedata

    monkeypatch.setenv("COLUMNS", str(columns))
    with pytest.raises(SystemExit):
        cli.main(["--lang", "ja", "--help"])
    for line in capsys.readouterr().out.splitlines():
        cells = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in line)
        # Option names and usage lines are not text; hanging punctuation may overhang by one.
        if line.startswith(" " * 20) and any(ord(c) > 0x2E80 for c in line):
            assert cells <= columns, line


def test_wrap_by_width_never_starts_a_line_with_closing_punctuation():
    lines = cli.wrap_by_width("あいうえおかきくけこ。さしすせそ", 12)
    assert all(not line.startswith("。") for line in lines)
    assert "".join(lines) == "あいうえおかきくけこ。さしすせそ"

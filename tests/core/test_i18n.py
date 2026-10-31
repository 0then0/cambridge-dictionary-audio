"""Every interface language covers every message and keeps its placeholders."""

import ast
import re
from pathlib import Path

import pytest

from cambridge_audio import i18n
from cambridge_audio.i18n import (
    CATALOGS,
    LANGUAGES,
    RUSSIAN,
    english_text,
    language_code,
    translate,
)

NEW = ["es", "de", "fr", "ja", "pt-BR"]
PLACEHOLDER = re.compile(r"\{(\w+)\}")
# Messages that are identical in some languages by convention (product names, keys, units).
SAME = {"OK", "WikDict: {done} / {total} bytes", "{prog}: error: {error}\n", "Error: {error}"}
# Labels that only look like errors to the English keyword classifier.
NOT_ERRORS = {"No recording yet"}
UI_FUNCTIONS = {"translate", "_t", "t", "_status", "status"}


def used_messages():
    found = set()
    for path in Path(i18n.__file__).parent.rglob("*.py"):
        if path.name == "i18n.py" or "locales" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and node.args:
                function = node.func
                name = (
                    function.attr
                    if isinstance(function, ast.Attribute)
                    else getattr(function, "id", "")
                )
                first = node.args[0]
                if (
                    name in UI_FUNCTIONS
                    and isinstance(first, ast.Constant)
                    and isinstance(first.value, str)
                ):
                    found.add(first.value)
    return found


def test_registry_lists_every_supported_language_once():
    assert list(LANGUAGES) == ["en", "ru", "es", "de", "fr", "ja", "pt-BR"]
    assert set(CATALOGS) == set(LANGUAGES) - {"en"}
    assert language_code(" PT-br ") == "pt-BR" and language_code("JA") == "ja"
    with pytest.raises(ValueError):
        language_code("pt")


def test_every_message_used_by_the_application_is_translated_everywhere():
    used = used_messages()
    assert used
    for language, catalog in CATALOGS.items():
        assert not used - catalog.keys(), (language, sorted(used - catalog.keys()))


@pytest.mark.parametrize("language", NEW)
def test_new_catalogue_matches_the_reference_exactly(language):
    catalog = CATALOGS[language]
    assert catalog.keys() == RUSSIAN.keys()
    for english, translated in catalog.items():
        assert translated.strip(), english
        assert PLACEHOLDER.findall(english) == PLACEHOLDER.findall(translated), english
        assert english.count("\n") == translated.count("\n"), english
        assert english.endswith(" ") == translated.endswith(" "), english
        assert english.endswith("\n") == translated.endswith("\n"), english
        # Short words are often legitimate cognates ("Action", "System"); sentences never are.
        assert translated != english or english in SAME or len(english) <= 20, english


@pytest.mark.parametrize("language", NEW)
def test_formatting_works_with_every_message(language):
    for english, translated in CATALOGS[language].items():
        values = dict.fromkeys(PLACEHOLDER.findall(english), "X")
        assert translate(english, language, **values) == translated.format(**values)


def test_unknown_language_falls_back_to_english():
    assert translate("Close", "xx") == "Close"
    assert translate("Version {version}", "en", version="1") == "Version 1"


def test_translated_errors_are_recognised_by_their_english_source():
    for language in NEW + ["ru"]:
        text = translate("The service took too long to respond. Please try again.", language)
        assert "took too long" in english_text(text)


@pytest.mark.parametrize("language", NEW)
def test_errors_stored_in_any_language_classify_like_their_english_source(language):
    from cambridge_audio.errors import friendly_error

    checked = 0
    for english, translated in CATALOGS[language].items():
        if english in NOT_ERRORS:
            continue
        values = dict.fromkeys(PLACEHOLDER.findall(english), "X")
        expected = friendly_error(english.format(**values), "en")
        assert friendly_error(translated.format(**values), "en") == expected, (language, english)
        # The summary is shown in the requested language.
        assert friendly_error(translated.format(**values), language) == translate(
            expected, language
        )
        checked += expected != translate("Could not complete the operation. Please try again.")
    assert checked > 20, "most messages classify as something more specific than the fallback"


def test_wikdict_package_size_uses_the_local_decimal_mark_and_unit():
    from cambridge_audio.wikdict import PACKAGE

    sizes = {language: PACKAGE.describe(language) for language in LANGUAGES}
    assert " MB · " in sizes["en"] and "." in sizes["en"].split(" · ")[2]
    assert sizes["ru"].split(" · ")[2].endswith(" МБ") and "," in sizes["ru"].split(" · ")[2]
    assert sizes["fr"].split(" · ")[2].endswith(" Mo")
    for language in ("es", "de", "pt-BR"):
        assert "," in sizes[language].split(" · ")[2] and sizes[language].count(" MB") == 1
    assert "." in sizes["ja"].split(" · ")[2] and sizes["ja"].split(" · ")[2].endswith(" MB")


def test_error_classification_stays_fast_on_long_diagnostics():
    import time

    from cambridge_audio.errors import friendly_error

    english_text("warm up the pattern cache")
    text = "Request failed for https://dictionary.cambridge.org/x: HTTPError 500 " * 600
    started = time.perf_counter()
    friendly_error(text, "en")
    assert time.perf_counter() - started < 1.0
    # Leading values do not hide a translated message.
    assert "Could not play" in english_text(translate("Could not play {path}.", "ja", path="a.mp3"))
    assert "Could not play" in english_text(translate("Could not play {path}.", "de", path="a.mp3"))

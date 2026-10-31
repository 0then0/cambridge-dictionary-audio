"""The mobile interface catalogues cover the sources and the generated code is current."""

import json

import pytest

from cambridge_audio.i18n import LANGUAGES
from scripts import mobile_locales as locales


def test_language_menus_match_between_desktop_and_mobile():
    assert locales.LANGUAGES == LANGUAGES


def test_catalogues_cover_exactly_the_strings_used_by_the_sources():
    assert locales.problems() == []
    assert len(locales.english_strings()) > 150


@pytest.mark.parametrize("target", locales.GENERATED, ids=lambda path: path.name)
def test_generated_sources_are_current(target):
    assert target.read_text(encoding="utf-8") == locales.render(target)


def test_extraction_handles_interpolation_in_both_languages():
    kotlin = 't("Meanings (${entries.size})", "Значения (${entries.size})")'
    swift = 't("Meanings (\\(model.entries.count))", "Значения (\\(model.entries.count))")'
    for source, swift_syntax in ((kotlin, False), (swift, True)):
        literal, _ = locales.read_literal(source, source.index('"'), swift_syntax)
        assert locales.template(literal, []) == "Meanings ({0})"


def test_numbered_placeholders_follow_first_appearance():
    expressions = []
    assert locales.template("\0a\0 and \0b\0 and \0a\0", expressions) == "{0} and {1} and {0}"
    assert expressions == ["a", "b"]


def test_every_catalogue_is_valid_json_with_string_values():
    for language in locales.TRANSLATED:
        data = json.loads((locales.LOCALES / f"{language}.json").read_text(encoding="utf-8"))
        assert all(isinstance(key, str) and isinstance(value, str) for key, value in data.items())

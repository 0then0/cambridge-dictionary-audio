"""Python consumes the same vectors used by the Kotlin common domain tests."""

import json
from dataclasses import asdict
from pathlib import Path

import genanki
import pytest

from cambridge_audio import anki
from cambridge_audio.dictionary import audio_filename, normalize_word, parse_entries, stable_id
from cambridge_audio.translations import TranslationOption, match_options
from scripts.mobile_contracts import TARGET, render

ROOT = Path(__file__).resolve().parents[2] / "contracts"
GOLDEN = json.loads((ROOT / "golden.json").read_text())


def test_python_normalization_and_identity_vectors():
    for case in GOLDEN["normalization"]:
        if case.get("invalid"):
            with pytest.raises(ValueError):
                normalize_word(case["input"])
        else:
            value = normalize_word(case["input"])
            assert value == case["normalized"]
            assert audio_filename(value, "us") == case["filename"]
    for case in GOLDEN["identities"]:
        assert stable_id(*case["values"]) == case["id"]
    for case in GOLDEN["guids"]:
        assert genanki.guid_for("cambridge-dictionary-audio", case["id"]) == case["guid"]


def test_python_parser_and_translation_vectors():
    for case in GOLDEN["parsers"]:
        actual = parse_entries((ROOT / case["file"]).read_text(), case["url"])
        assert json.loads(json.dumps([asdict(e) for e in actual])) == case["entries"]
    for case in GOLDEN["matching"]:
        options = [TranslationOption(**(o | {"texts": tuple(o["texts"])})) for o in case["options"]]
        actual = match_options(options, case["definition"], case["part"])
        assert json.loads(json.dumps([asdict(o) for o in actual])) == case["expected"]


def test_mobile_anki_constants_are_exactly_the_python_contract():
    contract = json.loads((ROOT / "anki.json").read_text())
    assert contract["model"] == anki._model().to_json(1700000000, anki.DECK_ID)
    assert contract["deck_id"] == anki.DECK_ID
    assert contract["columns"] == list(anki.COLUMNS)
    assert contract["sources"] == anki.SOURCES
    assert TARGET.read_text() == render()

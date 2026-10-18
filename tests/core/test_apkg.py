"""Inspect generated packages without claiming this tests Anki's importer."""

import json
import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock
from zipfile import ZipFile

import genanki
import pytest

from cambridge_audio import anki
from cambridge_audio.anki import adopt_anki_identities, export_apkg
from cambridge_audio.dictionary import variants
from cambridge_audio.library import SavedRecording, scan_recordings
from tests.core.test_shared_audio import AUDIO, bank, save
from tests.helpers import response


def inspect_package(path, tmp_path):
    with ZipFile(path) as archive:
        db = tmp_path / "inspect.sqlite"
        db.write_bytes(archive.read("collection.anki2"))
        media = json.loads(archive.read("media"))
        with closing(sqlite3.connect(db)) as connection:
            notes = connection.execute("SELECT guid, mid, flds FROM notes ORDER BY flds").fetchall()
            models = json.loads(connection.execute("SELECT models FROM col").fetchone()[0])
            cards = connection.execute("SELECT ord FROM cards").fetchall()
        return notes, models, cards, media, archive.read("SOURCES.txt").decode()


def test_package_notes_template_sources_escaping_and_shared_media(client, tmp_path):
    client.session.get.return_value = response(AUDIO)
    for choice in variants(bank()):
        save(client, tmp_path, choice)
    records = scan_recordings(tmp_path)
    records[0] = SavedRecording(replace(records[0].recording, definition='<b>"test"</b> &\nnew'))
    output = export_apkg(records, tmp_path / "export.apkg")
    notes, models, cards, media, sources = inspect_package(output, tmp_path)
    assert len(notes) == 2
    assert len(set(n[0] for n in notes)) == 2
    assert len(media) == 1
    assert cards == [(0,), (0,)]
    model = models[str(anki.MODEL_ID)]
    assert len(model["tmpls"]) == 1
    assert "{{Word}}" in model["tmpls"][0]["qfmt"]
    assert "{{Audio}}" not in model["tmpls"][0]["qfmt"]
    assert "{{Translation}}" in model["tmpls"][0]["afmt"]
    assert "nightMode" in model["css"]
    from bs4 import BeautifulSoup

    answer = model["tmpls"][0]["afmt"]
    assert answer.count("{{Source}}") == 1
    assert BeautifulSoup(answer, "html.parser").find("details") is None
    for note in notes:
        source = BeautifulSoup(note[2].split("\x1f")[-1], "html.parser")
        disclosure = source.select_one("details.cambridge-source")
        assert disclosure is not None and not disclosure.has_attr("open")
        assert disclosure.summary.get_text(strip=True) == "Source"
        assert "Cambridge content retains" in disclosure.div.get_text()
        assert "font-size:13px" in disclosure["style"]
    with closing(sqlite3.connect(tmp_path / "inspect.sqlite")) as connection:
        decks = json.loads(connection.execute("SELECT decks FROM col").fetchone()[0])
    description = BeautifulSoup(decks[str(anki.DECK_ID)]["desc"], "html.parser")
    disclosure = description.select_one("details.cambridge-source")
    assert disclosure is not None and not disclosure.has_attr("open")
    assert "Cambridge content retains" in disclosure.get_text()
    assert "&lt;b&gt;&quot;test&quot;&lt;/b&gt; &amp;<br>new" in " ".join(n[2] for n in notes)
    assert "Cambridge" in sources and "CC BY-SA 4.0" in sources
    assert all("Cambridge content retains" in n[2] for n in notes)
    assert all("[sound:" + next(iter(media.values())) + "]" in n[2] for n in notes)


def test_guids_model_and_template_ids_survive_content_and_media_edits(client, tmp_path):
    client.session.get.return_value = response(AUDIO)
    record = save(client, tmp_path, variants(bank())[0])
    output = export_apkg([SavedRecording(record)], tmp_path / "export.apkg")
    old, models, _, media, _ = inspect_package(output, tmp_path)
    record.path.write_bytes(b"ID3replacement")
    changed = replace(record, word="Bank", definition="revised", ipa="new", audio_sha256="")
    export_apkg([SavedRecording(changed)], output)
    new, new_models, _, new_media, _ = inspect_package(output, tmp_path)
    assert old[0][:2] == new[0][:2]
    assert old[0][2] != new[0][2]
    assert media != new_media
    assert (
        models[str(anki.MODEL_ID)]["tmpls"][0]["id"]
        == new_models[str(anki.MODEL_ID)]["tmpls"][0]["id"]
    )


def test_failed_package_write_preserves_previous_export(client, tmp_path, monkeypatch):
    client.session.get.return_value = response(AUDIO)
    record = save(client, tmp_path, variants(bank())[0])
    output = export_apkg([SavedRecording(record)], tmp_path / "export.apkg")
    before = output.read_bytes()
    monkeypatch.setattr(genanki.Package, "write_to_file", Mock(side_effect=OSError("disk full")))
    with pytest.raises(OSError):
        export_apkg([SavedRecording(record)], output)
    assert output.read_bytes() == before
    assert not list(tmp_path.glob(".cambridge-apkg-*"))
    personal = tmp_path / "personal.apkg"
    personal.write_bytes(b"personal")
    with pytest.raises(FileExistsError):
        export_apkg([SavedRecording(record)], personal)
    assert personal.read_bytes() == b"personal"


def legacy_reference(path: Path, record, *, duplicate=False, extra=False):
    model = anki._model()
    model.model_id = 1700000000
    model.name = "My original TSV type"
    if extra:
        model.fields.append({"name": "Personal"})
    deck = genanki.Deck(1700000001, "Old TSV")
    for guid in ["oldGuid001", "oldGuid002"] if duplicate else ["oldGuid001"]:
        fields = [record.id, record.word] + [""] * (len(model.fields) - 2)
        deck.add_note(genanki.Note(model=model, fields=fields, guid=guid))
    genanki.Package(deck).write_to_file(str(path))


def test_explicit_tsv_transition_preserves_original_guid_and_note_type(client, tmp_path):
    client.session.get.return_value = response(AUDIO)
    record = save(client, tmp_path, variants(bank())[0])
    records = [SavedRecording(record)]
    reference = tmp_path / "from-anki.apkg"
    legacy_reference(reference, record)
    before = reference.read_bytes()
    for _ in range(2):
        assert adopt_anki_identities(records, reference, tmp_path) == 1
    output = export_apkg(records, tmp_path / "export.apkg")
    notes, models, _, _, _ = inspect_package(output, tmp_path)
    assert notes[0][:2] == ("oldGuid001", 1700000000)
    assert models["1700000000"]["name"] == "My original TSV type"
    assert reference.read_bytes() == before


@pytest.mark.parametrize("options", [{"duplicate": True}, {"extra": True}])
def test_ambiguous_or_modified_tsv_schema_does_not_write_mapping(client, tmp_path, options):
    client.session.get.return_value = response(AUDIO)
    record = save(client, tmp_path, variants(bank())[0])
    reference = tmp_path / "from-anki.apkg"
    legacy_reference(reference, record, **options)
    with pytest.raises(ValueError):
        adopt_anki_identities([SavedRecording(record)], reference, tmp_path)
    assert not (tmp_path / anki.MAPPING_FILE).exists()


def test_rapid_exports_to_different_paths_have_increasing_note_mtime(client, tmp_path):
    client.session.get.return_value = response(AUDIO)
    record = save(client, tmp_path, variants(bank())[0])
    times = []
    for name in ("one.apkg", "two.apkg"):
        output = export_apkg([SavedRecording(record)], tmp_path / name)
        with ZipFile(output) as archive:
            database = tmp_path / "timestamp.sqlite"
            database.write_bytes(archive.read("collection.anki2"))
        with closing(sqlite3.connect(database)) as connection:
            times.append(connection.execute("SELECT mod FROM notes").fetchone()[0])
    assert times[1] > times[0]


def test_tsv_transition_reads_legacy2_database_instead_of_anki2_placeholder(client, tmp_path):
    client.session.get.return_value = response(AUDIO)
    record = save(client, tmp_path, variants(bank())[0])
    reference = tmp_path / "old-format.apkg"
    legacy_reference(reference, record)
    with ZipFile(reference) as archive:
        content = archive.read("collection.anki2")
    modern_legacy = tmp_path / "from-current-anki.apkg"
    with ZipFile(modern_legacy, "w") as archive:
        archive.writestr("collection.anki2", b"upgrade notice placeholder")
        archive.writestr("collection.anki21", content)
    assert adopt_anki_identities([SavedRecording(record)], modern_legacy, tmp_path) == 1


def test_card_text_and_source_have_readable_contrast_in_both_themes():
    import re

    def luminance(color):
        channels = [int(color[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
        return sum(a * b for a, b in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))

    rules = dict(re.findall(r"([^{}]+)\{([^{}]+)\}", anki.CARD_CSS))
    for card_selector, source_selector in (
        (".card", ".source"),
        (".nightMode.card, .night_mode.card", ".nightMode .source, .night_mode .source"),
    ):
        card = next(style for selector, style in rules.items() if selector.strip() == card_selector)
        source = next(
            style for selector, style in rules.items() if selector.strip() == source_selector
        )
        background = re.search(r"background:\s*#([a-f0-9]{6})", card)[1]
        for style in (card, source):
            foreground = re.search(r"color:\s*#([a-f0-9]{6})", style)[1]
            one, two = sorted((luminance(foreground), luminance(background)))
            assert (two + 0.05) / (one + 0.05) >= 4.5


@pytest.mark.parametrize("invalid", [False, True])
def test_reference_database_is_closed_before_temporary_directory_cleanup(
    client, tmp_path, monkeypatch, invalid
):
    client.session.get.return_value = response(AUDIO)
    record = save(client, tmp_path, variants(bank())[0])
    reference = tmp_path / "reference.apkg"
    legacy_reference(reference, record, duplicate=invalid)
    connect = sqlite3.connect
    connections = []

    def retain_connection(*args, **kwargs):
        connection = connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", retain_connection)
    try:
        if invalid:
            with pytest.raises(ValueError, match="Ambiguous Anki ID"):
                adopt_anki_identities([SavedRecording(record)], reference, tmp_path)
        else:
            assert adopt_anki_identities([SavedRecording(record)], reference, tmp_path) == 1
        assert len(connections) == 1
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            connections[0].execute("SELECT 1")
    finally:
        for connection in connections:
            connection.close()


def test_source_disclosure_escapes_untrusted_text_and_keeps_legacy_templates(client, tmp_path):
    from bs4 import BeautifulSoup

    client.session.get.return_value = response(AUDIO)
    record = save(client, tmp_path, variants(bank())[0])
    reference = tmp_path / "legacy.apkg"
    legacy_reference(reference, record)
    saved = SavedRecording(replace(record, source_url='<img src=x onerror="alert(1)">'))
    adopt_anki_identities([saved], reference, tmp_path)
    output = export_apkg([saved], tmp_path / "disclosure.apkg")
    notes, models, _, _, _ = inspect_package(output, tmp_path)
    with ZipFile(reference) as archive:
        old_db = tmp_path / "legacy.sqlite"
        old_db.write_bytes(archive.read("collection.anki2"))
    with closing(sqlite3.connect(old_db)) as connection:
        old_models = json.loads(connection.execute("SELECT models FROM col").fetchone()[0])
    assert models["1700000000"] == old_models["1700000000"]
    source = BeautifulSoup(notes[0][2].split("\x1f")[-1], "html.parser")
    assert source.find("details") is not None and source.find("img") is None
    assert '<img src=x onerror="alert(1)">' in source.get_text()

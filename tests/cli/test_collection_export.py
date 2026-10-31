"""The CLI reports a refused backup as a failure and replaces only on request."""

import hashlib

import pytest

from cambridge_audio import cli
from cambridge_audio.bundle import _load_bundle
from tests.core.test_bundle import collection

FOREIGN = b"hand written notes\n"


@pytest.fixture
def source(client, tmp_path):
    collection(client, tmp_path / "source")
    return tmp_path / "source"


def export(source, destination, *flags):
    return cli.main(["--output-dir", str(source), "--export-collection", str(destination), *flags])


def test_export_to_new_path_succeeds_and_prints_the_path(source, tmp_path, capsys):
    destination = tmp_path / "backup.cda"
    assert export(source, destination) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == str(destination) and captured.err == ""
    _load_bundle(destination)


@pytest.mark.parametrize("flags", [(), ("--overwrite",)])
def test_existing_file_fails_without_success_output(source, tmp_path, capsys, flags):
    destination = tmp_path / "thesis.docx"
    destination.write_bytes(FOREIGN)
    assert export(source, destination, *flags) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert str(destination) in captured.err and "--replace-bundle" in captured.err
    assert destination.read_bytes() == FOREIGN
    assert sorted(p.name for p in tmp_path.iterdir()) == ["source", "thesis.docx"]


def test_existing_valid_archive_is_kept_and_readable(source, tmp_path, capsys):
    destination = tmp_path / "backup.cda"
    assert export(source, destination) == 0
    before = hashlib.sha256(destination.read_bytes()).hexdigest()
    capsys.readouterr()
    assert export(source, destination) == 1
    assert capsys.readouterr().out == ""
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == before
    _load_bundle(destination)


def test_replace_bundle_allows_replacement(source, tmp_path, capsys):
    destination = tmp_path / "thesis.docx"
    destination.write_bytes(FOREIGN)
    assert export(source, destination, "--replace-bundle") == 0
    assert capsys.readouterr().out.strip() == str(destination)
    _load_bundle(destination)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["source", "thesis.docx"]


def test_refusal_message_follows_the_interface_language(source, tmp_path, capsys):
    destination = tmp_path / "thesis.docx"
    destination.write_bytes(FOREIGN)
    assert export(source, destination, "--lang", "ru") == 1
    assert "уже существует" in capsys.readouterr().err
    assert destination.read_bytes() == FOREIGN


def test_folder_destination_fails_with_its_reason(source, tmp_path, capsys):
    destination = tmp_path / "backup.cda"
    destination.mkdir()
    assert export(source, destination, "--replace-bundle") == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "folder" in captured.err


def test_replace_bundle_requires_an_export(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(["--output-dir", str(tmp_path), "--replace-bundle"])
    assert error.value.code == 2
    assert "--replace-bundle requires --export-collection" in capsys.readouterr().err

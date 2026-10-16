"""Browser release archives have a flat manifest and reproducible bytes."""

import json
from zipfile import ZipFile

import pytest

from scripts.package_extension import package_extensions


def test_extension_archives_are_reproducible_and_installable(tmp_path):
    for browser in ("chrome", "firefox"):
        directory = tmp_path / "extension/dist" / browser
        directory.mkdir(parents=True)
        (directory / "manifest.json").write_text(json.dumps({"version": "0.2.0"}))
        (directory / "popup.html").write_text("<html></html>")
        (directory / "icons").mkdir()
        (directory / "icons/icon.png").write_bytes(b"image")
    archives = package_extensions(tmp_path)
    contents = [archive.read_bytes() for archive in archives]
    assert [archive.read_bytes() for archive in package_extensions(tmp_path)] == contents
    assert len(archives) == 2
    for archive in archives:
        with ZipFile(archive) as stream:
            assert "manifest.json" in stream.namelist()
            assert "icons/icon.png" in stream.namelist()
            assert all(not name.startswith("/") for name in stream.namelist())
            assert stream.getinfo("popup.html").external_attr >> 16 == 0o100644


def test_extension_packaging_requires_a_built_manifest(tmp_path):
    with pytest.raises(FileNotFoundError):
        package_extensions(tmp_path)

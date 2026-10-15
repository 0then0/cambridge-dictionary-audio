"""Small schema-compatible packages; real package checks are an explicit script."""

import hashlib
from dataclasses import replace
from unittest.mock import Mock

import pytest
import requests

from cambridge_audio import wikdict


def download_session(content, failure=None):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)

    def chunks(size):
        yield content[:100]
        if failure:
            raise failure
        yield content[100:]

    response.iter_content.side_effect = chunks
    session = Mock()
    session.get.return_value = response
    return session


def test_verified_install_and_local_query_without_network(tmp_path, wikdict_package):
    spec, content = wikdict_package
    directory = tmp_path / "installed"
    progress = []
    destination = wikdict.install_dictionary(
        directory,
        package=spec,
        session=download_session(content),
        progress=lambda done, total: progress.append((done, total)),
    )
    assert destination.read_bytes() == content
    assert progress[-1] == (spec.size, spec.size)
    assert "CC BY-SA 4.0" in (directory / "WIKDICT-LICENSE.txt").read_text()
    options = wikdict.lookup("bank", directory, package=spec)
    assert len(options) == 2
    assert options[0].texts == ("банк",)
    assert options[1].texts == ("бе́рег", "берег")
    assert options[1].definition == "edge of a river"
    assert not any(o.matched for o in options)
    assert wikdict.lookup("went", directory, package=spec) == ()  # No guessed lemma.


@pytest.mark.parametrize("failure", [requests.ConnectionError("interrupted"), KeyboardInterrupt()])
def test_interrupted_update_preserves_previous_package(tmp_path, wikdict_package, failure):
    spec, content = wikdict_package
    directory = tmp_path / "installed"
    path = wikdict.install_dictionary(directory, package=spec, session=download_session(content))
    with pytest.raises((wikdict.CambridgeError, KeyboardInterrupt)):
        wikdict.install_dictionary(
            directory, package=spec, session=download_session(content, failure)
        )
    assert path.read_bytes() == content
    assert not list(directory.glob("*.tmp"))


def test_absent_corrupt_and_invalid_update(tmp_path, wikdict_package):
    spec, content = wikdict_package
    directory = tmp_path / "installed"
    with pytest.raises(wikdict.DictionaryMissing):
        wikdict.lookup("hello", directory, package=spec)
    path = wikdict.install_dictionary(directory, package=spec, session=download_session(content))
    with pytest.raises(wikdict.DictionaryCorrupt):
        wikdict.install_dictionary(directory, package=spec, session=download_session(b"wrong"))
    assert path.read_bytes() == content
    path.write_bytes(content[:-1] + b"x")
    with pytest.raises(wikdict.DictionaryCorrupt):
        wikdict.lookup("hello", directory, package=spec)


def test_corrupt_sqlite_with_matching_hash_is_rejected(tmp_path, wikdict_package):
    spec, _ = wikdict_package
    content = b"not a database"
    spec = replace(spec, size=len(content), sha256=hashlib.sha256(content).hexdigest())
    with pytest.raises(wikdict.DictionaryCorrupt):
        wikdict.install_dictionary(
            tmp_path / "installed", package=spec, session=download_session(content)
        )


def test_wiki_cleanup():
    assert (
        wikdict.clean_wiki("'''[[gramophone|record]]''' <i>disc</i> {{qualifier|rare}}")
        == "record disc"
    )
    assert (
        wikdict.clean_wiki("{{l|ru|привет}} &amp; [https://example.org greeting]")
        == "привет & greeting"
    )


@pytest.mark.parametrize("language,size", [("en", "20.9 MB"), ("ru", "20,9 МБ")])
def test_package_description_uses_decimal_megabytes(language, size):
    assert size in wikdict.PACKAGE.describe(language)
    assert "bytes" not in wikdict.PACKAGE.describe(language)
    assert wikdict.PACKAGE.size == 20938752
    assert wikdict.PACKAGE.version in wikdict.PACKAGE.description
    assert wikdict.PACKAGE.license in wikdict.PACKAGE.description

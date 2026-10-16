import concurrent.futures
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cambridge_audio import dictionary
from cambridge_audio.dictionary import CambridgeClient
from cambridge_audio.terminal import settings as terminal_settings

# Resolve Python 3.15's lazy import before PySide6 installs its import hook.
# The CLI itself never loads Qt; this only affects a mixed GUI/CLI test process.
_executor_type = concurrent.futures.ThreadPoolExecutor

MP3 = b"ID3\x04\x00\x00\x00\x00\x00\x00audio data"


@pytest.fixture(autouse=True)
def isolated_terminal_settings(tmp_path, monkeypatch):
    path = tmp_path / "config/tui-settings.json"
    monkeypatch.setattr(terminal_settings, "settings_path", lambda: path)
    return path


@pytest.fixture(autouse=True)
def request_clock(monkeypatch):
    clock = SimpleNamespace(now=1000.0)

    def advance(seconds):
        clock.now += seconds

    monkeypatch.setattr(dictionary, "monotonic", lambda: clock.now)
    monkeypatch.setattr(dictionary, "time", lambda: clock.now)
    monkeypatch.setattr(dictionary, "sleep", advance)
    monkeypatch.setattr(dictionary, "uniform", lambda low, high: 0.0)
    monkeypatch.setattr(dictionary, "_request_pacer", dictionary._RequestPacer())
    return clock


@pytest.fixture(autouse=True)
def isolated_dictionary_directory(tmp_path, monkeypatch):
    # Tests must not depend on a dictionary installed in the user's profile.
    monkeypatch.setattr(
        "cambridge_audio.wikdict.default_dictionary_dir", lambda: tmp_path / "dictionaries"
    )


HTML = """
<div class="entry-body__el">
  <div class="pos-header dpos-h">
    <div class="di-title"><span class="hw dhw">hello</span></div>
    <span class="us dpron-i">
      <span class="daud"><audio>
        <source type="audio/ogg" src="/us/media/hello.ogg">
        <source type="audio/mpeg" src="/us/media/hello-us.mp3">
      </audio></span><span class="ipa dipa">heˈloʊ</span>
    </span>
    <span class="uk dpron-i">
      <span class="daud"><audio>
        <source type="audio/mpeg" src="/us/media/hello-uk.mp3">
      </audio></span><span class="ipa dipa">heˈləʊ</span>
    </span>
  </div>
  <div class="def ddef_d db">used when meeting someone</div>
</div>
"""


@pytest.fixture
def client():
    with CambridgeClient() as instance:
        instance.session.get = Mock()
        yield instance


@pytest.fixture
def html():
    return HTML


@pytest.fixture
def mp3():
    return MP3


@pytest.fixture
def wikdict_package(tmp_path):
    import hashlib
    import sqlite3
    from dataclasses import replace

    from cambridge_audio import wikdict

    source = tmp_path / "source.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute(
            "CREATE TABLE translation (lexentry, sense_num, sense, written_rep, trans_list, score)"
        )
        connection.executemany(
            "INSERT INTO translation VALUES (?, NULL, ?, ?, ?, ?)",
            [
                ("eng/bank__Noun__1", "financial institution", "bank", "[[банк]] | банк", 100),
                (
                    "eng/bank__Noun__2",
                    "edge of a river",
                    "bank",
                    "[[берег|бе́рег]] | {{l|ru|берег}}",
                    90,
                ),
                ("eng/hello__Interjection__1", "greeting", "hello", "[[привет]]", 100),
            ],
        )
    content = source.read_bytes()
    return replace(
        wikdict.PACKAGE, size=len(content), sha256=hashlib.sha256(content).hexdigest()
    ), content

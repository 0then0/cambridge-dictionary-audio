import concurrent.futures
from unittest.mock import Mock

import pytest
import requests

from cambridge_audio.dictionary import BASE_URL, CambridgeClient

# Resolve Python 3.15's lazy import before PySide6 installs its import hook.
# The CLI itself never loads Qt; this only affects a mixed GUI/CLI test process.
_executor_type = concurrent.futures.ThreadPoolExecutor

MP3 = b"ID3\x04\x00\x00\x00\x00\x00\x00audio data"
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


def response(content, *, status=200, url=f"{BASE_URL}/us/dictionary/english/hello"):
    result = requests.Response()
    result.status_code = status
    result.url = url
    result._content = content.encode() if isinstance(content, str) else content
    return result


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

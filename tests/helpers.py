"""Reusable mock HTTP responses and streaming sessions."""

from unittest.mock import Mock

import requests

from cambridge_audio.dictionary import BASE_URL


def response(content, *, status=200, url=f"{BASE_URL}/us/dictionary/english/hello"):
    result = requests.Response()
    result.status_code = status
    result.url = url
    result._content = content.encode() if isinstance(content, str) else content
    result._content_consumed = True
    return result


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


BANK_FINANCIAL_DEFINITION = (
    "an organization where people and businesses can invest or borrow money, "
    "change it to foreign money, etc., or a building where these services are offered"
)
BANK_BILINGUAL_HTML = """
<div class="entry-body__el"><span class="pos">noun</span>
<div class="def-block"><div class="def ddef_d">
  an organization or place where you can borrow money , save money , etc
</div><div class="def-body"><span class="trans">банк</span></div></div>
<div class="def-block"><div class="def ddef_d">the land along the side of a river</div>
<div class="def-body"><span class="trans">берег</span></div></div>
<div class="def-block"><div class="def ddef_d">a large pile of snow, sand, or soil</div>
<div class="def-body"><span class="trans">занос, нанос</span></div></div></div>
"""

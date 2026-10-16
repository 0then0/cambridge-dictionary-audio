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

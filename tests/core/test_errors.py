"""Technical diagnostics are kept separate from actionable, localized UI summaries."""

import errno

import pytest
import requests

from cambridge_audio.dictionary import CambridgeError
from cambridge_audio.errors import diagnostic_details, friendly_error

RAW_TIMEOUT = (
    "Request failed for https://dictionary.cambridge.org/us/dictionary/english-russian/bay: "
    "HTTPSConnectionPool(host='dictionary.cambridge.org', port=443): "
    "Read timed out. (read timeout=15.0)"
)


@pytest.mark.parametrize(
    "error,expected",
    [
        (RAW_TIMEOUT, "too long"),
        (requests.ConnectionError("https://private.test:443"), "connect"),
        ("Cambridge blocked the request (HTTP 403): https://private.test", "refused access"),
        ("Cambridge rate limit reached (HTTP 429)", "too many requests"),
        ("HTTPError: 503 Server Error at https://private.test", "temporarily unavailable"),
        (PermissionError("/private/secret.txt"), "permissions"),
        (OSError(errno.ENOSPC, "full", "/private/secret.txt"), "free space"),
        (FileExistsError("/private/secret.txt"), "already in use"),
        (ValueError("invalid MP3 signature in /private/secret.txt"), "damaged"),
        (RuntimeError("unhandled 429a403b500c <b>secret</b>"), "complete the operation"),
    ],
)
def test_errors_have_safe_actionable_summary_and_complete_details(error, expected):
    summary = friendly_error(error)
    assert expected in summary
    assert all(
        secret not in summary
        for secret in ("https://", "HTTPSConnectionPool", "/private/", "secret", "15.0")
    )
    assert str(error) in diagnostic_details(error)
    russian = friendly_error(error, "ru")
    assert russian != summary
    assert any("а" <= char <= "я" for char in russian)


def test_diagnostics_keep_exception_chain_and_do_not_loop():
    cause = requests.ReadTimeout("low-level timeout")
    error = CambridgeError("request failed")
    error.__cause__ = cause
    cause.__context__ = error
    details = diagnostic_details(error)
    assert "CambridgeError: request failed" in details
    assert "ReadTimeout: low-level timeout" in details
    assert "too long" in friendly_error(error)


@pytest.mark.parametrize(
    "context,expected",
    [
        ("translation", "translation"),
        ("metadata", "Audio is saved"),
        ("export", "export"),
        ("library", "collection"),
        ("playback", "play"),
        ("settings", "settings"),
    ],
)
def test_unrecognized_errors_keep_operation_context(context, expected):
    assert expected in friendly_error(
        RuntimeError("private implementation detail"), context=context
    )

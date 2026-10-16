from unittest.mock import Mock

import pytest

from cambridge_audio import service
from cambridge_audio.dictionary import CambridgeError
from cambridge_audio.service import DownloadCancelled, download_recordings
from tests.helpers import response


def test_translation_failure_retains_recording(client, html, mp3, tmp_path):
    client.session.get.side_effect = [
        response(html),
        response(mp3),
        response("blocked", status=403),
    ]
    result = download_recordings(client, "hello", tmp_path, translation="russian")
    assert result.recordings[0].path.read_bytes() == mp3
    assert result.translations == ()
    assert "403" in result.translation_error


def test_second_accent_failure_reports_first_saved_recording(client, html, mp3, tmp_path):
    client.session.get.side_effect = [response(html), response(mp3), response("error", status=500)]
    saved = []
    with pytest.raises(CambridgeError):
        download_recordings(client, "hello", tmp_path, "both", on_recording=saved.append)
    assert len(saved) == 1
    assert saved[0].accent == "uk"
    assert saved[0].path.read_bytes() == mp3


def test_cancellation_prevents_next_request(client, html, tmp_path):
    client.session.get.return_value = response(html)
    check = Mock(side_effect=[None, DownloadCancelled("cancelled")])
    with pytest.raises(DownloadCancelled):
        download_recordings(client, "hello", tmp_path, check_cancelled=check)
    assert client.session.get.call_count == 1
    assert list(tmp_path.iterdir()) == []


def test_combined_recording_is_explicit(monkeypatch, client, tmp_path, mp3):
    client.session.get.return_value = response("missing", status=404)

    def combine(client, word, accent, destination, **kwargs):
        destination.write_bytes(mp3)

    monkeypatch.setattr(service, "combine_phrase", combine)
    result = download_recordings(client, "hello world", tmp_path, combine=True)
    assert result.recordings[0].combined
    assert result.recordings[0].ipa == ""


@pytest.mark.parametrize("word,accent", [("world", "us"), ("hello", "uk"), ("hello", "both")])
def test_wrong_redownload_target_is_rejected_before_network(client, tmp_path, word, accent):
    from cambridge_audio.service import Recording

    path = tmp_path / "hello.us.mp3"
    path.write_bytes(b"ID3original")
    target = Recording("hello", "us", path, "", "greeting")
    with pytest.raises(ValueError, match="does not match"):
        download_recordings(client, word, tmp_path, accent, target=target, overwrite=True)
    assert path.read_bytes() == b"ID3original"
    client.session.get.assert_not_called()

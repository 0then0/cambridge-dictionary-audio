"""Exercise the actual terminal UI without a network, player or display server."""

import time

from cambridge_audio.library import save_metadata
from cambridge_audio.service import Recording


def saved(directory, word="hello", accent="us"):
    record = Recording(word, accent, directory / f"{word}.{accent}.mp3", "heˈloʊ", "A greeting")
    record.path.write_bytes(b"ID3saved")
    save_metadata(record, ("привет",), "russian")
    return record


async def finish_download(app, pilot):
    await app.workers.wait_for_complete()
    await pilot.pause()


async def wait_for_ui(pilot, predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        await pilot.pause(0.01)
    assert predicate(), "Terminal UI did not reach the expected state"

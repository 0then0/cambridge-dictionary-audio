"""Batch lists: explicit choices, sequential saves, retries and stable identities."""

import json
from pathlib import Path

import pytest
import requests

from cambridge_audio import batch
from cambridge_audio.anki import export_apkg
from cambridge_audio.batch import (
    ERROR,
    EXISTING,
    FAILED,
    FOUND,
    MAX_BATCH_QUERIES,
    MISSING,
    SAVED,
    BatchRow,
    SaveSettings,
    lookup,
    options,
    parse_batch,
    pending_items,
    retry_lookups,
    save_item,
    selected_items,
)
from cambridge_audio.dictionary import BASE_URL, dictionary_url, parse_entries
from cambridge_audio.library import scan_recordings
from cambridge_audio.translations import cached_translation, edit_translation
from tests.conftest import HTML
from tests.core.test_apkg import inspect_package
from tests.core.test_shared_audio import AUDIO, BANK
from tests.helpers import response

# The source distribution ships tests/core without contracts/: keep the fixture inline.
LEAD = """
    <div class="entry-body__el" id="lead-metal"><div class="pos-header">
      <span class="hw">lead</span><span class="pos">noun</span>
      <span class="us"><span class="dpron-i"><span class="ipa">led</span>
      <audio><source src="/media/lead-metal.mp3"></audio></span></span></div>
      <div class="def-block" data-wl-senseid="metal"><div class="def ddef_d">a metal</div></div>
    </div>
    <div class="entry-body__el" id="lead-guide"><div class="pos-header">
      <span class="hw">lead</span><span class="pos">verb</span>
      <span class="us"><span class="dpron-i"><span class="ipa">liːd</span>
      <audio><source src="/media/lead-guide.mp3"></audio></span>
      <span class="dpron-i"><span class="ipa">lid</span>
      <audio><source src="/media/lead-guide-alt.mp3"></audio></span></span></div>
      <div class="def-block" data-wl-senseid="guide"><div class="def ddef_d">to guide</div></div>
      <div class="def-block" data-wl-senseid="first"><div class="def ddef_d">to be first</div></div>
    </div>"""


def router(client, pages, *, fail=(), calls=None):
    """Serve pages by URL; unknown dictionary pages are 404 and MP3s are valid audio."""
    calls = [] if calls is None else calls

    def get(url, timeout=None):
        calls.append(url)
        if any(part in url for part in fail):
            raise requests.ConnectionError("Connection refused")
        if url in pages:
            return response(pages[url], url=url)
        if url.endswith(".mp3"):
            return response(AUDIO, url=url)
        return response("not here", status=404, url=url)

    client.session.get.side_effect = get
    return calls


def found(query, html):
    row = BatchRow(query, FOUND, parse_entries(html, dictionary_url(query)))
    return row


def settings(directory, **values):
    return SaveSettings(directory, "en", **values)


def save_all(client, rows, directory, **values):
    for item in pending_items(rows):
        row = next(r for r in rows if r.query == item.query)
        row.outcomes[item.key] = save_item(client, item, settings(directory, **values))


def test_parse_skips_blank_lines_merges_duplicates_and_rejects_invalid_lines():
    parsed = parse_batch("Lead\n\n  lead \nGood   Morning\nhttps://x.org\nlead\n../etc\n")
    assert parsed.queries == ("lead", "good morning")
    assert parsed.duplicates == (("lead", 2),)
    assert parsed.invalid == ((5, "https://x.org"), (7, "../etc"))
    assert not parsed.ready
    assert parse_batch("lead\n\ngood morning").ready
    assert not parse_batch(" \n\n").ready


def test_limit_counts_unique_queries_and_is_reported_not_truncated():
    words = [f"word{i}" for i in range(MAX_BATCH_QUERIES)]
    assert parse_batch("\n".join(words + words)).ready
    parsed = parse_batch("\n".join(words + ["extra"]))
    assert parsed.over_limit and not parsed.ready
    assert len(parsed.queries) == MAX_BATCH_QUERIES + 1


def test_ambiguous_word_has_no_arbitrary_meaning_or_recording():
    row = found("lead", LEAD)
    row.reset_selection(("us",))
    assert len(row.meanings()) == 3
    assert row.selection == {}
    assert selected_items([row]) == ()
    guide = next(e for e in row.meanings() if e.definition == "to guide")
    row.select(guide.sense_id, ("us",))
    # Two US recordings: the user must choose one.
    assert row.selection[guide.sense_id] == {"us": ""}
    assert row.unresolved() == 1 and selected_items([row]) == ()
    second = options(guide, "us")[1]
    row.choose(guide.sense_id, "us", second.id)
    assert [i.variant for i in selected_items([row])] == [second]
    with pytest.raises(ValueError):
        row.choose(guide.sense_id, "us", "unknown")


def test_single_unambiguous_meaning_is_only_preselected():
    row = found("hello", HTML)
    row.reset_selection(("us", "uk"))
    entry = row.meanings()[0]
    assert set(row.selection[entry.sense_id]) == {"us", "uk"}
    assert not row.unresolved()


def test_several_meanings_and_both_accents_with_a_missing_accent():
    lead, hello = found("lead", LEAD), found("hello", HTML)
    regions = ("us", "uk")
    for row in (lead, hello):
        row.reset_selection(regions)
    metal, guide, first = lead.meanings()
    lead.select(metal.sense_id, regions)
    lead.select(first.sense_id, regions)
    lead.choose(first.sense_id, "us", options(first, "us")[0].id)
    # Lead has no UK recordings: only US items are planned, never a substitute.
    assert lead.selection[metal.sense_id] == {"us": options(metal, "us")[0].id}
    items = selected_items([lead, hello])
    planned = [(i.query, i.variant.entry.definition, i.variant.pronunciation.accent) for i in items]
    assert planned == [
        ("lead", "a metal", "us"),
        ("lead", "to be first", "us"),
        ("hello", "used when meeting someone", "us"),
        ("hello", "used when meeting someone", "uk"),
    ]
    assert len({i.key for i in items}) == 4


def test_missing_entry_is_not_reported_as_network_error(client):
    calls = router(client, {dictionary_url("lead"): LEAD}, fail=("english/broken",))
    assert lookup(client, "lead")[0] == FOUND
    status, entries, details = lookup(client, "zzqx")
    assert status == MISSING and entries == () and "not found" in details.casefold()
    status, _, details = lookup(client, "broken")
    assert status == ERROR and "Connection" in details
    rows = [BatchRow("a", FOUND), BatchRow("b", MISSING), BatchRow("c", ERROR), BatchRow("d")]
    assert retry_lookups(rows) == (2, 3)
    assert len(calls) == 3


def test_saved_meanings_shared_audio_and_personal_translation(client, tmp_path):
    calls = router(client, {})
    first = found("bank", BANK)
    money, river = first.meanings()
    first.select(money.sense_id, ("us",))
    save_all(client, [first], tmp_path)
    saved = scan_recordings(tmp_path)
    assert len(saved) == 1 and len(calls) == 1
    edit_translation(saved[0], "russian", "личный перевод")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    # A new batch: the saved meaning is recognized, the new one reuses the MP3.
    second = found("bank", BANK)
    second.select(money.sense_id, ("us",))
    second.select(river.sense_id, ("us",))
    save_all(client, [second], tmp_path, translation_language=None)
    outcomes = sorted(o for o, _ in second.outcomes.values())
    assert outcomes == [EXISTING, SAVED]
    assert len(calls) == 1  # Shared audio needs no second download.
    records = scan_recordings(tmp_path)
    assert len(records) == 2 and len({r.recording.path for r in records}) == 1
    for name, content in before.items():
        assert (tmp_path / name).read_bytes() == content  # Existing record untouched.
    money_record = next(r for r in records if r.recording.definition == "money")
    assert cached_translation(money_record, "russian").texts == ("личный перевод",)


def test_partial_failure_retries_only_unfinished_items(client, tmp_path):
    lead = found("lead", LEAD)
    metal, guide, _ = lead.meanings()
    lead.select(metal.sense_id, ("us",))
    lead.select(guide.sense_id, ("us",))
    lead.choose(guide.sense_id, "us", options(guide, "us")[0].id)
    calls = router(client, {}, fail=("lead-guide.mp3",))
    save_all(client, [lead], tmp_path)
    assert sorted(o for o, _ in lead.outcomes.values()) == [FAILED, SAVED]
    failed = next(o for o in lead.outcomes.values() if o[0] == FAILED)
    assert "Connection" in failed[1]
    saved = scan_recordings(tmp_path)
    assert len(saved) == 1
    metal_json = saved[0].recording.reference.read_bytes()

    retry = pending_items([lead])
    assert [i.variant.entry.definition for i in retry] == ["to guide"]
    calls.clear()
    router(client, {}, calls=calls)
    save_all(client, [lead], tmp_path)
    assert all(o == SAVED for o, _ in lead.outcomes.values())
    assert calls == [f"{BASE_URL}/media/lead-guide.mp3"]
    assert saved[0].recording.reference.read_bytes() == metal_json
    assert pending_items([lead]) == ()
    assert len(scan_recordings(tmp_path)) == 2


def test_translation_failure_keeps_saved_audio(client, tmp_path, monkeypatch):
    router(client, {}, fail=("english-russian",))
    row = found("hello", HTML)
    row.reset_selection(("us",))
    save_all(client, [row], tmp_path, translation_language="russian")
    ((outcome, details),) = row.outcomes.values()
    assert outcome == SAVED and details
    assert len(scan_recordings(tmp_path)) == 1


def test_cancellation_after_publication_counts_as_saved(client, tmp_path):
    from cambridge_audio.service import DownloadCancelled

    router(client, {})
    row = found("hello", HTML)
    row.reset_selection(("us",))
    (item,) = pending_items([row])
    published = []

    def cancel_after_publication():
        if scan_recordings(tmp_path):
            published.append(True)
            raise DownloadCancelled("cancelled")

    result = save_item(
        client,
        item,
        settings(tmp_path, translation_language="russian"),
        check_cancelled=cancel_after_publication,
    )
    assert result == (SAVED, "") and published
    row2 = found("bank", BANK)
    row2.select(row2.meanings()[0].sense_id, ("us",))
    (item,) = pending_items([row2])

    def cancel_now():
        raise DownloadCancelled("cancelled")

    with pytest.raises(DownloadCancelled):
        save_item(client, item, settings(tmp_path), check_cancelled=cancel_now)
    assert len(scan_recordings(tmp_path)) == 1


def test_repeated_batches_keep_collection_and_anki_identities(client, tmp_path):
    router(client, {})

    def run():
        rows = [found("bank", BANK), found("hello", HTML)]
        for row in rows:
            for entry in row.meanings():
                row.select(entry.sense_id, ("us", "uk"))
        save_all(client, rows, tmp_path / "audio")
        return rows

    first = run()
    assert [o for r in first for o, _ in r.outcomes.values()] == [SAVED] * 4
    ids = sorted(s.recording.id for s in scan_recordings(tmp_path / "audio"))
    notes, *_ = inspect_package(
        export_apkg(scan_recordings(tmp_path / "audio"), tmp_path / "one.apkg"), tmp_path
    )
    second = run()
    assert [o for r in second for o, _ in r.outcomes.values()] == [EXISTING] * 4
    assert sorted(s.recording.id for s in scan_recordings(tmp_path / "audio")) == ids
    again, *_ = inspect_package(
        export_apkg(scan_recordings(tmp_path / "audio"), tmp_path / "two.apkg"), tmp_path
    )
    assert sorted(n[0] for n in again) == sorted(n[0] for n in notes)
    assert len(notes) == 4
    for saved in scan_recordings(tmp_path / "audio"):
        assert json.loads(saved.recording.reference.read_text())["version"] == 3


def test_core_module_has_no_qt_dependency():
    assert "PySide6" not in Path(batch.__file__).read_text()

"""Batch word lists: parsing, explicit meaning selection and the frozen save plan.

This module holds no Qt objects. The desktop dialog keeps a list of ``BatchRow``
values in memory; workers receive immutable ``BatchItem`` plans and report results
by item key, so late results never depend on mutable widget state.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .dictionary import AudioNotFoundError, CambridgeClient, Entry, Variant, variants

# A bounded batch keeps sequential, rate-limited lookups to a few minutes.
MAX_BATCH_QUERIES = 100

PENDING = "pending"
SEARCHING = "searching"
FOUND = "found"
MISSING = "missing"
ERROR = "error"

SAVED = "saved"
EXISTING = "existing"
FAILED = "failed"


@dataclass(frozen=True)
class BatchInput:
    queries: tuple[str, ...] = ()
    # Normalized query and how many extra lines repeated it.
    duplicates: tuple[tuple[str, int], ...] = ()
    # One-based line number and the original text of each rejected line.
    invalid: tuple[tuple[int, str], ...] = ()

    @property
    def over_limit(self) -> bool:
        return len(self.queries) > MAX_BATCH_QUERIES

    @property
    def ready(self) -> bool:
        return bool(self.queries) and not self.invalid and not self.over_limit


def parse_batch(text: str, language: str = "en") -> BatchInput:
    """One word or phrase per line, using the single-word normalization rules."""
    from .dictionary import normalize_word

    queries: dict[str, int] = {}
    invalid = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            query = normalize_word(line, language)
        except ValueError:
            invalid.append((number, line.strip()))
            continue
        queries[query] = queries.get(query, 0) + 1
    return BatchInput(
        tuple(queries),
        tuple((query, count - 1) for query, count in queries.items() if count > 1),
        tuple(invalid),
    )


def accent_regions(accent: str) -> tuple[str, ...]:
    return ("us", "uk") if accent == "both" else (accent,)


def meanings(entries: tuple[Entry, ...]) -> tuple[Entry, ...]:
    """Distinct source meanings that own at least one recording."""
    unique: dict[str, Entry] = {}
    for entry in entries:
        if entry.pronunciations:
            unique.setdefault(entry.sense_id, entry)
    return tuple(unique.values())


def options(entry: Entry, region: str) -> tuple[Variant, ...]:
    return variants((entry,), region)


def selectable(entry: Entry, regions: tuple[str, ...]) -> bool:
    return any(options(entry, region) for region in regions)


@dataclass
class BatchRow:
    query: str
    status: str = PENDING
    entries: tuple[Entry, ...] = ()
    details: str = ""
    # Selected meaning sense ID -> region -> variant ID ("" while the user must choose).
    selection: dict[str, dict[str, str]] = field(default_factory=dict)
    # Item key -> (outcome, details). Completed keys are never planned again.
    outcomes: dict[str, tuple[str, str]] = field(default_factory=dict)

    def meanings(self) -> tuple[Entry, ...]:
        return meanings(self.entries)

    def entry(self, sense_id: str) -> Entry | None:
        return next((e for e in self.meanings() if e.sense_id == sense_id), None)

    def select(self, sense_id: str, regions: tuple[str, ...], checked: bool = True) -> None:
        entry = self.entry(sense_id)
        if not checked or entry is None or not selectable(entry, regions):
            self.selection.pop(sense_id, None)
            return
        # Only a single recording per accent is implied; several need an explicit choice.
        self.selection.setdefault(
            sense_id,
            {
                region: choices[0].id if len(choices) == 1 else ""
                for region in regions
                if (choices := options(entry, region))
            },
        )

    def choose(self, sense_id: str, region: str, variant_id: str) -> None:
        entry = self.entry(sense_id)
        if (
            entry is None
            or sense_id not in self.selection
            or region not in self.selection[sense_id]
            or variant_id not in {v.id for v in options(entry, region)}
        ):
            raise ValueError("The selected meaning/audio is no longer available. Choose again.")
        self.selection[sense_id][region] = variant_id

    def reset_selection(self, regions: tuple[str, ...]) -> None:
        """Preselect only one unambiguous meaning; never guess among several."""
        self.selection.clear()
        candidates = [e for e in self.meanings() if selectable(e, regions)]
        if len(candidates) == 1 and all(
            len(options(candidates[0], region)) <= 1 for region in regions
        ):
            self.select(candidates[0].sense_id, regions)

    def unresolved(self) -> int:
        return sum(1 for chosen in self.selection.values() if "" in chosen.values())


@dataclass(frozen=True)
class BatchItem:
    """One meaning in one accent, frozen when the user confirms saving."""

    key: str
    query: str
    entries: tuple[Entry, ...]
    variant: Variant


def item_key(query: str, variant: Variant) -> str:
    # Normalized queries never contain ":"; one batch holds each query once.
    return f"{query}:{variant.id}"


def selected_items(rows: list[BatchRow]) -> tuple[BatchItem, ...]:
    items = []
    for row in rows:
        if row.status != FOUND:
            continue
        for sense_id, chosen in row.selection.items():
            entry = row.entry(sense_id)
            if entry is None:
                continue
            for region, variant_id in chosen.items():
                variant = next((v for v in options(entry, region) if v.id == variant_id), None)
                if variant is not None:
                    key = item_key(row.query, variant)
                    items.append(BatchItem(key, row.query, row.entries, variant))
    return tuple(items)


def pending_items(rows: list[BatchRow]) -> tuple[BatchItem, ...]:
    """Selected items without a completed outcome: the next save or retry."""
    outcomes = {row.query: row.outcomes for row in rows}
    return tuple(
        item
        for item in selected_items(rows)
        if outcomes[item.query].get(item.key, ("", ""))[0] not in {SAVED, EXISTING}
    )


def retry_lookups(rows: list[BatchRow]) -> tuple[int, ...]:
    """Rows a search should (re)visit: never searched, interrupted or failed by error."""
    return tuple(i for i, row in enumerate(rows) if row.status in {PENDING, SEARCHING, ERROR})


def lookup(client: CambridgeClient, query: str) -> tuple[str, tuple[Entry, ...], str]:
    """Classify one search: an absent entry is not a network or service error."""
    from .errors import diagnostic_details
    from .service import DownloadCancelled

    try:
        entries = client.lookup(query)
    except AudioNotFoundError as exc:
        return MISSING, (), diagnostic_details(exc)
    except DownloadCancelled:
        raise
    except Exception as exc:
        return ERROR, (), diagnostic_details(exc)
    # An entry without recordings is found; the dialog reports the missing audio.
    return FOUND, entries, ""


@dataclass(frozen=True)
class SaveSettings:
    """Destination and options captured when the user confirms saving."""

    output_dir: Path
    language: str
    translation_language: str | None = None
    dictionary_dir: Path | None = None
    audio_cache_dir: Path | None = None


def save_item(
    client: CambridgeClient,
    item: BatchItem,
    settings: SaveSettings,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[str, str]:
    """Save one item through the shared service; existing records stay untouched.

    Returns ``(outcome, details)``. ``details`` of a saved item is an optional
    translation problem: the audio and its record are already published.
    """
    from .errors import diagnostic_details
    from .library import _METADATA_LOCK, scan_recordings
    from .service import DownloadCancelled, download_recordings, saved_choice_matches

    try:
        with _METADATA_LOCK:
            saved = scan_recordings(settings.output_dir)
    except OSError as exc:
        return FAILED, diagnostic_details(exc)
    if any(saved_choice_matches(s.recording, item.query, item.variant) for s in saved):
        return EXISTING, ""
    published = []
    try:
        result = download_recordings(
            client,
            item.query,
            settings.output_dir,
            item.variant.pronunciation.accent,
            translation=settings.translation_language,
            variant_id=item.variant.id,
            entries=item.entries,
            dictionary_dir=settings.dictionary_dir,
            audio_cache_dir=settings.audio_cache_dir,
            on_recording=published.append,
            check_cancelled=check_cancelled,
        )
    except DownloadCancelled:
        if published:
            # Cancellation after publication skipped only the optional translation.
            return SAVED, ""
        raise
    except Exception as exc:
        if published:
            return SAVED, diagnostic_details(exc)
        return FAILED, diagnostic_details(exc)
    return SAVED, result.translation_error

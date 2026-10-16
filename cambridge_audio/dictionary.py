"""Cambridge Dictionary HTML parsing and MP3 downloading."""

import hashlib
import math
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from random import uniform
from tempfile import NamedTemporaryFile
from threading import Lock
from time import monotonic, sleep, time
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .i18n import translate

BASE_URL = "https://dictionary.cambridge.org"
DEFAULT_REQUESTS_HEADERS = {"User-Agent": "Mozilla/5.0"}
_REQUEST_INTERVAL = 1.0
_MAX_WAIT = 30.0
_MAX_RETRIES = 2
_PAGE_CACHE_SIZE = 64


class CambridgeError(Exception):
    """A dictionary lookup or download failed."""


class CambridgeBlockedError(CambridgeError):
    """Cambridge refused access or returned an anti-bot page."""


class AudioNotFoundError(CambridgeError):
    """The requested pronunciation is absent."""


class _RequestPacer:
    """Share request spacing and server cooldowns across clients in this process."""

    def __init__(self):
        self._lock = Lock()
        self._next_request = 0.0

    def defer(self, seconds: float):
        with self._lock:
            self._next_request = max(self._next_request, monotonic() + seconds)

    def wait(self, check_cancelled: Callable[[], None] | None, language: str):
        while True:
            if check_cancelled:
                check_cancelled()
            with self._lock:
                remaining = self._next_request - monotonic()
                if remaining <= 0:
                    self._next_request = monotonic() + _REQUEST_INTERVAL
                    return
            if remaining > _MAX_WAIT:
                raise CambridgeBlockedError(
                    translate(
                        "Cambridge rate limit reached. Try again in {seconds} seconds.",
                        language,
                        seconds=math.ceil(remaining),
                    )
                )
            # Never hold the shared lock while sleeping or checking cancellation.
            sleep(min(remaining, 0.1) if check_cancelled else remaining)


_request_pacer = _RequestPacer()


def _retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if re.fullmatch(r"[0-9]+", value):
        try:
            seconds = float(value)
        except ValueError:
            return None
        # Keep even an unreasonably large server cooldown; do not retry early.
        return min(seconds, 1e100)
    try:
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            return None
        return max(0.0, date.timestamp() - time())
    except (ValueError, TypeError, OverflowError):
        return None


@dataclass(frozen=True)
class Pronunciation:
    accent: str
    url: str
    ipa: str = ""

    @property
    def id(self) -> str:
        return stable_id("cambridge-audio", self.accent, self.url)


@dataclass(frozen=True)
class Entry:
    word: str
    definition: str
    pronunciations: tuple[Pronunciation, ...]
    part_of_speech: str = ""
    entry_id: str = ""
    sense_id: str = ""
    source_url: str = ""
    lemma: str = ""
    legacy_ids: tuple[str, ...] = ()


def stable_id(*values: str) -> str:
    return hashlib.sha256("\0".join(values).encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class Variant:
    entry: Entry
    pronunciation: Pronunciation

    @property
    def id(self) -> str:
        return stable_id(self.entry.sense_id, self.pronunciation.accent, self.pronunciation.url)

    @property
    def label(self) -> str:
        return (
            f"{self.pronunciation.accent.upper()} · {self.entry.part_of_speech} · "
            f"{self.entry.definition[:55]} · /{self.pronunciation.ipa}/"
        )


def variants(entries: tuple[Entry, ...], accent: str = "us") -> tuple[Variant, ...]:
    return tuple(
        {
            v.id: v
            for e in entries
            for p in e.pronunciations
            if accent == "both" or p.accent == accent
            for v in (Variant(e, p),)
        }.values()
    )


class SelectionRequired(CambridgeError):
    def __init__(self, choices: tuple[Variant, ...], entries: tuple[Entry, ...], language="en"):
        self.choices = choices
        self.entries = entries
        super().__init__(
            "Choose a meaning and its audio:\n" + "\n".join(f"{v.id}  {v.label}" for v in choices)
        )


def normalize_word(word: str, language: str = "en") -> str:
    word = " ".join(word.strip().lower().split())
    if not word or not re.fullmatch(r"[a-z0-9]+(?:[ '\-][a-z0-9]+)*", word):
        raise ValueError(
            translate("Enter an English word or phrase without URLs or path separators.", language)
        )
    return word


def audio_filename(word: str, accent: str, variant_id: str = "") -> str:
    """Avoid Windows device names on every platform so files remain portable."""
    if word in {"con", "prn", "aux", "nul"} or re.fullmatch(r"(?:com|lpt)[1-9]", word):
        word = f"_{word}"
    if variant_id:
        word = f"{word[:80].rstrip()}--{variant_id}"
    elif len(word) > 100:
        word = f"{word[:80].rstrip()}--{stable_id(word)}"
    return f"{word}.{accent}.mp3"


def dictionary_url(word: str, mode: str = "english", language: str = "en") -> str:
    if not re.fullmatch(r"english(?:-[a-z]+)?", mode):
        raise ValueError(translate("Unsupported dictionary.", language))
    slug = normalize_word(word, language).replace(" ", "-")
    return f"{BASE_URL}/us/dictionary/{mode}/{quote(slug, safe='-')}"


def parse_entries(html: str | bytes, page_url: str) -> tuple[Entry, ...]:
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    fallback_blocks = {}
    for block in soup.select(".entry-body__el"):
        header = block.select_one(".pos-header, .dpos-h")
        if header is None:
            continue
        headword = header.select_one(".hw, .headword, .di-title")
        pos = header.select_one(".pos, .dpos")
        word = headword.get_text(" ", strip=True) if headword else ""
        part = pos.get_text(" ", strip=True) if pos else ""
        pronunciations = []
        seen = set()
        for region in header.select(".uk, .us"):
            accent = "us" if "us" in region.get("class", []) else "uk"
            for source in region.select("audio source[src]"):
                url = urljoin(page_url, str(source["src"]))
                parsed = urlparse(url)
                if (
                    parsed.scheme != "https"
                    or parsed.netloc != "dictionary.cambridge.org"
                    or not parsed.path.lower().endswith(".mp3")
                    or (accent, url) in seen
                ):
                    continue
                # Each dpron-i owns its IPA, even with several pronunciations in one region.
                owner = source.find_parent(class_="dpron-i") or region
                ipa = owner.select_one(".ipa")
                pronunciations.append(
                    Pronunciation(accent, url, ipa.get_text(strip=True) if ipa else "")
                )
                seen.add((accent, url))
        upstream = str(block.get("id") or header.get("id") or "")
        # Source IDs take precedence over mutable definitions and pronunciation lists.
        # Without an upstream block ID, word + POS is only a fallback namespace;
        # definition fingerprints below distinguish senses without guessing on edits.
        fallback = word + ":" + part
        ordinal = fallback_blocks.get(fallback, 0)
        fallback_blocks[fallback] = ordinal + 1
        entry_id = stable_id(
            "cambridge-entry", page_url.split("#")[0], upstream or f"{fallback}:{ordinal}"
        )
        legacy_entry = stable_id(
            "cambridge",
            word,
            part,
            str(block.get("id", "")),
            *sorted(p.url for p in pronunciations),
        )
        fallback_senses = {}
        for definition in block.select(".def.ddef_d") or [None]:
            text = (
                definition.get_text(" ", strip=True).removesuffix(":").rstrip()
                if definition
                else ""
            )
            sense = definition.find_parent(class_="def-block") if definition else None
            sense_key = str(sense.get("data-wl-senseid") or sense.get("id") or "") if sense else ""
            occurrence = fallback_senses.get(text, 0)
            fallback_senses[text] = occurrence + 1
            entries.append(
                Entry(
                    word,
                    text,
                    tuple(pronunciations),
                    part,
                    entry_id,
                    stable_id("cambridge-sense", page_url.split("#")[0], sense_key)
                    if sense_key
                    else stable_id(entry_id, "text", text, str(occurrence)),
                    page_url,
                    word,
                    tuple(
                        stable_id(stable_id(legacy_entry, sense_key, text), p.accent, p.url)
                        for p in pronunciations
                    ),
                )
            )
    return tuple(entries)


def is_mp3(content: bytes) -> bool:
    return content.startswith(b"ID3") or (
        len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0
    )


def save_mp3(
    content: bytes, destination: Path, *, overwrite: bool = False, language: str = "en"
) -> Path:
    """Validate before writing; replace existing files atomically when requested."""
    if not is_mp3(content):
        raise CambridgeError(
            translate(
                "The server returned an empty response or data that does not look like MP3.",
                language,
            )
        )
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(dir=destination.parent, suffix=".tmp", delete=False) as f:
            temporary = Path(f.name)
            f.write(content)
        if overwrite:
            temporary.replace(destination)
        elif os.name == "nt":
            # Windows rename refuses an existing destination, including on exFAT.
            temporary.rename(destination)
        else:
            # Publish a complete file exclusively; never replace a concurrent writer.
            os.link(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination


class CambridgeClient:
    def __init__(
        self,
        timeout: float = 15.0,
        headers: dict | None = None,
        *,
        language: str = "en",
        check_cancelled: Callable[[], None] | None = None,
    ):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError(translate("Timeout must be a positive finite number.", language))
        self.language = language
        self.timeout = timeout
        self.check_cancelled = check_cancelled
        self._pages: dict[str, requests.Response] = {}
        self.session = requests.Session()
        self.session.headers.update(headers or DEFAULT_REQUESTS_HEADERS)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._pages.clear()
        self.session.close()

    def _get(
        self, url: str, *, missing_entry: bool = False, cache: bool = False
    ) -> requests.Response:
        if self.check_cancelled:
            self.check_cancelled()
        if cache and url in self._pages:
            return self._pages[url]
        try:
            for attempt in range(_MAX_RETRIES + 1):
                _request_pacer.wait(self.check_cancelled, self.language)
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code == 429:
                    delay = _retry_after(response.headers.get("Retry-After"))
                    if delay is None:
                        delay = 2 ** (attempt + 1) + uniform(0, 0.5)
                    _request_pacer.defer(delay)
                    response.close()
                    if attempt < _MAX_RETRIES:
                        continue
                    raise CambridgeBlockedError(
                        translate(
                            "Cambridge rate limit reached (HTTP 429). Try again later.",
                            self.language,
                        )
                    )
                if missing_entry and response.status_code == 404:
                    raise AudioNotFoundError(
                        translate("Dictionary entry not found: {url}", self.language, url=url)
                    )
                if response.status_code == 403:
                    raise CambridgeBlockedError(
                        f"Cambridge blocked the request (HTTP {response.status_code}): {url}"
                    )
                break
            response.raise_for_status()
            if cache:
                self._check_blocked(response)
                if len(self._pages) >= _PAGE_CACHE_SIZE:
                    del self._pages[next(iter(self._pages))]
                self._pages[url] = response
            return response
        except requests.RequestException as exc:
            raise CambridgeError(
                translate("Request failed for {url}: {error}", self.language, url=url, error=exc)
            ) from exc

    def lookup(self, word: str) -> tuple[Entry, ...]:
        response = self._get(
            dictionary_url(word, language=self.language), missing_entry=True, cache=True
        )
        entries = parse_entries(response.content, response.url)
        if not entries:
            self._pages.pop(dictionary_url(word, language=self.language), None)
            raise AudioNotFoundError(
                translate("No dictionary entry found for '{word}'.", self.language, word=word)
            )
        return entries

    def download(
        self,
        entries: tuple[Entry, ...],
        accent: str,
        destination: Path,
        *,
        overwrite: bool = False,
    ) -> Pronunciation:
        if accent not in {"uk", "us"}:
            raise ValueError(translate("Accent must be uk or us.", self.language))
        pronunciation = next(
            (p for entry in entries for p in entry.pronunciations if p.accent == accent),
            None,
        )
        if pronunciation is None:
            raise AudioNotFoundError(
                translate("No {accent} pronunciation found.", self.language, accent=accent.upper())
            )
        if destination.exists() and not overwrite:
            raise FileExistsError(
                translate(
                    "File already exists: {path}. Use --overwrite to replace it.",
                    self.language,
                    path=destination,
                )
            )
        response = self._get(pronunciation.url)
        save_mp3(response.content, destination, overwrite=overwrite, language=self.language)
        return pronunciation

    @staticmethod
    def _check_blocked(response):
        text = response.content[:20000].lower()
        if any(marker in text for marker in (b"cf-chl-", b"captcha", b"access denied")):
            raise CambridgeBlockedError("Cambridge returned a blocking page.")

    def translation_options(self, word: str, language: str, definition: str = "", part: str = ""):
        from .translations import TranslationOption

        # Keep translations() as the public text lookup and permit existing client adapters.
        self._translation_html = None
        texts = self.translations(word, language)
        if self._translation_html is None:
            return (
                (TranslationOption(stable_id(*texts), texts, "", "", "", False),) if texts else ()
            )
        soup = BeautifulSoup(self._translation_html, "html.parser")
        options = []
        for block in soup.select(".entry-body__el .def-body"):
            texts = tuple(
                dict.fromkeys(t.get_text(" ", strip=True) for t in block.select(".trans"))
            )
            if not texts:
                continue
            owner = block.find_parent(class_="entry-body__el")
            tag = owner.select_one(".pos, .dpos") if owner else None
            pos = tag.get_text(" ", strip=True) if tag else ""
            sense = block.find_parent(class_="def-block") or block
            tag = sense.select_one(".def.ddef_d")
            gloss = tag.get_text(" ", strip=True).removesuffix(":").rstrip() if tag else ""
            matched = bool(
                definition
                and gloss.casefold() == definition.casefold()
                and (not part or pos.casefold() == part.casefold())
            )
            options.append(
                TranslationOption(
                    stable_id(pos, gloss, *texts),
                    texts,
                    gloss,
                    pos,
                    dictionary_url(word, f"english-{language}"),
                    matched,
                )
            )
        matches = tuple(o for o in options if o.matched)
        same_part = tuple(
            o for o in options if part and o.part_of_speech.casefold() == part.casefold()
        )
        return matches or tuple({o.id: o for o in same_part or options}.values())

    def translations(self, word: str, language: str) -> tuple[str, ...]:
        response = self._get(
            dictionary_url(word, f"english-{language}", self.language),
            missing_entry=True,
            cache=True,
        )
        self._translation_html = response.content
        soup = BeautifulSoup(response.content, "html.parser")
        return tuple(
            dict.fromkeys(
                tag.get_text(" ", strip=True)
                for tag in soup.select(".entry-body__el .def-body .trans")
            )
        )

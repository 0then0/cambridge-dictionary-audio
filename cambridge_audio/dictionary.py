"""Cambridge Dictionary HTML parsing and MP3 downloading."""

import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .i18n import translate

BASE_URL = "https://dictionary.cambridge.org"
DEFAULT_REQUESTS_HEADERS = {"User-Agent": "Mozilla/5.0"}


class CambridgeError(Exception):
    """A dictionary lookup or download failed."""


class AudioNotFoundError(CambridgeError):
    """The requested pronunciation is absent."""


@dataclass(frozen=True)
class Pronunciation:
    accent: str
    url: str
    ipa: str = ""


@dataclass(frozen=True)
class Entry:
    word: str
    definition: str
    pronunciations: tuple[Pronunciation, ...]


def normalize_word(word: str, language: str = "en") -> str:
    word = " ".join(word.strip().lower().split())
    if not word or not re.fullmatch(r"[a-z0-9]+(?:[ '\-][a-z0-9]+)*", word):
        raise ValueError(
            translate("Enter an English word or phrase without URLs or path separators.", language)
        )
    return word


def audio_filename(word: str, accent: str) -> str:
    """Avoid Windows device names on every platform so files remain portable."""
    if word in {"con", "prn", "aux", "nul"} or re.fullmatch(r"(?:com|lpt)[1-9]", word):
        word = f"_{word}"
    return f"{word}.{accent}.mp3"


def dictionary_url(word: str, mode: str = "english", language: str = "en") -> str:
    if not re.fullmatch(r"english(?:-[a-z]+)?", mode):
        raise ValueError(translate("Unsupported dictionary.", language))
    slug = normalize_word(word, language).replace(" ", "-")
    return f"{BASE_URL}/us/dictionary/{mode}/{quote(slug, safe='-')}"


def parse_entries(html: str | bytes, page_url: str) -> tuple[Entry, ...]:
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for block in soup.select(".entry-body__el"):
        header = block.select_one(".pos-header, .dpos-h")
        if header is None:
            continue
        headword = header.select_one(".hw, .headword, .di-title")
        definition = block.select_one(".def.ddef_d")
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
                ipa = region.select_one(".ipa")
                pronunciations.append(
                    Pronunciation(accent, url, ipa.get_text(strip=True) if ipa else "")
                )
                seen.add((accent, url))
        entries.append(
            Entry(
                headword.get_text(" ", strip=True) if headword else "",
                definition.get_text(" ", strip=True).removesuffix(":").rstrip()
                if definition
                else "",
                tuple(pronunciations),
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
    def __init__(self, timeout: float = 15.0, headers: dict | None = None, *, language: str = "en"):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError(translate("Timeout must be a positive finite number.", language))
        self.language = language
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(headers or DEFAULT_REQUESTS_HEADERS)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.session.close()

    def _get(self, url: str, *, missing_entry: bool = False) -> requests.Response:
        try:
            response = self.session.get(url, timeout=self.timeout)
            if missing_entry and response.status_code == 404:
                raise AudioNotFoundError(
                    translate("Dictionary entry not found: {url}", self.language, url=url)
                )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            raise CambridgeError(
                translate("Request failed for {url}: {error}", self.language, url=url, error=exc)
            ) from exc

    def lookup(self, word: str) -> tuple[Entry, ...]:
        response = self._get(dictionary_url(word, language=self.language), missing_entry=True)
        entries = parse_entries(response.content, response.url)
        if not entries:
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

    def translations(self, word: str, language: str) -> tuple[str, ...]:
        response = self._get(dictionary_url(word, f"english-{language}", self.language))
        soup = BeautifulSoup(response.content, "html.parser")
        return tuple(
            dict.fromkeys(
                tag.get_text(" ", strip=True)
                for tag in soup.select(".entry-body__el .def-body .trans")
            )
        )

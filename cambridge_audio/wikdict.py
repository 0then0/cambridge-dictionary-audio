"""Pinned, compact WikDict language pair; explicit, verified atomic installation."""

import hashlib
import os
import re
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from tempfile import NamedTemporaryFile

import requests
from bs4 import BeautifulSoup

from .dictionary import CambridgeError, stable_id


@dataclass(frozen=True)
class DictionaryPackage:
    version: str = "2_2026-06"
    url: str = "https://download.wikdict.com/dictionaries/sqlite/2_2026-06/en-ru.sqlite3"
    size: int = 20938752
    sha256: str = "3f65395883b996131c9b7a7b7b7c14c1b4458c892fae0050decd71dc0a3b4b0a"
    license: str = "CC BY-SA 4.0"
    license_url: str = "https://creativecommons.org/licenses/by-sa/4.0/"

    @property
    def description(self):
        return self.describe()

    def describe(self, language: str = "en") -> str:
        size = f"{self.size / 1_000_000:.1f}"
        if language == "ru":
            size = size.replace(".", ",") + " МБ"
        else:
            size += " MB"
        return f"WikDict en → ru · {self.version} · {size} · {self.license}"


PACKAGE = DictionaryPackage()
ATTRIBUTION = (
    "WikDict by Karl Bartel, https://www.wikdict.com/page/download. "
    "Wiktionary contributors via DBnary (https://kaiko.getalp.org/about-dbnary/). "
    "CC BY-SA 4.0: https://creativecommons.org/licenses/by-sa/4.0/. "
    "Displayed/exported translations have wiki markup removed and duplicates removed. "
    "Dictionary content is separate from the application's Apache-2.0 code."
)


class DictionaryMissing(CambridgeError):
    pass


class DictionaryCorrupt(CambridgeError):
    pass


def default_dictionary_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library/Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return root / "cambridge-dictionary-audio/dictionaries"


def package_path(directory: Path | None = None, package: DictionaryPackage = PACKAGE) -> Path:
    return (directory or default_dictionary_dir()) / f"en-ru-{package.version}.sqlite3"


def validate_package(path: Path, package: DictionaryPackage = PACKAGE) -> None:
    if not path.is_file():
        raise DictionaryMissing("Local WikDict en → ru is not installed. Use Install WikDict.")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if path.stat().st_size != package.size or digest.hexdigest() != package.sha256:
        raise DictionaryCorrupt("Local WikDict failed size / SHA-256 verification. Reinstall it.")
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            if connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise DictionaryCorrupt("WikDict SQLite integrity check failed.")
            connection.execute(
                "SELECT written_rep, lexentry, sense, trans_list FROM translation LIMIT 1"
            )
    except sqlite3.Error as exc:
        raise DictionaryCorrupt(f"Unsupported / damaged WikDict SQLite: {exc}") from exc


def install_dictionary(
    directory: Path | None = None,
    *,
    package: DictionaryPackage = PACKAGE,
    session=None,
    progress=None,
    check_cancelled=None,
) -> Path:
    destination = package_path(directory, package)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    own_session = session is None
    session = session or requests.Session()
    try:
        with session.get(package.url, stream=True, timeout=30) as response:
            response.raise_for_status()
            with NamedTemporaryFile(dir=destination.parent, suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                received = 0
                for chunk in response.iter_content(256 * 1024):
                    if check_cancelled:
                        check_cancelled()
                    received += len(chunk)
                    if received > package.size:
                        raise DictionaryCorrupt("WikDict download exceeds its expected size.")
                    stream.write(chunk)
                    if progress:
                        progress(received, package.size)
                stream.flush()
                os.fsync(stream.fileno())
        validate_package(temporary, package)
        if check_cancelled:
            check_cancelled()
        # License is staged before publication; it also survives an interrupted update.
        (destination.parent / "WIKDICT-LICENSE.txt").write_text(
            ATTRIBUTION + f"\nVersion: {package.version}\nSource: {package.url}\n"
            f"SHA256: {package.sha256}\n",
            encoding="utf-8",
        )
        os.replace(temporary, destination)
        return destination
    except requests.RequestException as exc:
        raise CambridgeError(f"WikDict download failed: {exc}") from exc
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
        if own_session:
            session.close()


def clean_wiki(value: str) -> str:
    value = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", value)
    # Preserve the displayed term in common templates; omit metadata-only templates.
    value = re.sub(r"\{\{(?:l|m|t|t\+)\|[^|{}]+\|([^|{}]+)(?:\|[^{}]*)?\}\}", r"\1", value)
    value = re.sub(r"\{\{[^{}]*\}\}", "", value)
    value = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", value)
    value = value.replace("'''", "").replace("''", "")
    return " ".join(BeautifulSoup(unescape(value), "html.parser").get_text(" ").split())


def lookup(word: str, directory: Path | None = None, *, package: DictionaryPackage = PACKAGE):
    from .translations import TranslationOption

    path = package_path(directory, package)
    validate_package(path, package)
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            rows = connection.execute(
                "SELECT lexentry, sense, trans_list FROM translation WHERE written_rep = ? "
                "ORDER BY score DESC, lexentry, sense",
                (word,),
            ).fetchall()
    except sqlite3.Error as exc:
        raise DictionaryCorrupt(f"WikDict lookup failed: {exc}") from exc
    options = {}
    for lexentry, sense, text in rows:
        # Split only the dataset's ' | ' separator, not pipes inside [[target|label]].
        texts = tuple(
            dict.fromkeys(t for raw in re.split(r"\s+\|\s+", text or "") if (t := clean_wiki(raw)))
        )
        if not texts:
            continue
        gloss = clean_wiki(sense or "")
        pos = lexentry.split("__")[1].lower() if lexentry and "__" in lexentry else ""
        key = stable_id(lexentry or "", gloss, *texts)
        options[key] = TranslationOption(
            key, texts, gloss, pos, f"{package.url}#{lexentry or word}", False
        )
    return tuple(options.values())

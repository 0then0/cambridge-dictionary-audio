"""Sense- and language-scoped translations shared by all three application interfaces."""

from dataclasses import asdict, dataclass, replace

from .dictionary import AudioNotFoundError, CambridgeBlockedError, CambridgeError, stable_id
from .wikdict import PACKAGE, DictionaryCorrupt, DictionaryMissing, lookup


@dataclass(frozen=True)
class TranslationOption:
    id: str
    texts: tuple[str, ...]
    definition: str = ""
    part_of_speech: str = ""
    origin: str = ""
    matched: bool = False

    @property
    def label(self):
        return self.label_for("en")

    def label_for(self, language: str) -> str:
        from .i18n import translate

        context = " · ".join(
            filter(None, (translate(self.part_of_speech, language), self.definition))
        )
        return "; ".join(self.texts) + (" · " + context if context else "")


@dataclass(frozen=True)
class TranslationResult:
    language: str
    sense_id: str
    source: str
    options: tuple[TranslationOption, ...] = ()
    selected_id: str = ""
    status: str = "ok"
    error: str = ""
    version: str = ""

    @property
    def texts(self) -> tuple[str, ...]:
        selected = next((o for o in self.options if o.id == self.selected_id), None)
        if selected:
            return selected.texts
        return self.options[0].texts if len(self.options) == 1 else ()

    @property
    def display(self):
        return self.format("en")

    def format(self, language="en", *, show_ids=True):
        from .i18n import translate

        t = lambda text: translate(text, language)  # noqa: E731
        if not self.options:
            return (
                "; ".join(t(part) for part in self.error.split("; "))
                if self.error
                else t("No translation found.")
            )
        note = (
            ""
            if all(o.matched for o in self.options)
            else "\n" + t("Source senses; Cambridge match unverified.")
        )
        if self.texts:
            body = "; ".join(self.texts)
        elif show_ids:
            body = "\n".join(f"{o.id} · {o.label_for(language)}" for o in self.options)
        else:
            body = "\n\n".join(
                "• "
                + "; ".join(o.texts)
                + (" · " + t(o.part_of_speech) if o.part_of_speech else "")
                + ("\n  " + o.definition if o.definition else "")
                for o in self.options
            )
        return f"{t(self.source)}\n{body}{note}" + (
            "\n" + "; ".join(t(part) for part in self.error.split("; ")) if self.error else ""
        )

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        try:
            fields = ("language", "sense_id", "source")
            if not all(isinstance(data[k], str) for k in fields):
                return None
            options = []
            for item in data.get("options", []):
                if not isinstance(item, dict) or not isinstance(item.get("texts"), list):
                    return None
                if not all(isinstance(t, str) for t in item["texts"]):
                    return None
                if not all(
                    isinstance(item.get(k, ""), str)
                    for k in ("id", "definition", "part_of_speech", "origin")
                ):
                    return None
                options.append(
                    TranslationOption(
                        item["id"],
                        tuple(item["texts"]),
                        item.get("definition", ""),
                        item.get("part_of_speech", ""),
                        item.get("origin", ""),
                        item.get("matched") is True,
                    )
                )
            if not all(
                isinstance(data.get(k, ""), str)
                for k in ("selected_id", "status", "error", "version")
            ):
                return None
            return cls(
                *(data[k] for k in fields),
                tuple(options),
                data.get("selected_id", ""),
                data.get("status", "ok"),
                data.get("error", ""),
                data.get("version", ""),
            )
        except (KeyError, TypeError):
            return None


def cached_translation(saved, language: str) -> TranslationResult | None:
    candidates = [
        t
        for t in saved.translation_cache
        if t.language == language and t.sense_id == saved.recording.sense_id and t.options
    ]
    for source in ("User", "Cambridge", "WikDict"):
        match = next((t for t in reversed(candidates) if t.source == source), None)
        if match:
            return match
    return None


def resolve_translation(
    client, saved, language: str, *, directory=None, offline: bool = False, refresh: bool = False
) -> TranslationResult:
    language = language.strip().lower()
    cached = cached_translation(saved, language)
    if cached and (not refresh or cached.source == "User"):
        return cached
    record = saved.recording
    status, error = "absent", ""
    if not offline:
        try:
            options = client.translation_options(
                record.word, language, record.definition, record.part_of_speech
            )
            if options:
                return TranslationResult(language, record.sense_id, "Cambridge", options)
        except AudioNotFoundError:
            status = "absent"
        except CambridgeBlockedError as exc:
            status, error = "blocked", str(exc)
        except (CambridgeError, ValueError) as exc:
            status, error = "network_error", str(exc)
    if language == "russian":
        try:
            # lemma is only populated by the source, never guessed by stemming.
            options = lookup(record.lemma or record.word, directory)
            if options:
                return TranslationResult(
                    language,
                    record.sense_id,
                    "WikDict",
                    options,
                    status=status,
                    error=error,
                    version=PACKAGE.version,
                )
        except DictionaryMissing as exc:
            return TranslationResult(
                language,
                record.sense_id,
                "WikDict",
                status="dictionary_missing",
                error="; ".join(filter(None, (error, str(exc)))),
            )
        except (DictionaryCorrupt, OSError) as exc:
            return TranslationResult(
                language,
                record.sense_id,
                "WikDict",
                status="dictionary_corrupt",
                error="; ".join(filter(None, (error, str(exc)))),
            )
    return TranslationResult(
        language,
        record.sense_id,
        "WikDict" if offline else "Cambridge",
        status=status,
        error=error or "No translation found.",
    )


def persist_translation(saved, result: TranslationResult):
    # Read/merge under one lock: a late response must preserve a newer manual edit.
    from .library import _METADATA_LOCK, read_recording, save_metadata

    if saved is None:
        return None
    with _METADATA_LOCK:
        current = read_recording(saved.recording.reference)
        if current is None or current.recording.sense_id != result.sense_id:
            return current
        cache = tuple(
            t
            for t in current.translation_cache
            if (t.language, t.source, t.sense_id)
            != (result.language, result.source, result.sense_id)
        ) + (result,)
        save_metadata(current.recording, translation_cache=cache)
        return read_recording(current.recording.reference)


def edit_translation(saved, language: str, text: str | None):
    from .library import _METADATA_LOCK, read_recording, save_metadata, scan_recordings

    with _METADATA_LOCK:
        current = read_recording(saved.recording.reference)
        if current is None:
            raise FileNotFoundError(saved.recording.path)
        cache = tuple(
            t
            for t in current.translation_cache
            if not (
                t.language == language
                and t.source == "User"
                and t.sense_id == current.recording.sense_id
            )
        )
        if text is not None and text.strip():
            option = TranslationOption(
                stable_id(text), (text.strip(),), origin="User edit", matched=True
            )
            cache += (TranslationResult(language, current.recording.sense_id, "User", (option,)),)
        for related in scan_recordings(current.recording.path.parent):
            record = related.recording
            if (
                record.word != current.recording.word
                or record.meaning_key != current.recording.meaning_key
            ):
                continue
            own_cache = tuple(
                t
                for t in related.translation_cache
                if not (
                    t.language == language and t.source == "User" and t.sense_id == record.sense_id
                )
            )
            own_cache += tuple(
                replace(t, sense_id=record.sense_id)
                for t in cache
                if t.language == language
                and t.source == "User"
                and t.sense_id == current.recording.sense_id
            )
            save_metadata(record, translation_cache=own_cache)
        return read_recording(current.recording.reference)


def select_translation(saved, language: str, option_id: str):
    result = cached_translation(saved, language)
    if result is None or not any(o.id == option_id for o in result.options):
        raise ValueError("Unknown translation option ID.")
    return persist_translation(saved, replace(result, selected_id=option_id))

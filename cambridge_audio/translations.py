"""Sense- and language-scoped translations shared by all three application interfaces."""

import re
import unicodedata
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


# Ignore grammar words, retaining negation and descriptive qualifiers. No stemming
# or synonym guessing: uncertain paraphrases remain available for explicit choice.
_GLOSS_STOP = frozenset(
    "a an the to of in on at by for from with or and is are be been being "
    "that which where when who you your it its can as into etc".split()
)


def _gloss_words(text):
    text = unicodedata.normalize("NFKC", text).casefold().replace("’", "'")
    text = text.replace("cannot", "can not").replace("can't", "can not")
    text = text.replace("won't", "will not").replace("n't", " not")
    return re.findall(r"[^\W_]+", text)


def match_options(options, definition, part=""):
    """Resolve only exact or distinctive lexical matches; retain other candidates."""
    if not definition:
        return tuple(options)
    eligible = tuple(
        o
        for o in options
        if not part or not o.part_of_speech or o.part_of_speech.casefold() == part.casefold()
    )
    words = _gloss_words(definition)
    exact = tuple(o for o in eligible if _gloss_words(o.definition) == words)
    if exact:
        return tuple(replace(o, matched=True) for o in exact)
    # Overlap cannot establish the direction of an action (pay/receive,
    # give/take). Restrict paraphrase inference to known noun senses; other
    # parts of speech need the normalized exact match above or a human choice.
    if part.casefold() != "noun":
        return tuple(replace(o, matched=False) for o in eligible or options)
    anchors = [w for w in words if w not in _GLOSS_STOP]
    target = set(anchors)
    scores = []
    for option in eligible:
        tokens = [w for w in _gloss_words(option.definition) if w not in _GLOSS_STOP]
        other = set(tokens)
        overlap = target & other
        # A shared two-word phrase and three content words prevent a generic
        # word such as money/river from linking otherwise unrelated meanings.
        phrases = set(zip(anchors, anchors[1:], strict=False)) & set(
            zip(tokens, tokens[1:], strict=False)
        )
        negatives = {"not", "no", "never", "without", "only", "except", "excluding"}
        score = len(overlap) / max(1, min(len(target), len(other)))
        if len(overlap) < 3 or not phrases or target & negatives != other & negatives:
            score = 0
        scores.append((score, option))
    scores.sort(key=lambda pair: pair[0], reverse=True)
    if scores and scores[0][0] >= 0.6:
        best = scores[0][0]
        winners = [o for score, o in scores if score == best]
        # Multiple glosses with identical translations are harmless; different
        # translations at the same score or a close runner-up need human input.
        next_score = max((score for score, _ in scores if score < best), default=0)
        if len({o.texts for o in winners}) == 1 and best - next_score >= 0.2:
            return tuple(replace(o, matched=True) for o in winners)
    return tuple(replace(o, matched=False) for o in eligible or options)


def align_translation(result, definition, part=""):
    if (
        result.source == "User"
        or result.selected_id
        or not definition
        or not result.options
        # Preserve legacy flat translations and adapters with no sense metadata.
        or not any(o.definition or o.part_of_speech or o.origin for o in result.options)
    ):
        return result
    options = match_options(result.options, definition, part)
    matched = any(o.matched for o in options)
    return replace(result, options=options, alignment="matched" if matched else "unmatched")


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
    alignment: str = ""

    @property
    def texts(self) -> tuple[str, ...]:
        selected = next((o for o in self.options if o.id == self.selected_id), None)
        if selected:
            return selected.texts
        matched = tuple(o for o in self.options if o.matched)
        if matched:
            return tuple(dict.fromkeys(text for o in matched for text in o.texts))
        if self.alignment == "unmatched":
            return ()
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
        if not self.texts and not show_ids:
            message = t("No automatic translation match for this meaning.")
            return message + ("\n" + self.error if self.error else "")
        note = (
            ""
            if self.selected_id or all(o.matched for o in self.options)
            else "\n" + t("Source senses; Cambridge match unverified.")
        )
        if self.texts:
            body = "; ".join(self.texts)
        else:
            body = "\n".join(f"{o.id} · {o.label_for(language)}" for o in self.options)
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
                for k in ("selected_id", "status", "error", "version", "alignment")
            ):
                return None
            return cls(
                *(data[k] for k in fields),
                tuple(options),
                data.get("selected_id", ""),
                data.get("status", "ok"),
                data.get("error", ""),
                data.get("version", ""),
                data.get("alignment", ""),
            )
        except (KeyError, TypeError):
            return None


def cached_translation(saved, language: str) -> TranslationResult | None:
    source_priority = {"User": 3, "Cambridge": 2, "WikDict": 1}
    candidates = []
    # Recency breaks ties between explicit choices, regardless of the source.
    for result in reversed(saved.translation_cache):
        if (
            result.language != language
            or result.sense_id != saved.recording.sense_id
            or not result.options
            or result.source not in source_priority
        ):
            continue
        if any(o.definition for o in result.options):
            result = align_translation(
                result, saved.recording.definition, saved.recording.part_of_speech
            )
        candidates.append(result)

    def priority(result):
        explicit = any(o.id == result.selected_id for o in result.options)
        tier = 3 if result.source == "User" else 2 if explicit else 1 if result.texts else 0
        return tier, 0 if explicit else source_priority[result.source]

    return max(candidates, key=priority, default=None)


def resolve_translation(
    client, saved, language: str, *, directory=None, offline: bool = False, refresh: bool = False
) -> TranslationResult:
    language = language.strip().lower()
    cached = cached_translation(saved, language)
    if cached and (
        cached.source == "User" or (not refresh and (cached.texts or cached.source == "WikDict"))
    ):
        return cached
    record = saved.recording
    status, error = "absent", ""
    unmatched = cached if cached and not refresh else None
    # An unresolved cache is reusable as candidates, not a completed lookup.
    # Try the installed dictionary without repeating a Cambridge request.
    if not offline and (cached is None or refresh):
        try:
            options = client.translation_options(
                record.word, language, record.definition, record.part_of_speech
            )
            if options:
                unmatched = align_translation(
                    TranslationResult(language, record.sense_id, "Cambridge", options),
                    record.definition,
                    record.part_of_speech,
                )
                if unmatched.texts:
                    return unmatched
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
                local = align_translation(
                    TranslationResult(
                        language,
                        record.sense_id,
                        "WikDict",
                        options,
                        status=status,
                        error=error,
                        version=PACKAGE.version,
                    ),
                    record.definition,
                    record.part_of_speech,
                )
                return local if local.texts or unmatched is None else unmatched
        except DictionaryMissing as exc:
            if unmatched is not None:
                return unmatched
            return TranslationResult(
                language,
                record.sense_id,
                "WikDict",
                status="dictionary_missing",
                error="; ".join(filter(None, (error, str(exc)))),
            )
        except (DictionaryCorrupt, OSError) as exc:
            if unmatched is not None:
                return unmatched
            return TranslationResult(
                language,
                record.sense_id,
                "WikDict",
                status="dictionary_corrupt",
                error="; ".join(filter(None, (error, str(exc)))),
            )
    if unmatched is not None:
        return unmatched
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
        if result.source == "User":
            # A resolver can return a snapshot of a personal cache. Only the
            # dedicated edit operation may replace an existing personal value.
            result = next(
                (
                    t
                    for t in current.translation_cache
                    if (t.language, t.source, t.sense_id)
                    == (result.language, result.source, result.sense_id)
                ),
                result,
            )
        if not result.selected_id:
            explicit = next(
                (
                    t
                    for t in current.translation_cache
                    if (t.language, t.source, t.sense_id)
                    == (result.language, result.source, result.sense_id)
                    and t.selected_id
                ),
                None,
            )
            if explicit:
                result = explicit
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
        # A read-time upgrade may have narrowed an old cache. Explicit CLI/source
        # choices can still refer to its retained original options.
        result = next(
            (
                t
                for t in reversed(saved.translation_cache)
                if t.language == language
                and t.sense_id == saved.recording.sense_id
                and any(o.id == option_id for o in t.options)
            ),
            None,
        )
        if result is None:
            raise ValueError("Unknown translation option ID.")
    from .library import _METADATA_LOCK, scan_recordings

    with _METADATA_LOCK:
        for related in scan_recordings(saved.recording.path.parent):
            if (
                related.recording.word == saved.recording.word
                and related.recording.meaning_key == saved.recording.meaning_key
            ):
                persist_translation(
                    related,
                    replace(result, sense_id=related.recording.sense_id, selected_id=option_id),
                )
        from .library import read_recording

        return read_recording(saved.recording.reference)

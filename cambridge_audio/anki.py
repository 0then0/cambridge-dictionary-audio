"""Transactional Anki text export. Never downloads or modifies source recordings."""

import csv
import html
import os
import shutil
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from .dictionary import is_mp3
from .translations import cached_translation
from .wikdict import ATTRIBUTION

COLUMNS = (
    "ID",
    "Word",
    "PartOfSpeech",
    "Definition",
    "Translation",
    "IPA",
    "Accent",
    "Audio",
    "Source",
)
FILES = {"collection.tsv", "media", "IMPORT.txt", "SOURCES.txt"}
INSTRUCTIONS = """Anki TSV import (UTF-8)
1. Create a note type with fields in this order:
   ID, Word, PartOfSpeech, Definition, Translation, IPA, Accent, Audio, Source.
   ID must be the FIRST field. Use Word and Audio in your card templates.
2. Copy every MP3 from media/ directly into your Anki profile's collection.media.
   Do not copy the media directory itself; Anki requires a flat media directory.
3. Import collection.tsv, separator Tab, Allow HTML in fields enabled.
   Anki 2.1.54+ reads the headers. On older versions ignore the three # header lines.
   Map all nine columns to the corresponding note fields, including ID to ID.
4. For repeat imports choose update existing notes and match by note type / first field.
   Do not map our ID to Anki's internal GUID. Keep the same note type and ID field.
   Every pronunciation/sense has its own ID, including US/UK variants.
5. Text is HTML-escaped; line breaks use <br>. Audio uses [sound:filename.mp3].
   A blank Translation means no translation was selected for the requested language.
Sources and data licenses are recorded in SOURCES.txt and the Source field.
Reference: https://docs.ankiweb.net/manual/importing/text-files
"""


def field(value: str) -> str:
    return (
        html.escape(value, quote=True)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "<br>")
    )


def export_anki(records, destination: Path, *, language: str = "russian") -> Path:
    records = list(records)
    if not records:
        raise ValueError("No recordings selected for export.")
    destination = Path(destination).absolute()
    if destination.is_symlink():
        raise ValueError("Export destination must not be a symbolic link.")
    if destination.exists() and (
        not destination.is_dir()
        or set(p.name for p in destination.iterdir()) != FILES
        or not (destination / "IMPORT.txt")
        .read_text(encoding="utf-8")
        .startswith("Anki TSV import (UTF-8)")
    ):
        raise FileExistsError("Choose a new folder or an existing Cambridge Anki export folder.")
    if destination.exists():
        with (destination / "collection.tsv").open(encoding="utf-8", newline="") as stream:
            lines = (line for line in stream if not line.startswith("#"))
            expected = set()
            for row in csv.reader(lines, delimiter="\t"):
                if (
                    len(row) != len(COLUMNS)
                    or not row[7].startswith("[sound:")
                    or not row[7].endswith("]")
                ):
                    raise ValueError("Existing export TSV is damaged; choose a new export folder.")
                expected.add(row[7][7:-1])
        media_dir = destination / "media"
        if (
            media_dir.is_symlink()
            or not media_dir.is_dir()
            or any(p.name not in expected or not p.is_file() for p in media_dir.iterdir())
        ):
            raise FileExistsError(
                "Export media folder contains unrelated files; choose a new folder."
            )
    seen, prepared, problems = set(), [], []
    for saved in records:
        record = saved.recording
        path = record.path
        if path.resolve().is_relative_to(destination.resolve()):
            problems.append(f"Export destination contains the source recording: {path}")
            continue
        try:
            with path.open("rb") as stream:
                if not is_mp3(stream.read(16)):
                    raise ValueError("invalid MP3 signature")
        except (OSError, ValueError) as exc:
            problems.append(f"Cannot export {path}: {exc}")
            continue
        translation = cached_translation(saved, language)
        if translation and translation.options and not translation.texts:
            problems.append(
                f"Choose a translation sense before exporting {path.name} ({language})."
            )
            continue
        if record.id in seen:
            continue
        seen.add(record.id)
        media = f"cambridge-{record.id}.mp3"
        source = record.source_url or "https://dictionary.cambridge.org/"
        if translation:
            origins = "; ".join(
                o.origin
                for o in translation.options
                if not translation.selected_id or o.id == translation.selected_id
            )
            source += f"; translation: {translation.source} ({language}); {origins}"
            if translation.source == "WikDict":
                source += f"; {translation.version}; CC BY-SA 4.0"
        prepared.append(
            (
                path,
                media,
                [
                    record.id,
                    record.word,
                    record.part_of_speech,
                    record.definition,
                    "; ".join(translation.texts) if translation else "",
                    record.ipa,
                    record.accent.upper(),
                    f"[sound:{media}]",
                    source,
                ],
            )
        )
    if problems:
        raise ValueError("Export failed:\n" + "\n".join(problems))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".cambridge-anki-", dir=destination.parent) as temporary:
        staging = Path(temporary) / "export"
        staging.mkdir()
        (staging / "media").mkdir()
        with (staging / "collection.tsv").open("w", encoding="utf-8", newline="") as stream:
            stream.write("#separator:Tab\n#html:true\n#columns:" + "\t".join(COLUMNS) + "\n")
            writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
            for path, media, row in prepared:
                shutil.copyfile(path, staging / "media" / media)
                writer.writerow([field(value) for value in row])
        (staging / "IMPORT.txt").write_text(INSTRUCTIONS, encoding="utf-8")
        (staging / "SOURCES.txt").write_text(
            "Audio, definitions, IPA: Cambridge Dictionary, https://dictionary.cambridge.org/.\n"
            "Cambridge content retains its owners' rights; "
            "no Apache-2.0 license is granted to it.\n"
            + ATTRIBUTION
            + "\nUser translations are identified as User.\n"
            "WikDict notices apply to included WikDict translations only.\n\n"
            + "\n".join(row[-1] for _, _, row in prepared)
            + "\n",
            encoding="utf-8",
        )
        backup = Path(temporary) / "previous"
        had_previous = destination.exists()
        if had_previous:
            os.replace(destination, backup)
        try:
            os.replace(staging, destination)
        except BaseException:
            if had_previous:
                os.replace(backup, destination)
            raise
    return destination / "collection.tsv"


# These identities and field/template ordinals are part of the export contract.
MODEL_ID = 1635286301
DECK_ID = 1635286302
MODEL_NAME = "Cambridge Dictionary Audio"
SOURCES = (
    "Audio, definitions and IPA: Cambridge Dictionary, https://dictionary.cambridge.org/. "
    "Cambridge content retains its owners' rights; the application's Apache-2.0 license "
    "does not apply to dictionary content.\n" + ATTRIBUTION + "\n"
    "WikDict license notices apply only to included WikDict translations. "
    "Personal translations are identified as User.\n"
)
CARD_CSS = """
.card { font-family: Arial, sans-serif; font-size: 22px; text-align: left;
        color: #202124; background: #ffffff; line-height: 1.5; padding: 20px; }
.word { font-size: 32px; font-weight: bold; }
.context, .source { font-size: 15px; overflow-wrap: anywhere; }
.source { margin-top: 24px; color: #53565a; }
.nightMode.card, .night_mode.card { color: #f1f3f4; background: #202124; }
.nightMode .source, .night_mode .source { color: #bdc1c6; }
"""
MAPPING_FILE = ".anki-mapping.json"


def _model():
    import genanki

    class CambridgeModel(genanki.Model):
        def to_json(self, timestamp, deck_id):
            model = super().to_json(timestamp, deck_id)
            # Content exports must not replace a user's later template styling edits.
            model["mod"] = 1635286301
            return model

    return CambridgeModel(
        MODEL_ID,
        MODEL_NAME,
        fields=[{"name": name, "id": 1635286400 + i} for i, name in enumerate(COLUMNS)],
        templates=[
            {
                "name": "Word → meaning",
                "id": 1635286500,
                "qfmt": '<div class="word">{{Word}}</div>',
                "afmt": '{{FrontSide}}<hr id="answer"><div>{{Translation}}</div>'
                '<div class="context">{{PartOfSpeech}}</div><div>{{Definition}}</div>'
                "<div>{{IPA}} · {{Accent}}</div>{{Audio}}"
                '<div class="source">{{Source}}</div>',
            }
        ],
        css=CARD_CSS,
        sort_field_index=1,
    )


def _atomic_json(destination, data):
    import json
    from tempfile import NamedTemporaryFile

    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent, suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def _read_mapping(directory):
    import json

    path = directory / MAPPING_FILE
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or data.get("version") != 1
        or not isinstance(data.get("notes"), dict)
    ):
        raise ValueError(f"Invalid Anki identity mapping: {path}")
    return data["notes"]


def adopt_anki_identities(records, reference: Path, directory: Path) -> int:
    """Read an explicitly exported legacy APKG, never the user's live Anki database.

    Preserve both original GUID and note type; no field/GUID guessing or note deletion.
    Only Anki's uncompressed legacy package format is accepted.
    """
    import json
    import sqlite3
    from zipfile import ZipFile, is_zipfile

    if not is_zipfile(reference):
        raise ValueError("The reference is not a readable Anki .apkg export.")
    records = list(records)
    directory = Path(directory).resolve()
    if any(s.recording.reference.parent.resolve() != directory for s in records):
        raise ValueError(
            "Use --output-dir for the collection folder containing the selected entries."
        )
    selected = {s.recording.id for s in records}
    matches = {}
    with (
        TemporaryDirectory(prefix="cambridge-anki-reference-") as temp,
        ZipFile(reference) as archive,
    ):
        names = archive.namelist()
        if "collection.anki21b" in names:
            raise ValueError("Export from Anki with 'Support older Anki versions' enabled.")
        # Modern legacy exports put the real v11 database in .anki21, while
        # .anki2 can be a dummy upgrade notice for very old clients.
        member = "collection.anki21" if "collection.anki21" in names else "collection.anki2"
        if member not in names:
            raise ValueError("The reference contains no supported Anki collection.")
        database = Path(temp) / "reference.anki2"
        database.write_bytes(archive.read(member))
        try:
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
                models = json.loads(connection.execute("SELECT models FROM col").fetchone()[0])
                for guid, mid, values in connection.execute("SELECT guid, mid, flds FROM notes"):
                    columns = values.split("\x1f")
                    local_id = html.unescape(columns[0])
                    if local_id not in selected:
                        continue
                    model = models.get(str(mid), {})
                    if (
                        [f["name"] for f in model.get("flds", [])] != list(COLUMNS)
                        or len(model.get("tmpls", [])) != 1
                        or model.get("type") != 0
                    ):
                        raise ValueError(
                            "TSV transition requires the original nine fields "
                            "and one card template."
                        )
                    if local_id in matches:
                        raise ValueError(f"Ambiguous Anki ID in reference package: {local_id}")
                    matches[local_id] = {"guid": guid, "model": model}
        except (sqlite3.Error, KeyError, TypeError, IndexError) as exc:
            raise ValueError("Unreadable Anki reference package.") from exc
    if not matches:
        raise ValueError("No TSV IDs match the selected collection. No mapping was written.")
    previous = _read_mapping(directory)
    for identity, mapped in matches.items():
        if identity in previous and previous[identity] != mapped:
            raise ValueError(
                "An Anki identity is already mapped differently; previous mapping retained."
            )
    previous_state = {}
    if (directory / MAPPING_FILE).exists():
        previous_state = json.loads((directory / MAPPING_FILE).read_text(encoding="utf-8"))
    _atomic_json(
        directory / MAPPING_FILE, previous_state | {"version": 1, "notes": previous | matches}
    )
    return len(matches)


def export_apkg(records, destination: Path, *, language: str = "russian") -> Path:
    """Publish a complete package atomically, with stable note identity and hashed media."""
    import hashlib
    import json
    from time import time
    from zipfile import BadZipFile, ZipFile

    import genanki

    records = list(records)
    if not records:
        raise ValueError("No recordings selected for export.")
    destination = Path(destination).absolute()
    if destination.suffix.lower() != ".apkg":
        raise ValueError("Choose an .apkg file.")
    if destination.is_symlink():
        raise ValueError("Export destination must not be a symbolic link.")
    if destination.exists():
        try:
            with ZipFile(destination) as archive:
                marker = json.loads(archive.read("cambridge-export.json"))
                if marker != {"application": "cambridge-dictionary-audio", "version": 1}:
                    raise ValueError("Unrecognized export marker.")
        except (OSError, BadZipFile, KeyError, ValueError) as exc:
            raise FileExistsError(
                "Choose a new file or an existing Cambridge .apkg export."
            ) from exc
    # Anki compares modification times in whole seconds. Reserve a monotonic
    # timestamp per collection even for rapid exports to different destinations.
    from .library import _METADATA_LOCK

    with _METADATA_LOCK:
        directories = {s.recording.reference.parent for s in records}
        states = {}
        timestamp = int(time())
        for directory in directories:
            _read_mapping(directory)
            state_path = directory / MAPPING_FILE
            state = (
                json.loads(state_path.read_text(encoding="utf-8"))
                if state_path.exists()
                else {"version": 1, "notes": {}}
            )
            previous_time = state.get("last_export", 0)
            if not isinstance(previous_time, int):
                raise ValueError(f"Invalid export timestamp: {state_path}")
            timestamp = max(timestamp, previous_time + 1)
            states[directory] = state
        for directory, state in states.items():
            _atomic_json(directory / MAPPING_FILE, state | {"last_export": timestamp})
    model = _model()
    deck = genanki.Deck(DECK_ID, MODEL_NAME, description=field(SOURCES))
    seen, mappings = set(), {}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".cambridge-apkg-", dir=destination.parent) as temporary:
        staging = Path(temporary)
        media = {}
        sources = []
        for saved in records:
            record = saved.recording
            if record.id in seen:
                raise ValueError("Duplicate collection ID; select each record only once.")
            seen.add(record.id)
            from .library import valid_audio

            if not valid_audio(record):
                raise ValueError(f"Cannot export missing or damaged MP3: {record.path}")
            content = record.path.read_bytes()
            name = "cambridge-audio-" + hashlib.sha256(content).hexdigest() + ".mp3"
            if name not in media:
                path = staging / name
                path.write_bytes(content)
                media[name] = str(path)
            translation = cached_translation(saved, language)
            if translation and translation.options and not translation.texts:
                raise ValueError(f"Choose a translation sense before exporting {record.word}.")
            source = record.source_url or "https://dictionary.cambridge.org/"
            source += "; audio: " + record.audio_url + "; " + SOURCES
            if translation:
                source += (
                    f"\nTranslation: {translation.source} ({language}); {translation.version}; "
                )
                source += "; ".join(
                    o.origin
                    for o in translation.options
                    if not translation.selected_id or o.id == translation.selected_id
                )
            values = [
                record.id,
                record.word,
                record.part_of_speech,
                record.definition,
                "; ".join(translation.texts) if translation else "",
                record.ipa,
                record.accent.upper(),
                f"[sound:{name}]",
                source,
            ]
            sources.append(source)
            directory = record.reference.parent
            if directory not in mappings:
                mappings[directory] = _read_mapping(directory)
            identity = mappings[directory].get(record.id)
            note_model = model
            guid = genanki.guid_for("cambridge-dictionary-audio", record.id)
            if identity:
                # Keep the exported legacy model exactly, including its modification time.
                class LegacyModel(genanki.Model):
                    def to_json(self, timestamp, deck_id):
                        return self.original

                original = identity["model"]
                note_model = LegacyModel(
                    int(original["id"]),
                    original["name"],
                    fields=original["flds"],
                    templates=original["tmpls"],
                )
                note_model.original = original
                guid = identity["guid"]
            deck.add_note(
                genanki.Note(model=note_model, fields=[field(v) for v in values], guid=guid)
            )
        output = staging / "collection.apkg"
        genanki.Package(deck, media_files=list(media.values())).write_to_file(
            str(output), timestamp=timestamp
        )
        with ZipFile(output, "a") as archive:
            archive.writestr("SOURCES.txt", SOURCES + "\n" + "\n".join(sources))
            archive.writestr(
                "cambridge-export.json",
                json.dumps({"application": "cambridge-dictionary-audio", "version": 1}),
            )
        os.replace(output, destination)
    return destination

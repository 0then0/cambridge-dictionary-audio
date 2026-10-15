"""Transactional Anki text export. Never downloads or modifies source recordings."""

import csv
import html
import os
import shutil
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

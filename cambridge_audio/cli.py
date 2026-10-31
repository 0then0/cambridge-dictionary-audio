"""Command-line and interactive Cambridge Dictionary audio downloader."""

import argparse
import math
import re
import sys
import unicodedata
from importlib.metadata import version
from pathlib import Path

from .anki import adopt_anki_identities, export_anki, export_apkg
from .audio import play_audio
from .bundle import BundleExistsError, apply_import, export_bundle, preview_import
from .console import Output, is_terminal
from .dictionary import (
    CambridgeClient,
    CambridgeError,
    SelectionRequired,
    variants,
)
from .i18n import LANGUAGES, language_code, translate
from .library import delete_recording, read_recording, save_metadata, scan_recordings
from .service import Recording, download_recordings, preview_recording
from .translations import (
    cached_translation,
    edit_translation,
    persist_translation,
    resolve_translation,
    select_translation,
)
from .wikdict import PACKAGE, install_dictionary


def _cells(character: str) -> int:
    return 2 if unicodedata.east_asian_width(character) in "WF" else 1


def wrap_by_width(text: str, width: int) -> list[str]:
    """Wrap by terminal cells; textwrap cannot break CJK text and counts wide glyphs as one."""
    width = max(width - 2, 10)  # room for hanging punctuation
    lines, line, used = [], "", 0
    # A token is a run of narrow non-space characters, one wide character or one space.
    for token in re.findall(r"[^\s\u2e80-\uffff]+|[\u2e80-\uffff]|\s", text):
        size = sum(map(_cells, token))
        # Closing punctuation may hang past the margin instead of starting a line.
        if used + size > width and line.strip() and token not in "。、，．）」』】！？：；)":
            lines.append(line.rstrip())
            line, used = "", 0
            if token.isspace():
                continue
        line += token
        used += size
    return lines + [line.rstrip()] if line.strip() else lines


class HelpFormatter(argparse.HelpFormatter):
    def __init__(self, prog: str, language: str):
        super().__init__(prog)
        self.language = language

    def _split_lines(self, text, width):
        if self.language != "ja":
            return super()._split_lines(text, width)
        return wrap_by_width(" ".join(text.split()), width)

    def _fill_text(self, text, width, indent):
        if self.language != "ja":
            return super()._fill_text(text, width, indent)
        return "\n".join(indent + line for line in wrap_by_width(" ".join(text.split()), width))

    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, prefix or translate("usage: ", self.language))


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, language: str, **kwargs):
        self.language = language
        super().__init__(
            formatter_class=lambda prog: HelpFormatter(prog, language),
            add_help=False,
            allow_abbrev=False,
            **kwargs,
        )

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(
            2, translate("{prog}: error: {error}\n", self.language, prog=self.prog, error=message)
        )


def interface_language(value: str) -> str:
    """Accept any letter case; unknown values are rejected by argparse's choices."""
    try:
        return language_code(value)
    except ValueError:
        return value


def positive_timeout(value: str, language: str = "en") -> float:
    try:
        timeout = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            translate("Timeout must be a positive finite number.", language)
        ) from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError(
            translate("Timeout must be a positive finite number.", language)
        )
    return timeout


def russian_translation(value: str, language: str = "en") -> str | None:
    value = value.strip().casefold()
    if not value:
        return None
    if value in {"russian", "ru", "русский"}:
        return "russian"
    raise argparse.ArgumentTypeError(
        translate("Only Russian translation is supported. Use russian or ru.", language)
    )


def download_word(client: CambridgeClient, word: str, args, downloaded: set[Path]) -> None:
    output = Output(args.lang, plain=args.plain)
    known_ids = {s.recording.id for s in scan_recordings(args.output_dir)}

    def saved(recording: Recording) -> None:
        if recording.id not in known_ids:
            downloaded.add(recording.reference)
        if recording.combined:
            output.message(
                translate(
                    "{accent}: combined from individual word recordings",
                    args.lang,
                    accent=recording.accent.upper(),
                )
            )
        else:
            output.message(f"{recording.accent.upper()}: /{recording.ipa}/", style="bold cyan")
        output.message(translate("Saved: {path}", args.lang, path=recording.path), style="dim")
        store_details(recording)
        if args.play:
            try:
                play_audio(recording.path, args.lang)
            except (CambridgeError, OSError) as exc:
                print(translate("Playback: {error}", args.lang, error=exc), file=sys.stderr)

    def store_details(recording, translations=()):
        try:
            save_metadata(recording, translations, args.translation)
        except OSError as exc:
            print(
                translate("Audio saved. Details could not be saved: {error}", args.lang, error=exc),
                file=sys.stderr,
            )

    def perform(variant_id=args.variant, entries=None):
        target = read_recording(args.update_recording) if args.update_recording else None
        if args.update_recording and target is None:
            raise ValueError(f"Missing or ambiguous collection entry: {args.update_recording}")
        return download_recordings(
            client,
            word,
            args.output_dir,
            args.accent,
            overwrite=args.overwrite,
            combine=args.combine,
            translation=args.translation,
            on_recording=saved,
            variant_id=variant_id,
            entries=entries,
            dictionary_dir=args.dictionary_dir,
            offline_translation=args.offline,
            sense_id=args.sense,
            audio_id=args.audio,
            target=target.recording if target else None,
        )

    try:
        with output.working():
            result = perform()
    except SelectionRequired as exc:
        if args.word:
            raise
        print(translate("Choose a meaning and its audio:", args.lang))
        for index, choice in enumerate(exc.choices, 1):
            print(f"{index}. {choice.label}")
        selected = input(translate("Meaning number (empty cancels): ", args.lang)).strip()
        if not selected:
            return
        if not selected.isdecimal() or not 1 <= int(selected) <= len(exc.choices):
            raise ValueError(translate("Choose a number from the list.", args.lang)) from None
        with output.working():
            result = perform(exc.choices[int(selected) - 1].id, exc.entries)
    for i, recording in enumerate(result.recordings):
        store_details(recording, () if result.translation_results else result.translations)
        if result.translation_results:
            persist_translation(read_recording(recording.reference), result.translation_results[i])
            output.message(result.translation_results[i].format(args.lang))
    output.details(result.recordings[0].word, result.recordings[0].definition, result.translations)
    if result.translation_error:
        print(
            translate("Translation: {error}", args.lang, error=result.translation_error),
            file=sys.stderr,
        )


def interactive(client: CambridgeClient, args) -> int:
    downloaded: set[Path] = set()
    print(
        translate(
            "Enter a word or phrase. /m: playback, /r: delete this session's files, /q: quit.",
            args.lang,
        )
    )
    while True:
        try:
            word = input("> ").strip()
            if not word:
                continue
            if word == "/q":
                return 0
            if word == "/m":
                args.play = not args.play
                print(
                    translate("Playback enabled." if args.play else "Playback disabled.", args.lang)
                )
                continue
            if word == "/r":
                for path in tuple(downloaded):
                    record = read_recording(path)
                    if record:
                        delete_recording(record.recording)
                    downloaded.remove(path)
                print(translate("Files downloaded in this session have been deleted.", args.lang))
                continue
            download_word(client, word, args, downloaded)
        except (CambridgeError, OSError, ValueError) as exc:
            print(translate("Error: {error}", args.lang, error=exc), file=sys.stderr)
        except (EOFError, KeyboardInterrupt):
            print()
            return 0


def main(argv: list[str] | None = None) -> int:
    if sys.platform == "win32":
        # Preserve IPA and Russian text when Windows output is redirected as well.
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")
    language_parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    language_parser.add_argument(
        "--lang", type=interface_language, choices=tuple(LANGUAGES), default="en"
    )
    language = language_parser.parse_known_args(argv)[0].lang
    parser = ArgumentParser(
        language,
        description=translate(
            "Download US or UK pronunciation audio from Cambridge Dictionary.", language
        ),
    )
    arguments = parser.add_argument_group(translate("Arguments", language))
    options = parser.add_argument_group(translate("Options", language))
    arguments.add_argument(
        "word",
        nargs="*",
        help=translate("Word or phrase; omit to start interactive mode.", language),
    )
    options.add_argument(
        "-h", "--help", action="help", help=translate("Show this help message and exit.", language)
    )
    options.add_argument(
        "--version",
        action="version",
        version=version("cambridge-dictionary-audio"),
        help=translate("Show version and exit.", language),
    )
    modes = options.add_mutually_exclusive_group()
    modes.add_argument(
        "--plain",
        action="store_true",
        help=translate("Use plain output and the line-based interactive prompt.", language),
    )
    modes.add_argument(
        "--tui",
        action="store_true",
        help=translate("Open the terminal workspace (requires an interactive terminal).", language),
    )
    options.add_argument(
        "--lang",
        type=interface_language,
        choices=tuple(LANGUAGES),
        default=language,
        help=translate(
            "Interface language (default: en); does not change dictionary translations.", language
        ),
    )
    options.add_argument(
        "--accent",
        choices=("us", "uk", "both"),
        default="us",
        help=translate("Pronunciation accent (default: us).", language),
    )
    options.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd() / "downloads",
        help=translate(
            "Destination directory (default: downloads/ in the current directory).", language
        ),
    )
    options.add_argument(
        "--timeout",
        type=lambda value: positive_timeout(value, language),
        default=15.0,
        help=translate("HTTP timeout in seconds (default: 15).", language),
    )
    options.add_argument(
        "--play",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=translate("Play downloaded audio (enabled by default in interactive mode).", language),
    )
    options.add_argument(
        "--overwrite", action="store_true", help=translate("Replace existing MP3 files.", language)
    )
    options.add_argument(
        "--combine",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=translate(
            "Combine missing phrases (enabled by default in interactive mode).", language
        ),
    )
    options.add_argument(
        "--translation",
        type=lambda value: russian_translation(value, language),
        metavar="russian",
        help=translate(
            "Show Russian translations (russian, ru or русский); disabled by default.", language
        ),
    )
    options.add_argument(
        "--list-variants",
        action="store_true",
        help=translate("List meaning/audio IDs without downloading.", language),
    )
    options.add_argument(
        "--variant", help=translate("Save the listed meaning/audio ID (legacy option).", language)
    )
    options.add_argument(
        "--sense", help=translate("Select the meaning ID from --list-variants.", language)
    )
    options.add_argument(
        "--audio", help=translate("Select the audio ID from --list-variants.", language)
    )
    options.add_argument(
        "--update-recording",
        type=Path,
        help=translate(
            "Reassociate this saved entry with the explicitly selected meaning/audio.", language
        ),
    )
    options.add_argument(
        "--preview",
        action="store_true",
        help=translate("Listen without saving to the collection.", language),
    )
    options.add_argument(
        "--export-format",
        choices=("apkg", "tsv"),
        default="apkg",
        help=translate("Anki export format (default: apkg).", language),
    )
    options.add_argument(
        "--anki-reference",
        type=Path,
        help=translate(
            "Adopt TSV GUIDs from an Anki export made with older-version support.", language
        ),
    )
    options.add_argument(
        "--dictionary-info",
        action="store_true",
        help=translate("Show the verified WikDict package, size and license.", language),
    )
    options.add_argument(
        "--install-dictionary",
        action="store_true",
        help=translate("Install the displayed WikDict en → ru package.", language),
    )
    options.add_argument(
        "--dictionary-dir", type=Path, help=translate("Local WikDict package directory.", language)
    )
    options.add_argument(
        "--export-anki",
        type=Path,
        help=translate(
            "Export the collection to an Anki .apkg file (default) or TSV folder.", language
        ),
    )
    options.add_argument(
        "--recording",
        action="append",
        type=Path,
        help=translate("Select a collection JSON or an unambiguous MP3; repeatable.", language),
    )
    options.add_argument(
        "--translate-saved",
        action="store_true",
        help=translate("Translate selected saved recordings without downloading audio.", language),
    )
    options.add_argument(
        "--offline",
        action="store_true",
        help=translate("Use only cached translations and installed WikDict.", language),
    )
    editing = options.add_mutually_exclusive_group()
    editing.add_argument(
        "--set-translation",
        help=translate("Set a personal translation for the selected sense and language.", language),
    )
    editing.add_argument(
        "--reset-translation",
        action="store_true",
        help=translate(
            "Remove the personal translation for the selected sense and language.", language
        ),
    )
    editing.add_argument(
        "--choose-translation",
        help=translate("Select a source sense by its displayed translation ID.", language),
    )
    transfers = options.add_mutually_exclusive_group()
    transfers.add_argument(
        "--export-collection",
        type=Path,
        help=translate("Export a checksummed collection bundle.", language),
    )
    transfers.add_argument(
        "--import-collection",
        type=Path,
        help=translate("Preview a collection bundle import.", language),
    )
    options.add_argument(
        "--replace-bundle",
        action="store_true",
        help=translate(
            "Allow --export-collection to replace an existing file (kept until the new "
            "bundle is complete).",
            language,
        ),
    )
    options.add_argument(
        "--apply-import",
        action="store_true",
        help=translate("Apply the displayed collection import.", language),
    )
    options.add_argument(
        "--resolve-conflict",
        action="append",
        default=[],
        metavar="ID=CHOICE",
        help=translate("Resolve an import conflict: existing or incoming.", language),
    )
    args = parser.parse_args(argv)
    if (
        args.list_variants or args.variant or args.sense or args.audio or args.preview
    ) and not args.word:
        parser.error("--list-variants and --variant require a word argument.")
    if args.replace_bundle and not args.export_collection:
        parser.error("--replace-bundle requires --export-collection.")
    if args.apply_import or args.resolve_conflict:
        if not args.import_collection:
            parser.error("--apply-import / --resolve-conflict require --import-collection.")
    if args.export_collection or args.import_collection:
        if args.word or args.recording or args.export_anki or args.anki_reference:
            parser.error("Collection transfer uses --output-dir and no word/recording/Anki action.")
        try:
            if args.export_collection:
                print(
                    export_bundle(
                        args.output_dir, args.export_collection, replace=args.replace_bundle
                    )
                )
            else:
                import json

                preview = preview_import(args.import_collection, args.output_dir)
                print(
                    json.dumps(
                        {
                            "added": preview.added,
                            "unchanged": preview.unchanged,
                            "conflicts": preview.conflicts,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                if args.apply_import:
                    decisions = {}
                    for value in args.resolve_conflict:
                        identity, separator, choice = value.partition("=")
                        if not separator or choice not in {"existing", "incoming"}:
                            raise ValueError("Use --resolve-conflict ID=existing or ID=incoming.")
                        decisions[identity] = choice
                    backup = apply_import(preview, decisions)
                    print(
                        translate(
                            "Collection imported. Backup: {path}", args.lang, path=backup or "-"
                        )
                    )
            return 0
        except BundleExistsError as exc:
            message = "File already exists: {path}. Use --replace-bundle to replace it."
            print(translate(message, args.lang, path=exc.path), file=sys.stderr)
            return 1
        except (OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.dictionary_info or args.install_dictionary:
        print(PACKAGE.description)
        print(PACKAGE.url)
        print(PACKAGE.license_url)
        if args.install_dictionary:
            try:
                print(install_dictionary(args.dictionary_dir))
            except (CambridgeError, OSError) as exc:
                print(str(exc), file=sys.stderr)
                return 1
        return 0
    if (
        args.recording
        or args.anki_reference
        or args.export_anki
        or args.translate_saved
        or args.set_translation is not None
        or args.reset_translation
        or args.choose_translation
    ):
        try:
            if args.word:
                parser.error("Use --recording to select saved MP3 files, without a word argument.")
            if args.recording:
                records = []
                for path in args.recording:
                    saved = read_recording(path)
                    if saved is None:
                        raise ValueError(f"Missing or unreadable recording: {path}")
                    records.append(saved)
            else:
                records = scan_recordings(args.output_dir)
            editing_translation = (
                args.set_translation is not None
                or args.reset_translation
                or args.choose_translation
            )
            if editing_translation and not args.recording:
                parser.error("Translation edits require --recording.")
            language = args.translation or "russian"
            updated = []
            for saved in records:
                if args.set_translation is not None or args.reset_translation:
                    saved = edit_translation(saved, language, args.set_translation)
                elif args.choose_translation:
                    saved = select_translation(saved, language, args.choose_translation)
                elif args.translate_saved:
                    with CambridgeClient(args.timeout, language=args.lang) as client:
                        result = resolve_translation(
                            client,
                            saved,
                            language,
                            directory=args.dictionary_dir,
                            offline=args.offline,
                        )
                    saved = persist_translation(saved, result)
                    print(result.format(args.lang))
                    if result.error:
                        print(result.error, file=sys.stderr)
                result = cached_translation(saved, language)
                if result and not args.translate_saved:
                    print(result.format(args.lang))
                updated.append(saved)
            if args.anki_reference:
                count = adopt_anki_identities(updated, args.anki_reference, args.output_dir)
                print(translate("Mapped {count} existing Anki notes.", args.lang, count=count))
            if args.export_anki:
                exporter = export_apkg if args.export_format == "apkg" else export_anki
                print(exporter(updated, args.export_anki, language=language))
            return 0
        except (CambridgeError, OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.tui and (args.word or not is_terminal()):
        parser.error(translate("--tui requires a terminal and no word argument.", language))
    if args.play is None:
        args.play = not args.word
    if args.combine is None:
        args.combine = not args.word
    if not args.word and not args.plain and is_terminal():
        # Import lazily: scripts and desktop packaging do not initialize a TUI.
        from .terminal import CambridgeApp, Options
        from .terminal.settings import load_settings

        saved = load_settings()
        # Reparse with persisted defaults so argparse itself gives explicit flags
        # priority, including --flag=value, abbreviations and --no-play/combine.
        names = {"language": "lang", "directory": "output_dir"}
        parser.set_defaults(**{names.get(k, k): v for k, v in saved.items() if k != "theme"})
        args = parser.parse_args(argv)
        if args.play is None:
            args.play = True
        if args.combine is None:
            args.combine = True

        CambridgeApp(
            Options(
                args.output_dir,
                language=args.lang,
                accent=args.accent,
                play=args.play,
                combine=args.combine,
                translation=args.translation,
                timeout=args.timeout,
                overwrite=args.overwrite,
                dictionary_dir=args.dictionary_dir,
                offline=args.offline,
            ),
            theme=saved.get("theme", "cambridge-dark"),
        ).run()
        return 0
    with CambridgeClient(args.timeout, language=args.lang) as client:
        if not args.word:
            return interactive(client, args)
        try:
            if args.list_variants:
                for choice in variants(client.lookup(" ".join(args.word)), args.accent):
                    print(
                        f"{choice.id}  sense={choice.entry.sense_id}  "
                        f"audio={choice.pronunciation.id}  {choice.label}"
                    )
            elif args.preview:
                from tempfile import TemporaryDirectory

                choices = tuple(
                    v
                    for v in variants(client.lookup(" ".join(args.word)), args.accent)
                    if (not args.variant or v.id == args.variant)
                    and (not args.sense or v.entry.sense_id == args.sense)
                    and (not args.audio or v.pronunciation.id == args.audio)
                )
                if not choices:
                    raise ValueError(
                        translate(
                            "The selected meaning/audio is no longer available. Choose again.",
                            args.lang,
                        )
                    )
                if len(choices) != 1:
                    raise SelectionRequired(choices, tuple(v.entry for v in choices))
                with TemporaryDirectory(prefix="cambridge-preview-") as temp:
                    path = preview_recording(
                        client, choices[0], Path(temp), collection_dir=args.output_dir
                    )
                    play_audio(path, args.lang)
            else:
                download_word(client, " ".join(args.word), args, set())
        except (CambridgeError, OSError, ValueError) as exc:
            print(translate("Error: {error}", args.lang, error=exc), file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            return 130
    return 0

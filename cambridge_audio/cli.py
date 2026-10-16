"""Command-line and interactive Cambridge Dictionary audio downloader."""

import argparse
import math
import sys
from importlib.metadata import version
from pathlib import Path

from .anki import export_anki
from .audio import play_audio
from .console import Output, is_terminal
from .dictionary import (
    CambridgeClient,
    CambridgeError,
    SelectionRequired,
    variants,
)
from .i18n import translate
from .library import read_recording, save_metadata, scan_recordings
from .service import Recording, download_recordings
from .translations import (
    cached_translation,
    edit_translation,
    persist_translation,
    resolve_translation,
    select_translation,
)
from .wikdict import PACKAGE, install_dictionary


class HelpFormatter(argparse.HelpFormatter):
    def __init__(self, prog: str, language: str):
        super().__init__(prog)
        self.language = language

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

    def saved(recording: Recording) -> None:
        downloaded.add(recording.path)
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
        )

    try:
        with output.working():
            result = perform()
    except SelectionRequired as exc:
        if args.word:
            raise
        print(str(exc))
        selected = input(translate("Pronunciation ID (empty cancels): ", args.lang)).strip()
        if not selected:
            return
        with output.working():
            result = perform(selected, exc.entries)
    for i, recording in enumerate(result.recordings):
        store_details(recording, () if result.translation_results else result.translations)
        if result.translation_results:
            persist_translation(read_recording(recording.path), result.translation_results[i])
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
                    path.unlink(missing_ok=True)
                    path.with_suffix(".json").unlink(missing_ok=True)
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
    language_parser.add_argument("--lang", choices=("en", "ru"), default="en")
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
        choices=("en", "ru"),
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
        help=translate("List pronunciation IDs without downloading.", language),
    )
    options.add_argument(
        "--variant", help=translate("Download the listed pronunciation ID.", language)
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
        help=translate("Export the collection to an Anki TSV folder.", language),
    )
    options.add_argument(
        "--recording",
        action="append",
        type=Path,
        help=translate("Select a saved MP3 for translation or export; repeatable.", language),
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
    args = parser.parse_args(argv)
    if (args.list_variants or args.variant) and not args.word:
        parser.error("--list-variants and --variant require a word argument.")
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
            if args.export_anki:
                print(export_anki(updated, args.export_anki, language=language))
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
                    print(f"{choice.id}  {choice.label}")
            else:
                download_word(client, " ".join(args.word), args, set())
        except (CambridgeError, OSError, ValueError) as exc:
            print(translate("Error: {error}", args.lang, error=exc), file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            return 130
    return 0

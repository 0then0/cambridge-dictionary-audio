# Cambridge Dictionary Audio CLI

Download US and UK pronunciation recordings from Cambridge Dictionary, keep a
local collection, add Russian translations and export notes to Anki. The package
includes command-line and terminal interfaces for Windows, macOS and Linux, with
Python **3.10–3.15** and no Qt dependency.

[Project documentation](https://github.com/0then0/cambridge-dictionary-audio/blob/main/docs/README.md) ·
[Changelog](https://github.com/0then0/cambridge-dictionary-audio/blob/main/CHANGELOG.md) ·
[Desktop downloads](https://github.com/0then0/cambridge-dictionary-audio/releases)

Repository documentation follows `main`; the changelog identifies changes not yet
included in published packages.

## Installation

```sh
uv tool install cambridge-dictionary-audio
```

Alternatively, use `pipx install cambridge-dictionary-audio` or install with pip
inside a virtual environment. Desktop and mobile applications are distributed
separately.

## First download

```sh
cambridge-audio hello
cambridge-audio "good morning" --accent both --output-dir audio
cambridge-audio hello --lang ru --translation russian
cambridge-audio --help
```

US pronunciation and English interface messages are the defaults. Recordings are
saved under `downloads/` in the current directory. Use `--output-dir PATH` to
change the destination. Completed MP3s are written atomically; interrupted writes
do not replace saved audio. Existing files are retained unless `--overwrite` is
specified. `python -m cambridge_audio` is an equivalent entry point.

Words and phrases are case-insensitive. Quotes, apostrophes and hyphens are
supported; URLs and path separators are rejected. Saved filenames include `.us`
or `.uk`. Interface language and translation settings are independent:
`--lang en|ru|es|de|fr|ja|pt-BR` changes messages, while `--translation russian` enables
translations.
Aliases `ru` and `русский` are accepted for the translation language.

Lookup/download failures exit with status 1; invalid arguments exit with status 2.
Playback or optional translation failure does not invalidate a completed download.
With both accents selected, a completed first recording survives a failure of the
second download.

## Meanings and pronunciations

A word can have several dictionary meanings or recordings. List the choices,
then select the intended meaning and audio:

```sh
cambridge-audio lead --list-variants
cambridge-audio lead --sense SENSE_ID --audio AUDIO_ID --preview
cambridge-audio lead --sense SENSE_ID --audio AUDIO_ID
```

`--preview` plays from a temporary cache without adding an entry to the collection.
Without it, the selected recording is saved. If a choice is ambiguous, the CLI
lists alternatives and exits with status 1. The combined `--variant CHOICE_ID`
option is also supported. `--accent both` saves both accents when each has one
unambiguous choice; an explicit audio ID selects only that recording.

Meanings keep their own definitions, translations and permanent collection IDs.
They can share a verified MP3 when the accent and source URL match. Keep JSON
metadata and MP3s together when moving the collection. Prefer an entry's JSON
path for `--recording`; an MP3 path is accepted when it identifies one meaning.
Older MP3-only collections and v1/v2 metadata remain readable.

## Russian translations

Look up translations without downloading saved audio again:

```sh
cambridge-audio --recording downloads/ENTRY.us.json --translation russian --translate-saved
cambridge-audio --recording downloads/ENTRY.us.json --translation russian --set-translation "привет"
cambridge-audio --recording downloads/ENTRY.us.json --translation russian --reset-translation
cambridge-audio --recording downloads/ENTRY.us.json --translation russian --choose-translation SOURCE_SENSE_ID
```

Personal translations take priority over cached and dictionary results. An edit
applies to the same meaning and language across its saved pronunciations; other
meanings are unaffected. Reset removes the personal edit and restores the cached
dictionary result. Ambiguous source translations require an explicit choice
before Anki export.

### Offline WikDict

```sh
cambridge-audio --dictionary-info
cambridge-audio --install-dictionary
cambridge-audio --recording downloads/ENTRY.us.json --translation russian --translate-saved --offline
```

WikDict is installed only on request. `--dictionary-info` displays the pinned
English–Russian package, size, source URL and license. Downloads are verified by
size, SHA-256 and SQLite checks before replacement. A failed update preserves an
existing package. Use `--dictionary-dir PATH` to override its data directory.
`--offline` uses cached translations and the installed dictionary without making
online translation requests.

See [dictionary sources and licenses](https://github.com/0then0/cambridge-dictionary-audio/blob/main/docs/data-sources.md)
for provenance and the exact package checksum.

## Backups and collection transfer

A `.cda` archive contains metadata, personal translations, shared audio and Anki
identity mappings. Import previews changes before applying them:

```sh
cambridge-audio --output-dir downloads --export-collection ../backup.cda
cambridge-audio --output-dir restored --import-collection ../backup.cda
cambridge-audio --output-dir restored --import-collection ../backup.cda --apply-import
cambridge-audio --output-dir restored --import-collection ../backup.cda --apply-import \
  --resolve-conflict ID=existing
```

Resolve each conflict with `ID=existing` or `ID=incoming`. Import retains the
previous collection as a backup. The same format works with the desktop GUI and
mobile apps.

Export never replaces an existing file by default: the command exits with status 1,
prints no success output and leaves the file unchanged. To replace a previous backup
deliberately, add `--replace-bundle` (`--overwrite` applies to MP3 files only):

```sh
cambridge-audio --output-dir downloads --export-collection ../backup.cda --replace-bundle
```

The archive is written to a temporary file next to the destination, validated and then
published in one step. Until that step the previous file is kept, and an error leaves it
unchanged. A file that appears at the destination in the meantime is not replaced
either. This protects against accidental replacement and interrupted writes; it does
not promise that the file survives a power failure. On Linux and macOS a new file is
published with a hard link, so a file system without hard-link support may report an
error instead of saving; choose another location. The export never falls back to
replacing the destination.

To restore, import the archive into a collection folder as shown above. Import
previews the changes first and retains the previous folder as a backup. See the [storage specification](https://github.com/0then0/cambridge-dictionary-audio/blob/main/docs/mobile/storage.md)
for archive limits, identity rules and recovery.

## Anki export

```sh
cambridge-audio --output-dir downloads --export-anki my-deck.apkg
cambridge-audio --recording downloads/ENTRY.us.json --export-anki selected.apkg
cambridge-audio --output-dir downloads --export-anki tsv-export --export-format tsv
```

An `.apkg` includes the note type, one card template, selected audio, definitions,
IPA, translations and source attribution. The front shows the word; the back
shows the remaining fields and a collapsed **Source** disclosure. Anki does not
need to be installed to create an export.

Stable collection IDs let reimports update matching notes while retaining card
identities and review history. Anki controls note and note-type updates separately:
**If newer** for notes can replace edits made only in Anki when the export is newer;
**Never** preserves those edits but prevents content updates. **Never** for note
types preserves existing CSS and templates. Keep personal translations in the
Cambridge collection when they must survive later exports.

TSV export produces `collection.tsv`, `media/`, `IMPORT.txt` and `SOURCES.txt`.
Follow `IMPORT.txt` when setting up its fields and copying audio. Previously
imported TSV notes need explicit GUID mapping before switching to packages:

```sh
cambridge-audio --output-dir downloads --anki-reference old-from-anki.apkg
cambridge-audio --output-dir downloads --export-anki updated.apkg
```

Create the reference in Anki with **Support older Anki versions** enabled and keep
a backup first. Mapping supports the original nine-field, single-template schema.
Retain `.anki-mapping.json` with the collection. For a different schema, continue
using TSV. The command reads the exported copy, not a live Anki profile.
The [collection guide](https://github.com/0then0/cambridge-dictionary-audio/blob/main/docs/collection.md)
explains import options, compatibility and migration in detail.

## Terminal workspace

Run `cambridge-audio` without a word in an interactive terminal to open the
searchable library and recording panel. `--tui` selects the workspace explicitly;
`--plain` selects a line-based prompt. Enter in search finds meanings or opens
saved audio offline; Enter in the library plays the selected recording.

- **Tab / Shift+Tab** navigates controls; **Up / Down** selects a recording.
- **Ctrl+L** searches; **Ctrl+P** plays/stops; **Ctrl+R** refreshes the library.
- **Ctrl+S** opens settings; **F1** opens help; **F2** opens About; **Ctrl+Q** quits.
- **Ctrl+C** cancels a download, stops playback or quits when idle. Completed
  recordings are retained.

Function keys work independently of keyboard layout: **F3** search, **F4**
play/stop, **F5** refresh, **F6** settings, **F7** export, **F8** translation,
**F9** WikDict, **F10** meanings, **F11** cancel and **F12** quit.

Settings persist language, theme, accent, destination, translation display,
autoplay and phrase synthesis. Explicit CLI flags override saved values for the
current run. Preferences are stored in `cambridge-dictionary-audio/tui-settings.json`
under `~/Library/Application Support` on macOS, `%APPDATA%` on Windows, or
`$XDG_CONFIG_HOME` (default `~/.config`) on Linux. Invalid settings fall back to
defaults; failed writes preserve the previous file and display an error.

## Playback and phrase synthesis

Use `--play` to listen after downloading. Windows opens the default audio player;
macOS uses `afplay`; Linux needs `ffplay`, commonly supplied with FFmpeg.
To synthesize a phrase when Cambridge has no complete recording, install FFmpeg
with the `libmp3lame` encoder in PATH and pass `--combine`:

```sh
cambridge-audio "hello friendly world" --combine
```

Synthesis combines recorded words in order and normalizes loudness. It runs when
the phrase or requested accent is absent, not after a network failure. Every
segment needs a recording in the selected accent. The result is synthesized
from recordings, not text-to-speech or a Cambridge recording of the full phrase.
`ffprobe` is useful for inspection but is not a runtime dependency.

## Requests and diagnostics

Cambridge requests share a one-second minimum interval within the process.
HTTP 429 is retried at most twice, respecting `Retry-After`; otherwise delays
start at two and four seconds with up to half a second of jitter. HTTP 403 is not
retried. A cooldown longer than 30 seconds stops the operation and reports the
remaining wait. Cancellation interrupts backoff waits.

A client caches up to 64 successful HTML pages during its lifetime. Recordings
and translations persist separately in the collection. Errors in the terminal
workspace show a short explanation with optional technical details.

## License and attribution

Application code uses [Apache-2.0](https://github.com/0then0/cambridge-dictionary-audio/blob/main/LICENSE).
Code inherited from [astrosander/cambridge-dictionary-audio](https://github.com/astrosander/cambridge-dictionary-audio)
retains its [MIT license](https://github.com/0then0/cambridge-dictionary-audio/blob/main/LICENSE-MIT).
Both licenses and the attribution notice are included in the distribution.

The project is independent of Cambridge University Press & Assessment.
Dictionary content retains its owners' rights and is subject to
[Cambridge's website terms](https://dictionary.cambridge.org/terms-of-use).
WikDict data and adaptations retain CC BY-SA 4.0 with their separate provenance.

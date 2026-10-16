# Cambridge Dictionary Audio CLI

Download American and British pronunciation recordings from Cambridge Dictionary
without a desktop interface. US pronunciation and English interface messages are
the defaults. Python 3.10–3.15 is supported on Windows, macOS and Linux.

## Installation

```sh
uv tool install cambridge-dictionary-audio
```

Alternatively, use `pipx install cambridge-dictionary-audio` or install with pip
inside a virtual environment. This package contains the CLI only and does not
install Qt. Desktop installers are available from the
[GitHub releases](https://github.com/0then0/cambridge-dictionary-audio/releases).

## Usage

```sh
cambridge-audio hello
cambridge-audio "good morning" --accent both --output-dir audio
cambridge-audio hello --lang ru --translation russian
cambridge-audio --help
cambridge-audio
cambridge-audio --lang ru
```

Files are saved in `downloads/` under the current working directory. Use
`--output-dir` to change the destination and `--overwrite` to replace existing
files. Completed MP3s are published atomically; an interrupted write leaves no
partial recording. Running `cambridge-audio` without a word opens the terminal workspace.
`python -m cambridge_audio` is also supported.

## Request pacing and rate limits

Cambridge requests share a one-second minimum interval within the process.
HTTP 429 responses are retried at most twice. The client honors `Retry-After`
(seconds or an HTTP date); otherwise delays start at two and four seconds with
up to half a second of random jitter. HTTP 403 responses are not retried.
If a server cooldown exceeds 30 seconds, the operation stops and reports the
remaining wait; subsequent requests in the same process honor that cooldown.
GUI/TUI cancellation interrupts these waits, and Ctrl+C interrupts CLI waits.

A client caches up to 64 successful HTML pages for its lifetime. This reduces
repeated lookups while preserving fresh MP3 downloads when explicitly requested.
Saved recordings and translations retain their existing persistent cache behavior.

## Terminal workspace

The workspace has a searchable library and a recording detail panel. Narrow
terminals use a vertical layout. Enter in search downloads a word or opens saved
audio offline; Enter in the library plays the selected recording. Selecting both
accents downloads only missing files. **Download again** asks before replacing audio.
Downloads and playback run in the background so navigation remains responsive.

- **Tab / Shift+Tab**: navigate controls; **Up / Down**: select a recording.
- **Ctrl+L**: search; **Ctrl+P**: play/stop; **Ctrl+R**: refresh the library.
- **Ctrl+S**: settings; **F1**: help; **F2**: About; **Ctrl+Q**: quit.
- **Ctrl+C**: cancel the download, stop playback or quit when idle. The current request finishes
  before cancellation, and completed files are retained.

All commands also have shortcuts independent of the keyboard layout: **F3** search,
**F4** play/stop, **F5** refresh, **F6** settings, **F7** export, **F8** translation,
**F9** WikDict, **F10** pronunciation, **F11** cancel, **F12** quit.
Ctrl shortcuts accept Russian and Ukrainian letters at the same key positions.
If the terminal does not report Ctrl with non-Latin letters, use the function keys.

Settings offer English/Russian interface messages, light/dark themes, accent,
destination, a Russian translation toggle, autoplay and phrase synthesis. Apply
saves these preferences for future TUI launches; Cancel discards dialog changes.
Explicit CLI flags override saved values for the current run without rewriting
the file until preferences are changed in the UI. Plain and one-shot CLI commands
keep their existing defaults. The main translation checkbox also saves its state.

Preferences are stored as UTF-8 JSON in `cambridge-dictionary-audio/tui-settings.json`
under `~/Library/Application Support` on macOS, `%APPDATA%` on Windows, or
`$XDG_CONFIG_HOME` (default `~/.config`) on Linux. Invalid fields fall back to
defaults; failed writes preserve the previous file and show an error in the TUI.

Translation is
optional and always targets Russian. The checkbox shows or hides cached results
immediately. Missing translations are fetched in the background without downloading
audio again. The panel shows loading and request errors. English definitions stay
visible with translation off. Metadata remains in JSON beside MP3s, shared with the
GUI. Old foreign-language caches and edits are preserved. A legacy translation
without a language is not assumed to be Russian. Existing MP3s without metadata
remain playable; empty files are ignored.

## License and attribution

This fork is distributed under Apache-2.0. Code inherited from
[astrosander/cambridge-dictionary-audio](https://github.com/astrosander/cambridge-dictionary-audio)
retains its MIT license and copyright notice. The distribution includes both
licenses and the attribution notice.

The project is independent of Cambridge University Press & Assessment.
Downloaded recordings remain subject to their owners' rights and Cambridge's
[website terms](https://dictionary.cambridge.org/terms-of-use).

## Choose a pronunciation

A choice identifies a Cambridge entry, part of speech, definition and a specific
US or UK MP3 with its own IPA. Multiple definitions sharing audio remain distinct
choices. A word with one choice downloads immediately. Ambiguous words open a
selector in the GUI and TUI. Labels show accent, part of speech, definition and IPA.

```sh
cambridge-audio lead --list-variants
cambridge-audio lead --variant ID_FROM_THE_LIST
cambridge-audio lead --variant ID_FROM_THE_LIST --overwrite
```

One explicit ID selects one accent and pronunciation, including with `--accent both`.
Without an explicit ID, `both` saves both accents when each has a single choice.
If choices are ambiguous, choose and save individual variants. One-shot CLI commands
report available IDs and exit with status 1 until `--variant` selects one.
The plain interactive prompt asks for an ID when needed.

The GUI's **Choose another pronunciation** button searches the current word even
if a recording is already saved. In the TUI use **Ctrl+O**. Saved variants appear
separately in the library. **Download again** targets only the selected recording
and asks before replacement. In the CLI `--overwrite` is the explicit replacement
confirmation; it only applies to the selected variant.

IDs derive from Cambridge's entry/sense identifiers and content, not HTML order.
A recording ID additionally includes accent and the MP3 URL. If Cambridge changes
these identifiers or definitions, a new ID can result; old recordings are retained.
Ambiguous variants use `word--ID.us.mp3` / `word--ID.uk.mp3`. Long words are truncated
with a hash; Windows reserved names receive `_`. Names are portable across all
three platforms. A unique ordinary download keeps `word.us.mp3` / `word.uk.mp3`.

JSON v2 sidecars preserve source entry, sense, part of speech, definition, IPA,
audio URL, IDs and translation caches. The app reads old v1 sidecars and MP3s
without metadata, including symlink aliases. Unknown legacy translation languages
are never assumed to be Russian. Existing files are not renamed or moved.
A legacy recording without source identity must be selected again to associate a
precise Cambridge sense; its original file remains available.

## Translation lookup and editing

Lookup order: personal translation for this sense and language, usable saved
cache, Cambridge bilingual dictionary, installed local WikDict. Audio saving and
playback do not depend on a successful translation. A local fallback keeps the
Cambridge error visible. Missing translation, network failure, blocking, missing
local dictionary and corrupt local dictionary produce separate statuses.

Version 0.3.0 supports English words and definitions with optional Russian
translations. The GUI has a **Show Russian translation** checkbox, an offline
dictionary status and **Install WikDict**; no free-form language field is shown.
The TUI offers the same Russian translation toggle in its recording panel and
Settings. English definitions remain visible when translation is off. Interface
language (`--lang en` / `--lang ru`) is independent of this toggle.

The checkbox shows and hides cached Russian results immediately, without repeating
requests for a usable cache. CLI: `--translation russian` enables translation;
`ru` and `русский` are accepted aliases. Other translation languages are rejected
before network access. Existing foreign-language caches and personal edits remain
in JSON with their original language and source; they are not relabeled or deleted.

WikDict source senses are not asserted to match a Cambridge definition. The result
shows the source's part of speech and gloss and explicitly marks unverified sense
alignment. If several source senses remain, choose one before exporting.

GUI: **Edit translation**, **Reset translation**, **Choose translation sense**.
TUI: **Ctrl+T** opens editing, reset and source-sense choices.
CLI examples, without any audio download:

```sh
cambridge-audio --recording downloads/hello.us.mp3 --translation russian --translate-saved
cambridge-audio --recording downloads/hello.us.mp3 --translation russian --set-translation "привет"
cambridge-audio --recording downloads/hello.us.mp3 --translation russian --reset-translation
cambridge-audio --recording downloads/hello.us.mp3 --translation russian --choose-translation SOURCE_SENSE_ID
```

Personal edits apply to a sense and language, shared by saved pronunciations of
that same sense in the folder. Other meanings and languages are untouched. They
survive restart, automatic lookup and redownload. Reset removes only the personal
edit so the original cached dictionary result becomes available again.

## Install the local dictionary

The supported translation direction in 0.3.0 is **English → Russian**, both for
Cambridge online lookup and the verified local WikDict package.

```sh
cambridge-audio --dictionary-info
cambridge-audio --install-dictionary
cambridge-audio --recording downloads/hello.us.mp3 --translation russian --translate-saved --offline
```

The CLI prints the version, download size, source URL and license before
installation. GUI: **Install WikDict**. TUI: **Ctrl+D**. Both show the package
information before confirmation; the GUI reports downloaded bytes. Installation
is explicit; normal lookup never downloads a dictionary. No API key is needed.
Each GUI click checks the installed package locally. A verified installation or
a damaged package prompts for explicit confirmation before downloading again;
declining leaves the existing file untouched.
Use `--dictionary-dir PATH` to override the platform data directory in CLI/TUI.

The pinned package is `en-ru.sqlite3`, version `2_2026-06`, **20.9 MB** (20,938,752 bytes)
(about 20 MiB). SHA-256:
`3f65395883b996131c9b7a7b7b7c14c1b4458c892fae0050decd71dc0a3b4b0a`.
The application downloads only this pair, without the large English morphology
DB or a full Wiktionary dump. It queries exact source forms; a Cambridge headword
is used as a lemma only when explicitly supplied by Cambridge, with no stemming.

The download is staged beside the destination, bounded by the expected size,
verified by size, pinned SHA-256 and SQLite integrity/schema checks, then replaced
atomically. An interrupted download or failed update leaves an existing package
intact. Lookup verifies the installed package and opens it read-only. Attribution
is installed in `WIKDICT-LICENSE.txt` beside the database.

Default locations:

- Windows: `%LOCALAPPDATA%/cambridge-dictionary-audio/dictionaries`.
- macOS: `~/Library/Application Support/cambridge-dictionary-audio/dictionaries`.
- Linux: `$XDG_DATA_HOME/cambridge-dictionary-audio/dictionaries`, defaulting to
  `~/.local/share/cambridge-dictionary-audio/dictionaries`.

See [data sources and licenses](data-sources.md). WikDict data is CC BY-SA 4.0,
separate from the application's Apache-2.0 code.

## Export to Anki

GUI: **Export to Anki**, select the current recording or whole collection, then a
parent folder. The app writes `cambridge-anki/` there. TUI: **Ctrl+E**, choose scope
and enter the export folder. CLI exports everything in `--output-dir` unless one
or more `--recording` arguments select specific MP3s:

```sh
cambridge-audio --output-dir downloads --export-anki exports/my-deck --translation russian
cambridge-audio --recording downloads/hello.us.mp3 --recording downloads/hello.uk.mp3 --export-anki exports/two-notes
```

The export folder contains `collection.tsv` (UTF-8), `media/` with flat, unique
MP3 names, `IMPORT.txt` and `SOURCES.txt`. The nine fields are **ID, Word,
PartOfSpeech, Definition, Translation, IPA, Accent, Audio, Source**.
Only the selected translation for the requested language is exported. A blank
translation stays blank. Ambiguous untranslated sense choices must be resolved
before export. Missing, invalid or inaccessible MP3s fail the export with the
specific file named. No original file is changed and no audio is downloaded.

Copy the contents of `media/` directly into Anki's `collection.media`, without a
subdirectory. Create a note type with the nine fields in the listed order, keeping
**ID first**, and use Word and Audio in your card templates. Import with **Tab**
as separator and **Allow HTML in fields** enabled. The TSV includes these headers
for Anki 2.1.54+. Text is HTML-escaped; line breaks become `<br>`; quotes and tabs
are handled as quoted TSV fields. Audio fields contain `[sound:filename.mp3]`.

For repeat imports use the same note type, match on its first field and choose
**update existing notes**. Map our ID to the ordinary ID field, not Anki's internal
GUID. Different senses and pronunciations have distinct IDs. Re-exporting the
same variants preserves IDs and media names. Existing Cambridge export folders
can be replaced transactionally; unrelated destination folders are refused.
A copy or publication failure preserves the previous export and source collection.
Do not add personal files inside an export folder that will be regenerated.

This release creates TSV only, without `.apkg`, AnkiConnect or synchronization.
Format reference: [Anki text import manual](https://docs.ankiweb.net/manual/importing/text-files).

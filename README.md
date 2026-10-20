<p align="center">
  <img src="assets/icon.svg" width="120" alt="Cambridge Dictionary Audio icon">
</p>

# Cambridge Dictionary Audio

[![Checks](https://img.shields.io/github/actions/workflow/status/0then0/cambridge-dictionary-audio/checks.yml?branch=main&label=checks)](https://github.com/0then0/cambridge-dictionary-audio/actions/workflows/checks.yml)
[![Mobile checks](https://img.shields.io/github/actions/workflow/status/0then0/cambridge-dictionary-audio/mobile.yml?branch=main&label=mobile)](https://github.com/0then0/cambridge-dictionary-audio/actions/workflows/mobile.yml)
[![Python](https://img.shields.io/badge/Python-3.10%E2%80%933.15-3776AB?logo=python&logoColor=white)](#python-versions)
[![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20macOS%20%7C%20Linux-blue)](#playback-and-ffmpeg)
[![uv](https://img.shields.io/badge/dependencies-uv-DE5FE9)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/badge/lint%20%26%20format-Ruff-D7FF64)](https://docs.astral.sh/ruff/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

[![Release](https://img.shields.io/github/v/release/0then0/cambridge-dictionary-audio)](https://github.com/0then0/cambridge-dictionary-audio/releases/latest)
[![PyPI](https://img.shields.io/pypi/v/cambridge-dictionary-audio)](https://pypi.org/project/cambridge-dictionary-audio/)

[Русский](README.ru.md) · [Documentation](docs/README.md) · [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

Download English pronunciation recordings from
[Cambridge Dictionary](https://dictionary.cambridge.org/) as MP3 files.
Desktop, terminal and mobile applications provide US and UK audio, IPA
transcriptions, English definitions, Russian translations and Anki export.
Browser extensions download pronunciation from the current dictionary page.

## Android and iOS

The [mobile applications](docs/mobile/README.md) offer pronunciation search,
offline collections, Russian translations, phrase synthesis and Anki export.
Android uses Kotlin and Compose Material 3; iOS uses SwiftUI with a shared Kotlin
core. Minimum versions are Android 9 and iOS 17. The mobile version is
**1.0.0**. Android test APKs and unsigned iOS archives are available in the
[release downloads](https://github.com/0then0/cambridge-dictionary-audio/releases/latest).
See [builds, installation and signing](docs/mobile/install.md).

Collections can be backed up and transferred between the desktop and mobile apps
as `.cda` archives, including personal translations, shared media and permanent
Anki identities. Import previews conflicts before applying changes.
See [backups and transfer](docs/collection.md#backups-and-transfer).

## Desktop app

<!-- downloads:start -->

Direct downloads for the latest verified stable release **v1.0.0**:

| Platform    | Architecture                     | Download                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ----------- | -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Windows 10+ | x86-64                           | [![Windows 10+ x86-64 EXE](https://img.shields.io/badge/EXE-0078D4?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xIDFoMTB2MTBIMXpNMTMgMWgxMHYxMEgxM3pNMSAxM2gxMHYxMEgxek0xMyAxM2gxMHYxMEgxM3oiLz48L3N2Zz4%3D&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-dictionary-audio-1.0.0-windows-x86_64-setup.exe) [![Windows 10+ x86-64 Portable ZIP](https://img.shields.io/badge/Portable%20ZIP-0078D4?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xIDFoMTB2MTBIMXpNMTMgMWgxMHYxMEgxM3pNMSAxM2gxMHYxMEgxek0xMyAxM2gxMHYxMEgxM3oiLz48L3N2Zz4%3D&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-dictionary-audio-1.0.0-windows-x86_64-portable.zip) |
| macOS 14+   | Apple Silicon (arm64)            | [![macOS 14+ Apple Silicon (arm64) PKG](https://img.shields.io/badge/PKG-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-dictionary-audio-1.0.0-macos-arm64.pkg) [![macOS 14+ Apple Silicon (arm64) DMG](https://img.shields.io/badge/DMG-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-dictionary-audio-1.0.0-macos-arm64.dmg) [![macOS 14+ Apple Silicon (arm64) TAR.GZ](https://img.shields.io/badge/TAR.GZ-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-dictionary-audio-1.0.0-macos-arm64.tar.gz)                                                                                                                                                                                                                            |
| macOS 14+   | Intel (x86-64)                   | [![macOS 14+ Intel (x86-64) PKG](https://img.shields.io/badge/PKG-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-dictionary-audio-1.0.0-macos-x86_64.pkg) [![macOS 14+ Intel (x86-64) DMG](https://img.shields.io/badge/DMG-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-dictionary-audio-1.0.0-macos-x86_64.dmg) [![macOS 14+ Intel (x86-64) TAR.GZ](https://img.shields.io/badge/TAR.GZ-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-dictionary-audio-1.0.0-macos-x86_64.tar.gz)                                                                                                                                                                                                                                              |
| Linux       | x86-64 · glibc 2.34+             | [![Linux x86-64 · glibc 2.34+ DEB](https://img.shields.io/badge/DEB-FCC624?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-dictionary-audio_1.0.0_amd64.deb) [![Linux x86-64 · glibc 2.34+ RPM](https://img.shields.io/badge/RPM-FCC624?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-dictionary-audio-1.0.0-1.x86_64.rpm) [![Linux x86-64 · glibc 2.34+ Portable TAR.GZ](https://img.shields.io/badge/Portable%20TAR.GZ-FCC624?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-dictionary-audio-1.0.0-linux-x86_64-portable.tar.gz)                                                                                                                                                                                                                      |
| Android 9+  | arm64-v8a / armeabi-v7a / x86_64 | [![Android 9+ arm64-v8a / armeabi-v7a / x86_64 Test APK](https://img.shields.io/badge/Test%20APK-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-audio-1.0.0-android-debug-TEST-ONLY.apk) [![Android 9+ arm64-v8a / armeabi-v7a / x86_64 Unsigned APK](https://img.shields.io/badge/Unsigned%20APK-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-audio-1.0.0-android-unsigned-NOT-INSTALLABLE.apk)                                                                                                                                                                                                                                                                                                                                                                                                                               |
| iOS 17+     | arm64                            | [![iOS 17+ arm64 Device · signing required](https://img.shields.io/badge/Device%20%C2%B7%20signing%20required-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-audio-1.0.0-ios-device-unsigned-REQUIRES-SIGNING.tar.gz) [![iOS 17+ arm64 Simulator only](https://img.shields.io/badge/Simulator%20only-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-audio-1.0.0-ios-simulator-NOT-FOR-DEVICE.tar.gz)                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| Python CLI  | Any                              | [![Python CLI Any WHL](https://img.shields.io/badge/WHL-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge_dictionary_audio-1.0.0-py3-none-any.whl) [![Python CLI Any Source TAR.GZ](https://img.shields.io/badge/Source%20TAR.GZ-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge_dictionary_audio-1.0.0.tar.gz)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| Chrome      | Any                              | [![Chrome Any ZIP](https://img.shields.io/badge/ZIP-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-audio-chrome-1.0.0.zip)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| Firefox     | Any                              | [![Firefox Any ZIP](https://img.shields.io/badge/ZIP-FF7139?style=for-the-badge&logo=firefoxbrowser&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/cambridge-audio-firefox-1.0.0.zip)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |

[![SHA-256](https://img.shields.io/badge/SHA--256-SHA256SUMS.txt-555555?style=flat-square)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.0/SHA256SUMS.txt)

Android: the test APK uses a development certificate; the unsigned APK requires signing before installation. iOS: the device archive requires signing and a provisioning profile; the simulator build cannot be installed on an iPhone. [Installation and signing](docs/mobile/install.md).
<!-- downloads:end -->

Installers and portable builds include Python, Qt and an audio-only LGPL build
of FFmpeg with LAME. Phrase synthesis needs no additional installation or PATH
configuration. Matching FFmpeg/LAME source archives and build parameters are
included in each release. Releases also include the CLI wheel, source
distribution and `SHA256SUMS.txt`. Windows installers require Windows 10 or later. Current installers are not signed with a
publisher certificate; macOS builds are not notarized.

Install the CLI separately from [PyPI](https://pypi.org/project/cambridge-dictionary-audio/):

```sh
uv tool install cambridge-dictionary-audio
```

### Run from source

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) 0.13.0 or newer,
then run these commands in the project directory:

```sh
uv sync --locked --group gui
uv run --group gui -m cambridge_audio.gui
```

Enter a word or phrase and click **Find** (or press Enter). Choose a meaning below
the result, switch US/UK, and use **Play** before **Save meaning**. Definitions are
shown in full; **Other pronunciation** appears only for multiple recordings of
the selected accent. Click **Play** to listen in the window,
or **Open folder** to find the MP3. No external player is needed for GUI playback.

- English and Russian interfaces; English is the default.
- System, light and dark appearance. System mode follows Qt's OS appearance
  notifications, with a light fallback when the platform does not report its theme.
- The gear button opens **Settings** for language and appearance. Choose any
  background and accent colours for the active light or dark palette; changes
  apply immediately and are remembered separately. Text and interface icons adapt
  for contrast. **Restore default colours** resets the active palette.
  **About** in Settings shows the app version, repository link and license information.
- US by default, UK or both available. Both recordings can be played individually.
- Optional dictionary translation and phrase synthesis using FFmpeg.
- Downloads run in the background. Errors are shown in the window; replacing
  existing recordings requires confirmation.
- Language, theme, pronunciation, options and folder are remembered using Qt's
  platform settings. The main window also restores its size, position and maximized
  state after restarting. The default GUI folder is `Cambridge Dictionary Audio` inside
  the user's Downloads folder. **Choose...** selects a different destination.
- **Saved recordings** lists existing `word.us.mp3` and `word.uk.mp3` files in the
  selected folder. Listen offline after restarting; **Refresh** picks up external
  changes. Entering a saved word opens it, and selecting both accents downloads
  only the missing variant. **Download again** asks before replacing a recording.
- New collection entries save details and translations in separate JSON files
  that can reference a shared MP3. Older recordings remain playable without that file.
  **Show Russian translation** shows or hides a cached translation immediately.
  When it is missing, the app fetches it in the background without downloading
  audio again. Loading and errors appear in the recording panel; toggle the
  checkbox off and on to retry a failed request.
- Errors show a short explanation. **Technical details** expands the original
  diagnostic next to the error message; it is hidden by default. The TUI offers the same
  details in a dialog.
- Scrollbar handles are 4 logical pixels wide and expand to 8 on hover. Their
  wider hit area stays fixed, so the surrounding layout does not shift.

The GUI uses PySide6 Essentials and Addons, without WebEngine or PDF components.
On macOS, launching from source automatically creates a small `.app` wrapper in
the application's cache so Dock displays the project name and icon.
Current wheels require macOS 14+, Linux glibc 2.34+ on x86-64 or 2.39+ on ARM64,
or supported 64-bit Windows. Minimal Linux desktops may also need the
[Qt platform runtime libraries](https://doc.qt.io/qt-6/linux-requirements.html).
These Qt requirements do not apply to the standalone Python CLI.
See [PySide6 releases](https://pypi.org/project/PySide6/) for platform details.

On Windows, `start-gui.bat` runs the desktop app from source through uv.

## Collection, translations and Anki

See the [collection guide](docs/collection.md) for meaning and pronunciation selection,
Russian translations, local WikDict installation and Anki export in the GUI, TUI
and CLI. [Data sources and licenses](docs/data-sources.md) covers dictionary
attribution and licensing separately from the application code.
Documentation describes the current source tree; check **Unreleased** in the
[changelog](CHANGELOG.md) for changes not yet included in published downloads.

Meanings remain separate collection entries and Anki notes, while meanings sharing
the same source recording reuse one verified MP3. Old local/export IDs and personal
translations are retained; old duplicate media are not removed automatically.

**Export to Anki** saves one ready `.apkg` with a template, audio and sources.
Sources and license notices are behind a small, closed **Source** disclosure on
cards and the deck overview. Export a fresh package and reimport with note updates
enabled to apply this to existing cards.
TSV remains available as an additional format:

```sh
cambridge-audio --output-dir downloads --export-anki my-deck.apkg
cambridge-audio --output-dir downloads --export-anki tsv-export --export-format tsv
```

Existing TSV imports need explicit GUID mapping before switching to packages;
otherwise duplicate notes are possible. The [transition instructions](docs/collection.md#existing-notes-imported-from-tsv)
use a copy exported by Anki and preserve original identities. Users with modified
note schemas can continue TSV updates.

Anki controls updates to notes and note types separately. **If newer** for notes
can replace edits made only in Anki when the export is newer; **Never** preserves
those edits but blocks content updates. **If newer** for note types retains newer
custom CSS and templates, while **Always** can replace them. Keep personal
translations in the Cambridge collection if they must survive future exports.

Anki compatibility checks cover repeated imports, content/audio updates,
import-option behaviour and migration from TSV without duplicate cards or lost
review history. See [Anki compatibility](docs/collection.md#anki-compatibility).

## Browser extension

A small TypeScript extension for Chrome and Firefox downloads audio from the open
Cambridge Dictionary page. Choose US or UK; when a page has multiple entries or
pronunciation variants, choose the recording. The gear button selects English or
Russian and system, light or dark appearance. Preferences are remembered locally.

The extension needs neither Python nor the desktop app. Downloads use the browser's
normal destination and file-chooser preferences. It reads the page only when opened
and leaves translations, a recording library and phrase synthesis to the application.
See [extension installation and development](extension/README.md) for build commands,
developer installation, permissions and privacy. Releases include Chrome and Firefox
ZIP archives; CI also provides them as the `browser-extensions` artifact.

## CLI quick start

The PyPI package contains only the CLI, without Qt or GUI modules:

```sh
uv tool install cambridge-dictionary-audio
cambridge-audio hello
```

Alternatively, use `pipx install cambridge-dictionary-audio` or pip inside a virtual
environment. See the [CLI package documentation](docs/cli.md).

### Run from source

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) 0.13.0 or newer,
then run these commands in the project directory:

```sh
uv sync --locked
uv run -m cambridge_audio hello
```

This saves `downloads/hello.us.mp3` relative to the current working directory
and prints the US transcription and first English definition.
**US pronunciation and English interface are the defaults.**
Responses are checked for an MP3 signature, written to a temporary file, and
published only after the write completes.
Existing files are preserved unless you pass `--overwrite`.

## Usage

```sh
uv run -m cambridge_audio hello --accent uk
uv run -m cambridge_audio "good morning" --accent both --output-dir audio
uv run -m cambridge_audio hello --play --overwrite
uv run -m cambridge_audio hello --translation russian
uv run -m cambridge_audio hello --lang ru
uv run -m cambridge_audio --lang ru --help
```

- `--accent us|uk|both`: select pronunciation; filenames include `.us` or `.uk`.
- `--output-dir PATH`: select the destination directory; default: `downloads/` in the
  current working directory. The directory is created if necessary.
- `--lang en|ru`: select the interface language, including help and application messages.
- `--translation russian`: enable Russian translations; `ru` and `русский` are aliases.
  Other target languages are rejected.
  Translation is disabled by default and independent of the interface language.
- `--play` / `--no-play`: enable or disable playback.
- `--combine` / `--no-combine`: enable or disable synthesis of missing phrases.
- `--overwrite`: replace existing recordings.
- `--timeout SECONDS`: set the timeout for each HTTP request; default: 15 seconds.
- `--help`: display all options.

Words and phrases are case-insensitive. Phrases can be quoted or passed as separate
arguments. Apostrophes and hyphens are supported; URLs and path separators are rejected.
Windows device names receive a leading underscore on all platforms, e.g. `con` is
saved as `_con.us.mp3`.

A failed lookup or download exits with status 1 and reports the error.
Invalid CLI arguments exit with status 2. Failed playback or an optional translation
request does not invalidate a successful download. With `--accent both`, a successful
first recording is retained if the second download fails.

## Terminal workspace

Omit the word in an interactive terminal to open the workspace:

```sh
uv run -m cambridge_audio
uv run -m cambridge_audio --lang ru --no-play --translation russian
```

The workspace shows a searchable library and recording details side by side.
On narrower terminals the panels stack vertically. It supports keyboard navigation,
mouse input, background downloads and playback, and an English or Russian interface.
Search filters the saved library as you type. Enter downloads the word or opens
existing audio offline; with both accents selected, only missing recordings are
downloaded. **Download again** asks before replacing an existing recording.

- **Enter** in search: find meanings or open saved audio; in the library: play the selected recording.
- **Tab / Shift+Tab**: move between controls; **Up / Down**: navigate the library.
- **Ctrl+L**: search; **Ctrl+P**: play/stop; **Ctrl+R**: refresh the library.
- **Ctrl+S**: settings; **F1**: help; **F2**: About; **Ctrl+Q**: quit.
- **Ctrl+C**: cancel a download, stop playback or quit when idle. An in-flight request finishes
  before cancellation; completed files are kept.

All commands also have shortcuts independent of the keyboard layout: **F3** search,
**F4** play/stop, **F5** refresh, **F6** settings, **F7** export, **F8** translation,
**F9** WikDict, **F10** meanings, **F11** cancel, **F12** quit.
Ctrl shortcuts accept Russian and Ukrainian letters at the same key positions.
If the terminal does not report Ctrl with non-Latin letters, use the function keys.

The translation panel groups dictionary senses without technical IDs and shows a
Ctrl+T hint for choosing a meaning. **F2** or **About** in Help opens the application
version, repository link and license information.

Settings include interface language, light/dark appearance, accent, destination,
a Russian translation toggle, autoplay and phrase synthesis. Applying settings saves
them for future TUI launches; explicit CLI flags override saved values for that run.
The translation checkbox also saves its state. The checkbox shows or
hides Russian translations immediately, using cache or fetching a missing result
without downloading the MP3 again. English definitions remain visible when
translation is off. Interface language can be English or Russian independently.
Loading and errors appear in the recording panel. JSON sidecars remain shared with
the GUI. Existing foreign-language caches and personal edits are preserved without
relabeling. Old sidecars without a translation language are treated as unknown.
Older MP3s without sidecars remain playable; empty files are excluded from the
library. Symlink aliases retain their own accent, filename and sidecar.

Playback and phrase synthesis are enabled by default in interactive mode.
US pronunciation and English remain the defaults. The workspace uses Textual and
does not require Qt, a graphical desktop or a special icon font.

Use `--plain` for the original line-based prompt and undecorated output. It is also
selected automatically when input or output is redirected or `TERM=dumb`.
The plain prompt accepts `/m` to toggle playback, `/r` to remove this session's
downloads and their sidecars, and `/q` to quit. Use `--tui` to require an interactive
terminal explicitly. `--version` prints the installed version. Single-word commands
retain their exit codes and print plain text when redirected; terminal output adds
a download indicator and a definition card. `NO_COLOR` disables colours.

## Playback and FFmpeg

Downloading original recordings does not require FFmpeg or an audio player.
CLI playback uses the default audio application on Windows, `afplay` on macOS,
and `ffplay` on Linux. On Windows, control playback in the external application;
the terminal's Stop action cannot close or stop that application. The GUI uses Qt Multimedia. Both require a working audio environment.

If Cambridge has no recording of a phrase, enable synthesis from individual words:

```sh
uv run -m cambridge_audio "hello friendly world" --combine
```

For source launches and the PyPI CLI, synthesis requires
[FFmpeg](https://ffmpeg.org/download.html) with the `libmp3lame`
encoder in `PATH`. It runs only when the entry or requested pronunciation is absent,
not after network failures. Every word must have a recording in the selected accent.
Temporary files are isolated and cleaned up without affecting existing downloads.
The output is concatenated and loudness-normalized; it is not a Cambridge recording
of the complete phrase. `ffprobe` is useful for inspection but is not a runtime dependency.

## Python versions

Python **3.10 through 3.15** are supported. Dependencies and source syntax support
3.10; `requires-python` in `pyproject.toml` defines the supported version range.

`.python-version` selects **3.15** as the development default, so uv can install it
when needed. It does not restrict support to 3.15 or pin a specific patch release.
To use an older supported interpreter, override the default explicitly:

```sh
uv sync --locked --python 3.10
uv run --python 3.10 -m cambridge_audio hello
```

Keep the same `--python` selection when running commands in that environment.
When PyYAML needs a source build, the project's uv configuration disables its
optional C extension. Running `uv sync` on Windows with Python 3.15 therefore does
not require Visual C++ Build Tools; Anki export works with the Python implementation.

## Development

See [Contributing](CONTRIBUTING.md) for source setup, checks, dependency updates,
repository structure and release packaging. The [documentation index](docs/README.md)
links the interface guides and technical specifications.

```sh
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
```

Desktop tests use `uv run --locked --group gui pytest`.
Mobile and extension toolchains are documented in their
[build guides](docs/README.md#building-and-contributing).

## Project layout

- `cambridge_audio/`: shared Python services, CLI, terminal workspace and desktop GUI.
- `mobile/`: shared Kotlin core, Android and iOS applications, and native audio library.
- `extension/`: Chrome/Firefox extension, TypeScript tests and browser bundles.
- `contracts/`: shared compatibility fixtures and Anki identities.
- `tests/`: Python tests for application behaviour and packaging.
- `scripts/` and `packaging/`: build tools, installer templates and release validation.
- `docs/`: user guides, contributor documentation and format specifications.

## License

This fork is distributed under the [Apache License 2.0](LICENSE).
It is based on [astrosander/cambridge-dictionary-audio](https://github.com/astrosander/cambridge-dictionary-audio).
Material inherited from the original project retains its [MIT license](LICENSE-MIT)
and copyright notice. See [NOTICE](NOTICE) for attribution.

PySide6/Qt and the multimedia libraries retain their own licenses. GUI distribution
must preserve their notices and satisfy the applicable Qt licensing terms; the
project's Apache-2.0 license does not replace dependency licenses.

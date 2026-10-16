<p align="center">
  <img src="assets/icon.svg" width="120" alt="Cambridge Dictionary Audio icon">
</p>

# Cambridge Dictionary Audio

[![Checks](https://img.shields.io/github/actions/workflow/status/0then0/cambridge-dictionary-audio/checks.yml?branch=main&label=checks)](https://github.com/0then0/cambridge-dictionary-audio/actions/workflows/checks.yml)
[![Python](https://img.shields.io/badge/Python-3.10%E2%80%933.15-3776AB?logo=python&logoColor=white)](#python-versions)
[![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20macOS%20%7C%20Linux-blue)](#playback-and-ffmpeg)
[![uv](https://img.shields.io/badge/dependencies-uv-DE5FE9)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/badge/lint%20%26%20format-Ruff-D7FF64)](https://docs.astral.sh/ruff/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

[![Release](https://img.shields.io/github/v/release/0then0/cambridge-dictionary-audio)](https://github.com/0then0/cambridge-dictionary-audio/releases/latest)
[![PyPI](https://img.shields.io/pypi/v/cambridge-dictionary-audio)](https://pypi.org/project/cambridge-dictionary-audio/)

[Russian documentation](README.ru.md) · [Changelog](CHANGELOG.md)

Download English pronunciation recordings from
[Cambridge Dictionary](https://dictionary.cambridge.org/) as MP3 files.
A desktop app and CLI provide US and UK audio, IPA transcriptions, English
definitions and optional dictionary translations.

## Desktop app

<!-- downloads:start -->
Direct downloads for the latest verified stable release **v0.3.0**:

| Platform | Architecture | Download |
| --- | --- | --- |
| Windows 10+ | x86-64 | [![Windows 10+ x86-64 EXE](https://img.shields.io/badge/EXE-0078D4?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xIDFoMTB2MTBIMXpNMTMgMWgxMHYxMEgxM3pNMSAxM2gxMHYxMEgxek0xMyAxM2gxMHYxMEgxM3oiLz48L3N2Zz4%3D&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-windows-x86_64-setup.exe) [![Windows 10+ x86-64 Portable ZIP](https://img.shields.io/badge/Portable%20ZIP-0078D4?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xIDFoMTB2MTBIMXpNMTMgMWgxMHYxMEgxM3pNMSAxM2gxMHYxMEgxek0xMyAxM2gxMHYxMEgxM3oiLz48L3N2Zz4%3D&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-windows-x86_64-portable.zip) |
| macOS 14+ | Apple Silicon (arm64) | [![macOS 14+ Apple Silicon (arm64) PKG](https://img.shields.io/badge/PKG-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-macos-arm64.pkg) [![macOS 14+ Apple Silicon (arm64) DMG](https://img.shields.io/badge/DMG-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-macos-arm64.dmg) [![macOS 14+ Apple Silicon (arm64) TAR.GZ](https://img.shields.io/badge/TAR.GZ-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-macos-arm64.tar.gz) |
| macOS 14+ | Intel (x86-64) | [![macOS 14+ Intel (x86-64) PKG](https://img.shields.io/badge/PKG-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-macos-x86_64.pkg) [![macOS 14+ Intel (x86-64) DMG](https://img.shields.io/badge/DMG-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-macos-x86_64.dmg) [![macOS 14+ Intel (x86-64) TAR.GZ](https://img.shields.io/badge/TAR.GZ-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-macos-x86_64.tar.gz) |
| Linux | x86-64 · glibc 2.34+ | [![Linux x86-64 · glibc 2.34+ DEB](https://img.shields.io/badge/DEB-FCC624?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio_0.3.0_amd64.deb) [![Linux x86-64 · glibc 2.34+ RPM](https://img.shields.io/badge/RPM-FCC624?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-1.x86_64.rpm) [![Linux x86-64 · glibc 2.34+ Portable TAR.GZ](https://img.shields.io/badge/Portable%20TAR.GZ-FCC624?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-linux-x86_64-portable.tar.gz) |
| Python CLI | Any | [![Python CLI Any WHL](https://img.shields.io/badge/WHL-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge_dictionary_audio-0.3.0-py3-none-any.whl) [![Python CLI Any Source TAR.GZ](https://img.shields.io/badge/Source%20TAR.GZ-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge_dictionary_audio-0.3.0.tar.gz) |
| Chrome | Any | [![Chrome Any ZIP](https://img.shields.io/badge/ZIP-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-audio-chrome-0.3.0.zip) |
| Firefox | Any | [![Firefox Any ZIP](https://img.shields.io/badge/ZIP-FF7139?style=for-the-badge&logo=firefoxbrowser&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-audio-firefox-0.3.0.zip) |

[![SHA-256](https://img.shields.io/badge/SHA--256-SHA256SUMS.txt-555555?style=flat-square)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/SHA256SUMS.txt)
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

Each format button downloads its file directly, without opening the release page.
Buttons are pinned to the verified stable version shown above because release
asset names include version numbers. After publishing a new stable release, run
`uv run --no-sync python scripts/download_links.py --refresh --verify-network`
to update both tables and verify the downloads.

### Run from source

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) 0.13.0 or newer,
then run these commands in the project directory:

```sh
uv sync --locked --group gui
uv run --group gui -m cambridge_audio.gui
```

Enter a word or phrase and click **Download** (or press Enter). The recording,
transcription and definition appear below. Click **Play** to listen in the window,
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
- New GUI downloads save pronunciation details and translations in a matching
  JSON file beside the MP3. Older recordings remain playable without that file.
  **Show Russian translation** shows or hides a cached translation immediately.
  When it is missing, the app fetches it in the background without downloading
  audio again. Loading and errors appear in the recording panel; toggle the
  checkbox off and on to retry a failed request.
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

See the [collection guide](docs/collection.md) for pronunciation selection,
Russian translations, local WikDict installation and Anki export in the GUI, TUI
and CLI. [Data sources and licenses](docs/data-sources.md) covers dictionary
attribution and licensing separately from the application code.

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

- **Enter** in search: download or open saved audio; in the library: play the selected recording.
- **Tab / Shift+Tab**: move between controls; **Up / Down**: navigate the library.
- **Ctrl+L**: search; **Ctrl+P**: play/stop; **Ctrl+R**: refresh the library.
- **Ctrl+S**: settings; **F1**: help; **F2**: About; **Ctrl+Q**: quit.
- **Ctrl+C**: cancel a download, stop playback or quit when idle. An in-flight request finishes
  before cancellation; completed files are kept.

All commands also have shortcuts independent of the keyboard layout: **F3** search,
**F4** play/stop, **F5** refresh, **F6** settings, **F7** export, **F8** translation,
**F9** WikDict, **F10** pronunciation, **F11** cancel, **F12** quit.
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

## Development

Dependencies are declared in `pyproject.toml` and resolved in `uv.lock`.
The minimal toolset is uv, Ruff (linting, import sorting, formatting), and pytest.
CI uses uv 0.13.1 and covers all six Python versions on Linux, plus Python 3.10 and
3.15 on Windows and macOS. Jobs with GUI dependencies run the full suite on Python
3.10 and 3.15 on all three OSes, plus Python 3.11 and 3.12 on Linux.

```sh
uv sync --locked
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run --isolated --locked pytest
```

Automated tests use local HTML fragments and mocked HTTP responses, without network
access. They cover downloads, cancellation, cache recovery, translation language,
keyboard interaction, GUI settings and release packaging. FFmpeg-dependent integration tests run when both `ffmpeg` and `ffprobe` are
available and otherwise report a skip. Update dependencies explicitly with
`uv lock --upgrade`, then run the checks above.

To run without development tools, use `uv run --no-dev -m cambridge_audio hello`.

To include desktop tests, run `uv run --locked --group gui pytest`.
On Linux with Python 3.10 or 3.11, the lockfile selects Qt 6.11.2 for runtime
compatibility; other environments use Qt 6.12. The suite checks normal process
termination after repeated scrollbar painting, as well as widget behavior.
GUI tests use an offscreen Qt platform, temporary settings and mocked HTTP responses.
The [desktop design system](docs/design.md) documents layout, appearance and behavior.

Browser extension development uses a separate npm lockfile in `extension/`.
Node.js 24.15+ provides the TypeScript compiler and DOM tests; CI checks it on all
three OSes and validates the Firefox bundle with Mozilla's `web-ext` tool. The npm
tools are not required for Python CLI or GUI development.

## Project layout

- `cambridge_audio/dictionary.py`: dictionary entries, HTML parsing, HTTP requests and MP3 saving.
- `cambridge_audio/audio.py`: phrase synthesis and platform-specific playback.
- `cambridge_audio/cli.py`: command-line options, one-shot downloads and the plain prompt.
- `cambridge_audio/terminal/`: terminal workspace, settings and background tasks.
- `cambridge_audio/console.py`: formatted terminal output and plain fallback.
- `cambridge_audio/service.py`: download workflow shared by both interfaces.
- `cambridge_audio/gui/`: desktop window, download/translation workers and in-window playback.
- `cambridge_audio/gui/theme.py`: light/dark design tokens and Qt styling.
- `cambridge_audio/gui/preferences.py`: language and appearance settings.
- `cambridge_audio/library.py`: saved recordings and optional JSON details.
- `cambridge_audio/i18n.py`: English and Russian interface messages.
- `assets/icon.svg`: editable vector icon; `assets/icon.ico` is its Windows export.
- `extension/`: TypeScript browser popup, browser manifests, DOM tests and build scripts.
- `tests/`: grouped core, CLI, GUI, terminal and packaging tests, with shared helpers.
- `scripts/` and `packaging/`: release validation, native bundle builders and installer templates.

The application runs as `python -m cambridge_audio`. The root `main.py` remains a
compatibility launcher, so existing `uv run main.py` commands continue to work.

On Windows, `start.bat` runs the interactive CLI through uv.
`compile.bat` builds the Windows desktop app and installer; it needs Inno Setup.
Native builds use the locked `gui` and `release` dependency groups. Build them on
the target platform: first `scripts/build_ffmpeg.py`, then `scripts/build_desktop.py`
and `scripts/package_desktop.py`. See the [FFmpeg build instructions](packaging/ffmpeg-build.md)
for compiler requirements and rebuilding the LGPL components.
Generated files are placed in `dist/`. Qt shared libraries and dependency license
notices remain separate inside the application bundle.

## License

This fork is distributed under the [Apache License 2.0](LICENSE).
It is based on [astrosander/cambridge-dictionary-audio](https://github.com/astrosander/cambridge-dictionary-audio).
Material inherited from the original project retains its [MIT license](LICENSE-MIT)
and copyright notice. See [NOTICE](NOTICE) for attribution.

PySide6/Qt and the multimedia libraries retain their own licenses. GUI distribution
must preserve their notices and satisfy the applicable Qt licensing terms; the
project's Apache-2.0 license does not replace dependency licenses.

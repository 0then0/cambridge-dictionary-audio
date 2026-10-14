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

## Terminal workspace

The workspace has a searchable library and a recording detail panel. Narrow
terminals use a vertical layout. Enter in search downloads a word or opens saved
audio offline; Enter in the library plays the selected recording. Selecting both
accents downloads only missing files. **Download again** asks before replacing audio.
Downloads and playback run in the background so navigation remains responsive.

- **Tab / Shift+Tab**: navigate controls; **Up / Down**: select a recording.
- **Ctrl+L**: search; **Ctrl+P**: play/stop; **Ctrl+R**: refresh the library.
- **Ctrl+S**: settings; **F1**: help; **Ctrl+Q**: quit.
- **Ctrl+C**: cancel the download, stop playback or quit when idle. The current request finishes
  before cancellation, and completed files are retained.

Settings offer English/Russian interface messages, light/dark themes, accent,
destination, translation language, autoplay and phrase synthesis. They apply to
the current session; use CLI flags for future launches. The translation checkbox
shows and hides cached translations immediately. When missing, a translation is
fetched in the background and cached without downloading audio again. Russian is
the default translation language; settings or `--translation` override it. The
recording panel shows loading and request errors. Metadata is stored in JSON files
beside MP3s and is shared with the desktop app. Existing MP3s without metadata are
also recognized. Empty files are ignored. Translation metadata includes its language:
changing languages refreshes the translation. Older metadata without a language is
refetched when translation is enabled. Audio is retained throughout this operation.

`--plain` uses undecorated output and a line-based interactive prompt with `/m`
(toggle playback), `/r` (delete this session's downloads and metadata), and `/q`
(quit). This fallback is automatic for redirected input/output and `TERM=dumb`.
`--tui` requires an interactive terminal explicitly. `--version` prints the installed
version. `NO_COLOR` disables colours. One-shot commands retain plain output in
pipes and add a download indicator and definition card in a terminal.

Textual provides the terminal interface without Qt, a graphical display server or
special fonts. The same package supports Windows, macOS and Linux.

FFmpeg is optional and required only for combining a phrase from individual word
recordings. CLI playback uses `afplay` on macOS, `ffplay` on Linux, and the Windows
default audio application on Windows. The terminal can stop its player on macOS
and Linux; on Windows, use the external application to stop playback. Playback is enabled by default in interactive mode and can
be requested for a single download with `--play`.

## License and attribution

This fork is distributed under Apache-2.0. Code inherited from
[astrosander/cambridge-dictionary-audio](https://github.com/astrosander/cambridge-dictionary-audio)
retains its MIT license and copyright notice. The distribution includes both
licenses and the attribution notice.

The project is independent of Cambridge University Press & Assessment.
Downloaded recordings remain subject to their owners' rights and Cambridge's
[website terms](https://dictionary.cambridge.org/terms-of-use).

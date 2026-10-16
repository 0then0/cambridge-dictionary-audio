# Changelog

User-visible changes are listed newest first. Unreleased changes describe the
current source tree and may not be available in published downloads. Historical
entries were reconstructed from Git history and project development discussions;
release dates are included only where a published release can be verified.

## 0.3.0 (Unreleased)

### Added

- Shared pronunciation selection in the CLI, TUI and GUI, keeping the Cambridge
  entry, part of speech, definition, IPA and audio together. Multiple meanings
  and US/UK pronunciations can be saved separately with stable recording IDs and
  portable filenames. The CLI supports `--list-variants` and `--variant`.
- Russian translation lookup using personal edits, saved cache, Cambridge and an
  installed local WikDict fallback. Results retain their source and sense
  alignment; missing results, network failures, blocking and dictionary problems
  have separate statuses. Translation failure does not prevent audio downloads.
- Translation editing, reset and source-sense selection in all three interfaces.
  Personal edits survive restart and redownload and are shared by pronunciations
  of the same sense. JSON v2 retains language, source and provenance while reading
  legacy JSON, standalone MP3s and symlink aliases without renaming files.
- Explicit installation of the WikDict English → Russian SQLite package
  (`2_2026-06`, 20.9 MB), with version and license information, size, SHA-256 and
  SQLite validation, and atomic replacement. Interrupted installation preserves
  the existing dictionary; installed lookups work offline without an API key.
- Anki export of selected recordings or the whole collection as UTF-8 TSV with
  flat MP3 media, stable IDs, import instructions and source/license notices.
  Export preserves originals and reports inaccessible audio and unresolved
  translation choices.
- About dialogs in GUI Settings and TUI Help (`F2`), showing the installed
  application version, repository link and license information.
- Restoration of the desktop window's size, position and maximized state,
  including recovery when the previous monitor is unavailable.
- Direct platform-specific download links in both READMEs and a script to refresh
  them from the latest published stable GitHub release and verify the URLs.

### Changed

- Translation controls now explicitly enable Russian translations of English
  words. The free-form language field was removed; CLI aliases `russian`, `ru`
  and `русский` are accepted, and other languages are rejected before network
  access. Existing foreign-language caches and edits are preserved. The English
  or Russian interface language remains an independent setting.
- GUI and TUI translation panels use readable senses and localized parts of
  speech instead of internal hashes and empty sense placeholders.
- Desktop scrollbars have rounded handles that expand on hover within a fixed
  hit area, inspired by Zen Browser's GTK scrollbar behavior. Discrete wheel
  scrolling is animated; precise scrolling and direct dragging remain immediate.
- The WikDict button explains the dictionary's purpose, displays readable package
  sizes and checks the installed package before offering a confirmed redownload.
- Release-specific feature lists now live in this changelog; README files link
  to usage guides and the change history.

### Fixed

- TUI resizing updates the main layout even while Settings, Help or About is open,
  keeping recording controls visible after the dialog closes.
- Linux with Python 3.10 or 3.11 uses compatible Qt 6.11.2 wheels to prevent
  singleton reference corruption and crashes during interpreter shutdown.
  GUI CI runs the full core/terminal/Qt suite together; a subprocess regression
  checks normal exit after repeated scrollbar painting.
- README download-link updates explicitly use UTF-8 on Windows and other
  platforms, preserving Russian documentation regardless of the system locale.
- TUI button widths are recalculated after language changes and playback state
  changes, keeping translated labels fully visible.
- Closing the desktop window during WikDict installation exits the application
  after cancellation and completion of the remaining workers.
- Clipped selection menus and unnecessary popup scrolling at normal Windows
  scale, and an Anki export dialog too small to show both scope options.
- TUI keyboard handling for Russian and Ukrainian layouts, with function-key
  alternatives for commands across layouts and localized shortcut help.
- GUI redownload targeting an unrelated saved recording when downloading a new
  word; replacement now validates the selected word and accent.
- Cambridge translation parsing and sense matching, avoiding unrelated parts of
  speech and preserving uncertainty when source definitions differ.
- Legacy personal translations losing their source or leaking into another
  meaning after redownload; reset and inheritance respect sense and language.
- TUI downloads with both accents stopping after finding an existing US variant
  instead of downloading the missing UK recording.
- Background TUI updates targeting an open modal or disposed screen.

See the [collection guide](docs/collection.md) and
[data sources and licenses](docs/data-sources.md) for usage and compatibility.

## 0.2.1 (2026-10-15)

### Fixed

- Windows release builds explicitly select MSYS Bash for FFmpeg and LAME
  configuration, preventing Windows from launching WSL's `bash.exe` instead.

This is the first release currently available on GitHub. It includes the desktop,
CLI and browser extension work developed under version 0.2.0 below.

[Release and downloads](https://github.com/0then0/cambridge-dictionary-audio/releases/tag/v0.2.1)
· [Build fix](https://github.com/0then0/cambridge-dictionary-audio/commit/e952fda7ae69d72b3b9c1299414807642c624c87)

## 0.2.0 (development history, 2026-10-15)

The source tree used this version before 0.2.1. No separate published 0.2.0
release is currently available on GitHub; the date here is the commit date.

### Added

- PySide6 desktop app with embedded audio playback, saved-recording browsing,
  background downloads and confirmation before replacing audio.
- Textual terminal workspace and a separately installable Python CLI package,
  supporting Python 3.10–3.15 without a Qt dependency in the CLI distribution.
- English and Russian interfaces, system/light/dark appearance, persistent
  settings, custom GUI background and accent colors, and adaptive icons.
- IPA, English definitions and dictionary translations stored alongside MP3s in
  language-aware JSON metadata. Existing recordings can be reopened and played
  offline, and cached translations can be shown without downloading audio again.
- Standalone TypeScript extensions for Chrome and Firefox, downloading US/UK
  pronunciation from the open Cambridge page with entry/variant selection and
  saved language and appearance preferences.
- Native installers and portable desktop bundles for Windows x86-64, macOS
  Apple Silicon/Intel and Linux x86-64, with a minimal bundled FFmpeg/LAME,
  corresponding source and license notices, Python distributions and checksums.
- Locked uv environments, Ruff, regression tests, cross-platform CI, browser
  extension Biome/TypeScript checks and automated release packaging.

### Changed

- Replaced the original scripts with a shared Python package for dictionary
  lookup, audio processing, recording metadata and application interfaces.
- Modernized the Cambridge parser and phrase synthesis, and made audio and
  metadata writes atomic.
- Documented Apache-2.0 licensing for the current code and retained MIT notices
  for the original project.

### Fixed

- Concurrent metadata reads blocking atomic JSON replacement on Windows.
- Platform-specific path and permission assertions and timing-dependent terminal
  tests in cross-platform CI.
- Browser extension line-ending consistency on Windows.

[Source history](https://github.com/0then0/cambridge-dictionary-audio/compare/6d917aa45af0c0c424d6fb465bc2c5067fba5f07...c53fc54)

## Earlier unversioned history (2023–2024)

These milestones use commit dates, not release dates.

- **2024-07-20:** added macOS support to the original launcher
  ([commit](https://github.com/0then0/cambridge-dictionary-audio/commit/6d917aa45af0c0c424d6fb465bc2c5067fba5f07)).
- **2023-08-20–21:** added word definitions and corrected definition mode
  ([feature](https://github.com/0then0/cambridge-dictionary-audio/commit/fa5d81d),
  [fix](https://github.com/0then0/cambridge-dictionary-audio/commit/bf4497397d89c96d655bc8d105c4a4d7bd816bfc)).
- **2023-07-22:** added combining individual word recordings into phrase audio
  ([commit](https://github.com/0then0/cambridge-dictionary-audio/commit/30a0b46bef0b1006d6697bc9365135cf79fb2619)).
- **2023-06-11:** initial Python scripts for downloading Cambridge Dictionary audio
  ([commit](https://github.com/0then0/cambridge-dictionary-audio/commit/ab4875a)).

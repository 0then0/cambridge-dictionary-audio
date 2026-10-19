# Changelog

User-visible changes are listed newest first. Unreleased changes describe the
current source tree and may not be available in published downloads. Historical
entries were reconstructed from Git history and project development discussions;
release dates are included only where a published release can be verified.

## Unreleased

### 1.0 development (not released; acceptance incomplete)

- Fix Windows collection transfer flushes by using writable file handles, correct
  the pinned Gradle distribution checksum, and stop requesting the removed Android
  SDK `tools` package in mobile build/signing workflows. Enable Debug testability
  for the iOS application module used by XCTest.
- Keep collection identities intact when accepting incoming records: retire only
  unreferenced media of replaced entries, retain shared audio and independent MP3s,
  and allow verified backups to restore missing or corrupt local audio.
- Restore synthesized phrases with their saved pronunciation plan and selections,
  preserving personal translations and the permanent ID without a new word lookup.
- Verify local WikDict status in mobile Settings and before installation; distinguish
  missing, verified and damaged packages and ask explicitly before downloading again.
  Keep verification off the UI thread and preserve the existing package on failure.
- Show three translation choices initially on Android and iOS, with expandable
  alternatives that collapse after selection; keep the chosen translation visible.
- Fit the Android shield inside the adaptive icon's safe circle so launcher,
  app-info and system splash masks no longer crop its top corners.
- Replace the cramped Android license alert with a full-screen reader, component
  summaries and separate offline Apache/MIT/NOTICE documents. Reflow printed text
  into readable paragraphs without changing bundled licenses. Structure iOS
  license information into native sections and expandable full texts.
- Show three compact search meanings initially, with expandable alternatives that
  collapse after selection. Open saved word details inside Collection, retaining
  the Search selection and unsaved translation draft on return.
- Add an independent pure-black OLED switch for the active dark theme, including
  system appearance, and migrate the former standalone black mode without resetting
  preferences. Keep the desktop red accent on Android and iOS.
- Apply Android manual accents to the complete colour scheme, including selected
  chips, switches, navigation and surfaces, instead of retaining Material's default
  purple roles. Distinguish the active system palette from manual colour selection.
  Adapt iOS accent colours for light and dark appearance.
- Prepare playback inline instead of briefly inserting the global operation toolbar.
- Pin ktfmt and official swift-format with shared mobile settings, source checks
  before builds/signing, cached verified tools and locked Swift formatter dependencies.

- Add standalone Kotlin Multiplatform business logic, Android Compose Material 3
  presentation and native iOS SwiftUI presentation. Implement Cambridge search,
  pronunciation choice, persistent collections, personal/dictionary translations,
  explicit WikDict installation, native playback and independent APKG/TSV export.
- Build real MP3 phrases on device using platform decoders and pinned source-built
  LAME. Supply source/build/relink materials alongside mobile artifacts.
- Add versioned, checksummed `.cda` collection transfer to desktop GUI/CLI and
  mobile, explicit conflict decisions, stale-preview protection, staged import,
  retained backups and recovery. Preserve unknown sidecar/cache fields on edits.
- Add shared Python/Kotlin fixtures and Anki identity contracts. Verify real Anki
  scheduler history across Python/Kotlin and Android exports; distinguish these
  checks from unperformed iOS runtime acceptance.
- Add Android/iOS CI and protected owner-signing workflows. Keep GitHub release
  independent of optional PyPI publication; restore the existing PyPI job behind
  an explicit manual `publish_pypi` input, default false.
- Document installation/signing limits, storage migration and measured acceptance.
  Mobile builds remain 1.0.0-dev. Python and extensions remain 0.4.2; iOS full build,
  device signing and accessibility gates have not passed on this host.

## 0.4.2 (2026-10-19)

- Collapse sources and license attribution under a small Source disclosure on
  Anki cards and the deck overview. With note updates enabled, reimporting a fresh
  package updates Source even when Anki retains an older template and custom styling.

- Restore GUI translation actions after saving a meaning, so unresolved phrases
  such as `good morning` can be translated and exported to Anki without restarting.

- Verify an Anki 26.09.3 backend round-trip on macOS, including scheduler-created
  review history, repeated imports, content and media updates, custom note/template
  edits and a transition from actual TSV imports. Document how note and note-type
  import options control replacement of personal contents, CSS and templates.

## 0.4.1 (2026-10-18)

- Resolve Russian translations against the selected English definition and part
  of speech, including conservative matching of differently worded definitions.
  GUI/TUI show the matched translation before saving and keep unrelated source
  senses behind an optional picker. Translation choice and editing also work
  before saving; the preview is saved without another translation request.
- Avoid confirming verb paraphrases from word overlap, preserve prepared
  translations when their display is disabled, and apply new personal drafts
  over inherited source choices without overwriting newer edits. Prefer explicit
  and resolved cached translations over unmatched sources; old unresolved
  Cambridge caches can use installed WikDict without another network request.
- Reuse resolved translations and explicit choices across pronunciations of one
  meaning, re-evaluate old gloss-bearing caches on read, and preserve personal
  choices against late dictionary responses.

## 0.4.0 (2026-10-17)

- Allow `uv sync` on Windows with Python 3.15 without Visual C++ Build Tools by
  disabling PyYAML's optional C extension for source builds. Windows CI verifies
  this fallback explicitly.

- Close Anki reference databases before temporary-file cleanup on Windows, and
  account for the actual viewport when sizing short GUI choice lists.

- Keep GUI meaning selection tied to its search, restore saved accents after failed
  downloads, and refresh translation edits for the currently displayed meaning.
- Retain legacy collection metadata paths when replacing audio; old media stays on
  disk without adding duplicate collection entries. Audio downloads no longer hold
  the metadata lock, so collection reads remain available during network requests.

- GUI and TUI errors use localized, actionable summaries. Original diagnostics,
  including cached translation failures and exception causes, are available only
  through Technical details. CLI diagnostic output is unchanged.

- Separate collection meanings from shared audio, with permanent local identities,
  source IDs, checksum verification and repair of missing or damaged MP3s.
  Existing IDs, translations and files remain compatible; legacy metadata upgrades
  atomically on save without removing old duplicate media.
- Select meanings inline in GUI/TUI, preview before saving, and choose another
  pronunciation only when audio alternatives exist for the selected accent.
  CLI supports separate meaning/audio selection and disposable preview.
- Export ready Anki `.apkg` packages with stable GUIDs, a single light/dark template,
  shared media and source/license attribution. TSV remains available. Explicit TSV
  transition reads original GUIDs and note types from an Anki-exported package;
  real Anki import and review-history retention had not yet been tested at this
  release. See the current [verification results](docs/collection.md#verified-anki-round-trip).

## 0.3.0 (2026-10-16)

### Added

- TUI settings persist across launches: interface language, theme, accent,
  destination, autoplay, phrase synthesis and Russian translation visibility.
  Explicit CLI flags override saved preferences; cancelled dialogs do not save.
- Cambridge requests share a one-second interval within each process. HTTP 429
  responses honor `Retry-After` and use at most two retries with exponential
  backoff and jitter otherwise. Long server cooldowns are reported without
  blocking the interface; GUI/TUI waits can be cancelled.
- Each Cambridge client reuses up to 64 successful HTML pages. Explicit audio
  redownloads still fetch fresh MP3 data.
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
- Platform download tables in both READMEs with Shields.io format buttons that
  download each verified stable release asset directly, including a custom
  Windows icon. A script refreshes pinned URLs and validates the release assets.

### Changed

- GUI and TUI code is grouped into packages with separate workers, dialogs,
  rendering and settings modules; terminal styles live in a packaged TCSS file.
  Existing CLI and GUI launch commands are preserved. Tests are grouped by
  interface and behavior, sharing HTTP helpers without cross-test imports.
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

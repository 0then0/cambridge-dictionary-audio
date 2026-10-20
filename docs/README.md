# Documentation

Cambridge Dictionary Audio downloads English pronunciation recordings, keeps a
local collection and exports study material to Anki. Choose the guide for the
interface you use or the part of the project you want to change.

## Using the applications

- [Desktop app and quick start](../README.md): installation, playback and appearance.
- [Руководство на русском](../README.ru.md): установка и работа с приложением.
- [Command-line and terminal interfaces](cli.md): commands, shortcuts and examples.
- [Collection, translations and Anki](collection.md): meanings, saved recordings,
  Russian translations, offline dictionaries, backups and export.
- [Android and iOS](mobile/README.md): search, collection management and settings.
- [Browser extension](../extension/README.md): installation and pronunciation downloads
  from the current Cambridge Dictionary page.
- [Dictionary sources and licenses](data-sources.md): attribution, data provenance
  and the WikDict package used for offline translation.

## Building and contributing

- [Contributing](../CONTRIBUTING.md): source setup, project structure, checks,
  dependency updates and release packaging.
- [Desktop interface design](design.md): layout, colours, interaction and accessibility.
- [Mobile builds and signing](mobile/install.md): toolchains, artifacts and installation.
- [Mobile testing](mobile/readiness.md): automated suites and release checks.
- [Collection storage format](mobile/storage.md): identities, metadata, `.cda`
  archives, conflict handling and recovery.
- [Shared compatibility fixtures](../contracts/README.md): Python/Kotlin and Anki contracts.
- [Rebuilding FFmpeg](../packaging/ffmpeg-build.md): desktop audio components and
  the matching source materials shipped with releases.

## Versions

Repository documentation follows `main`. The [changelog](../CHANGELOG.md) separates
unreleased changes from published versions. For an installed release, use the
corresponding tag on GitHub when comparing its behaviour with the source.

Download published builds from [GitHub Releases](https://github.com/0then0/cambridge-dictionary-audio/releases).
Builds attached to GitHub Actions runs are intended for testing; their installation
requirements depend on platform and signing status.

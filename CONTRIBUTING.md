# Contributing

This guide covers source setup, repository structure, validation and release
packaging. For application usage, start with the [documentation index](docs/README.md).

## Issues and pull requests

Use the [issue templates](https://github.com/0then0/cambridge-dictionary-audio/issues/new/choose)
for reproducible bugs and feature proposals. Include the affected platform,
version and a minimal example. Discuss substantial compatibility or architecture
changes before implementing them. Never attach credentials or private collections.

Keep pull requests focused. Explain the resulting behavior, relevant checks and
any effects on existing data or supported platforms. Add regression coverage for
behavior changes and update the changelog when users are affected. Use English
Conventional Commit messages, for example `fix: preserve selected pronunciation`.

Follow the [code of conduct](CODE_OF_CONDUCT.md). Report vulnerabilities privately
as described in [SECURITY.md](SECURITY.md), rather than in a public issue.

## Python setup

Use [uv](https://docs.astral.sh/uv/) 0.13.0 or later. Python 3.10–3.15 is supported;
`.python-version` selects 3.15 for development. Dependencies are declared in
`pyproject.toml` and resolved in `uv.lock`.

```sh
uv sync --locked
uv run -m cambridge_audio hello
```

For desktop development, include the GUI dependency group:

```sh
uv sync --locked --group gui
uv run --locked --group gui -m cambridge_audio.gui
```

To use another supported interpreter, pass the same `--python` selection to both
`uv sync` and `uv run`. The CLI wheel excludes Qt and desktop modules. The `gui`
group supplies PySide6; the `release` group supplies packaging tools. See
[Python versions](README.md#python-versions) for platform-specific dependency notes.

## Repository structure

- `cambridge_audio/dictionary.py`: Cambridge parsing, HTTP and source identities.
- `cambridge_audio/service.py`: download and recording workflows.
- `cambridge_audio/library.py`, `bundle.py`, `translations.py`, `anki.py`: metadata,
  portable collections, translation resolution and study-material export.
- `cambridge_audio/audio.py`: desktop/CLI playback and FFmpeg phrase processing.
- `cambridge_audio/cli.py`, `terminal/`, `gui/`: the Python application interfaces.
- `mobile/shared/`: Kotlin core for mobile storage, lookup, transfer and export.
- `mobile/androidApp/`: Android Compose interface and platform adapters.
- `mobile/iosApp/`: SwiftUI interface, platform adapters and XCTest targets.
- `mobile/native/`: shared PCM processing and LAME integration.
- `extension/`: browser popup, manifests, TypeScript tests and build scripts.
- `contracts/`: shared fixtures and stable Python/Kotlin/Anki contracts.
- `tests/`: Python core, CLI, terminal, desktop and packaging tests.
- `assets/`: the application icon and interface SVGs.
- `scripts/`, `packaging/`: build helpers, release checks and installer templates.
- `docs/`: user guides, design, storage specifications and build instructions.

`python -m cambridge_audio` is the package entry point. The root `main.py` remains
a compatibility launcher. On Windows, `start.bat` and `start-gui.bat` launch the
CLI and desktop app through uv.

## Python checks

Run the following from the repository root:

```sh
uv lock --check
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
uv run --locked --group gui pytest
```

Use `uv run --locked ruff format .` to apply Python formatting. `.editorconfig`
defines shared whitespace conventions. Tests use temporary collections, isolated
settings and mocked HTTP. GUI tests use Qt's offscreen platform. The optional
audio integration test needs both `ffmpeg` and `ffprobe` and otherwise reports a
skip. It does not change normal application playback requirements.

The [Checks workflow](https://github.com/0then0/cambridge-dictionary-audio/actions/workflows/checks.yml)
covers all supported Python versions on Linux and Python 3.10/3.15 on Windows and
macOS. Desktop suites additionally cover Python 3.11/3.12 on Linux. Extension and
package-integrity jobs run in the same workflow.

Keep tests independent of live dictionary services. When changing asynchronous
interfaces, wait for observable state rather than assuming one event-loop pause
has processed a worker result. Preserve user metadata and stable export identities.

## Mobile and browser development

Mobile applications have their own Gradle and Xcode toolchains. See
[mobile build instructions](docs/mobile/install.md) for pinned versions and
[mobile testing](docs/mobile/readiness.md) for native and compatibility checks.
Full mobile CI runs for relevant changes on `main` and pull requests: mobile
sources, shared contracts, transfer/Anki compatibility, native source manifests,
licenses and mobile/release workflows. Documentation-only and unrelated desktop
changes do not start native builds. New branch/PR commits cancel superseded mobile
checks. Manual runs remain available, and Release always calls the mobile workflow.

The shared generated Anki contract is checked with:

```sh
python3 scripts/mobile_contracts.py --check
```

Change `contracts/anki.json` only with a deliberate compatibility decision, then
regenerate `AnkiContract.kt` with `python3 scripts/mobile_contracts.py`.

The browser extension uses Node.js and `extension/package-lock.json`. Its
[development guide](extension/README.md#build-and-test) covers Biome, TypeScript,
DOM tests and packaging. npm tools are independent of the Python environment.

## Dependencies

Keep lockfiles in version control. Update dependencies deliberately and run the
checks for the affected interface. For Python, `uv lock --upgrade` refreshes the
lockfile within declared constraints.

[Dependabot](.github/dependabot.yml) checks uv, npm, Gradle and GitHub Actions
monthly at 09:00 Europe/Moscow. Normal updates are limited to minor/patch versions
at least 14 days old, grouped into one open pull request per ecosystem. Automatic
rebasing is disabled; the configuration does not enable automatic merging. Python updates change the lockfile
within the manifest's existing constraints. GitHub security updates, when enabled,
are grouped separately and are not delayed by the normal update schedule.

Major upgrades, exact Python pins, Xcode/SDK versions, Xcode Swift-package
references and custom source/formatter checksums are maintained manually. Review
compatibility across Kotlin, Gradle, Android plugins and native build tools together.

## Desktop and Python packaging

Build desktop bundles on the target operating system and architecture. Install
the platform compiler and packaging tools listed in
[Rebuilding FFmpeg](packaging/ffmpeg-build.md) and the [Release workflow](.github/workflows/release.yml).
Then run:

```sh
uv sync --locked --group gui --group release
uv run --locked --group gui --group release python scripts/build_ffmpeg.py
uv run --locked --group gui --group release python scripts/build_desktop.py
uv run --locked --group gui --group release python scripts/package_desktop.py
```

`compile.bat` provides the Windows build entry point and requires Inno Setup.
Outputs are written under `dist/`. Preserve the bundled dependency notices and
matching FFmpeg/LAME source materials when distributing a desktop build.

Build and validate the CLI distributions independently:

```sh
uv build --out-dir dist/python
uv run --locked --group release python scripts/release.py verify-python dist/python
uv run --locked --group release twine check --strict dist/python/*
```

The wheel and source distribution use [docs/cli.md](docs/cli.md) as their package
README. Keep its links usable on PyPI as well as in the repository.

## Releases

Keep Python and extension versions aligned in `pyproject.toml`, `package.json`
and the npm lockfile. Mobile version names and platform build numbers are
configured separately. Version changes must not change storage schemas or stable
Anki identities implicitly.

A `v…` tag matching the Python package version triggers the Release workflow,
which builds GitHub release assets. PyPI publication is a separate opt-in within
that workflow: select an existing release tag in **Run workflow** and enable
`publish_pypi`. The protected `pypi` environment uses Trusted Publishing/OIDC.
Mobile signing uses the protected `mobile-signing` environment described in the
[mobile guide](docs/mobile/install.md).

After publishing a stable release, update the pinned download buttons:

```sh
uv run --locked python scripts/download_links.py --refresh --verify-network
```

This command updates `packaging/downloads.json` and the marked download sections
in both root README files. Without `--refresh`, the script checks the existing
snapshot. Keep user-facing changes in [CHANGELOG.md](CHANGELOG.md), and update
both English and Russian README text when their shared instructions change.

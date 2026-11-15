<p align="center">
  <img src="assets/icon.svg" width="120" alt="Cambridge Dictionary Audio icon">
</p>

# Cambridge Dictionary Audio

[![Checks](https://img.shields.io/github/actions/workflow/status/0then0/cambridge-dictionary-audio/checks.yml?branch=main&label=checks)](https://github.com/0then0/cambridge-dictionary-audio/actions/workflows/checks.yml)
[![Mobile checks](https://img.shields.io/github/actions/workflow/status/0then0/cambridge-dictionary-audio/mobile.yml?branch=main&label=mobile)](https://github.com/0then0/cambridge-dictionary-audio/actions/workflows/mobile.yml)
[![Release](https://img.shields.io/github/v/release/0then0/cambridge-dictionary-audio)](https://github.com/0then0/cambridge-dictionary-audio/releases/latest)
[![PyPI](https://img.shields.io/pypi/v/cambridge-dictionary-audio)](https://pypi.org/project/cambridge-dictionary-audio/)
[![Python](https://img.shields.io/badge/Python-3.10%E2%80%933.15-3776AB?logo=python&logoColor=white)](CONTRIBUTING.md#python-setup)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

[Русский](README.ru.md) · [Documentation](docs/README.md) · [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

Save English pronunciations from [Cambridge Dictionary](https://dictionary.cambridge.org/)
as MP3 files and turn them into study material. Search a word, choose the meaning
you need, listen to the US or UK recording and keep it in a local collection with
its IPA, definition and an optional Russian translation. Export the collection to
Anki as a ready-made deck.

The project includes a desktop app for Windows, macOS and Linux, a command-line
tool with a terminal interface, Android and iOS apps, and a browser extension for
Chrome and Firefox.

## Features

- US and UK recordings with IPA transcriptions and English definitions.
- Explicit choice between meanings and pronunciations; each meaning is a separate
  collection entry, while meanings with the same recording share one MP3.
- Adding many words at once from a pasted list in the desktop app.
- Optional Russian translations from Cambridge or the offline
  [WikDict](https://www.wikdict.com/) dictionary, with personal edits.
- Anki export to `.apkg` with stable note identities, so re-exports update
  existing cards instead of duplicating them.
- Synthesis of phrases without their own recording from the recordings of
  individual words (uses FFmpeg).
- `.cda` backups that move a collection between the desktop and mobile apps.
- Interface in English, Russian, Spanish, German, French, Japanese and
  Brazilian Portuguese.

## Download

<!-- downloads:start -->
Direct downloads for the latest verified stable release **v1.0.1**:

| Platform | Architecture | Download |
| --- | --- | --- |
| Windows 10+ | x86-64 | [![Windows 10+ x86-64 EXE](https://img.shields.io/badge/EXE-0078D4?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xIDFoMTB2MTBIMXpNMTMgMWgxMHYxMEgxM3pNMSAxM2gxMHYxMEgxek0xMyAxM2gxMHYxMEgxM3oiLz48L3N2Zz4%3D&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-dictionary-audio-1.0.1-windows-x86_64-setup.exe) [![Windows 10+ x86-64 Portable ZIP](https://img.shields.io/badge/Portable%20ZIP-0078D4?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xIDFoMTB2MTBIMXpNMTMgMWgxMHYxMEgxM3pNMSAxM2gxMHYxMEgxek0xMyAxM2gxMHYxMEgxM3oiLz48L3N2Zz4%3D&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-dictionary-audio-1.0.1-windows-x86_64-portable.zip) |
| macOS 14+ | Apple Silicon (arm64) | [![macOS 14+ Apple Silicon (arm64) PKG](https://img.shields.io/badge/PKG-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-dictionary-audio-1.0.1-macos-arm64.pkg) [![macOS 14+ Apple Silicon (arm64) DMG](https://img.shields.io/badge/DMG-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-dictionary-audio-1.0.1-macos-arm64.dmg) [![macOS 14+ Apple Silicon (arm64) TAR.GZ](https://img.shields.io/badge/TAR.GZ-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-dictionary-audio-1.0.1-macos-arm64.tar.gz) |
| macOS 14+ | Intel (x86-64) | [![macOS 14+ Intel (x86-64) PKG](https://img.shields.io/badge/PKG-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-dictionary-audio-1.0.1-macos-x86_64.pkg) [![macOS 14+ Intel (x86-64) DMG](https://img.shields.io/badge/DMG-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-dictionary-audio-1.0.1-macos-x86_64.dmg) [![macOS 14+ Intel (x86-64) TAR.GZ](https://img.shields.io/badge/TAR.GZ-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-dictionary-audio-1.0.1-macos-x86_64.tar.gz) |
| Linux | x86-64 · glibc 2.34+ | [![Linux x86-64 · glibc 2.34+ DEB](https://img.shields.io/badge/DEB-FCC624?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-dictionary-audio_1.0.1_amd64.deb) [![Linux x86-64 · glibc 2.34+ RPM](https://img.shields.io/badge/RPM-FCC624?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-dictionary-audio-1.0.1-1.x86_64.rpm) [![Linux x86-64 · glibc 2.34+ Portable TAR.GZ](https://img.shields.io/badge/Portable%20TAR.GZ-FCC624?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-dictionary-audio-1.0.1-linux-x86_64-portable.tar.gz) |
| Android 9+ | arm64-v8a / armeabi-v7a / x86_64 | [![Android 9+ arm64-v8a / armeabi-v7a / x86_64 Test APK](https://img.shields.io/badge/Test%20APK-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-audio-1.0.1-android-debug-TEST-ONLY.apk) [![Android 9+ arm64-v8a / armeabi-v7a / x86_64 Unsigned APK](https://img.shields.io/badge/Unsigned%20APK-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-audio-1.0.1-android-unsigned-NOT-INSTALLABLE.apk) |
| iOS 17+ | arm64 | [![iOS 17+ arm64 Device · signing required](https://img.shields.io/badge/Device%20%C2%B7%20signing%20required-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-audio-1.0.1-ios-device-unsigned-REQUIRES-SIGNING.tar.gz) [![iOS 17+ arm64 Simulator only](https://img.shields.io/badge/Simulator%20only-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-audio-1.0.1-ios-simulator-NOT-FOR-DEVICE.tar.gz) |
| Python CLI | Any | [![Python CLI Any WHL](https://img.shields.io/badge/WHL-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge_dictionary_audio-1.0.1-py3-none-any.whl) [![Python CLI Any Source TAR.GZ](https://img.shields.io/badge/Source%20TAR.GZ-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge_dictionary_audio-1.0.1.tar.gz) |
| Chrome | Any | [![Chrome Any ZIP](https://img.shields.io/badge/ZIP-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-audio-chrome-1.0.1.zip) |
| Firefox | Any | [![Firefox Any ZIP](https://img.shields.io/badge/ZIP-FF7139?style=for-the-badge&logo=firefoxbrowser&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/cambridge-audio-firefox-1.0.1.zip) |

[![SHA-256](https://img.shields.io/badge/SHA--256-SHA256SUMS.txt-555555?style=flat-square)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v1.0.1/SHA256SUMS.txt)

Android: the test APK uses a development certificate; the unsigned APK requires signing before installation. iOS: the device archive requires signing and a provisioning profile; the simulator build cannot be installed on an iPhone. [Installation and signing](docs/mobile/install.md).
<!-- downloads:end -->

Desktop installers and portable builds include Python, Qt and an audio-only
FFmpeg with LAME; nothing else needs to be installed. Windows builds require
Windows 10 or later. Installers are not signed with a publisher certificate and
macOS builds are not notarized, so the operating system may ask for confirmation
on first launch. Each release also contains the FFmpeg/LAME source archives and
`SHA256SUMS.txt`.

The command-line tool is published on [PyPI](https://pypi.org/project/cambridge-dictionary-audio/):

```sh
uv tool install cambridge-dictionary-audio
```

`pipx install cambridge-dictionary-audio` works as well.

## Quick start

**Desktop app.** Type a word or phrase and press **Find**. Choose a meaning,
switch between US and UK, listen with **Play** and press **Save meaning**.
Recordings are saved to `Cambridge Dictionary Audio` in your Downloads folder.
**Word list...** adds up to 100 words at once. See the [desktop guide](docs/desktop.md).

**Command line.**

```sh
cambridge-audio hello                          # saves downloads/hello.us.mp3
cambridge-audio "good morning" --accent both   # US and UK recordings
cambridge-audio hello --translation russian    # with a Russian translation
cambridge-audio                                # opens the terminal interface
```

See the [command-line guide](docs/cli.md) for all options and keyboard shortcuts.

**Mobile apps and browser extension.** See [Android and iOS](docs/mobile/README.md)
and the [browser extension guide](extension/README.md).

## Documentation

- [Desktop app](docs/desktop.md)
- [Command line and terminal interface](docs/cli.md)
- [Collection, translations and Anki](docs/collection.md)
- [Android and iOS](docs/mobile/README.md)
- [Browser extension](extension/README.md)
- [Data sources and licenses](docs/data-sources.md)
- [All documentation](docs/README.md)

## Run from source

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) 0.13.0 or
newer, then run in the project directory:

```sh
uv sync --locked --group gui
uv run --locked --group gui -m cambridge_audio.gui   # desktop app
uv run --locked -m cambridge_audio hello             # command line
```

[CONTRIBUTING.md](CONTRIBUTING.md) explains the project structure, tests and
release builds. Bug reports and feature requests are welcome in
[GitHub issues](https://github.com/0then0/cambridge-dictionary-audio/issues/new/choose);
please report security problems privately as described in [SECURITY.md](SECURITY.md).

## License

The application is distributed under the [Apache License 2.0](LICENSE). It is
based on [astrosander/cambridge-dictionary-audio](https://github.com/astrosander/cambridge-dictionary-audio);
code inherited from that project keeps its [MIT license](LICENSE-MIT). See
[NOTICE](NOTICE) for attribution. Bundled components such as Qt/PySide6 and
FFmpeg keep their own licenses.

Cambridge Dictionary Audio is an independent project and is not affiliated with
or endorsed by Cambridge University Press & Assessment. Dictionary content and
recordings belong to their owners and are subject to
[Cambridge's terms of use](https://dictionary.cambridge.org/terms-of-use). See [data sources and licenses](docs/data-sources.md).

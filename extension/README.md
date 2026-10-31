<p align="center">
  <img src="../assets/icon.svg" width="80" alt="Cambridge Dictionary Audio icon">
</p>

# Cambridge Dictionary Audio browser extension

Download the pronunciation linked on the Cambridge Dictionary page you are viewing.
The extension runs independently of the Python application and supports Chrome and
Firefox on desktop. It uses TypeScript and Manifest V3, with no runtime dependencies.

## Use

1. Open a word or phrase on [Cambridge Dictionary](https://dictionary.cambridge.org/).
2. Click the extension icon. Pin it to the toolbar for convenient access.
3. Choose **US** or **UK**, then click **Download MP3**.

US is the default. On pages with multiple dictionary entries or pronunciation
variants, selectors let you choose the recording. An unavailable accent is marked
explicitly. **Refresh** reads the current page again after it loads or changes.
Transcriptions and definitions come from the page and remain in the dictionary's
language. The extension downloads existing recordings; translations, a saved-recording
library and phrase synthesis are available in the [desktop app and CLI](../README.md).

The gear button opens **Settings**. Interfaces in English, Russian, Spanish, German,
French, Japanese and Brazilian Portuguese are available; English is the default. Choose **System**, **Light** or **Dark** appearance. System
mode follows the browser's operating-system colour preference. Language, theme and
accent are stored locally and restored the next time you open the popup.

Files are named `word.us.mp3` or `word.uk.mp3`. The browser controls the destination
and whether to show a file chooser, using your usual download preferences. Existing
files receive unique names instead of being overwritten. Closing the popup does not
cancel a download that the browser has started; check the browser's download manager
for completion or network errors.

## Installation

Build locally as described below, or extract the matching ZIP from a GitHub release
or the `browser-extensions` artifact of a successful Checks workflow.

**Chrome:** open `chrome://extensions`, enable **Developer mode**, choose
**Load unpacked**, and select `extension/dist/chrome` (or the extracted Chrome ZIP
folder containing `manifest.json`).

**Firefox:** open `about:debugging#/runtime/this-firefox`, choose **Load Temporary
Add-on**, and select `extension/dist/firefox/manifest.json`. A temporary add-on is
removed when Firefox restarts. Permanent installation in standard Firefox requires
a Mozilla-signed release; the generated ZIP is unsigned.

The manifests target Chrome 102+ and Firefox desktop 140+. This guide covers
desktop installation; Firefox Android is outside the supported desktop workflow.
Browser API behaviour has automated tests, with installation and download checks
included in release verification.

## Build and test

Use Node.js 24 LTS (24.15 or later), or Node.js 26+. Run these commands in `extension/`:

```sh
npm ci --ignore-scripts
npm run check
npm test
```

`npm run check` runs Biome's formatting, lint and import checks, followed by TypeScript
checking. `npm run format` formats the source; `npx biome check --write .` also applies
safe lint and import fixes. Generated bundles, dependencies, the npm lockfile and
third-party HTML test fixtures are excluded from source checks.

`npm test` compiles TypeScript, builds both browser folders, and runs offline tests
with Node's test runner and jsdom. Tests cover actual DOM parsing, serialized script
injection, URL filtering, filenames, popup interaction, preferences and bundle contents.
No production pages or audio files are requested by automated tests.

To create reproducible ZIP archives, also make Python 3 available and run:

```sh
npm run package
```

The archives appear as `dist/cambridge-audio-chrome-<version>.zip` and
`dist/cambridge-audio-firefox-<version>.zip`. Set the `PYTHON` environment variable
if the desired interpreter is not named `python3` on Unix or `python` on Windows.
Extension and Python versions must match; update `package.json`, its lockfile and
`pyproject.toml` together when changing the release version.

After rebuilding, reload the extension in the browser's extensions/developer page
and reopen its popup. Smoke-test US and UK downloads, a page without audio, multiple
entries, both languages, all themes, settings after reopening, and filename conflicts.

The PNG toolbar icons are exports of [`assets/icon.svg`](../assets/icon.svg) at
16, 32, 48 and 128 pixels. The build copies the shared SVG for the popup. Update the
PNG exports when changing that source icon.

## Permissions and privacy

- `activeTab` gives temporary access to the tab when you click the extension icon.
  The code checks that it is an HTTPS Cambridge dictionary page before reading it.
- `scripting` extracts the word, definition, transcription and linked MP3 URLs from
  that page. It does not modify the dictionary page.
- `downloads` starts the selected MP3 download using the browser's download manager.
  The extension does not read your download history or delete files.
- `storage` remembers only language, theme and accent in local extension storage.
  Words, page URLs and download history are not stored or synchronized.

There are no background scripts, persistent host permissions, analytics, remote code,
or uploads. Audio requests go to `dictionary.cambridge.org` through the browser.
The extension does not communicate with the Python app. Browser and desktop
preferences remain separate.

This extension follows the repository's [Apache-2.0 license](../LICENSE), retained
[MIT notice](../LICENSE-MIT) and [attribution](../NOTICE). It is independent of Cambridge
University Press & Assessment. Audio remains subject to its owners' rights and
[Cambridge's website terms](https://dictionary.cambridge.org/terms-of-use).

## Project documentation

See the [documentation index](../docs/README.md) for application guides and
[Contributing](../CONTRIBUTING.md) for repository conventions and releases.

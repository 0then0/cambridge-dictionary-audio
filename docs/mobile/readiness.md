# Mobile testing and release checks

The mobile test suites cover the shared Kotlin core, native audio and storage
adapters, and platform interfaces. Use them alongside the Python compatibility
fixtures when changing collection storage, translations or Anki export.

The [Mobile checks and artifacts workflow](https://github.com/0then0/cambridge-dictionary-audio/actions/workflows/mobile.yml)
runs for mobile-related changes on `main` and pull requests, and can be started
manually. Documentation-only changes do not trigger native builds. Release builds
always include this workflow. It checks formatting before building Android
and iOS, runs emulator/simulator tests, and uploads packaged artifacts.
[Build instructions](install.md) describe the required toolchains and signing.

## Shared core and compatibility

From the repository root, verify the generated contract and Python transfer tests:

```sh
python3 scripts/mobile_contracts.py --check
uv run --locked pytest tests/core/test_mobile_contract.py tests/core/test_bundle.py
```

Run the Kotlin JVM tests from `mobile/`:

```sh
./gradlew :shared:jvmTest
```

Coverage includes dictionary parsing, identities, translation matching, legacy
metadata, shared audio, collection import conflicts, recovery and phrase repair.
The [shared fixtures](../../contracts/README.md) define common Python/Kotlin
behaviour and stable Anki identities.

Two integration checks need additional local fixtures and otherwise report a
skip. Set `CDA_WIKDICT_ACCEPTANCE_PATH` to the pinned WikDict SQLite file to test
verified installation and failed replacement without downloading a dictionary.
The Anki round-trip uses `CDA_ACCEPTANCE_ROOT`, configured by the script below.

## Android

After building the native codec, run these commands from `mobile/`:

```sh
./gradlew :shared:jvmTest :androidApp:assembleDebug :androidApp:assembleRelease \
  :androidApp:lintDebug :androidApp:testDebugUnitTest
./gradlew :androidApp:connectedDebugAndroidTest
```

The connected tests need a running Android emulator or a connected test device.
CI uses an API 36 x86-64 emulator with KVM hardware acceleration. Its Linux setup
waits for udev permission changes before starting the emulator.

Instrumented tests exercise native MP3 decoding and LAME encoding, SQLite and
archives, collection repair and transfer, navigation, preference persistence,
activity recreation, expandable choices, colour contrast and the license reader.
Audio fixtures are generated tones; automated tests do not request Cambridge
recordings. Test reports are written under each module's `build/reports/` directory.

## iOS

Run the CambridgeAudio scheme with the pinned toolchain and Python interpreter as
shown in [the iOS build instructions](install.md#ios). The test action includes:

- `CoreIntegrationTests`: legacy collection persistence, audio validation and
  cancellation, native phrase synthesis, Android collection import, Anki export,
  identity preservation and restoration of missing or damaged media.
- `NavigationTests`: navigation between the native application tabs.

CI builds and tests on the iPhone 17 simulator, then builds the Release application
for a generic iOS device. Both simulator and unsigned device archives are uploaded
with checksums and source/relink materials. Device installation requires the
[appropriate signing and provisioning](install.md#ios).

## Anki integration

`scripts/verify_mobile_anki.py` transfers a disposable collection through the
Python exporter, Kotlin core and Anki backend. It imports packages, creates real
scheduler reviews, reimports changed contents, reopens the collection and checks
that note/card identities, scheduling and review history are preserved.

Use a Python interpreter compatible with the installed Anki backend and expose
its `app_packages` directory through `PYTHONPATH`. The repository `.venv` supplies
the desktop exporter; Java and Gradle supply the Kotlin test. Pass a new, empty
output directory:

```sh
PYTHONPATH="/path/to/Anki/app_packages" /path/to/anki-compatible-python \
  scripts/verify_mobile_anki.py /path/to/disposable-anki-check
```

The script creates its own test profile and writes `anki-results.json`. Never
point it at a personal Anki profile. `CDA_IOS_ACCEPTANCE_OUTPUT` can additionally
save the iOS native test's `.cda` and `.apkg` outputs for inspection or a separate
Anki import check. Anki's note and note-type update options still control how
[personal edits are handled](../collection.md#reimport-and-personal-edits).

## Checks before distribution

Automated CI verifies builds and regression behaviour. A release also needs the
following checks on the intended devices and distribution route:

1. Search, choose a meaning and pronunciation, preview, save, edit a translation,
   restart offline, play saved audio, synthesize a phrase and share an export.
2. Export and import `.cda` archives between desktop, Android and iOS. Confirm
   permanent IDs, personal translations, shared audio and explicit conflict choices.
3. Check large fonts, Dynamic Type, TalkBack/VoiceOver, keyboard focus, landscape,
   tablet layouts, safe areas, themes, contrast and system Back navigation.
4. Interrupt playback with a call or headphone removal. Background and return to
   the app. Cancel downloads and imports, interrupt the network and test recovery
   with disposable storage and collections.
5. Verify the release certificate, provisioning profile, checksums and non-debug
   configuration. Install an update over a previous build signed with the same
   identity and confirm that the collection remains available.
6. Include dependency licenses, data attribution and matching LAME source/relink
   materials. Check release notes and installation instructions for each artifact.

Do these checks with disposable data and record device/OS versions in the release
review. CI success alone does not establish physical-device accessibility,
provisioning or update compatibility.

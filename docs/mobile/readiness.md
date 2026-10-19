# Mobile / 1.0 acceptance record

Measured on **2026-10-19**. Baseline: Python/desktop/extensions **0.4.2**, initially
clean worktree with no mobile modules. Current mobile version is **1.0.0-dev**,
build **1000001**; sidecar schema **3**, transfer schema **1**. No commit, push,
release, PyPI publication, account registration or paid action was performed.

**Stable 1.0 and RC are not ready.** Android development builds work locally.
iOS source and shared native compilation are available, but the full Swift/Kotlin
bridge, app linking and runtime have not been validated with Xcode. These are
technical acceptance gaps, not merely missing distribution certificates. The
complete desktop → Android → iOS → desktop device chain remains unverified.

## Capability and parity checklist

- **Search and pronunciation:** existing Python normalization, Cambridge block /
  sense / audio identity and variant rules are ported to shared Kotlin. Original
  Python HTML fixtures plus a multiple-recording `lead` fixture run against both
  implementations. Android's live `hello` lookup displayed actual Cambridge
  definitions and saved a fully decoded remote MP3 with its selected meaning. US/UK/both, explicit recording choice, preview and verified download
  are implemented. Device playback/route interruption still require manual checks.
- **Collection:** persistent sidecars and shared media remain the portable format;
  legacy v1/v2/v3 and MP3-only reading, edit/reset, delete/reference handling,
  missing-media repair and offline restart are implemented. Android integration
  checks shared-media deletion, personal edits, reopen and native audio. JVM
  fault tests check cancellation, simulated disk-full flush and startup recovery.
  A real process kill/power-loss matrix and OS upgrade remain unverified.
- **Translations:** personal > explicit choice > matched cache > dictionary;
  shared conservative matching, independent EN/RU UI, online Cambridge and explicit
  pinned WikDict installation. Golden matching and late-result tests pass.
  Interrupted WikDict replacement, iOS offline lookup and physical-device
  loss-of-network tests still require acceptance. Android's explicit 20.9 MB
  download passed the exact checksum and native SQLite checks; with both network
  interfaces disabled, `hello` showed WikDict candidates without silently choosing
  an ambiguous meaning.
- **Phrase synthesis:** desktop retains FFmpeg concat/loudnorm/LAME. Android/iOS
  platform decoders feed ordered PCM to shared C/LAME. Android native decoding and
  JNI encoding pass with real MP3 fixtures; host spectral tests confirm segment
  order and a real 1.0-second MP3. Mobile RMS processing is not identical to desktop
  EBU R128 loudness processing. iOS AVAudioConverter/LAME runtime is unverified;
  real-device listening and route/interruption checks remain open.
- **Anki:** shared fixed model/deck/field/template/GUID contracts, adopted mapping,
  independent SQLite APKG and TSV/media ZIP exporters. Real Anki **26.09.3** accepts
  Python → Kotlin → Python and actual Android output while retaining 3 note IDs,
  3 card rows and 3 scheduler-created reviews. Personal fields update with note
  updates enabled and note-type replacement disabled. Full iOS and mobile adopted
  TSV-model/custom-template round-trips have not been validated; existing desktop
  adoption tests remain intact. No AnkiMobile purchase was made.
- **Backup/transfer:** Python GUI/CLI and shared mobile core implement `.cda`,
  checksums, bounded paths/members, explicit conflicts, stale previews, staged
  import, retained backups and recovery. Unknown metadata/cache fields travel with
  records and survive edits. Python tests cover hostile archives, internal legacy
  audio aliases, external links, rollback and metadata-symlink protection.
  Actual desktop → Android → desktop transfer passes; JVM's second independent
  store is explicitly not an iOS runtime test.
- **Preferences and UI:** Compose Material 3 with dynamic/fallback colour, native
  SwiftUI controls, EN/RU, US default, system/light/dark with an independent OLED
  switch applied only in dark appearance, colour choice
  including the desktop red accent, native
  pickers/sharing and copyable diagnostics. Android navigation, language persistence
  and Activity recreation pass. Long-content search screen inspected in the API36
  emulator. TalkBack, VoiceOver, 200% fonts, contrast settings, tablets, split screen,
  predictive Back and physical-device ergonomics have not been signed off.

## Checks actually run

Baseline: Python **548 passed**, extension **39 passed** plus lint/type checks.
After implementation: `.venv/bin/python -m pytest` **566 passed**, 45 dependency
warnings. After the metadata-symlink guard's regression test was added, targeted
`pytest -q tests/core/test_bundle.py tests/core/test_mobile_contract.py` passed
**19 tests**, 1 dependency warning. The full suite was not rerun after that one
additional test; the targeted result supplements the earlier full run.

- `.venv/bin/ruff check .` and `ruff format --check .`: passed, 105 Python files.
- `git diff --check`: passed.
- `.gitignore`: 17 generated/private paths ignored; 13 wrapper, shared-scheme,
  lockfile, fixture and environment-example paths retained.
- YAML parsing: all workflow files parse. GitHub-hosted workflows were not run.
- `./gradlew :shared:jvmTest`: **9 passed, 1 skipped**. The skipped opt-in test
  requires a real Anki setup; it passed separately with `CDA_ACCEPTANCE_ROOT`.
- `./gradlew :shared:compileKotlinIosSimulatorArm64 -PenableAppleTargets=true`:
  passed. This compiles native Kotlin IR only, not a SwiftUI application.
- Android `assembleDebug`, `assembleRelease`, `assembleDebugAndroidTest`,
  `lintDebug`: passed (0 errors, 13 advisory warnings). `testDebugUnitTest` has no separate Android unit sources;
  domain coverage is in JVM and instrumented suites.
- `connectedDebugAndroidTest`, then direct instrumentation after final builds:
  **4 passed** on **Android 16/API36 arm64 emulator**. Includes EN/RU settings,
  Activity recreation, real MP3 decoding, shared JNI/LAME phrase, SQLite/APKG and
  desktop bundle import/export and graceful undecodable legacy-MP3 errors. API28/API37 emulators and physical Android untested.
- Live Android `hello` lookup → actual remote MP3 save → force-stop/reopen with
  Wi-Fi and cellular disabled: collection entry persisted. Reinstalling the same
  debug APK with `adb install -r` preserved exact metadata/MP3 SHA-256 bytes. This
  is a same-build emulator reinstall check, not production version-upgrade or
  physical-device acceptance.
- `scripts/verify_mobile_audio.py`: real decode/encode/decode, 44,100 frames at
  44.1 kHz, ordered 440/880 Hz segments, no clipping.
- `scripts/verify_mobile_anki.py` with Anki's compatible Python and disposable
  profile: passed; actual Android APKG independently reimported with identical
  notes/cards/review history. No personal Anki profile was opened or modified.
- `uv build`: wheel/sdist built in isolation without changing `.venv` or `uv.lock`.
  `scripts/release.py verify-python dist/python-development`: passed; no GUI/Qt in
  CLI distributions. `twine==7.0.0 check --strict`: both artifacts passed.
- `swiftc -frontend -parse`: Swift app/XCTest/UI-test syntax passed.
  `plutil -lint`: Info.plist and Xcode project passed. These checks do not prove
  Swift type checking, framework linkage or XCTest success.

Evidence is under ignored `build/mobile-tools/*.log` and
`build/mobile-verification/`: real APKG/bundle exports, Anki reports, phrase audio
and an Android live-search screenshot. Synthetic tones/records contain no user
collection data. No independent code review tool was available for this local diff.

## Source formatting gate

The source-format gate added subsequently passes locally with **ktfmt 0.64**
(22 Kotlin/Gradle files) and official **swift-format 602.0.0** (5 Swift files).
`scripts/format_mobile.py check` preserves source bytes; temporary malformed
fixtures verified nonzero checks and explicit correction in both languages.
Corrupted cached tools are refused before execution, and locked Swift bootstrap
was exercised. The generated Anki contract remains byte-identical; its 3 Python
contract tests pass. Ruff now checks 106 Python files. Both build and owner-signing
workflows require the reusable formatting gate; hosted Actions have not been run.
See [formatter commands and configuration](install.md#source-formatting).

## Mobile interface update

Search shows three compact meanings, with the remaining choices behind an
expandable control that collapses after selection. Saved details open inside
Collection with playback, repair, deletion, translation and export actions.
Returning restores the Search selection and unsaved translation draft. Android
also retains this navigation state across Activity recreation.

Playback preparation has its own inline cancellable state. The new regression
test failed against the previous Android APK because `play()` immediately set
the global `busy` flag and inserted a toolbar above the content. With the fix,
listening no longer enters global progress or changes the top bar's height.

After this update, debug/release APK builds, `assembleDebugAndroidTest` and
`lintDebug` passed. Direct instrumentation on the Android 16/API36 arm64 emulator
passed **9 tests**, including the original four integration tests, playback
progress, Collection navigation and draft restoration after recreation, OLED/red
preference persistence, meaning expansion/selection and exact theme colours.
Live Cambridge `bank` returned 25 meanings; the compact three-item list and pure
black/red settings were visually inspected in the emulator. Screenshots are in
`build/mobile-verification/ui-*.png`. Source formatting passes for 23 Kotlin/Gradle
files and 5 Swift files; the generated Anki contract check passes. Rebuilt Android
artifacts were packaged and their SHA-256 checksums verified.

Logs: `build/mobile-tools/ui-playback-baseline.log`, `ui-final-tests.log`,
`ui-final-build.log` and `ui-release-build.log`. Swift source syntax and formatting
pass; the new iOS interface has not been type-checked, linked or run without full
Xcode. The earlier iOS acceptance gaps still apply.

### OLED preference and complete accent palettes

OLED is now a separate persisted switch on both platforms. It changes the
background only while dark appearance is active, including when following system
appearance. Selecting light appearance retains the switch without applying a black
background. Legacy `theme=black` preferences migrate to `theme=dark` plus
`pureBlack=true`, retaining other settings.

Android previously changed `primary` but left most Material colour roles at their
default purple values. Each manual accent now supplies all accent/neutral roles,
including secondary/tertiary containers, fixed colours, surfaces, outlines and
inverse colours. Semantic error colours remain distinct. The system palette is
used intact unless OLED overrides its dark surfaces. Selecting a manual accent
disables system colours; the chips indicate the palette actually in use. iOS
native accents now have explicit light/dark variants.

After this change, debug/release APK builds, Android lint, source-format checks
(24 Kotlin/Gradle and 5 Swift files), and Swift syntax parsing passed. Android
instrumentation passed **11 tests**, including migration from the old black mode,
OLED persistence and independence from appearance, system/manual palette selection,
light-mode exclusion of black backgrounds, and text contrast of at least **4.5:1**
for the tested text/background roles in all five manual palettes, light and dark.
Logs: `build/mobile-tools/theme-final-build.log`, `theme-tests.log` and
`theme-format-check.log`. The emulator was also switched from system light to
system dark appearance with OLED enabled; the same setting correctly left the
light background intact and made the dark background black. The selected green
palette and OLED setting survived a full app process restart. Visual checks are
recorded in `build/mobile-verification/theme-*.png`. iOS full compilation and
runtime remain unverified.

### License reader

The subsequent license-reader update passes Android debug/release builds, lint
and **12 instrumented tests**, including full license navigation and scrolling
at 200% font scale with the close control kept visible. License summaries are
separated from full Apache/MIT/NOTICE text; printed indentation and hard line wraps
are reflowed for display, and bundled files remain byte-identical to the originals.
Formatting passes for 25 Kotlin/Gradle and 5 Swift files; Swift syntax parsing
passes, with the existing iOS build/runtime limitation unchanged. Logs are in
`build/mobile-tools/licenses-*.log`. The Russian overview and Apache reader were
visually inspected in the emulator; screenshots are in
`build/mobile-verification/licenses-overview.png` and `licenses-apache-reader.png`.

### WikDict verification and translation choices

The WikDict/translation-menu follow-up passes Android debug/release builds, lint
and **14 instrumented tests**. Settings and each installation request verify the
local dictionary on a worker (pinned size/SHA-256 plus SQLite integrity/schema),
distinguishing missing, verified, damaged and unavailable states. Reinstallation
requires explicit confirmation. Cancelling the prompt leaves the existing file
unchanged. Both mobile interfaces show three translation options initially and
collapse expanded alternatives after selection; the chosen full translation stays
visible above the options.

The shared JVM run passed **10 tests**, with 2 opt-in tests skipped. With the
already installed pinned WikDict copied from the disposable emulator, both
`WikdictStatusTest` tests passed separately, including successful reinstallation
and preservation of the valid package after a failed download checksum check.
No external download was needed for these checks. Native Kotlin compilation for
`iosSimulatorArm64`, Swift syntax parsing and formatting (26 Kotlin/Gradle, 5 Swift
files) passed. These still do not verify an iOS app build or runtime. Evidence:
`build/mobile-tools/wikdict-build.log`, `wikdict-ui-tests.log`,
`wikdict-native-compile.log` and the JVM XML results for `WikdictStatusTest`.
The installed/verified status and Russian reinstallation prompt were visually
checked in the emulator (`build/mobile-verification/wikdict-reinstall-confirmation.png`).

### Review regression fixes

The subsequent review found and fixed three defects: incoming replacements left
orphan MP3s that reappeared as extra records, missing local audio blocked import,
and phrase repair ignored stored pronunciation selections. Import now retires
only replaced media with no remaining owners, preserves independent MP3-only
records and shared media, and treats invalid local audio as an explicit conflict.
A corrupt managed blob is replaced only if every existing owner expects the
verified incoming SHA-256. Unowned filename collisions still fail without changing
the collection. Staging failures retain original metadata/audio; retained backups
also preserve the exact missing/corrupt pre-import state.

Phrase repair reuses saved segment URLs and choices without fetching word HTML.
Legacy phrases without a plan retain the previous unambiguous rebuild path;
malformed saved plans fail without silently changing pronunciations. Network
failure and cancellation preserve existing audio and personal translations.

New regressions failed against the pre-fix implementation. After the fixes:

- Python: **577 passed**, 45 existing dependency warnings; targeted bundle/contract
  checks: **29 passed**. Ruff check/format check and generated contract check pass.
- Shared JVM: **17 passed, 1 skipped**, using the local pinned WikDict fixture.
  The optional real-Anki acceptance test is skipped in this general run, then
  passes separately through `scripts/verify_mobile_anki.py` using Anki's compatible
  Python and a new disposable profile. Reimported Python/Kotlin APKGs preserve
  note/card identities, scheduling and three real scheduler-created reviews;
  the returned Kotlin bundle also survives Python export and Anki reimport.
- Android debug/release/test APK builds and lint pass. Direct instrumentation on
  the disposable API36 arm64 emulator passes **15 tests**, including real native
  MP3 synthesis, selected-pronunciation repair, duplicate-free replacement and
  missing/corrupt media restoration. The test delegates only HTTP fixture responses;
  storage, archive handling, decoding and LAME encoding use native implementations.
- Native Kotlin simulator compilation passes. Swift app/test syntax parsing passes;
  an equivalent iOS import/restore XCTest was added but cannot run locally without
  full Xcode/iPhone SDK. The earlier iOS runtime/signing gates remain open.

Logs: `build/mobile-tools/review-fixes-python.log`, `review-fixes-jvm.log`,
`review-fixes-android.log`, `review-fixes-instrumentation.log`, and
`review-fixes-native.log`; the independent Anki run is in `review-fixes-anki.log`.
Source formatting checks include 27 Kotlin/Gradle files
and 5 Swift files. These fixes do not establish stable/RC or owner-signing readiness.

## Artifacts and signing

`dist/mobile/` contains only actually built outputs:

- `cambridge-audio-1.0.0-dev-android-debug-TEST-ONLY.apk`: locally debug-signed,
  installable for testing; not production.
- `cambridge-audio-1.0.0-dev-android-unsigned-NOT-INSTALLABLE.apk`: non-debuggable
  release build, no owner certificate; cannot install until signed.
- `android-artifacts.json`, signature diagnostic and `android-SHA256SUMS.txt`.
- `android-source-and-relink-materials.tar.gz`, exact LAME source/build settings,
  native objects and notices, plus `android-INSTALL.md`.

CLI wheel/sdist are in `dist/python-development/` with the existing **0.4.2**
version, unpublished development contents. Pre-existing old `dist/python` files
were preserved. No iOS `.app`/IPA was produced: this host has only Command Line
Tools (Swift 6.2.4), not full Xcode or iOS SDKs. No owner signing keys are supplied.
Signing workflows and exact installation commands are in [install.md](install.md).

## Remaining acceptance gates

1. Install full Xcode 26.4.1 and its iPhone/iPad simulator runtime. Build Swift/Kotlin
   framework plus SwiftUI app; fix any type/link/runtime failures before claiming RC.
   Run `CoreIntegrationTests` and `NavigationTests`; the native integration fixture
   is actual Android-produced synthetic `android.cda`, plus real MP3 segments.
   Export iOS APKG/bundle through `CDA_IOS_ACCEPTANCE_OUTPUT` and reimport into the
   same disposable Anki/Python chain. This closes the required four-platform chain.
2. On Android/iPhone, exercise real lookup → choose meaning/US/UK recording →
   preview → save → personal translation → force stop/reopen offline → playback →
   phrase → APKG/TSV sharing → `.cda` conflict/backup import. Check installed WikDict
   offline, cancelled/failed downloads and unavailable accents.
3. Check layout at 200% Android fonts and iOS accessibility Dynamic Type, landscape,
   split screen/tablet, keyboard/safe areas; TalkBack/VoiceOver labels/focus/actions,
   dark/light, contrast/reduced transparency/motion, system Back/back gesture.
4. During playback test call/audio-focus interruption, headphone removal and
   background/return. During save/import cancel, lose network and exhaust disposable
   storage; kill/reopen and verify existing media/edits remain.
5. Supply owner Android keystore/password/alias; verify production certificate,
   APK checksums and non-debug flags. Supply Apple distribution certificate/key,
   owner team and Ad Hoc profile for explicitly registered devices, or use local
   Xcode Personal Team with the documented provisioning expiry.
6. Install signed builds and update over an existing installation with the same
   app/bundle identity and key/profile; compare collection IDs, personal translations
   and offline media. No physical device/install/update validation has passed yet.
7. Run hosted CI for desktop/CLI/extensions and both mobile targets, build available
   iOS simulator/device artifacts, review source/license materials and release notes.
   Only then assign RC/stable versions and publish after separate authorization.

Missing hardware/certificates do not make unrun checks pass. See the preserved
[desktop Anki import-option contract](../collection.md#verified-anki-round-trip):
choosing replacement import options can intentionally replace personal note/template
content; scheduling preservation is checked separately.

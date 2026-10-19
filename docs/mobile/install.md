# Mobile builds, installation and updates

Development sources target **1.0.0-dev**, build **1000001**. Python and extensions
remain 0.4.2 until the acceptance gates pass. These sources are not a declaration
of stable 1.0 or a completed RC. See [actual evidence](readiness.md).

## Build versions

Pinned: Kotlin 2.4.21, Gradle 9.3.1 (wrapper checksum verified), AGP 9.1.1,
Compose BOM 2026.09.00 with stable Material 3, Java 17, Android compile/target API
37 (platform package `platforms;android-37.0`), min API **28 / Android 9**.
NDK 28.2.13676358, CMake 3.22.1. Shared libraries: kotlinx.serialization 1.10.0,
Okio 3.16.4, Ksoup 0.2.6. Android uses activity-compose 1.12.4 and lifecycle 2.10.0.
These exact compatible releases are deliberately pinned, not automatic ranges.

Apple build configuration: **Xcode 26.4.1**, iOS deployment minimum **17.0**,
Swift language mode 5 with the selected Xcode toolchain. ZIPFoundation 0.9.20 is
an exact Swift Package dependency. Normal Objective-C framework export connects
Kotlin to Swift; experimental Swift export is not used. SwiftUI supplies the iOS
presentation, independently of Compose. Python is not embedded in either app.

Version compatibility sources checked on 2026-10-19:
[Kotlin](https://kotlinlang.org/docs/multiplatform/multiplatform-compatibility-guide.html),
[AGP](https://developer.android.com/build/releases/agp-9-1-0-release-notes),
[Compose BOM](https://developer.android.com/develop/ui/compose/bom),
[Android KMP plugin](https://developer.android.com/kotlin/multiplatform/plugin),
[Ksoup](https://github.com/fleeksoft/ksoup/releases),
[GitHub macOS runner](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md).

## Source formatting

Use the same commands locally and in CI (Python 3.12+, Java 17 for Kotlin,
and a Swift 6.2+ compiler for Swift):

```sh
python3 scripts/format_mobile.py check
python3 scripts/format_mobile.py format
# Run only one language when the other toolchain is not installed:
python3 scripts/format_mobile.py check --language kotlin
python3 scripts/format_mobile.py check --language swift
python3 scripts/mobile_contracts.py --check
```

`check` exits unsuccessfully on violations and never rewrites source files.
`format` explicitly applies fixes. Both use the versions and SHA-256 values in
`mobile/formatters.json`: **ktfmt 0.64** with Kotlin language style and the official
**swiftlang/swift-format 602.0.0**. This is not Nick Lockwood's `SwiftFormat`.
Kotlin/Gradle scripts use four-space indentation; Swift uses two spaces, both with
100-column formatting. Shared settings live in `mobile/.editorconfig` and
`mobile/.swift-format`.

The wrapper downloads verified tools into ignored `build/format-tools/`. On the
first Swift run it builds the exact upstream source release, using the transitive
revisions in `mobile/swift-format.resolved` with automatic resolution disabled.
Subsequent runs reuse that binary. A system `swift-format` is not substituted:
Xcode/Command Line Tools can bundle a different formatter version. The tool does
not require an iOS SDK, Android SDK or Gradle. Local Swift compilation works with
Command Line Tools; hosted checks select the pinned Xcode build toolchain and
cache formatter downloads/builds.

Checks cover Kotlin shared/platform/UI/tests and Gradle `.kts` files, plus all
three Swift application/test targets. Generated/build/cache trees are not scanned.
`AnkiContract.kt` is excluded because the Python generator owns its exact bytes;
its dedicated `mobile_contracts.py --check` remains mandatory.

`mobile-format.yml` is a reusable prerequisite of both `mobile.yml` and
`mobile-sign.yml`. Formatting must pass before native codec builds, SDK setup,
app builds, emulator tests or signing jobs begin. No formatting dependency is
added to the Python CLI package.

## Android builds

Install Java 17, Android SDK platform 37.0, build-tools 36.0.0, the pinned NDK and
CMake. Set `ANDROID_HOME`; install `pkgconf` for LAME's configure. Android tooling
is independent of `uv sync` and the CLI wheel.

```sh
python3 scripts/build_mobile_codec.py android-arm64-v8a
python3 scripts/build_mobile_codec.py android-armeabi-v7a
python3 scripts/build_mobile_codec.py android-x86_64
cd mobile
./gradlew :shared:jvmTest :androidApp:assembleDebug :androidApp:assembleRelease \
  :androidApp:lintDebug :androidApp:testDebugUnitTest
./gradlew :androidApp:connectedDebugAndroidTest
```

Release signing requires the owner's existing key. Export `ANDROID_KEYSTORE`
(absolute path), `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` and
`ANDROID_KEY_PASSWORD`, then run `:androidApp:assembleRelease`. Do not put these
values or files in Git. The release build is not debuggable. The owner-only
`mobile-sign.yml` workflow uses environment `mobile-signing`; PR checks receive
no signing secrets. With no key, `androidApp-release-unsigned.apk` is built and
labelled **NOT INSTALLABLE**. A debug APK is **TEST ONLY**, signed with a local
debug certificate. It is never a production release.

```sh
adb install -r mobile/androidApp/build/outputs/apk/debug/androidApp-debug.apk
# Owner-signed build:
$ANDROID_HOME/build-tools/36.0.0/apksigner verify --verbose --print-certs \
  mobile/androidApp/build/outputs/apk/release/androidApp-release.apk
```

For a GitHub release, download the owner-signed APK and checksums; compare SHA-256
and the published signing-certificate fingerprint. Open the APK on the phone and
allow installation for the browser/file manager when Android asks. For updates,
install the APK **over the existing app** with the same application ID and signing
key. A debug certificate cannot update an owner-signed installation. Export a
collection backup before deliberately uninstalling; uninstall may remove the
application's private collection. No broad storage permission is required: import
uses the system document picker and export uses Sharesheet/Files.

GitHub hosting does not override Android verification policy. As of the official
[Android developer verification page](https://developer.android.com/developer-verification)
checked on 2026-10-19, protections began on 2026-09-30 for participating stores in
Brazil, Indonesia, Singapore and Thailand on certified Android 7+ devices; broader
rollout is planned for 2027. Limited distribution accounts and a power-user
advanced flow are documented by Google. Applicable install routes depend on the
device, region and rollout. The owner must verify the applicable route before
claiming unrestricted public installation. This task creates no developer account
or verification registration.

## iOS

Full Xcode is required, including device and simulator SDKs. Command Line Tools
alone cannot build an iOS app. Open `mobile/iosApp/CambridgeAudio.xcodeproj`, select
the CambridgeAudio scheme and an iPhone simulator. Install Java 17, pkgconf and
Python 3.12+. Set `CDA_PYTHON` to that interpreter's absolute path: Xcode puts its
own older Python ahead of the normal shell PATH. Both iOS workflows select a
managed Python explicitly, so local Xcode installation is unnecessary for CI.
The build phase runs Gradle's standard framework integration and compiles the
pinned LAME source for the selected architectures. No server is involved.

```sh
export DEVELOPER_DIR=/Applications/Xcode_26.4.1.app/Contents/Developer
uv python install 3.15
export CDA_PYTHON="$(uv python find 3.15)"
xcodebuild -project mobile/iosApp/CambridgeAudio.xcodeproj -scheme CambridgeAudio \
  -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17' \
  -derivedDataPath build/ios-simulator CODE_SIGNING_ALLOWED=NO test
xcodebuild -project mobile/iosApp/CambridgeAudio.xcodeproj -scheme CambridgeAudio \
  -configuration Release -destination 'generic/platform=iOS' \
  -derivedDataPath build/ios-device CODE_SIGNING_ALLOWED=NO build
"$CDA_PYTHON" scripts/package_mobile.py ios --output dist/mobile
```

Artifacts have distinct meanings:

- **Simulator `.app` archive**: simulator only, cannot install on an iPhone.
- **Unsigned device `.app` archive**: device binary requiring code signing and a
  matching provisioning profile. Prefer rebuilding from these sources in Xcode;
  it is not an installable IPA and is not a universal sideloading package.
- **Signed Ad Hoc IPA**: only devices listed in the owner's provisioning profile.
  Requires an eligible Apple Developer Program membership, distribution
  certificate/private key and Ad Hoc profile for `org.cambridgeaudio.app`.
  Run `scripts/sign_mobile_ios.py` or the protected owner workflow after supplying
  its documented environment secrets. Install through supported Xcode/device
  tooling or Apple Configurator for registered devices.
- **Local Xcode Personal Team installation**: sign into the owner's own Apple
  Account in Xcode, select that Personal Team in Signing & Capabilities, connect
  the iPhone, enable Developer Mode when requested and Run. Resolve bundle-ID
  ownership in Xcode explicitly; changing the bundle ID creates a separate app
  container. Back up before switching identities. No account is created by tools.

Apple's current [account overview](https://developer.apple.com/help/account/basics/about-your-developer-account)
states that Personal Team device provisioning expires **7 days** after issuance.
The app then needs a renewed development build/profile; GitHub hosting does not
remove the expiry. Ad Hoc limits and device registration are documented in
[Apple's registered-device distribution guide](https://developer.apple.com/documentation/xcode/distributing-your-app-to-registered-devices)
and [Ad Hoc profile instructions](https://developer.apple.com/help/account/provisioning-profiles/create-an-ad-hoc-provisioning-profile).
No App Store, TestFlight, third-party signing service or paid AnkiMobile purchase
is required by the application. A normal signed update preserves the app's data
container; deleting the app removes its private data unless separately backed up.

## Audio and licenses

Platform MP3 decoders produce sequential mono 44.1 kHz PCM; a shared C library
applies one phrase-wide RMS gain (target -18 dBFS, -1 dBFS peak ceiling), then LAME
encodes a genuine MP3. This preserves recording order. It is not TTS, byte
concatenation or renamed AAC. The loudness method differs from desktop FFmpeg's
EBU R128 `loudnorm`; it should be assessed by listening on real devices.

LAME 4.0 comes from the repository's pinned source/hash manifest and is built with
no frontend or decoder. Its GNU Library GPL v2-or-later license is distinct from
the application license. There are no FFmpegKit binaries or GPL FFmpeg options.
`<platform>-source-and-relink-materials.tar.gz` contains full application/native source,
exact upstream source archive, license and build settings; Android object files
are included when available. Users can rebuild/relink a modified LAME and sign
with their own credentials. Owner signing keys are not distributed. Preserve
these materials and notices with binary releases. Cambridge and WikDict data
rights are described in [data sources](../data-sources.md).

## Validation and current limits

See [readiness](readiness.md) for checks actually run and remaining gates. iOS
simulator/device/unsigned artifacts must not be listed as produced until Xcode
has successfully built them. There is no unlimited iOS background execution:
operations cancel safely when the app backgrounds and can be retried after
return. Playback stops on interruption/old-route removal/background. Long input,
font scaling, navigation and sharing need concrete accessibility/device checks.

## GitHub Releases and optional PyPI publication

`release.yml` uploads GitHub artifacts independently of PyPI. The `publish-pypi`
job stays in the same workflow for the existing Trusted Publisher registration,
but tag pushes do not publish to PyPI. For an explicitly authorized Python
publication, manually run Release against the existing `v…` tag and enable
`publish_pypi`; the default is false. Its protected `pypi` environment and OIDC
permissions are retained. Neither workflow has been dispatched by this change.

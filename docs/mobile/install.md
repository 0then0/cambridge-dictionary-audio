# Mobile builds, installation and updates

This guide covers Android and iOS source builds, CI artifacts, signing and updates.
For application usage, see [Android and iOS](https://github.com/0then0/cambridge-dictionary-audio/blob/main/docs/mobile/README.md); for regression suites,
see [Mobile testing](https://github.com/0then0/cambridge-dictionary-audio/blob/main/docs/mobile/readiness.md).

The mobile version is **1.0.0-dev**, build **1000001**. Python and browser-extension
versions are managed separately. Published downloads are listed on
[GitHub Releases](https://github.com/0then0/cambridge-dictionary-audio/releases).

## Toolchains

The repository pins the following build versions:

- Android: Kotlin 2.4.21, Gradle 9.3.1, Android Gradle Plugin 9.1.1, Compose BOM
  2026.09.00, Java 17, compile/target API 37 and minimum API 28 (Android 9).
- Native Android tools: NDK 28.2.13676358, CMake 3.22.1 and build-tools 36.0.0.
- Shared dependencies: kotlinx.serialization 1.10.0, Okio 3.16.4 and Ksoup 0.2.6.
- Android UI dependencies: activity-compose 1.12.4 and lifecycle 2.10.0.
- Apple: Xcode 26.4.1, iOS 17.0 deployment minimum, Swift language mode 5 and
  ZIPFoundation 0.9.20.
- Build scripts: Python 3.12 or later, Bash, Make and pkgconf/pkg-config.

The Gradle wrapper verifies its distribution checksum. Kotlin connects to Swift
through an Objective-C framework; SwiftUI supplies the iOS interface. Neither
mobile application embeds Python.

## Source formatting

Run these commands from the repository root. Kotlin formatting needs Java 17;
Swift formatting needs Swift 6.2 or later:

```sh
python3 scripts/format_mobile.py check
python3 scripts/format_mobile.py format
python3 scripts/format_mobile.py check --language kotlin
python3 scripts/format_mobile.py check --language swift
python3 scripts/mobile_contracts.py --check
```

`check` reports violations without editing files; `format` applies changes.
The wrapper uses ktfmt 0.64 and the official `swiftlang/swift-format` 602.0.0,
with versions and SHA-256 values in `mobile/formatters.json`. Kotlin uses four-space
indentation and Swift uses two spaces, with 100-column formatting. Settings live
in `.editorconfig`, `mobile/.editorconfig` and `mobile/.swift-format`.

Tools are cached under `build/format-tools/`. The Swift formatter is built from
its pinned source release using `mobile/swift-format.resolved`. The wrapper uses
that verified binary rather than an arbitrary formatter from PATH. Generated
`AnkiContract.kt` is checked by `mobile_contracts.py` instead of the formatter.

The reusable [formatting workflow](https://github.com/0then0/cambridge-dictionary-audio/blob/main/.github/workflows/mobile-format.yml)
runs before mobile builds and signing.

## Android

Install Java 17 and the Android SDK command-line tools, set `ANDROID_HOME`, and
install the pinned packages:

```sh
sdkmanager 'platform-tools' 'platforms;android-37.0' 'build-tools;36.0.0' \
  'ndk;28.2.13676358' 'cmake;3.22.1'
```

With pkgconf and the native build tools available, build the codec from the
repository root, then build the applications from `mobile/`:

```sh
python3 scripts/build_mobile_codec.py android-arm64-v8a
python3 scripts/build_mobile_codec.py android-armeabi-v7a
python3 scripts/build_mobile_codec.py android-x86_64
cd mobile
./gradlew :shared:jvmTest :androidApp:assembleDebug :androidApp:assembleRelease \
  :androidApp:lintDebug :androidApp:testDebugUnitTest
```

Start an Android emulator or connect a test device before running
`./gradlew :androidApp:connectedDebugAndroidTest`. See [Mobile testing](https://github.com/0then0/cambridge-dictionary-audio/blob/main/docs/mobile/readiness.md)
for coverage and optional fixtures. Android tooling is separate from the Python
CLI environment.

### Install and sign an APK

Install a debug build for testing:

```sh
adb install -r mobile/androidApp/build/outputs/apk/debug/androidApp-debug.apk
```

Run this command from the repository root. Debug APKs use a development
certificate. Unsigned Release APKs need signing before installation; the packaging
script marks them `unsigned-NOT-INSTALLABLE`.

To sign a Release build, set `ANDROID_KEYSTORE` to the absolute keystore path,
then supply `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` and
`ANDROID_KEY_PASSWORD`. Run `:androidApp:assembleRelease` from `mobile/`, then
verify the certificate from the repository root:

```sh
"$ANDROID_HOME/build-tools/36.0.0/apksigner" verify --verbose --print-certs \
  mobile/androidApp/build/outputs/apk/release/androidApp-release.apk
python3 scripts/package_mobile.py android --require-signed --output dist/mobile
```

Keep signing files and passwords outside Git. The protected
[mobile signing workflow](https://github.com/0then0/cambridge-dictionary-audio/blob/main/.github/workflows/mobile-sign.yml) accepts
`ANDROID_KEYSTORE_BASE64` and the corresponding password/alias secrets through the
`mobile-signing` environment.

For downloaded APKs, compare the SHA-256 checksum and signing-certificate
fingerprint with the release information. Open the APK on the device and follow
Android's installation prompts. Distribution requirements can vary by device and
region; consult [Android developer verification](https://developer.android.com/developer-verification)
for the applicable installation route.

Install updates over the existing app using the same application ID and signing
key. A debug-signed build cannot update an installation signed with a different
release key. Back up the collection before uninstalling: uninstalling can remove
private application data. Import and export use Android's document picker and
share sheet rather than broad storage access.

## iOS

Install the pinned Xcode version with iOS device and simulator SDKs, Java 17,
pkgconf and Python 3.12 or later. Open
`mobile/iosApp/CambridgeAudio.xcodeproj` and select the CambridgeAudio scheme.

Set `CDA_PYTHON` to the absolute path of the build-script interpreter. Xcode
prepends its bundled tools to PATH, so an explicit interpreter keeps codec builds
consistent. With uv installed, run from the repository root:

```sh
export DEVELOPER_DIR=/Applications/Xcode_26.4.1.app/Contents/Developer
uv python install 3.15
export CDA_PYTHON="$(uv python find 3.15)"
xcodebuild -project mobile/iosApp/CambridgeAudio.xcodeproj -scheme CambridgeAudio \
  -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 17' \
  -derivedDataPath build/ios-simulator -resultBundlePath build/ios-tests.xcresult \
  CODE_SIGNING_ALLOWED=NO test
xcodebuild -project mobile/iosApp/CambridgeAudio.xcodeproj -scheme CambridgeAudio \
  -configuration Release -destination 'generic/platform=iOS' \
  -derivedDataPath build/ios-device CODE_SIGNING_ALLOWED=NO build
"$CDA_PYTHON" scripts/package_mobile.py ios --output dist/mobile
```

The Xcode build phase integrates the Kotlin framework and compiles pinned LAME
sources for the selected architectures. Debug builds use the selected simulator
architecture; Release builds use the destination's supported architectures.

### Artifacts and device installation

- **Simulator `.app` archive:** run it in an iOS simulator. It cannot be installed
  on an iPhone.
- **Unsigned device `.app` archive:** requires signing and a matching provisioning
  profile. Rebuild and sign in Xcode for the intended device or distribution route.
- **Ad Hoc IPA:** install only on devices registered in its provisioning profile.
  Distribution requires the corresponding Apple Developer membership,
  certificate, private key and profile for `org.cambridgeaudio.app`.

For a Personal Team development installation, sign into Xcode with your Apple
Account, select the team in **Signing & Capabilities**, connect the iPhone and
choose **Run**. Enable Developer Mode when requested. Changing the bundle ID
creates a different application container, so export a backup before switching
identities. Personal Team provisioning expires after seven days and needs renewal;
see [Apple's account overview](https://developer.apple.com/help/account/basics/about-your-developer-account).

For Ad Hoc distribution, configure the `mobile-signing` environment with
`IOS_P12_BASE64`, `IOS_P12_PASSWORD`, `IOS_PROFILE_BASE64`, `IOS_TEAM_ID`,
`IOS_PROFILE_NAME` and `IOS_SIGNING_IDENTITY`. Run the protected signing workflow
or `scripts/sign_mobile_ios.py --output dist/mobile` using the selected Python
interpreter. The signing script archives and exports an IPA for the supplied
profile. See Apple's [registered-device distribution guide](https://developer.apple.com/documentation/xcode/distributing-your-app-to-registered-devices)
and [Ad Hoc profile instructions](https://developer.apple.com/help/account/provisioning-profiles/create-an-ad-hoc-provisioning-profile).

A signed update with the same application identity preserves its data container.
Deleting the app can remove its private data. Export a `.cda` backup beforehand.

## CI artifacts

The [Mobile checks and artifacts workflow](https://github.com/0then0/cambridge-dictionary-audio/actions/workflows/mobile.yml)
uploads `mobile-android-distributions` and `mobile-ios-distributions`. Each includes
platform archives, a signing-status manifest, checksums, installation instructions
and matching source/relink materials. Artifact names identify debug, unsigned
and simulator builds. Use the signing workflow for signed distribution artifacts.

GitHub release and optional PyPI publication are described in
[Contributing](https://github.com/0then0/cambridge-dictionary-audio/blob/main/CONTRIBUTING.md#releases).

## Audio, data and licenses

Platform decoders feed sequential mono 44.1 kHz PCM to the shared C audio library.
A phrase-wide RMS gain targets -18 dBFS with a -1 dBFS peak ceiling; LAME encodes
an MP3. Desktop synthesis uses FFmpeg's EBU R128 `loudnorm`, so the loudness methods
are different. Playback stops on audio interruption, route removal or backgrounding;
interrupted operations can be retried after returning to the app.

LAME 4.0 is built from the pinned source/hash manifest with its frontend and decoder
disabled. Its GNU Library GPL v2-or-later license is separate from the application
license. Distribute the matching `<platform>-source-and-relink-materials.tar.gz`,
which includes application/native source, the upstream archive, build settings and
available Android object files for rebuilding with a modified LAME. Signing keys
are excluded. See [Data sources](https://github.com/0then0/cambridge-dictionary-audio/blob/main/docs/data-sources.md) for Cambridge and WikDict
attribution, and [Mobile testing](https://github.com/0then0/cambridge-dictionary-audio/blob/main/docs/mobile/readiness.md#checks-before-distribution) for release checks.

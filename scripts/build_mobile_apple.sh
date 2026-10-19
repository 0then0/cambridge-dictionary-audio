#!/bin/bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
python="${CDA_PYTHON:-python3}"
cd "$repo/mobile"
./gradlew -PenableAppleTargets=true :shared:embedAndSignAppleFrameworkForXcode
cd "$repo"
codec_archives=()
for architecture in ${ARCHS:-arm64}; do
  if [[ "${PLATFORM_NAME:-iphoneos}" == "iphonesimulator" ]]; then target="ios-simulator-$architecture"; else target="ios-$architecture"; fi
  if [[ ! -f "build/mobile-codec/$target/lib/libmp3lame.a" ]]; then
    "$python" scripts/build_mobile_codec.py "$target"
  fi
  codec_archives+=("build/mobile-codec/$target/lib/libmp3lame.a")
done
output="build/mobile-codec/ios-${PLATFORM_NAME:-iphoneos}"
mkdir -p "$output/include"
xcrun lipo -create "${codec_archives[@]}" -output "$output/libmp3lame.a"
cp -R "build/mobile-codec/$target/include/lame" "$output/include/"

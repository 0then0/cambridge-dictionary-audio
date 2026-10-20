"""Package only artifacts that were actually built; label signing state explicitly."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def android(output, require_signed):
    folder = ROOT / "mobile/androidApp/build/outputs/apk"
    signed = folder / "release/androidApp-release.apk"
    unsigned = folder / "release/androidApp-release-unsigned.apk"
    candidate = signed if signed.exists() else unsigned
    if not candidate.exists():
        raise FileNotFoundError("Build :androidApp:assembleRelease first")
    sdk = Path(os.environ.get("ANDROID_HOME", ROOT / "build/mobile-tools/sdk"))
    apksigner = sdk / "build-tools/36.0.0/apksigner"
    result = subprocess.run(
        [str(apksigner), "verify", "--verbose", "--print-certs", str(candidate)],
        capture_output=True,
        text=True,
    )
    release_signed = result.returncode == 0
    if release_signed and (
        "Android Debug" in result.stdout or "androiddebugkey" in result.stdout.lower()
    ):
        raise ValueError("Debug-signed APK cannot be labelled production")
    if require_signed and not release_signed:
        raise ValueError("Owner release signing key is required")
    status = "owner-signed" if release_signed else "unsigned-NOT-INSTALLABLE"
    name = f"cambridge-audio-1.0.0-android-{status}.apk"
    shutil.copyfile(candidate, output / name)
    (output / "android-signature.txt").write_text(result.stdout + result.stderr)
    debug = folder / "debug/androidApp-debug.apk"
    if debug.exists():
        shutil.copyfile(debug, output / "cambridge-audio-1.0.0-android-debug-TEST-ONLY.apk")
    return {
        "platform": "android",
        "release_signing": status,
        "release_sha256": checksum(output / name),
        "application_id": "org.cambridgeaudio.app",
        "version_name": "1.0.0",
        "version_code": 1000002,
    }


def ios(output):
    simulator = ROOT / "build/ios-simulator/Build/Products/Debug-iphonesimulator/CambridgeAudio.app"
    device = ROOT / "build/ios-device/Build/Products/Release-iphoneos/CambridgeAudio.app"
    if not simulator.is_dir() or not device.is_dir():
        raise FileNotFoundError("Build simulator and unsigned device apps with Xcode first")
    for label, source in [
        ("simulator-NOT-FOR-DEVICE", simulator),
        ("device-unsigned-REQUIRES-SIGNING", device),
    ]:
        with tarfile.open(output / f"cambridge-audio-1.0.0-ios-{label}.tar.gz", "w:gz") as archive:
            archive.add(source, arcname=source.name)
    return {
        "platform": "ios",
        "simulator": "not installable on devices",
        "device": "unsigned; re-sign or rebuild with an owner provisioning profile",
        "bundle_id": "org.cambridgeaudio.app",
    }


def materials(output, platform):
    # All application/native source needed to relink against a modified LAME,
    # exact upstream source tarball, license and recorded cross-compile settings.
    source = ROOT / "build/mobile-codec/downloads"
    archives = list(source.glob("lame-*.tar.gz"))
    if not archives:
        raise FileNotFoundError("Missing required matching LAME source distribution")
    with tarfile.open(output / f"{platform}-source-and-relink-materials.tar.gz", "w:gz") as archive:
        for path in [
            ROOT / "mobile",
            ROOT / "contracts",
            ROOT / "LICENSE",
            ROOT / "LICENSE-MIT",
            ROOT / "NOTICE",
            ROOT / "packaging/ffmpeg-sources.json",
        ]:

            def exclude(info):
                parts = Path(info.name).parts
                return (
                    None
                    if any(
                        p
                        in {
                            "build",
                            ".gradle",
                            ".kotlin",
                            ".cxx",
                            ".externalNativeBuild",
                            ".build",
                            ".swiftpm",
                            "DerivedData",
                            "xcuserdata",
                        }
                        for p in parts
                    )
                    or Path(info.name).name in {"local.properties", ".DS_Store"}
                    or Path(info.name).suffix
                    in {
                        ".jks",
                        ".keystore",
                        ".p12",
                        ".pfx",
                        ".p8",
                        ".mobileprovision",
                        ".provisionprofile",
                        ".xcarchive",
                        ".xcresult",
                        ".dSYM",
                        ".apk",
                        ".aab",
                        ".ipa",
                    }
                    or Path(info.name).name.startswith(".env")
                    else info
                )

            archive.add(path, arcname=str(path.relative_to(ROOT)), filter=exclude)
        for path in (ROOT / "scripts").glob("*mobile*"):
            if path.is_file():
                archive.add(path, arcname=str(path.relative_to(ROOT)))
        for path in archives:
            archive.add(path, arcname="upstream/" + path.name)
        for path in (ROOT / "build/mobile-codec").glob("*/build-materials.json"):
            archive.add(path, arcname="build-materials/" + path.parent.name + ".json")
        native_build = ROOT / "mobile/androidApp/.cxx"
        if native_build.exists():
            for path in native_build.rglob("*.o"):
                archive.add(path, arcname="relink-objects/" + str(path.relative_to(native_build)))
    shutil.copyfile(ROOT / "docs/mobile/install.md", output / f"{platform}-INSTALL.md")


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("platform", choices=["android", "ios"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-signed", action="store_true")
    args = parser.parse_args()
    output = args.output.absolute()
    output.mkdir(parents=True, exist_ok=True)
    result = android(output, args.require_signed) if args.platform == "android" else ios(output)
    materials(output, args.platform)
    (output / f"{args.platform}-artifacts.json").write_text(json.dumps(result, indent=2) + "\n")
    lines = [
        f"{checksum(p)}  {p.name}"
        for p in sorted(output.iterdir())
        if p.is_file() and not p.name.endswith("SHA256SUMS.txt")
    ]
    (output / f"{args.platform}-SHA256SUMS.txt").write_text("\n".join(lines) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

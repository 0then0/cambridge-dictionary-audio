"""Owner-invoked Ad Hoc signing, isolated keychain and provisioning cleanup."""

import argparse
import base64
import os
import plistlib
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from package_mobile import checksum, materials

ROOT = Path(__file__).resolve().parents[1]


def run(args):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)


def sign(output):
    names = [
        "IOS_P12_BASE64",
        "IOS_P12_PASSWORD",
        "IOS_PROFILE_BASE64",
        "IOS_TEAM_ID",
        "IOS_PROFILE_NAME",
        "IOS_SIGNING_IDENTITY",
    ]
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise ValueError("Missing owner signing credentials: " + ", ".join(missing))
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="cambridge-sign-") as temp:
        folder = Path(temp)
        p12, profile = folder / "owner.p12", folder / "owner.mobileprovision"
        p12.write_bytes(base64.b64decode(os.environ["IOS_P12_BASE64"], validate=True))
        profile.write_bytes(base64.b64decode(os.environ["IOS_PROFILE_BASE64"], validate=True))
        p12.chmod(0o600)
        decoded = plistlib.loads(
            subprocess.check_output(["security", "cms", "-D", "-i", str(profile)])
        )
        if not decoded.get("ProvisionedDevices") or decoded.get("ProvisionsAllDevices"):
            raise ValueError("Provide an Ad Hoc profile for explicitly registered devices")
        expected = os.environ["IOS_TEAM_ID"] + ".org.cambridgeaudio.app"
        if decoded.get("Entitlements", {}).get("application-identifier") != expected:
            raise ValueError("Provisioning profile must match the stable bundle ID and owner team")
        if decoded.get("Entitlements", {}).get("get-task-allow"):
            raise ValueError("Provide an Ad Hoc distribution profile, not development")
        if decoded.get("Name") != os.environ["IOS_PROFILE_NAME"]:
            raise ValueError("Provisioning profile name differs from IOS_PROFILE_NAME")
        profiles = Path.home() / "Library/MobileDevice/Provisioning Profiles"
        profiles.mkdir(parents=True, exist_ok=True)
        installed = profiles / (decoded["UUID"] + ".mobileprovision")
        previous = installed.read_bytes() if installed.exists() else None
        keychain = folder / "owner.keychain-db"
        password = uuid4().hex
        try:
            shutil.copyfile(profile, installed)
            run(["security", "create-keychain", "-p", password, keychain])
            run(["security", "unlock-keychain", "-p", password, keychain])
            run(
                [
                    "security",
                    "import",
                    p12,
                    "-k",
                    keychain,
                    "-P",
                    os.environ["IOS_P12_PASSWORD"],
                    "-T",
                    "/usr/bin/codesign",
                ]
            )
            run(
                [
                    "security",
                    "set-key-partition-list",
                    "-S",
                    "apple-tool:,apple:,codesign:",
                    "-s",
                    "-k",
                    password,
                    keychain,
                ]
            )
            archive = folder / "CambridgeAudio.xcarchive"
            run(
                [
                    "xcodebuild",
                    "-project",
                    "mobile/iosApp/CambridgeAudio.xcodeproj",
                    "-scheme",
                    "CambridgeAudio",
                    "-configuration",
                    "Release",
                    "-destination",
                    "generic/platform=iOS",
                    "-archivePath",
                    archive,
                    "CODE_SIGN_STYLE=Manual",
                    "DEVELOPMENT_TEAM=" + os.environ["IOS_TEAM_ID"],
                    "CODE_SIGN_IDENTITY=" + os.environ["IOS_SIGNING_IDENTITY"],
                    "PROVISIONING_PROFILE_SPECIFIER=" + os.environ["IOS_PROFILE_NAME"],
                    "OTHER_CODE_SIGN_FLAGS=--keychain " + str(keychain),
                    "archive",
                ]
            )
            options = folder / "ExportOptions.plist"
            options.write_bytes(
                plistlib.dumps(
                    {
                        "method": "release-testing",
                        "teamID": os.environ["IOS_TEAM_ID"],
                        "signingStyle": "manual",
                        "provisioningProfiles": {
                            "org.cambridgeaudio.app": os.environ["IOS_PROFILE_NAME"]
                        },
                    }
                )
            )
            run(
                [
                    "xcodebuild",
                    "-exportArchive",
                    "-archivePath",
                    archive,
                    "-exportOptionsPlist",
                    options,
                    "-exportPath",
                    output,
                ]
            )
            (output / "SIGNING-STATUS.txt").write_text(
                "Signed Ad Hoc IPA: only devices registered in the supplied profile. "
                "Not universal public installation.\n"
            )
            materials(output, "ios")
            (output / "ios-SHA256SUMS.txt").write_text(
                "\n".join(
                    f"{checksum(path)}  {path.name}"
                    for path in sorted(output.iterdir())
                    if path.is_file() and not path.name.endswith("SHA256SUMS.txt")
                )
                + "\n"
            )
        finally:
            subprocess.run(
                ["security", "delete-keychain", str(keychain)], check=False, capture_output=True
            )
            if previous is None:
                installed.unlink(missing_ok=True)
            else:
                installed.write_bytes(previous)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sign(args.output.absolute())

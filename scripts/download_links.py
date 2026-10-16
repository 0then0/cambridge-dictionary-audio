"""Verify the latest stable release and refresh direct README download buttons."""

import argparse
import json
import re
from base64 import b64encode
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com/repos/0then0/cambridge-dictionary-audio/releases/latest"
SNAPSHOT = ROOT / "packaging/downloads.json"


def assets_for(release):
    if release.get("draft") or release.get("prerelease"):
        raise ValueError("Downloads must point to a published stable release.")
    tag = release["tag_name"]
    version = tag.removeprefix("v")
    base = f"cambridge-dictionary-audio-{version}"
    names = [
        (
            "Windows x86-64",
            [f"{base}-windows-x86_64-setup.exe", f"{base}-windows-x86_64-portable.zip"],
        ),
        (
            "macOS 14+ Apple Silicon",
            [f"{base}-macos-arm64.pkg", f"{base}-macos-arm64.dmg", f"{base}-macos-arm64.tar.gz"],
        ),
        (
            "macOS 14+ Intel",
            [f"{base}-macos-x86_64.pkg", f"{base}-macos-x86_64.dmg", f"{base}-macos-x86_64.tar.gz"],
        ),
        (
            "Linux x86-64, glibc 2.34+",
            [
                f"cambridge-dictionary-audio_{version}_amd64.deb",
                f"{base}-1.x86_64.rpm",
                f"{base}-linux-x86_64-portable.tar.gz",
            ],
        ),
        (
            "Python CLI",
            [
                f"cambridge_dictionary_audio-{version}-py3-none-any.whl",
                f"cambridge_dictionary_audio-{version}.tar.gz",
            ],
        ),
        (
            "Chrome / Firefox",
            [f"cambridge-audio-chrome-{version}.zip", f"cambridge-audio-firefox-{version}.zip"],
        ),
        ("SHA-256", ["SHA256SUMS.txt"]),
    ]
    assets = {a["name"]: a for a in release["assets"]}
    groups = []
    for label, filenames in names:
        group = []
        for name in filenames:
            asset = assets[name]
            url = asset["browser_download_url"]
            if (
                not url.endswith(f"/releases/download/{tag}/{name}")
                or asset["size"] <= 0
                or asset.get("state", "uploaded") != "uploaded"
            ):
                raise ValueError(f"Invalid release artifact: {name}")
            group.append((name, url))
        groups.append((label, group))
    return groups


# The named Windows logo is absent from Shields' Simple Icons collection.
# Embed the four-pane mark through Shields' documented custom SVG logo support.
WINDOWS_LOGO = "data:image/svg+xml;base64," + b64encode(
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    b'<path fill="white" d="M1 1h10v10H1zM13 1h10v10H13zM1 13h10v10H1zM13 13h10v10H13z"/>'
    b"</svg>"
).decode("ascii")


def render(release, russian=False):
    groups = assets_for(release)
    version = release["tag_name"]
    heading = (
        f"Прямое скачивание последнего проверенного стабильного релиза **{version}**:"
        if russian
        else f"Direct downloads for the latest verified stable release **{version}**:"
    )
    any_arch = "Любая" if russian else "Any"
    rows = [
        ("Windows 10+", "x86-64", groups[0][1], "0078D4", WINDOWS_LOGO),
        ("macOS 14+", "Apple Silicon (arm64)", groups[1][1], "555555", "apple"),
        ("macOS 14+", "Intel (x86-64)", groups[2][1], "555555", "apple"),
        ("Linux", "x86-64 · glibc 2.34+", groups[3][1], "FCC624", "linux"),
        ("Python CLI", any_arch, groups[4][1], "3776AB", "python"),
        ("Chrome", any_arch, groups[5][1][:1], "4285F4", "googlechrome"),
        ("Firefox", any_arch, groups[5][1][1:], "FF7139", "firefoxbrowser"),
    ]
    headers = (
        "| Платформа | Архитектура | Скачать |"
        if russian
        else "| Platform | Architecture | Download |"
    )
    lines = [heading, "", headers, "| --- | --- | --- |"]
    for platform, architecture, assets, color, logo in rows:
        buttons = []
        for name, url in assets:
            label = (
                "EXE"
                if name.endswith(".exe")
                else "Portable ZIP"
                if name.endswith("-portable.zip")
                else "Portable TAR.GZ"
                if "-portable.tar.gz" in name
                else "Source TAR.GZ"
                if name.startswith("cambridge_dictionary_audio-") and name.endswith(".tar.gz")
                else "TAR.GZ"
                if name.endswith(".tar.gz")
                else name.rsplit(".", 1)[-1].upper()
            )
            query = urlencode({"style": "for-the-badge", "logo": logo, "logoColor": "white"})
            badge = f"https://img.shields.io/badge/{quote(label, safe='')}-{color}?{query}"
            buttons.append(f"[![{platform} {architecture} {label}]({badge})]({url})")
        lines.append(f"| {platform} | {architecture} | " + " ".join(buttons) + " |")
    checksum = "https://img.shields.io/badge/SHA--256-SHA256SUMS.txt-555555?style=flat-square"
    lines.extend(["", f"[![SHA-256]({checksum})]({groups[6][1][0][1]})"])
    return "\n".join(lines)


def refresh(release):
    assets_for(release)
    snapshot = {
        "tag_name": release["tag_name"],
        "draft": False,
        "prerelease": False,
        "assets": [
            {k: a[k] for k in ("name", "size", "browser_download_url", "state")}
            for a in release["assets"]
        ],
    }
    SNAPSHOT.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    for filename, russian in (("README.md", False), ("README.ru.md", True)):
        path = ROOT / filename
        start, end = "<!-- downloads:start -->", "<!-- downloads:end -->"
        text = path.read_text(encoding="utf-8")
        replacement = start + "\n" + render(release, russian) + "\n" + end
        text, count = re.subn(
            re.escape(start) + r".*?" + re.escape(end),
            lambda _, replacement=replacement: replacement,
            text,
            flags=re.S,
        )
        if count != 1:
            raise ValueError(f"Expected one download marker in {filename}")
        path.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh", action="store_true", help="Refresh the snapshot and both READMEs."
    )
    parser.add_argument(
        "--verify-network", action="store_true", help="Verify direct artifact URLs too."
    )
    args = parser.parse_args()
    with urlopen(
        Request(API, headers={"User-Agent": "cambridge-audio-download-check"}), timeout=30
    ) as response:
        release = json.load(response)
    groups = assets_for(release)
    if args.refresh:
        refresh(release)
    else:
        saved = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        if assets_for(saved) != groups:
            raise ValueError("A newer stable release is available. Run with --refresh.")
    if args.verify_network:
        for _, group in groups:
            for name, url in group:
                with urlopen(Request(url, method="HEAD"), timeout=30) as response:
                    if response.status != 200:
                        raise ValueError(f"Download unavailable: {url}")
                print(f"OK {name}")
    print(
        f"Verified {release['tag_name']} release assets; "
        "README buttons download matching files directly"
    )


if __name__ == "__main__":
    main()

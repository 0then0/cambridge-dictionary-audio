"""Refresh pinned README downloads from the latest published stable GitHub release."""

import argparse
import json
import re
from pathlib import Path
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


def render(release, russian=False):
    groups = assets_for(release)
    version = release["tag_name"]
    heading = (
        f"Прямые ссылки на опубликованную стабильную версию **{version}**:"
        if russian
        else f"Direct downloads for published stable **{version}**:"
    )
    # The snapshot version and asset URLs stay pinned together across future releases.
    lines = [heading, ""]
    for label, group in groups:
        links = []
        for name, url in group:
            extension = next(
                (
                    s
                    for s in (
                        "-setup.exe",
                        "-portable.zip",
                        ".tar.gz",
                        ".whl",
                        ".pkg",
                        ".dmg",
                        ".deb",
                        ".rpm",
                        ".zip",
                        ".txt",
                    )
                    if name.endswith(s)
                ),
                name,
            )
            title = (
                "Chrome ZIP"
                if "chrome-" in name
                else "Firefox ZIP"
                if "firefox-" in name
                else "SHA256SUMS.txt"
                if name == "SHA256SUMS.txt"
                else extension.lstrip("-")
            )
            links.append(f"[{title}]({url})")
        lines.append(f"- {label}: " + ", ".join(links) + ".")
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
        text = path.read_text()
        replacement = start + "\n" + render(release, russian) + "\n" + end
        text, count = re.subn(
            re.escape(start) + r".*?" + re.escape(end),
            lambda _, replacement=replacement: replacement,
            text,
            flags=re.S,
        )
        if count != 1:
            raise ValueError(f"Expected one download marker in {filename}")
        path.write_text(text)


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
        saved = json.loads(SNAPSHOT.read_text())
        if assets_for(saved) != groups:
            raise ValueError("A newer stable release is available. Run with --refresh.")
    if args.verify_network:
        for _, group in groups:
            for name, url in group:
                with urlopen(Request(url, method="HEAD"), timeout=30) as response:
                    if response.status != 200:
                        raise ValueError(f"Download unavailable: {url}")
                print(f"OK {name}")
    print(f"Verified {release['tag_name']} release assets and pinned download links")


if __name__ == "__main__":
    main()

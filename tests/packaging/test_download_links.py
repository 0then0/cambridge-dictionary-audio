import copy
import io
import json
import re
import sys
from base64 import b64decode
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

import pytest
from markdown_it import MarkdownIt

from scripts import download_links


def test_both_readmes_have_direct_format_buttons_for_verified_release_assets():
    release = json.loads(download_links.SNAPSHOT.read_text(encoding="utf-8"))
    assets = {url for _, group in download_links.assets_for(release) for _, url in group}
    assert len(assets) == 20
    for filename, russian in (("README.md", False), ("README.ru.md", True)):
        text = (download_links.ROOT / filename).read_text(encoding="utf-8")
        block = text.split("<!-- downloads:start -->")[1].split("<!-- downloads:end -->")[0].strip()
        markdown = MarkdownIt().enable("table")
        assert markdown.render(block) == markdown.render(download_links.render(release, russian))
        urls = set(re.findall(r"\]\((https://github.com/[^)]+)\)", block))
        assert urls == assets
        assert len(re.findall(r"!\[[^\]]+\]\(https://img.shields.io/", block)) == 20
        assert len([line for line in block.splitlines() if line.startswith("| ")]) == 11
        assert release["tag_name"] in block
        assert "/releases/latest" not in block
        rows = [line for line in block.splitlines() if line.startswith("| ")]
        assert all(
            "windows-x86_64" in url
            for url in re.findall(r"\]\((https://github.com/[^)]+)\)", rows[2])
        )
        assert all(
            "macos-arm64" in url for url in re.findall(r"\]\((https://github.com/[^)]+)\)", rows[3])
        )
        assert all(
            "macos-x86_64" in url
            for url in re.findall(r"\]\((https://github.com/[^)]+)\)", rows[4])
        )
        for platform, filenames in (
            ("Android 9+", ("-debug-TEST-ONLY.apk", "-unsigned-NOT-INSTALLABLE.apk")),
            (
                "iOS 17+",
                (
                    "-device-unsigned-REQUIRES-SIGNING.tar.gz",
                    "-simulator-NOT-FOR-DEVICE.tar.gz",
                ),
            ),
        ):
            row = next(line for line in rows if line.startswith(f"| {platform} |"))
            links = re.findall(r"\]\((https://github.com/[^)]+)\)", row)
            assert len(links) == 2
            assert all(any(url.endswith(name) for url in links) for name in filenames)
        assert "docs/mobile/install.md" in block
        assert text.index('src="assets/icon.svg"') < text.index("<!-- downloads:start -->")


def test_refresh_renders_matching_versioned_urls_for_a_future_release():
    release = json.loads(download_links.SNAPSHOT.read_text(encoding="utf-8"))
    future = copy.deepcopy(release)
    old = release["tag_name"].removeprefix("v")
    future["tag_name"] = "v999.0.0"
    for asset in future["assets"]:
        for field in ("name", "browser_download_url"):
            asset[field] = asset[field].replace(old, "999.0.0")
    for russian in (False, True):
        table = download_links.render(future, russian)
        urls = set(re.findall(r"\]\((https://github.com/[^)]+)\)", table))
        assert urls == {url for _, group in download_links.assets_for(future) for _, url in group}
        assert "v999.0.0" in table and f"/download/{release['tag_name']}/" not in table


def test_refresh_validation_rejects_missing_assets_and_unpublished_releases():
    release = json.loads(download_links.SNAPSHOT.read_text(encoding="utf-8"))
    for key in ("prerelease", "draft"):
        other = copy.deepcopy(release)
        other[key] = True
        with pytest.raises(ValueError):
            download_links.assets_for(other)
    release["assets"] = [asset for asset in release["assets"] if asset["name"] != "SHA256SUMS.txt"]
    with pytest.raises(KeyError):
        download_links.assets_for(release)


def test_refresh_preserves_utf8_documentation_outside_download_block(tmp_path, monkeypatch):
    release = json.loads(download_links.SNAPSHOT.read_text(encoding="utf-8"))
    monkeypatch.setattr(download_links, "ROOT", tmp_path)
    snapshot = tmp_path / "downloads.json"
    monkeypatch.setattr(download_links, "SNAPSHOT", snapshot)
    before = "# Произношение и перевод\n\n"
    after = "\n\nПример: привет, солнце.\n"
    for filename in ("README.md", "README.ru.md"):
        (tmp_path / filename).write_text(
            before + "<!-- downloads:start -->\nold\n<!-- downloads:end -->" + after,
            encoding="utf-8",
        )

    download_links.refresh(release)

    for filename, russian in (("README.md", False), ("README.ru.md", True)):
        content = (tmp_path / filename).read_text(encoding="utf-8")
        assert content == (
            before
            + "<!-- downloads:start -->\n"
            + download_links.render(release, russian)
            + "\n<!-- downloads:end -->"
            + after
        )
    assert json.loads(snapshot.read_bytes()) == release


def test_verification_reports_when_pinned_buttons_need_a_release_refresh(monkeypatch):
    release = json.loads(download_links.SNAPSHOT.read_text(encoding="utf-8"))
    old = release["tag_name"].removeprefix("v")
    release["tag_name"] = "v999.0.0"
    for asset in release["assets"]:
        for field in ("name", "browser_download_url"):
            asset[field] = asset[field].replace(old, "999.0.0")
    monkeypatch.setattr(sys, "argv", ["download_links.py"])
    monkeypatch.setattr(
        download_links,
        "urlopen",
        lambda *a, **kw: io.BytesIO(json.dumps(release).encode("utf-8")),
    )
    with pytest.raises(ValueError, match="newer stable release"):
        download_links.main()


def test_windows_buttons_embed_a_valid_custom_icon():
    release = json.loads(download_links.SNAPSHOT.read_text(encoding="utf-8"))
    row = download_links.render(release).splitlines()[4]
    badges = re.findall(r"!\[[^\]]+\]\((https://img.shields.io/[^)]+)\)", row)
    assert len(badges) == 2
    for badge in badges:
        logo = parse_qs(urlparse(badge).query)["logo"][0]
        assert logo.startswith("data:image/svg+xml;base64,")
        svg = ElementTree.fromstring(b64decode(logo.split(",", 1)[1]))
        assert svg.tag == "{http://www.w3.org/2000/svg}svg"
        assert svg.find("{http://www.w3.org/2000/svg}path").attrib["d"]

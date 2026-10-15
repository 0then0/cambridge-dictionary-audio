import copy
import json
import re

import pytest

from scripts import download_links


def test_both_readmes_match_verified_release_assets():
    release = json.loads(download_links.SNAPSHOT.read_text(encoding="utf-8"))
    assets = {url for _, group in download_links.assets_for(release) for _, url in group}
    assert len(assets) == 16
    for filename, russian in (("README.md", False), ("README.ru.md", True)):
        text = (download_links.ROOT / filename).read_text(encoding="utf-8")
        block = text.split("<!-- downloads:start -->")[1].split("<!-- downloads:end -->")[0].strip()
        assert block == download_links.render(release, russian)
        urls = set(re.findall(r"\]\((https://github.com/[^)]+/releases/download/[^)]+)\)", block))
        assert urls == assets
        assert "/latest/download/" not in text
        assert text.index('src="assets/icon.svg"') < text.index("<!-- downloads:start -->")


def test_refresh_validation_rejects_missing_assets_and_unpublished_releases():
    release = json.loads(download_links.SNAPSHOT.read_text(encoding="utf-8"))
    for key in ("prerelease", "draft"):
        other = copy.deepcopy(release)
        other[key] = True
        with pytest.raises(ValueError):
            download_links.assets_for(other)
    release["assets"].pop(0)
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

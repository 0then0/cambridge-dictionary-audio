import copy
import json
import re

import pytest

from scripts import download_links


def test_both_readmes_match_verified_release_assets():
    release = json.loads(download_links.SNAPSHOT.read_text())
    assets = {url for _, group in download_links.assets_for(release) for _, url in group}
    assert len(assets) == 16
    for filename, russian in (("README.md", False), ("README.ru.md", True)):
        text = (download_links.ROOT / filename).read_text()
        block = text.split("<!-- downloads:start -->")[1].split("<!-- downloads:end -->")[0].strip()
        assert block == download_links.render(release, russian)
        urls = set(re.findall(r"\]\((https://github.com/[^)]+/releases/download/[^)]+)\)", block))
        assert urls == assets
        assert "/latest/download/" not in text
        assert text.index('src="assets/icon.svg"') < text.index("<!-- downloads:start -->")


def test_refresh_validation_rejects_missing_assets_and_unpublished_releases():
    release = json.loads(download_links.SNAPSHOT.read_text())
    for key in ("prerelease", "draft"):
        other = copy.deepcopy(release)
        other[key] = True
        with pytest.raises(ValueError):
            download_links.assets_for(other)
    release["assets"].pop(0)
    with pytest.raises(KeyError):
        download_links.assets_for(release)

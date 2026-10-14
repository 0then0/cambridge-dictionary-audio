"""Protect artifact integrity and the installer paths used by native launchers."""

import hashlib
import importlib.metadata
import plistlib
import tarfile

import pytest
from packaging.version import Version

from scripts import package_desktop, release


def test_version_tag_must_match_package_metadata(monkeypatch):
    version = importlib.metadata.version("cambridge-dictionary-audio")
    monkeypatch.setenv("GITHUB_REF_TYPE", "tag")
    monkeypatch.setenv("GITHUB_REF_NAME", f"v{version}")
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    release.validate()
    monkeypatch.setenv("GITHUB_REF_NAME", "v0.0.0")
    with pytest.raises(ValueError, match="must match"):
        release.validate()


def test_version_outputs_mark_prereleases(tmp_path, monkeypatch):
    monkeypatch.setattr(release.importlib.metadata, "version", lambda name: "0.3.0rc1")
    monkeypatch.setenv("GITHUB_REF_TYPE", "tag")
    monkeypatch.setenv("GITHUB_REF_NAME", "v0.3.0rc1")
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    release.validate()
    assert output.read_text().splitlines() == ["version=0.3.0rc1", "prerelease=true"]


def test_checksums_cover_every_artifact_and_ignore_previous_checksum_file(tmp_path):
    files = {"app.pkg": b"installer", "cli.whl": b"wheel"}
    for name, content in files.items():
        (tmp_path / name).write_bytes(content)
    (tmp_path / "SHA256SUMS.txt").write_text("outdated")
    release.checksums(tmp_path)
    expected = [f"{hashlib.sha256(content).hexdigest()}  {name}" for name, content in files.items()]
    assert (tmp_path / "SHA256SUMS.txt").read_text().splitlines() == expected


@pytest.mark.parametrize(
    "version,expected",
    [
        ("0.2.0", "0.2.0"),
        ("0.3.0rc1", "0.3.0~rc1"),
        ("0.3.0.dev1", "0.3.0~dev1"),
        ("0.2.0.post1", "0.2.0+post1"),
    ],
)
def test_linux_prereleases_sort_before_stable(version, expected):
    assert package_desktop.linux_version(Version(version)) == expected


def test_linux_payload_and_installer_metadata_are_consistent(tmp_path, monkeypatch):
    monkeypatch.setattr(package_desktop, "ROOT", tmp_path)
    output = tmp_path / "dist/installers"
    output.mkdir(parents=True)
    monkeypatch.setattr(package_desktop, "OUTPUT", output)
    monkeypatch.setattr(package_desktop.platform, "machine", lambda: "x86_64")
    frozen = tmp_path / "dist/desktop" / package_desktop.NAME
    frozen.mkdir(parents=True)
    binary = frozen / package_desktop.NAME
    binary.write_bytes(b"binary")
    binary.chmod(0o755)
    for relative in ("packaging/linux.desktop", "assets/icon.svg", "build/icon.png"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"asset")
    commands = []

    def run(*command):
        commands.append(command)
        if command[0] == "dpkg-deb":
            control = (tmp_path / "build/linux-root/DEBIAN/control").read_text()
            assert "Version: 0.3.0~rc1" in control
            assert "Architecture: amd64" in control
            assert "libc6 (>= 2.34)" in control
        if command[0] == "rpmbuild":
            spec = (tmp_path / "build/rpm/SPECS/desktop.spec").read_text()
            assert "Version: 0.3.0~rc1" in spec
            assert "/usr/bin/cambridge-audio-gui" in spec

    monkeypatch.setattr(package_desktop, "run", run)
    package_desktop.linux(Version("0.3.0rc1"))
    launcher = tmp_path / "build/linux-root/usr/bin/cambridge-audio-gui"
    assert (
        'exec "/opt/cambridge-dictionary-audio/Cambridge Dictionary Audio" "$@"'
        in launcher.read_text()
    )
    assert launcher.stat().st_mode & 0o111
    assert [command[0] for command in commands] == ["dpkg-deb", "rpmbuild"]
    with tarfile.open(next(output.glob("*.tar.gz"))) as stream:
        assert stream.getmember(f"{package_desktop.NAME}/{package_desktop.NAME}").mode & 0o111


def test_macos_installer_cannot_relocate_to_a_cached_source_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(package_desktop, "ROOT", tmp_path)
    output = tmp_path / "dist/installers"
    output.mkdir(parents=True)
    monkeypatch.setattr(package_desktop, "OUTPUT", output)
    app = tmp_path / "dist/desktop" / f"{package_desktop.NAME}.app"
    app.mkdir(parents=True)
    staging = tmp_path / "build/macos-root"
    staging.mkdir(parents=True)
    (staging / "obsolete").write_text("stale payload")
    commands = []

    def run(*command):
        commands.append(command)
        if command[:2] == ("pkgbuild", "--analyze"):
            command[-1].write_bytes(
                plistlib.dumps(
                    [
                        {
                            "RootRelativeBundlePath": app.name,
                            "BundleIsRelocatable": True,
                        }
                    ]
                )
            )
        if command[:2] == ("pkgbuild", "--root"):
            data = plistlib.loads((tmp_path / "build/macos-components.plist").read_bytes())
            assert all(not item["BundleIsRelocatable"] for item in data)
            index = command.index("--install-location")
            assert command[index + 1] == "/Applications"

    monkeypatch.setattr(package_desktop, "run", run)
    package_desktop.macos(Version("0.2.0"))
    assert len(commands) == 3
    assert not (staging / "obsolete").exists()


def test_ffmpeg_source_checksum_failure_stops_build(tmp_path):
    from scripts.build_ffmpeg import download

    (tmp_path / "source.tar.xz").write_bytes(b"corrupted archive")
    source = {"url": "https://example.invalid/source.tar.xz", "sha256": "0" * 64}
    with pytest.raises(ValueError, match="checksum mismatch"):
        download(source, tmp_path)


def test_ffmpeg_verified_source_cache_needs_no_network(tmp_path, monkeypatch):
    from scripts import build_ffmpeg

    content = b"verified source"
    source = {
        "url": "https://example.invalid/source.tar.xz",
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    path = tmp_path / "source.tar.xz"
    path.write_bytes(content)

    def unexpected_download(*args, **kwargs):
        raise AssertionError("Valid cached sources should not be downloaded")

    monkeypatch.setattr(build_ffmpeg.urllib.request, "urlopen", unexpected_download)
    assert build_ffmpeg.download(source, tmp_path) == path

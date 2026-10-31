"""Collection backups never replace a file without explicit permission."""

import errno
import hashlib
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from cambridge_audio import bundle
from cambridge_audio.bundle import BundleExistsError, _load_bundle, export_bundle
from tests.core.test_bundle import collection

ROOT = Path(__file__).parents[2]
EXCLUSIVE = "rename" if os.name == "nt" else "link"
FOREIGN = b"PK-not-really: a thesis someone typed by hand\n"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def only(parent, *names):
    """No temporary file may survive next to the destination."""
    assert sorted(p.name for p in parent.iterdir()) == sorted(names)


@pytest.fixture
def source(client, tmp_path):
    collection(client, tmp_path / "source")
    return tmp_path / "source"


@pytest.fixture
def out(tmp_path):
    folder = tmp_path / "out"
    folder.mkdir()
    return folder


def test_export_to_new_path_publishes_a_valid_archive_and_no_temporary(source, out):
    destination = out / "backup.cda"
    assert export_bundle(source, destination) == destination
    _, records, mapping = _load_bundle(destination)
    assert len(records) == 2 and mapping["notes"]
    only(out, "backup.cda")


def test_export_creates_missing_parent_folder(source, out):
    destination = out / "new" / "folder" / "backup.cda"
    export_bundle(source, destination)
    _load_bundle(destination)


def test_existing_foreign_file_is_kept_without_permission(source, out):
    destination = out / "thesis.docx"
    destination.write_bytes(FOREIGN)
    with pytest.raises(BundleExistsError, match="not replaced") as error:
        export_bundle(source, destination)
    assert isinstance(error.value, FileExistsError) and error.value.path == destination
    assert destination.read_bytes() == FOREIGN
    only(out, "thesis.docx")


def test_existing_valid_archive_is_kept_and_still_readable(source, out):
    destination = out / "backup.cda"
    export_bundle(source, destination)
    before = digest(destination)
    with pytest.raises(BundleExistsError):
        export_bundle(source, destination)
    assert digest(destination) == before
    _load_bundle(destination)
    only(out, "backup.cda")


def test_replacement_needs_permission_for_this_call_only(source, out):
    destination = out / "backup.cda"
    export_bundle(source, destination)
    export_bundle(source, destination, replace=True)
    _load_bundle(destination)
    only(out, "backup.cda")
    with pytest.raises(BundleExistsError):
        export_bundle(source, destination)


def test_replacement_keeps_previous_file_until_new_archive_is_validated(source, out, monkeypatch):
    destination = out / "thesis.docx"
    destination.write_bytes(FOREIGN)
    seen = {}
    real = bundle._publish

    def inspect(temporary, target, replace):
        seen["previous"] = target.read_bytes()
        seen["valid"] = _load_bundle(temporary)
        seen["replace"] = replace
        real(temporary, target, replace)

    monkeypatch.setattr(bundle, "_publish", inspect)
    export_bundle(source, destination, replace=True)
    assert seen["previous"] == FOREIGN and seen["replace"] is True
    assert destination.read_bytes() != FOREIGN
    _load_bundle(destination)
    only(out, "thesis.docx")


def test_empty_collection_follows_the_same_rule_over_an_existing_file(tmp_path, out):
    empty = tmp_path / "empty"
    empty.mkdir()
    destination = out / "thesis.docx"
    destination.write_bytes(FOREIGN)
    with pytest.raises(BundleExistsError):
        export_bundle(empty, destination)
    assert destination.read_bytes() == FOREIGN
    export_bundle(empty, destination, replace=True)
    assert _load_bundle(destination)[1] == {}
    only(out, "thesis.docx")


@pytest.mark.parametrize("replace", [False, True])
def test_failed_validation_keeps_previous_file_and_publishes_nothing(
    source, out, monkeypatch, replace
):
    previous = out / "previous.cda"
    previous.write_bytes(FOREIGN)
    destination = previous if replace else out / "new.cda"

    def reject(path):
        raise ValueError("Size / SHA-256 mismatch: injected")

    monkeypatch.setattr(bundle, "_load_bundle", reject)
    with pytest.raises(ValueError, match="injected"):
        export_bundle(source, destination, replace=replace)
    assert previous.read_bytes() == FOREIGN
    only(out, "previous.cda")


def test_failed_archive_preparation_keeps_previous_file_and_reason(source, out, monkeypatch):
    destination = out / "backup.cda"
    destination.write_bytes(FOREIGN)

    def full_disk(self, *args, **kwargs):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(bundle.ZipFile, "writestr", full_disk)
    with pytest.raises(OSError, match="No space") as error:
        export_bundle(source, destination, replace=True)
    assert error.value.errno == errno.ENOSPC
    assert destination.read_bytes() == FOREIGN
    only(out, "backup.cda")


def test_corrupt_source_media_fails_before_touching_the_destination(source, out):
    destination = out / "backup.cda"
    destination.write_bytes(FOREIGN)
    next(source.glob("*.mp3")).write_bytes(b"not audio")
    with pytest.raises(ValueError, match="corrupt"):
        export_bundle(source, destination, replace=True)
    assert destination.read_bytes() == FOREIGN
    only(out, "backup.cda")


def test_failed_replacement_keeps_previous_file(source, out, monkeypatch):
    destination = out / "backup.cda"
    destination.write_bytes(FOREIGN)

    def locked(source_path, target):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(bundle.os, "replace", locked)
    with pytest.raises(PermissionError):
        export_bundle(source, destination, replace=True)
    assert destination.read_bytes() == FOREIGN
    only(out, "backup.cda")


def test_unsupported_exclusive_publication_never_falls_back_to_replacing(source, out, monkeypatch):
    destination = out / "backup.cda"

    def unsupported(*args):
        raise OSError(errno.EPERM, "Operation not permitted")

    def forbidden(*args):
        raise AssertionError("must not overwrite")

    monkeypatch.setattr(bundle.os, EXCLUSIVE, unsupported)
    monkeypatch.setattr(bundle.os, "replace", forbidden)
    with pytest.raises(OSError, match="choose another location") as error:
        export_bundle(source, destination)
    assert not isinstance(error.value, FileExistsError)
    only(out)


def test_other_publication_errors_keep_their_cause(source, out, monkeypatch):
    def denied(*args):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(bundle.os, EXCLUSIVE, denied)
    with pytest.raises(PermissionError, match="Permission denied"):
        export_bundle(source, out / "backup.cda")
    only(out)


def test_destination_that_appears_after_the_export_started_is_not_replaced(
    source, out, monkeypatch
):
    destination = out / "backup.cda"
    real = bundle._load_bundle

    def writer_arrives_during_validation(path):
        result = real(path)
        destination.write_bytes(FOREIGN)
        return result

    monkeypatch.setattr(bundle, "_load_bundle", writer_arrives_during_validation)
    with pytest.raises(BundleExistsError):
        export_bundle(source, destination)
    assert destination.read_bytes() == FOREIGN
    only(out, "backup.cda")


def test_exclusive_publication_has_a_single_winner_on_the_real_filesystem(out):
    destination = out / "backup.cda"
    workers = 8
    barrier = threading.Barrier(workers)
    payloads = [f"archive {i} ".encode() * 50_000 for i in range(workers)]
    temporaries = []
    for index, payload in enumerate(payloads):
        temporary = out / f"candidate-{index}.tmp"
        temporary.write_bytes(payload)
        temporaries.append(temporary)
    results = [None] * workers

    def publish(index):
        barrier.wait()
        try:
            bundle._publish(temporaries[index], destination, False)
            results[index] = "won"
        except BundleExistsError:
            results[index] = "lost"

    threads = [threading.Thread(target=publish, args=(i,)) for i in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.count("won") == 1 and results.count("lost") == workers - 1
    assert destination.read_bytes() == payloads[results.index("won")]


def test_concurrent_cli_exports_to_one_path_leave_one_complete_archive(source, out):
    destination = out / "backup.cda"
    command = [
        sys.executable,
        "-m",
        "cambridge_audio",
        "--output-dir",
        str(source),
        "--export-collection",
        str(destination),
    ]
    processes = [
        subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(2)
    ]
    outcomes = [(p.wait(), *p.communicate()) for p in processes]
    assert sorted(code for code, *_ in outcomes) == [0, 1], outcomes
    loser = next(o for o in outcomes if o[0] == 1)
    assert b"already exists" in loser[2] and loser[1] == b""
    _load_bundle(destination)
    only(out, "backup.cda")


def test_symlink_destination_is_rejected_and_target_is_untouched(source, out):
    target = out / "precious.txt"
    target.write_bytes(FOREIGN)
    link = out / "backup.cda"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Symbolic links need extra privileges on this platform")
    for replace in (False, True):
        with pytest.raises(ValueError, match="symbolic"):
            export_bundle(source, link, replace=replace)
    assert link.is_symlink() and target.read_bytes() == FOREIGN
    only(out, "backup.cda", "precious.txt")


@pytest.mark.parametrize("replace", [False, True])
def test_folder_destination_is_rejected_and_untouched(source, out, replace):
    destination = out / "backup.cda"
    destination.mkdir()
    (destination / "keep.txt").write_bytes(FOREIGN)
    with pytest.raises(IsADirectoryError, match="folder"):
        export_bundle(source, destination, replace=replace)
    assert (destination / "keep.txt").read_bytes() == FOREIGN
    only(out, "backup.cda")


@pytest.mark.skipif(
    os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="Needs POSIX directory permissions and an unprivileged user",
)
@pytest.mark.parametrize("replace", [False, True])
def test_read_only_destination_folder_reports_permission_and_keeps_files(source, out, replace):
    previous = out / "previous.cda"
    previous.write_bytes(FOREIGN)
    destination = previous if replace else out / "new.cda"
    out.chmod(0o500)
    try:
        with pytest.raises(PermissionError):
            export_bundle(source, destination, replace=replace)
    finally:
        out.chmod(0o700)
    assert previous.read_bytes() == FOREIGN
    only(out, "previous.cda")


def test_destination_inside_the_collection_is_still_rejected(source):
    with pytest.raises(ValueError, match="outside the collection"):
        export_bundle(source, source / "backup.cda", replace=True)

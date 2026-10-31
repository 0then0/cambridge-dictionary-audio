"""Desktop collection backup: the user decides about replacement, once."""

import errno
import os
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6", reason="Install the gui group to run desktop tests")

from PySide6.QtWidgets import QMessageBox  # noqa: E402

from cambridge_audio import bundle  # noqa: E402
from cambridge_audio.gui import app as gui  # noqa: E402
from cambridge_audio.library import save_metadata  # noqa: E402
from cambridge_audio.service import Recording  # noqa: E402

FOREIGN = b"existing file that is not a backup\n"
YES, NO = QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No


@pytest.fixture
def backup(window, monkeypatch, mp3, tmp_path):
    window.output_dir.mkdir()
    path = window.output_dir / "hello.us.mp3"
    path.write_bytes(mp3)
    save_metadata(Recording("hello", "us", path, "", "greeting"))
    window.refresh_library()
    folder = tmp_path / "backups"
    folder.mkdir()
    state = type("State", (), {})()
    state.destination = folder / "backup.cda"
    state.folder = folder
    state.dialog = Mock(side_effect=lambda *a, **k: (str(state.destination), ""))
    state.confirm = Mock(return_value=NO)
    monkeypatch.setattr(gui.QFileDialog, "getSaveFileName", state.dialog)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: state.confirm(self.text()))
    monkeypatch.setattr(
        gui.ChoiceDialog,
        "exec",
        lambda dialog: (
            dialog.setTextValue(dialog.comboBoxItems()[0]) or gui.ChoiceDialog.DialogCode.Accepted
        ),
    )
    return state


def status(window):
    return window.status_label.text(), window.status_label.property("severity")


def names(folder):
    return sorted(p.name for p in folder.iterdir())


def test_new_path_is_saved_without_asking(window, backup):
    window.transfer_collection()
    bundle._load_bundle(backup.destination)
    backup.confirm.assert_not_called()
    text, severity = status(window)
    assert "Collection bundle saved" in text and severity != "error"
    assert names(backup.folder) == ["backup.cda"]


def test_save_dialog_leaves_the_replacement_prompt_to_the_application(window, backup):
    window.transfer_collection()
    assert backup.dialog.call_args.args[-1] == gui.QFileDialog.Option.DontConfirmOverwrite


def test_cancelled_save_dialog_exports_nothing(window, backup, monkeypatch):
    backup.destination.write_bytes(FOREIGN)
    backup.dialog.side_effect = lambda *a, **k: ("", "")
    export = Mock()
    monkeypatch.setattr(gui, "export_bundle", export)
    window.transfer_collection()
    export.assert_not_called()
    backup.confirm.assert_not_called()
    assert backup.destination.read_bytes() == FOREIGN
    assert "Collection bundle saved" not in status(window)[0]


def test_declined_replacement_keeps_the_file_and_does_not_export(window, backup, monkeypatch):
    backup.destination.write_bytes(FOREIGN)
    export = Mock()
    monkeypatch.setattr(gui, "export_bundle", export)
    window.transfer_collection()
    assert backup.destination.name in backup.confirm.call_args.args[0]
    export.assert_not_called()
    assert backup.destination.read_bytes() == FOREIGN
    assert "Collection bundle saved" not in status(window)[0]
    assert names(backup.folder) == ["backup.cda"]


def test_confirmed_replacement_is_passed_to_the_export(window, backup, monkeypatch):
    backup.destination.write_bytes(FOREIGN)
    backup.confirm.return_value = YES
    export = Mock(wraps=bundle.export_bundle)
    monkeypatch.setattr(gui, "export_bundle", export)
    window.transfer_collection()
    assert export.call_args.kwargs == {"replace": True}
    bundle._load_bundle(backup.destination)
    assert "Collection bundle saved" in status(window)[0]
    assert names(backup.folder) == ["backup.cda"]


def test_file_that_appears_after_the_choice_is_not_replaced(window, backup, monkeypatch):
    real = bundle._load_bundle

    def writer_arrives(path):
        result = real(path)
        backup.destination.write_bytes(FOREIGN)
        return result

    monkeypatch.setattr(bundle, "_load_bundle", writer_arrives)
    window.transfer_collection()
    backup.confirm.assert_not_called()
    assert backup.destination.read_bytes() == FOREIGN
    text, severity = status(window)
    assert severity == "error" and "already in use" in text
    assert "not replaced" in window._error_details["Operation"]
    assert "Collection bundle saved" not in text
    assert names(backup.folder) == ["backup.cda"]


def test_write_error_after_confirmation_keeps_the_file_and_reports_failure(
    window, backup, monkeypatch
):
    backup.destination.write_bytes(FOREIGN)
    backup.confirm.return_value = YES

    def full_disk(self, *args, **kwargs):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(bundle.ZipFile, "writestr", full_disk)
    window.transfer_collection()
    text, severity = status(window)
    assert severity == "error" and "Not enough free space" in text
    assert "No space left" in window._error_details["Operation"]
    assert "Collection bundle saved" not in text
    assert backup.destination.read_bytes() == FOREIGN
    assert names(backup.folder) == ["backup.cda"]


def test_folder_destination_is_reported_without_asking(window, backup):
    backup.destination.mkdir()
    window.transfer_collection()
    backup.confirm.assert_not_called()
    text, severity = status(window)
    assert severity == "error"
    assert "folder" in window._error_details["Operation"]
    assert names(backup.folder) == ["backup.cda"]


def test_replacement_prompt_is_translated(window, backup):
    window.language = "ru"
    backup.destination.write_bytes(FOREIGN)
    window.transfer_collection()
    assert "Заменить его?" in backup.confirm.call_args.args[0]

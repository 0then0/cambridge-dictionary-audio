"""Exercise desktop behavior offscreen with isolated settings and mocked HTTP."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6", reason="Install the gui group to run desktop tests")


from cambridge_audio.gui import app as gui  # noqa: E402
from cambridge_audio.service import Recording  # noqa: E402


def test_gui_export_selected_and_all_and_reports_missing_mp3(window, monkeypatch, mp3, tmp_path):
    from cambridge_audio.library import save_metadata

    window.output_dir.mkdir()
    for accent in ("us", "uk"):
        path = window.output_dir / f"hello.{accent}.mp3"
        path.write_bytes(mp3)
        save_metadata(Recording("hello", accent, path, "", "greeting"))
    window.refresh_library()
    parent = tmp_path / "exports"
    parent.mkdir()
    monkeypatch.setattr(
        gui.QFileDialog,
        "getSaveFileName",
        lambda *args: (str(parent / "cambridge-anki.tsv"), "TSV (*.tsv)"),
    )
    scope = [0]

    def accept_export(dialog):
        dialog.setTextValue(dialog.comboBoxItems()[scope[0]])
        return gui.ChoiceDialog.DialogCode.Accepted

    monkeypatch.setattr(gui.ChoiceDialog, "exec", accept_export)
    window.export_collection()
    output = parent / "cambridge-anki"
    assert len(list((output / "media").iterdir())) == 1
    scope[0] = 1
    window.export_collection()
    assert len(list((output / "media").iterdir())) == 2
    original = (output / "collection.tsv").read_bytes()
    window.selected_recording().path.unlink()
    scope[0] = 0
    window.export_collection()
    assert window.status_label.property("severity") == "error"
    assert (output / "collection.tsv").read_bytes() == original

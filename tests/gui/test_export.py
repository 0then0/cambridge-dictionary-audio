"""Exercise desktop behavior offscreen with isolated settings and mocked HTTP."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6", reason="Install the gui group to run desktop tests")


from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from cambridge_audio.gui import app as gui  # noqa: E402
from cambridge_audio.library import save_metadata  # noqa: E402
from cambridge_audio.service import Recording  # noqa: E402
from tests.core.test_apkg import inspect_package  # noqa: E402


def test_gui_export_selected_and_all_and_reports_missing_mp3(window, monkeypatch, mp3, tmp_path):
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


@pytest.fixture
def saved_choices(window, mp3, monkeypatch):
    window.output_dir.mkdir()
    records = []
    for word, accent, pos, definition in (
        ("lead", "us", "verb", "to guide someone"),
        ("lead", "us", "noun", "a position ahead of others"),
        ("good morning", "uk", "phrase", "a greeting used in the morning"),
        ("apple", "us", "noun", "a round fruit"),
    ):
        path = window.output_dir / f"{word}.{accent}.mp3"
        path.write_bytes(mp3 + word.encode())
        # A legacy ID is also used for the bare MP3 if its sidecar disappears.
        identity = f"test-record-{len(records)}" if word != "apple" else ""
        record = Recording(
            word,
            accent,
            path,
            "",
            definition,
            part_of_speech=pos,
            variant_id=identity,
            metadata_path=window.output_dir / f"{identity}.{accent}.json" if identity else None,
        )
        save_metadata(record)
        records.append(record)
    window.refresh_library()

    def choose_subset(dialog):
        dialog.setTextValue("Choose recordings...")
        return gui.ChoiceDialog.DialogCode.Accepted

    monkeypatch.setattr(gui.ChoiceDialog, "exec", choose_subset)
    return records


def _items(view):
    return [view.item(index) for index in range(view.count())]


def test_export_selection_keeps_distinct_meanings_across_filters(
    window, saved_choices, monkeypatch, tmp_path
):
    expected = saved_choices[:3]

    def select_recordings(dialog):
        dialog.filter_edit.setText(" LEAD ")
        leads = _items(dialog.recordings_list)
        assert len(leads) == 2
        lead_labels = {item.text() for item in leads}
        assert lead_labels == {
            f"{record.word} · {record.part_of_speech} · US\n{record.definition}"
            for record in expected[:2]
        }
        for item in leads:
            item.setCheckState(Qt.CheckState.Checked)

        dialog.filter_edit.setText("good  morning")
        (phrase,) = _items(dialog.recordings_list)
        phrase_label = phrase.text()
        assert "UK" in phrase_label
        QTest.keyClick(dialog.recordings_list, Qt.Key.Key_Home)
        QTest.keyClick(dialog.recordings_list, Qt.Key.Key_Space)
        dialog.filter_edit.setText("apple")
        assert dialog.selection_label.text() == "Selected for export: 3"
        assert {item.text() for item in _items(dialog.selection_list)} == lead_labels | {
            phrase_label
        }
        dialog.filter_edit.setText("lead")
        assert all(
            item.checkState() == Qt.CheckState.Checked for item in _items(dialog.recordings_list)
        )
        dialog.export_button.click()
        return dialog.result()

    destination = tmp_path / "subset.apkg"

    def save_package(parent, title, default, file_filter):
        assert file_filter == "Anki (*.apkg)"
        return str(destination), file_filter

    monkeypatch.setattr(gui.ExportSelectionDialog, "exec", select_recordings)
    monkeypatch.setattr(gui.QFileDialog, "getSaveFileName", save_package)
    window.export_collection()

    notes, _, cards, media, _ = inspect_package(destination, tmp_path)
    rows = [values.split("\x1f") for _, _, values in notes]
    fields = {row[0]: row[1:4] for row in rows}
    assert fields == {r.id: [r.word, r.part_of_speech, r.definition] for r in expected}
    assert len(notes) == len(cards) == 3
    assert len(media) == 2


def test_empty_export_selection_cannot_open_save_dialog(window, saved_choices, monkeypatch):
    def clear_selection(dialog):
        assert not dialog.export_button.isEnabled()
        dialog.filter_edit.setText("lead")
        item = dialog.recordings_list.item(0)
        item.setCheckState(Qt.CheckState.Checked)
        dialog.filter_edit.setText("apple")
        assert dialog.export_button.isEnabled()
        dialog.clear_button.click()
        dialog.filter_edit.setText("lead")
        assert all(
            item.checkState() == Qt.CheckState.Unchecked for item in _items(dialog.recordings_list)
        )
        assert not dialog.selection_list.count()
        assert dialog.selection_label.text() == "Selected for export: 0"
        assert not dialog.export_button.isEnabled()
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(gui.ExportSelectionDialog, "exec", clear_selection)
    monkeypatch.setattr(
        gui.QFileDialog, "getSaveFileName", lambda *args: pytest.fail("Empty selection exported")
    )
    window.export_collection()


@pytest.mark.parametrize("removed", ["recording", "audio", "damaged audio", "legacy sidecar"])
def test_stale_export_selection_preserves_destination_and_suggests_refresh(
    window, saved_choices, monkeypatch, tmp_path, removed
):
    selected, *_, another = saved_choices
    ids = {selected.id, another.id}

    def select_recordings(dialog):
        for item in _items(dialog.recordings_list):
            if item.data(Qt.ItemDataRole.UserRole) in ids:
                item.setCheckState(Qt.CheckState.Checked)
        dialog.export_button.click()
        return dialog.result()

    destination = gui.export_apkg(gui.scan_recordings(window.output_dir), tmp_path / "export.apkg")
    original = destination.read_bytes()

    def save_package(parent, title, default, file_filter):
        if removed == "recording":
            selected.reference.unlink()
        elif removed == "legacy sidecar":
            another.reference.unlink()
            assert another.path.is_file()
            (fallback,) = (
                saved.recording
                for saved in gui.scan_recordings(window.output_dir)
                if saved.recording.id == another.id
            )
            assert not fallback.definition
        elif removed == "audio":
            selected.path.unlink()
        else:
            selected.path.write_bytes(b"not an mp3")
        return str(destination), file_filter

    warnings = []
    monkeypatch.setattr(gui.ExportSelectionDialog, "exec", select_recordings)
    monkeypatch.setattr(gui.QFileDialog, "getSaveFileName", save_package)
    monkeypatch.setattr(
        gui.QMessageBox, "warning", lambda parent, title, text: warnings.append(text)
    )
    window.export_collection()
    assert window.status_label.property("severity") == "error"
    assert len(warnings) == 1 and "Use Refresh in the collection" in warnings[0]
    assert destination.read_bytes() == original

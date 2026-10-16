"""Qt fixtures are loaded only when a GUI test requests them."""

import pytest


@pytest.fixture(scope="package")
def app():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QEvent

    from cambridge_audio.gui import app as gui

    application = gui.create_application([])
    application.setQuitOnLastWindowClosed(False)
    yield application
    # close() hides widgets; dispose them while Qt and its event loop are still
    # usable, instead of leaving multimedia/animation teardown to Python exit.
    for widget in application.topLevelWidgets():
        widget.deleteLater()
    application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()
    application.shutdown()
    assert gui.QApplication.instance() is None


@pytest.fixture
def window(app, tmp_path):
    from PySide6.QtCore import QEvent, QSettings

    from cambridge_audio.gui import app as gui

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("output_dir", str(tmp_path / "audio"))
    instance = gui.MainWindow(settings)
    instance.show()
    app.processEvents()
    yield instance
    for worker in (instance._worker, instance._translation_worker, instance._dictionary_worker):
        if worker is not None:
            worker.requestInterruption()
            worker.wait(5000)
            app.processEvents()
    instance.close()
    instance.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()

import time

from PySide6.QtCore import QEvent


def wait_until(app, predicate, timeout=5):
    end = time.monotonic() + timeout
    while not predicate() and time.monotonic() < end:
        app.processEvents()
        # Delete closed windows as the event loop would. Sleep in Python rather than
        # with QTest.qWait: PySide keeps the GIL during qWait, starving worker threads.
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.01)
    assert predicate(), "GUI worker did not finish in time"

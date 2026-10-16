import time

from PySide6.QtTest import QTest


def wait_until(app, predicate, timeout=5):
    end = time.monotonic() + timeout
    while not predicate() and time.monotonic() < end:
        app.processEvents()
        QTest.qWait(10)
    assert predicate(), "GUI worker did not finish in time"

"""Desktop interface; optional Qt dependencies are loaded only by GUI users."""

from .app import MainWindow as MainWindow
from .app import create_application as create_application
from .app import main as main
from .workers import (
    DictionaryWorker as DictionaryWorker,
)
from .workers import (
    DownloadRequest as DownloadRequest,
)
from .workers import (
    DownloadWorker as DownloadWorker,
)
from .workers import (
    TranslationWorker as TranslationWorker,
)

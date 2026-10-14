"""English application messages and their Russian translations."""

RUSSIAN = {
    "Loading translation...": "Загрузка перевода...",
    "No translation found. Toggle off and on to retry.": (
        "Перевод не найден. Выключите и включите чекбокс, чтобы повторить запрос."
    ),
    "Show version and exit.": "Показать версию и выйти.",
    "Use plain output and the line-based interactive prompt.": (
        "Простой текстовый вывод и построчный диалог."
    ),
    "Open the terminal workspace (requires an interactive terminal).": (
        "Открыть терминальный интерфейс (нужен интерактивный терминал)."
    ),
    "--tui requires a terminal and no word argument.": (
        "Для --tui нужен интерактивный терминал без аргумента слова."
    ),
    "Search": "Поиск",
    "Help": "Справка",
    "Quit": "Выход",
    "Recording": "Запись",
    "Accent": "Вариант",
    "Autoplay": "Автовоспроизведение",
    "Apply": "Применить",
    "Cancel": "Отмена",
    "Show translation": "Показывать перевод",
    "Translation language (Russian if empty)": "Язык перевода (русский, если поле пустое)",
    "Settings apply to this session. Use CLI flags for future launches.": (
        "Настройки действуют в текущей сессии. Для следующих запусков используйте параметры CLI."
    ),
    "Replace saved audio for '{word}'?": "Заменить сохранённое аудио для «{word}»?",
    "Ready · {count} saved recordings": "Готово · сохранённых записей: {count}",
    "No matching recordings": "Подходящих записей нет",
    "Downloading '{word}' · Ctrl+C to cancel": "Скачивание «{word}» · Ctrl+C для отмены",
    "Playing '{word}'": "Воспроизведение «{word}»",
    "Cancelling after the current request...": "Отмена после завершения текущего запроса...",
    "Finishing the current operation before closing...": (
        "Завершение текущей операции перед закрытием..."
    ),
    "Keyboard shortcuts": "Горячие клавиши",
    "Unexpected error: {error}": "Непредвиденная ошибка: {error}",
    "Enter in search: download or open saved audio\n"
    "Enter in library: play selected recording\n"
    "Tab / Shift+Tab: move between controls\n"
    "Up / Down: navigate saved recordings\n"
    "Ctrl+L: focus search\nCtrl+P: play / stop selected recording\n"
    "Ctrl+R: refresh library\nCtrl+S: settings\n"
    "Ctrl+C: cancel download / stop playback, or quit when idle\nCtrl+Q: quit\n"
    "F1: this help\nEsc: close a dialog": (
        "Enter в поиске: скачать или открыть сохранённое аудио\n"
        "Enter в библиотеке: прослушать выбранную запись\n"
        "Tab / Shift+Tab: переход между элементами\n"
        "Вверх / Вниз: выбор сохранённых записей\n"
        "Ctrl+L: перейти к поиску\nCtrl+P: прослушать / остановить запись\n"
        "Ctrl+R: обновить библиотеку\nCtrl+S: настройки\n"
        "Ctrl+C: отменить загрузку / остановить звук или выйти, если операций нет\nCtrl+Q: выйти\n"
        "F1: эта справка\nEsc: закрыть диалог"
    ),
    "Existing audio opens offline. Download again asks before replacing it.\n"
    "Phrase synthesis needs FFmpeg; Linux playback needs ffplay.": (
        "Сохранённое аудио открывается без сети. Повторная загрузка требует подтверждения.\n"
        "Для склейки нужен FFmpeg, для воспроизведения на Linux нужен ffplay."
    ),
    "Settings": "Настройки",
    "Background colour": "Цвет фона",
    "Accent colour": "Цвет акцента",
    "Restore default colours": "Вернуть стандартные цвета",
    "Close": "Закрыть",
    "Colours: {theme}": "Цвета: {theme}",
    "Changes apply immediately. System uses the palette matching your OS appearance.": (
        "Изменения применяются сразу. Системная тема использует палитру в соответствии с темой ОС."
    ),
    "Saved recordings": "Сохранённые записи",
    "No saved recordings": "Нет сохранённых записей",
    "Refresh": "Обновить",
    "Open saved": "Открыть запись",
    "Download again": "Скачать заново",
    "Opened saved recording.": "Открыта сохранённая запись.",
    "Details are unavailable for this saved recording.": (
        "Для этой сохранённой записи нет дополнительных сведений."
    ),
    "Could not read saved recordings: {error}": "Не удалось прочитать записи: {error}",
    "Audio saved. Details could not be saved: {error}": (
        "Аудио сохранено. Не удалось сохранить дополнительные сведения: {error}"
    ),
    "Replace": "Заменить",
    "Keep existing": "Оставить текущие",
    "The recording already exists:\n{files}\n\nReplace it?": (
        "Эта запись уже существует:\n{files}\n\nЗаменить её?"
    ),
    "Audio output is unavailable. Check your system sound settings.": (
        "Устройство вывода звука не найдено. Проверьте настройки звука."
    ),
    "Clear word": "Очистить слово",
    "Enter an English word or phrase without URLs or path separators.": (
        "Введите английское слово или фразу без URL и разделителей пути."
    ),
    "Unsupported dictionary.": "Неподдерживаемый словарь.",
    "The server returned an empty response or data that does not look like MP3.": (
        "Сервер вернул пустой ответ или данные, не похожие на MP3."
    ),
    "Timeout must be a positive finite number.": (
        "Тайм-аут должен быть положительным конечным числом."
    ),
    "Dictionary entry not found: {url}": "Словарная статья не найдена: {url}",
    "Request failed for {url}: {error}": "Ошибка запроса {url}: {error}",
    "No dictionary entry found for '{word}'.": "Словарная статья для «{word}» не найдена.",
    "Accent must be uk or us.": "Произношение должно быть uk или us.",
    "No {accent} pronunciation found.": "Произношение {accent} не найдено.",
    "File already exists: {path}. Use --overwrite to replace it.": (
        "Файл уже существует: {path}. Используйте --overwrite для замены."
    ),
    "Combining requires a phrase with at least two words.": (
        "Для склейки нужна фраза минимум из двух слов."
    ),
    "Install FFmpeg and add it to PATH to combine a phrase.": (
        "Для склейки фразы установите FFmpeg и добавьте его в PATH."
    ),
    "Audio player not found: afplay (macOS) or ffplay (Linux) is required.": (
        "Аудиоплеер не найден: нужен afplay (macOS) или ffplay (Linux)."
    ),
    "Could not play {path}.": "Не удалось воспроизвести {path}.",
    "{accent}: combined from individual word recordings": (
        "{accent}: склеено из произношений отдельных слов"
    ),
    "Saved: {path}": "Сохранено: {path}",
    "Playback: {error}": "Воспроизведение: {error}",
    "Translation: {error}": "Перевод: {error}",
    "Enter a word or phrase. /m: playback, /r: delete this session's files, /q: quit.": (
        "Введите слово или фразу. /m: звук, /r: удалить файлы этой сессии, /q: выход."
    ),
    "Playback enabled.": "Воспроизведение включено.",
    "Playback disabled.": "Воспроизведение выключено.",
    "Files downloaded in this session have been deleted.": "Файлы этой сессии удалены.",
    "Error: {error}": "Ошибка: {error}",
    "Download US or UK pronunciation audio from Cambridge Dictionary.": (
        "Скачивание аудио с US- или UK-произношением из Cambridge Dictionary."
    ),
    "Word or phrase; omit to start interactive mode.": (
        "Слово или фраза; без аргументов запускается диалог."
    ),
    "Pronunciation accent (default: us).": "Произношение (по умолчанию: us).",
    "Destination directory (default: downloads/ in the current directory).": (
        "Каталог сохранения (по умолчанию: downloads/ в текущем каталоге)."
    ),
    "HTTP timeout in seconds (default: 15).": "Тайм-аут HTTP в секундах (по умолчанию: 15).",
    "Play downloaded audio (enabled by default in interactive mode).": (
        "Воспроизвести аудио (в диалоге включено по умолчанию)."
    ),
    "Replace existing MP3 files.": "Заменять существующие MP3.",
    "Combine missing phrases (enabled by default in interactive mode).": (
        "Склеить отсутствующую фразу (в диалоге включено по умолчанию)."
    ),
    "Cambridge translation language, e.g. russian; disabled by default.": (
        "Язык перевода Cambridge, например russian; по умолчанию перевод выключен."
    ),
    "Interface language (default: en); does not change dictionary translations.": (
        "Язык интерфейса (по умолчанию: en); не меняет язык словарного перевода."
    ),
    "Show this help message and exit.": "Показать справку и выйти.",
    "Arguments": "Аргументы",
    "Options": "Параметры",
    "usage: ": "использование: ",
    "{prog}: error: {error}\n": "{prog}: ошибка: {error}\n",
    "Download cancelled.": "Скачивание отменено.",
    "Download and listen to English pronunciation.": (
        "Скачивайте и слушайте английское произношение."
    ),
    "Language": "Язык",
    "Appearance": "Тема",
    "System": "Системная",
    "Light": "Светлая",
    "Dark": "Тёмная",
    "Word or phrase": "Слово или фраза",
    "For example: hello or good morning": "Например: hello или good morning",
    "Pronunciation": "Произношение",
    "American (US)": "Американское (US)",
    "British (UK)": "Британское (UK)",
    "Both": "Оба варианта",
    "Save to": "Сохранить в",
    "Choose...": "Выбрать...",
    "Open folder": "Открыть папку",
    "Russian translation": "Русский перевод",
    "Combine words if the phrase has no recording": "Склеить слова, если у фразы нет записи",
    "Combining requires FFmpeg. The result is not a recording of the whole phrase.": (
        "Для склейки нужен FFmpeg. Результат не является записью цельной фразы."
    ),
    "Recording to play": "Запись для прослушивания",
    "Ready to download.": "Готово к скачиванию.",
    "Download": "Скачать",
    "Downloading...": "Скачивание...",
    "Replace recordings?": "Заменить записи?",
    "These files already exist:\n{files}\n\nReplace them?": (
        "Эти файлы уже существуют:\n{files}\n\nЗаменить их?"
    ),
    "Audio saved. Translation unavailable: {error}": "Аудио сохранено. Перевод недоступен: {error}",
    "Recording saved.": "Запись сохранена.",
    "Both recordings saved.": "Обе записи сохранены.",
    "No recording yet": "Записей пока нет",
    "Combined from individual words": "Склеено из отдельных слов",
    "Download a word or phrase to listen to it here.": (
        "Скачайте слово или фразу, чтобы прослушать произношение."
    ),
    "The recording was moved or deleted. Download it again.": (
        "Запись перемещена или удалена. Скачайте её ещё раз."
    ),
    "Stop": "Стоп",
    "Play": "Слушать",
    "Choose a download folder": "Выберите папку сохранения",
    "Could not open the folder.": "Не удалось открыть папку.",
    "Cambridge took too long to respond. Please try again.": (
        "Cambridge не ответил вовремя. Попробуйте ещё раз."
    ),
    "Cambridge could not provide the recording (HTTP {status}). Try again later.": (
        "Cambridge не смог предоставить запись (HTTP {status}). Попробуйте позже."
    ),
    "Could not connect to Cambridge. Check your internet connection and try again.": (
        "Не удалось связаться с Cambridge. Проверьте интернет-соединение и попробуйте ещё раз."
    ),
    "No recording was found for '{word}' with this pronunciation.": (
        "Для «{word}» не найдена запись с этим произношением."
    ),
    "A recording appeared in this folder. Download again to choose whether to replace it.": (
        "В этой папке появилась запись. Нажмите «Скачать» ещё раз, чтобы выбрать, заменять ли её."
    ),
    "Cannot save in this folder. Choose another folder or close apps using the file.": (
        "Не удалось сохранить запись. Выберите другую папку или закройте приложения, "
        "использующие файл."
    ),
    "Not enough free space in the selected folder.": (
        "В выбранной папке недостаточно свободного места."
    ),
}


def translate(message: str, language: str = "en", **values) -> str:
    if language == "ru":
        message = RUSSIAN.get(message, message)
    return message.format(**values)

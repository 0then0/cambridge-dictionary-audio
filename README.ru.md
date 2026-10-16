<p align="center">
  <img src="assets/icon.svg" width="120" alt="Иконка Cambridge Dictionary Audio">
</p>

# Cambridge Dictionary Audio

[English documentation](README.md) · [История изменений](CHANGELOG.md)

Скачивание MP3 с произношением английских слов и фраз из
[Cambridge Dictionary](https://dictionary.cambridge.org/).
Доступны графическое приложение и CLI, US/UK, транскрипции IPA,
английские определения и необязательные переводы.

## Графическое приложение

<!-- downloads:start -->
Прямое скачивание последнего проверенного стабильного релиза **v0.3.0**:

| Платформа | Архитектура | Скачать |
| --- | --- | --- |
| Windows 10+ | x86-64 | [![Windows 10+ x86-64 EXE](https://img.shields.io/badge/EXE-0078D4?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xIDFoMTB2MTBIMXpNMTMgMWgxMHYxMEgxM3pNMSAxM2gxMHYxMEgxek0xMyAxM2gxMHYxMEgxM3oiLz48L3N2Zz4%3D&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-windows-x86_64-setup.exe) [![Windows 10+ x86-64 Portable ZIP](https://img.shields.io/badge/Portable%20ZIP-0078D4?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xIDFoMTB2MTBIMXpNMTMgMWgxMHYxMEgxM3pNMSAxM2gxMHYxMEgxek0xMyAxM2gxMHYxMEgxM3oiLz48L3N2Zz4%3D&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-windows-x86_64-portable.zip) |
| macOS 14+ | Apple Silicon (arm64) | [![macOS 14+ Apple Silicon (arm64) PKG](https://img.shields.io/badge/PKG-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-macos-arm64.pkg) [![macOS 14+ Apple Silicon (arm64) DMG](https://img.shields.io/badge/DMG-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-macos-arm64.dmg) [![macOS 14+ Apple Silicon (arm64) TAR.GZ](https://img.shields.io/badge/TAR.GZ-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-macos-arm64.tar.gz) |
| macOS 14+ | Intel (x86-64) | [![macOS 14+ Intel (x86-64) PKG](https://img.shields.io/badge/PKG-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-macos-x86_64.pkg) [![macOS 14+ Intel (x86-64) DMG](https://img.shields.io/badge/DMG-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-macos-x86_64.dmg) [![macOS 14+ Intel (x86-64) TAR.GZ](https://img.shields.io/badge/TAR.GZ-555555?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-macos-x86_64.tar.gz) |
| Linux | x86-64 · glibc 2.34+ | [![Linux x86-64 · glibc 2.34+ DEB](https://img.shields.io/badge/DEB-FCC624?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio_0.3.0_amd64.deb) [![Linux x86-64 · glibc 2.34+ RPM](https://img.shields.io/badge/RPM-FCC624?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-1.x86_64.rpm) [![Linux x86-64 · glibc 2.34+ Portable TAR.GZ](https://img.shields.io/badge/Portable%20TAR.GZ-FCC624?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-dictionary-audio-0.3.0-linux-x86_64-portable.tar.gz) |
| Python CLI | Любая | [![Python CLI Любая WHL](https://img.shields.io/badge/WHL-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge_dictionary_audio-0.3.0-py3-none-any.whl) [![Python CLI Любая Source TAR.GZ](https://img.shields.io/badge/Source%20TAR.GZ-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge_dictionary_audio-0.3.0.tar.gz) |
| Chrome | Любая | [![Chrome Любая ZIP](https://img.shields.io/badge/ZIP-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-audio-chrome-0.3.0.zip) |
| Firefox | Любая | [![Firefox Любая ZIP](https://img.shields.io/badge/ZIP-FF7139?style=for-the-badge&logo=firefoxbrowser&logoColor=white)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/cambridge-audio-firefox-0.3.0.zip) |

[![SHA-256](https://img.shields.io/badge/SHA--256-SHA256SUMS.txt-555555?style=flat-square)](https://github.com/0then0/cambridge-dictionary-audio/releases/download/v0.3.0/SHA256SUMS.txt)
<!-- downloads:end -->

Установщики и переносимые сборки включают Python, Qt и минимальный аудио-FFmpeg
с LAME под LGPL. Для склейки фраз не нужны отдельная установка и настройка `PATH`.
Соответствующие исходники FFmpeg/LAME и параметры сборки входят в каждый релиз.
В релизы также входят wheel и исходный архив CLI, а также `SHA256SUMS.txt`.
Для Windows нужна Windows 10 или новее. Установщики пока не подписаны сертификатом издателя; сборки macOS не нотарифицированы.

CLI устанавливается отдельно из [PyPI](https://pypi.org/project/cambridge-dictionary-audio/):

```sh
uv tool install cambridge-dictionary-audio
```

Каждая кнопка скачивает нужный файл напрямую, без перехода на страницу релиза.
Ссылки закреплены на проверенной стабильной версии, указанной над таблицей:
имена файлов содержат номер версии. После публикации нового стабильного релиза
команда `uv run --no-sync python scripts/download_links.py --refresh --verify-network`
обновит обе таблицы и проверит скачивание.

### Запуск из исходников

Нужен [uv](https://docs.astral.sh/uv/getting-started/installation/) версии 0.13.0
или новее. Выполните команды в каталоге проекта:

```sh
uv sync --locked --group gui
uv run --group gui -m cambridge_audio.gui
```

Введите слово или фразу и нажмите **Скачать** или Enter. Внизу появятся запись,
транскрипция и определение. **Слушать** воспроизводит звук внутри окна,
**Открыть папку** показывает каталог с MP3. Внешний плеер для GUI не нужен.

- Английский и русский интерфейс; по умолчанию английский.
- Системная, светлая и тёмная темы. Системная следует уведомлениям Qt об оформлении ОС;
  если платформа не сообщает тему, используется светлая.
- Шестерёнка открывает **Настройки** языка и оформления. Можно выбрать любой цвет
  фона и акцента активной светлой или тёмной палитры. Изменения применяются сразу
  и запоминаются отдельно для каждой палитры; текст и иконки адаптируются для
  читаемости. **Вернуть стандартные цвета** сбрасывает активную палитру.
  **О приложении** в настройках показывает версию, ссылку на репозиторий и сведения о лицензиях.
- По умолчанию US; можно выбрать UK или оба и прослушивать их отдельно.
- Необязательные русский перевод и склейка фраз через FFmpeg.
- Скачивание выполняется в фоне. Ошибки показаны в окне; перезапись требует подтверждения.
- Язык, тема, произношение, параметры и папка запоминаются через настройки Qt.
  После перезапуска также восстанавливаются размер, положение и развёрнутое состояние окна.
  По умолчанию записи GUI сохраняются в `Cambridge Dictionary Audio` внутри
  пользовательской папки загрузок. Кнопка **Выбрать...** меняет каталог.
- **Сохранённые записи** показывает файлы `word.us.mp3` и `word.uk.mp3` из выбранной
  папки. Их можно слушать без интернета после перезапуска; **Обновить** учитывает
  внешние изменения. Ввод сохранённого слова открывает запись, а выбор обоих
  вариантов скачивает только недостающий. **Скачать заново** запрашивает подтверждение замены.
- Новые записи GUI сохраняют транскрипцию, определение и перевод в JSON рядом с MP3.
  Старые файлы можно слушать и без дополнительных сведений.
  Чекбокс **Показывать перевод** сразу показывает или скрывает сохранённый русский перевод.
  Если его нет, приложение загружает перевод в фоне без повторного скачивания аудио.
  В панели записи отображаются загрузка и ошибки; выключите и включите чекбокс для повтора.
- Ползунок прокрутки имеет ширину 4 логических пикселя и расширяется до 8 при наведении.
  Область взаимодействия сохраняет размер, поэтому содержимое окна не сдвигается.

GUI использует PySide6 Essentials и Addons без WebEngine и PDF.
При запуске из исходников на macOS автоматически создаётся небольшая оболочка
`.app` в кэше приложения, чтобы Dock показывал название и иконку проекта.
Готовым колёсам нужны macOS 14+, Linux с glibc 2.34+ для x86-64 или 2.39+ для ARM64
либо поддерживаемая 64-битная Windows. В минимальных Linux-системах могут потребоваться
[системные библиотеки Qt](https://doc.qt.io/qt-6/linux-requirements.html).
Эти требования Qt не относятся к отдельному Python CLI.
Подробности: [релизы PySide6](https://pypi.org/project/PySide6/).

`start-gui.bat` запускает GUI из исходников на Windows через uv.

## Коллекция, переводы и Anki

[Руководство по коллекции](docs/collection.md) описывает выбор произношения,
переводы на русский, установку локального WikDict и экспорт в Anki из GUI, TUI
и CLI, включая команды, горячие клавиши, совместимость записей и импорт медиа.
[Источники и лицензии](docs/data-sources.md) содержат сведения об атрибуции
словарных данных и их лицензировании отдельно от кода приложения.

## Расширение браузера

Расширение на TypeScript для Chrome и Firefox скачивает аудио с открытой словарной
страницы Cambridge. Доступен выбор US/UK, словарной записи и варианта произношения.
Шестерёнка открывает настройки языка (английский или русский) и темы (системная,
светлая или тёмная). Настройки сохраняются локально.

Python и установленное приложение не требуются. Файлы сохраняются по обычным
настройкам загрузок браузера. Расширение читает страницу при открытии; переводы,
библиотека записей и склейка фраз остаются в приложении.
[Документация расширения](extension/README.md) описывает сборку, установку для
разработки, разрешения и приватность. Релизы включают ZIP для обоих браузеров;
архивы также доступны в артефакте `browser-extensions` успешного запуска Checks.

## Установка и запуск CLI

Пакет PyPI содержит только CLI, без Qt и графических модулей:

```sh
uv tool install cambridge-dictionary-audio
cambridge-audio hello
```

Также доступны `pipx install cambridge-dictionary-audio` и установка через pip
в виртуальном окружении. [Документация пакета CLI](docs/cli.md).

### Запуск из исходников

Нужен [uv](https://docs.astral.sh/uv/getting-started/installation/) версии 0.13.0
или новее. Выполните команды в каталоге проекта:

```sh
uv sync --locked
uv run -m cambridge_audio hello
uv run -m cambridge_audio hello --lang ru --translation russian
```

По умолчанию используются **американское произношение (US)** и **английский интерфейс**.
Файл сохраняется в `downloads/hello.us.mp3` относительно текущего рабочего каталога;
существующие записи не заменяются без `--overwrite`.
Ответ проверяется на сигнатуру MP3 и записывается во временный файл.
Готовая запись появляется только после завершения записи; прерывание не оставляет
пустой или частичный MP3 в библиотеке.
Определения остаются английскими; `--lang ru` меняет только интерфейс.

## Параметры

```sh
uv run -m cambridge_audio hello --accent uk
uv run -m cambridge_audio "good morning" --accent both --output-dir audio
uv run -m cambridge_audio hello --play --overwrite
uv run -m cambridge_audio --lang ru --help
```

- `--accent us|uk|both`: вариант произношения; имя файла содержит `.us` или `.uk`.
- `--output-dir PATH`: каталог сохранения; по умолчанию `downloads/` в текущем рабочем
  каталоге. Создаётся при необходимости.
- `--lang en|ru`: язык интерфейса, справки и сообщений приложения.
- `--translation russian`: включить русский перевод; также принимаются `ru` и `русский`.
  Другие языки перевода отклоняются.
  Перевод по умолчанию выключен и не зависит от языка интерфейса.
- `--play` / `--no-play`: включить или выключить воспроизведение.
- `--combine` / `--no-combine`: включить или выключить склейку отсутствующих фраз.
- `--overwrite`: заменять существующие MP3.
- `--timeout SECONDS`: тайм-аут каждого HTTP-запроса; по умолчанию 15 секунд.

Регистр слов не имеет значения. Фразы можно передавать в кавычках или отдельными
аргументами. Поддерживаются апострофы и дефисы; URL и разделители пути отклоняются.
Зарезервированные имена Windows получают префикс `_` на всех платформах:
например, `con` сохраняется в `_con.us.mp3`.

Ошибка загрузки возвращает код 1, неверные параметры CLI возвращают код 2.
Сбой воспроизведения или перевода не отменяет успешную загрузку.
При `--accent both` успешная первая запись остаётся, если вторая загрузка завершилась ошибкой.

## Интерактивный режим

```sh
uv run -m cambridge_audio --lang ru
uv run -m cambridge_audio --lang ru --no-play --translation russian
```

Без слова в интерактивном терминале открывается интерфейс с библиотекой записей
и панелью сведений. В узком окне панели располагаются одна под другой. Работают
мышь, клавиатура, фоновое скачивание и прослушивание. Поиск фильтрует библиотеку
при вводе. Enter открывает сохранённое аудио без сети или скачивает отсутствующее.
При выборе US и UK скачивается только недостающий вариант. Повторное скачивание
требует подтверждения замены.

- **Enter** в поиске: скачать или открыть запись; в библиотеке: прослушать.
- **Tab / Shift+Tab**: переход между элементами; **Вверх / Вниз**: выбор записи.
- **Ctrl+L**: поиск; **Ctrl+P**: прослушать/остановить; **Ctrl+R**: обновить библиотеку.
- **Ctrl+S**: настройки; **F1**: справка; **F2**: о приложении; **Ctrl+Q**: выход.
- **Ctrl+C**: отменить скачивание, остановить звук или выйти, если операций нет. Текущий запрос
  завершается перед отменой; уже скачанные файлы сохраняются.

Все команды также доступны при любой раскладке: **F3** поиск, **F4** прослушать/остановить,
**F5** обновить, **F6** настройки, **F7** экспорт, **F8** перевод, **F9** WikDict,
**F10** произношение, **F11** отмена, **F12** выход. Ctrl-сочетания работают и с русскими
и украинскими буквами на тех же клавишах. Если терминал не передаёт Ctrl с нелатинскими
буквами, используйте функциональные клавиши.

Значения перевода показаны отдельными пунктами без технических ID; Ctrl+T
открывает выбор и редактирование. F2 или **О приложении** в справке показывает
версию, ссылку на репозиторий и сведения о лицензиях.

В настройках доступны язык интерфейса, светлая и тёмная темы, US/UK, папка,
переключатель русского перевода, автовоспроизведение и склейка фраз. После нажатия
«Применить» настройки сохраняются для следующих запусков TUI. Явные параметры CLI
имеют приоритет при запуске. Флажок перевода в основном окне тоже запоминается.
Чекбокс показывает и скрывает русский перевод сразу. Готовый кэш используется без
повторных запросов; отсутствующий перевод загружается без скачивания MP3.
Английское определение остаётся видимым при выключенном переводе. Язык интерфейса
независим: русский или английский. Загрузка и ошибки показаны в панели записи.
Метаданные хранятся в JSON рядом с MP3 и совместимы с GUI. Старые иноязычные кэши
и пользовательские правки сохраняются с исходным языком, без удаления или подмены.
Переводы без языка не считаются русскими автоматически. MP3 без дополнительных
сведений остаются доступными, пустые файлы не попадают в библиотеку.
Символьные ссылки сохраняют собственные имена, варианты произношения и JSON.

Воспроизведение и склейка включены по умолчанию, произношение US, язык английский.
Терминальный интерфейс использует Textual и не требует Qt или специального шрифта.

`--plain` включает простой текстовый вывод и прежний построчный диалог.
Он также выбирается автоматически при перенаправлении ввода или вывода и при
`TERM=dumb`. Команды диалога: `/m` переключает воспроизведение, `/r` удаляет
скачанные в текущей сессии файлы и их JSON, `/q` завершает работу.
`--tui` требует интерактивный терминал, `--version` показывает версию.
Разовые команды сохраняют коды завершения и простой вывод при перенаправлении;
в терминале отображаются индикатор загрузки и карточка определения.
`NO_COLOR` отключает цвета.

## Воспроизведение и склейка

Для скачивания оригинальных записей плеер и FFmpeg не требуются.
На Windows файл открывается в системном аудиоприложении, на macOS используется
`afplay`, на Linux нужен `ffplay`. На Windows управлять воспроизведением нужно во внешнем
приложении: действие «Остановить» в терминале не управляет этим приложением.
GUI использует Qt Multimedia.
Для обоих способов требуется рабочая аудиосистема.

```sh
uv run -m cambridge_audio "hello friendly world" --combine
```

Если у фразы нет собственной записи, её можно склеить из отдельных слов.
При запуске из исходников и для CLI с PyPI нужен
[FFmpeg](https://ffmpeg.org/download.html) с кодировщиком `libmp3lame` в `PATH`.
Склейка не запускается после сетевых ошибок; каждое слово должно иметь запись
выбранного произношения. Результат нормализуется по громкости и не является
записью цельной фразы Cambridge. Временные файлы удаляются автоматически,
существующие загрузки не затрагиваются. `ffprobe` нужен только для проверки файлов.

## Python и разработка

Поддерживаются Python **3.10–3.15**. Диапазон версий задан в `pyproject.toml`.
`.python-version` выбирает **3.15** для разработки, без фиксации патч-версии.
Это не ограничивает поддержку других версий:

```sh
uv sync --locked --python 3.10
uv run --python 3.10 -m cambridge_audio hello
```

Для этого окружения используйте одинаковый `--python` во всех командах.
Зависимости описаны в `pyproject.toml` и зафиксированы в `uv.lock`.
Проверки: Ruff для линтинга и форматирования, pytest для тестов.

```sh
uv sync --locked
uv lock --check
uv run ruff check .
uv run ruff format --check .
uv run --isolated --locked pytest
```

Тесты работают без сети и проверяют скачивание, отмену, восстановление кэша,
язык перевода, навигацию с клавиатуры, настройки GUI и упаковку релиза.
Интеграционные тесты склейки запускаются при наличии
`ffmpeg` и `ffprobe`, иначе пропускаются. CI использует uv 0.13.1 и проверяет все
шесть версий Python на Linux, а также 3.10 и 3.15 на Windows и macOS.
Задания с GUI-зависимостями запускают весь набор тестов на Python 3.10 и 3.15
на всех трёх ОС, а также на Python 3.11 и 3.12 на Linux.
Обновление зависимостей: `uv lock --upgrade`, затем проверки выше.
Запуск без инструментов разработки: `uv run --no-dev -m cambridge_audio hello`.

Для запуска вместе с GUI-тестами: `uv run --locked --group gui pytest`.
На Linux с Python 3.10 или 3.11 lockfile выбирает Qt 6.11.2 для совместимости;
в остальных окружениях используется Qt 6.12. Помимо поведения виджетов, тесты
проверяют нормальное завершение процесса после многократной перерисовки скроллбара.
Тесты GUI используют Qt без видимого окна, временные настройки и подменённые
HTTP-ответы.
[Дизайн-система](docs/design.md) описывает оформление и поведение приложения.

Расширение использует отдельный npm lockfile в `extension/`. Для его разработки
нужен Node.js 24.15+: TypeScript проверяет типы, Node и jsdom запускают тесты DOM.
CI проверяет сборку на всех трёх ОС и дополнительно использует `web-ext` для Firefox.
Эти инструменты не нужны для разработки Python CLI и GUI.

## Структура проекта

- `cambridge_audio/dictionary.py`: словарные статьи, HTML, HTTP-запросы и сохранение MP3.
- `cambridge_audio/audio.py`: склейка фраз и воспроизведение на разных платформах.
- `cambridge_audio/cli.py`: параметры командной строки, разовое скачивание и построчный диалог.
- `cambridge_audio/terminal/`: терминальный интерфейс, настройки и фоновые задачи.
- `cambridge_audio/console.py`: форматированный вывод и простой текст для перенаправления.
- `cambridge_audio/service.py`: общий сценарий скачивания для обоих интерфейсов.
- `cambridge_audio/gui/`: окно, фоновые задачи аудио и перевода, встроенное воспроизведение.
- `cambridge_audio/gui/theme.py`: цветовые токены и оформление Qt.
- `cambridge_audio/gui/preferences.py`: настройки языка и оформления.
- `cambridge_audio/library.py`: сохранённые записи и дополнительные сведения в JSON.
- `cambridge_audio/i18n.py`: английские и русские сообщения интерфейса.
- `assets/icon.svg`: исходная векторная иконка; `assets/icon.ico`: её версия для Windows.
- `extension/`: popup на TypeScript, манифесты браузеров, тесты DOM и сборка.
- `tests/`: группы core, cli, gui, terminal и packaging; общие вспомогательные функции.
- `scripts/` и `packaging/`: проверки релиза, сборка приложения и шаблоны установщиков.

Основной запуск: `python -m cambridge_audio`. Корневой `main.py` оставлен для
совместимости: прежняя команда `uv run main.py` также работает.

`start.bat` запускает CLI на Windows. `compile.bat` собирает GUI и установщик Windows;
для него нужен Inno Setup. Нативные сборки используют группы зависимостей `gui`
и `release` из lockfile. На целевой платформе сначала запускается `scripts/build_ffmpeg.py`,
затем `scripts/build_desktop.py` и `scripts/package_desktop.py`.
[Инструкция по сборке FFmpeg](packaging/ffmpeg-build.md) описывает требования к компилятору
и пересборку LGPL-компонентов. Результат помещается в `dist/`. Общие библиотеки Qt
и лицензионные уведомления зависимостей остаются отдельными файлами внутри сборки.

## Лицензия

Основная лицензия этого форка: [Apache License 2.0](LICENSE).
Проект основан на [astrosander/cambridge-dictionary-audio](https://github.com/astrosander/cambridge-dictionary-audio).
Унаследованные материалы сохраняют исходную [MIT-лицензию](LICENSE-MIT)
и уведомление об авторских правах. Атрибуция приведена в [NOTICE](NOTICE).

PySide6/Qt и мультимедийные библиотеки сохраняют собственные лицензии.
При распространении GUI необходимо сохранять их уведомления и соблюдать условия Qt;
Apache-2.0 этого проекта не заменяет лицензии зависимостей.

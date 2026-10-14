# Desktop interface

The desktop app provides one workflow: enter a word, download its pronunciation,
listen, and find the saved MP3. The main window contains the library and recording
controls; a separate Settings window contains language and appearance preferences.

## Layout and appearance

The interface uses the platform font at 14 logical pixels, with 20–22 pixel
headings. Spacing follows 8, 16 and 24 pixel increments, with 24 pixel page margins.
Controls have 6 pixel corner radii and panels have 8 pixel radii. Qt handles
high-DPI scaling. Layouts resize and scroll so essential controls remain accessible
in a small window.

The default palettes combine neutral surfaces with a muted red accent from the
project icon. Settings offers system, light and dark modes, with independent
background and accent overrides for each palette. System mode follows Qt's OS
appearance notifications and falls back to light when no preference is reported.
Changes apply immediately and persist through Qt's platform settings.

Text maintains at least 4.5:1 contrast; focus indicators maintain at least 3:1.
Interface SVGs receive colours from the active palette. Visible focus indicators,
label buddies, accessible names and plain-text status messages support keyboard
and assistive-technology users. Scrollbar handles measure 4 logical pixels and
expand to 8 on hover inside a fixed 12 pixel hit area. Hover does not shift content.

Palette tokens, contrast calculations and widget styles are in
[`theme.py`](../cambridge_audio/theme.py). Shared icons are in
[`assets/ui/`](../assets/ui/), each with an accessible SVG title.

## Recording workflow

English and American pronunciation are the defaults. Interface language affects
controls and messages; dictionary definitions remain English. Russian dictionary
translation is an independent option.

Download is the primary action; Enter submits the word field. Network requests
and phrase synthesis run in worker threads. Status messages report progress and
errors in the window. Existing recordings open without network access, and only
missing accents are downloaded. Download again requires overwrite confirmation.
Successfully saved audio remains available if another accent or translation fails.

The library scans the selected folder on startup and folder changes. Refresh
picks up external changes. Each `word.us.mp3` or `word.uk.mp3` can have an optional
JSON sidecar with IPA, definition, phrase-synthesis status, translations and their
language. Files without sidecars remain playable; empty MP3s are ignored.

Enabling Russian translation displays its cached value or fetches it in the
background without replacing audio. A translation from another language, or one
without a recorded language, is refreshed. Loading and failure messages appear
in the recording panel. Toggling off and on retries a failed request. Responses
are cached beside the original recording without changing the user's selection.

Qt Multimedia handles playback with Play and Stop actions. Closing while a worker
is active hides the window and lets the bounded network request finish. Threads
are never forcibly terminated. Completed audio and metadata writes are atomic.

## Platform integration

GUI recordings default to `Cambridge Dictionary Audio` inside the user's Downloads
folder. The CLI defaults to `downloads/` in its working directory. Both interfaces
can select the same folder and share recordings and metadata.

The application icon and name are set globally. On macOS, source launches use a
cached `.app` wrapper linked to the active Python interpreter so Dock displays the
project's identity. Packaged applications supply this identity through their native
bundle. Language, appearance, accent, options and the chosen folder persist between
GUI launches.

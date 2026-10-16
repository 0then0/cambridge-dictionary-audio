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
expand to 8 on hover inside a fixed 12 pixel hit area. In the main scroll area and
combo-box lists, the thumb expands smoothly over 120 ms, remains expanded during
dragging, and uses a subtle track highlight. The layout stays fixed. Discrete
mouse-wheel steps animate over 80 ms and accumulate; precise touchpad events keep
Qt's direct handling. Clicking, dragging and keyboard actions interrupt a running
scroll animation.

This Qt implementation adapts the GTK scrollbar behavior selected by
[Zen Browser's scrollbar preference](https://github.com/zen-browser/desktop/blob/dceca78d98280bbceee25a8e5358b2ce3953f718/prefs/firefox/browser.yaml#L23),
whose thumb geometry is implemented in
[Gecko's GTK scrollbar renderer](https://github.com/mozilla/gecko-dev/blob/master/widget/ScrollbarDrawingGTK.cpp).
Colors continue to follow the application's light, dark and custom palettes.

Palette tokens, contrast calculations and widget styles are in
[`theme.py`](../cambridge_audio/gui/theme.py). Shared icons are in
[`assets/ui/`](../assets/ui/), each with an accessible SVG title.

## Recording workflow

English and American pronunciation are the defaults. Interface language affects
controls and messages; dictionary definitions remain English. Optional translation
targets Russian in 0.3.0. A Russian translation toggle and the local dictionary
status replace the former free-form language field. Historical foreign-language
caches and edits remain intact.

Find displays meanings inline, grouped by part of speech. Selecting a meaning shows
its complete definition and the audio owned by its source block. US/UK and preview
playback precede the explicit Save meaning action. Other pronunciation is visible
only for distinct audio alternatives of the selected accent. Saved entries remain
available offline; Choose meaning performs a fresh search. Saving a meaning closes
its selection list in the GUI. A new search clears the previous choices, including
when the request fails. Failed accent downloads preserve enough context to return
to the saved accent without another network request.

JSON v3 separates permanent collection identity from source identity and media.
Several collection JSON files may reference one MP3 identified by accent and URL.
Checksums verify managed media before reuse. Legacy v1/v2 metadata upgrades only
on save; IDs, metadata paths and translations remain intact, including when audio
is replaced. Existing duplicate files are retained. Network audio downloads do not
hold the metadata lock, so collection reads can continue while a download waits.

Enabling translation displays its cached result or fetches it in the background
without replacing audio. Cache entries coexist by language, source and sense.
Personal edits take priority, followed by cache, Cambridge and installed WikDict.
Source senses without verified Cambridge alignment are labeled explicitly.
The user can edit, reset or choose a translation sense. Late background responses
preserve manual edits and do not switch the selected recording or reveal a hidden
translation. Toggling off and on retries a failed request. Closing waits for
active downloads, translations and dictionary installation.

Install WikDict shows version, size in MB and license before explicit confirmation.
Anki export uses genanki to package the selected entry or whole collection into one
.apkg with a stable model, template and note GUIDs. TSV is an additional format;
missing media or unresolved source-sense choices produce a visible failure.
See [collection guide](collection.md) for storage, export and license details.

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

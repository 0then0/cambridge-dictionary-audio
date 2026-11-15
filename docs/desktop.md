# Desktop app

The desktop app runs on Windows 10 or later, macOS 14 or later and Linux
(x86-64, glibc 2.34 or later). Download it from the
[latest release](https://github.com/0then0/cambridge-dictionary-audio/releases/latest)
or [run it from source](#run-from-source).

## Find and save a pronunciation

1. Type an English word or phrase and press **Find** or Enter.
2. Choose a meaning in the list below the result. Meanings are grouped by part of
   speech, and the full definition and IPA are shown for the selected one.
3. Choose **American (US)**, **British (UK)** or **Both**. **Other pronunciation**
   appears when the selected meaning has several recordings for that accent.
4. Press **Play** to listen. Listening does not add anything to the collection.
5. Press **Save meaning**.

To pick another meaning of a saved word later, press **Choose meaning**. Typing a
word that is already saved opens it without a network request; with **Both**
selected, only a missing accent is downloaded. **Download again** replaces a saved
recording after confirmation.

If Cambridge has no recording of a whole phrase, enable **Combine words if the
phrase has no recording** in **Settings**. The app joins the recordings of the individual words;
the result is not a recording of the complete phrase.

## Add a word list

**Word list...** next to **Find** searches up to 100 words or phrases at once.
Paste one per line, review the meanings found for each word, choose meanings and
pronunciations, and save them together. Words with several meanings are never
saved without your choice. See [Add a word list](collection.md#add-a-word-list-desktop)
for details on retries, cancellation and duplicates.

## Saved recordings

Recordings are saved to `Cambridge Dictionary Audio` in your Downloads folder.
**Choose...** selects another folder and **Open folder** shows it in the file
manager. **Saved recordings** lists the collection in that folder; it works
offline, and **Refresh** picks up changes made outside the app.

Each meaning is stored as an MP3 with a JSON file holding its definition, IPA and
translation. Meanings that share a recording use one MP3. Keep the MP3 and JSON
files together when moving the folder. The command-line tool and terminal
interface can use the same folder.

## Translations

**Show Russian translation** shows a translation of the selected meaning. A missing
translation is loaded in the background; turn the option off and on to retry a
failed request. **Edit translation**, **Reset translation** and **Find translation**
let you correct or choose a translation; personal edits are kept across later
lookups and exports. **Install WikDict** in **Settings** downloads an
English–Russian dictionary for offline translations. See [translations](collection.md#translation-lookup-and-editing).

## Anki and backups

**Export to Anki** saves the selected recording or the whole collection as an
`.apkg` deck, or as a TSV folder. Exporting again later updates the same Anki notes.
**Back up / transfer collection** creates or imports a `.cda` archive, for example
to move the collection to the mobile app. See [Export to Anki](collection.md#export-to-anki)
and [Backups and transfer](collection.md#backups-and-transfer).

## Settings

The gear button opens **Settings**:

- Interface language: English, Russian, Spanish, German, French, Japanese or
  Brazilian Portuguese. Dictionary translations are always Russian.
- Appearance: system, light or dark, with custom background and accent colours
  for each palette. **Restore default colours** resets them.
- **Options**: phrase synthesis, the offline dictionary status and
  **Install WikDict**.
- **About** shows the version, the source code link and license information.

The app remembers the language, appearance, accent, options, folder and window
size between launches.

## Errors

Errors are shown in the window as a short explanation. **Technical details** shows
the original message, which is useful in bug reports. Downloads run in the
background, so the window stays responsive; closing the window waits for the
current request to finish.

## Run from source

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) 0.13.0 or
newer and run in the project directory:

```sh
uv sync --locked --group gui
uv run --locked --group gui -m cambridge_audio.gui
```

On Windows, `start-gui.bat` does the same. Phrase synthesis from source requires
[FFmpeg](https://ffmpeg.org/download.html) with the `libmp3lame` encoder in `PATH`;
release builds include it.

The app uses PySide6. Its wheels need macOS 14 or later, Linux with glibc 2.34
(x86-64) or 2.39 (ARM64), or 64-bit Windows. Minimal Linux desktops may also need
the [Qt runtime libraries](https://doc.qt.io/qt-6/linux-requirements.html). On
macOS, launching from source creates a small `.app` wrapper in the app's cache so
that the Dock shows the project name and icon.

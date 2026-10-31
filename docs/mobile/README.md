# Android and iOS applications

The mobile applications provide Cambridge pronunciation search, a local recording
collection, Russian translations, phrase synthesis and Anki export. They run
independently of the desktop application and do not require a Python installation.

Android requires **Android 9 or later**; iOS requires **iOS 17 or later**.
The mobile version is **1.0.1**. For build artifacts, signing requirements and
installation commands, see [Mobile builds and installation](install.md).

## Search and save

1. Open **Search** and enter an English word or phrase.
2. Choose a meaning. The first three meanings are visible initially; expand the
   list to see more. Choosing an item collapses the additional choices.
3. Select **US** or **UK** pronunciation and listen before saving. An unavailable
   accent is shown explicitly.
4. Save the selected meaning to the collection. Meanings sharing one recording
   reuse the same audio file.

Playback preparation appears beside the playback controls. Longer operations,
including downloads and imports, show progress and offer cancellation.
If a complete phrase recording is unavailable, phrase synthesis combines the
selected word recordings into an MP3. This is assembled audio rather than a
Cambridge recording of the complete phrase.

## Collection

Open a word in **Collection** to view its definition, IPA, pronunciation and
translation. Playback, audio restoration, deletion, translation editing and export
are available in that detail view. Returning to Search preserves the selected
meaning and unsaved translation.

Saved audio and personal translations remain available offline. Restoring a
missing or damaged recording requires its source recording to be available.
Removing one meaning keeps any audio still used by another collection entry.

## Russian translations and WikDict

Translations can come from Cambridge or an explicitly installed WikDict
English–Russian dictionary. Personal translations take priority over dictionary
results. Translation failure does not prevent saving or playing audio.

The first three translation alternatives are visible initially. Expand the list
for additional alternatives; selecting one collapses the list and keeps the chosen
translation visible. You can also edit or reset the translation.

Settings displays the local WikDict installation status. Before downloading, the
app checks the installed package and asks for confirmation when a download would
replace it. A failed download preserves an existing valid dictionary. Once
installed, WikDict can provide translations without a network connection.
See [Data sources](../data-sources.md) for the package version and attribution.

## Appearance

Settings offers English, Russian, Spanish, German, French, Japanese and Brazilian
Portuguese interface languages, a default pronunciation, and system, light and dark
appearance. Choose a blue, green, purple, orange or red
accent; the red matches the desktop palette. Android can also use system colours.
Selecting a manual accent switches away from the system palette.

**Pure black (OLED)** is a separate preference for dark appearance. It applies
when dark mode is active, including system dark mode, and leaves light appearance
unchanged. Preferences persist between launches.

**Licenses and sources** opens component information and the bundled license texts.
Android uses a full-screen reader; iOS groups the information into native sections.

## Backups, transfer and Anki

Use **Back up / export** to save a `.cda` collection archive through the system
share sheet. Each export is a new file; the app you share it with decides where it is
saved and how an existing file with the same name is handled. Import previews changes
and asks how to resolve conflicts before applying them. A retained backup protects the
previous collection. The same format is supported by the desktop GUI and CLI.

Export Anki material as an `.apkg` package, or as TSV with audio. Export does not
require Anki to be installed on the phone. Import the exported package into Anki
using its normal import controls. Keep the collection's permanent identities to
update existing notes rather than creating duplicates.

- [Collection and Anki guide](../collection.md)
- [Portable storage and transfer format](storage.md)
- [Builds, signing and updates](install.md)
- [Testing and release checks](readiness.md)

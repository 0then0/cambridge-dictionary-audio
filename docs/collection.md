# Collection, translations and Anki

The CLI, terminal workspace and desktop app use the same recording, translation
and export services. The browser extensions remain independent pronunciation downloaders.
This guide describes the current source tree. Features listed under **Unreleased**
in the [changelog](../CHANGELOG.md) are not yet included in published downloads.

## Choose a meaning and audio

Enter a word and choose **Find** in the GUI or TUI. Meanings appear beneath the
result, grouped by part of speech. Selecting a meaning immediately shows its full
definition, IPA and available translation. Use US/UK and **Play** before
**Save meaning**. **Other pronunciation** appears only when the selected meaning
has several distinct recordings for that accent. Already saved choices are marked.
A missing accent is not replaced with another accent's recording. If its download
fails in the GUI, switching back opens the saved accent without a network request.
After saving a meaning, the GUI hides the selection list; use **Choose meaning**
to open it again.

Opening a saved word works offline. To search all meanings again, use
**Choose meaning** in the GUI or **Ctrl+O** in the TUI. Select saved collection
entries individually to edit their translation or export them. Technical IDs are
shown only by the CLI's diagnostic listing, not in ordinary interface labels.

```sh
cambridge-audio lead --list-variants
cambridge-audio lead --sense SENSE_ID --audio AUDIO_ID --preview
cambridge-audio lead --sense SENSE_ID --audio AUDIO_ID
cambridge-audio lead --variant CHOICE_ID
```

The listing contains the combined choice ID, `sense=…` and `audio=…`.
`--sense` chooses a meaning; `--audio` chooses its recording. If more than one
choice remains, the CLI lists choices and exits with status 1. `--variant` remains
supported. `--preview` plays from a temporary cache without adding a collection
entry. Without it, one unambiguous CLI choice is saved immediately. `--accent both`
saves both accents when each has one choice; an explicit audio/choice ID selects
only that recording. `--overwrite` requests a fresh download. The plain interactive
prompt shows numbered choices rather than technical IDs.

Meanings stay linked to their source dictionary blocks: for example, the metal
and verb senses of “lead” keep their respective recordings. Two meanings of
“bank” may reference one MP3. Audio identity uses accent and source URL, never IPA
alone. Selecting another meaning reuses verified local audio, including after a
restart. Missing audio, invalid signatures and checksum mismatches trigger repair.
Explicitly replacing shared audio affects all entries referencing that file.

### Storage and existing collections

Collection entries have permanent local IDs and separate JSON v3 metadata.
Their `audio_file` may point to the same MP3. Keep JSON files and MP3s together
when moving or backing up the collection. For CLI selection, use the entry's JSON
path with `--recording`; an MP3 path is accepted only when it identifies one meaning.
Filenames remain portable across Windows, macOS and Linux.

Cambridge block and sense IDs identify source entries when available. Changing a
definition, translation or pronunciation list does not change these identities.
Without source IDs, the fallback uses the page, headword, part of speech and block
occurrence, then a definition fingerprint. Such a fallback cannot safely identify
a rewritten or reordered ambiguous source entry. Existing local IDs remain stored;
unmatched choices are never automatically merged. Select the saved record and
choose its updated meaning explicitly when a source match is unavailable. In the
CLI use `cambridge-audio WORD --update-recording PATH_TO_ENTRY.json --sense SENSE_ID
--audio AUDIO_ID --output-dir downloads` (as one command). The saved local ID and
personal translation are retained.

Old v1/v2 sidecars, MP3-only collections and symlink aliases remain readable.
Opening them does not rewrite them. A later metadata save upgrades only that
sidecar atomically, retaining the original collection/export ID, user translations,
source selections and unknown translation languages. Failed replacement retains
the previous JSON; repeating an update is safe. Old duplicate MP3s are not removed
or consolidated automatically. Deleting one collection entry retains audio used
by another entry.

## Backups and transfer

Use **Back up / transfer collection** in the desktop GUI to export or import a
`.cda` archive. Export includes recording metadata, personal translations, shared
MP3s and Anki identity mappings. Import previews added, unchanged and conflicting
entries before applying changes. Choose whether to retain the existing or incoming
version for each conflict; device timestamps do not choose a winner automatically.

The CLI separates preview from applying the import:

```sh
cambridge-audio --output-dir downloads --export-collection ../backup.cda
cambridge-audio --output-dir restored --import-collection ../backup.cda
cambridge-audio --output-dir restored --import-collection ../backup.cda --apply-import
cambridge-audio --output-dir restored --import-collection ../backup.cda --apply-import \
  --resolve-conflict ID=existing
```

Use `ID=incoming` to replace that entry with its archive version. A successful
import retains the previous collection as a sibling backup directory. Export a
backup before moving application data or uninstalling an app.

[Android and iOS](mobile/README.md#backups-transfer-and-anki) use the same `.cda`
format through native file and share controls. The
[storage specification](mobile/storage.md) describes archive limits, checksums,
conflict detection and recovery.

## Translation lookup and editing

Lookup order: personal translation for this sense and language, usable saved
cache, Cambridge bilingual dictionary, installed local WikDict. Audio saving and
playback do not depend on a successful translation. A local fallback keeps the
Cambridge error visible. Missing translation, network failure, blocking, missing
local dictionary and corrupt local dictionary produce separate statuses.

The application supports English words and definitions with optional Russian
translations. The GUI has a **Show Russian translation** checkbox, an offline
dictionary status and **Install WikDict**; no free-form language field is shown.
The TUI offers the same Russian translation toggle in its recording panel and
Settings. English definitions remain visible when translation is off. Interface
language (`--lang en` / `--lang ru`) is independent of this toggle.

The checkbox shows and hides cached Russian results immediately, without repeating
requests for a usable cache. CLI: `--translation russian` enables translation;
`ru` and `русский` are accepted aliases. Other translation languages are rejected
before network access. Existing foreign-language caches and personal edits remain
in JSON with their original language and source; they are not relabeled or deleted.

Translations are resolved against the selected English definition and part of
speech before saving. Matching ignores punctuation, spacing and case. Distinctive
shared words and phrases can also resolve differently worded noun definitions,
provided there is no close competing translation or conflicting negation. Other
parts of speech require a normalized exact definition or an explicit choice:
word overlap cannot establish the direction of an action such as paying versus
receiving. This is a conservative lexical comparison, not a semantic model;
some paraphrases remain unresolved.
Cambridge and installed WikDict use the same matching rules. Dictionary sense IDs
from different pages are not assumed to identify the same meaning.

GUI/TUI previews show the resolved translation next to the English meaning.
**Save meaning** saves that translation together with the audio, without another
translation request. Several Russian formulations for the same matched meaning
are kept together. When no match is reliable, the main panel says so and hides
other source meanings. Saving English and audio remains available. GUI:
**Find translation** opens source candidates; **Edit translation** accepts personal
text. TUI: **Ctrl+T** offers the same optional choices, including before saving.
For a saved entry, these actions remain available without downloading the audio
again. If Anki export asks for a translation choice, open that entry and use
**Find translation** to confirm a source candidate or **Edit translation** to
provide personal text, then export again. For example, an unresolved `good morning`
can be given the personal translation `доброе утро`.
Hiding the translation before saving preserves any prepared translation or
personal text; it does not start another translation request.
Technical source IDs remain available in CLI output and storage.

Confirmed source choices, resolved translations and personal edits are reused
across pronunciations of the same meaning. Personal edits take priority; a late
lookup cannot replace an explicit choice. New personal text takes priority over
an inherited source choice, while edits made during a download are retained.
Among dictionary results, explicit choices precede automatic matches and
unresolved candidates. Unresolved Cambridge caches can use installed WikDict
without repeating the Cambridge request. Old caches with source glosses are
re-evaluated when read without rewriting existing files or personal choices.
Legacy flat translations without source-sense metadata retain their old behaviour.
Unresolved choices still need confirmation before Anki export.

**F2** or **About** in Help opens the installed version, repository link and
code/data license information.
CLI examples, without any audio download:

```sh
cambridge-audio --recording downloads/hello.us.mp3 --translation russian --translate-saved
cambridge-audio --recording downloads/hello.us.mp3 --translation russian --set-translation "привет"
cambridge-audio --recording downloads/hello.us.mp3 --translation russian --reset-translation
cambridge-audio --recording downloads/hello.us.mp3 --translation russian --choose-translation SOURCE_SENSE_ID
```

Personal edits apply to a sense and language, shared by saved pronunciations of
that same sense in the folder, including pronunciations saved after the edit.
Other meanings and languages are untouched. They
survive restart, automatic lookup and redownload. Reset removes only the personal
edit so the original cached dictionary result becomes available again.

## Install the local dictionary

The supported translation direction is **English → Russian**, both for
Cambridge online lookup and the verified local WikDict package.

```sh
cambridge-audio --dictionary-info
cambridge-audio --install-dictionary
cambridge-audio --recording downloads/hello.us.mp3 --translation russian --translate-saved --offline
```

The CLI prints the version, download size, source URL and license before
installation. GUI: **Install WikDict**. TUI: **Ctrl+D**. Both show the package
information before confirmation; the GUI reports downloaded bytes. Installation
is explicit; normal lookup never downloads a dictionary. No API key is needed.
Each GUI click checks the installed package locally. A verified installation or
a damaged package prompts for explicit confirmation before downloading again;
declining leaves the existing file untouched.
Use `--dictionary-dir PATH` to override the platform data directory in CLI/TUI.

The pinned package is `en-ru.sqlite3`, version `2_2026-06`, **20.9 MB** (20,938,752 bytes)
(about 20 MiB). SHA-256:
`3f65395883b996131c9b7a7b7b7c14c1b4458c892fae0050decd71dc0a3b4b0a`.
The application downloads only this pair, without the large English morphology
DB or a full Wiktionary dump. It queries exact source forms; a Cambridge headword
is used as a lemma only when explicitly supplied by Cambridge, with no stemming.

The download is staged beside the destination, bounded by the expected size,
verified by size, pinned SHA-256 and SQLite integrity/schema checks, then replaced
atomically. An interrupted download or failed update leaves an existing package
intact. Lookup verifies the installed package and opens it read-only. Attribution
is installed in `WIKDICT-LICENSE.txt` beside the database.

Default locations:

- Windows: `%LOCALAPPDATA%/cambridge-dictionary-audio/dictionaries`.
- macOS: `~/Library/Application Support/cambridge-dictionary-audio/dictionaries`.
- Linux: `$XDG_DATA_HOME/cambridge-dictionary-audio/dictionaries`, defaulting to
  `~/.local/share/cambridge-dictionary-audio/dictionaries`.

See [data sources and licenses](data-sources.md). WikDict data is CC BY-SA 4.0,
separate from the application's Apache-2.0 code.

## Errors and diagnostics

GUI and TUI errors show a short explanation and an appropriate action, such as
retrying later, checking the connection or choosing another folder. This applies
to translation, audio, collection files, exports and unexpected failures.

**Technical details** is available when an error occurs. In the GUI, expand it
next to the error message to read and copy the original diagnostic. In the TUI, the same
button opens a scrollable dialog; Escape closes it. Details include the original
error and, when available, its underlying cause. They remain hidden by default
and are updated for the current operation. Interface messages use the selected
English/Russian language; the original diagnostic is retained unchanged.
CLI diagnostic output remains available as before.

## Export to Anki

Choose the selected entry or the whole collection, then **Export to Anki** and
save one `.apkg`. Import it in Anki with **File → Import**. No running Anki,
manual field setup or copying into `collection.media` is needed for export.

```sh
cambridge-audio --output-dir downloads --export-anki exports/my-deck.apkg
cambridge-audio --recording downloads/ENTRY.us.json --export-anki exports/selected.apkg
cambridge-audio --output-dir downloads --export-anki exports/tsv --export-format tsv
```

The package contains one note per selected collection entry, a fixed note type,
one card template and deduplicated MP3 media. The front shows the word. The back
shows the chosen translation, definition, part of speech, IPA, accent and audio,
followed by a small **Source** disclosure, closed by default, containing sources
and data-license attribution. The disclosure is stored in the Source field, so
exporting a fresh package and reimporting it also updates cards whose existing
template displays `{{Source}}`, with note updates enabled in Anki. There is no need
to edit that template manually. To update exported content, create
a new package before reimporting it. The deck overview uses the same
compact, closed Source disclosure for its description.
The template defines light and Anki night-mode colours. Text is HTML-escaped,
including user translations and the text inside the Source disclosure.

The note type, field IDs, template ID/ordinal and note GUIDs are stable. GUIDs use
the permanent local collection ID, not editable fields or storage paths. Reimport
into the same Anki collection matches these identities, rather than the word or
translation. Keep the note type's fields and single card template intact.
Existing card scheduling and review history are retained when matching notes are
updated; see the verified scenario below. This utility does not export study
progress or reverse cards.

### Reimport and personal edits

Anki's import options control updates to **notes** and **note types** separately.
The following behaviour was verified in Anki 26.09.3:

- **If newer** for notes: a more recent Anki edit survives an older package, but a
  newer export replaces the note's exported fields, including personal edits in
  Anki. This is not a field-by-field merge.
- **Always** for notes: matching notes receive the exported contents even if the
  Anki edit is newer.
- **Never** for notes: personal contents in Anki remain, but Cambridge updates to
  translation, definition, Audio and Source do not apply to those notes.
- **If newer** for note types: the export's fixed older note-type timestamp lets
  newer custom CSS and template edits in Anki survive. **Never** explicitly keeps
  the existing note type. **Always** can replace custom CSS and templates with the
  exported versions.

For ordinary updates, keep **If newer** for notes. Use **Never** for note types
when you want to retain an existing layout, including an older template that
renders `{{Source}}`. To keep a personal translation through future exports, edit
it in the Cambridge collection, which supplies the exported contents. Editing it
only in Anki does not guarantee preservation on the next import. Import option
labels may differ by Anki version or interface language.

Missing/damaged MP3s or unresolved translation choices fail the export before
replacing the previous package. Existing files are replaced only if recognized as
this application's exports. Sources and license notices are included in each
note's Source field, the deck description and `SOURCES.txt` inside the package.

### Additional TSV export

GUI: select **TSV** in the save dialog. TUI: use a destination ending in `.tsv`;
this creates a folder with that suffix removed. CLI: use `--export-format tsv`
and a folder path. The folder contains `collection.tsv`, `media/`, `IMPORT.txt`
and `SOURCES.txt`. Follow `IMPORT.txt` to create the nine fields, copy the MP3s
and import with Tab separation and HTML enabled. ID remains the first field;
repeat TSV imports match the same note type and ID and retain scheduling.
Do not map the first field to Anki's internal GUID.

### Existing notes imported from TSV

Importing an ordinary new `.apkg` over older TSV notes can create duplicates:
TSV matched the first field, while packages match Anki GUIDs. Changing note type
alone does not establish that correspondence. Do not delete cards with learning
history to work around this difference. Continuing to update those notes with TSV
is supported.

For an explicit transition with the original nine fields and one normal card:

1. In Anki, export the relevant old deck as **Anki Deck Package (.apkg)** with
   **Support older Anki versions** enabled. Retain a backup. This is a copy of the
   collection; the utility does not open your live Anki database.
2. Run the following once, using the same local collection that produced the TSV:

   ```sh
   cambridge-audio --output-dir downloads --anki-reference old-from-anki.apkg
   cambridge-audio --output-dir downloads --export-anki updated.apkg
   ```

3. Import `updated.apkg` in the original Anki profile. Use update-existing-notes
   behaviour, and keep note types unchanged. The package uses the exported GUID
   and original note type for each mapped ID, rather than creating a new identity.

The command reports the number of mapped notes. Only exact first-field IDs are
mapped. Duplicate IDs, incompatible schemas and conflicting prior mappings are
rejected before writing. Unmatched local entries remain new package notes; compare
the mapped count with the old notes you intend to move. Store the generated
`.anki-mapping.json` with the collection and use it for all later exports. Migration
does not rewrite the reference package, delete notes or touch review history.
Collections with extra fields or multiple card templates should keep using TSV.

<a id="verified-anki-round-trip"></a>

### Anki compatibility

Package interoperability is checked against the Anki 26.09.3 backend using
isolated test collections. Checks cover note/card identities, shared media,
scheduler-created review history, repeated imports, updated fields and audio,
custom templates and migration from the original TSV format.

The compatibility model depends on stable collection IDs and the original nine
fields with one card template. Anki's import settings determine which contents
are replaced. Other note layouts should continue using the TSV workflow unless
an explicit mapping supports their schema. Audio quality, device playback and
Anki sync are separate from package compatibility checks.

See [mobile testing](mobile/readiness.md#anki-integration) for the cross-platform
Anki integration script. Anki documents package and text import behaviour in its
[package manual](https://docs.ankiweb.net/manual/importing/packaged-decks) and
[text import manual](https://docs.ankiweb.net/manual/importing/text-files).

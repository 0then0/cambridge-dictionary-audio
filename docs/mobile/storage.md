# Portable storage contract

Sidecar schema remains **3**. Bundle schema is **1**. Application versions and
platform build numbers do not select a storage schema. Python remains the
implementation for desktop/CLI/TUI; `mobile/shared` defines the mobile rules.
`contracts/golden.json` is consumed by both implementations, including original
HTML fixtures, normalization, source identities, filenames, matching and GUIDs.
`contracts/anki.json` freezes model/deck/field/template identities. Regenerate the
Kotlin constant with `python scripts/mobile_contracts.py`; tests reject drift.

## Identity

A collection ID is a stored 24-character lowercase hexadecimal string. New
meanings get random IDs once. Import, edits, source refresh and export retain it.
Source entry/sense IDs are SHA-256 of UTF-8 values separated by NUL, first 24 hex
characters. Upstream Cambridge block and sense IDs take precedence. A fallback
cannot identify an arbitrarily rewritten/reordered source sense. Audio identity
uses accent and source URL, not IPA. Anki GUID is genanki's base-91 representation
of the first eight bytes of SHA-256 of `cambridge-dictionary-audio__COLLECTION_ID`.
Adopted TSV GUID/model mappings override it. Never regenerate adopted identities.

Metadata is a JSON object. Unknown keys, translation languages, cached provenance
and mapping attributes travel in the bundle. Supported legacy v1/v2 metadata and
MP3-only entries become v3 snapshots in a bundle without rewriting their source.
MP3-only IDs are frozen using the existing Python legacy identity calculation.
A future metadata version is refused for transfer, not silently rewritten.

Mobile storage lives in Android `filesDir/collection` and iOS Application Support
`CambridgeAudio/collection`. Cache contains only disposable previews/work/export
files. An app update preserves its application container; uninstall may remove
local data. Export a `.cda` backup before uninstalling or changing signing identity.
Android automatic cloud backup is disabled; this application has no cloud sync.

## Bundle v1

A `.cda` file is ZIP with exactly:

- `manifest.json`: `format = cambridge-dictionary-audio-collection`, `version = 1`,
  `storage_version = 3`, `records = [{id, metadata}]`, `files = {path: {size, sha256}}`.
- `collection/ID.ACCENT.json`: canonical v3 metadata, `variant_id = ID`,
  `audio_file = audio-SHA256.ACCENT.mp3`, `audio_sha256`, `separate_metadata = true`.
- `collection/audio-SHA256.ACCENT.mp3`: shared content, stored once per filename.
- Optional `collection/.anki-mapping.json`: v1 adopted GUID/model mapping and
  monotonic `last_export` state. Orphan note mappings are retained.
- `SOURCES.txt`: dictionary attribution. It does not grant rights to Cambridge data.

All payload members have size and SHA-256 entries in the manifest. No unreferenced
payloads are allowed. IDs and references must agree. Limits: 100,000 ZIP members,
64 MiB per payload, 8 MiB manifest, 2 GiB total uncompressed. Absolute paths,
`..`, empty/dot components, backslashes, colons, NUL, duplicate/case-colliding
paths, directory entries and encrypted members are refused. Archive paths are
never passed to a generic extract-all operation. Python permits legacy audio
symlink aliases only when their resolved target remains inside the collection;
external audio/metadata links cannot be packaged. Mobile storage creates no links.

## Import and recovery

Preview verifies the complete archive before mutation and reports added,
unchanged and conflicting IDs. Any changed record or adopted mapping for an
existing ID needs an explicit `existing` or `incoming` decision. Imported device
clocks never resolve conflicts. A byte revision rejects a stale preview.

Apply constructs a complete staged collection alongside the destination, retaining
unrelated local files and original filenames for existing metadata. It merges
adopted mappings and retains the maximum export timestamp. New files have canonical
names; ambiguous occupied paths are refused. Completed files are flushed before
publication. The previous collection is renamed to a retained sibling
`.COLLECTION.backup-UUID`; then staging becomes the active collection. A recovery
journal records the backup before either rename. If interrupted between renames,
the next collection open restores the previous directory. Failed publication rolls
back. Repeating the same bundle is a no-op. A retained backup is deliberately not
a full undo engine; it can be inspected/exported separately.

Media is reference-counted by collection entries on deletion. Removing one meaning
retains a shared MP3. Checksums detect damaged managed media. Downloads and phrase
work are staged; failed or cancelled subsequent operations retain saved metadata.
Mobile multi-file saves publish a durable `.COLLECTION.write.json` intent only
after all staged files are flushed. Startup completes an interrupted committed
write. Cancellation or a failed flush before intent preserves the existing media
and metadata. Python import also refuses local metadata/mapping symlinks to avoid
writing through a copied link. A corrupt/future sidecar is not overwritten.

## Desktop use

GUI: **Back up / transfer collection**, choose export or import. Import shows the
counts, each conflict's contents and the final preview. CLI:

```sh
cambridge-audio --output-dir downloads --export-collection ../backup.cda
cambridge-audio --output-dir restored --import-collection ../backup.cda
cambridge-audio --output-dir restored --import-collection ../backup.cda --apply-import
cambridge-audio --output-dir restored --import-collection ../backup.cda --apply-import \
  --resolve-conflict ID=existing
```

Keep JSON and MP3 together for manual legacy-folder backups. Bundle import never
accesses a running Anki profile. Exported APKG note updates are still governed by
Anki's **If newer / Always / Never** import options; see the collection guide.

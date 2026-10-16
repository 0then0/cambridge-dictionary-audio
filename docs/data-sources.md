# Dictionary and recording data

Application code is Apache-2.0, with inherited MIT code identified in NOTICE.
Dictionary content and downloaded recordings do not inherit the code license.

## WikDict English → Russian

- Publisher: WikDict by Karl Bartel.
- Origin: Wiktionary contributors, extracted through DBnary.
- License: [Creative Commons Attribution-ShareAlike 4.0 International](https://creativecommons.org/licenses/by-sa/4.0/).
- Official format and provenance: <https://www.wikdict.com/page/download>.
- Verified snapshot: `2_2026-06`, SQLite format version 2.
- Artifact: <https://download.wikdict.com/dictionaries/sqlite/2_2026-06/en-ru.sqlite3>.
- Size: 20,938,752 bytes.
- SHA-256: `3f65395883b996131c9b7a7b7b7c14c1b4458c892fae0050decd71dc0a3b4b0a`.
- Verified on 2026-10-15 against the actual downloaded artifact.

The native `translation` table supplies `written_rep`, `lexentry`, `sense`,
`sense_num`, `trans_list`, `score`, `is_good`, and `importance`. The app queries
`written_rep` exactly and retains `lexentry` and the gloss as provenance.
Translations separated by the dataset's ` | ` delimiter are deduplicated within
each sense after removal of wiki markup. Distinct glosses are not merged.
The full English morphology database is not installed; unsupported inflected
forms are not guessed. A source-provided Cambridge headword may be queried.

Installation retains the database unchanged. Display and Anki export remove
formatting markup and duplicates; these transformations are identified in the
attribution notice. Included WikDict translations and adaptations retain
CC BY-SA 4.0, including its attribution and ShareAlike requirements. The installed
notice and exported SOURCES.txt identify WikDict, Wiktionary, DBnary, the package
version, artifact origin and license. The database is downloaded explicitly and
is not embedded in the code wheel or GUI installers.

To verify a future package, check the official download index and license, inspect
the pair's schema and sample senses, and verify its exact size and SHA-256 before
updating the pinned package in `cambridge_audio/wikdict.py`. Run the opt-in network
check separately from ordinary tests:

```sh
uv run --no-sync python scripts/verify_wikdict.py
```

## Cambridge

Audio, IPA, English definitions and Cambridge bilingual translations originate
at <https://dictionary.cambridge.org/>. They retain their owners' rights and are
subject to [Cambridge's website terms](https://dictionary.cambridge.org/terms-of-use).
No Apache-2.0 or WikDict license is granted to Cambridge content. Exports record
source URLs separately and do not grant redistribution rights to that content.
User edits are labeled User and retain their separate provenance.

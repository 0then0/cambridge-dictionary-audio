# Shared compatibility fixtures

`golden.json` defines shared expected results for Python and Kotlin tests.
Its synthetic HTML fixtures cover shared audio, dictionary source blocks and
pronunciation alternatives without network requests. `bank-russian.html` covers
bilingual translation matching. Fixtures contain only the markup needed for
each regression case, rather than complete dictionary pages.

`anki.json` freezes the public nine-field Anki model and default collection data
produced by the Python exporter. Python tests compare it to current
export code; the mobile generated constant must match this fixture. Do not update
identities to make a failing test pass without investigating compatibility.

`segment-a.mp3` and `segment-b.mp3` are generated 440/880 Hz test tones, 0.5 seconds
each. They contain no Cambridge recordings or personal data. Their source command:
`ffmpeg -f lavfi -i sine=frequency=440:duration=0.5 -c:a libmp3lame segment-a.mp3`
(and 880 Hz for the second). Generated fixtures are available under the application
license. Native pipeline tests decode these real MP3 bitstreams, encode the phrase
and inspect the output; neither tone nor TTS substitutes for dictionary recordings
in the application.

The Android test-only `desktop.cda` fixture contains these tones and three synthetic
entries with fixed test IDs and personal translations labelled `desktop-*`.
It is never bundled with the production application. The opt-in Anki integration
script regenerates a disposable desktop collection and transfers it through the
actual Kotlin core. Tests must never open the user's live Anki profile.

## Updating fixtures

Run `python3 scripts/mobile_contracts.py --check` from the repository root to
verify the generated Kotlin Anki contract. After an intentional contract change,
run the same command without `--check` to regenerate `AnkiContract.kt`, then run
the Python and Kotlin suites.

See [Mobile testing](../docs/mobile/readiness.md) for the native fixtures and
Anki integration workflow, and [Contributing](../CONTRIBUTING.md) for source setup.

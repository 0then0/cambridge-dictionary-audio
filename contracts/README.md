# Shared compatibility fixtures

`golden.json` is consumed by Python and Kotlin tests. Its HTML fixtures are
extracted from the existing Python regression tests, preserving their cases for
shared audio, source blocks and pronunciation alternatives. These are local,
network-independent synthetic markup fixtures, not a complete copy of Cambridge.
`bank-russian.html` preserves the existing bilingual matching case.

`anki.json` freezes the public nine-field Anki model and default collection data
produced by the existing Python exporter. Python tests compare it to current
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
entries with fixed acceptance IDs and personal translations labelled `desktop-*`.
It is never bundled with the production application. The opt-in Anki acceptance
script regenerates a disposable desktop collection and transfers it through the
actual Kotlin core. Tests must never open the user's live Anki profile.

"""Opt-in network verification of the pinned compact WikDict artifact."""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cambridge_audio.wikdict import PACKAGE, install_dictionary, lookup  # noqa: E402


def main():
    print(PACKAGE.description)
    with TemporaryDirectory(prefix="cambridge-wikdict-check-") as directory:
        path = install_dictionary(Path(directory))
        print(f"Verified size, SHA-256, SQLite integrity/schema: {path.name}")
        options = lookup("hello", Path(directory))
        assert options and any("greeting" in o.definition for o in options)
        print(f"Local hello lookup: {len(options)} distinct source senses")
        assert len(lookup("bank", Path(directory))) > 1
        assert lookup("went", Path(directory)) == ()
        print("Ambiguous senses retained; unavailable inflection is not guessed")


if __name__ == "__main__":
    main()

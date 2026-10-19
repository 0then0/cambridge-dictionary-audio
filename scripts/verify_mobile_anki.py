"""Opt-in real Anki backend acceptance using disposable collections only.

Run with Anki's compatible Python, adding its app_packages to PYTHONPATH.
The desktop exporter runs in the repository venv. Kotlin runs via Gradle tests.
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def execute(command, *, env=None):
    subprocess.run([str(c) for c in command], cwd=ROOT, env=env, check=True)


def fixtures(folder):
    code = r"""
import hashlib, json, sys
from pathlib import Path
from cambridge_audio.dictionary import stable_id
from cambridge_audio.library import SavedRecording, save_metadata, read_recording
from cambridge_audio.service import Recording
from cambridge_audio.translations import edit_translation
from cambridge_audio.anki import export_apkg
from cambridge_audio.bundle import export_bundle
root=Path(sys.argv[1]);collection=root/'desktop';collection.mkdir()
records=[]
for word,sense,definition,fixture in [
 ('bank','money','an organization where people keep and borrow money','segment-a.mp3'),
 ('bank','river','the land along the side of a river','segment-a.mp3'),
 ('bay','coast','a part of the coast where the land curves in','segment-b.mp3')]:
 content=(Path('contracts/fixtures')/fixture).read_bytes()
 path=collection/(word+'.us.mp3');path.write_bytes(content)
 identity=stable_id('acceptance',sense)
 record=Recording(word,'us',path,'test',definition,False,'noun','entry-'+word,sense,identity,
  'https://dictionary.cambridge.org/dictionary/english/'+word,
  'https://dictionary.cambridge.org/media/'+word+'.mp3',word,
  collection/(identity+'.us.json'),'entry-'+word,sense,hashlib.sha256(content).hexdigest())
 save_metadata(record);edit_translation(read_recording(record.reference),'russian','desktop-'+sense)
 records.append(read_recording(record.reference))
export_apkg(records,root/'desktop.apkg');export_bundle(collection,root/'desktop.cda')
"""
    execute(
        [ROOT / ".venv/bin/python", "-c", code, folder],
        env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
    )


def verify(folder, gradle):
    from anki.collection import Collection
    from anki.import_export_pb2 import ImportAnkiPackageOptions, ImportAnkiPackageRequest

    folder.mkdir(parents=True, exist_ok=False)
    fixtures(folder)
    profile = folder / "profile"
    profile.mkdir()
    collection = Collection(str(profile / "collection.anki2"))
    report = {
        "adapter": "shared Kotlin core on JVM, not Android/iOS device validation",
        "checks": [],
    }

    def import_package(name):
        collection.import_anki_package(
            ImportAnkiPackageRequest(
                package_path=str(folder / name),
                options=ImportAnkiPackageOptions(update_notes=1, update_notetypes=0),
            )
        )
        collection.models._clear_cache()

    def snapshot():
        return {
            "notes": collection.db.all("SELECT id,guid,mid FROM notes ORDER BY id"),
            "cards": collection.db.all("SELECT * FROM cards ORDER BY id"),
            "revlog": collection.db.all("SELECT * FROM revlog ORDER BY id"),
        }

    try:
        import_package("desktop.apkg")
        assert len(collection.find_notes("")) == 3
        assert len(collection.find_cards("")) == 3
        collection.decks.select(collection.db.scalar("SELECT did FROM cards LIMIT 1"))
        for rating in [3, 4, 3]:
            card = collection.sched.getCard()
            assert card
            card.start_timer()
            collection.sched.answerCard(card, rating)
        before = snapshot()
        assert len(before["revlog"]) == 3
        report["checks"].append("desktop import and three real scheduler answers")
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env["CDA_ACCEPTANCE_ROOT"] = str(folder)
        execute(
            [
                gradle,
                "-p",
                "mobile",
                ":shared:jvmTest",
                "--tests",
                "org.cambridgeaudio.core.CrossPlatformAcceptance",
                "--rerun-tasks",
            ],
            env=env,
        )
        for name in ["mobile.apkg", "second-mobile.apkg"]:
            import_package(name)
            assert snapshot() == before, name
            assert len(collection.find_notes("")) == 3
            translated = [collection.get_note(nid) for nid in collection.find_notes("")]
            money = next(
                n
                for n in translated
                if n["ID"] == __import__("hashlib").sha256(b"acceptance\0money").hexdigest()[:24]
            )
            assert money["Translation"] == "мобильный личный перевод"
            assert money["Definition"] == "updated financial meaning from mobile"
            report["checks"].append(
                name + ": same notes/cards/scheduling/review history; fields updated"
            )
        collection.close()
        collection = Collection(str(profile / "collection.anki2"))
        assert snapshot() == before
        report["checks"].append("close/reopen persisted scheduling and reviews")
        # Return through the actual Python importer and exporter, retaining identities.
        code = """from pathlib import Path
from cambridge_audio.bundle import preview_import,apply_import
from cambridge_audio.library import scan_recordings
from cambridge_audio.anki import export_apkg
import sys
root=Path(sys.argv[1]);target=root/'returned-desktop'
apply_import(preview_import(root/'return.cda',target))
export_apkg(scan_recordings(target),root/'returned-desktop.apkg')
"""
        execute(
            [ROOT / ".venv/bin/python", "-c", code, folder],
            env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
        )
        import_package("returned-desktop.apkg")
        assert snapshot() == before
        report["checks"].append(
            "Kotlin bundle → Python → APKG → Anki keeps all identities and review history"
        )
        report["passed"] = True
    finally:
        collection.close()
        (folder / "anki-results.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--gradle", type=Path, default=ROOT / "mobile/gradlew")
    args = parser.parse_args()
    verify(args.output.absolute(), args.gradle.absolute())

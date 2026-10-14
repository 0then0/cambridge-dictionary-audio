"""Package the already-built Chrome and Firefox extensions as reproducible ZIPs."""

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]


def package_extensions(root: Path = ROOT) -> list[Path]:
    output = root / "extension/dist"
    archives = []
    for browser in ("chrome", "firefox"):
        source = output / browser
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        destination = output / f"cambridge-audio-{browser}-{manifest['version']}.zip"
        with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
            for path in sorted(source.rglob("*")):
                if path.is_file():
                    entry = ZipInfo(
                        path.relative_to(source).as_posix(), date_time=(2020, 1, 1, 0, 0, 0)
                    )
                    entry.compress_type = ZIP_DEFLATED
                    entry.create_system = 3
                    entry.external_attr = 0o100644 << 16
                    archive.writestr(entry, path.read_bytes())
        archives.append(destination)
    return archives


if __name__ == "__main__":
    for path in package_extensions():
        print(path)

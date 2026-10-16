"""Persistent terminal preferences, independent of Textual and Qt."""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile


def settings_path() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData/Roaming")
    elif sys.platform == "darwin":
        root = Path.home() / "Library/Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return root / "cambridge-dictionary-audio/tui-settings.json"


def load_settings() -> dict:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    settings = {}
    for name, choices in {
        "language": ("en", "ru"),
        "accent": ("us", "uk", "both"),
        "theme": ("cambridge-dark", "cambridge-light"),
        "translation": (None, "russian"),
    }.items():
        if name in data and data[name] in choices:
            settings[name] = data[name]
    for name in ("play", "combine"):
        if type(data.get(name)) is bool:
            settings[name] = data[name]
    directory = data.get("directory")
    if isinstance(directory, str) and directory.strip() and "\0" not in directory:
        try:
            path = Path(directory).expanduser()
        except RuntimeError:
            return settings
        if path.is_absolute():
            settings["directory"] = path
    return settings


def save_settings(options, theme: str) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        name: getattr(options, name)
        for name in ("language", "accent", "translation", "play", "combine")
    }
    data.update(directory=str(options.directory), theme=theme)
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as output:
            temporary = Path(output.name)
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class Options:
    directory: Path
    language: str = "en"
    accent: str = "us"
    play: bool = True
    combine: bool = True
    translation: str | None = None
    timeout: float = 15.0
    overwrite: bool = False
    dictionary_dir: Path | None = None
    offline: bool = False

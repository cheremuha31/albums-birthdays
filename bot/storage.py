from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, Iterator, List

from album_analyzer.exporter import load_albums
from album_analyzer.models import AlbumListening

DATA_DIR = Path("bot_data")
DATA_DIR.mkdir(exist_ok=True)


def _user_file(chat_id: int) -> Path:
    return DATA_DIR / f"{chat_id}.json"


def _notifications_file() -> Path:
    return DATA_DIR / "notifications.json"


def save_user_albums(chat_id: int, albums: Iterable[AlbumListening]) -> Path:
    path = _user_file(chat_id)
    payload = {
        "albums": [album.to_dict() for album in albums],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_user_albums(chat_id: int) -> List[AlbumListening]:
    path = _user_file(chat_id)
    if not path.exists():
        return []
    return load_albums(path)


def iter_users() -> Iterator[int]:
    for file in DATA_DIR.glob("*.json"):
        if file.name == "notifications.json":
            continue
        try:
            yield int(file.stem)
        except ValueError:
            continue


def load_notification_log() -> Dict[str, str]:
    path = _notifications_file()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_notification_log(log: Dict[str, str]) -> None:
    _notifications_file().write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

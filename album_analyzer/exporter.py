from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from .models import AlbumListening


def _build_payload(albums: Iterable[AlbumListening]) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "albums": [album.to_dict() for album in albums],
    }


def serialize_albums(albums: Iterable[AlbumListening]) -> str:
    """Return a JSON representation of albums with metadata."""

    payload = _build_payload(albums)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def export_albums(albums: Iterable[AlbumListening], output_path: Path) -> None:
    output_path.write_text(serialize_albums(albums), encoding="utf-8")


def load_albums(path: Path) -> List[AlbumListening]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [AlbumListening.from_dict(entry) for entry in data.get("albums", [])]

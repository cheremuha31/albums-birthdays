import json
from datetime import date
from pathlib import Path

from album_analyzer.exporter import export_albums, load_albums, serialize_albums
from album_analyzer.models import AlbumListening


def test_export_and_load(tmp_path: Path) -> None:
    albums = [
        AlbumListening(album="Album", artist="Artist", minutes=123.4, release_date=date(2020, 5, 1)),
    ]
    output = tmp_path / "albums.json"
    export_albums(albums, output)

    loaded = load_albums(output)
    assert len(loaded) == 1
    assert loaded[0].album == "Album"
    assert loaded[0].release_date == date(2020, 5, 1)
    assert loaded[0].minutes == albums[0].minutes


def test_serialize_albums() -> None:
    albums = [AlbumListening(album="Album", artist="Artist", minutes=50.0)]
    payload = json.loads(serialize_albums(albums))

    assert payload["albums"]
    assert payload["albums"][0]["album"] == "Album"
    assert "generated_at" in payload

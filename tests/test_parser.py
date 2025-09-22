import json
from pathlib import Path
from zipfile import ZipFile

from album_analyzer.parser import aggregate_archives, filter_by_minutes


def test_aggregate_archives(tmp_path: Path) -> None:
    sample = Path(__file__).parent / "data" / "sample_streaming.json"
    albums = aggregate_archives([sample])
    assert len(albums) == 2

    top = albums[0]
    assert top.album == "Test Album"
    assert top.artist == "Test Artist"
    assert round(top.minutes, 2) == 6.0
    assert top.tracks == {"Track One", "Track Two"}

    filtered = filter_by_minutes(albums, minimum_minutes=5)
    assert len(filtered) == 1
    assert filtered[0].album == "Test Album"


def test_aggregate_archives_spotify_zip(tmp_path: Path) -> None:
    archive = tmp_path / "spotify_history.zip"
    entries = [
        {
            "master_metadata_album_album_name": "Album",
            "master_metadata_album_artist_name": "Artist",
            "master_metadata_track_name": "Track One",
            "ms_played": 600_000,
        },
        {
            "albumName": "Album",
            "artistName": "Artist",
            "trackName": "Track Two",
            "msPlayed": 120_000,
        },
    ]
    with ZipFile(archive, "w") as handle:
        handle.writestr(
            "Spotify Extended Streaming History/Streaming_History_Audio_2024.json",
            json.dumps(entries),
        )

    albums = aggregate_archives([archive])
    assert len(albums) == 1

    album = albums[0]
    assert album.album == "Album"
    assert album.artist == "Artist"
    assert round(album.minutes, 1) == 12.0
    assert album.tracks == {"Track One", "Track Two"}

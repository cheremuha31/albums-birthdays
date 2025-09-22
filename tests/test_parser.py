from pathlib import Path

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

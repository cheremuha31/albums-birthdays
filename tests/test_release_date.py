from datetime import date

from album_analyzer import release_date


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:  # pragma: no cover - no-op in tests
        return

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._payloads = [
            {"release-groups": []},
            {
                "release-groups": [
                    {
                        "id": "pinkerton",
                        "first-release-date": "1996-09-24",
                    }
                ]
            },
        ]

    def get(self, url: str, params: dict, headers: dict, timeout: int) -> FakeResponse:
        self.calls.append(params["query"])
        payload = self._payloads.pop(0)
        return FakeResponse(payload)


def test_lookup_release_handles_deluxe_titles() -> None:
    release_date._CACHE.clear()
    session = FakeSession()

    musicbrainz_id, released = release_date.lookup_release(
        "Pinkerton - Deluxe Edition",
        "Weezer",
        session=session,  # type: ignore[arg-type]
    )

    assert musicbrainz_id == "pinkerton"
    assert released == date(1996, 9, 24)
    assert session.calls == [
        'release:"Pinkerton - Deluxe Edition" AND artist:"Weezer"',
        'release:"Pinkerton" AND artist:"Weezer"',
    ]

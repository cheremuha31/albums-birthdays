from album_analyzer.webapp import create_app


def test_webapp_index_get() -> None:
    app = create_app()
    client = app.test_client()

    response = client.get("/")
    assert response.status_code == 200
    assert "albums.json" in response.get_data(as_text=True)


def test_webapp_requires_files() -> None:
    app = create_app()
    client = app.test_client()

    response = client.post(
        "/",
        data={"min_minutes": "60", "pause": "1.1"},
        content_type="multipart/form-data",
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Загрузите хотя бы один архив" in body

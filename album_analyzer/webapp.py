"""Minimal web application for preparing ``albums.json`` files locally."""

from __future__ import annotations

import io
from pathlib import Path
from tempfile import TemporaryDirectory

from flask import Flask, Response, render_template_string, request, send_file
from werkzeug.utils import secure_filename

from .exporter import serialize_albums
from .parser import aggregate_archives, filter_by_minutes
from .release_date import enrich_with_release_dates


INDEX_TEMPLATE = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>albums-birthdays — подготовка JSON</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 720px; line-height: 1.5; }
    header { margin-bottom: 1.5rem; }
    form { display: flex; flex-direction: column; gap: 1rem; padding: 1.5rem; border: 1px solid #dadada; border-radius: 12px; }
    label { font-weight: 600; }
    input[type="file"], input[type="number"] { padding: 0.4rem; }
    input[type="submit"] { padding: 0.6rem 1.2rem; font-size: 1rem; cursor: pointer; background: #1c6ee8; color: white; border: none; border-radius: 8px; }
    .error { color: #a40000; font-weight: 600; }
    .checkbox-group { display: flex; align-items: center; gap: 0.5rem; }
    footer { margin-top: 2rem; font-size: 0.9rem; color: #555; }
  </style>
</head>
<body>
  <header>
    <h1>Подготовка JSON для Telegram-бота</h1>
    <p>Загрузите архивы или JSON-файлы с историей прослушиваний, выберите параметры и получите готовый <code>albums.json</code>.</p>
  </header>
  {% if error %}
    <p class="error">{{ error }}</p>
  {% endif %}
  <form method="post" enctype="multipart/form-data">
    <div>
      <label for="archives">Архивы или JSON-файлы</label><br>
      <input id="archives" type="file" name="archives" multiple required>
    </div>
    <div>
      <label for="min_minutes">Минимум минут прослушивания</label><br>
      <input id="min_minutes" type="number" name="min_minutes" step="1" min="0" value="{{ min_minutes }}" required>
    </div>
    <div class="checkbox-group">
      <input id="fetch_release_dates" type="checkbox" name="fetch_release_dates" value="on" {% if fetch_release_dates %}checked{% endif %}>
      <label for="fetch_release_dates">Запрашивать даты релиза на MusicBrainz</label>
    </div>
    <div>
      <label for="pause">Пауза между запросами к MusicBrainz (сек.)</label><br>
      <input id="pause" type="number" name="pause" step="0.1" min="0" value="{{ pause }}">
    </div>
    <input type="submit" value="Сформировать JSON">
  </form>
  <footer>
    <p>Приложение работает локально. После завершения обработки откроется загрузка файла <code>albums.json</code>.</p>
  </footer>
</body>
</html>
"""


def _parse_float(value: str | None, fallback: float) -> float:
    if value is None:
        return fallback
    try:
        return float(value)
    except ValueError as exc:  # pragma: no cover - validation guard
        raise ValueError("Некорректное числовое значение") from exc


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/", methods=["GET", "POST"])
    def index() -> str | Response:
        error: str | None = None
        min_minutes_raw = request.form.get("min_minutes", "60")
        pause_raw = request.form.get("pause", "1.1")
        fetch_release_dates = request.form.get("fetch_release_dates") == "on" if request.method == "POST" else True
        min_minutes = 60.0
        pause = 1.1

        if request.method == "POST":
            try:
                min_minutes = _parse_float(min_minutes_raw or "60", 60.0)
                if min_minutes < 0:
                    raise ValueError("Минимум минут не может быть отрицательным")
            except ValueError as exc:
                error = str(exc)
            if error is None:
                try:
                    pause = _parse_float(pause_raw or "1.1", 1.1)
                    if pause < 0:
                        raise ValueError("Пауза не может быть отрицательной")
                except ValueError as exc:
                    error = str(exc)

            uploaded_files = []
            if error is None:
                uploaded_files = [
                    item for item in request.files.getlist("archives") if item and item.filename
                ]
                if not uploaded_files:
                    error = "Загрузите хотя бы один архив или JSON-файл."

            if error is None:
                try:
                    with TemporaryDirectory() as temp_dir:
                        temp_path = Path(temp_dir)
                        saved_paths: list[Path] = []
                        for index, item in enumerate(uploaded_files):
                            filename = secure_filename(item.filename) or f"upload_{index}"
                            destination = temp_path / filename
                            item.save(destination)
                            saved_paths.append(destination)
                        albums = aggregate_archives(saved_paths)
                        filtered = filter_by_minutes(albums, minimum_minutes=min_minutes)
                        if fetch_release_dates:
                            filtered = enrich_with_release_dates(filtered, pause_seconds=pause)
                        payload = serialize_albums(filtered)
                except Exception as exc:  # pragma: no cover - runtime guard
                    error = f"Ошибка при обработке данных: {exc}"
                else:
                    buffer = io.BytesIO(payload.encode("utf-8"))
                    buffer.seek(0)
                    return send_file(
                        buffer,
                        mimetype="application/json",
                        as_attachment=True,
                        download_name="albums.json",
                    )

        return render_template_string(
            INDEX_TEMPLATE,
            error=error,
            min_minutes=min_minutes_raw or "60",
            pause=pause_raw or "1.1",
            fetch_release_dates=fetch_release_dates,
        )

    return app


def main() -> None:  # pragma: no cover - entry point for manual runs
    create_app().run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()

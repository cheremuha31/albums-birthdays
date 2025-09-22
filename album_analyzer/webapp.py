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


INDEX_TEMPLATE = r"""
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
    .processing-indicator[hidden] { display: none; }
    .processing-indicator { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(255, 255, 255, 0.88); backdrop-filter: blur(2px); transition: opacity 0.2s ease-in-out; opacity: 0; pointer-events: none; z-index: 1000; }
    .processing-indicator.visible { opacity: 1; pointer-events: all; }
    .processing-content { background: white; padding: 2rem; border-radius: 16px; box-shadow: 0 20px 45px rgba(16, 30, 54, 0.12); max-width: 420px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 1rem; }
    .spinner { width: 52px; height: 52px; border-radius: 50%; border: 5px solid #dbe5ff; border-top-color: #1c6ee8; animation: spin 0.9s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .progress-text { font-weight: 600; }
  </style>
</head>
<body>
  <div id="processing-indicator" class="processing-indicator" hidden>
    <div class="processing-content" role="status" aria-live="polite">
      <div class="spinner" aria-hidden="true"></div>
      <div class="progress-text" data-progress-text>Обработка данных…</div>
      <p>Пожалуйста, не закрывайте окно. Если включен поиск дат релиза, запросы к MusicBrainz могут занять несколько минут.</p>
    </div>
  </div>
  <header>
    <h1>Подготовка JSON для Telegram-бота</h1>
    <p>Загрузите архивы или JSON-файлы с историей прослушиваний, выберите параметры и получите готовый <code>albums.json</code>.</p>
  </header>
  {% if error %}
    <p class="error">{{ error }}</p>
  {% endif %}
  <p id="client-error" class="error" hidden></p>
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
  <script>
    (function () {
      const form = document.querySelector('form');
      const indicator = document.getElementById('processing-indicator');
      const clientErrorBox = document.getElementById('client-error');
      const pywebviewApi = window.pywebview && typeof window.pywebview.api === 'object'
        ? window.pywebview.api
        : null;
      if (!form || !indicator) {
        return;
      }

      const submitButton = form.querySelector('input[type="submit"]');
      const originalButtonText = submitButton ? submitButton.value : '';
      const statusText = indicator.querySelector('[data-progress-text]');
      const frames = ['Обработка данных…', 'Обработка данных.', 'Обработка данных..', 'Обработка данных...'];
      let frameIndex = 0;
      let intervalId;

      function showIndicator() {
        indicator.removeAttribute('hidden');
        indicator.classList.add('visible');
        if (submitButton) {
          submitButton.disabled = true;
          submitButton.value = 'Обработка…';
        }
        if (statusText && !intervalId) {
          intervalId = window.setInterval(() => {
            frameIndex = (frameIndex + 1) % frames.length;
            statusText.textContent = frames[frameIndex];
          }, 600);
        }
      }

      function hideIndicator() {
        indicator.classList.remove('visible');
        indicator.setAttribute('hidden', '');
        if (submitButton) {
          submitButton.disabled = false;
          submitButton.value = originalButtonText || 'Сформировать JSON';
        }
        if (intervalId) {
          window.clearInterval(intervalId);
          intervalId = undefined;
        }
        if (statusText) {
          frameIndex = 0;
          statusText.textContent = frames[0];
        }
      }

      form.addEventListener('submit', async (event) => {
        if (clientErrorBox) {
          clientErrorBox.hidden = true;
          clientErrorBox.textContent = '';
        }

        if (!window.fetch || !window.URL || !window.URL.createObjectURL) {
          showIndicator();
          return;
        }

        event.preventDefault();
        showIndicator();

        try {
          const response = await fetch(form.action || window.location.href, {
            method: 'POST',
            body: new FormData(form),
          });

          const contentType = response.headers.get('Content-Type') || '';

          if (contentType.includes('text/html')) {
            const html = await response.text();
            document.open();
            document.write(html);
            document.close();
            return;
          }

          if (!response.ok) {
            throw new Error(`Request failed with status ${response.status}`);
          }

          const blob = await response.blob();
          const disposition = response.headers.get('Content-Disposition') || '';
          const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
          const plainMatch = disposition.match(/filename="?([^";]+)"?/i);
          let filename = 'albums.json';
          if (utf8Match && utf8Match[1]) {
            filename = decodeURIComponent(utf8Match[1]);
          } else if (plainMatch && plainMatch[1]) {
            filename = plainMatch[1];
          }

          let pywebviewSave = null;
          if (pywebviewApi) {
            if (typeof pywebviewApi.save_albums_json === 'function') {
              pywebviewSave = pywebviewApi.save_albums_json.bind(pywebviewApi);
            } else if (typeof pywebviewApi.saveAlbumsJson === 'function') {
              pywebviewSave = pywebviewApi.saveAlbumsJson.bind(pywebviewApi);
            }
          }

          if (pywebviewSave) {
            try {
              const textContent = await blob.text();
              const result = await pywebviewSave(filename, textContent);
              if (result && result.status === 'saved') {
                return;
              }
              if (result && result.status === 'cancelled') {
                if (clientErrorBox) {
                  clientErrorBox.textContent = 'Сохранение отменено. Повторите попытку при необходимости.';
                  clientErrorBox.hidden = false;
                }
                return;
              }
              if (result && result.status === 'error' && result.message) {
                throw new Error(result.message);
              }
            } catch (pywebviewError) {
              console.error('pywebview: не удалось сохранить файл', pywebviewError);
            }
          }

          const blobUrl = window.URL.createObjectURL(blob);
          const downloadLink = document.createElement('a');
          downloadLink.href = blobUrl;
          downloadLink.download = filename;
          downloadLink.style.display = 'none';
          document.body.appendChild(downloadLink);
          downloadLink.click();
          window.setTimeout(() => {
            document.body.removeChild(downloadLink);
            window.URL.revokeObjectURL(blobUrl);
          }, 0);
        } catch (fetchError) {
          console.error('Ошибка при формировании JSON', fetchError);
          const errorMessage = fetchError && typeof fetchError.message === 'string' && fetchError.message
            ? fetchError.message
            : 'Проверьте подключение к интернету и попробуйте снова.';
          if (clientErrorBox) {
            clientErrorBox.textContent = `Не удалось сформировать или сохранить JSON. ${errorMessage}`;
            clientErrorBox.hidden = false;
          } else {
            window.alert(`Не удалось сформировать или сохранить JSON. ${errorMessage}`);
          }
        } finally {
          hideIndicator();
        }
      });

      window.addEventListener('pageshow', () => {
        hideIndicator();
      });
    })();
  </script>
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

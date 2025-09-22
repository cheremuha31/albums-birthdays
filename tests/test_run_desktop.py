from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from run_desktop import _DesktopApi


@pytest.fixture
def desktop_api() -> _DesktopApi:
    return _DesktopApi(SimpleNamespace())


def test_save_albums_json_prefers_win32(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, desktop_api: _DesktopApi) -> None:
    calls: list[str] = []

    def fake_win32(filename: str):
        calls.append("win32")
        return tmp_path / filename, False, None

    def fail_if_called(_filename: str):  # pragma: no cover - defensive guard
        raise AssertionError("Fallback dialog should not be used when Win32 succeeds")

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(desktop_api, "_prompt_with_win32", fake_win32)
    monkeypatch.setattr(desktop_api, "_prompt_with_tkinter", fail_if_called)
    monkeypatch.setattr(desktop_api, "_prompt_with_pywebview", fail_if_called)

    result = desktop_api.save_albums_json("albums.json", "payload")

    assert result == {"status": "saved"}
    assert (tmp_path / "albums.json").read_text("utf-8") == "payload"
    assert calls == ["win32"]


def test_save_albums_json_falls_back_from_win32(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, desktop_api: _DesktopApi) -> None:
    order: list[str] = []
    destination = tmp_path / "albums.json"

    def failing_win32(_filename: str):
        order.append("win32")
        return None, False, "win32 failure"

    def tkinter_success(filename: str):
        order.append("tk")
        assert filename == "albums.json"
        return destination, False, None

    def fail_if_called(_filename: str):  # pragma: no cover - defensive guard
        raise AssertionError("pywebview fallback should not run once tkinter succeeds")

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(desktop_api, "_prompt_with_win32", failing_win32)
    monkeypatch.setattr(desktop_api, "_prompt_with_tkinter", tkinter_success)
    monkeypatch.setattr(desktop_api, "_prompt_with_pywebview", fail_if_called)

    result = desktop_api.save_albums_json("albums.json", "payload")

    assert result == {"status": "saved"}
    assert destination.read_text("utf-8") == "payload"
    assert order == ["win32", "tk"]


def test_save_albums_json_non_windows_order(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, desktop_api: _DesktopApi) -> None:
    order: list[str] = []
    destination = tmp_path / "albums.json"

    def pywebview_success(filename: str):
        order.append("pywebview")
        return destination, False, None

    def fail_if_called(_filename: str):  # pragma: no cover - defensive guard
        raise AssertionError("tkinter fallback should not run when pywebview succeeds")

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(desktop_api, "_prompt_with_pywebview", pywebview_success)
    monkeypatch.setattr(desktop_api, "_prompt_with_tkinter", fail_if_called)

    result = desktop_api.save_albums_json("albums.json", "payload")

    assert result == {"status": "saved"}
    assert destination.read_text("utf-8") == "payload"
    assert order == ["pywebview"]

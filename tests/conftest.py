"""Shared pytest fixtures for ytaudio tests.

`YoutubeDL` is always mocked here — no network access, no real downloads,
no ffmpeg required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _mock_check_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Autouse: `extract()` gates on `check_ffmpeg()`; tests never need real ffmpeg."""
    monkeypatch.setattr("ytaudio.extractor.check_ffmpeg", lambda: Path("/usr/bin/ffmpeg"))


@pytest.fixture
def fake_info() -> dict[str, Any]:
    """A representative `yt-dlp` `extract_info` result dict."""
    return {
        "title": "Some Video Title",
        "uploader": "Some Channel",
        "duration": 123.45,
        "ext": "webm",
    }


@pytest.fixture
def mock_ydl_class(fake_info: dict[str, Any]) -> MagicMock:
    """A `MagicMock` standing in for `ytaudio.extractor.YoutubeDL`.

    `YoutubeDL(opts)` is used as a context manager: `with YoutubeDL(opts) as ydl: ...`.
    The mocked instance's `extract_info` returns `fake_info` and `prepare_filename`
    returns a deterministic path derived from the title.
    """
    mock_instance = MagicMock()
    mock_instance.extract_info.return_value = fake_info
    mock_instance.prepare_filename.return_value = f"/tmp/{fake_info['title']}.{fake_info['ext']}"
    mock_instance.__enter__.return_value = mock_instance
    mock_instance.__exit__.return_value = False

    mock_class = MagicMock(return_value=mock_instance)
    return mock_class

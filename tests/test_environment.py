from __future__ import annotations

from pathlib import Path

import pytest

from ytaudio.environment import check_ffmpeg, ffmpeg_install_hint
from ytaudio.exceptions import FfmpegNotFoundError


def test_check_ffmpeg_returns_path_when_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/ffmpeg")

    result = check_ffmpeg()

    assert result == Path("/usr/bin/ffmpeg")


def test_check_ffmpeg_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: None)

    with pytest.raises(FfmpegNotFoundError) as exc_info:
        check_ffmpeg()

    assert "ffmpeg" in str(exc_info.value).lower()
    assert exc_info.value.install_hint


@pytest.mark.parametrize(
    ("platform", "expected_snippet"),
    [
        ("darwin", "brew install ffmpeg"),
        ("linux", "apt install ffmpeg"),
        ("win32", "winget install ffmpeg"),
    ],
)
def test_ffmpeg_install_hint_is_os_specific(
    monkeypatch: pytest.MonkeyPatch, platform: str, expected_snippet: str
) -> None:
    monkeypatch.setattr("sys.platform", platform)

    hint = ffmpeg_install_hint()

    assert "ffmpeg is required to extract audio" in hint
    assert expected_snippet in hint
    assert "https://ffmpeg.org/download.html" in hint


def test_check_ffmpeg_error_message_includes_os_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr("sys.platform", "darwin")

    with pytest.raises(FfmpegNotFoundError) as exc_info:
        check_ffmpeg()

    assert "brew install ffmpeg" in exc_info.value.install_hint

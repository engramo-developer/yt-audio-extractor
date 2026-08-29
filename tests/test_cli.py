from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import ytaudio
from ytaudio.cli import build_parser, main
from ytaudio.exceptions import FfmpegNotFoundError, VideoUnavailableError
from ytaudio.options import AudioFormat, ExtractionResult, PlayerClient


def _fake_result(url: str) -> ExtractionResult:
    return ExtractionResult(
        url=url,
        filepath=Path("/tmp/Some Video.mp3"),
        title="Some Video",
        artist="Some Channel",
        duration_s=123.45,
        format=AudioFormat.MP3,
        client_used=PlayerClient.ANDROID,
    )


@pytest.fixture(autouse=True)
def _mock_check_ffmpeg_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """By default ffmpeg is present; individual tests override to simulate absence."""
    monkeypatch.setattr("ytaudio.cli.check_ffmpeg", lambda: Path("/usr/bin/ffmpeg"))


def test_build_parser_parses_defaults() -> None:
    parser = build_parser()

    args = parser.parse_args(["https://example.com/video"])

    assert args.urls == ["https://example.com/video"]
    assert args.format == "mp3"
    assert args.quality == "0"
    assert args.quiet is False
    assert args.no_metadata is False
    assert args.no_thumbnail is False


def test_build_parser_accepts_multiple_urls_and_options(tmp_path: Path) -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "url1",
            "url2",
            "-o",
            str(tmp_path),
            "-f",
            "opus",
            "-q",
            "5",
            "--quiet",
            "--no-metadata",
            "--no-thumbnail",
            "--cookies-from-browser",
            "chrome",
        ]
    )

    assert args.urls == ["url1", "url2"]
    assert args.output_dir == tmp_path
    assert args.format == "opus"
    assert args.quality == "5"
    assert args.quiet is True
    assert args.no_metadata is True
    assert args.no_thumbnail is True
    assert args.cookies_from_browser == "chrome"


def test_main_returns_zero_on_all_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_extractor = MagicMock()
    mock_extractor.extract.side_effect = lambda url: _fake_result(url)
    monkeypatch.setattr("ytaudio.cli.AudioExtractor", MagicMock(return_value=mock_extractor))

    exit_code = main(["https://example.com/a", "https://example.com/b"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Some Video" in out
    assert "✓" in out


def test_main_returns_one_on_partial_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_extractor = MagicMock()

    def extract_side_effect(url: str) -> ExtractionResult:
        if url == "https://example.com/bad":
            raise VideoUnavailableError("video is private")
        return _fake_result(url)

    mock_extractor.extract.side_effect = extract_side_effect
    monkeypatch.setattr("ytaudio.cli.AudioExtractor", MagicMock(return_value=mock_extractor))

    exit_code = main(["https://example.com/good", "https://example.com/bad"])

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "video is private" in err


def test_main_quiet_suppresses_success_output_but_not_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mock_extractor = MagicMock()

    def extract_side_effect(url: str) -> ExtractionResult:
        if url == "https://example.com/bad":
            raise VideoUnavailableError("boom")
        return _fake_result(url)

    mock_extractor.extract.side_effect = extract_side_effect
    monkeypatch.setattr("ytaudio.cli.AudioExtractor", MagicMock(return_value=mock_extractor))

    exit_code = main(["--quiet", "https://example.com/good", "https://example.com/bad"])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "boom" in captured.err


def test_main_returns_two_when_ffmpeg_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def raise_missing() -> Path:
        raise FfmpegNotFoundError("brew install ffmpeg")

    monkeypatch.setattr("ytaudio.cli.check_ffmpeg", raise_missing)
    mock_extractor_class = MagicMock()
    monkeypatch.setattr("ytaudio.cli.AudioExtractor", mock_extractor_class)

    exit_code = main(["https://example.com/a"])

    assert exit_code == 2
    err = capsys.readouterr().err
    assert "ffmpeg" in err.lower()
    mock_extractor_class.assert_not_called()


def test_main_version_exits_zero_and_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert ytaudio.__version__ in out


def test_main_missing_url_arg_exits_two() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([])

    assert exc_info.value.code == 2


def test_main_invalid_format_choice_exits_two() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["https://example.com/a", "-f", "bogus"])

    assert exc_info.value.code == 2

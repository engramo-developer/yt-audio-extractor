from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from yt_dlp.utils import DownloadError

from ytaudio.exceptions import BotProtectionError, VideoUnavailableError
from ytaudio.extractor import AudioExtractor
from ytaudio.options import AudioFormat, ExtractionResult, ExtractOptions, PlayerClient


def test_build_ydl_opts_uses_client_and_format(tmp_path: Path) -> None:
    options = ExtractOptions(
        output_dir=tmp_path,
        audio_format=AudioFormat.MP3,
        embed_metadata=False,
        embed_thumbnail=False,
    )
    extractor = AudioExtractor(options)

    opts = extractor._build_ydl_opts(PlayerClient.ANDROID)

    assert opts["format"] == "bestaudio/best"
    assert opts["outtmpl"] == str(tmp_path / "%(title)s.%(ext)s")
    assert opts["extractor_args"] == {"youtube": {"player_client": ["android"]}}

    postprocessors = opts["postprocessors"]
    assert len(postprocessors) == 1
    pp = postprocessors[0]
    assert pp["key"] == "FFmpegExtractAudio"
    assert pp["preferredcodec"] == "mp3"
    assert pp["preferredquality"] == "0"


def test_build_ydl_opts_reflects_client(tmp_path: Path) -> None:
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path))

    opts = extractor._build_ydl_opts(PlayerClient.WEB)

    assert opts["extractor_args"] == {"youtube": {"player_client": ["web"]}}


def test_build_ydl_opts_is_silent_by_default(tmp_path: Path) -> None:
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path))

    opts = extractor._build_ydl_opts(PlayerClient.ANDROID)

    assert opts["quiet"] is True
    assert opts["no_warnings"] is True
    assert "logger" in opts
    assert "verbose" not in opts


def test_build_ydl_opts_verbose_shows_logs(tmp_path: Path) -> None:
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path, verbose=True))

    opts = extractor._build_ydl_opts(PlayerClient.ANDROID)

    assert opts["verbose"] is True
    assert "quiet" not in opts
    assert "logger" not in opts


def test_build_ydl_opts_wires_progress_hook_when_set(tmp_path: Path) -> None:
    def hook(status: dict[str, Any]) -> None:
        return None

    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path, progress_hook=hook))

    opts = extractor._build_ydl_opts(PlayerClient.ANDROID)

    assert opts["progress_hooks"] == [hook]


def test_build_ydl_opts_omits_progress_hook_by_default(tmp_path: Path) -> None:
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path))

    opts = extractor._build_ydl_opts(PlayerClient.ANDROID)

    assert "progress_hooks" not in opts


def test_extract_calls_extract_info_with_download_true(
    monkeypatch: pytest.MonkeyPatch, mock_ydl_class: MagicMock, tmp_path: Path
) -> None:
    monkeypatch.setattr("ytaudio.extractor.YoutubeDL", mock_ydl_class)
    url = "https://www.youtube.com/watch?v=abc123"
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path))

    extractor.extract(url)

    mock_ydl_class.return_value.extract_info.assert_called_once_with(url, download=True)


def test_extract_returns_populated_extraction_result(
    monkeypatch: pytest.MonkeyPatch,
    mock_ydl_class: MagicMock,
    fake_info: dict[str, Any],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("ytaudio.extractor.YoutubeDL", mock_ydl_class)
    url = "https://www.youtube.com/watch?v=abc123"
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path, audio_format=AudioFormat.MP3))

    result = extractor.extract(url)

    assert result.url == url
    assert result.title == fake_info["title"]
    assert result.artist == fake_info["uploader"]
    assert result.duration_s == fake_info["duration"]
    assert result.format is AudioFormat.MP3
    assert result.client_used is PlayerClient.ANDROID
    assert result.filepath.suffix == ".mp3"


def test_extract_raises_video_unavailable_when_info_is_none(
    monkeypatch: pytest.MonkeyPatch, mock_ydl_class: MagicMock, tmp_path: Path
) -> None:
    mock_ydl_class.return_value.extract_info.return_value = None
    monkeypatch.setattr("ytaudio.extractor.YoutubeDL", mock_ydl_class)
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path))

    with pytest.raises(VideoUnavailableError):
        extractor.extract("https://www.youtube.com/watch?v=missing")


def test_extract_falls_back_to_next_client_on_bot_wall(
    monkeypatch: pytest.MonkeyPatch,
    mock_ydl_class: MagicMock,
    fake_info: dict[str, Any],
    tmp_path: Path,
) -> None:
    mock_ydl_class.return_value.extract_info.side_effect = [
        DownloadError("Sign in to confirm you're not a bot"),
        fake_info,
    ]
    monkeypatch.setattr("ytaudio.extractor.YoutubeDL", mock_ydl_class)
    options = ExtractOptions(output_dir=tmp_path)
    extractor = AudioExtractor(options)

    result = extractor.extract("https://www.youtube.com/watch?v=abc123")

    assert result.client_used is options.client_order[1]
    assert mock_ydl_class.call_count == 2


def test_extract_fails_fast_on_fatal_error_without_retrying(
    monkeypatch: pytest.MonkeyPatch, mock_ydl_class: MagicMock, tmp_path: Path
) -> None:
    mock_ydl_class.return_value.extract_info.side_effect = DownloadError("Video unavailable")
    monkeypatch.setattr("ytaudio.extractor.YoutubeDL", mock_ydl_class)
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path))

    with pytest.raises(VideoUnavailableError):
        extractor.extract("https://www.youtube.com/watch?v=gone")

    assert mock_ydl_class.call_count == 1


def test_extract_raises_bot_protection_when_all_clients_exhausted(
    monkeypatch: pytest.MonkeyPatch, mock_ydl_class: MagicMock, tmp_path: Path
) -> None:
    mock_ydl_class.return_value.extract_info.side_effect = DownloadError(
        "Sign in to confirm you're not a bot"
    )
    monkeypatch.setattr("ytaudio.extractor.YoutubeDL", mock_ydl_class)
    options = ExtractOptions(output_dir=tmp_path)
    extractor = AudioExtractor(options)

    with pytest.raises(BotProtectionError) as exc_info:
        extractor.extract("https://www.youtube.com/watch?v=stuck")

    assert mock_ydl_class.call_count == len(options.client_order)
    for client in options.client_order:
        assert client.value in str(exc_info.value)


def test_extract_many_skips_failed_urls_without_aborting_batch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path))

    def fake_extract(url: str) -> ExtractionResult:
        if url == "https://bad":
            raise BotProtectionError("all clients exhausted")
        return ExtractionResult(
            url=url,
            filepath=tmp_path / "out.mp3",
            title="t",
            artist=None,
            duration_s=None,
            format=AudioFormat.MP3,
            client_used=PlayerClient.ANDROID,
        )

    monkeypatch.setattr(extractor, "extract", fake_extract)

    results = extractor.extract_many(["https://bad", "https://good"])

    assert len(results) == 1
    assert results[0].url == "https://good"


def test_build_ydl_opts_includes_ffmpeg_metadata_when_embed_metadata_true(
    tmp_path: Path,
) -> None:
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path, embed_metadata=True))

    opts = extractor._build_ydl_opts(PlayerClient.ANDROID)

    keys = [pp["key"] for pp in opts["postprocessors"]]
    assert "FFmpegMetadata" in keys
    metadata_pp = next(pp for pp in opts["postprocessors"] if pp["key"] == "FFmpegMetadata")
    assert metadata_pp["add_metadata"] is True


def test_build_ydl_opts_omits_ffmpeg_metadata_when_embed_metadata_false(
    tmp_path: Path,
) -> None:
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path, embed_metadata=False))

    opts = extractor._build_ydl_opts(PlayerClient.ANDROID)

    keys = [pp["key"] for pp in opts["postprocessors"]]
    assert "FFmpegMetadata" not in keys


def test_build_ydl_opts_includes_embed_thumbnail_and_writethumbnail_when_true(
    tmp_path: Path,
) -> None:
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path, embed_thumbnail=True))

    opts = extractor._build_ydl_opts(PlayerClient.ANDROID)

    keys = [pp["key"] for pp in opts["postprocessors"]]
    assert "EmbedThumbnail" in keys
    assert opts["writethumbnail"] is True


def test_build_ydl_opts_omits_embed_thumbnail_and_writethumbnail_when_false(
    tmp_path: Path,
) -> None:
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path, embed_thumbnail=False))

    opts = extractor._build_ydl_opts(PlayerClient.ANDROID)

    keys = [pp["key"] for pp in opts["postprocessors"]]
    assert "EmbedThumbnail" not in keys
    assert "writethumbnail" not in opts


def test_build_ydl_opts_postprocessor_order_extract_audio_before_thumbnail(
    tmp_path: Path,
) -> None:
    extractor = AudioExtractor(
        ExtractOptions(output_dir=tmp_path, embed_metadata=True, embed_thumbnail=True)
    )

    opts = extractor._build_ydl_opts(PlayerClient.ANDROID)

    keys = [pp["key"] for pp in opts["postprocessors"]]
    assert keys == ["FFmpegExtractAudio", "FFmpegMetadata", "EmbedThumbnail"]


def test_build_ydl_opts_sets_cookiesfrombrowser_tuple_when_configured(tmp_path: Path) -> None:
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path, cookies_from_browser="chrome"))

    opts = extractor._build_ydl_opts(PlayerClient.ANDROID)

    assert opts["cookiesfrombrowser"] == ("chrome",)
    assert "cookiefile" not in opts


def test_build_ydl_opts_sets_cookiefile_when_configured(tmp_path: Path) -> None:
    cookies_path = tmp_path / "cookies.txt"
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path, cookies_file=cookies_path))

    opts = extractor._build_ydl_opts(PlayerClient.ANDROID)

    assert opts["cookiefile"] == str(cookies_path)
    assert "cookiesfrombrowser" not in opts


def test_build_ydl_opts_omits_cookie_keys_by_default(tmp_path: Path) -> None:
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path))

    opts = extractor._build_ydl_opts(PlayerClient.ANDROID)

    assert "cookiesfrombrowser" not in opts
    assert "cookiefile" not in opts


def test_probe_calls_extract_info_with_download_false(
    monkeypatch: pytest.MonkeyPatch, mock_ydl_class: MagicMock, tmp_path: Path
) -> None:
    monkeypatch.setattr("ytaudio.extractor.YoutubeDL", mock_ydl_class)
    url = "https://www.youtube.com/watch?v=abc123"
    extractor = AudioExtractor(ExtractOptions(output_dir=tmp_path))

    info = extractor.probe(url)

    mock_ydl_class.return_value.extract_info.assert_called_once_with(url, download=False)
    assert info["title"] == "Some Video Title"

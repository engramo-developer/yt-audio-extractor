from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from ytaudio.options import AudioFormat, ExtractionResult, ExtractOptions, PlayerClient


def test_extract_options_defaults() -> None:
    options = ExtractOptions()

    assert options.output_dir == Path.cwd()
    assert options.output_template == "%(title)s.%(ext)s"
    assert options.audio_format is AudioFormat.MP3
    assert options.audio_quality == "0"
    assert options.embed_metadata is True
    assert options.embed_thumbnail is True
    assert options.cookies_from_browser is None
    assert options.cookies_file is None
    assert options.client_order == (
        PlayerClient.ANDROID,
        PlayerClient.TV,
        PlayerClient.WEB,
    )
    assert options.quiet is False


def test_extract_options_normalizes_str_output_dir_and_expands_tilde() -> None:
    options = ExtractOptions(output_dir="~/Music")

    assert isinstance(options.output_dir, Path)
    assert options.output_dir == Path.home() / "Music"


def test_extract_options_normalizes_str_cookies_file_and_expands_tilde() -> None:
    options = ExtractOptions(cookies_file="~/cookies.txt")

    assert isinstance(options.cookies_file, Path)
    assert options.cookies_file == Path.home() / "cookies.txt"


def test_extract_options_is_frozen() -> None:
    options = ExtractOptions()

    with pytest.raises(dataclasses.FrozenInstanceError):
        options.quiet = True  # type: ignore[misc]


def test_audio_format_values_match_ffmpeg_codec_tokens() -> None:
    assert AudioFormat.MP3.value == "mp3"
    assert AudioFormat.M4A.value == "m4a"
    assert AudioFormat.OPUS.value == "opus"
    assert AudioFormat.FLAC.value == "flac"


def test_player_client_values_match_yt_dlp_tokens() -> None:
    assert PlayerClient.ANDROID.value == "android"
    assert PlayerClient.TV.value == "tv"
    assert PlayerClient.WEB.value == "web"


def test_extraction_result_is_frozen() -> None:
    result = ExtractionResult(
        url="https://example.com/watch?v=abc",
        filepath=Path("/tmp/song.mp3"),
        title="Song",
        artist="Artist",
        duration_s=200.0,
        format=AudioFormat.MP3,
        client_used=PlayerClient.ANDROID,
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.title = "Other"  # type: ignore[misc]

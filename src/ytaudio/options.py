"""Configuration and result data model for ytaudio.

Frozen dataclasses are the single source of truth for defaults and translate
user intent into `yt-dlp` options. Enums subclass `str, Enum` so their
`.value` is the exact token `yt-dlp` expects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class AudioFormat(str, Enum):
    """Target audio container/codec produced by the `FFmpegExtractAudio` postprocessor."""

    MP3 = "mp3"
    M4A = "m4a"
    OPUS = "opus"
    FLAC = "flac"


class PlayerClient(str, Enum):
    """YouTube "innertube" player client used for extraction (anti-bot fallback ladder)."""

    ANDROID = "android"
    TV = "tv"
    WEB = "web"


@dataclass(frozen=True, slots=True)
class ExtractOptions:
    """User-facing configuration for :class:`ytaudio.extractor.AudioExtractor`."""

    output_dir: str | Path = field(default_factory=Path.cwd)
    output_template: str = "%(title)s.%(ext)s"
    audio_format: AudioFormat = AudioFormat.MP3
    audio_quality: str = "0"  # yt-dlp/ffmpeg VBR scale, 0 = best
    embed_metadata: bool = True
    embed_thumbnail: bool = True
    cookies_from_browser: str | None = None  # e.g. "chrome", "firefox"
    cookies_file: str | Path | None = None
    client_order: tuple[PlayerClient, ...] = (
        PlayerClient.ANDROID,
        PlayerClient.TV,
        PlayerClient.WEB,
    )
    quiet: bool = False

    def __post_init__(self) -> None:
        # Accept str or Path for path-like fields, and expand a leading `~`,
        # so `output_dir="~/Music"` works. Frozen dataclass → set via object.
        object.__setattr__(self, "output_dir", Path(self.output_dir).expanduser())
        if self.cookies_file is not None:
            object.__setattr__(self, "cookies_file", Path(self.cookies_file).expanduser())


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Structured outcome of a successful extraction."""

    url: str
    filepath: Path
    title: str
    artist: str | None
    duration_s: float | None
    format: AudioFormat
    client_used: PlayerClient

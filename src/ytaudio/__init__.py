"""ytaudio — a zero-config Python library and CLI to extract audio from YouTube.

Wraps `yt-dlp` to abstract away format selection, `ffmpeg` post-processing,
ID3/thumbnail embedding, and YouTube's anti-bot mitigations.
"""

from __future__ import annotations

from ytaudio.exceptions import (
    BotProtectionError,
    FfmpegNotFoundError,
    UnsupportedURLError,
    VideoUnavailableError,
    YtAudioError,
)
from ytaudio.extractor import AudioExtractor
from ytaudio.options import AudioFormat, ExtractionResult, ExtractOptions, PlayerClient

__version__ = "0.1.0"

__all__ = [
    "AudioExtractor",
    "AudioFormat",
    "BotProtectionError",
    "ExtractOptions",
    "ExtractionResult",
    "FfmpegNotFoundError",
    "PlayerClient",
    "UnsupportedURLError",
    "VideoUnavailableError",
    "YtAudioError",
    "__version__",
]

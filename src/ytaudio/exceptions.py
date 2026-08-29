"""Typed exception hierarchy for ytaudio.

All errors raised by this library derive from :class:`YtAudioError`, so
consumers can catch precisely with a single `except YtAudioError:` clause or
narrow down to a specific failure mode.
"""

from __future__ import annotations


class YtAudioError(Exception):
    """Base class for all errors raised by ytaudio."""


class FfmpegNotFoundError(YtAudioError):
    """Raised when the `ffmpeg` binary cannot be located on PATH.

    Carries an OS-specific install hint (e.g. "brew install ffmpeg") so
    callers can surface actionable guidance to the user.
    """

    def __init__(self, install_hint: str) -> None:
        self.install_hint = install_hint
        super().__init__(f"ffmpeg was not found on PATH. {install_hint}")


class VideoUnavailableError(YtAudioError):
    """Raised when the requested video is fatally unavailable (private, deleted, geo-blocked).

    Non-retriable: no player-client or cookie fallback can recover from this.
    """


class BotProtectionError(YtAudioError):
    """Raised when YouTube's anti-bot wall blocks extraction after all fallback strategies."""


class UnsupportedURLError(YtAudioError):
    """Raised when the given URL is not supported by the underlying `yt-dlp` extractors."""

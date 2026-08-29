"""`yt-dlp` error classification for the client fallback ladder.

`classify_error` centralizes the mapping from `yt-dlp`'s error text to fatal
vs. retriable outcomes, so wording changes only touch one function. The client
rotation itself is just iteration over `ExtractOptions.client_order` in the
extractor — no separate strategy object is needed now that cookies (when
configured) are applied on every attempt.
"""

from __future__ import annotations

from ytaudio.exceptions import BotProtectionError, VideoUnavailableError, YtAudioError

# Substrings indicating the video itself is unavailable — no client rotation
# can recover from these, so we fail fast instead of trying every client.
_FATAL_PATTERNS: tuple[str, ...] = (
    "video unavailable",
    "private video",
    "this video is not available",
    "has been removed",
    "video has been deleted",
    "members-only",
    "who has blocked it",
    "account associated with this video has been terminated",
)

# Substrings indicating a transient/bot-wall failure — retriable by trying the
# next player client. Documented here for reference; `classify_error` treats
# any non-fatal message as retriable, so this list need not be exhaustive.
_RETRIABLE_PATTERNS: tuple[str, ...] = (
    "sign in to confirm you're not a bot",
    "confirm you're not a bot",
    "the page needs to be reloaded",
    "http error 403",
    "unable to download webpage",
    "failed to extract",
    "sign in to confirm your age",
    "requested format is not available",
)


def classify_error(exc: Exception) -> type[YtAudioError]:
    """Classify a `yt_dlp.utils.DownloadError` as fatal or retriable.

    Returns `VideoUnavailableError` when the message indicates the video
    itself is unavailable (fail fast, no point trying other clients). Returns
    `BotProtectionError` for bot-wall/transient signals, and as the default
    for any unrecognized message (better to try the next client than abort on
    unfamiliar wording).
    """
    message = str(exc).lower()
    if any(pattern in message for pattern in _FATAL_PATTERNS):
        return VideoUnavailableError
    return BotProtectionError

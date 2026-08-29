"""Fallback strategy ladder + `yt-dlp` error classification.

`build_strategies` encodes the escalation order (client rotation, then
optional cookie-enabled retries) as data rather than branching logic, so
tuning the ladder is a config change, not a code change. `classify_error`
centralizes the mapping from `yt-dlp`'s error text to retriable vs. fatal
outcomes, so wording changes only touch one function.
"""

from __future__ import annotations

from dataclasses import dataclass

from ytaudio.exceptions import BotProtectionError, VideoUnavailableError, YtAudioError
from ytaudio.options import ExtractOptions, PlayerClient

# Substrings indicating the video itself is unavailable — no client/cookie
# fallback can recover from these, so we fail fast instead of burning the
# rest of the ladder.
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

# Substrings indicating a transient/bot-wall failure — retriable via the
# next strategy (different player client, or a cookie-enabled retry).
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


@dataclass(frozen=True, slots=True)
class FallbackStrategy:
    """One attempt in the fallback ladder: a player client, optionally with cookies."""

    client: PlayerClient
    use_cookies: bool


def build_strategies(options: ExtractOptions) -> list[FallbackStrategy]:
    """Build the ordered ladder of attempts for `options`.

    First, one strategy per client in `client_order` without cookies. Then,
    only if cookies are configured (`cookies_from_browser` or `cookies_file`
    is set), one cookie-enabled strategy per client, appended in the same
    client order.
    """
    strategies = [FallbackStrategy(client, use_cookies=False) for client in options.client_order]
    if options.cookies_from_browser or options.cookies_file:
        strategies.extend(
            FallbackStrategy(client, use_cookies=True) for client in options.client_order
        )
    return strategies


def classify_error(exc: Exception) -> type[YtAudioError]:
    """Classify a `yt_dlp.utils.DownloadError` as fatal or retriable.

    Returns `VideoUnavailableError` when the message indicates the video
    itself is unavailable (fail fast, no point retrying). Returns
    `BotProtectionError` for bot-wall/transient signals, and as the default
    for any unrecognized message (better to try the next strategy than abort
    on unfamiliar wording).
    """
    message = str(exc).lower()
    if any(pattern in message for pattern in _FATAL_PATTERNS):
        return VideoUnavailableError
    return BotProtectionError

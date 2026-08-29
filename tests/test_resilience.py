from __future__ import annotations

import pytest

from ytaudio.exceptions import BotProtectionError, VideoUnavailableError
from ytaudio.resilience import classify_error


@pytest.mark.parametrize(
    "message",
    [
        "ERROR: [youtube] abc123: Video unavailable",
        "ERROR: Private video",
        "This video is not available",
        "This video has been removed by the uploader",
        "This video has been deleted",
        "This is a members-only video",
        "The uploader's account associated with this video has been terminated",
        "This video is unavailable because the channel who has blocked it",
    ],
)
def test_classify_error_fatal_patterns_map_to_video_unavailable(message: str) -> None:
    assert classify_error(Exception(message)) is VideoUnavailableError


@pytest.mark.parametrize(
    "message",
    [
        "Sign in to confirm you're not a bot",
        "Sign in to confirm you're not a bot before you can view this video",
        "The page needs to be reloaded",
        "HTTP Error 403: Forbidden",
        "Unable to download webpage: HTTP Error 429",
        "Failed to extract player response",
        "Sign in to confirm your age",
        "Requested format is not available",
    ],
)
def test_classify_error_retriable_patterns_map_to_bot_protection(message: str) -> None:
    assert classify_error(Exception(message)) is BotProtectionError


def test_classify_error_unknown_message_defaults_to_bot_protection() -> None:
    assert classify_error(Exception("some completely unrecognized error string")) is (
        BotProtectionError
    )

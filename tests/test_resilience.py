from __future__ import annotations

from pathlib import Path

import pytest

from ytaudio.exceptions import BotProtectionError, VideoUnavailableError
from ytaudio.options import ExtractOptions, PlayerClient
from ytaudio.resilience import FallbackStrategy, build_strategies, classify_error


def test_build_strategies_no_cookies_returns_one_per_client_in_order() -> None:
    options = ExtractOptions(cookies_from_browser=None, cookies_file=None)

    strategies = build_strategies(options)

    assert len(strategies) == len(options.client_order)
    assert all(not strategy.use_cookies for strategy in strategies)
    assert [strategy.client for strategy in strategies] == list(options.client_order)


def test_build_strategies_with_cookies_appends_cookie_retries_last() -> None:
    options = ExtractOptions(cookies_from_browser="chrome")

    strategies = build_strategies(options)

    assert len(strategies) == 2 * len(options.client_order)

    no_cookie_strategies = strategies[: len(options.client_order)]
    cookie_strategies = strategies[len(options.client_order) :]

    assert all(not strategy.use_cookies for strategy in no_cookie_strategies)
    assert all(strategy.use_cookies for strategy in cookie_strategies)
    assert [s.client for s in no_cookie_strategies] == list(options.client_order)
    assert [s.client for s in cookie_strategies] == list(options.client_order)


def test_build_strategies_with_cookies_file_also_appends_cookie_retries() -> None:
    options = ExtractOptions(cookies_file=Path("/tmp/cookies.txt"))

    strategies = build_strategies(options)

    assert len(strategies) == 2 * len(options.client_order)


def test_fallback_strategy_is_frozen_dataclass() -> None:
    strategy = FallbackStrategy(client=PlayerClient.ANDROID, use_cookies=False)

    assert strategy.client is PlayerClient.ANDROID
    assert strategy.use_cookies is False


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

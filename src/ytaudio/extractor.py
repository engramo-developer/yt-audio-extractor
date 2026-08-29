"""The `AudioExtractor` engine — the public façade around `yt-dlp`.

Runs the player-client fallback ladder from `resilience.py`: each configured
client is tried in order, then (if cookies are configured) a cookie-enabled
retry per client. Retriable `yt-dlp` errors (bot-walls, transient failures)
advance to the next strategy; fatal errors (video unavailable) fail fast.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from ytaudio.environment import check_ffmpeg
from ytaudio.exceptions import BotProtectionError, VideoUnavailableError, YtAudioError
from ytaudio.options import ExtractionResult, ExtractOptions
from ytaudio.resilience import FallbackStrategy, build_strategies, classify_error


class AudioExtractor:
    """Smart, zero-config audio extractor around yt-dlp."""

    def __init__(self, options: ExtractOptions | None = None) -> None:
        self._options = options if options is not None else ExtractOptions()

    def _build_ydl_opts(self, strategy: FallbackStrategy) -> dict[str, Any]:
        """Build the `yt-dlp` options dict for a single fallback `strategy`."""
        outtmpl = str(self._options.output_dir / self._options.output_template)
        postprocessors: list[dict[str, Any]] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": self._options.audio_format.value,
                "preferredquality": self._options.audio_quality,
            }
        ]
        if self._options.embed_metadata:
            postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})

        opts: dict[str, Any] = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "quiet": self._options.quiet,
            "extractor_args": {"youtube": {"player_client": [strategy.client.value]}},
        }

        if self._options.embed_thumbnail:
            opts["writethumbnail"] = True
            postprocessors.append({"key": "EmbedThumbnail"})

        opts["postprocessors"] = postprocessors

        if strategy.use_cookies:
            if self._options.cookies_from_browser:
                opts["cookiesfrombrowser"] = (self._options.cookies_from_browser,)
            if self._options.cookies_file:
                opts["cookiefile"] = str(self._options.cookies_file)

        return opts

    def extract(self, url: str) -> ExtractionResult:
        """Download and convert a single URL to audio. Blocking.

        Walks the fallback ladder built by `resilience.build_strategies`:
        each strategy is tried in order, retriable failures advance to the
        next one, and a fatal failure raises immediately.

        Raises:
            FfmpegNotFoundError: if `ffmpeg` is not found on PATH.
            VideoUnavailableError: if the video is fatally unavailable.
            BotProtectionError: if every fallback strategy is exhausted.
        """
        check_ffmpeg()
        strategies = build_strategies(self._options)
        last_exc: Exception | None = None

        for strategy in strategies:
            try:
                with YoutubeDL(self._build_ydl_opts(strategy)) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if info is None:
                        raise VideoUnavailableError(f"No extractable info returned for {url!r}")
                    base_filepath = Path(ydl.prepare_filename(info))
            except DownloadError as exc:
                error_cls = classify_error(exc)
                if error_cls is VideoUnavailableError:
                    raise VideoUnavailableError(str(exc)) from exc
                last_exc = exc
                continue

            filepath = base_filepath.with_suffix(f".{self._options.audio_format.value}")
            return ExtractionResult(
                url=url,
                filepath=filepath,
                title=str(info.get("title", "")),
                artist=info.get("artist") or info.get("uploader"),
                duration_s=info.get("duration"),
                format=self._options.audio_format,
                client_used=strategy.client,
            )

        raise BotProtectionError(
            f"All fallback strategies exhausted for {url!r} "
            f"(tried clients: {[s.client.value for s in strategies]}). "
            f"Last error: {last_exc}"
        ) from last_exc

    def extract_many(self, urls: Sequence[str]) -> list[ExtractionResult]:
        """Extract audio for each of `urls`, blocking.

        Convenience loop over `extract`; a per-URL `YtAudioError` is
        swallowed so one bad URL doesn't abort the rest of the batch.
        Failures are simply absent from the returned list.
        """
        results: list[ExtractionResult] = []
        for url in urls:
            try:
                results.append(self.extract(url))
            except YtAudioError:
                continue
        return results

    def probe(self, url: str) -> dict[str, Any]:
        """Fetch metadata for `url` without downloading."""
        strategy = build_strategies(self._options)[0]
        ydl_opts = self._build_ydl_opts(strategy)
        ydl_opts["quiet"] = True
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return dict(info) if info is not None else {}

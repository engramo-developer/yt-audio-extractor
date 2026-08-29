"""The `AudioExtractor` engine — the public façade around `yt-dlp`.

Tries each player client in `ExtractOptions.client_order` in turn: a retriable
failure (bot-wall, transient error) advances to the next client, while a fatal
failure (video unavailable) raises immediately. Cookies, when configured, are
applied on every attempt. By default `yt-dlp` runs silently — set
`ExtractOptions.verbose=True` to see its full logs.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from ytaudio.environment import check_ffmpeg
from ytaudio.exceptions import BotProtectionError, VideoUnavailableError, YtAudioError
from ytaudio.options import ExtractionResult, ExtractOptions, PlayerClient
from ytaudio.resilience import classify_error


class _QuietLogger:
    """A no-op logger so `yt-dlp` prints nothing unless `verbose` is set."""

    def debug(self, msg: str) -> None: ...
    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...


class AudioExtractor:
    """Smart, zero-config audio extractor around yt-dlp."""

    def __init__(self, options: ExtractOptions | None = None) -> None:
        self._options = options if options is not None else ExtractOptions()

    def _build_ydl_opts(self, client: PlayerClient) -> dict[str, Any]:
        """Build the `yt-dlp` options dict for a single player `client`."""
        outtmpl = str(Path(self._options.output_dir) / self._options.output_template)
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
            "extractor_args": {"youtube": {"player_client": [client.value]}},
        }

        if self._options.verbose:
            opts["verbose"] = True
        else:
            opts["quiet"] = True
            opts["no_warnings"] = True
            opts["noprogress"] = True
            opts["logger"] = _QuietLogger()

        if self._options.embed_thumbnail:
            opts["writethumbnail"] = True
            postprocessors.append({"key": "EmbedThumbnail"})

        opts["postprocessors"] = postprocessors

        if self._options.cookies_from_browser:
            opts["cookiesfrombrowser"] = (self._options.cookies_from_browser,)
        if self._options.cookies_file:
            opts["cookiefile"] = str(self._options.cookies_file)

        if self._options.progress_hook is not None:
            opts["progress_hooks"] = [self._options.progress_hook]

        return opts

    def extract(self, url: str) -> ExtractionResult:
        """Download and convert a single URL to audio. Blocking.

        Tries each client in `client_order`; a retriable failure advances to
        the next client, a fatal failure raises immediately.

        Raises:
            FfmpegNotFoundError: if `ffmpeg` is not found on PATH.
            VideoUnavailableError: if the video is fatally unavailable.
            BotProtectionError: if every player client is exhausted.
        """
        check_ffmpeg()
        last_exc: Exception | None = None

        for client in self._options.client_order:
            try:
                with YoutubeDL(self._build_ydl_opts(client)) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if info is None:
                        raise VideoUnavailableError(f"No extractable info returned for {url!r}")
                    base_filepath = Path(ydl.prepare_filename(info))
            except DownloadError as exc:
                if classify_error(exc) is VideoUnavailableError:
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
                client_used=client,
            )

        raise BotProtectionError(
            f"All player clients exhausted for {url!r} "
            f"(tried: {[c.value for c in self._options.client_order]}). "
            f"Last error: {last_exc}"
        ) from last_exc

    def extract_many(self, urls: Sequence[str]) -> list[ExtractionResult]:
        """Extract audio for each of `urls`, blocking.

        Convenience loop over `extract`; a per-URL `YtAudioError` is swallowed
        so one bad URL doesn't abort the rest of the batch. Failures are simply
        absent from the returned list.
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
        ydl_opts = self._build_ydl_opts(self._options.client_order[0])
        ydl_opts["quiet"] = True
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return dict(info) if info is not None else {}

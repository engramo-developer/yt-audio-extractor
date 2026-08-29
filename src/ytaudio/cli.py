"""`argparse`-based CLI entry point (`console_scripts`: `yt-audio-extractor`).

Designed to be friendly for non-technical users: `yt-dlp`'s technical logs are
hidden by default (use `--verbose` to see them), progress shows as a simple bar,
and failures are reported in plain language. Run with no URL to be prompted for
one.

Exit codes:
    0 — all URLs extracted successfully (or nothing to do).
    1 — at least one URL failed to extract.
    2 — `ffmpeg` is missing, or argument parsing failed (argparse default).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, TextIO

import ytaudio
from ytaudio.environment import check_ffmpeg
from ytaudio.exceptions import (
    BotProtectionError,
    FfmpegNotFoundError,
    UnsupportedURLError,
    VideoUnavailableError,
    YtAudioError,
)
from ytaudio.extractor import AudioExtractor
from ytaudio.options import AudioFormat, ExtractOptions

_BAR_WIDTH = 24


class _ProgressBar:
    """A simple in-place download progress bar driven by a yt-dlp progress hook."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream if stream is not None else sys.stdout
        self._active = False

    def __call__(self, status: dict[str, Any]) -> None:
        state = status.get("status")
        if state == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            if not total:
                return
            downloaded = status.get("downloaded_bytes", 0)
            frac = max(0.0, min(1.0, downloaded / total))
            filled = int(frac * _BAR_WIDTH)
            bar = "█" * filled + "░" * (_BAR_WIDTH - filled)
            self._stream.write(f"\r  [{bar}] {frac * 100:5.1f}%")
            self._stream.flush()
            self._active = True
        elif state == "finished":
            self.clear()

    def clear(self) -> None:
        """Erase the progress line, if one is currently shown."""
        if self._active:
            self._stream.write("\r" + " " * (_BAR_WIDTH + 12) + "\r")
            self._stream.flush()
            self._active = False


def _friendly_error(exc: YtAudioError) -> str:
    """Translate a library exception into a plain-language, actionable message."""
    if isinstance(exc, VideoUnavailableError):
        return (
            "Couldn't download this video — it may be private, deleted, "
            "age-restricted, or blocked in your region."
        )
    if isinstance(exc, BotProtectionError):
        return (
            "YouTube blocked this download. Try updating with "
            "'pip install -U yt-dlp', or sign in using "
            "'--cookies-from-browser chrome'."
        )
    if isinstance(exc, UnsupportedURLError):
        return "That doesn't look like a supported video link."
    return str(exc)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="yt-audio-extractor",
        description="Zero-config audio extraction from YouTube (and other yt-dlp-supported sites).",
    )
    parser.add_argument(
        "urls",
        nargs="*",
        help="One or more video URLs. If omitted, you'll be prompted to paste one.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory to save audio files to (default: current directory).",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=[fmt.value for fmt in AudioFormat],
        default=AudioFormat.MP3.value,
        help="Target audio format (default: mp3).",
    )
    parser.add_argument(
        "-q",
        "--quality",
        default="0",
        help="Audio quality (yt-dlp/ffmpeg VBR scale, 0 = best; default: 0).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print errors (no progress or success messages).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show yt-dlp's full technical output (for debugging).",
    )
    parser.add_argument(
        "--cookies-from-browser",
        default=None,
        help="Read cookies from a browser you're signed into (e.g. 'chrome', 'firefox').",
    )
    parser.add_argument(
        "--cookies-file",
        type=Path,
        default=None,
        help="Path to a Netscape-format cookies.txt file.",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Do not embed ID3/metadata tags in the output file.",
    )
    parser.add_argument(
        "--no-thumbnail",
        action="store_true",
        help="Do not embed a thumbnail/cover art in the output file.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {ytaudio.__version__}",
    )
    return parser


def _build_options(
    args: argparse.Namespace,
    progress: _ProgressBar | None,
) -> ExtractOptions:
    return ExtractOptions(
        output_dir=args.output_dir,
        audio_format=AudioFormat(args.format),
        audio_quality=args.quality,
        embed_metadata=not args.no_metadata,
        embed_thumbnail=not args.no_thumbnail,
        cookies_from_browser=args.cookies_from_browser,
        cookies_file=args.cookies_file,
        verbose=args.verbose,
        progress_hook=progress,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    urls: list[str] = list(args.urls)
    if not urls:
        if sys.stdin.isatty():
            try:
                entered = input("Paste a YouTube link (or press Enter to quit): ").strip()
            except EOFError:
                entered = ""
            if not entered:
                print("Nothing to do — bye!")
                return 0
            urls = [entered]
        else:
            parser.error("at least one URL is required")

    try:
        check_ffmpeg()
    except FfmpegNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    show_progress = not args.verbose and not args.quiet and sys.stdout.isatty()
    progress = _ProgressBar() if show_progress else None
    extractor = AudioExtractor(_build_options(args, progress))

    had_failure = False
    total = len(urls)
    for index, url in enumerate(urls, start=1):
        if not args.quiet:
            counter = f" ({index}/{total})" if total > 1 else ""
            print(f"⏳ Downloading{counter}: {url}", flush=True)

        try:
            result = extractor.extract(url)
        except YtAudioError as exc:
            if progress is not None:
                progress.clear()
            print(f"✗ {_friendly_error(exc)}", file=sys.stderr)
            had_failure = True
            continue

        if progress is not None:
            progress.clear()
        if not args.quiet:
            print(f"✓ {result.title}  →  {result.filepath}")

    return 1 if had_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())

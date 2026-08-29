"""`argparse`-based CLI entry point (`console_scripts`: `yt-audio-extractor`).

Parses args into an `ExtractOptions`, drives a single `AudioExtractor` across
all given URLs, and renders minimal, dependency-free progress/errors.

Exit codes:
    0 — all URLs extracted successfully.
    1 — at least one URL failed to extract.
    2 — `ffmpeg` is missing, or argument parsing failed (argparse default).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import ytaudio
from ytaudio.environment import check_ffmpeg
from ytaudio.exceptions import FfmpegNotFoundError, YtAudioError
from ytaudio.extractor import AudioExtractor
from ytaudio.options import AudioFormat, ExtractOptions


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="yt-audio-extractor",
        description="Zero-config audio extraction from YouTube (and other yt-dlp-supported sites).",
    )
    parser.add_argument("urls", nargs="+", help="One or more video URLs to extract audio from.")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory to write extracted audio files to (default: current directory).",
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
        help="Suppress per-URL success output (errors are still printed).",
    )
    parser.add_argument(
        "--cookies-from-browser",
        default=None,
        help="Read cookies from an installed browser (e.g. 'chrome', 'firefox').",
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


def _build_options(args: argparse.Namespace) -> ExtractOptions:
    return ExtractOptions(
        output_dir=args.output_dir,
        audio_format=AudioFormat(args.format),
        audio_quality=args.quality,
        embed_metadata=not args.no_metadata,
        embed_thumbnail=not args.no_thumbnail,
        cookies_from_browser=args.cookies_from_browser,
        cookies_file=args.cookies_file,
        quiet=args.quiet,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        check_ffmpeg()
    except FfmpegNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    options = _build_options(args)
    extractor = AudioExtractor(options)

    had_failure = False
    for url in args.urls:
        try:
            result = extractor.extract(url)
        except YtAudioError as exc:
            print(f"✗ {url}: {exc}", file=sys.stderr)
            had_failure = True
            continue

        if not args.quiet:
            print(f"✓ {result.title} → {result.filepath}")

    return 1 if had_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())

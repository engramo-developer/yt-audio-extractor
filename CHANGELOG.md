# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-29

### Added
- `AudioExtractor` engine with `extract()`, `extract_many()`, and `probe()` — a zero-config
  façade over the `yt-dlp` Python API.
- `ExtractOptions` / `ExtractionResult` frozen dataclasses and `AudioFormat` / `PlayerClient`
  enums as the single source of truth for configuration and results.
- Audio extraction to MP3 (default) with ID3 metadata and embedded thumbnail via the
  `FFmpegExtractAudio`, `FFmpegMetadata`, and `EmbedThumbnail` post-processors.
- Anti-bot **fallback ladder**: automatic player-client rotation (`android → tv → web`) with
  fail-fast on fatal errors and opt-in cookies (`cookies_from_browser` / `cookies_file`, applied
  on every attempt).
- Typed exception hierarchy rooted at `YtAudioError`
  (`FfmpegNotFoundError`, `VideoUnavailableError`, `BotProtectionError`, `UnsupportedURLError`).
- `ffmpeg`/`ffprobe` detection with OS-specific install hints.
- `argparse` CLI (`yt-audio-extractor` / `python -m ytaudio`) designed for non-technical users:
  `yt-dlp`'s technical logs are hidden by default (a simple progress bar and plain-language
  success/error messages instead, with `--verbose` to restore the full logs), prompts for a URL
  when none is given on an interactive terminal, and returns meaningful exit codes.
- PEP 561 `py.typed` marker so consumers get full type inference.
- GitHub Actions CI (Python 3.10–3.13, plus a weekly run against the latest `yt-dlp`) and a
  tag-triggered PyPI release workflow using Trusted Publishing.

[Unreleased]: https://github.com/engramo-developer/yt-audio-extractor/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/engramo-developer/yt-audio-extractor/releases/tag/v0.1.0

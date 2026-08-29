# yt-audio-extractor — Claude Code Guide

## Project Overview

A zero-config Python library **and** CLI that wraps [`yt-dlp`](https://github.com/yt-dlp/yt-dlp)
to reliably extract audio from YouTube (and other supported sites). It abstracts away format
selection, `ffmpeg` post-processing, ID3/thumbnail embedding, and YouTube's anti-bot mitigations
(player-client fallback, opt-in cookies).

**Distribution name:** `yt-audio-extractor` · **Import package:** `ytaudio` · **Python:** 3.9+

**Stack:** yt-dlp (Python API, in-process) · ffmpeg (host binary) · argparse (CLI) ·
pytest + mypy (strict) + ruff · GitHub Actions · Hatchling build backend.

## Repository Layout (src layout)

| Path | Purpose |
|---|---|
| `src/ytaudio/extractor.py` | `AudioExtractor` engine — the public façade |
| `src/ytaudio/options.py` | `ExtractOptions`, `ExtractionResult`, `AudioFormat`, `PlayerClient` (frozen dataclasses / enums) |
| `src/ytaudio/resilience.py` | Fallback strategy ladder + `yt-dlp` error classification |
| `src/ytaudio/environment.py` | `ffmpeg`/`ffprobe` detection + OS-specific install hints |
| `src/ytaudio/exceptions.py` | Typed exception hierarchy (`YtAudioError` base) |
| `src/ytaudio/cli.py` | argparse CLI; `console_scripts` entry point |
| `src/ytaudio/__init__.py` | Public re-exports; `__version__` |
| `src/ytaudio/py.typed` | PEP 561 marker (ships type info to consumers) |
| `tests/` | pytest suite — `YoutubeDL` and PATH always mocked; **no network** |

`src/` layout is deliberate: tests run against the *installed* package, so imports can't
accidentally resolve to the working tree.

## Code Conventions

### Typing
- `from __future__ import annotations` at the top of every module.
- **Full annotations on every public function, method, and dataclass field.** `mypy` runs in
  strict mode over `src/` — no `Any` leaks across public boundaries, no untyped defs.
- Prefer `X | None` (PEP 604 via the future import) over `Optional[X]`.
- The package ships `py.typed`; keep the public API fully typed so consumers get inference.

### Errors
- Every raised error derives from `YtAudioError` (in `exceptions.py`) so library consumers can
  `except YtAudioError`. Map failure modes to specific subclasses
  (`FfmpegNotFoundError`, `VideoUnavailableError`, `BotProtectionError`, `UnsupportedURLError`).
- **Never** catch bare `Exception` to swallow it. Catch the narrowest type; re-raise as a
  `YtAudioError` subclass with context. `yt-dlp` raises `yt_dlp.utils.DownloadError` — classify it
  in `resilience.py`, don't leak it to callers.
- No `assert` for runtime validation (stripped under `-O`); raise instead.

### Data model
- Config and results are **frozen dataclasses** with `slots=True` (`ExtractOptions`,
  `ExtractionResult`). Defaults live in `ExtractOptions` — it is the single source of truth.
- Enums (`AudioFormat`, `PlayerClient`) subclass `str, Enum` so their `.value` is the exact token
  `yt-dlp` expects.

### Style
- `ruff` owns both linting and formatting — do not hand-format or add a separate formatter.
- Comments sparingly, only for non-obvious logic; self-documenting names preferred.
- Public classes/functions get concise docstrings (what + args + raises). Private helpers
  (`_build_ydl_opts`) need a docstring only when non-obvious.
- Keep the yt-dlp coupling behind `extractor.py` / `resilience.py`. `cli.py` and consumers touch
  only `AudioExtractor` + `ExtractOptions` + the exception types.

### yt-dlp integration
- Drive yt-dlp via its **Python API** (`from yt_dlp import YoutubeDL`), never by shelling out to
  the binary. Build the opts dict in `_build_ydl_opts`; register post-processors
  (`FFmpegExtractAudio`, `FFmpegMetadata`, `EmbedThumbnail`) there.
- Depend on `yt-dlp` with a **floor, no ceiling** (`yt-dlp>=<recent>`), so users get YouTube fixes
  via `pip install -U yt-dlp` without waiting on our release.

### Testing
- `pytest`. Unit tests **mock `YoutubeDL`** (patch `ytaudio.extractor.YoutubeDL`) and mock PATH /
  `shutil.which` — **no network, no real downloads, no ffmpeg required** in CI.
- Test the happy path **and** every error branch (ffmpeg missing, bot-wall exhausted, video
  unavailable, bad URL).
- Assert on *behavior we own*: the opts dict `_build_ydl_opts` produces, the strategy ordering,
  error classification, CLI arg parsing + exit codes. Do not assert yt-dlp internals.
- Test names: `test_<unit>_<scenario>` (e.g. `test_extract_falls_back_to_tv_on_bot_wall`).
- Real end-to-end network smoke tests are **manual only** (see the plan's Verification section);
  never in the default `pytest` run.

## Mandatory After Every Code Change

Run this chain after **every** edit; fix all issues before moving on:

```bash
ruff format . \
  && ruff check --fix . \
  && mypy src/ \
  && pytest -q
```

- `ruff format .` applies formatting; `ruff check --fix .` lints + auto-fixes safe issues.
- `mypy src/` must be clean (strict). `pytest -q` must be green.
- CI runs the check-only variant (`ruff format --check .`, `ruff check .`) — so format locally
  first or CI will fail.

> Python here has **no slow compile step and no container-per-test** cost (unlike the Rust repo
> this tooling was adapted from). The full chain runs in seconds. There is **no** need for
> `caffeinate`, `--offline`, testcontainers cleanup, or scoped-vs-full-workspace juggling — always
> run the whole chain.

## Commands

```bash
# Editable install with dev extras (first-time setup)
pip install -e '.[dev]'

# Format · lint · type-check · test (the mandatory chain)
ruff format . && ruff check --fix . && mypy src/ && pytest -q

# Tests with coverage
pytest --cov=ytaudio --cov-report=term-missing

# Run the CLI locally
yt-audio-extractor "https://www.youtube.com/watch?v=<id>"
python -m ytaudio "https://www.youtube.com/watch?v=<id>"   # module form

# Build a distribution
python -m build
```

## Skills & Commands

| Command | Purpose |
|---|---|
| `/review` | Review→fix loop: Python idioms, correctness, security, coverage. Spawns domain reviewers in parallel, synthesizes, applies fixes, re-verifies. |

Supporting skills (`.claude/skills/`): `code-review`, `coverage-analysis`, `orchestration`.
Agents (`.claude/agents/`): `review-python`, `review-security`, `review-coverage`,
`synthesis-reviewer`, `code-implementator`.

### Orchestrator role

When the user explicitly puts the main session in an **orchestrator/coordinator** role — "you are
the orchestrator", "spawn one subagent per phase", or "keep main-session tokens minimal while
delegating" — **load and apply the `orchestration` skill**
(`.claude/skills/orchestration/SKILL.md`) before dispatching work. It encodes how to divide labor
between orchestrator and subagents, size tasks to the cache window, and keep the
verification/diff-review loop lean.

---
name: code-review
description: Comprehensive Python code review for the yt-audio-extractor library + CLI (yt-dlp wrapper). Checks idioms, typing, error handling, API design, security of subprocess/cookie/path handling, performance, and testing. Use when reviewing a file, module, or diff for quality, correctness, and production-readiness.
---

# Code Review Skill — yt-audio-extractor

Apply this checklist to the target code (file, module, package, or diff). Be exhaustive but
precise — surface real issues, not stylistic noise `ruff` already handles.

## Checklist

### Typing & API design
- [ ] `from __future__ import annotations` present; public functions/methods/dataclass fields fully annotated
- [ ] `X | None` used over `Optional[X]`; no bare `Any` crossing a public boundary
- [ ] Config/results are frozen dataclasses (`frozen=True, slots=True`); no mutable default args
- [ ] Enums subclass `str, Enum` and carry the exact token `yt-dlp` expects
- [ ] Public surface stays minimal — yt-dlp coupling stays behind `extractor.py`/`resilience.py`
- [ ] `__init__.py` re-exports match the documented public API; `__all__` accurate

### Python idioms
- [ ] `pathlib.Path` over `os.path` string munging; no manual string path joins
- [ ] Context managers (`with YoutubeDL(...) as ydl:`) rather than manual open/close
- [ ] Comprehensions / generators over manual accumulate-in-loop where it reads cleaner
- [ ] f-strings over `%`/`.format`; no f-string without a placeholder
- [ ] `enumerate`/`zip`/`dict.get` used where they simplify
- [ ] No mutable module-level globals; constants are UPPER_SNAKE and truly constant

### Error handling
- [ ] No bare `except:` / `except Exception:` that swallows; catch the narrowest type
- [ ] All raised errors derive from `YtAudioError`; `yt_dlp.utils.DownloadError` classified in `resilience.py`, never leaked
- [ ] Exceptions carry actionable context (URL, tried clients, install hint) — not just a bare message
- [ ] No `assert` used for runtime validation (stripped under `-O`)
- [ ] Cleanup (temp files, partial downloads) happens on the error path too

### Security (subprocess / cookies / paths / untrusted metadata)
- [ ] `subprocess` (if any) never uses `shell=True` with interpolated input; args passed as a list
- [ ] ffmpeg/ffprobe resolved via `shutil.which`, not an attacker-influenced PATH string
- [ ] Output paths derived from video titles are constrained to `output_dir` (no `../` traversal); rely on yt-dlp `outtmpl` sanitization, don't hand-roll
- [ ] Cookie handling is opt-in; cookie file contents / browser names never logged
- [ ] No secrets, cookie values, or full auth headers in logs or error messages
- [ ] URL input validated before use; unsupported/malformed URLs raise `UnsupportedURLError`

### Resilience (the core value prop)
- [ ] Fallback strategy order is data-driven (from `ExtractOptions.client_order`), not hardcoded `if/elif`
- [ ] `classify_error` centralizes retriable (bot-wall) vs fatal (unavailable/private) mapping in one place
- [ ] Fatal errors fail fast — no wasted retries across the whole client ladder
- [ ] Cookie retries only attempted when the user actually supplied cookies
- [ ] Exhausting all strategies raises `BotProtectionError` with the list of attempts tried

### Performance
- [ ] `probe()` uses `extract_info(download=False)` — no wasted download for metadata-only
- [ ] No redundant repeated `extract_info` calls for the same URL within one operation
- [ ] Large loops (`extract_many`) don't hold everything in memory unnecessarily; failures collected without aborting the batch

### Testing
- [ ] Every public function/method has at least one test
- [ ] Error branches covered: ffmpeg-missing, bot-wall-exhausted, video-unavailable, bad-URL
- [ ] `YoutubeDL` and `shutil.which`/PATH are mocked — no network, no ffmpeg dependency in the test
- [ ] Tests assert on *our* behavior (opts dict, strategy order, exit codes), not yt-dlp internals
- [ ] Test names follow `test_<unit>_<scenario>`

## Output Contract

When invoked by an agent that supplies a `feedback_path`, write findings to that file using
**exactly** the format below. The first line of every finding **must** be
`### [ ] F<N> · <Severity> · <Category>` — the `[ ]` checkbox is parsed downstream.

```markdown
# Code Review — Iteration <N>

**Target:** <path or scope>
**Date:** <YYYY-MM-DD>

## Summary

- Total findings: <N>
- Critical: <X> | High: <Y> | Medium: <Z> | Low: <W>

## Findings

### [ ] F1 · High · Error-handling
**Location:** `src/ytaudio/extractor.py:88`
**Issue:** Bare `except Exception` swallows every yt-dlp failure, so a fatal
`VideoUnavailable` is retried across the whole client ladder before failing.
**Fix:**
```python
except DownloadError as exc:
    error_cls = classify_error(exc)
    if error_cls is not BotProtectionError:
        raise error_cls(str(exc)) from exc
    # else: fall through to next strategy
```

### [ ] F2 · Medium · Idiom
**Location:** `src/ytaudio/environment.py:24`
**Issue:** Manual `os.path.join` + string PATH split to find ffmpeg.
**Fix:** Use `shutil.which("ffmpeg")` and return a `pathlib.Path`.
```

Severity scale: `Critical` (security / data loss / broken core resilience) · `High`
(correctness bug) · `Medium` (idiom / maintainability / typing gap) · `Low` (style / polish).

When invoked **without** a `feedback_path` (interactive single-shot), produce the same content as
plain output and end with a summary table by severity.

## Scope Discipline

- Read the target file(s) fully before flagging — partial reads produce false positives.
- Do not flag style `ruff`/`ruff format` already enforce (line length, quotes, import order).
- Do not flag conventions that disagree with this repo's `CLAUDE.md` — it wins.
- Do not propose refactors beyond what each finding requires.

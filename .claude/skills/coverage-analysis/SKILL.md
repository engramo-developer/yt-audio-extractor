---
name: coverage-analysis
description: Test-coverage gap analysis for yt-audio-extractor Python source. Identifies uncovered functions, branches, and error paths and proposes concrete pytest scaffolds. Use when auditing whether a module's behavior — especially its error branches and fallback ladder — is exercised by the test suite.
---

# Coverage Analysis Skill — yt-audio-extractor

Identify **untested behavior** in the target and propose concrete pytest scaffolds. Focus on
branches that matter for a resilience-focused wrapper: error paths and the fallback ladder.

## Procedure

1. Read the target module fully. Enumerate its public functions/methods and every distinct
   branch (each `except`, each `if/elif`, each strategy in a loop, each early `return`/`raise`).
2. Locate existing tests that exercise the target (grep `tests/` for the symbol names).
3. For each **uncovered** function or branch, emit a finding with a runnable test scaffold.
4. Prioritize by risk: an untested **error branch or fallback step** is higher severity than an
   untested trivial getter.

## What to prioritize (this codebase)

- [ ] Every `except`/error branch: ffmpeg-missing, bot-wall-exhausted, video-unavailable, bad-URL
- [ ] Each step of the client fallback ladder (android→tv→web) and the cookie-retry path
- [ ] `classify_error` mapping for each representative yt-dlp error string
- [ ] `_build_ydl_opts` output for each `AudioFormat` and each flag combination (metadata/thumbnail on/off, cookies set/unset)
- [ ] CLI arg parsing + exit codes for success, ffmpeg-missing, and extraction failure
- [ ] `extract_many` partial-failure collection (some URLs fail, batch continues)

## Rules

- Mocks only — every scaffold must mock `YoutubeDL` and `shutil.which`/PATH. No network, no real
  ffmpeg, no real download.
- Propose the **minimal** test that pins the behavior; don't over-parametrize.
- Do not flag quality issues in existing tests — only *missing* coverage.
- Every finding cites a function/branch **defined inside the target** and includes a scaffold.

## Output Contract

Write findings to `feedback_path` using the same format as the `code-review` skill — first line of
each finding is `### [ ] F<N> · <Severity> · <Category>` with `<Category>` = `Coverage`. Example:

```markdown
### [ ] F1 · High · Coverage
**Location:** `src/ytaudio/resilience.py:41` — `classify_error`, DownloadError → fatal branch
**Issue:** The "Video unavailable" → `VideoUnavailableError` mapping is never exercised, so a
regression that retries fatal errors across the whole ladder would pass CI.
**Fix:** Add:
```python
def test_classify_error_video_unavailable_is_fatal():
    exc = DownloadError("ERROR: Video unavailable")
    assert classify_error(exc) is VideoUnavailableError
```
```

Severity: `High` (untested error/fallback branch) · `Medium` (untested public function) ·
`Low` (untested trivial accessor / edge polish).

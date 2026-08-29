Run a review→fix loop on $ARGUMENTS (or the most recently edited Python file if no arguments).
If `--plan <path>` is present, run the **plan-alignment flow** instead — review-only, no fixing,
branch-vs-base scope, mapping the plan's phases/deliverables to their implementation status. See
`## Plan-alignment flow` below.

You are the orchestrator running in the main conversation. You are the **only** place that can spawn
subagents in parallel — domain reviewers cannot spawn each other. Follow this loop exactly.

## Argument parsing

Parse `$ARGUMENTS` before doing anything else:

- If `--plan <path>` is present, set `PLAN_MODE = true` and extract `<path>` as `PLAN_SPEC`. Remove
  `--plan <path>` from the string. Otherwise `PLAN_MODE = false`.
- If `--branch <ref>` is present, extract `<ref>` as `BRANCH_REF`. Remove it. Otherwise `BRANCH_REF = HEAD`.
- If `--base <ref>` is present, extract `<ref>` as `BASE_REF`. Remove it. Otherwise `BASE_REF = main`.
- If `--iterations N` is present:
  - If `PLAN_MODE = true` → abort with: `error: --iterations is incompatible with --plan (plan mode is review-only)`.
  - Otherwise extract `N` as `MAX_ITERATIONS`. Remove it.
- Otherwise `MAX_ITERATIONS = 1`.
- If `--continue` is present, set `CONTINUE_MODE = true`. Remove it. Otherwise `CONTINUE_MODE = false`.
- The remaining string after removing all flags is the target. In `PLAN_MODE` the target is ignored
  (file list comes from the branch diff). Otherwise: if empty, default to "the most recently edited
  Python file in the working tree".

`MAX_ITERATIONS` controls how many times @code-implementator may run. A reviewer pass always runs at
least once (at the start) and once more at the end (regression check); it does not count toward
`MAX_ITERATIONS`.

**If `PLAN_MODE = true`, skip the rest of this section and jump to `## Plan-alignment flow`.**
Otherwise continue below.

## Hang safety (background agent watchdog)

Every Agent invocation in this command runs in the background. Immediately after spawning one — or a
parallel batch — call `ScheduleWakeup` with `delaySeconds≈270` (just under the prompt-cache TTL) and
a reason naming what's being watched, instead of relying only on the automatic completion
notification. This bounds how long a stuck agent can go unnoticed.

When the wakeup fires:
- If a completion notification already arrived, proceed normally.
- If agents are still running with visible progress, reschedule another ~270s wakeup and keep waiting.
- If an agent shows no progress across 2+ consecutive checks (same state, no new output), treat it
  as hung: say so, and re-invoke that single agent once as a fallback before giving up on it.

> Unlike the Rust repo this tooling came from, the **verify chain here is fast** (`ruff && mypy &&
> pytest`, seconds). There are no long `cargo` builds, no `caffeinate`, no `--offline`, and no
> testcontainers to reap. The watchdog above is only for a genuinely stuck *agent*, not a slow build.

Examples:
- `/review src/ytaudio/extractor.py` → 1 reviewer pass, up to 2 implementator passes, 1 final reviewer pass
- `/review src/ytaudio/extractor.py --iterations 1` → 1 reviewer, up to 1 implementator, 1 final reviewer
- `/review src/ytaudio/cli.py --continue` → resume from last cache, same counting rules
- `/review --plan /Users/vova/.claude/plans/role-you-are-a-transient-hennessy.md` → plan-alignment, current branch vs `main`, no fixing

## Setup

**If `CONTINUE_MODE = false`**, run:
```bash
rm -rf .claude/.review-cache && mkdir -p .claude/.review-cache
```
Then set `IMPL_ITER = 0`.

**If `CONTINUE_MODE = true`**, run:
```bash
mkdir -p .claude/.review-cache
ls .claude/.review-cache/iter-*.md 2>/dev/null | sort | tail -1
```
Determine `IMPL_ITER` (implementator passes already completed) from the output:
- No files: warn ("no previous cache found, starting fresh"), set `IMPL_ITER = 0`.
- Last file is `iter-N.md`: count unchecked findings with
  `grep -c '^### \[ \]' .claude/.review-cache/iter-N.md || echo 0`.
  - count > 0: implementator did not finish — resume it first (Step 2a), then set `IMPL_ITER = N`.
  - count == 0: implementator finished — set `IMPL_ITER = N`.
- If `IMPL_ITER >= MAX_ITERATIONS`: report "nothing left to do" and emit the Final Report from files.

Compute the absolute path to `.claude/.review-cache` (call it `<CACHE_DIR>`) and use it below.

## Reviewer pass sub-procedure

Whenever the loop says **"run a reviewer pass"** with `feedback_path=<CACHE_DIR>/<basename>.md` and a
given `iteration`, execute this exactly:

**RP-1.** Derive three temp paths in `<CACHE_DIR>`:
- `python_path = <CACHE_DIR>/python-<basename>.md`
- `security_path = <CACHE_DIR>/security-<basename>.md`
- `coverage_path = <CACHE_DIR>/coverage-<basename>.md` *(only if `iteration != final`)*

**RP-2.** Spawn the domain reviewers **in parallel** — emit **a single assistant message containing
all the Agent tool calls below as separate tool-use blocks**. Sequential calls defeat the design.
- @review-python with `target=<target>`, `output_path=<python_path>`, `iteration=<iteration>`
- @review-security with `target=<target>`, `output_path=<security_path>`, `iteration=<iteration>`
- @review-coverage with `target=<target>`, `output_path=<coverage_path>` *(skip on `iteration=final`)*

All run as `model: sonnet`. The bulk file reading / grepping stays inside Sonnet contexts. Each
returns `DOMAIN=<d> FILE=<path> COUNT=<N>`. Read those. (Apply the watchdog while they run.)

**RP-3.** If any domain agent failed to return a parseable line, re-invoke that single agent once as
a fallback. If it still fails, set its COUNT=0 and proceed — synthesis treats the temp file as empty.

**RP-4.** Invoke @synthesis-reviewer (model: opus) with:
```
target=<target>
feedback_path=<CACHE_DIR>/<basename>.md
iteration=<iteration>
python_path=<python_path>
security_path=<security_path>
coverage_path=<coverage_path>     # omit on iteration=final
```
It reads only the three (or two) temp files — not source — dedupes, prioritizes, renumbers, writes
the merged file, cleans up temps, and returns:
```
FEEDBACK_FILE=<feedback_path> TOTAL=<N> CRITICAL=<X> HIGH=<Y> MEDIUM=<Z> LOW=<W>
```
Parse that line. This is the result of the reviewer pass.

## Loop

### Step 1 — Initial review (always runs, unless continuing with unfinished implementator work)
> Skip only if `CONTINUE_MODE = true` AND the last cache file had unchecked findings (resume
> implementator instead — see Setup).

Run a reviewer pass with `feedback_path=<CACHE_DIR>/iter-0.md` and `iteration=1`.
- If TOTAL == 0 → skip to Final Report, outcome = `clean`.

### Step 2 — Fix loop (up to MAX_ITERATIONS times)
Repeat, incrementing `IMPL_ITER` each time, while `IMPL_ITER < MAX_ITERATIONS`:

**2a.** Invoke @code-implementator with `feedback_path=<CACHE_DIR>/iter-<IMPL_ITER>.md`. (First pass
uses `iter-0.md`; later passes use the previous reviewer pass's file from 2b.) Parse the returned
line `FIXED=N BLOCKED=M REMAINING=K`. (Apply the watchdog — this is usually the longest step.)
- If REMAINING > 0 and FIXED == 0 → stop loop, outcome = `stuck`.
- If REMAINING == 0 → proceed to Final Review (Step 3).

Increment `IMPL_ITER`.

**2b.** If `IMPL_ITER < MAX_ITERATIONS` and REMAINING > 0, run a reviewer pass with
`feedback_path=<CACHE_DIR>/iter-<IMPL_ITER>.md` and `iteration=<IMPL_ITER + 1>`.
- If TOTAL == 0 → stop loop, outcome = `clean`.

If `IMPL_ITER == MAX_ITERATIONS` → stop loop, outcome = `residual-blocked`.

### Step 3 — Final regression review (always runs if loop completed without `stuck`)
Run a reviewer pass with `feedback_path=<CACHE_DIR>/final.md` and `iteration=final`.
*(review-coverage is skipped on this pass — final only checks for regressions across python/security.)*
- If TOTAL == 0 → outcome = `clean`.
- Else → outcome = `residual-blocked`.

## Fallback parsing
If synthesis-reviewer does not return the expected line, count directly from the merged file:
- TOTAL / REMAINING: `grep -c '^### \[ \]' <feedback_path>` (or 0 if missing).
- FIXED: previous TOTAL minus current REMAINING.

## Final Report

```markdown
# Review Loop Result

**Target:** <target>
**Implementator passes:** <IMPL_ITER> / MAX_ITERATIONS
**Mode:** <fresh | continued from iter-N>
**Outcome:** <clean | residual-blocked | stuck>

| Pass    | Role          | Total | Critical | High | Medium | Low | Fixed | Blocked |
|:--------|:--------------|------:|---------:|-----:|-------:|----:|------:|--------:|
| Initial | reviewer      | ...   |          |      |        |     | —     | —       |
| 1       | implementator | —     | —        | —    | —      | —   | ...   | ...     |
| Final   | reviewer      | ...   |          |      |        |     | —     | —       |

**Feedback files:** list the `.claude/.review-cache/*.md` files that were written.
```

---

## Plan-alignment flow

Reached **only** when `--plan` is set. **Review-only**: no code-implementator, no fix loop, no
iterations. Output is a Plan Alignment Report — a developer-facing diagnostic mapping every plan
phase/deliverable to its implementation status (Implemented / Partial / Missing / Deviated / Extra).

### Setup (plan mode)
Compute `<CACHE_DIR>` = absolute path to `.claude/.review-cache`.
- `CONTINUE_MODE = false` → `rm -rf .claude/.review-cache && mkdir -p .claude/.review-cache`.
- `CONTINUE_MODE = true` → `mkdir -p .claude/.review-cache`.

### Phase 0 — Resolve file list
1. Verify both refs exist (abort on failure):
   ```bash
   git rev-parse --verify "${BRANCH_REF}^{commit}"
   git rev-parse --verify "${BASE_REF}^{commit}"
   ```
2. Compute the file list (Python source + packaging + workflows):
   ```bash
   git diff --name-only "${BASE_REF}...${BRANCH_REF}" -- '*.py' '*.toml' '*.cfg' '.github/**' \
     | grep -Ev '^(\.venv/|build/|dist/|.*\.egg-info/)'
   ```
   If the branch is not yet committed, fall back to the working tree:
   `git status --short -- '*.py' '*.toml' '.github/**'`.
3. Empty list → abort: `error: no source changes between ${BRANCH_REF} and ${BASE_REF}`.
4. List size > 80 → print it, then abort: `error: scope too large (N > 80) — narrow with --base`.
5. Persist to `<CACHE_DIR>/files.txt` (one path per line). `--continue` reads this.

### Phase A — Per-file LOCAL passes
For each `<file>` in `<CACHE_DIR>/files.txt` (process **sequentially**):
1. `basename = $(basename "<file>" | sed 's/\..*//')`. Disambiguate collisions by prepending the
   parent dir (e.g. `ytaudio-extractor`).
2. If `CONTINUE_MODE = true` and `<CACHE_DIR>/local-<basename>-plan.md` exists, **skip** (done).
3. Invoke @review-python (single agent, foreground) with a **plan-alignment directive** instead of
   the normal review:
   ```
   target=<file>
   output_path=<CACHE_DIR>/local-<basename>-plan.md
   iteration=1
   directive: PLAN-ALIGNMENT mode. Read the plan at <PLAN_SPEC>. For every plan item whose
              implementation should live in <file>, report its status as one of
              Implemented / Partial / Missing / Deviated, citing file:line, plus any Extra code
              not called for by the plan. Do NOT propose refactors; this is a status map.
   ```
4. Parse `DOMAIN=python FILE=<path> COUNT=<N>`. If unparseable, re-invoke once, else COUNT=0.

### Phase B — Synthesis
Invoke @synthesis-reviewer (opus) with the per-file `local-*-plan.md` files as `python_path`
(comma-joined is fine; it reads all provided temp files), `feedback_path=<CACHE_DIR>/plan-alignment.md`,
`iteration=final`, and this directive: "Merge the per-file plan-alignment reports into one Plan
Alignment Report grouped by plan phase; add a coverage summary line
`IMPLEMENTED=<a> PARTIAL=<b> MISSING=<c> DEVIATED=<d> EXTRA=<e>`. Do not invent findings."

### Phase C — Emit report
Read `<CACHE_DIR>/plan-alignment.md` and emit it inline as the assistant message. Append:
```
Cached at: .claude/.review-cache/plan-alignment.md · Re-run with --continue to refresh after changes.
```
No fix loop. Exit.

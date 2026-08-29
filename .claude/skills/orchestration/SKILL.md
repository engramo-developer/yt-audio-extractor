---
name: orchestration
description: Playbook for running the main session as an ORCHESTRATOR that drives a multi-phase implementation by spawning one fresh subagent per phase. Load this when the user explicitly puts the main session in an orchestrator/coordinator role, asks you to spawn a subagent per task/phase, or says to keep main-session token usage minimal while delegating work. Encodes how to divide labor, size tasks to the cache window, keep verification honest, and review subagent output without bloating context.
---

# Orchestration Skill — yt-audio-extractor

You are the **orchestrator**: a thin coordinator. The expensive work (reading files, writing code,
running the verify chain) happens in subagents; your job is to plan, dispatch, review outcomes, and
keep your own context lean. Optimise for **trustworthy progress per cache window**, not for doing
the work yourself.

## Division of labor (default)

- **Subagent** implements one phase and self-verifies with the full mandatory chain (it is fast in
  this repo — see below), then hands back a **tight report**: files changed, chain result
  (pass/fail + counts), and any deviations from the plan. No code dumps, no transcript.
- **Orchestrator (you)** picks the phase from the plan, writes a **self-contained** prompt, reviews
  the returned **diff** (not the transcript), and does a final full-chain verify yourself before
  marking the phase done and dispatching the next.

## Verification is cheap here — no Rust-style hang machinery

This tooling was adapted from a Rust repo where verification was a ~20-minute containerized build
that subagents routinely stalled on. **None of that applies to this Python repo.** The full chain:

```bash
ruff format . && ruff check --fix . && mypy src/ && pytest -q
```

runs in **seconds**. So:

- Run the chain **foreground** (`run_in_background=false`). Do **not** background it, poll it, wrap
  it in `caffeinate`, pass `--offline`, or reap `cargo`/testcontainers processes — there is nothing
  slow or leaky to manage.
- A subagent can safely self-verify by blocking on the chain. Still, **you re-run it once** after
  reviewing the diff — you get reliable completion, and it's cheap.
- The one carry-over lesson that still holds: **never let a subagent fire-and-forget a command and
  then end its turn.** Every command it runs must be foreground and its result reported inline.

## Spawning subagents

- **One fresh subagent per phase** (`subagent_type: general-purpose`, `model: sonnet` unless the
  user says otherwise). A fresh agent starts cold, so the prompt must be **self-contained**: point
  it at the plan file (`/Users/vova/.claude/plans/role-you-are-a-transient-hennessy.md`) and
  `CLAUDE.md`, state the exact files in scope, the deliverable + acceptance criteria for that phase,
  and the required report format. Do not assume it shares your context.
- **Do NOT use `fork`** for phase work — a fork inherits your full context (defeats the token goal).
- **Size each task to finish inside one cache window.** These phases are small; one phase per
  subagent is right. Don't bundle all five into one agent.
- Run phases **sequentially** — later phases import symbols earlier ones define. Dispatch → review
  diff → verify → update the plan/task progress → dispatch the next.

## Reviewing a subagent's work without bloating context

- Review the **diff**, not the transcript: `git status --short`, `git --no-pager diff --stat`,
  `git --no-pager diff <scope files>`. **Never** `Read`/`tail` a subagent's raw JSONL output.
- Sanity-check the implementation against the plan's acceptance criteria for that phase **before**
  you run the verify chain — a quick diff read catches wrong-shape work early.
- After a phase is green, update the task list (mark the phase task completed) so the rollout is
  resumable. Do **not** commit unless the user asks.

## Token discipline (orchestrator)

- Don't re-read a file you just wrote — Write/Edit already confirmed it.
- Pipe verification output through `tail`/`grep`; never let a full `pytest -v` log land in context.
  Prefer `pytest -q` and read only the summary line.
- Relay only what matters from a subagent's result; don't quote its report verbatim.
- Keep your own tool calls few and batched.

## Repo-specific guardrails (from CLAUDE.md — enforce in every phase)

- yt-dlp is driven via its **Python API** (`from yt_dlp import YoutubeDL`), never a subprocess.
- Every raised error derives from `YtAudioError`; `yt_dlp.utils.DownloadError` is classified in
  `resilience.py`, never leaked to callers. No bare `except Exception`.
- Tests **mock `YoutubeDL` and PATH** — no network, no real ffmpeg, no real download in CI.
- `mypy src/` runs strict and must stay clean; the package ships `py.typed`.
- Depend on `yt-dlp` with a floor and no ceiling.
- The mandatory chain (`ruff format . && ruff check --fix . && mypy src/ && pytest -q`) must be
  green at the end of every phase — the orchestrator owns the final run.

# yt-audio-extractor

Zero-config Python **library** and **CLI** to reliably extract audio from YouTube (and every
other site [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) supports).

It wraps `yt-dlp` and abstracts away the parts that make one-off audio extraction annoying:
format selection, `ffmpeg` post-processing, ID3 tag + thumbnail embedding, and — crucially —
YouTube's anti-bot walls ("Sign in to confirm you're not a bot", "The page needs to be reloaded")
via an automatic **player-client fallback ladder** and opt-in cookies.

- **Distribution:** `yt-audio-extractor` · **Import package:** `ytaudio` · **Python:** 3.9+
- **Requires** [`ffmpeg`](https://ffmpeg.org/download.html) on your `PATH` (the tool tells you how
  to install it if it's missing).

## Install

`yt-audio-extractor` is a Python package (3.9+; a recent 3.11–3.13 is ideal). Install it into an
**isolated environment** so it doesn't touch your system Python. Pick one of the two options below.

> **Not on PyPI yet.** Until the first release, install from source by replacing
> `yt-audio-extractor` in the commands below with
> `git+https://github.com/engramo-developer/yt-audio-extractor.git` — e.g.
> `pipx install git+https://github.com/engramo-developer/yt-audio-extractor.git`.

### Option A — pipx (recommended for using the CLI)

[pipx](https://pipx.pypa.io) installs the tool in its own isolated environment **and** puts the
`yt-audio-extractor` command on your `PATH`, so it works everywhere without activating anything:

```bash
pipx install yt-audio-extractor
```

### Option B — a virtual environment

Create a project-local virtual environment and install into it:

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install yt-audio-extractor
```

```powershell
# Windows (PowerShell)
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install yt-audio-extractor
```

The `yt-audio-extractor` command is available while the venv is active; run `deactivate` to leave
it. Nothing lands in your system Python either way.

### ffmpeg

Install `ffmpeg` if you don't have it (the tool prints this hint too if it's missing):

| OS | Command |
|---|---|
| macOS | `brew install ffmpeg` |
| Debian/Ubuntu | `sudo apt install ffmpeg` |
| Fedora | `sudo dnf install ffmpeg` |
| Arch | `sudo pacman -S ffmpeg` |
| Windows | `winget install ffmpeg` (or `choco install ffmpeg`) |

## CLI

```bash
# Simplest case — MP3 into the current directory, tags + cover art embedded
yt-audio-extractor "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# No URL? Just run it and paste the link when prompted:
yt-audio-extractor

# Choose format, output dir, quality
yt-audio-extractor -f m4a -o ~/Music -q 0 "https://youtu.be/dQw4w9WgXcQ"

# Multiple URLs (a failure on one doesn't abort the rest)
yt-audio-extractor URL1 URL2 URL3

# Skip metadata / thumbnail embedding
yt-audio-extractor --no-metadata --no-thumbnail URL

# Get past a login/age wall with browser cookies (opt-in)
yt-audio-extractor --cookies-from-browser chrome URL
yt-audio-extractor --cookies-file cookies.txt URL

# See the full technical output when something goes wrong
yt-audio-extractor --verbose URL
```

Output is clean by default — a progress bar and a `✓ Saved: …` line per URL,
with plain-language messages on failure. Pass `--verbose` for the raw `yt-dlp`
logs, or `--quiet` to print only errors. The module form works too:
`python -m ytaudio URL`.

**Exit codes:** `0` all succeeded (or nothing to do) · `1` at least one URL failed ·
`2` `ffmpeg` missing or bad args.

## Library

```python
from ytaudio import AudioExtractor, ExtractOptions, AudioFormat

extractor = AudioExtractor(
    ExtractOptions(
        audio_format=AudioFormat.MP3,
        output_dir="~/Music",  # str or pathlib.Path; a leading ~ is expanded
        embed_metadata=True,
        embed_thumbnail=True,
    )
)

result = extractor.extract("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
print(result.filepath, result.title, result.artist, result.client_used)

# Metadata only, no download:
info = extractor.probe("https://youtu.be/dQw4w9WgXcQ")

# Batch — returns only the successful results:
results = extractor.extract_many(["URL1", "URL2"])
```

Everything raised derives from `YtAudioError`, so you can catch broadly or precisely:

```python
from ytaudio import (
    AudioExtractor,
    YtAudioError,
    FfmpegNotFoundError,
    VideoUnavailableError,
    BotProtectionError,
)

try:
    AudioExtractor().extract(url)
except FfmpegNotFoundError as e:
    print(e)  # includes an OS-specific install hint
except VideoUnavailableError:
    ...  # private/removed/members-only — not retriable
except BotProtectionError:
    ...  # every fallback client was exhausted
except YtAudioError:
    ...  # anything else from this library
```

## How the anti-bot resilience works

YouTube's extraction defenses are a moving target — and the fixes for them live in **`yt-dlp`**,
not here. This library stays a thin, current layer on top:

1. **Client fallback ladder.** Each extraction tries a sequence of YouTube "player clients"
   (`android → tv → web` by default, configurable via `ExtractOptions.client_order`). A bot-wall or
   transient failure advances to the next client automatically.
2. **Fail fast on fatal errors.** If the video is genuinely unavailable (private, removed,
   members-only), the ladder stops immediately instead of burning every client.
3. **Opt-in cookies.** When client rotation isn't enough (age/login gates), supply
   `cookies_from_browser="chrome"` or a `cookies.txt` and the library retries the ladder with them.
4. **Loose `yt-dlp` floor, no ceiling.** If a video breaks, **update yt-dlp first** —
   `pip install -U yt-dlp` — to pick up upstream YouTube fixes without waiting on a release here.

## Troubleshooting

**"Video unavailable" / "This video is unavailable" on videos you know are public.**
This is almost always YouTube bot-walling your IP, not a real takedown — the same request
succeeds from a browser. Work through it in order:

1. **Update yt-dlp first** — most YouTube breakage is fixed upstream within days:
   ```bash
   pip install -U yt-dlp
   ```
2. **Supply cookies from a browser that is signed in to YouTube.** Anonymous cookies do **not**
   defeat the wall — you must be logged into your YouTube/Google account in that browser:
   ```bash
   yt-audio-extractor --cookies-from-browser firefox "<url>"
   # or an exported Netscape cookies.txt:
   yt-audio-extractor --cookies-file cookies.txt "<url>"
   ```
   On macOS, reading Chrome/Safari cookies may prompt for Keychain / Full Disk Access; Firefox
   reads without a prompt.
3. **Try a different network** if you're on a datacenter/VPN IP — those are aggressively walled.

`FfmpegNotFoundError` at startup means `ffmpeg` isn't on your `PATH` — install it (see the table
above); the error message includes the exact command for your OS.

## Development

```bash
pip install -e '.[dev]'

# Format · lint · type-check · test
ruff format . && ruff check --fix . && mypy src/ && pytest -q

# With coverage
pytest --cov=ytaudio --cov-report=term-missing
```

Tests mock `yt-dlp` and the `ffmpeg` lookup — **no network and no real downloads** — so the suite
runs in seconds. Real end-to-end checks are manual only.

## License

MIT © Volodymyr Dotsenko

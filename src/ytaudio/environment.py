"""Host-capability checks — `ffmpeg` detection and OS-specific install guidance.

`ffmpeg` is a required external binary (not a Python dependency); we detect it
via `shutil.which` rather than parsing `PATH` ourselves, and surface an
actionable, OS-specific install hint when it is missing.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from ytaudio.exceptions import FfmpegNotFoundError

_PREAMBLE = "ffmpeg is required to extract audio."
_DOWNLOAD_URL = "See https://ffmpeg.org/download.html for other options."


def ffmpeg_install_hint() -> str:
    """Return an OS-specific, human-readable ffmpeg install instruction."""
    if sys.platform == "darwin":
        install_line = "Install it with Homebrew:\n  brew install ffmpeg"
    elif sys.platform.startswith("linux"):
        install_line = (
            "Install it with your distro's package manager:\n"
            "  sudo apt install ffmpeg      # Debian/Ubuntu\n"
            "  sudo dnf install ffmpeg      # Fedora\n"
            "  sudo pacman -S ffmpeg        # Arch"
        )
    elif sys.platform == "win32":
        install_line = (
            "Install it with a package manager:\n  winget install ffmpeg\n  choco install ffmpeg"
        )
    else:
        install_line = "Install it via your platform's package manager."

    return f"{_PREAMBLE}\n{install_line}\n{_DOWNLOAD_URL}"


def check_ffmpeg() -> Path:
    """Locate the `ffmpeg` binary on PATH.

    Returns:
        The resolved path to `ffmpeg`.

    Raises:
        FfmpegNotFoundError: if `ffmpeg` cannot be found on PATH.
    """
    found = shutil.which("ffmpeg")
    if found is None:
        raise FfmpegNotFoundError(ffmpeg_install_hint())
    return Path(found)

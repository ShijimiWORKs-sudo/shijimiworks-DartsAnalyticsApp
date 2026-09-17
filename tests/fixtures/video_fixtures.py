"""Synthetic test video generation via ffmpeg's lavfi test sources.

No real board-throw footage exists in this repo (device video files are
never committed — see .gitignore's `media/` entry and design principle
"動画原本を上書きしない"). These synthetic clips exercise the same
ffprobe/ffmpeg code paths as real footage would, with known, controllable
properties (resolution/fps/duration/brightness/sharpness) — the same
approach Phase 3 used for board-image calibration tests.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def make_test_video(
    path: str | Path,
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    duration: float = 4.0,
    source: str = "testsrc",  # 'testsrc' (patterned/sharp), 'color=c=black', 'color=c=gray'
) -> Path:
    path = Path(path)
    # ffmpeg lavfi syntax: "name=key=val:key2=val2" — the separator between
    # the source name and its first option is '=', but if `source` already
    # carries an option (e.g. "color=c=black"), further options append with
    # ':' instead.
    separator = ":" if "=" in source else "="
    lavfi = f"{source}{separator}size={width}x{height}:rate={fps}:duration={duration}"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        lavfi,
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0 or not path.exists():
        raise RuntimeError(f"failed to generate test video: {result.stderr}")
    return path

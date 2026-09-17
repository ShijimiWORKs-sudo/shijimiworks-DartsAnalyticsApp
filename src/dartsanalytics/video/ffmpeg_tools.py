"""Thin wrapper around the `ffmpeg`/`ffprobe` binaries for metadata and
frame extraction.

Design note (new external dependency, flagged per AGENTS.md
"新規依存関係は必要性を確認"): reading arbitrary video containers/codecs
without ffmpeg would mean writing or vendoring a video decoder, which is
out of scope. ffmpeg is a *system* binary, not a pip package — it must be
installed separately on whatever machine runs this code (this sandbox has
it; the user's Windows PC may not). Every function here fails with a clear
FFmpegNotFoundError rather than a cryptic OSError/FileNotFoundError so the
app can surface "ffmpegをインストールしてください" instead of crashing.

Frame extraction never writes into the source video file or its directory
implicitly — callers control the output path, and this module never
deletes or moves the source (動画原本を上書きしない).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


class FFmpegNotFoundError(RuntimeError):
    def __init__(self, binary: str):
        super().__init__(
            f"'{binary}' was not found on PATH. Video intake requires ffmpeg/ffprobe "
            "to be installed separately (they are not a Python package) — "
            "see AGENTS.md / docs/codex/reports for setup notes."
        )


class VideoProbeError(ValueError):
    """Raised when ffprobe ran but the file has no usable video stream, or
    is unreadable — i.e. a genuinely bad/corrupt input, not a missing tool.
    """


@dataclass(frozen=True)
class VideoMetadata:
    width: int
    height: int
    fps: float
    duration_sec: float
    codec: str | None

    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "duration_sec": self.duration_sec,
            "codec": self.codec,
        }


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise FFmpegNotFoundError(cmd[0]) from None


def _parse_frame_rate(rate_str: str) -> float:
    """ffprobe reports frame rate as a fraction string, e.g. '30000/1001'."""
    if "/" in rate_str:
        num, den = rate_str.split("/", 1)
        den_f = float(den)
        return float(num) / den_f if den_f else 0.0
    return float(rate_str)


def probe_metadata(path: str | Path) -> VideoMetadata:
    path = Path(path)
    if not path.exists():
        raise VideoProbeError(f"file does not exist: {path}")

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,codec_name",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    result = _run(cmd)
    if result.returncode != 0:
        raise VideoProbeError(f"ffprobe failed for {path}: {result.stderr.strip()}")

    try:
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        if not streams:
            raise VideoProbeError(f"no video stream found in {path}")
        stream = streams[0]
        duration = float(data.get("format", {}).get("duration", 0.0))
        return VideoMetadata(
            width=int(stream["width"]),
            height=int(stream["height"]),
            fps=_parse_frame_rate(stream["r_frame_rate"]),
            duration_sec=duration,
            codec=stream.get("codec_name"),
        )
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise VideoProbeError(f"could not parse ffprobe output for {path}: {exc}") from exc


def extract_sample_frames_gray(
    path: str | Path, *, count: int = 5, metadata: VideoMetadata | None = None
) -> list[np.ndarray]:
    """Extract `count` evenly-spaced grayscale frames as numpy arrays.

    Sampling avoids the first/last ~5% of the clip (the "3秒静止" buffer at
    each end per the shooting procedure doc) so quality metrics reflect the
    actual throwing action, not the stationary setup/wind-down.
    """
    path = Path(path)
    meta = metadata or probe_metadata(path)
    if meta.duration_sec <= 0:
        raise VideoProbeError(f"video has no usable duration: {path}")
    if count < 1:
        raise ValueError(f"count must be >= 1, got {count}")

    margin = meta.duration_sec * 0.05
    usable_start, usable_end = margin, max(margin, meta.duration_sec - margin)
    if usable_end <= usable_start:
        usable_start, usable_end = 0.0, meta.duration_sec

    timestamps = (
        [meta.duration_sec / 2]
        if count == 1
        else [usable_start + (usable_end - usable_start) * i / (count - 1) for i in range(count)]
    )

    frames: list[np.ndarray] = []
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        for i, ts in enumerate(timestamps):
            out_path = Path(tmp_dir) / f"frame_{i}.png"
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                f"{ts:.3f}",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-vf",
                "format=gray",
                str(out_path),
            ]
            result = _run(cmd)
            if result.returncode != 0 or not out_path.exists():
                raise VideoProbeError(
                    f"failed to extract frame at t={ts:.2f}s from {path}: {result.stderr.strip()}"
                )
            with Image.open(out_path) as img:
                frames.append(np.array(img, dtype=np.float64))

    return frames

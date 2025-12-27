# video_overlay.py

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image


BBox = Tuple[int, int, int, int]


def _run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            "FFmpeg failed:\n"
            + " ".join(cmd)
            + "\n\nSTDERR:\n"
            + p.stderr
        )


def _find_hole_bbox(frame_rgba: Image.Image, hole_alpha_max: int) -> BBox:
    """
    Detect transparent placeholder hole via alpha channel.
    """
    arr = np.array(frame_rgba)
    alpha = arr[..., 3]

    mask = alpha <= hole_alpha_max
    ys, xs = np.where(mask)

    if xs.size == 0 or ys.size == 0:
        raise RuntimeError("Could not detect hole in frame (alpha scan failed)")

    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def overlay_video_with_frame_only(
    input_video: Path,
    output_video: Path,
    frame_path: Path,
    *,
    hole_alpha_max: int = 20,
    ffmpeg_bin: str = "ffmpeg",
) -> Path:
    """
    Places input video inside frame hole and overlays frame on top.
    NO TEXT. NO FONTS.
    """

    input_video = Path(input_video)
    output_video = Path(output_video)
    frame_path = Path(frame_path)

    if not input_video.exists():
        raise FileNotFoundError(input_video)
    if not frame_path.exists():
        raise FileNotFoundError(frame_path)

    frame_img = Image.open(frame_path).convert("RGBA")
    frame_w, frame_h = frame_img.size

    px0, py0, px1, py1 = _find_hole_bbox(frame_img, hole_alpha_max)
    hole_w = px1 - px0
    hole_h = py1 - py0

    output_video.parent.mkdir(parents=True, exist_ok=True)

    filter_complex = (
        f"color=c=black@0.0:s={frame_w}x{frame_h}[base];"
        f"[0:v]scale={hole_w}:{hole_h}:force_original_aspect_ratio=increase,"
        f"crop={hole_w}:{hole_h}[vid];"
        f"[base][vid]overlay={px0}:{py0}[withvid];"
        f"[withvid][1:v]overlay=0:0[outv]"
    )

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(input_video),
        "-loop", "1",
        "-i", str(frame_path),
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-movflags", "+faststart",
        "-shortest",
        str(output_video),
    ]

    _run(cmd)
    return output_video


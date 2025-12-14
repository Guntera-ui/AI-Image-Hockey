from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont


RGB = Tuple[int, int, int]
BBox = Tuple[int, int, int, int]


# ============================
# Config
# ============================

@dataclass
class OverlayConfig:
    frame_path: Path
    font_name_path: Path
    font_shot_path: Path

    # Detect placeholder hole by alpha <= this value
    hole_alpha_max: int = 20

    # Safe horizontal region for text (avoids left logo / edges)
    safe_left_ratio: float = 0.22
    safe_right_ratio: float = 0.04

    # Text vertical placement relative to placeholder top
    text_y_in_placeholder_ratio: float = 0.055

    # Font sizes relative to placeholder height
    name_size_ratio_ph: float = 0.018
    shot_size_ratio_ph: float = 0.075

    # Gap between name and powershot (relative to placeholder height)
    gap_ratio_ph: float = 0.045

    # Colors
    name_color: RGB = (240, 240, 240)
    shot_color: RGB = (230, 30, 45)

    # Readability stroke
    stroke_width: int = 2
    stroke_fill: RGB = (0, 0, 0)

    # ffmpeg path
    ffmpeg_bin: str = "ffmpeg"


# ============================
# Helpers
# ============================

def _run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(cmd)
            + "\n\nSTDOUT:\n"
            + p.stdout
            + "\n\nSTDERR:\n"
            + p.stderr
        )


def _find_hole_bbox(frame_rgba: Image.Image, hole_alpha_max: int) -> BBox:
    """
    Find bbox of the transparent-ish hole area using alpha <= hole_alpha_max.
    Returns (x0, y0, x1, y1) where x1/y1 are exclusive.
    """
    arr = np.array(frame_rgba)  # H,W,4
    alpha = arr[..., 3]

    mask = alpha <= hole_alpha_max
    ys, xs = np.where(mask)

    if xs.size == 0 or ys.size == 0:
        raise ValueError(
            "Could not detect placeholder hole by alpha.\n"
            f"Try increasing hole_alpha_max (current {hole_alpha_max})."
        )

    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    return x0, y0, x1, y1


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    b = draw.textbbox((0, 0), text, font=font)
    return b[2] - b[0]


def _fit_font_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Path,
    start_size: int,
    max_width: int,
    min_size: int = 10,
) -> ImageFont.FreeTypeFont:
    """
    Reduce font size until text fits max_width.
    """
    size = start_size
    while size > min_size:
        f = ImageFont.truetype(str(font_path), size=size)
        if _text_width(draw, text, f) <= max_width:
            return f
        size -= 1
    return ImageFont.truetype(str(font_path), size=min_size)


def _cap_word(w: str) -> str:
    if not w:
        return ""
    return w[:1].upper() + w[1:].lower()


def _normalize_name(first_name: str, last_name: str) -> str:
    """
    Dynamic (not hardcoded), professional capitalization.
    """
    fn = (first_name or "").strip()
    ln = (last_name or "").strip()

    if not fn and not ln:
        return "PLAYER"

    # Capitalize each token
    fn = " ".join(_cap_word(x) for x in fn.split())
    ln = " ".join(_cap_word(x) for x in ln.split())

    return f"{fn} {ln}".strip()


def _normalize_shot(powershot: str) -> str:
    """
    Powershot stays hardcoded by default in public API, but we normalize just in case.
    """
    s = (powershot or "").strip()
    return s.upper() if s else ""


def _make_overlay_png_with_text(
    cfg: OverlayConfig,
    first_name: str,
    last_name: str,
    powershot: str,
    out_png: Path,
) -> Tuple[int, int, BBox]:
    """
    Creates overlay PNG: frame (already has hole) + text drawn on top.
    Returns (frame_w, frame_h, hole_bbox).
    """
    frame = Image.open(cfg.frame_path).convert("RGBA")
    w, h = frame.size

    hole_bbox = _find_hole_bbox(frame, cfg.hole_alpha_max)
    px0, py0, px1, py1 = hole_bbox
    ph = py1 - py0

    overlay = frame.copy()
    draw = ImageDraw.Draw(overlay)

    # Dynamic name, hardcoded powershot (passed in)
    full_name = _normalize_name(first_name, last_name)
    shot = _normalize_shot(powershot)

    # Safe horizontal region
    safe_left = int(w * cfg.safe_left_ratio)
    safe_right = w - int(w * cfg.safe_right_ratio)
    usable_w = max(10, safe_right - safe_left)

    # Font sizes based on placeholder height
    name_size = max(12, int(ph * cfg.name_size_ratio_ph))
    shot_size = max(11, int(ph * cfg.shot_size_ratio_ph))

    # Gap scales with placeholder height (resolution safe)
    gap = int(ph * cfg.gap_ratio_ph)

    # Width budgeting (dynamic, not a fixed 38%)
    name_len = max(1, len(full_name))
    shot_len = max(1, len(shot))
    total_len = name_len + shot_len

    shot_share = shot_len / total_len
    shot_share = max(0.25, min(0.55, shot_share))  # clamp
    shot_budget = int(usable_w * shot_share)
    name_budget = usable_w - gap - shot_budget
    name_budget = max(40, name_budget)
    shot_budget = max(40, shot_budget)

    # Fit fonts to budgets
    name_font = _fit_font_to_width(draw, full_name, cfg.font_name_path, name_size, name_budget, min_size=10)
    shot_font = _fit_font_to_width(draw, shot, cfg.font_shot_path, shot_size, shot_budget, min_size=10)

    name_w = _text_width(draw, full_name, name_font)
    shot_w = _text_width(draw, shot, shot_font)
    total_w = name_w + gap + shot_w

    # Center inside safe region
    x = safe_left + (usable_w - total_w) // 2
    x = max(safe_left, min(x, safe_right - total_w))

    # Y relative to placeholder
    y = py0 + int(ph * cfg.text_y_in_placeholder_ratio)

    # Draw name
    draw.text(
        (x, y),
        full_name,
        font=name_font,
        fill=cfg.name_color,
        stroke_width=cfg.stroke_width,
        stroke_fill=cfg.stroke_fill,
    )

    # Draw shot
    draw.text(
        (x + name_w + gap, y),
        shot,
        font=shot_font,
        fill=cfg.shot_color,
        stroke_width=cfg.stroke_width,
        stroke_fill=cfg.stroke_fill,
    )

    out_png.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(out_png)

    return w, h, hole_bbox


# ============================
# Public API
# ============================

def overlay_video_with_branding(
    input_video: Path,
    output_video: Path,
    first_name: str,
    last_name: str,
    *,
    frame_path: Path,
    font_name_path: Path,
    font_shot_path: Path,
    hole_alpha_max: int = 20,
    # keep this overridable but default is your requested hardcode behavior
    powershot: str = "THUNDERSTRIKE",
    # Optional tuning knobs
    safe_left_ratio: float = 0.22,
    safe_right_ratio: float = 0.04,
    text_y_in_placeholder_ratio: float = 0.055,
    name_size_ratio_ph: float = 0.018,
    shot_size_ratio_ph: float = 0.075,
    gap_ratio_ph: float = 0.045,
    name_color: RGB = (240, 240, 240),
    shot_color: RGB = (230, 30, 45),
    stroke_width: int = 2,
    stroke_fill: RGB = (0, 0, 0),
    work_dir: Optional[Path] = None,
    ffmpeg_bin: str = "ffmpeg",
) -> Path:
    """
    Output video = input video placed into the frame hole + frame+text on top.

    Name & surname are dynamic (passed in).
    Powershot defaults to hardcoded "THUNDERSTRIKE".
    """
    input_video = Path(input_video)
    output_video = Path(output_video)

    if work_dir is None:
        work_dir = output_video.parent / ".tmp_overlay"
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    cfg = OverlayConfig(
        frame_path=Path(frame_path),
        font_name_path=Path(font_name_path),
        font_shot_path=Path(font_shot_path),
        hole_alpha_max=hole_alpha_max,
        safe_left_ratio=safe_left_ratio,
        safe_right_ratio=safe_right_ratio,
        text_y_in_placeholder_ratio=text_y_in_placeholder_ratio,
        name_size_ratio_ph=name_size_ratio_ph,
        shot_size_ratio_ph=shot_size_ratio_ph,
        gap_ratio_ph=gap_ratio_ph,
        name_color=name_color,
        shot_color=shot_color,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
        ffmpeg_bin=ffmpeg_bin,
    )

    overlay_png = work_dir / "overlay_top.png"
    frame_w, frame_h, (px0, py0, px1, py1) = _make_overlay_png_with_text(
        cfg=cfg,
        first_name=first_name,
        last_name=last_name,
        powershot=powershot,
        out_png=overlay_png,
    )

    pw = px1 - px0
    ph = py1 - py0

    # Compose:
    # - create transparent canvas
    # - scale input video to cover hole, crop to hole
    # - overlay cropped video into hole position
    # - overlay frame+text PNG on top
    filter_complex = (
        f"color=c=black@0.0:s={frame_w}x{frame_h}[base];"
        f"[0:v]scale={pw}:{ph}:force_original_aspect_ratio=increase,"
        f"crop={pw}:{ph}[vfit];"
        f"[base][vfit]overlay={px0}:{py0}:format=auto[withvid];"
        f"[withvid][1:v]overlay=0:0:format=auto[outv]"
    )

    cmd = [
        cfg.ffmpeg_bin,
        "-y",
        "-i", str(input_video),
        "-loop", "1",
        "-i", str(overlay_png),
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


if __name__ == "__main__":
    # Local test (adjust paths)
    input_video = Path("media/test.mp4")
    output_video = Path("media/test_framed.mp4")

    frame = Path("assets/overlays/frame_reference.png")
    font_name = Path("assets/overlays/fonts/Montserrat-SemiBold.ttf")
    font_shot = Path("assets/overlays/fonts/Montserrat-Bold.ttf")

    overlay_video_with_branding(
        input_video=input_video,
        output_video=output_video,
        first_name="giorgi",
        last_name="lekiashvili",
        frame_path=frame,
        font_name_path=font_name,
        font_shot_path=font_shot,
        hole_alpha_max=20,
        # powershot defaults to THUNDERSTRIKE
    )

    print(f"✅ Wrote {output_video}")


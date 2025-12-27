# overlay_frames.py

from pathlib import Path
from random import choice
from typing import Literal

Tier = Literal["low", "mid", "high"]

BASE_DIR = Path(__file__).resolve().parent
OVERLAYS_DIR = BASE_DIR / "assets" / "overlays"

FRAMES = {
    "low": [
        OVERLAYS_DIR / "JM Photoframe_Low 1.png",
        OVERLAYS_DIR / "JM Photoframe_Low 2.png",
        OVERLAYS_DIR / "JM Photoframe_Low 3.png",
    ],
    "mid": [
        OVERLAYS_DIR / "JM Photoframe_Mid 1.png",
        OVERLAYS_DIR / "JM Photoframe_Mid 2.png",
        OVERLAYS_DIR / "JM Photoframe_Mid 3.png",
    ],
    "high": [
        OVERLAYS_DIR / "JM Photoframe_High 1.png",
        OVERLAYS_DIR / "JM Photoframe_High 2.png",
        OVERLAYS_DIR / "JM Photoframe_High 3.png",
    ],
}


def tier_from_score(total_score: int) -> Tier:
    if total_score >= 300:
        return "high"
    if total_score >= 150:
        return "mid"
    return "low"


def pick_frame_for_score(total_score: int) -> Path:
    tier = tier_from_score(total_score)
    frames = FRAMES[tier]

    if not frames:
        raise RuntimeError(f"No frames defined for tier: {tier}")

    frame = choice(frames)

    if not frame.exists():
        raise FileNotFoundError(f"Frame not found: {frame}")

    return frame


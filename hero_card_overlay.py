# hero_card_overlay.py

from pathlib import Path
from PIL import Image
import uuid

from config import MEDIA_DIR


def generate_card_with_frame(
    hero_image_path: Path,
    frame_path: Path,
) -> Path:
    """
    Simple compositing:
    - Hero image goes behind
    - Frame stays untouched on top
    """

    hero = Image.open(hero_image_path).convert("RGBA")
    frame = Image.open(frame_path).convert("RGBA")

    # Resize hero to cover frame
    hero = hero.resize(frame.size, Image.LANCZOS)

    card = Image.alpha_composite(hero, frame)

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    out = MEDIA_DIR / f"card_{uuid.uuid4().hex}.png"
    card.save(out)

    return out


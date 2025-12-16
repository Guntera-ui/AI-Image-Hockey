import uuid
from io import BytesIO
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types
from PIL import Image

from config import MEDIA_DIR

MODEL_ID = "gemini-2.5-flash-image"
client = genai.Client()


def _guess_mime_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in [".jpg", ".jpeg"]:
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    return "image/jpeg"


def _player_desc_from_gender(gender: Optional[str]) -> str:
    if gender and gender.lower() == "female":
        return "a professional female ice hockey player"
    if gender and gender.lower() == "male":
        return "a professional male ice hockey player"
    return "a professional ice hockey player"


def generate_hero_from_photo(
    user_photo_path: Path,
    user_name: str,
    power_label: str,
    gender: Optional[str] = None,  # optional, backward-compatible
) -> Path:
    """
    Use Gemini 2.5 Flash Image to turn the user photo into a
    full hockey-style hero image.

    Returns: Path to a PNG hero image stored in MEDIA_DIR.
    """
    mime_type = _guess_mime_type(user_photo_path)
    photo_bytes = user_photo_path.read_bytes()

    image_part = types.Part.from_bytes(
        data=photo_bytes,
        mime_type=mime_type,
    )

    player_desc = _player_desc_from_gender(gender)

    # Big changes:
    # - identity locked
    # - gender-neutral pronouns unless gender is provided
    # - remove contradictory branding instructions
    prompt = f"""
CRITICAL IDENTITY RULES (MUST FOLLOW):
- Preserve the EXACT facial identity from the selfie.
- Do NOT change gender, age, ethnicity, face shape, eyes, nose, lips, or jawline.
- SAME PERSON as the selfie. No face swap. No look-alike.
- Keep realistic skin texture (no beauty filter / no plastic skin).

TASK:
Convert this selfie into a hyper-realistic, high-definition image of {player_desc}
in full motion skating aggressively on a glossy, reflective ice rink during an intense championship moment,
facing toward the camera POV.

UNIFORM (DO NOT CHANGE THESE COLORS):
- Navy-base hockey jersey with sky-blue stripes
- Subtle teal piping
- Minimal sand trim
- Bold neon-pink accents
- White numbers
- Professional helmet, gloves, skates, and pads (realistic fabric texture + stitching)
BACKGROUND:
Behind the player, the ice hockey arena is realistic but cinematically enhanced.
The crowd and boards remain believable and true to a real championship arena,
but lighting is elevated for a promotional, high-energy look.

Arena lighting features controlled neon accents as LIGHTING ONLY:
purple, magenta, electric blue, and subtle crimson highlights.
These appear as rim light, reflections, and spotlights — not as physical glowing objects.

Use volumetric light rays from stadium spotlights, soft bloom, and gentle lens flare
to illuminate ice spray, mist, and airborne particles.
The background transitions into soft bokeh with blurred crowd silhouettes and
colored spotlights, maintaining strong depth separation from the player.

The ice surface is glossy and reflective with realistic texture,
showing faint reflections of the player and light streaks.
Add subtle fog and illuminated ice particles for atmosphere,
but keep the arena grounded and realistic (not futuristic, not abstract).

BRANDING:
- No third-party logos.
- No extra text.
- Do not invent team/NHL branding.

ACTION:
- Mid-stride, forward lean, knees bent, ice spray
- Hockey stick held with both hands, puck visible near blade
- Subtle motion blur on limbs, sharp focus on face

CAMERA / STYLE:
- Photorealistic sports photography look (not illustrated)
- Natural arena lighting, realistic shadows and reflections
- Shallow depth of field, face in crisp focus
- 9:16 vertical
"""

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=[image_part, prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="9:16"),
        ),
    )

    image_bytes = None
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) is not None:
            image_bytes = part.inline_data.data
            break

    if image_bytes is None:
        raise RuntimeError("Gemini did not return an image")

    hero_image = Image.open(BytesIO(image_bytes)).convert("RGBA")
    out_path = MEDIA_DIR / f"hero_{uuid.uuid4().hex}.png"
    hero_image.save(out_path)

    return out_path


def generate_full_card_from_hero(
    hero_image_path: Path,
    frame_style_path: Path,
    user_name: str,
    power_label: str,
) -> Path:
    """
    Use Gemini to create the final card by combining:
    - IMAGE 1: hero (must keep player identity)
    - IMAGE 2: thunderstrike template (must keep graphics/logos)
    """
    hero_bytes = hero_image_path.read_bytes()
    frame_bytes = frame_style_path.read_bytes()

    # ✅ FIX: correct MIME types (do NOT force image/jpeg)
    hero_part = types.Part.from_bytes(
        data=hero_bytes,
        mime_type=_guess_mime_type(hero_image_path),
    )
    frame_part = types.Part.from_bytes(
        data=frame_bytes,
        mime_type=_guess_mime_type(frame_style_path),
    )

    name_text = user_name.upper()
    power_text = power_label.upper()
    arc_text = f"{name_text} • {power_text}"

    # Best-possible prompt for "keep frame still" while still using Gemini.
    # Works whether frame has true alpha (PNG) or a black/dark "fake cutout" (JPG).
    

    prompt = f"""
You are doing STRICT COMPOSITING (NOT redesigning).

IMAGE 1 = HERO IMAGE (source of PLAYER + BACKGROUND).
IMAGE 2 = THUNDERSTRIKE TEMPLATE (frame, logos, graphics).

ABSOLUTE RULES:
1) KEEP IMAGE 2 UNCHANGED.
   - Do NOT redraw, repaint, recolor, warp, resize, or move ANY element from IMAGE 2.
   - Preserve Thunderstrike wordmark, Jersey Mike’s logo, NHL logo, puck, borders,
     brush strokes, dotted patterns, and bottom logo strip EXACTLY.

2) BACKGROUND & PLAYER FILL:
   - Use IMAGE 1 as the COMPLETE filler for the inner area of the frame.
   - The background visible inside the frame must come directly from IMAGE 1.
   - Do NOT generate or replace the background with a new environment.
   - Ensure the hero background fully covers all black/empty areas.

3) PLAYER INTEGRITY:
   - The player (face, body, pose, gear) must remain exactly from IMAGE 1.
   - Do NOT change identity, gender, facial features, or proportions.

TEXT:
- Keep all existing text/logos in IMAGE 2 unchanged EXCEPT the top curved arc text.
- Replace ONLY the top arc text with exactly:
  "{arc_text}"
- Match the same curvature, font style, spacing, size, and white color.

OUTPUT:
- Final image must look like IMAGE 2 unchanged,
  with IMAGE 1 (player + background) visible behind it.
- 9:16 aspect ratio.
"""



    response = client.models.generate_content(
        model=MODEL_ID,
        contents=[hero_part, frame_part, prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="9:16"),
        ),
    )

    image_bytes = None
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) is not None:
            image_bytes = part.inline_data.data
            break

    if image_bytes is None:
        raise RuntimeError("Gemini did not return an image")

    card_image = Image.open(BytesIO(image_bytes)).convert("RGBA")
    out_path = MEDIA_DIR / f"card_{uuid.uuid4().hex}.png"
    card_image.save(out_path)

    return out_path


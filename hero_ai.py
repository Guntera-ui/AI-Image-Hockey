import uuid
from io import BytesIO
from pathlib import Path

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


def generate_hero_from_photo(
    user_photo_path: Path,
    user_name: str,
    power_label: str,
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

    prompt = (
        "You are creating a vertical hockey action poster from a reference face.\n\n"
        "Use the person or animal in the input photo as the character's face, but "
        "turn them into a professional hockey player.\n\n"
        "Composition and style requirements:\n"
        "- Vertical 9:16 poster framing.\n"
        "- Full body in a dynamic skating or shooting pose on the ice.\n"
        "- Put the head and upper body in the upper half of the frame and keep "
        "the skates comfortably above the very bottom edge so there is visual "
        "space above and below the player for graphic overlays.\n"
        "- Background: bright hockey arena with stadium lights and a blurred "
        "crowd, similar to a professional NHL broadcast. Slight depth-of-field "
        "blur in the background is good.\n"
        "- Jersey: generic red and blue pro-style uniform with a simple, bold "
        "fictional logo. Do NOT use any real team or brand logos or text.\n"
        "- Lighting: vivid and dramatic, with strong highlights from the arena "
        "lights, but keep the scene clean and readable.\n"
        "- Keep the ice and player clearly visible. Do NOT add extra diagonal "
        "paint strokes, graphic overlays, UI elements or spark trails across "
        "the image. No text, no watermarks, no border, no logo in the corners.\n\n"
        "Important: Only generate the photographic hockey scene (player + arena). "
        "We will add all poster templates, logos, and typography later."
    )

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=[image_part, prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="9:16"),
        ),
    )

    # extract hero image
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
    Use Gemini to create a full Thunderstrike-style card using:
    - hero_image_path: arena + player image
    - frame_style_path: reference card that shows frame+layout
    - user_name, power_label: text to use in the arc
    Returns: path to final card PNG.
    """
    hero_bytes = hero_image_path.read_bytes()
    frame_bytes = frame_style_path.read_bytes()

    hero_part = types.Part.from_bytes(data=hero_bytes, mime_type="image/jpeg")
    frame_part = types.Part.from_bytes(data=frame_bytes, mime_type="image/jpeg")

    name_text = user_name.upper()
    power_text = power_label.upper()
    arc_text = f"{name_text} • {power_text}"

    prompt = f"""
    You are EDITING a hockey hero image by applying a Thunderstrike-style frame.

    IMAGE 1 — BASE HERO IMAGE:
    • This image contains the FINAL hockey player.
    • You MUST keep this exact character, face, head shape, and expression.
    • The final output must ALWAYS use the face from IMAGE 1. Do NOT replace the face
      with the person in IMAGE 2.
    • Keep the original pose, body proportions, and camera angle exactly the same.
    • Preserve the arena background from IMAGE 1 (ice, boards, stadium lights, crowd).
    • You may enhance lighting and colors, but DO NOT replace the background or flatten it.

    IMAGE 2 — STYLE REFERENCE (Thunderstrike card):
    • This image is ONLY a style/layout guide.
    • You MUST NOT copy or replace the player from IMAGE 2.
    • You MUST NOT copy the face from IMAGE 2.
    • You MUST NOT copy the pose from IMAGE 2.
    • Only use stylistic elements from this card:
        - Jersey Mike’s top logo area
        - the curved white arc across the top
        - curved dotted red/blue brush pattern
        - the exact *position and curvature* of the top arc text
        - the Thunderstrike script title at the bottom
        - the diagonal red/blue paint strokes
        - the puck at lower right
        - the bottom blue bar with team logos
        - bright arena glow and vivid lighting style

    YOUR TASK:
    • Start from IMAGE 1 and KEEP the original player, arena, pose, and scene.
    • Add Thunderstrike-style overlays from IMAGE 2 on top of IMAGE 1.
    • DO NOT change the pose, helmet, body, or gear of the hero.
    • DO NOT replace or redraw the player with someone else.
    • DO NOT remove or overwrite the arena background from IMAGE 1.

    TEXT REQUIREMENTS:
    • In the curved top arc area, write exactly:
          "{arc_text}"
      and follow the same curvature, spacing, and white typographic style as in IMAGE 2.
    • DO NOT add placeholder text or extra words.

    JERSEY REQUIREMENTS:
    • Keep the shape and folds of the jersey from IMAGE 1.
    • Recolor it in the Thunderstrike / Jersey Mike’s palette (white/red/blue),
      inspired by the reference card’s uniform style.
    • Add a simple fictional crest or stylized circular logo similar in style to
      the reference. DO NOT use real NHL logos.

    FINAL RESULT MUST:
    • Preserve the hero from IMAGE 1 (face, pose, arena).
    • Apply Thunderstrike-style overlays, lighting, and layout from IMAGE 2.
    • Produce a polished, high-quality hockey promo poster with a 9:16 aspect ratio.
    """

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=[hero_part, frame_part, prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="9:16"),
        ),
    )

    # Extract the first image from the response
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

from io import BytesIO
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image

from config import MEDIA_DIR

client = genai.Client()  # GEMINI_API_KEY comes from env var


def ai_write_arc_text(poster_path: Path, user_name: str, power_label: str) -> Path:
    """
    Ask Gemini to:
    - remove the existing 'AL SILVESTRI • POWER SHOT' arc text
    - replace it with '<NAME> • <POWER_LABEL>' in the same style.

    Returns: path to edited poster PNG.
    """
    # Read poster image
    img_bytes = poster_path.read_bytes()
    img_part = types.Part.from_bytes(
        data=img_bytes,
        mime_type="image/png",  # or "image/jpeg" if that's what you save
    )

    name_text = user_name.upper()
    power_text = power_label.upper()
    new_arc_text = f"{name_text} • {power_text}"

    prompt = (
        "You are editing a hockey promo card.\n\n"
        "In the curved red arc near the top of the card there is existing small "
        "white curved text that currently says 'AL SILVESTRI • POWER SHOT' "
        "or something similar.\n\n"
        "Edit the image as follows:\n"
        "1. Completely remove that existing curved text from the arc.\n"
        f"2. In the exact same position, curve and render the new text:\n"
        f"   '{new_arc_text}'\n"
        "   Use bold white letters with a subtle outline that match the original "
        "typography style and follow the same curvature of the arc.\n"
        "3. Do NOT change any other part of the image: keep the sponsor logo, "
        "colors, strokes, player, background, and the word 'Thunderstrike' "
        "exactly as they are.\n\n"
        "Only modify the curved text in the arc; everything else should remain "
        "visually identical."
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=[img_part, prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio="9:16",
            ),
        ),
    )

    # Extract first image from the response
    edited_bytes = None
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) is not None:
            edited_bytes = part.inline_data.data
            break

    if edited_bytes is None:
        raise RuntimeError("Gemini did not return an edited image")

    edited_img = Image.open(BytesIO(edited_bytes)).convert("RGBA")

    out_path = MEDIA_DIR / f"poster_arc_{poster_path.stem}.png"
    edited_img.save(out_path)

    return out_path

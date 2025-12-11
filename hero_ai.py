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

    prompt = """Convert this selfie into a hyper-realistic, high-definition image of a professional ice hockey player wearing a professional uniform
    (navy-base hockey jersey with sky-blue stripes,
    subtle teal piping, minimal sand trim, bold neon-pink accents, and white numbers) in full motion skating
    aggressively on a glossy, reflective ice rink during an
    intense championship moment facing towards the camera pov.
    There should be no branding or text on the player at all, no logo on the shoulders, no branding on the gloves, helmet, or stick.
    The player is mid-stride, leaning forward with determination, knees bent, and both skates cutting sharply through the ice, sending small shards of ice flying.
    He grips his hockey stick with both hands, ready to strike or pass the puck, which is visible near the blade.
    The athlete wears a white and blue uniform with red accents — detailed fabric texture, subtle wear marks, mesh ventilation details, and realistic padding beneath the jersey.
    Include visible branding details like stitched seams, laces, and small logos, all accurately rendered without distortion. His helmet has a clear visor reflecting the surrounding lights, and dynamic shadows fall naturally across his body and the rink.
    Behind him, the arena lights explode into a vibrant, cinematic color palette — intense purple, magenta, electric blue, and crimson beams — creating a sense of high energy and depth. The light sources should produce volumetric light rays and subtle lens flares, illuminating the mist and ice particles in the air.
    The background should fade into soft bokeh with crowd silhouettes and colored spotlights, maintaining focus on the player in the foreground.
    The camera angle is dynamic, slightly low and tilted upward, emphasizing motion, power, and presence.
    The player’s reflection and motion blur appear subtly on the ice surface, adding realism and movement.
    The atmosphere is charged with energy and emotion — a mix of fog, glowing reflections, and high-contrast lighting that suggests this is the peak of a match.
    Include fine details like skate scratches, glistening ice texture, and faint vapor breath escaping the player’s helmet to convey intensity and realism.
    Render using ultra-photorealistic 8K resolution, physically based lighting, and dynamic depth of field (shallow focus on the player’s face and jersey details). The composition should resemble a cinematic sports photography shot captured on a 50mm lens, with a slightly desaturated background to make the foreground colors pop.
    Keywords for realism & quality: hyper-realistic lighting, ultra-detailed textures, realistic materials, volumetric glow, fog diffusion, light scattering, motion streaks, energy beams, high-contrast color grading, HDR exposure, professional sports photography, crisp reflections, studio-grade lighting setup, photoreal rendering.
    The size of the image should be 9x16"""

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

    FINAL RESULT MUST:
    • Preserve the hero from IMAGE 1 (face, pose, arena).
    • Apply Thunderstrike-style overlays and layout from IMAGE 2.
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

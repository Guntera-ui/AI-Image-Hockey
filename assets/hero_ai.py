import os
import uuid
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image
from google import genai
from google.genai import types

from config import MEDIA_DIR, HERO_MAX_TRIES, HERO_EARLY_ACCEPT,HERO_MIN_SHARPNESS

# =========================
# Gemini config
# =========================

MODEL_ID = "gemini-2.5-flash-image"
client = genai.Client()

# =========================
# InsightFace (lazy init)
# =========================

_face_app = None


def _get_face_app():
    """
    Initialize InsightFace once per process.
    CPU-only for maximum compatibility.
    """
    global _face_app
    if _face_app is not None:
        return _face_app

    from insightface.app import FaceAnalysis

    _face_app = FaceAnalysis(
        name="buffalo_l",
        providers=["CPUExecutionProvider"],
    )
    _face_app.prepare(ctx_id=-1, det_size=(640, 640))
    return _face_app


# =========================
# Helpers
# =========================

def _guess_mime_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
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


def _to_bgr_uint8(pil_img: Image.Image) -> np.ndarray:
    rgb = np.array(pil_img.convert("RGB"), dtype=np.uint8)
    return rgb[..., ::-1]  # RGB → BGR


def _largest_face_embedding(pil_img: Image.Image) -> Optional[np.ndarray]:
    app = _get_face_app()
    faces = app.get(_to_bgr_uint8(pil_img))
    if not faces:
        return None

    def area(f):
        x1, y1, x2, y2 = f.bbox
        return (x2 - x1) * (y2 - y1)

    face = max(faces, key=area)
    emb = getattr(face, "embedding", None)
    if emb is None:
        return None

    emb = np.asarray(emb, dtype=np.float32)
    norm = np.linalg.norm(emb)
    if norm < 1e-8:
        return None
    return emb / norm


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))  # both normalized


def _laplacian_var(pil_img: Image.Image) -> float:
    g = np.array(pil_img.convert("L"), dtype=np.float32)
    lap = (
        -4.0 * g
        + np.roll(g, 1, axis=0)
        + np.roll(g, -1, axis=0)
        + np.roll(g, 1, axis=1)
        + np.roll(g, -1, axis=1)
    )
    return float(lap.var())


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except Exception:
        return default


# =========================
# Gemini hero generation
# =========================

def _generate_hero_image_bytes(
    user_photo_path: Path,
    gender: Optional[str],
) -> bytes:
    image_part = types.Part.from_bytes(
        data=user_photo_path.read_bytes(),
        mime_type=_guess_mime_type(user_photo_path),
    )

    player_desc = _player_desc_from_gender(gender)

    prompt = f"""
IDENTITY LOCK (HIGHEST PRIORITY):
- The final player MUST be the SAME PERSON as the selfie.
- Preserve exact facial structure (eyes, eyebrows, nose, lips, jawline, cheekbones).
- Do NOT beautify or change the face.
- Do NOT change gender, age, or ethnicity.
- Face must remain SHARP (no blur, no heavy visor glare, no shadow covering the face).

TASK:
Convert the selfie into a hyper-realistic image of {player_desc}
skating aggressively toward the camera on a glossy ice rink.

UNIFORM (LOCK COLORS):
- Navy-base jersey, sky-blue stripes, subtle teal piping,
  minimal sand trim, bold neon-pink accents, white numbers.
- No third-party logos, no NHL branding, no extra text.

BACKGROUND:
Realistic ice hockey arena with cinematic neon lighting accents
(purple, magenta, electric blue) used ONLY as lighting.
Soft bloom, volumetric light rays, subtle lens flare.
NOT abstract. NOT sci-fi.

CAMERA:
- Mid-stride skating, knees bent, ice spray.
- Shallow depth of field: face sharp, background softened.
- Vertical 9:16.
"""

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=[image_part, prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="9:16"),
        ),
    )

    for p in response.candidates[0].content.parts:
        if getattr(p, "inline_data", None):
            return p.inline_data.data

    raise RuntimeError("Gemini did not return hero image")


# =========================
# PUBLIC API
# =========================

def generate_hero_from_photo(
    user_photo_path: Path,
    user_name: str,
    power_label: str,
    gender: Optional[str] = None,
) -> Path:
    """
    Best-of-N hero generation using InsightFace similarity.
    """

    MAX_TRIES = max(1, _env_int("HERO_MAX_TRIES", 4))
    EARLY_ACCEPT = _env_float("HERO_EARLY_ACCEPT", 0.42)
    MIN_SHARP = _env_float("HERO_MIN_SHARPNESS", 60.0)

    selfie_img = Image.open(user_photo_path)
    selfie_emb = _largest_face_embedding(selfie_img)

    # Fallback: no face detected in selfie
    if selfie_emb is None:
        img_bytes = _generate_hero_image_bytes(user_photo_path, gender)
        hero = Image.open(BytesIO(img_bytes)).convert("RGBA")
        out = MEDIA_DIR / f"hero_{uuid.uuid4().hex}.png"
        hero.save(out)
        return out

    best: Optional[Tuple[float, float, bytes]] = None

    for _ in range(MAX_TRIES):
        img_bytes = _generate_hero_image_bytes(user_photo_path, gender)
        hero_img = Image.open(BytesIO(img_bytes))

        hero_emb = _largest_face_embedding(hero_img)
        if hero_emb is None:
            continue

        sim = _cosine_sim(selfie_emb, hero_emb)
        sharp = _laplacian_var(hero_img)

        if sharp < MIN_SHARP and sim < EARLY_ACCEPT:
            continue

        if best is None or sim > best[0]:
            best = (sim, sharp, img_bytes)

        if sim >= EARLY_ACCEPT:
            break

    if best is None:
        img_bytes = _generate_hero_image_bytes(user_photo_path, gender)
        hero = Image.open(BytesIO(img_bytes)).convert("RGBA")
    else:
        hero = Image.open(BytesIO(best[2])).convert("RGBA")

    out = MEDIA_DIR / f"hero_{uuid.uuid4().hex}.png"
    hero.save(out)
    return out


def generate_full_card_from_hero(
    hero_image_path: Path,
    frame_style_path: Path,
    user_name: str,
    power_label: str,
) -> Path:
    """
    Final card generation (hero + Thunderstrike frame).
    """
    hero_part = types.Part.from_bytes(
        data=hero_image_path.read_bytes(),
        mime_type=_guess_mime_type(hero_image_path),
    )
    frame_part = types.Part.from_bytes(
        data=frame_style_path.read_bytes(),
        mime_type=_guess_mime_type(frame_style_path),
    )

    arc_text = f"{user_name.upper()} • {power_label.upper()}"

    prompt = f"""
STRICT COMPOSITING.

IMAGE 1 = HERO IMAGE.
IMAGE 2 = THUNDERSTRIKE TEMPLATE.

RULES:
- KEEP IMAGE 2 UNCHANGED (logos, borders, graphics).
- Use IMAGE 1 as full background + player filler.
- Do NOT modify player identity.

TEXT:
Replace ONLY the top arc text with:
"{arc_text}"

OUTPUT:
- IMAGE 2 unchanged with IMAGE 1 behind it.
- Vertical 9:16.
"""

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=[hero_part, frame_part, prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="9:16"),
        ),
    )

    for p in response.candidates[0].content.parts:
        if getattr(p, "inline_data", None):
            card = Image.open(BytesIO(p.inline_data.data)).convert("RGBA")
            out = MEDIA_DIR / f"card_{uuid.uuid4().hex}.png"
            card.save(out)
            return out

    raise RuntimeError("Gemini did not return card image")


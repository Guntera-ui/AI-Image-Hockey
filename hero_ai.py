import json
import os
import uuid
from dataclasses import dataclass, asdict
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

import numpy as np
from PIL import Image
from google import genai
from google.genai import types

from config import MEDIA_DIR

MODEL_ID = "gemini-2.5-flash-image"
client = genai.Client()

_face_app = None


# ----------------------------
# Config helpers (config.py OR env)
# ----------------------------
def _cfg(name: str, default):
    # Prefer config.py variables if added them there
    try:
        import config  #
        if hasattr(config, name):
            return getattr(config, name)
    except Exception:
        pass
    # Fallback to environment
    val = os.getenv(name)
    if val is None:
        return default
    # cast based on default type
    try:
        if isinstance(default, bool):
            return val.strip().lower() in ("1", "true", "yes", "y", "on")
        if isinstance(default, int):
            return int(val)
        if isinstance(default, float):
            return float(val)
        return val
    except Exception:
        return default


# ----------------------------
# InsightFace init (GPU optional)
# ----------------------------
def _get_face_app():
    """
    GPU if INSIGHTFACE_GPU=True (or env INSIGHTFACE_GPU=1) and CUDA provider is available.
    Falls back to CPU automatically.
    """
    global _face_app
    if _face_app is not None:
        return _face_app

    from insightface.app import FaceAnalysis

    use_gpu = bool(_cfg("INSIGHTFACE_GPU", False))

    if use_gpu:
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        ctx_id = 0
    else:
        providers = ["CPUExecutionProvider"]
        ctx_id = -1

    _face_app = FaceAnalysis(name="buffalo_l", providers=providers)
    _face_app.prepare(ctx_id=ctx_id, det_size=(640, 640))
    return _face_app


# ----------------------------
# Metrics
# ----------------------------
@dataclass
class HeroMetrics:
    tries: int
    selected_try_index: int
    best_similarity: float
    best_sharpness: float
    early_accept: float
    min_sharpness: float
    facefix_enabled: bool
    facefix_triggered: bool
    facefix_threshold: float
    facefix_similarity: Optional[float] = None
    selfie_face_detected: bool = True


def _metrics_path_for(hero_path: Path) -> Path:
    return hero_path.with_suffix(hero_path.suffix + ".metrics.json")


def _save_metrics(hero_path: Path, metrics: HeroMetrics) -> None:
    mp = _metrics_path_for(hero_path)
    mp.write_text(json.dumps(asdict(metrics), ensure_ascii=False, indent=2))


# ----------------------------
# Image helpers
# ----------------------------
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
    return rgb[..., ::-1]  # RGB -> BGR


def _largest_face_embedding(pil_img: Image.Image) -> Optional[np.ndarray]:
    app = _get_face_app()
    faces = app.get(_to_bgr_uint8(pil_img))
    if not faces:
        return None

    def area(f) -> float:
        x1, y1, x2, y2 = f.bbox
        return float(max(0, x2 - x1) * max(0, y2 - y1))

    face = max(faces, key=area)
    emb = getattr(face, "embedding", None)
    if emb is None:
        return None

    emb = np.asarray(emb, dtype=np.float32)
    n = float(np.linalg.norm(emb))
    if n < 1e-8:
        return None
    return emb / n


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


# ----------------------------
# Gemini generation
# ----------------------------
def _generate_hero_image_bytes(user_photo_path: Path, gender: Optional[str]) -> bytes:
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
- Face must remain SHARP and clearly visible:
  no motion blur on face, no heavy visor glare, no shadow covering the face.
- DO NOT REMOVE HOCKEY STICK PLAYER NEEDS IT
TASK:
Convert the selfie into a hyper-realistic image of {player_desc}
skating toward the camera on a glossy ice rink.

UNIFORM (LOCK COLORS):
- Navy-base jersey, sky-blue stripes, subtle teal piping,
  minimal sand trim, bold neon-pink accents, white numbers.
- No third-party logos, no NHL/team branding, no extra text.

BACKGROUND:
Realistic arena (crowd + boards) with promotional neon lighting accents
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
    
    # --- BEGIN DEFENSIVE GUARD ---
    if not response.candidates:
        raise RuntimeError("Gemini returned no candidates")

    candidate = response.candidates[0]

    if not candidate.content or not candidate.content.parts:
        raise RuntimeError(
            "Gemini returned empty content parts "
            f"(finish_reason={getattr(candidate, 'finish_reason', None)})"
        )
    # --- END DEFENSIVE GUARD ---


    for p in candidate.content.parts:
        if getattr(p, "inline_data", None):
            return p.inline_data.data

    raise RuntimeError("Gemini did not return hero image")


def _facefix_hero_image_bytes(
    selfie_path: Path,
    hero_candidate_bytes: bytes,
    gender: Optional[str],
) -> bytes:
    selfie_part = types.Part.from_bytes(
        data=selfie_path.read_bytes(),
        mime_type=_guess_mime_type(selfie_path),
    )
    hero_part = types.Part.from_bytes(
        data=hero_candidate_bytes,
        mime_type="image/png",
    )

    player_desc = _player_desc_from_gender(gender)

    prompt = f"""
FACE FIX REFINEMENT (STRICT):
- Output must stay almost identical to IMAGE 1 (hero candidate):
  same pose, same uniform colors, same background, same lighting, same composition.
- ONLY modify the FACE region so the identity matches IMAGE 2 (selfie).
- Preserve facial structure: eyes, brows, nose, lips, jawline, cheekbones.
- Do NOT change gender/age/ethnicity. The player is {player_desc}.
- Do NOT change helmet, hairline, jersey, or background.
- Keep face sharp and visible.

IMAGE 1: hero candidate (keep everything)
IMAGE 2: selfie (identity reference)
"""

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=[hero_part, selfie_part, prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="9:16"),
        ),
    )
    # --- BEGIN DEFENSIVE GUARD ---
    if not response.candidates:
        raise RuntimeError("Gemini returned no candidates (facefix)")

    candidate = response.candidates[0]

    if not candidate.content or not candidate.content.parts:
        raise RuntimeError(
            "Gemini returned empty content parts (facefix) "
            f"(finish_reason={getattr(candidate, 'finish_reason', None)})"
        )
    # --- END DEFENSIVE GUARD ---


    for p in candidate.content.parts:
        if getattr(p, "inline_data", None):
            return p.inline_data.data

    raise RuntimeError("Gemini did not return face-fix image")


# ----------------------------
# Public API
# ----------------------------
def generate_hero_from_photo(
    user_photo_path: Path,
    user_name: str,
    power_label: str,
    gender: Optional[str] = None,
) -> Path:
    """
    Best-of-N hero generation with InsightFace similarity + optional face-fix refinement.
    Saves a sidecar JSON metrics file next to the hero output.
    """

    max_tries = max(1, int(_cfg("HERO_MAX_TRIES", 4)))
    early_accept = float(_cfg("HERO_EARLY_ACCEPT", 0.48))          # raised default
    min_sharp = float(_cfg("HERO_MIN_SHARPNESS", 55.0))            # slightly lower
    facefix_enabled = bool(_cfg("HERO_FACEFIX_ENABLE", True))
    facefix_threshold = float(_cfg("HERO_FACEFIX_THRESHOLD", 0.44))  # raised default

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    selfie_img = Image.open(user_photo_path)
    selfie_emb = _largest_face_embedding(selfie_img)

    # If selfie face detection fails, fallback to single generation (still returns a hero)
    if selfie_emb is None:
        img_bytes = _generate_hero_image_bytes(user_photo_path, gender)
        hero = Image.open(BytesIO(img_bytes)).convert("RGBA")
        out = MEDIA_DIR / f"hero_{uuid.uuid4().hex}.png"
        hero.save(out)

        metrics = HeroMetrics(
            tries=1,
            selected_try_index=1,
            best_similarity=0.0,
            best_sharpness=_laplacian_var(hero),
            early_accept=early_accept,
            min_sharpness=min_sharp,
            facefix_enabled=facefix_enabled,
            facefix_triggered=False,
            facefix_threshold=facefix_threshold,
            selfie_face_detected=False,
        )
        _save_metrics(out, metrics)
        return out

    best: Optional[Tuple[float, float, bytes, int]] = None  # sim, sharp, bytes, try_index

    for i in range(1, max_tries + 1):
        img_bytes = _generate_hero_image_bytes(user_photo_path, gender)
        hero_img = Image.open(BytesIO(img_bytes))

        hero_emb = _largest_face_embedding(hero_img)
        if hero_emb is None:
            continue

        sim = _cosine_sim(selfie_emb, hero_emb)
        sharp = _laplacian_var(hero_img)

        # Drop very blurry candidates unless similarity is already strong
        if sharp < min_sharp and sim < early_accept:
            continue

        if best is None or sim > best[0] or (sim == best[0] and sharp > best[1]):
            best = (sim, sharp, img_bytes, i)

        if sim >= early_accept:
            break

    # If everything failed (rare), do one last output
    if best is None:
        img_bytes = _generate_hero_image_bytes(user_photo_path, gender)
        hero = Image.open(BytesIO(img_bytes)).convert("RGBA")
        out = MEDIA_DIR / f"hero_{uuid.uuid4().hex}.png"
        hero.save(out)

        metrics = HeroMetrics(
            tries=max_tries,
            selected_try_index=0,
            best_similarity=0.0,
            best_sharpness=_laplacian_var(hero),
            early_accept=early_accept,
            min_sharpness=min_sharp,
            facefix_enabled=facefix_enabled,
            facefix_triggered=False,
            facefix_threshold=facefix_threshold,
        )
        _save_metrics(out, metrics)
        return out

    best_sim, best_sharp, best_bytes, best_i = best
    facefix_triggered = False
    facefix_sim: Optional[float] = None

    # Face-fix rescue if best similarity is still below threshold
    if facefix_enabled and best_sim < facefix_threshold:
        facefix_triggered = True
        fixed_bytes = _facefix_hero_image_bytes(
            selfie_path=user_photo_path,
            hero_candidate_bytes=best_bytes,
            gender=gender,
        )

        fixed_img = Image.open(BytesIO(fixed_bytes))
        fixed_emb = _largest_face_embedding(fixed_img)
        if fixed_emb is not None:
            facefix_sim = _cosine_sim(selfie_emb, fixed_emb)
            # Keep the fixed result only if it improves or matches
            if facefix_sim >= best_sim:
                best_bytes = fixed_bytes
                best_sim = facefix_sim

    hero = Image.open(BytesIO(best_bytes)).convert("RGBA")
    out = MEDIA_DIR / f"hero_{uuid.uuid4().hex}.png"
    hero.save(out)

    metrics = HeroMetrics(
        tries=max_tries,
        selected_try_index=best_i,
        best_similarity=float(best_sim),
        best_sharpness=float(best_sharp),
        early_accept=float(early_accept),
        min_sharpness=float(min_sharp),
        facefix_enabled=bool(facefix_enabled),
        facefix_triggered=bool(facefix_triggered),
        facefix_threshold=float(facefix_threshold),
        facefix_similarity=float(facefix_sim) if facefix_sim is not None else None,
    )
    _save_metrics(out, metrics)
    print(f"[hero_ai] best_sim={best_sim:.3f} try={best_i}/{max_tries} facefix={facefix_triggered} facefix_sim={facefix_sim}")

    return out


def generate_full_card_from_hero(
    hero_image_path: Path,
    frame_style_path: Path,
    user_name: str,
    power_label: str,
) -> Path:
    """
    Gemini composites hero + frame (frame stays unchanged, hero is filler behind).
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

IMAGE 1 = HERO IMAGE (player + background).
IMAGE 2 = THUNDERSTRIKE TEMPLATE (frame).

RULES:
- KEEP IMAGE 2 UNCHANGED (all logos, borders, graphics).
- Use IMAGE 1 as the full filler behind the frame.
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
    # --- BEGIN DEFENSIVE GUARD ---
    if not response.candidates:
        raise RuntimeError("Gemini returned no candidates (card)")

    candidate = response.candidates[0]

    if not candidate.content or not candidate.content.parts:
        raise RuntimeError(
            "Gemini returned empty content parts (card) "
            f"(finish_reason={getattr(candidate, 'finish_reason', None)})"
        )
    # --- END DEFENSIVE GUARD ---


    for p in candidate.content.parts:
        if getattr(p, "inline_data", None):
            card = Image.open(BytesIO(p.inline_data.data)).convert("RGBA")
            out = MEDIA_DIR / f"card_{uuid.uuid4().hex}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            card.save(out)
            return out

    raise RuntimeError("Gemini did not return card image")


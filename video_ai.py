import uuid
from pathlib import Path
from typing import Optional, Union, Any

import requests

from config import MEDIA_DIR, FAL_KEY, FAL_VIDEO_MODEL_ID

try:
    from fal_client import SyncClient
except ImportError as e:
    raise ImportError("Missing dependency. Run: pip install fal-client requests") from e


def _require(value: Optional[str], name: str) -> str:
    if not value:
        raise RuntimeError(f"Missing {name}. Check your .env and config.py.")
    return value


def _extract_video_url(payload: Any) -> str:
    """
    Common fal response shapes:
      {"video": {"url": "..."}}
      {"video_url": "..."}
      {"videos": [{"url": "..."}]}
    """
    if isinstance(payload, dict):
        v = payload.get("video")
        if isinstance(v, dict) and isinstance(v.get("url"), str):
            return v["url"]
        if isinstance(payload.get("video_url"), str):
            return payload["video_url"]
        vids = payload.get("videos")
        if isinstance(vids, list) and vids:
            first = vids[0]
            if isinstance(first, dict) and isinstance(first.get("url"), str):
                return first["url"]
            if isinstance(first, str) and first.startswith("http"):
                return first
        if isinstance(payload.get("url"), str) and payload["url"].startswith("http"):
            return payload["url"]

    if isinstance(payload, str) and payload.startswith("http"):
        return payload

    raise RuntimeError(f"Could not extract video URL from fal response: {payload}")


def generate_hockey_video_from_hero(
    hero_image_path: Union[str, Path],
    gender: Optional[str] = None,
) -> Path:
    """
    fal image-to-video generation using ONLY FAL_KEY + FAL_VIDEO_MODEL_ID from config.py.
    No extra knobs passed (duration/aspect/resolution/etc).
    """
    hero_image_path = Path(hero_image_path)
    if not hero_image_path.exists():
        raise FileNotFoundError(f"Hero image not found: {hero_image_path}")

    fal_key = _require(FAL_KEY, "FAL_KEY")
    model_id = _require(FAL_VIDEO_MODEL_ID, "FAL_VIDEO_MODEL_ID")

    # Optional gender lock (since you have the field already)
    if gender and gender.lower() == "female":
        gender_line = "The player is female."
    elif gender and gender.lower() == "male":
        gender_line = "The player is male."
    else:
        gender_line = "The player is the same person as in the reference image."

    # Integrated prompt (WAN 2.5 Fast style) + identity + 9:16 + 5 seconds
    prompt = f"""
VIDEO: (WAN 2.5 Fast) (Enhance ON)
Generate a 5-second ultra-realistic, slow-motion cinematic video of a professional ice hockey player executing a powerful slap shot on an illuminated rink.
{gender_line}

IDENTITY / CONSISTENCY (CRITICAL):
- The player must be the SAME PERSON as in the reference image.
- Preserve the same uniform colors, same lighting direction, and same realistic texture and equipment details.

ACTION:
Begin with the player gliding forward, knees bent, eyes locked on the puck.
As the motion progresses, the player winds up the stick, flexing it naturally under pressure, then strikes the puck with full force.
The puck launches forward at high speed, creating a trail of ice particles and subtle motion blur, while the stick follows through dynamically.
The camera tracks the player in a smooth handheld-style movement, slightly orbiting to the left to emphasize depth and power.

ENVIRONMENT / LIGHTING:
Stylized ice arena filled with cinematic colored lights — vibrant electric blue, magenta, and violet beams radiate behind the player.
These beams interact with mist and airborne ice dust, producing volumetric light rays and soft lens flares.
The ice surface reflects the colors vividly, showing shimmering highlights and skate reflections.

DETAILS:
Capture cloth folds, skate blade glint, micro-scratches on the stick, visible breath vapor,
and dynamic reflections across the visor and rink. Include fog diffusion, soft focus on the background,
and HDR lighting contrast to make the player pop against the glowing scene.

IMPACT:
As the shot connects, add a burst of confetti-like ice shards and a slight camera shake.
End with the puck streaking offscreen and the player holding the finishing pose, breathing heavily, under the glowing lights.

STYLE:
High-speed broadcast replay — cinematic slow motion at 120 fps look, depth-of-field focus on the player,
realistic motion blur, reflections, and particles.

Technical/Stylistic Tags:
hyper-realistic, HDR, cinematic lighting, volumetric fog, photoreal textures, motion-tracked camera,
slow-motion 120 fps replay, depth of field, shallow focus, handheld tracking, dynamic motion blur,
energy burst, dramatic color grading, physically based rendering, reflective ice surface,
particle simulation, lens flare, arena spotlight beams, emotional sports cinematography.

Aspect ratio: 9:16.
""".strip()

    client = SyncClient(key=fal_key)

    # Upload local image so fal can access it
    image_url = client.upload_file(str(hero_image_path))

    # ONLY required fields: prompt + image_url
    result = client.subscribe(
        model_id,
        {
            "prompt": prompt,
            "image_url": image_url,
        },
        with_logs=False,
    )

    data = result.get("data", result)
    video_url = _extract_video_url(data)

    videos_dir = MEDIA_DIR / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    out_path = videos_dir / f"hockey_{uuid.uuid4().hex}.mp4"

    r = requests.get(video_url, timeout=600)
    r.raise_for_status()
    out_path.write_bytes(r.content)

    print(f"[video_ai] Saved video to: {out_path}")
    return out_path


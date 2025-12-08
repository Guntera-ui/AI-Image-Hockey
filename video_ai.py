# video_ai.py

import time
import uuid
from pathlib import Path
from typing import Optional, Union

from google import genai
from google.genai import types

from config import MEDIA_DIR

# Use the model you told me: veo-3.1-fast-generate-preview
VEO_MODEL_ID = "veo-3.1-fast-generate-preview"

# Uses GOOGLE_GEMINI_API_KEY / GEMINI_API_KEY from env
client = genai.Client()


def generate_hockey_video_from_hero(
    hero_image_path: Union[str, Path],
    gender: Optional[str] = None,
) -> Path:
    """
    Generate a short Veo hockey video using the already-generated hero PNG.

    Args:
        hero_image_path: local path to hero image (PNG) on disk.
        gender: optional "male"/"female" to slightly tweak the prompt.

    Returns:
        Path to the saved MP4 video file.
    """
    hero_image_path = Path(hero_image_path)

    if not hero_image_path.exists():
        raise FileNotFoundError(f"Hero image not found: {hero_image_path}")

    # --- Build the prompt -------------------------------------------------
    # Keep it pretty generic and let the hero image drive appearance.
    if gender and gender.lower() == "female":
        player_desc = "a professional female ice hockey player"
    elif gender and gender.lower() == "male":
        player_desc = "a professional male ice hockey player"
    else:
        player_desc = "a professional ice hockey player"

    prompt = f"""
    Cinematic 8-second highlight of {player_desc} skating dynamically forward on an ice rink.
    The player is handling a puck with intensity, creating ice spray and shavings.
    Crucial detail: The player wears a jersey featuring a clear, static, and legible 'Jersey Mike's' logo on the center chest that does not distort.
    The camera follows low and close in a tracking shot, capturing the reflection on the ice and the bright purple and blue stadium spotlights in the blurred background.
    High-definition sports cinematography, photorealistic texture, stable, Eyes should be focused on the puck.

    Cinematography:
    Lens: 35mm-balanced
    Lighting: neon-colorful-reflections
    Mood: epic-grand-awe-inspiring

    Technical Parameters:
        Production Level: Cinematic
        Pacing: Moderate

    Audio:
    Audio Volume: medium
    """
    hero_image = types.Image.from_file(location=str(hero_image_path))

    # --- Kick off Veo video generation ------------------------------------
    operation = client.models.generate_videos(
        model=VEO_MODEL_ID,
        prompt=prompt,
        image=hero_image,
        config=types.GenerateVideosConfig(
            aspect_ratio="9:16",
            resolution="720p",
            duration_seconds=8,
            number_of_videos=1,
        ),
    )

    # --- Poll until done ---------------------------------------------------
    print("[video_ai] Waiting for Veo video...")
    while not operation.done:
        time.sleep(8)
        operation = client.operations.get(operation)

    # Safety check
    if not getattr(operation, "result", None) or not operation.result.generated_videos:
        raise RuntimeError("Veo returned no video")

    video_obj = operation.result.generated_videos[0]

    # Download the actual bytes
    client.files.download(file=video_obj.video)

    videos_dir = MEDIA_DIR / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    out_path = videos_dir / f"hockey_{uuid.uuid4().hex}.mp4"
    video_obj.video.save(out_path)

    print(f"[video_ai] Saved video to: {out_path}")
    return out_path

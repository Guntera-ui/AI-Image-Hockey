import time
import uuid
from pathlib import Path

from google import genai
from google.genai import types

from config import MEDIA_DIR

# Adjust model name if you're on 3.0 vs 3.1
VEO_MODEL_ID = (
    "veo-3.1-fast-generate-preview"  # or "veo-3.0-..." if that's what your plan uses
)

client = genai.Client()  # uses GEMINI_API_KEY env var


def generate_hockey_video_from_hero(
    hero_image_path: Path,
    user_name: str,
    gender: str,
    length_seconds: int = 8,
) -> Path:
    """
    Use Veo to generate a short hockey clip based on the hero image.

    hero_image_path: local path to the hero (arena + player) image.
    user_name: player's name (just for flavor in the prompt).
    gender: "male"/"female"/etc. for pose/physique hints.
    length_seconds: 5–9 seconds, Veo will pick closest supported length.

    Returns: local Path to the generated MP4 file.
    """
    if not hero_image_path.exists():
        raise FileNotFoundError(f"Hero image not found: {hero_image_path}")

    hero_bytes = hero_image_path.read_bytes()

    # Veo can be guided with reference images – we use the hero image for that.
    reference_image = types.Part.from_bytes(
        data=hero_bytes,
        mime_type="image/png",  # or "image/jpeg" depending on your hero file
    )

    prompt = f"""
    A dynamic broadcast-style ice hockey shot featuring the same player as in the reference image.
    Show a professional hockey player skating fast and taking a powerful shot on goal.

    Requirements:
    - Use the same face, hairstyle and jersey colors as in the reference image.
    - Camera: cinematic tracking and slight slow-motion feel, like an NHL highlight.
    - Duration: about {length_seconds} seconds.
    - Aspect ratio: 9:16 vertical, suitable for mobile.
    - Keep the action centered on the player; do not cut away to other people.
    - Arena lighting: bright stadium lights, visible crowd but softly blurred.
    - Overall mood: high-energy, exciting sports highlight.
    """

    operation = client.models.generate_videos(
        model=VEO_MODEL_ID,
        prompt=prompt,
        # Depending on SDK version this config signature may differ slightly.
        config=types.GenerateVideosConfig(
            reference_images=[reference_image],
            aspect_ratio="9:16",
            length_seconds=length_seconds,
        ),
    )

    # Poll until video is ready
    while not operation.done:
        print("[video_ai] Waiting for Veo video generation...")
        time.sleep(8)
        operation = client.operations.get(operation)

    if not operation.response or not operation.response.generated_videos:
        raise RuntimeError("Veo did not return a generated video")

    video_obj = operation.response.generated_videos[0]

    # Download via google-genai files API
    dl = client.files.download(file=video_obj.video)

    videos_dir = MEDIA_DIR / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    out_path = videos_dir / f"hockey_{uuid.uuid4().hex}.mp4"
    with open(out_path, "wb") as f:
        # `dl.read()` or `video_obj.video.read()` depending on SDK version –
        # adjust if IDE complains.
        f.write(dl.read())

    print(f"[video_ai] Saved Veo video to: {out_path}")
    return out_path

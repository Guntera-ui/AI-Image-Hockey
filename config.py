"""
Global configuration for the AI Hockey Image project.

Loads secrets from .env (EMAIL_*, GEMINI_API_KEY, FIREBASE_STORAGE_BUCKET),
and defines paths used across the app.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(exist_ok=True)


SERVICE_ACCOUNT_PATH = BASE_DIR / "firebase-key.json"


FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET")

EMAIL_SMTP_HOST = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM", EMAIL_USERNAME or "no-reply@example.com")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

FAL_KEY = os.getenv("FAL_KEY")
FAL_VIDEO_MODEL_ID = os.getenv("FAL_VIDEO_MODEL_ID")


EMAIL_BRAND_LOGO_URL = os.getenv("EMAIL_BRAND_LOGO_URL")


# ----------------------------
# Video overlay assets
# ----------------------------
# Place these files under ./assets/overlays/ to match defaults below.

VIDEO_OVERLAY_FRAME_PATH = Path(
    os.getenv(
        "VIDEO_OVERLAY_FRAME_PATH",
        str(BASE_DIR / "assets" / "overlays" / "frame_reference.png"),
    )
)

VIDEO_OVERLAY_FONT_NAME_PATH = Path(
    os.getenv(
        "VIDEO_OVERLAY_FONT_NAME_PATH",
        str(BASE_DIR / "assets" / "overlays" / "fonts" / "Montserrat-SemiBold.ttf"),
    )
)

VIDEO_OVERLAY_FONT_SHOT_PATH = Path(
    os.getenv(
        "VIDEO_OVERLAY_FONT_SHOT_PATH",
        str(BASE_DIR / "assets" / "overlays" / "fonts" / "Montserrat-Bold.ttf"),
    )
)

# Your requirement: hole alpha must be <= 20 to be detected.
VIDEO_OVERLAY_HOLE_ALPHA_MAX = int(os.getenv("VIDEO_OVERLAY_HOLE_ALPHA_MAX", "20"))


# ----------------------------
# Listener / pipeline safety
# ----------------------------

# How long before another worker can steal a stuck lock.
LOCK_TTL_SECONDS = int(os.getenv("LOCK_TTL_SECONDS", "900"))  # 15 minutes



# Lazzy checker values
#
HERO_MAX_TRIES=4
HERO_EARLY_ACCEPT=0.42
HERO_MIN_SHARPNESS=60

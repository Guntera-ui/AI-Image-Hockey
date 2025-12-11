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


EMAIL_BRAND_LOGO_URL = os.getenv("EMAIL_BRAND_LOGO_URL")

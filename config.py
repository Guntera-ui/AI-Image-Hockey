# config.py
from pathlib import Path

# Base project directory (where this file lives)
BASE_DIR = Path(__file__).resolve().parent

# Folders for outputs
MEDIA_DIR = BASE_DIR / "media"
QR_DIR = BASE_DIR / "qr_codes"

# Make sure folders exist
MEDIA_DIR.mkdir(exist_ok=True)
QR_DIR.mkdir(exist_ok=True)

# Firebase service account JSON (you already downloaded this)
SERVICE_ACCOUNT_PATH = BASE_DIR / "firebase-key.json"

# Your actual bucket name from Firebase Storage
FIREBASE_STORAGE_BUCKET = "ai-image-app-e900c.firebasestorage.app"


from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

MEDIA_DIR = BASE_DIR / "media"
QR_DIR = BASE_DIR / "qr_codes"

MEDIA_DIR.mkdir(exist_ok=True)
QR_DIR.mkdir(exist_ok=True)


SERVICE_ACCOUNT_PATH = BASE_DIR / "firebase-key.json"


FIREBASE_STORAGE_BUCKET = "ai-image-app-e900c.firebasestorage.app"

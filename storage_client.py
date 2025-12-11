from pathlib import Path

import firebase_admin
import requests
from firebase_admin import credentials
from firebase_admin import storage as fb_storage

from config import FIREBASE_STORAGE_BUCKET, MEDIA_DIR, SERVICE_ACCOUNT_PATH

if not firebase_admin._apps:
    cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
    firebase_admin.initialize_app(cred, {"storageBucket": FIREBASE_STORAGE_BUCKET})

bucket = fb_storage.bucket()


def upload_to_firebase(processed_path: Path) -> str:
    """
    Upload a generated image file to Firebase Storage under /processed.
    Returns a public HTTPS URL.
    """
    blob_path = f"processed/{processed_path.name}"
    blob = bucket.blob(blob_path)
    blob.upload_from_filename(str(processed_path))
    blob.make_public()
    return blob.public_url


def download_blob_to_temp(blob_path: str) -> Path:
    """
    Download from a Storage blob path (e.g. 'selfies/xyz.jpg')
    into MEDIA_DIR and return the local Path.
    """
    filename = Path(blob_path).name
    local_path = MEDIA_DIR / filename

    blob = bucket.blob(blob_path)
    blob.download_to_filename(str(local_path))

    return local_path


def download_url_to_temp(public_url: str) -> Path:
    """
    Download any public Firebase Storage URL (or any HTTPS URL)
    into MEDIA_DIR and return the local Path.

    Works with:
    - https://firebasestorage.googleapis.com/...
    - https://storage.googleapis.com/<bucket>/processed/...
    """
    response = requests.get(public_url)
    response.raise_for_status()

    filename = public_url.split("/")[-1].split("?")[0] or "downloaded"
    local_path = MEDIA_DIR / filename

    with open(local_path, "wb") as f:
        f.write(response.content)

    return local_path


def upload_video_to_firebase(video_path: Path) -> str:
    """
    Upload a generated video file to Firebase Storage under /videos.
    Returns a public HTTPS URL.
    """
    blob_path = f"videos/{video_path.name}"
    blob = bucket.blob(blob_path)
    blob.upload_from_filename(str(video_path))
    blob.make_public()
    return blob.public_url

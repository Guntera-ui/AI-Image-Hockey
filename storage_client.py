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
    return upload_file_to_firebase(processed_path, prefix="processed")


def upload_file_to_firebase(local_path: Path, prefix: str) -> str:
    """
    Generic uploader for any file.
    Uploads to gs://<bucket>/<prefix>/<filename> and returns a public URL.
    """
    local_path = Path(local_path)
    blob_path = f"{prefix}/{local_path.name}"
    blob = bucket.blob(blob_path)
    blob.upload_from_filename(str(local_path))
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
    Download any public HTTPS URL into MEDIA_DIR and return the local Path.
    Works with Firebase Storage public URLs too.
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
    Upload a branded/final video under /videos.
    """
    return upload_file_to_firebase(Path(video_path), prefix="videos")


def upload_raw_video_to_firebase(video_path: Path) -> str:
    """
    Upload the *raw* (pre-overlay) video under /videos_raw.
    NOTE: In the updated listener, this is only used on failures (Option A).
    """
    return upload_file_to_firebase(Path(video_path), prefix="videos_raw")


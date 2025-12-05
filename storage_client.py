# storage_client.py
from pathlib import Path
from urllib.parse import unquote, urlparse

import firebase_admin
from firebase_admin import credentials
from firebase_admin import storage as fb_storage

from config import FIREBASE_STORAGE_BUCKET, MEDIA_DIR, SERVICE_ACCOUNT_PATH

if not firebase_admin._apps:
    cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
    firebase_admin.initialize_app(cred, {"storageBucket": FIREBASE_STORAGE_BUCKET})

bucket = fb_storage.bucket()


def upload_to_firebase(processed_path: Path) -> str:
    """
    Upload the processed image file to Firebase Storage under /processed.
    Returns a public HTTPS URL.
    """
    blob_path = f"processed/{processed_path.name}"
    blob = bucket.blob(blob_path)
    blob.upload_from_filename(str(processed_path))
    blob.make_public()
    return blob.public_url


def _blob_path_from_url(public_url: str) -> str:
    """
    Convert a Firebase public download URL to a blob path inside the bucket.
    Example URL:
      https://firebasestorage.googleapis.com/v0/b/<bucket>/o/selfies%2Ffoo%40bar.com.jpg?alt=media&token=...
    We want:
      selfies/foo@bar.com.jpg
    """
    parsed = urlparse(public_url)
    pieces = parsed.path.split("/o/")
    if len(pieces) != 2:
        raise ValueError(f"Cannot parse blob path from URL: {public_url}")

    encoded = pieces[1]
    blob_path = unquote(encoded)
    return blob_path


def download_blob_to_temp(blob_path: str) -> Path:
    """
    Download a file from Firebase Storage to MEDIA_DIR, returning the local Path.
    blob_path example: 'selfies/somefile.jpg'
    """
    filename = Path(blob_path).name
    local_path = MEDIA_DIR / filename

    blob = bucket.blob(blob_path)
    blob.download_to_filename(str(local_path))

    return local_path


def download_url_to_temp(public_url: str) -> Path:
    """
    Download from a Firebase public URL into MEDIA_DIR, returning the local Path.
    """
    blob_path = _blob_path_from_url(public_url)
    return download_blob_to_temp(blob_path)

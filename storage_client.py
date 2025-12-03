# storage_client.py
from pathlib import Path

import firebase_admin
from firebase_admin import credentials
from firebase_admin import storage as fb_storage

from config import FIREBASE_STORAGE_BUCKET, SERVICE_ACCOUNT_PATH

if not firebase_admin._apps:
    cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
    firebase_admin.initialize_app(cred, {"storageBucket": FIREBASE_STORAGE_BUCKET})

bucket = fb_storage.bucket()


def upload_to_firebase(processed_path: Path) -> str:
    """
    Upload the processed image file to Firebase Storage.
    Returns a public HTTPS URL that we can put into a QR code.
    """

    blob_path = f"processed/{processed_path.name}"
    blob = bucket.blob(blob_path)

    blob.upload_from_filename(str(processed_path))

    blob.make_public()

    return blob.public_url

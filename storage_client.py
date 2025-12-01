# storage_client.py
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, storage as fb_storage

from config import SERVICE_ACCOUNT_PATH, FIREBASE_STORAGE_BUCKET


# Initialize Firebase Admin SDK once
if not firebase_admin._apps:
    cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
    firebase_admin.initialize_app(cred, {
        "storageBucket": FIREBASE_STORAGE_BUCKET
    })

bucket = fb_storage.bucket()


def upload_to_firebase(processed_path: Path) -> str:
    """
    Upload the processed image file to Firebase Storage.
    Returns a public HTTPS URL that we can put into a QR code.
    """
    # We'll keep files under 'processed/' folder in the bucket
    blob_path = f"processed/{processed_path.name}"
    blob = bucket.blob(blob_path)

    # Upload the local file
    blob.upload_from_filename(str(processed_path))

    # Make the file publicly readable (simple approach for now)
    blob.make_public()

    # This is the HTTPS URL you can open from anywhere
    return blob.public_url


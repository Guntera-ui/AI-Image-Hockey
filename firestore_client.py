from pathlib import Path
from typing import Any, Dict

import firebase_admin
from firebase_admin import credentials, firestore

from config import SERVICE_ACCOUNT_PATH

if not firebase_admin._apps:
    cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
    firebase_admin.initialize_app(cred)

db = firestore.client()


def get_player_data(email: str) -> Dict[str, Any]:
    """
    Load player doc from Firestore.
    Collection name from your screenshot: 'players'
    Document ID = email.
    """
    ref = db.collection("players").document(email)
    doc = ref.get()

    if not doc.exists:
        raise ValueError(f"Player document not found: {email}")

    return doc.to_dict()


def update_player_with_card(
    email: str,
    hero_url: str,
    card_url: str,
):
    """
    Write the final image URLs back to the same Firestore document.
    """
    ref = db.collection("players").document(email)
    ref.set(
        {
            "heroURL": hero_url,
            "cardURL": card_url,
        },
        merge=True,
    )


def upload_video_to_firebase(video_path: Path) -> str:
    """
    Upload the generated video file to Firebase Storage.
    Returns a public HTTPS URL.
    """
    blob_path = f"videos/{video_path.name}"
    blob = bucket.blob(blob_path)
    blob.upload_from_filename(str(video_path))
    blob.make_public()
    return blob.public_url

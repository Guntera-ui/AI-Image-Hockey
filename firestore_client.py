# firestore_client.py
from typing import Any, Dict

import firebase_admin
from firebase_admin import credentials, firestore

from config import SERVICE_ACCOUNT_PATH  # already exists in config.py  :contentReference[oaicite:3]{index=3}


# Init Firestore once
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
        merge=True,  # keep existing fields
    )

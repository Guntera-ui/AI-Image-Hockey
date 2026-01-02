from __future__ import annotations

from typing import Any, Dict, Optional

import firebase_admin
from firebase_admin import credentials, firestore

from config import SERVICE_ACCOUNT_PATH


# ----------------------------
# Firebase init (singleton)
# ----------------------------
if not firebase_admin._apps:
    cred = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
    firebase_admin.initialize_app(cred)

db = firestore.client()


# ----------------------------
# Basic helpers
# ----------------------------

def get_player_ref(player_id: str) -> firestore.DocumentReference:
    """Return reference to players/{player_id}."""
    return db.collection("players").document(player_id)


def get_player_doc(player_id: str) -> Dict[str, Any]:
    """Fetch players/{player_id} as a dict."""
    ref = get_player_ref(player_id)
    snap = ref.get()
    if not snap.exists:
        raise ValueError(f"Player document not found: {player_id}")
    return snap.to_dict() or {}


def update_player_fields(player_id: str, fields: Dict[str, Any]) -> None:
    """Merge-update players/{player_id}."""
    if not fields:
        return
    get_player_ref(player_id).set(fields, merge=True)


def delete_player_fields(player_id: str, *field_names: str) -> None:
    """Delete specific fields from players/{player_id}."""
    if not field_names:
        return
    updates = {name: firestore.DELETE_FIELD for name in field_names}
    get_player_ref(player_id).set(updates, merge=True)


# ----------------------------
# Convenience utilities
# ----------------------------

def find_player_by_email(email: str) -> Optional[str]:
    """
    Find a player document ID by email.
    Returns doc ID or None.
    """
    q = (
        db.collection("players")
        .where("email", "==", email)
        .limit(1)
        .stream()
    )
    for snap in q:
        return snap.id
    return None


def mark_player_status(player_id: str, status: str, message: Optional[str] = None) -> None:
    """
    Update status and optional human-readable statusMessage.
    Useful for admin tools / CLI.
    """
    data = {"status": status}
    if message:
        data["statusMessage"] = message
    update_player_fields(player_id, data)


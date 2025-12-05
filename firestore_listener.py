# firestore_listener.py

import time
from typing import Any, Dict

from google.cloud import firestore as gc_firestore
from google.oauth2 import service_account

from config import SERVICE_ACCOUNT_PATH
from main import run_player_pipeline_from_storage_url

_initialized = False


def init_firestore():
    """
    Initialize Firestore using your service account JSON
    via google.cloud.firestore with explicit credentials.
    """
    print(f"[listener] Using service account at: {SERVICE_ACCOUNT_PATH}")

    creds = service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_PATH)
    )

    project_id = creds.project_id
    print(f"[listener] Firestore project_id: {project_id}")

    db = gc_firestore.Client(project=project_id, credentials=creds)
    return db


def handle_player_change(doc_snapshot, changes, read_time):
    """
    Callback any time something in players/ changes.

    - Ignore initial snapshot of existing docs.
    - After that, react to ADDED and MODIFIED.
    - Ignore REMOVED.
    - Only run AI when:
        * selfieURL, firstName, gender exist
        * selfieUploadedAt exists (means upload+confirm done)
        * cardURL is NOT set yet
    """
    global _initialized

    if not _initialized:
        _initialized = True
        print(
            f"\n[listener] Initial snapshot received with "
            f"{len(doc_snapshot)} docs. Ignoring existing players."
        )
        return

    print(f"\n[listener] Snapshot at {read_time}, {len(changes)} change(s)")

    for change in changes:
        doc = change.document
        data: Dict[str, Any] = doc.to_dict()
        doc_id = doc.id

        change_type = change.type.name
        print(f"[listener] Change type: {change_type} on players/{doc_id}")
        print(f"[listener] Full data: {data}")

        if change_type == "REMOVED":
            print("[listener] -> REMOVED change, ignoring.")
            continue

        selfie_url = data.get("selfieUrl")
        first_name = data.get("firstName")
        last_name = data.get("lastName", "")
        gender = data.get("gender")
        card_url = data.get("cardURL")
        selfie_uploaded_at = data.get("selfieUploadedAt")

        print(f"[listener] selfieURL        = {selfie_url}")
        print(f"[listener] firstName        = {first_name}")
        print(f"[listener] lastName         = {last_name}")
        print(f"[listener] gender           = {gender}")
        print(f"[listener] cardURL          = {card_url}")
        print(f"[listener] selfieUploadedAt = {selfie_uploaded_at}")

        if card_url:
            print("[listener] -> cardURL already exists, skipping generation.")
            continue

        if not selfie_uploaded_at:
            print("[listener] -> selfieUploadedAt is not set yet, skipping.")
            continue

        if not selfie_url:
            print("[listener] -> Missing selfieURL, skipping.")
            continue
        if not first_name:
            print("[listener] -> Missing firstName, skipping.")
            continue
        if not gender:
            print("[listener] -> Missing gender, skipping.")
            continue

        print(
            "[listener] ✅ All conditions satisfied (upload+confirm done). Running AI pipeline..."
        )

        try:
            result = run_player_pipeline_from_storage_url(
                selfie_url=selfie_url,
                first_name=first_name,
                last_name=last_name or "",
                gender=gender,
            )

            hero_url = result["hero_url"]
            card_url = result["card_url"]

            print(f"[listener] AI finished. hero_url={hero_url}")
            print(f"[listener] AI finished. card_url={card_url}")

            doc.reference.set(
                {
                    "heroURL": hero_url,
                    "cardURL": card_url,
                    "status": "done",
                },
                merge=True,
            )
            print("[listener] Firestore updated with heroURL + cardURL + status=done")

        except Exception as e:
            print(f"[listener] ❌ ERROR while running pipeline: {e}")
            doc.reference.set(
                {
                    "status": "error",
                    "errorMessage": str(e),
                },
                merge=True,
            )


def start_listener():
    db = init_firestore()

    players_ref = db.collection("players")

    print("[listener] Starting Firestore listener on collection: players")
    query_watch = players_ref.on_snapshot(handle_player_change)

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n[listener] Stopping listener.")
        query_watch.unsubscribe()


if __name__ == "__main__":
    start_listener()

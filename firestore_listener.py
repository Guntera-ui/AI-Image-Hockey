# firestore_listener.py

import time
from typing import Any, Dict

from google.cloud import firestore as gc_firestore
from google.oauth2 import service_account

from config import SERVICE_ACCOUNT_PATH
from player_pipeline import run_player_pipeline_from_storage_url
from storage_client import download_url_to_temp, upload_video_to_firebase
from video_ai import generate_hockey_video_from_hero

_initialized = False


def init_firestore() -> gc_firestore.Client:
    """
    Initialize Firestore using the service-account JSON.
    This is the pattern that worked for you before (option B).
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

    PHASE 1 (image):
      - selfieUrl, firstName, gender filled
      - selfieUploadedAt set
      - cardURL is missing
      -> run hero/card pipeline, write heroURL + cardURL + status="done"

    PHASE 2 (video):
      - heroURL present
      - videoURL missing
      - status not in {"error_video", "video_done"}
      -> run video pipeline, write videoURL + status="video_done"
    """
    global _initialized

    # First callback is the initial snapshot of all existing docs — ignore.
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

        # Field names must match Firestore exactly (camelCase).
        selfie_url = data.get("selfieUrl")
        first_name = data.get("firstName")
        last_name = data.get("lastName", "")
        gender = data.get("gender")
        selfie_uploaded_at = data.get("selfieUploadedAt")
        card_url = data.get("cardURL")
        hero_url = data.get("heroURL")
        video_url = data.get("videoURL")
        status = data.get("status")

        print(f"[listener] selfieUrl        = {selfie_url}")
        print(f"[listener] firstName        = {first_name}")
        print(f"[listener] lastName         = {last_name}")
        print(f"[listener] gender           = {gender}")
        print(f"[listener] selfieUploadedAt = {selfie_uploaded_at}")
        print(f"[listener] cardURL          = {card_url}")
        print(f"[listener] heroURL          = {hero_url}")
        print(f"[listener] videoURL         = {video_url}")
        print(f"[listener] status           = {status}")

        # ------------------------------------------------------------------
        # PHASE 1: IMAGE PIPELINE (hero + card)
        # ------------------------------------------------------------------
        if not card_url:
            if not selfie_uploaded_at:
                print(
                    "[listener] -> selfieUploadedAt is not set yet, skipping image generation."
                )
            elif not selfie_url:
                print("[listener] -> Missing selfieUrl, skipping image generation.")
            elif not first_name:
                print("[listener] -> Missing firstName, skipping image generation.")
            elif not gender:
                print("[listener] -> Missing gender, skipping image generation.")
            else:
                print("[listener] ✅ Conditions satisfied. Running IMAGE pipeline...")
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
                            "status": "done",  # ready for video
                        },
                        merge=True,
                    )
                    print(
                        "[listener] Firestore updated with heroURL + cardURL + status=done"
                    )

                except Exception as e:
                    print(f"[listener] ❌ ERROR while running IMAGE pipeline: {e}")
                    doc.reference.set(
                        {
                            "status": "error_image",
                            "errorMessage": str(e),
                        },
                        merge=True,
                    )
                    # If image failed, don't attempt video
                    continue

        # ------------------------------------------------------------------
        # Refresh values after possible IMAGE update
        # ------------------------------------------------------------------
        updated = doc.reference.get().to_dict()
        selfie_url = updated.get("selfieUrl")
        first_name = updated.get("firstName")
        last_name = updated.get("lastName", "")
        gender = updated.get("gender")
        hero_url = updated.get("heroURL")
        video_url = updated.get("videoURL")
        status = updated.get("status")

        print(f"[listener] (after refresh) heroURL  = {hero_url}")
        print(f"[listener] (after refresh) videoURL = {video_url}")
        print(f"[listener] (after refresh) status   = {status}")

        # ------------------------------------------------------------------
        # PHASE 2: VIDEO PIPELINE
        # ------------------------------------------------------------------
        if hero_url and not video_url and status not in ("error_video", "video_done"):
            print("[listener] → Running VIDEO pipeline from hero...")
            try:
                # 1) Download hero image from public Storage URL to a temp local file
                hero_path = download_url_to_temp(hero_url)

                # 2) Generate video using Veo (hero as visual reference)
                video_path = generate_hockey_video_from_hero(
                    hero_image_path=hero_path,
                    gender=gender or "",
                )

                # 3) Upload generated video to Firebase Storage
                video_url = upload_video_to_firebase(video_path)

                # 4) Update Firestore with videoURL and final status
                doc.reference.set(
                    {
                        "videoURL": video_url,
                        "status": "video_done",
                    },
                    merge=True,
                )
                print(
                    f"[listener] ✓ Firestore updated with videoURL={video_url} + status=video_done"
                )

            except Exception as e:
                print(f"[listener] ❌ ERROR while running VIDEO pipeline: {e}")
                doc.reference.set(
                    {
                        "status": "error_video",
                        "videoErrorMessage": str(e),
                    },
                    merge=True,
                )
                continue


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

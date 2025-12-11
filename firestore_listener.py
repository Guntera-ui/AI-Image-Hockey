# firestore_listener.py

import time
from typing import Any, Dict

from google.cloud import firestore as gc_firestore
from google.oauth2 import service_account

from config import SERVICE_ACCOUNT_PATH
from email_client import send_player_result_email
from player_pipeline import run_player_pipeline_from_storage_url
from storage_client import download_url_to_temp, upload_video_to_firebase
from video_ai import generate_hockey_video_from_hero

_initialized = False


def init_firestore():
    """
    Initialize Firestore client using explicit service account credentials.
    """
    print(f"[listener] Using service account at: {SERVICE_ACCOUNT_PATH}")

    creds = service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_PATH)
    )

    project_id = creds.project_id
    print(f"[listener] Firestore project_id: {project_id}")

    db = gc_firestore.Client(project=project_id, credentials=creds)
    return db


def _get_field(data: Dict[str, Any], *names):
    """
    Helper: try several field names, return first non-None.
    Lets us handle selfieUrl vs selfieURL if both appear.
    """
    for name in names:
        if name in data:
            return data.get(name)
    return None


def handle_player_change(doc_snapshot, changes, read_time):
    global _initialized

    # First snapshot includes all existing docs; we don't want to
    # retro-process them, so we just mark initialized and bail out.
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

        # Extract fields (handling selfieUrl/selfieURL)
        selfie_url = _get_field(data, "selfieUrl", "selfieURL")
        first_name = data.get("firstName")
        last_name = data.get("lastName", "")
        gender = data.get("gender")
        selfie_uploaded_at = data.get("selfieUploadedAt")
        card_url = data.get("cardURL")
        hero_url = data.get("heroURL")
        video_url = data.get("videoURL")
        status = data.get("status")
        email = data.get("email")
        email_sent = data.get("emailSent", False)
        email_error = data.get("emailError", False)

        print(f"[listener] selfieUrl        = {selfie_url}")
        print(f"[listener] firstName        = {first_name}")
        print(f"[listener] lastName         = {last_name}")
        print(f"[listener] gender           = {gender}")
        print(f"[listener] selfieUploadedAt = {selfie_uploaded_at}")
        print(f"[listener] cardURL          = {card_url}")
        print(f"[listener] heroURL          = {hero_url}")
        print(f"[listener] videoURL         = {video_url}")
        print(f"[listener] status           = {status}")
        print(f"[listener] email            = {email}")
        print(f"[listener] emailSent        = {email_sent}")
        print(f"[listener] emailError       = {email_error}")

        # ======================================================
        # PHASE 1 – IMAGE PIPELINE (hero + card)
        # ======================================================
        if not card_url:
            if not selfie_uploaded_at:
                print(
                    "[listener] -> selfieUploadedAt not set yet, skipping image generation."
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
                    continue

        # Refresh after possible image update
        updated = doc.reference.get().to_dict()
        selfie_url = _get_field(updated, "selfieUrl", "selfieURL")
        first_name = updated.get("firstName")
        last_name = updated.get("lastName", "")
        gender = updated.get("gender")
        hero_url = updated.get("heroURL")
        card_url = updated.get("cardURL")
        video_url = updated.get("videoURL")
        status = updated.get("status")
        email = updated.get("email")
        email_sent = updated.get("emailSent", False)
        email_error = updated.get("emailError", False)

        print(f"[listener] (after refresh) heroURL    = {hero_url}")
        print(f"[listener] (after refresh) cardURL    = {card_url}")
        print(f"[listener] (after refresh) videoURL   = {video_url}")
        print(f"[listener] (after refresh) status     = {status}")
        print(f"[listener] (after refresh) emailSent  = {email_sent}")
        print(f"[listener] (after refresh) emailError = {email_error}")

        # ======================================================
        # PHASE 2 – VIDEO PIPELINE
        # ======================================================
        if hero_url and not video_url and status not in ("error_video", "video_done"):
            print("[listener] → Running VIDEO pipeline from hero...")
            try:
                hero_path = download_url_to_temp(hero_url)

                video_path = generate_hockey_video_from_hero(
                    hero_image_path=hero_path,
                    gender=gender or "",
                )

                video_url = upload_video_to_firebase(video_path)

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

        # Refresh again after possible video update
        updated = doc.reference.get().to_dict()
        card_url = updated.get("cardURL")
        video_url = updated.get("videoURL")
        status = updated.get("status")
        email = updated.get("email")
        email_sent = updated.get("emailSent", False)
        email_error = updated.get("emailError", False)
        first_name = updated.get("firstName")

        print(f"[listener] (after video) cardURL    = {card_url}")
        print(f"[listener] (after video) videoURL   = {video_url}")
        print(f"[listener] (after video) status     = {status}")
        print(f"[listener] (after video) email      = {email}")
        print(f"[listener] (after video) emailSent  = {email_sent}")
        print(f"[listener] (after video) emailError = {email_error}")

        # ======================================================
        # PHASE 3 – EMAIL SENDING (no infinite retry)
        # ======================================================
        # Only send if:
        #  - we have an email
        #  - we have at least a cardURL
        #  - emailSent is False
        #  - emailError is False (we haven't failed before)
        if email and card_url and not email_sent and not email_error:
            try:
                print(f"[listener] → Sending result email to {email}...")
                send_player_result_email(
                    to_email=email,
                    first_name=first_name or "",
                    card_url=card_url,
                    video_url=video_url,  # may be None if video failed
                )

                doc.reference.set(
                    {
                        "emailSent": True,
                        "emailError": False,
                    },
                    merge=True,
                )
                print("[listener] ✓ Email sent and emailSent flag updated.")
            except Exception as e:
                print(f"[listener] ❌ ERROR while sending email: {e}")
                doc.reference.set(
                    {
                        "emailSent": False,
                        "emailError": True,  # <-- prevents infinite retries
                        "emailErrorMessage": str(e),
                    },
                    merge=True,
                )
                print(
                    "[listener] Marked emailError=True so listener will NOT retry for this player."
                )
                # No further processing for this doc on this change
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

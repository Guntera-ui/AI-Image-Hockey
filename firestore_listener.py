# firestore_listener.py

from __future__ import annotations

import os
import random
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from google.cloud import firestore as gc_firestore
from google.oauth2 import service_account

from config import (
    LOCK_TTL_SECONDS,
    SERVICE_ACCOUNT_PATH,
    VIDEO_OVERLAY_FONT_NAME_PATH,
    VIDEO_OVERLAY_FONT_SHOT_PATH,
    VIDEO_OVERLAY_FRAME_PATH,
    VIDEO_OVERLAY_HOLE_ALPHA_MAX,
)
from email_client import send_player_result_email
from player_pipeline import run_player_pipeline_from_storage_url
from storage_client import (
    download_url_to_temp,
    upload_raw_video_to_firebase,
    upload_video_to_firebase,
)
from video_ai import generate_hockey_video_from_hero
from video_overlay import overlay_video_with_branding


# ----------------------------
# Tuning knobs
# ----------------------------
HEARTBEAT_INTERVAL_SECONDS = 45
RETRY_DELAYS_SECONDS = (2, 5, 12)  # 3 retries


_initialized = False
WORKER_ID = os.getenv("WORKER_ID", f"worker-{os.getpid()}-{random.randint(1000,9999)}")


# ----------------------------
# Firestore init
# ----------------------------
def init_firestore() -> gc_firestore.Client:
    print(f"[listener] Using service account at: {SERVICE_ACCOUNT_PATH}")
    creds = service_account.Credentials.from_service_account_file(str(SERVICE_ACCOUNT_PATH))
    db = gc_firestore.Client(project=creds.project_id, credentials=creds)
    print(f"[listener] Firestore project_id: {creds.project_id}")
    print(f"[listener] WORKER_ID: {WORKER_ID}")
    print(f"[listener] LOCK_TTL_SECONDS: {LOCK_TTL_SECONDS}")
    return db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _freshness_timestamp(lock_at: Optional[datetime], heartbeat_at: Optional[datetime]) -> Optional[datetime]:
    """
    Use whichever is newer: lockAt or heartbeatAt.
    This prevents lock stealing while a long-running job is still alive.
    """
    la = _as_utc(lock_at)
    hb = _as_utc(heartbeat_at)
    if la and hb:
        return hb if hb > la else la
    return hb or la


def _is_lock_expired(lock_at: Optional[datetime], heartbeat_at: Optional[datetime]) -> bool:
    fresh = _freshness_timestamp(lock_at, heartbeat_at)
    if not fresh:
        return True
    return (_utcnow() - fresh).total_seconds() > LOCK_TTL_SECONDS


def _get_field(data: Dict[str, Any], *names: str) -> Any:
    for n in names:
        if n in data:
            return data.get(n)
    return None


# ----------------------------
# Retry helper
# ----------------------------
def _with_retries(label: str, fn):
    last_err = None
    attempts = 1 + len(RETRY_DELAYS_SECONDS)
    for attempt_i in range(attempts):
        if attempt_i > 0:
            time.sleep(RETRY_DELAYS_SECONDS[attempt_i - 1])
        try:
            return fn()
        except Exception as e:
            last_err = e
            print(f"[listener] ⚠️ {label} failed (attempt {attempt_i+1}/{attempts}): {e}")
    raise last_err


# ----------------------------
# Heartbeat helper
# ----------------------------
class Heartbeat:
    def __init__(self, ref: gc_firestore.DocumentReference, interval_seconds: int = HEARTBEAT_INTERVAL_SECONDS):
        self.ref = ref
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)

    def _run(self):
        while not self._stop.is_set():
            try:
                self.ref.set({"heartbeatAt": gc_firestore.SERVER_TIMESTAMP}, merge=True)
            except Exception:
                pass
            self._stop.wait(self.interval_seconds)


# ----------------------------
# Lock/claim helpers
# ----------------------------
def _try_claim_phase(ref: gc_firestore.DocumentReference, desired_status: str) -> bool:
    @gc_firestore.transactional
    def _txn(txn: gc_firestore.Transaction) -> bool:
        snap = ref.get(transaction=txn)
        data = snap.to_dict() or {}

        status = data.get("status")
        lock_owner = data.get("lockOwner")
        lock_at = data.get("lockAt")
        heartbeat_at = data.get("heartbeatAt")

        if status == desired_status:
            return False

        # If another worker owns it and it's still fresh, skip.
        if lock_owner and lock_owner != WORKER_ID and not _is_lock_expired(lock_at, heartbeat_at):
            return False

        txn.set(
            ref,
            {
                "status": desired_status,
                "lockOwner": WORKER_ID,
                "lockAt": gc_firestore.SERVER_TIMESTAMP,
                "heartbeatAt": gc_firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        return True

    transaction = ref._client.transaction()
    return _txn(transaction)


def _release_lock(ref: gc_firestore.DocumentReference, extra_fields: Optional[Dict[str, Any]] = None) -> None:
    fields: Dict[str, Any] = {
        "lockOwner": gc_firestore.DELETE_FIELD,
        "lockAt": gc_firestore.DELETE_FIELD,
        "heartbeatAt": gc_firestore.DELETE_FIELD,
    }
    if extra_fields:
        fields.update(extra_fields)
    ref.set(fields, merge=True)


@dataclass(frozen=True)
class PlayerState:
    selfie_url: Optional[str]
    selfie_uploaded_at: Optional[Any]
    first_name: Optional[str]
    last_name: str
    gender: Optional[str]
    email: Optional[str]

    hero_url: Optional[str]
    card_url: Optional[str]
    video_url: Optional[str]

    status: Optional[str]

    email_sent: bool
    email_error: bool
    email_sending: bool

    lock_owner: Optional[str]
    lock_at: Optional[datetime]
    heartbeat_at: Optional[datetime]


def _read_state(data: Dict[str, Any]) -> PlayerState:
    return PlayerState(
        selfie_url=_get_field(data, "selfieUrl", "selfieURL"),
        selfie_uploaded_at=data.get("selfieUploadedAt"),
        first_name=data.get("firstName"),
        last_name=data.get("lastName", "") or "",
        gender=data.get("gender"),
        email=data.get("email"),
        hero_url=data.get("heroURL"),
        card_url=data.get("cardURL"),
        video_url=data.get("videoURL"),
        status=data.get("status"),
        email_sent=bool(data.get("emailSent", False)),
        email_error=bool(data.get("emailError", False)),
        email_sending=bool(data.get("emailSending", False)),
        lock_owner=data.get("lockOwner"),
        lock_at=data.get("lockAt"),
        heartbeat_at=data.get("heartbeatAt"),
    )


# ----------------------------
# Phases
# ----------------------------
def _phase_image(ref: gc_firestore.DocumentReference, state: PlayerState) -> None:
    if state.card_url:
        return
    if not state.selfie_uploaded_at or not state.selfie_url or not state.first_name or not state.gender:
        return

    if not _try_claim_phase(ref, "processing_image"):
        return

    print(f"[listener] ✅ Claimed IMAGE for {ref.id} ({WORKER_ID})")
    hb = Heartbeat(ref)
    hb.start()

    t0 = time.time()
    try:
        result = run_player_pipeline_from_storage_url(
            selfie_url=state.selfie_url,
            first_name=state.first_name,
            last_name=state.last_name or "",
            gender=state.gender,
        )
        hero_url = result["hero_url"]
        card_url = result["card_url"]

        ref.set(
            {
                "heroURL": hero_url,
                "cardURL": card_url,
                "status": "image_done",
                "metrics": {"imageMs": int((time.time() - t0) * 1000)},
            },
            merge=True,
        )
        print(f"[listener] ✓ IMAGE done for {ref.id}")

    except Exception as e:
        ref.set({"status": "error_image", "errorMessage": str(e)}, merge=True)
        print(f"[listener] ❌ IMAGE error for {ref.id}: {e}")

    finally:
        hb.stop()
        _release_lock(ref)


def _phase_video(ref: gc_firestore.DocumentReference, state: PlayerState) -> None:
    if not state.hero_url or state.video_url:
        return
    if state.status in ("error_video", "processing_video"):
        return

    if not _try_claim_phase(ref, "processing_video"):
        return

    print(f"[listener] ✅ Claimed VIDEO for {ref.id} ({WORKER_ID})")
    hb = Heartbeat(ref)
    hb.start()

    t0 = time.time()
    raw_video_path = None  # for Option A raw upload on failure
    try:
        hero_path = download_url_to_temp(state.hero_url)

        # 1) Veo (retry)
        raw_video_path = _with_retries(
            "VEO video generation",
            lambda: generate_hockey_video_from_hero(hero_image_path=hero_path, gender=state.gender or ""),
        )

        # 2) Overlay (Thunderstrike is hardcoded for now)
        framed_path = raw_video_path.with_name(raw_video_path.stem + "_framed.mp4")
        overlay_video_with_branding(
            input_video=raw_video_path,
            output_video=framed_path,
            first_name=state.first_name or "",
            last_name=state.last_name or "",
            powershot="THUNDERSTRIKE",
            frame_path=VIDEO_OVERLAY_FRAME_PATH,
            font_name_path=VIDEO_OVERLAY_FONT_NAME_PATH,
            font_shot_path=VIDEO_OVERLAY_FONT_SHOT_PATH,
            hole_alpha_max=VIDEO_OVERLAY_HOLE_ALPHA_MAX,
        )

        # 3) Upload final
        final_url = upload_video_to_firebase(framed_path)

        ref.set(
            {
                "videoURL": final_url,
                "status": "video_done",
                "metrics": {"videoMs": int((time.time() - t0) * 1000)},
            },
            merge=True,
        )
        print(f"[listener] ✓ VIDEO done for {ref.id}")

    except Exception as e:
        # ✅ Option A: upload raw ONLY on failure (if we have it)
        try:
            if raw_video_path is not None:
                raw_url = upload_raw_video_to_firebase(raw_video_path)
                ref.set({"videoRawURL": raw_url}, merge=True)
        except Exception:
            pass

        ref.set({"status": "error_video", "videoErrorMessage": str(e)}, merge=True)
        print(f"[listener] ❌ VIDEO error for {ref.id}: {e}")

    finally:
        hb.stop()
        _release_lock(ref)


def _phase_email(ref: gc_firestore.DocumentReference, state: PlayerState) -> None:
    if not state.email or not state.card_url:
        return
    if state.email_sent or state.email_error:
        return

    @gc_firestore.transactional
    def _txn(txn: gc_firestore.Transaction) -> bool:
        snap = ref.get(transaction=txn)
        data = snap.to_dict() or {}

        if bool(data.get("emailSent", False)) or bool(data.get("emailError", False)):
            return False
        if bool(data.get("emailSending", False)):
            return False

        lock_owner = data.get("lockOwner")
        lock_at = data.get("lockAt")
        heartbeat_at = data.get("heartbeatAt")
        if lock_owner and lock_owner != WORKER_ID and not _is_lock_expired(lock_at, heartbeat_at):
            return False

        txn.set(
            ref,
            {
                "emailSending": True,
                "status": "processing_email",
                "lockOwner": WORKER_ID,
                "lockAt": gc_firestore.SERVER_TIMESTAMP,
                "heartbeatAt": gc_firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        return True

    transaction = ref._client.transaction()
    if not _txn(transaction):
        return

    print(f"[listener] ✅ Claimed EMAIL for {ref.id} ({WORKER_ID})")
    hb = Heartbeat(ref)
    hb.start()

    t0 = time.time()
    try:
        _with_retries(
            "SMTP send",
            lambda: send_player_result_email(
                to_email=state.email,
                first_name=state.first_name or "",
                card_url=state.card_url,
                video_url=state.video_url,
            ),
        )

        ref.set(
            {
                "emailSent": True,
                "emailError": False,
                "emailSending": False,
                "status": "done",
                "metrics": {"emailMs": int((time.time() - t0) * 1000)},
            },
            merge=True,
        )
        print(f"[listener] ✓ EMAIL sent for {ref.id}")

    except Exception as e:
        ref.set(
            {
                "emailSent": False,
                "emailError": True,
                "emailSending": False,
                "emailErrorMessage": str(e),
                "status": "error_email",
            },
            merge=True,
        )
        print(f"[listener] ❌ EMAIL error for {ref.id}: {e}")

    finally:
        hb.stop()
        _release_lock(ref)


def _process_doc(ref: gc_firestore.DocumentReference) -> None:
    snap = ref.get()
    data = snap.to_dict() or {}
    state = _read_state(data)

    # If locked by another worker and still fresh, skip
    if state.lock_owner and state.lock_owner != WORKER_ID and not _is_lock_expired(state.lock_at, state.heartbeat_at):
        return

    _phase_image(ref, state)

    snap = ref.get()
    data = snap.to_dict() or {}
    state = _read_state(data)
    _phase_video(ref, state)

    snap = ref.get()
    data = snap.to_dict() or {}
    state = _read_state(data)
    _phase_email(ref, state)


# ----------------------------
# Snapshot callback
# ----------------------------
def handle_player_change(doc_snapshot, changes, read_time):
    global _initialized

    if not _initialized:
        _initialized = True
        print(f"\n[listener] Initial snapshot received with {len(doc_snapshot)} docs. Ignoring existing players.")
        return

    for change in changes:
        if change.type.name == "REMOVED":
            continue
        _process_doc(change.document.reference)


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


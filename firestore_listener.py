from __future__ import annotations

import os
import random
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from google.cloud import firestore as gc_firestore
from google.oauth2 import service_account

from config import (
    LOCK_TTL_SECONDS,
    SERVICE_ACCOUNT_PATH,
    VIDEO_OVERLAY_HOLE_ALPHA_MAX,
)
from email_client import send_player_result_email
from hero_ai import generate_hero_from_photo
from hero_card_overlay import generate_card_with_frame
from overlay_frames import pick_frame_for_score
from storage_client import (
    download_url_to_temp,
    upload_raw_video_to_firebase,
    upload_video_to_firebase,
    upload_to_firebase,
)
from video_ai import generate_hockey_video_from_hero
from video_overlay import overlay_video_with_frame_only


# ============================================================
# CONFIG
# ============================================================

HEARTBEAT_INTERVAL_SECONDS = 45
RETRY_DELAYS_SECONDS = (2, 5, 12)
SCORE_TIMEOUT_SECONDS = 8 * 60

WORKER_ID = os.getenv(
    "WORKER_ID",
    f"worker-{os.getpid()}-{random.randint(1000,9999)}",
)

_initialized = False


# ============================================================
# FIRESTORE INIT
# ============================================================

def init_firestore() -> gc_firestore.Client:
    creds = service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_PATH)
    )
    db = gc_firestore.Client(
        project=creds.project_id,
        credentials=creds,
    )
    print("")
    print("[listener] Firestore initialized")
    print("[listener] WORKER_ID:", WORKER_ID)
    print("[listener] SCORE_TIMEOUT_SECONDS:", SCORE_TIMEOUT_SECONDS)
    print("")
    return db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ============================================================
# LOCKING
# ============================================================

def _is_lock_expired(lock_at, heartbeat_at) -> bool:
    times = [_as_utc(lock_at), _as_utc(heartbeat_at)]
    times = [t for t in times if t]
    if not times:
        return True
    newest = max(times)
    return (_utcnow() - newest).total_seconds() > LOCK_TTL_SECONDS


def _try_claim(ref: gc_firestore.DocumentReference, status: str) -> bool:
    print(f"[listener][{ref.id}] Try claim status={status}")

    @gc_firestore.transactional
    def _txn(txn):
        snap = ref.get(transaction=txn)
        data = snap.to_dict() or {}

        owner = data.get("lockOwner")
        if owner and owner != WORKER_ID:
            if not _is_lock_expired(data.get("lockAt"), data.get("heartbeatAt")):
                print(f"[listener][{ref.id}] Lock owned by {owner}")
                return False

        txn.set(
            ref,
            {
                "status": status,
                "lockOwner": WORKER_ID,
                "lockAt": gc_firestore.SERVER_TIMESTAMP,
                "heartbeatAt": gc_firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        return True

    return _txn(ref._client.transaction())


def _release_lock(ref: gc_firestore.DocumentReference):
    ref.set(
        {
            "lockOwner": gc_firestore.DELETE_FIELD,
            "lockAt": gc_firestore.DELETE_FIELD,
            "heartbeatAt": gc_firestore.DELETE_FIELD,
        },
        merge=True,
    )


# ============================================================
# HEARTBEAT
# ============================================================

class Heartbeat:
    def __init__(self, ref: gc_firestore.DocumentReference):
        self.ref = ref
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._t.start()

    def stop(self):
        self._stop.set()
        self._t.join(timeout=2)

    def _run(self):
        while not self._stop.is_set():
            try:
                self.ref.set(
                    {"heartbeatAt": gc_firestore.SERVER_TIMESTAMP},
                    merge=True,
                )
            except Exception:
                pass
            self._stop.wait(HEARTBEAT_INTERVAL_SECONDS)


# ============================================================
# PLAYER STATE
# ============================================================

@dataclass(frozen=True)
class PlayerState:
    selfie_url: Optional[str]
    selfie_uploaded_at: Optional[Any]
    gender: Optional[str]
    email: Optional[str]
    first_name: Optional[str]

    total_score: Optional[int]
    awaiting_score_at: Optional[datetime]
    frame_id: Optional[str]

    hero_url: Optional[str]
    video_raw_url: Optional[str]
    card_url: Optional[str]
    video_url: Optional[str]

    unique_id: Optional[str]            # 🔥 ADDED

    status: Optional[str]
    email_sent: bool
    email_error: bool


def _read_state(data: Dict[str, Any]) -> PlayerState:
    return PlayerState(
        selfie_url=data.get("selfieUrl"),
        selfie_uploaded_at=data.get("selfieUploadedAt"),
        gender=data.get("gender"),
        email=data.get("email"),
        first_name=data.get("firstName"),

        total_score=data.get("TotalScore"),
        awaiting_score_at=_as_utc(data.get("awaitingScoreAt")),
        frame_id=data.get("frameId"),

        hero_url=data.get("heroURL"),
        video_raw_url=data.get("videoRawURL"),
        card_url=data.get("cardURL"),
        video_url=data.get("videoURL"),

        unique_id=data.get("uniqueId"),   # 🔥 ADDED

        status=data.get("status"),
        email_sent=bool(data.get("emailSent", False)),
        email_error=bool(data.get("emailError", False)),
    )


# ============================================================
# FRAME LOCKING HELPERS (UNCHANGED)
# ============================================================

def _choose_and_lock_frame(ref, score: int) -> Tuple[str, str]:
    frame_path = pick_frame_for_score(score)
    frame_id = frame_path.stem
    ref.set({"frameId": frame_id}, merge=True)
    print(f"[listener][{ref.id}] Frame locked: {frame_id}")
    return frame_path, frame_id


def _frame_from_id(frame_id: str) -> str:
    from overlay_frames import FRAMES
    for tier_frames in FRAMES.values():
        for p in tier_frames:
            if p.stem == frame_id:
                return p
    raise RuntimeError(f"Unknown frameId: {frame_id}")


# ============================================================
# PHASE 1: HERO + RAW VIDEO (UNCHANGED)
# ============================================================

def _phase_hero(ref, state: PlayerState):
    if state.hero_url and state.video_raw_url:
        return
    if not state.selfie_url or not state.selfie_uploaded_at or not state.gender:
        return
    if not _try_claim(ref, "processing_hero"):
        return

    hb = Heartbeat(ref)
    hb.start()

    try:
        selfie_path = download_url_to_temp(state.selfie_url)
        hero_path = generate_hero_from_photo(
            user_photo_path=selfie_path,
            user_name="",
            power_label="",
            gender=state.gender,
        )
        hero_url = upload_to_firebase(hero_path)

        raw_video_path = generate_hockey_video_from_hero(
            hero_image_path=hero_path,
            gender=state.gender,
        )
        raw_video_url = upload_raw_video_to_firebase(raw_video_path)

        ref.set(
            {
                "heroURL": hero_url,
                "videoRawURL": raw_video_url,
                "status": "awaiting_score",
                "awaitingScoreAt": gc_firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
    finally:
        hb.stop()
        _release_lock(ref)


# ============================================================
# PHASE 2: OVERLAY (UNCHANGED)
# ============================================================

def _phase_overlay(ref, state: PlayerState):
    if state.card_url and state.video_url:
        return
    if not state.hero_url or not state.video_raw_url:
        return

    score = state.total_score
    if score is None:
        if not state.awaiting_score_at:
            return
        waited = (_utcnow() - state.awaiting_score_at).total_seconds()
        if waited < SCORE_TIMEOUT_SECONDS:
            return
        score = 0

    if not _try_claim(ref, "processing_overlay"):
        return

    hb = Heartbeat(ref)
    hb.start()

    try:
        if state.frame_id:
            frame_path = _frame_from_id(state.frame_id)
        else:
            frame_path, _ = _choose_and_lock_frame(ref, int(score))

        hero_path = download_url_to_temp(state.hero_url)
        card_path = generate_card_with_frame(hero_path, frame_path)
        card_url = upload_to_firebase(card_path)

        raw_video_path = download_url_to_temp(state.video_raw_url)
        framed_video_path = raw_video_path.with_name(
            raw_video_path.stem + "_framed.mp4"
        )

        overlay_video_with_frame_only(
            input_video=raw_video_path,
            output_video=framed_video_path,
            frame_path=frame_path,
            hole_alpha_max=VIDEO_OVERLAY_HOLE_ALPHA_MAX,
        )
        video_url = upload_video_to_firebase(framed_video_path)

        ref.set(
            {
                "cardURL": card_url,
                "videoURL": video_url,
                "status": "ready_for_email",
            },
            merge=True,
        )
    finally:
        hb.stop()
        _release_lock(ref)


# ============================================================
# PHASE 3: EMAIL (ONLY REAL CHANGE)
# ============================================================

def _phase_email(ref, state: PlayerState):
    if not state.email or not state.card_url or not state.unique_id:
        return
    if state.email_sent or state.email_error:
        return
    if not _try_claim(ref, "processing_email"):
        return

    hb = Heartbeat(ref)
    hb.start()

    try:
        send_player_result_email(
            to_email=state.email,
            first_name=state.first_name,
            total_score=state.total_score,
            run_id=state.unique_id,     # 🔥 uniqueId used
        )
        ref.set(
            {
                "emailSent": True,
                "emailError": False,
                "status": "done",
            },
            merge=True,
        )
    finally:
        hb.stop()
        _release_lock(ref)


# ============================================================
# DISPATCHER
# ============================================================

def _process_doc(ref):
    data = ref.get().to_dict() or {}
    state = _read_state(data)

    _phase_hero(ref, state)
    state = _read_state(ref.get().to_dict() or {})

    _phase_overlay(ref, state)
    state = _read_state(ref.get().to_dict() or {})

    _phase_email(ref, state)


# ============================================================
# SNAPSHOT HANDLER
# ============================================================

def handle_player_change(doc_snapshot, changes, read_time):
    global _initialized
    if not _initialized:
        _initialized = True
        print("[listener] Initial snapshot ignored")
        return

    for change in changes:
        if change.type.name != "REMOVED":
            _process_doc(change.document.reference)


# ============================================================
# ENTRY POINT
# ============================================================

def start_listener():
    db = init_firestore()
    print("[listener] Listening on players collection")
    watch = db.collection("players").on_snapshot(handle_player_change)

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        watch.unsubscribe()


if __name__ == "__main__":
    start_listener()


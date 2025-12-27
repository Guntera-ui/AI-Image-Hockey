# player_pipeline.py

from pathlib import Path
from typing import TypedDict

from config import BASE_DIR
from hero_ai import generate_hero_from_photo
from hero_card_overlay import generate_card_with_frame
from overlay_frames import pick_frame_for_score
from storage_client import (
    download_blob_to_temp,
    download_url_to_temp,
    upload_to_firebase,
)


class PlayerRunResult(TypedDict):
    hero_url: str
    card_url: str
    hero_path: str
    card_path: str


def run_player_pipeline_from_storage_url(
    selfie_url: str,
    gender: str,
    total_score: int,
) -> PlayerRunResult:
    selfie_path: Path = download_url_to_temp(selfie_url)
    return _run_pipeline_local(selfie_path, gender, total_score)


def run_player_pipeline_from_storage_blob(
    selfie_blob_path: str,
    gender: str,
    total_score: int,
) -> PlayerRunResult:
    selfie_path: Path = download_blob_to_temp(selfie_blob_path)
    return _run_pipeline_local(selfie_path, gender, total_score)


def _run_pipeline_local(
    selfie_path: Path,
    gender: str,
    total_score: int,
) -> PlayerRunResult:

    hero_path = generate_hero_from_photo(
        user_photo_path=selfie_path,
        user_name="",        # unused now
        power_label="",      # unused now
        gender=gender,
    )

    frame_path = pick_frame_for_score(total_score)

    card_path = generate_card_with_frame(
        hero_image_path=hero_path,
        frame_path=frame_path,
    )

    hero_url = upload_to_firebase(hero_path)
    card_url = upload_to_firebase(card_path)

    return {
        "hero_url": hero_url,
        "card_url": card_url,
        "hero_path": str(hero_path),
        "card_path": str(card_path),
    }


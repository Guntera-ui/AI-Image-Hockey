# player_pipeline.py
from typing import TypedDict

from hero_ai import generate_hero_from_photo, generate_full_card_from_hero
from storage_client import (
    upload_to_firebase,
    download_blob_to_temp,
    download_url_to_temp,
)
from config import BASE_DIR

from pathlib import Path

FRAME_STYLE_PATH = BASE_DIR / "assets" / "thunderstrike_reference.jpg"
DEFAULT_POWER_LABEL = "Power Shot"


class PlayerRunResult(TypedDict):
    hero_url: str
    card_url: str
    hero_path: str
    card_path: str


def _ensure_frame_exists() -> None:
    if not FRAME_STYLE_PATH.exists():
        raise FileNotFoundError(
            f"Frame style image not found: {FRAME_STYLE_PATH}. "
            "Place your Thunderstrike reference card in assets/."
        )


def run_player_pipeline_from_storage_blob(
    selfie_blob_path: str,
    first_name: str,
    last_name: str,
    gender: str,
) -> PlayerRunResult:
    """
    Main AI pipeline, where the selfie already lives in Firebase Storage.

    Args:
        selfie_blob_path: e.g. 'selfies/xyz.jpg'
        first_name, last_name, gender: collected from the kiosk UI

    Returns:
        dict with hero/card local paths and Firebase public URLs.
    """
    _ensure_frame_exists()

    # 1) Download selfie from Storage to a temp local file (backend only)
    selfie_path: Path = download_blob_to_temp(selfie_blob_path)

    return _run_player_pipeline_local(
        selfie_path=selfie_path,
        first_name=first_name,
        last_name=last_name,
        gender=gender,
    )


def run_player_pipeline_from_storage_url(
    selfie_url: str,
    first_name: str,
    last_name: str,
    gender: str,
) -> PlayerRunResult:
    """
    Same as above, but starting from a Firebase public download URL
    (like the 'selfieURL' field you're showing in Firestore).
    """
    _ensure_frame_exists()

    selfie_path: Path = download_url_to_temp(selfie_url)

    return _run_player_pipeline_local(
        selfie_path=selfie_path,
        first_name=first_name,
        last_name=last_name,
        gender=gender,
    )


def _run_player_pipeline_local(
    selfie_path: Path,
    first_name: str,
    last_name: str,
    gender: str,
) -> PlayerRunResult:
    """
    Internal helper that still uses the existing hero_ai functions which
    expect a local file Path. This is where Gemini is actually called.
    """
    if not selfie_path.exists():
        raise FileNotFoundError(f"Selfie image not found: {selfie_path}")

    user_name = f"{first_name} {last_name}".strip()
    power_label = DEFAULT_POWER_LABEL

    # Hero from selfie
    hero_path = generate_hero_from_photo(
        user_photo_path=selfie_path,
        user_name=user_name,
        power_label=power_label,
    )

    # Card from hero + frame
    card_path = generate_full_card_from_hero(
        hero_image_path=hero_path,
        frame_style_path=FRAME_STYLE_PATH,
        user_name=user_name,
        power_label=power_label,
    )

    # Upload both to Storage
    hero_url = upload_to_firebase(hero_path)
    card_url = upload_to_firebase(card_path)

    return {
        "hero_url": hero_url,
        "card_url": card_url,
        "hero_path": str(hero_path),
        "card_path": str(card_path),
    }

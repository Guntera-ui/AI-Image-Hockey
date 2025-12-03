# main.py
import sys
from pathlib import Path

from config import BASE_DIR
from hero_ai import generate_full_card_from_hero, generate_hero_from_photo
from storage_client import upload_to_firebase

# Reference Thunderstrike-style frame image (the one with
# "PLAYER NAME PARTICIPATION TITLE" or similar placeholder text).
# Put that file into assets/ and adjust the filename if needed.
FRAME_STYLE_PATH = BASE_DIR / "assets" / "thunderstrike_reference.jpg"


def process_local_image(input_image_path_str: str):
    """
    Full pipeline for the kiosk prototype:

    1. Take the user input image from disk.
    2. Use Gemini to generate a hockey hero image (player + arena).
    3. Use Gemini again to create a full Thunderstrike-style card
       using the hero image + a reference frame style.
    4. Upload the final card to Firebase Storage and get a public URL.
    5. Generate a QR code that points to that URL.
    """
    input_path = Path(input_image_path_str)

    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    if not FRAME_STYLE_PATH.exists():
        raise FileNotFoundError(
            f"Frame style image not found: {FRAME_STYLE_PATH}\n"
            "Place your Thunderstrike reference card in assets/ and "
            "update FRAME_STYLE_PATH if the filename is different."
        )

    print(f"[1] Using input image: {input_path}")

    # TODO: later pull these from Firestore / UE5
    user_name = "Nika Mzhavanadze"
    power_label = "Power Shot"

    # Step 2: call Gemini to create the hero image from the user photo
    hero_path = generate_hero_from_photo(input_path, user_name, power_label)
    print(f"[2] Hero image from Gemini saved at: {hero_path}")

    # Step 3: call Gemini to create the full Thunderstrike-style card
    card_path = generate_full_card_from_hero(
        hero_image_path=hero_path,
        frame_style_path=FRAME_STYLE_PATH,
        user_name=user_name,
        power_label=power_label,
    )
    print(f"[3] Final Thunderstrike card saved at: {card_path}")

    # Step 4: upload card to Firebase Storage and get a public HTTPS URL
    public_url = upload_to_firebase(card_path)
    print("[4] Card uploaded to Firebase Storage.")
    print(f"    Public URL: {public_url}")

    print("\nDone!")


if __name__ == "__main__":
    # If an image path is passed as CLI arg, use it; otherwise default to test_input.jpg
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        image_path = "test3.jpg"  # fallback

    process_local_image(image_path)

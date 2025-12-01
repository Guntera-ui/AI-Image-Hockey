# main.py
from pathlib import Path
import sys

from image_processing import fake_ai_image_process
from storage_client import upload_to_firebase
from qr_codes import generate_qr_for_url


def process_local_image(input_image_path_str: str):
    """
    Full pipeline:
    - check image exists
    - run fake AI processing
    - upload processed image to Firebase Storage
    - generate QR pointing to the HTTPS URL
    - print where everything is saved
    """
    input_path = Path(input_image_path_str)

    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    print(f"[1] Using input image: {input_path}")

    # Step 1: process image with fake AI
    processed_path = fake_ai_image_process(input_path)
    print(f"[2] Processed image saved at: {processed_path}")

    # Step 2: upload to Firebase Storage, get public URL
    public_url = upload_to_firebase(processed_path)
    print(f"[3] Uploaded to Firebase Storage: {public_url}")

    # Step 3: generate QR code for that public URL
    qr_path = generate_qr_for_url(public_url)
    print(f"[4] QR code saved at: {qr_path}")

    print("\nDone!")
    print("→ Open the QR image and scan it with your phone.")
    print("  It should open the HTTPS URL to the processed image.")


if __name__ == "__main__":
    # If user passes an argument, use that, otherwise default to test_input.jpg
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        image_path = "test_input.PNG"  # fallback

    process_local_image(image_path)


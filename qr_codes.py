# qr_codes.py
from pathlib import Path
import uuid
import qrcode

from config import QR_DIR


def generate_qr_for_url(target_url: str) -> Path:
    """
    Generate a QR code that opens the given URL (https://...).
    """
    qr_img = qrcode.make(target_url)

    # Generate unique filename for the QR image
    qr_filename = f"qr_{uuid.uuid4().hex}.png"
    qr_path = QR_DIR / qr_filename

    # Save QR code image
    qr_img.save(qr_path)

    return qr_path


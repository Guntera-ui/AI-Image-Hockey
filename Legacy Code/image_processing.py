# image_processing.py
from pathlib import Path
from PIL import Image, ImageOps
import uuid

from config import MEDIA_DIR


def fake_ai_image_process(input_image_path: Path) -> Path:
    """
    Simulate an AI image process.
    - open the image
    - convert to grayscale
    - mirror it horizontally
    - save to media/ with a unique name
    Returns the path to the processed image.
    """
    img = Image.open(input_image_path)

    # Apply "effects" (this is our fake AI)
    img = ImageOps.grayscale(img)      # turn black & white
    img = ImageOps.mirror(img)         # flip horizontally

    # Build output filename: originalname_processed_<uuid>.png
    output_filename = f"{input_image_path.stem}_processed_{uuid.uuid4().hex}.png"
    output_path = MEDIA_DIR / output_filename

    img.save(output_path)

    return output_path


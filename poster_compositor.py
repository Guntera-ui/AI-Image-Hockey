import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from config import BASE_DIR, MEDIA_DIR

TEMPLATE_PATH = BASE_DIR / "assets" / "thunderstrike_template.png"

# Area where original "AL SILVESTRI • POWER SHOT" sits
ARC_CLEAR_BOX = (120, 205, 600, 285)


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Try to load a nice bold font, fall back to default."""
    try:
        return ImageFont.truetype("arial.ttf", size=size)
    except Exception:
        return ImageFont.load_default()


def _make_template_overlay(template: Image.Image) -> Image.Image:
    """
    Build an overlay from the Thunderstrike template:

    - Pure white pixels → fully transparent (show hero background)
    - Very bright pixels → low alpha (light brush tint)
    - Mid-bright pixels → medium alpha
    - Dark/colored pixels (logo, Thunderstrike, red/blue arcs) → fully opaque
    """
    tpl_rgb = template.convert("RGB")
    w, h = tpl_rgb.size

    alpha = Image.new("L", (w, h), 255)
    ap = alpha.load()
    px = tpl_rgb.load()

    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            brightness = (r + g + b) // 3
            color_spread = max(r, g, b) - min(r, g, b)

            # nearly white & neutral → treat as background
            if brightness > 245 and color_spread < 10:
                a = 0  # fully transparent
            elif brightness > 235:
                a = int(255 * 0.25)  # very bright → subtle overlay
            elif brightness > 210:
                a = int(255 * 0.5)  # mid bright → mid overlay
            else:
                a = 255  # colored / darker → strong branding
            ap[x, y] = a

    overlay = template.convert("RGBA")
    overlay.putalpha(alpha)
    return overlay


def _clear_arc_band(base_img: Image.Image) -> None:
    """
    Clear the old 'AL SILVESTRI • POWER SHOT' text by drawing a subtle
    rounded translucent band so our text is readable but still sits
    nicely on the hero+template combo.
    """
    draw = ImageDraw.Draw(base_img)
    x1, y1, x2, y2 = ARC_CLEAR_BOX

    sample_x = (x1 + x2) // 2
    sample_y = (y1 + y2) // 2
    r, g, b, *_ = base_img.getpixel((sample_x, sample_y))

    # Darken for contrast
    r = int(r * 0.6)
    g = int(g * 0.6)
    b = int(b * 0.6)

    band_color = (r, g, b, 190)
    draw.rounded_rectangle(ARC_CLEAR_BOX, radius=22, fill=band_color)


def create_thunderstrike_poster(
    hero_image_path: Path,
    user_name: str,
    power_label: str,
) -> Path:
    """
    - Use the Gemini hero image (arena + player) as the full background.
    - Overlay the Thunderstrike template with brightness-based alpha so
      logos/brushes show, white center mostly shows the arena.
    - Replace the default arc text with user_name + power_label.

    Returns: path to final poster PNG in MEDIA_DIR.
    """
    # 1) Load hero + template
    hero_img = Image.open(hero_image_path).convert("RGBA")
    template = Image.open(TEMPLATE_PATH).convert("RGBA")

    # 2) Resize hero to fill poster
    hero_bg = ImageOps.fit(hero_img, template.size, method=Image.BICUBIC)

    # 3) Build template overlay
    overlay = _make_template_overlay(template)

    # 4) Composite hero + overlay
    combined = hero_bg.copy()
    combined.paste(overlay, (0, 0), overlay)

    # 5) Clear arc band & draw our own text
    _clear_arc_band(combined)

    draw = ImageDraw.Draw(combined)
    w, _ = combined.size
    center_x = w // 2

    name_font = _load_font(40)
    shot_font = _load_font(32)

    name_text = user_name.upper()
    shot_text = power_label.upper()

    name_y = 235
    shot_y = 268

    def draw_centered(text: str, y: int, font: ImageFont.FreeTypeFont):
        draw.text(
            (center_x, y),
            text,
            font=font,
            fill=(255, 255, 255, 255),
            anchor="mm",
            stroke_width=3,
            stroke_fill=(0, 0, 0, 255),
        )

    draw_centered(name_text, name_y, name_font)
    draw_centered(shot_text, shot_y, shot_font)

    # 6) Save
    output_filename = f"thunderstrike_{uuid.uuid4().hex}.png"
    output_path = MEDIA_DIR / output_filename
    combined.save(output_path)

    return output_path
